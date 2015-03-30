# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# The idea here is that the guts of the CherryPy service is defined here -
# all the classes. The command line should only instantiate the class with
# the appropriate arguments and run it.

import MAT
import os, sys, cherrypy

#
# Constants
#

# Create a random workspace key.

import random, string
WORKSPACE_KEY = "".join([random.choice(string.ascii_letters + string.digits) for i in range(32)])

MAT_PKG_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

ALLOW_REMOTE_WORKSPACE_ACCESS = False

WORKSPACE_SEARCH_DIRS = None

#
# Classes
#

# I'm going to do something extremely evil. I'm going to use my own
# dispatcher to rewrite paths with cgi-bin in them. That way, I
# can use the regular hierarchy to implement CGI.

# The other thing I'm going to use the dispatch to do is convert
# things like tasks/<foo>/... to look for a task directory
# with the given name, and instantiate a MATImpl with the
# specified plugin restrictions.

# I'm going to isolate and store the service early here.

# For any task app, make any URL under the task available.

class TaskApp:

    def __init__(self, d, implClass = None):
        if implClass is None:
            implClass = MATImpl
        # d is the entry from plugins.byDir.
        self.root = implClass(enableStatic = True, pluginEntry = d)
        self.config = {}

class CherryPyMATDispatcher(cherrypy.dispatch.Dispatcher):    

    # We're going to specialize this someday.
    
    def _loadPlugins(self):
        return MAT.PluginMgr.LoadPlugins()

    def _taskApp(self, d):
        return TaskApp(d)        

    def _findPluginDir(self, pluginDirName):
        plugins = self._loadPlugins()
        if plugins is None:
            return None
        return plugins.getRecorded(pluginDirName)

    def find_handler(self, path):
        if path.startswith("/cgi-bin/MAT/"):
            path = "/MAT/cgi/" + path[len("/cgi-bin/MAT/"):]
            return cherrypy.dispatch.Dispatcher.find_handler(self, path)
        elif path.startswith("/tasks/"):
            # Hm. It appears that in order to be reentrant, I have to
            # reset request.app.root, but that's going to wreak havoc
            # with everything. So I need to insert a dummy app
            # just for the purposes of find_handler.
            components = path[1:].split("/", 2)
            if len(components) < 3:
                # I need something after /tasks/<dir>.
                # Go to the regular dispatcher, which will set up the
                # request properly, and yield 404.
                return cherrypy.dispatch.Dispatcher.find_handler(self, path)
            oldApp = cherrypy.request.app
            byDir = self._findPluginDir(components[1])
            if byDir is None:
                # Go to the regular dispatcher, which will set up the
                # request properly, and yield 404.
                return cherrypy.dispatch.Dispatcher.find_handler(self, path)
            cherrypy.request.app = self._taskApp(byDir)
            try:
                return cherrypy.dispatch.Dispatcher.find_handler(self, "/" + components[2])
            finally:
                cherrypy.request.app = oldApp
        else:
            return cherrypy.dispatch.Dispatcher.find_handler(self, path)

# This is the CherryPy object which implements CGI interaction.
# I want to pass all the keywords that come in, and ignore everything
# except tasks_of_interest.

# Problem: tasks_of_interest is possibly a list, possibly a single string,
# assuming it's even set. So we have to check this, using _getlist from WebService.

def _getSvc(tasks_of_interest = None):
    import socket
    localHost = socket.gethostbyname(socket.gethostname())
    if cherrypy.request.remote.ip == "127.0.0.1":
        remoteHost = localHost
    else:
        remoteHost = cherrypy.request.remote.ip
    from MAT.WebService import WebService, _getlist
    tasks_of_interest = _getlist(tasks_of_interest)
    if tasks_of_interest:
        plugins = MAT.PluginMgr.LoadPlugins()
        for v in plugins.values():
            if v.name not in tasks_of_interest:
                plugins.pruneTask(v)
    else:
        plugins = None
    svc = WebService(remoteHost, localHost, WORKSPACE_KEY,
                     plugins = plugins, allowRemoteWorkspaceAccess = ALLOW_REMOTE_WORKSPACE_ACCESS)
    cherrypy.request._matSvc = svc
    return svc

class WebServiceError(Exception):

    def __init__(self):
        import cgitb
        print cgitb.text(sys.exc_info())
        self.errVal = cgitb.html(sys.exc_info())

#######################################################
#
# The cherrypy CGI service
#
#######################################################

class CGI(object):

    def MATCGI_cgi(self, operation = None, tasks_of_interest = None, **kw):
        if operation is None:
            return _getSvc(tasks_of_interest = tasks_of_interest).show_main_page()
        elif hasattr(self, operation):
            return getattr(self, operation)(tasks_of_interest = tasks_of_interest, **kw)
        else:
            return "Error: unknown operation '%s'" % operation
    MATCGI_cgi.exposed = True

    def _debugWrapper(self, meth, *args, **kw):
        debug = MAT.ExecutionContext._DEBUG
        if debug:
            print >> sys.stderr, "[Incoming request: ", args, kw, "]"
        r = meth(*args, **kw)
        if debug:
            print >> sys.stderr, "[Request reply: ", r, "]"
        return r

    def _doNormalOperation(self, operation, tasks_of_interest, **kw):
        return self._debugWrapper(self._doNormalOperationInternal, operation, tasks_of_interest, **kw)

    def _doNormalOperationInternal(self, operation, tasks_of_interest, **kw):
        try:
            v = self._doNormalExecution(operation, tasks_of_interest, **kw)
            return self._doNormalReturn(v, 'application/json');
        except WebServiceError, e:
            return e.errVal

    def _doNormalExecution(self, operation, tasks_of_interest, **kw):
        # Don't use cgitb.enable - excepthook isn't what's handling the error.
        try:
            return getattr(_getSvc(tasks_of_interest = tasks_of_interest), operation)(**kw)
        except:
            raise WebServiceError()

    def _doNormalReturn(self, v, contentType):
        cherrypy.response.headers['content-type'] = contentType
        from MAT import json
        return json.dumps(v)

    def fetch_tasks(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("fetch_tasks", tasks_of_interest, **kw)
    fetch_tasks.exposed = True

    def load(self, **kw):
        return self._debugWrapper(self._loadInternal, **kw)
    load.exposed = True
    
    def _loadInternal(self, input = None, input_file = None, tasks_of_interest = None, **kw):
        # Note that the argument that's the form upload will
        # potentially be a fieldstorage object. See http.params_from_CGI_form.
        import cgi
        if isinstance(input, cgi.FieldStorage):
            input = input.value
        try:
            v = self._doNormalExecution("load", tasks_of_interest, input = input, input_file = input_file, **kw)
            # So the reason this is text/plain instead of application/json
            # is that it's done via a form upload, not via AJAX, and the
            # browser doesn't know what to do with application/json, so it
            # tries to download it instead of continue processing it. The PROBLEM
            # with that is that the error processing in mat_yui_connector.js
            # is looking for application/json, and if it doesn't find
            # it, it fails with the content. BUT it turns out that when
            # you use an uploadConversion in mat_yui_connector.js, the
            # content type is null, which is the other acceptable condition,
            # and the ONLY case where that happens is during load. So
            # as long as this happens during load, this setting is just
            # there to make the sure the browser doesn't capture the result
            # before Javascript has a chance to do the right thing.

            # BUT. And yet another but. It turns out that loadDocument is ALSO
            # done in demo_ui, as AJAX and NOT a form upload. I'm thinking
            # that if it's an input_file instead of an input, that's how I can tell.
            if input_file is not None:
                cType = 'application/json'
            else:
                cType = 'text/plain; charset=utf-8'
            return self._doNormalReturn(v, cType)
        except WebServiceError, e:
            return e.errVal

    # "ping" is used to check the server using GET, because POST
    # with a file upload doesn't return the error properly in YUI.
    def ping(self, **kw):
        cherrypy.response.headers['content-type'] = 'text/plain'
        return ""
    ping.exposed = True

    def steps(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("steps", tasks_of_interest, **kw)
    steps.exposed = True

    def undo_through(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("undo_through", tasks_of_interest, **kw)
    undo_through.exposed = True

    def document_reconciliation(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("document_reconciliation", tasks_of_interest, **kw)
    document_reconciliation.exposed = True

    def document_comparison(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("document_comparison", tasks_of_interest, **kw)
    document_comparison.exposed = True

    def update_reconciliation_document(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("update_reconciliation_document", tasks_of_interest, **kw)
    update_reconciliation_document.exposed = True

    def open_workspace(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("open_workspace", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    open_workspace.exposed = True

    def list_workspace_folder(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("list_workspace_folder", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    list_workspace_folder.exposed = True

    def open_workspace_file(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("open_workspace_file", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    open_workspace_file.exposed = True

    def import_into_workspace(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("import_into_workspace", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    import_into_workspace.exposed = True
    
    def do_workspace_operation(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("do_workspace_operation", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    do_workspace_operation.exposed = True

    def do_task_operation(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("do_task_operation", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    do_task_operation.exposed = True

    def do_toplevel_workspace_operation(self, tasks_of_interest = None, **kw):
        return self._doNormalOperation("do_toplevel_workspace_operation", tasks_of_interest, workspace_search_dirs = WORKSPACE_SEARCH_DIRS, **kw)
    do_toplevel_workspace_operation.exposed = True

    def _doSaveOperation(self, op, tasks_of_interest, contentType, **kw):
        return self._debugWrapper(self._doSaveOperationInternal, op, tasks_of_interest, contentType, **kw)

    def _doSaveOperationInternal(self, op, tasks_of_interest, contentType, save_transaction = None, **kw):
        try:
            v = self._doNormalExecution(op, tasks_of_interest, **kw)
            if v["success"]:
                cherrypy.response.headers['content-type'] = '%s; charset=utf-8' % contentType
                cherrypy.response.headers['content-disposition'] = 'attachment; filename=%s' % v["filename"]
                return v["bytes"]
            else:
                if save_transaction is not None:
                    v["save_transaction"] = save_transaction
                # It's gotta be a content type that won't trigger a download. Even text/plain isn't safe...
                return self._doNormalReturn(v, "text/html");
        except WebServiceError, e:            
            return e.errVal

    # Everything else should be text/plain, I think.
    CONTENT_TYPES = {
        ".xml": "text/xml",
        ".json": "application/json"
        }
        
    def save(self, tasks_of_interest = None, filename = None, **kw):
        # Infer the document type from the file extension. Safari will add something
        # incorrect if you don't.
        cType = "text/plain"
        if filename is not None:
            cType = self.CONTENT_TYPES.get(os.path.splitext(filename)[1].lower(), "text/plain")
        return self._doSaveOperation("save", tasks_of_interest, cType, filename = filename, **kw)
    save.exposed = True

    def export_reconciliation_doc(self, tasks_of_interest = None, for_save = False, **kw):
        if for_save:
            return self._doSaveOperation("export_reconciliation_doc", tasks_of_interest, "application/json", for_save = True, **kw)
        else:
            return self._doNormalOperation("export_reconciliation_doc", tasks_of_interest, **kw)
    export_reconciliation_doc.exposed = True

    def save_log(self, tasks_of_interest = None, **kw):
        return self._doSaveOperation("save_log", tasks_of_interest, "text/csv", **kw)
    save_log.exposed = True

#######################################################
#
# The cherrypy XMLRPC service
#
# Initially, this service will support tagging and nothing else.
# CLIENTS MUST SUPPORT THE xmlrpc NIL EXTENSION.
#
#######################################################

# And this one implements XMLRPC, I hope. 

class XMLRPC(cherrypy._cptools.XMLRPCController):

    def fetch_tasks(self, tasks_of_interest = None, **kw):
        [res, val] = _getSvc(tasks_of_interest = tasks_of_interest).fetch_tasks(**kw)
        if res is True:
            return val
        else:
            # This should send back an XMLRPC fault.
            raise Exception, val
    # fetch_tasks.exposed = True

    # task, workflow, file_type, encoding, input

    def load(self, task, workflow, file_type, encoding, input, tasks_of_interest = None, **kw):
        # Currently, the way the service is implemented, the input
        # is expected to be a byte sequence. So if the input
        # is of type unicode, then we need to encode it before
        # we proceed.
        if type(input) is type(u''):
            input = input.encode(encoding)
        d = _getSvc(tasks_of_interest = tasks_of_interest).load(input = input, task = task, workflow = workflow,
                                                                file_type = file_type, encoding = encoding, **kw)
        if d['success'] is True:
            return d['doc']
        else:
            raise Exception, d['error']             
    # load.exposed = True

    def tag(self, address, document):
        # The document will be an xmlrpc.Binary instance. I need to
        # convert that to the actual bytes.
        import xmlrpclib
        if isinstance(document, xmlrpclib.Binary):
            document = document.data
        if MAT.Tagger.TAGGER_BROKER is None:
            raise MAT.Command.ProcessError, "service unavailable"
        else:
            return MAT.Tagger.TAGGER_BROKER.request(address, document)
    tag.exposed = True    


#######################################################
#
# The cherrypy plugins
#
#######################################################

from cherrypy.process import plugins

#######################################################
#
# Plugin #1: the tagger broker service. This is a separate
# thread which manages the tagging.
#
#######################################################

# Here's a thread to start up a tagger server accumulator. This
# used to be MATServer, but I'm folding it into a thread here.
# Its children are managed by socket connections, using some ungodly
# complicated connection management code I wrote a long, long
# time ago. Perhaps replace it, someday.

from MAT.Tagger import TaggerBroker

class CherryPyTaggerBroker(TaggerBroker, plugins.SimplePlugin):

    def __init__(self, engine, stdout = sys.stdout):
        self.outfp = stdout
        plugins.SimplePlugin.__init__(self, engine)
        TaggerBroker.__init__(self, stdout = stdout)

    # This has to stop FIRST.

    def stop(self, *args, **kw):
        try:
            return TaggerBroker.stop(self, *args, **kw)
        finally:
            if self.outfp is not sys.stdout:
                self.outfp.close()
    # stop.priority = 25
    # No, 25 is the HTTP server.
    stop.priority = 10

#######################################################
#
# Plugin #2: the command loop. This is a separate thread which
# allows user control of the tool.
#
#######################################################
        
# And now, set up the command process thread. I don't really want
# to use wspbus.start_with_callback, because quickstart doesn't work
# with it and I don't want to duplicate the guts of quickstart.

# I want this to be a plugin, I think.

import cmd

HELP_MSG = """Web server command loop. Commands are:

exit       - exit the command loop and stop the Web server
loopexit   - exit the command loop, but leave the Web server running
taggerexit - shut down the tagger service, if it's running
restart    - restart the Web server
ws_key     - show the workspace key
help, ?    - this message"""

class WebLoop(cmd.Cmd, plugins.SimplePlugin):

    def __init__(self, engine, port, *args, **kw):
        self.exited = False
        self.cmdThread = None
        self.port = port
        if kw.has_key("disableInteractiveRestart"):
            self.disableInteractiveRestart = kw["disableInteractiveRestart"]
            del kw["disableInteractiveRestart"]
        else:
            self.disableInteractiveRestart = False
        cmd.Cmd.__init__(self, *args)
        if self.disableInteractiveRestart:
            import re
            self.HELP_MSG = re.compile("^restart.*$\n", re.M).sub("", HELP_MSG)
        else:
            self.HELP_MSG = HELP_MSG
        self.prompt = "Command: "
        plugins.SimplePlugin.__init__(self, engine)
        
        
    def start(self):
        if not self.cmdThread:
            import threading
            self.cmdThread = threading.Thread(target = self.cmdloop,
                                              args = ("\n\n".join(["Web server started on port %s.",
                                                                   self.HELP_MSG,
                                                                   "Workspace key is %s"]) %
                                                      (self.port, WORKSPACE_KEY),))
            self.cmdThread.setName("Command loop " + self.cmdThread.getName())
            self.cmdThread.start()

    def cmdloop(self, *args):
        cmd.raw_input = self.interruptable_raw_input
        # Just in case we want to customize it.
        cmd.Cmd.cmdloop(self, *args)

    def interruptable_raw_input(self, prompt):
        sys.stdout.write(prompt)
        sys.stdout.flush()
        # Now, don't call raw_input until there's
        # something to read. THIS WILL ONLY WORK ON UNIX.
        # I have to set raw_input in the cmd module to this
        # method.
        import time
        while True:
            if self.exited:
                return "loopexit"
            elif not self._pollStdin():
                time.sleep(0.1)
            else:
                return self.stdin.readline()
        
    def stop(self):
        # If stop was called, we want to exit this loop without
        # shutting down cherrypy, since someone already tried to
        # do that. The documentation for cmd implies strongly that
        # if you call onecmd, the right things will happen vis a vis
        # exiting the loop; but if you look at the 2.5 source, it
        # is quite clear that there's no way to exit the loop
        # except by enqueueing a line, which isn't really publicly
        # supported. So the first try will be to throw an error.
        # Well, that doesn't work, because this isn't called from
        # inside cmdloop.
        # And, unfortunately, right now it's reading from raw_input(),
        # and that blocks.
        # So until I set this up so that it's reading from somewhere
        # other than stdin, and stdin is feeding it input (and
        # how would we kill THAT thread?), C-c will require one more
        # newline to work.
        # Joining on the cmdThread doesn't work, either. Apparently,
        # I need to replace the reader with a reader which has a timeout.
        if self.cmdThread and (not self.exited):
            self.exited = True

    if sys.platform == "win32":
        def _pollStdin(self):
            import msvcrt
            # This doesn't wait for <enter>. Note, also, that this
            # doesn't work if you try to run it under a bash in
            # Cygwin, which is fine, because I don't support Cygwin anymore.
            return msvcrt.kbhit()
    else:
        def _pollStdin(self):
            import select
            return select.select([self.stdin], [], [], 0.0)[0]
            
    # Loop actions.

    def do_ws_key(self, line):
        print "Workspace key is %s" % WORKSPACE_KEY
        
    def do_help(self, *args):
        print self.HELP_MSG

    def do_loopexit(self, line):
        print "Exiting command loop."
        self.exited = True
        return True

    def do_taggerexit(self, line):
        if MAT.Tagger.TAGGER_BROKER is not None:
            MAT.Tagger.TAGGER_BROKER.stop()
            MAT.Tagger.TAGGER_BROKER.unsubscribe()
            MAT.Tagger.TAGGER_BROKER = None

    def do_exit(self, line):
        print "Exiting Web server."
        if not self.exited:
            self.exited = True
            self.bus.exit()
        return True

    def do_restart(self, line):
        if self.disableInteractiveRestart:
            return self.default(line)
        else:
            print "Restarting."
            # Hm. I THINK I can call restart on the engine.
            self.exited = True
            self.bus.restart()
            return True

#######################################################
#
# Plugin #3: Delayed restarter. Starting 10 minutes after
# midnight or later, restarts at midnight.
#
#######################################################

import datetime

class DelayedRestarter(cherrypy.process.plugins.Monitor):

    def __init__(self, engine):
        # start after this point.
        self.threshold = datetime.datetime.combine(datetime.datetime.today(), datetime.time(0, 10))
        self.started = False
        cherrypy.process.plugins.Monitor.__init__(self, engine, self._maybeRestart)

    def _maybeRestart(self):
        if (not self.started) and (datetime.datetime.now() > self.threshold):
            self.started = True
        if self.started:
            # Now that we've started, see if we're between 0 and 5 minutes after midnight.
            now = datetime.datetime.now()
            if (now.hour == 0) and (now.minute < 5):
                # Apparently, you have to cancel the thread.
                self.bus.log("Restarting at midnight.")
                self.thread.cancel()
                self.bus.log("Stopped thread %r." % self.thread.getName())
                self.bus.restart()

#######################################################
#
# Main class.
#
#######################################################

# These are the classes used to create the stack. Somehow, we
# need to convince this tool that the section is the right section.
# See the implementation of staticdir in CherryPy.

class MATImpl:

    def __init__(self, enableStatic = False, pluginEntry = None):
        # pluginDir is the byDir entry fullName, demo, tasks.
        self.pluginEntry = pluginEntry
        self.enableStatic = enableStatic

    def workbench(self, **kw):
        if self.pluginEntry:
            if not self.pluginEntry[2]:
                return "<h1>Error</h1><p>No tasks in this task directory."
            tasksOfInterest = [task.name for task in self.pluginEntry[2]]
        else:
            tasksOfInterest = None
        return _getSvc(tasks_of_interest = tasksOfInterest).show_page(os.path.join("web", "templates", "workbench_tpl.html"),
                                                                      tasksOfInterest = tasksOfInterest)
    workbench.exposed = True
    
    def demo(self, **kw):
        if self.pluginEntry:
            if not self.pluginEntry[1]:
                return "<h1>Error</h1><p>No demo found in this task directory."
            demo = self.pluginEntry[1]
            tasksOfInterest = demo.findRequiredTasks()
            return _getSvc(tasks_of_interest = tasksOfInterest).show_demo_page(demo)
        else:
            return "<h1>Error</h1><p>No demo named."
    demo.exposed = True

    cgi = CGI()

    xmlrpc = XMLRPC()

    def default(self, *args, **kw):
        if self.pluginEntry and self.enableStatic:
            from cherrypy.lib.static import serve_file
            return serve_file(os.path.join(self.pluginEntry[0], *args))
        raise cherrypy.NotFound()
    default.exposed = True

# The doc needs to be handled specially. Basically, if index.html is asked for,
# or if nothing is asked for, we open index.html, modify it according to the available
# task documentation, and return the string. All other documentation is handled
# as static files.

# If args == "html" or args == "html/index.html", do the postprocessing.
# Otherwise, raise notfound. The static files will be consulted first, and if
# they're not found, then the dynamic files will be called. But I have to make
# absolutely sure that index.html doesn't use static.

import re

class Doc:

    TASK_DOC_PAT = re.compile("^/MAT/doc/html/tasks/([^/]+)/(.*)$")

    def default(self, *args, **kw):
        # Ignore the args, because the args don't tell you whether
        # html has a trailing / or not. If it doesn't, the relative CSS
        # paths will be all screwed up, so I might as well just return
        # NotFound before anything awful happens.
        if (cherrypy.request.path_info == "/MAT/doc/html/") or \
           (cherrypy.request.path_info == "/MAT/doc/html/index.html"):
            # Seed the processing.
            from MAT.WebService import enhanceRootDocIndex
            s = enhanceRootDocIndex(MAT_PKG_HOME)
            cherrypy.response.headers['content-type'] = 'text/html'
            return s
        elif cherrypy.request.path_info == "/MAT/doc/html/BUNDLE_LICENSE":
            blPath = os.path.join(MAT_PKG_HOME, "BUNDLE_LICENSE")
            if os.path.exists(blPath):
                cherrypy.response.headers['content-type'] = 'text/plain'
                fp = open(blPath, "r")
                s = fp.read()
                fp.close()
                return s
        else:
            m = self.TASK_DOC_PAT.match(cherrypy.request.path_info)
            if m is not None:
                tName, pathRemainder = m.groups()
                # Gotta find the task documentation. This is the same sort of game
                # that was played in the dispatcher above.
                pDir = MAT.PluginMgr.LoadPlugins()
                byDir = pDir.getRecorded(tName)
                if byDir is None:
                    raise cherrypy.NotFound()
                # Make sure it works on Windows.
                p = os.path.join(byDir[0], *pathRemainder.split("/"))
                from cherrypy.lib.static import serve_file
                return serve_file(p)
        raise cherrypy.NotFound()
    default.exposed = True        

class RootMATImpl(MATImpl):

    doc = Doc()

    def pid(self, *args, **kw):
        return str(os.getpid())

    pid.exposed = True

class Root:

    # MAT = MATImpl()
    MAT = RootMATImpl()

# This server is commonly run on localhost, and if other servers
# are running localhost, this server may get cookies it's not supposed to get.
# We've seen cases where a bad cookie is sent, and this application breaks
# because a different server set a bad cookie in the browser. Since
# we don't use cookies at all, let's just squash them. I need to do this
# in two steps: the request needs to kill the cookie, and the application
# needs to host the new request type.

import Cookie

class DeafCookie(Cookie.SimpleCookie):

    def load(self, rawdata):
        return

class CookielessRequest(cherrypy._cprequest.Request):

    def process_headers(self):
        self.cookie = DeafCookie()
        return cherrypy._cprequest.Request.process_headers(self)

class CookielessApplication(cherrypy.Application):

    request_class = CookielessRequest

# There are site configurations and app configurations.
# The site configurations are global, so it's kind of fake
# that they're updated here. Bottom line: you can only have
# one CherryPyService instance.

class ServiceConfigurationException(Exception):
    pass

class CherryPyService:

    def __init__(self, port, localhostOnly = False, rootClass = Root,
                 dispatcherClass = CherryPyMATDispatcher,
                 noScreen = False, accessLog = None, errorLog = None,
                 taggerLog = None,  clearLogs = False, runCmdLoop = False,
                 disableInteractiveRestart = False,
                 runTaggerService = False, midnightRestart = False,
                 logRotationCount = None, workspaceKey = None,
                 workspaceKeyFile = None, workspaceKeyFileIsTemporary = False,
                 workspaceContainerDirectories = None,
                 allowRemoteWorkspaceAccess = False,
                 supersedeExistingServer = False,
                 outputLog = None,
                 asService = None):

        global WORKSPACE_KEY, ALLOW_REMOTE_WORKSPACE_ACCESS, WORKSPACE_SEARCH_DIRS
        
        if asService:
            if not os.path.exists(asService):
                try:
                    os.makedirs(asService)
                except os.error:
                    raise ServiceConfigurationException, ("Can't create log directory '%s'" % asService)
            elif not os.path.isdir(asService):
                raise ServiceConfigurationException, ("Requested log directory '%s' exists, but is not a directory." % asService)
            else:
                # Make sure you can write to it. The tempfile isn't vulnerable to
                # race conditions, and doesn't stay in the directory after it's closed.
                import tempfile
                try:
                    f = tempfile.TemporaryFile(dir=asService)
                    f.close()
                except os.error:
                    raise ServiceConfigurationException, ("Requested log directory '%s' exists, but can't be written to." % asService)
            # OK, now we know that the directory exists and can be written to.
            # This enforces a number of the boolean flags, and provides
            # nondefault values for some of the others.
            noScreen = True
            accessLog = accessLog or os.path.join(asService, "access.log")
            errorLog = errorLog or os.path.join(asService, "error.log")
            taggerLog = taggerLog or os.path.join(asService, "tagger.log")
            outputLog = outputLog or os.path.join(asService, "output.log")
            runCmdLoop = False
            # Not enforcing the tagger service or localhost only. These
            # are set to True and False by default in MATWeb, and I want to
            # allow people to be able to overwrite them.
            # runTaggerService = True
            # localhostOnly = False
            midnightRestart = True
            if logRotationCount is None:
                logRotationCount = 7
            allowRemoteWorkspaceAccess = True
            supersedeExistingServer = True

        # Only set this AFTERWARD.
        ALLOW_REMOTE_WORKSPACE_ACCESS = allowRemoteWorkspaceAccess                    
        WORKSPACE_SEARCH_DIRS = workspaceContainerDirectories

        if supersedeExistingServer:
            # Let's see if there is one.
            import urllib
            if MAT.Utilities.portTaken(port):
                # Hmmmm. There's a server on this port. Let's find out what its PID is, and
                # kill it. We'll ask it its pid, rather than remotely shut it down, since
                # adding a remote shutdown method is too mischievous - this way, if you don't
                # own the process, it won't be possible to kill it.
                # Ugh. There's a bug with proxy handling. At least on the Mac, localhost isn't
                # automatically unproxied, and in Python 2.6.5 and previous, there's a even uglier
                # bug in managing the port number on the Mac for proxy configuration.
                # Having localhost unproxied is, well, pretty much indisputable.
                os.environ["no_proxy"] = "localhost"
                import urllib
                pid = None
                try:
                    fp = urllib.urlopen("http://localhost:%d/MAT/pid" % port)
                    pid = fp.read()
                    fp.close()
                except:
                    # Well, we couldn't read the PID, but there's a server at this port,
                    # so we're not going to be able to get it.
                    raise ServiceConfigurationException, ("A server is running at localhost:%d, but it can't be determined if it's a MAT server. Giving up." % port)
                # At this point, the pd read SOMEthing. But lots of servers respond
                # with a 200 which describes a 404 error, rather than just giving 404.
                # So this might not be a pid.
                try:
                    pid = int(pid)
                except ValueError:
                    raise ServiceConfigurationException, ("A server is running at localhost:%d, but it can't be determined if it's a MAT server. Giving up." % port)
                # Try to kill it. This may also mean addressing a Windows omission.
                # We do this in Command.py.
                try:
                    MAT.Command._kill_process(pid)
                except os.error, e:
                    # Failed to kill it. Abort.
                    raise ServiceConfigurationException, ("Couldn't kill existing MATWeb server at port %d. Reason was: %s." % (port, e))
                # Now that it's been killed, wait till it's dead.
                # Sleep 10 seconds. If it isn't dead by then, give up.
                tries = 0
                import time
                while MAT.Utilities.portTaken(port):
                    time.sleep(1.0)
                    tries += 1
                    if tries > 10:
                        raise ServiceConfigurationException, "Killed existing MATWeb server, but port is still available after 10 tries"
                # Now, and only now, we can proceed.                

        # AAAGH. Originally, I was restarting with the workspace key on the
        # command line, but Seamus points out that then you can see the workspace key
        # on the command line in ps, which is kind of not what I intended. So
        # I'm going to introduce two new options: --workspace_key_file and
        # --workspace_key_file_is_temporary.

        # But I REALLY need to subclass the CherryPy Bus object, and
        # I can't, because it's created when CherryPy loads. So what I
        # need to do is redefine the _do_execv method. Someday, I'm going to
        # pay for all this. Hey! It turns out that I'm already redefining it
        # for win32. So I'm already going to hell...        

        if workspaceKeyFile is not None:
            import codecs
            fp = codecs.open(workspaceKeyFile, "r", "utf-8")
            WORKSPACE_KEY = fp.read()
            fp.close()
            if workspaceKeyFileIsTemporary:
                os.remove(workspaceKeyFile)
        elif workspaceKey is not None:
            WORKSPACE_KEY = workspaceKey            

        # Might as well update the site configuration at init time.

        self.siteConf = {"server.socket_port": port,
                         "server.socket_host": (localhostOnly and "127.0.0.1") or "0.0.0.0"}

        self.allLogs = []

        # Store some stuff:
        self.runCmdLoop = runCmdLoop
        self.disableInteractiveRestart = disableInteractiveRestart
        self.runTaggerService = runTaggerService
        self.port = port
        self.rootClass = rootClass
        self.dispatcherClass = dispatcherClass
        self.taggerLog = taggerLog
        self.outputLog = outputLog
        self.midnightRestart = midnightRestart
        self.logRotationCount = logRotationCount
        if self.logRotationCount is not None:
            self.logRotationCount = int(self.logRotationCount)
        self.clearLogs = clearLogs
        
        if noScreen:
            self.siteConf['log.screen'] = False
        if accessLog:
            self.siteConf['log.access_file'] = accessLog
            self.allLogs.append(accessLog)
        if errorLog:
            self.siteConf['log.error_file'] = errorLog
            self.allLogs.append(errorLog)
        if taggerLog:
            self.allLogs.append(taggerLog)
        if outputLog:
            self.allLogs.append(outputLog)
        
        HTML_ROOT = os.path.join(MAT_PKG_HOME, "web", "htdocs")
        YUI = MAT.Config.MATConfig["YUI_JS_LIB"]
        JCARAFE = os.path.dirname(MAT.Config.MATConfig["JCARAFE_JAR"])
        
        self.config = {'/': {'request.dispatch': self.dispatcherClass()},
                       '/MAT/css':  {'tools.staticdir.on': True,
                                     'tools.staticdir.dir': os.path.join(HTML_ROOT, "css")},
                       '/MAT/js':  {'tools.staticdir.on': True,
                                    'tools.staticdir.dir': os.path.join(HTML_ROOT, "js")},
                       '/MAT/doc':  {'tools.staticdir.on': True,
                                     'tools.staticdir.dir': os.path.join(HTML_ROOT, "doc")},
                       # We need to make sure this is processed by the default method in Doc.
                       '/MAT/doc/html/index.html':
                       {'tools.staticdir.on': False,
                        'tools.staticfile.on': False},
                       '/MAT/img':  {'tools.staticdir.on': True,
                                     'tools.staticdir.dir': os.path.join(HTML_ROOT, "img")},
                       '/MAT/doc/html/LICENSE':
                       {'tools.staticfile.on': True,
                        'tools.staticfile.filename': os.path.join(MAT_PKG_HOME, "LICENSE")},
                       '/MAT/doc/html/jcarafe_resources':
                       {'tools.staticdir.on': True,
                        'tools.staticdir.dir': os.path.join(JCARAFE, "resources")},
                       '/MAT/resources/' + os.path.basename(YUI):
                       {'tools.staticdir.on': True,
                        'tools.staticdir.dir': YUI}}

    # SAM 6/14/10: in order to respawn, I have to change the behavior
    # of cherrypy.engine, but you can't change the class before import,
    # and the engine gets created on import, so we just have to change
    # the method. The problem is that the default restarter calls the
    # Python executable, but in Windows, you may have a batch or cmd file
    # which can't be modified. This is copied from CherryPy 3.1.2.
    # Punchline: Restarting .cmd files, even if you get the quoting
    # right for spaces in pathnames, strands the console. So just bail.

    # But that's wrong, because I need to be able to restart if the
    # console interaction isn't connected, for services, etc., even on
    # Windows.

    # But wait! There's something else that needs to be done. If
    # we're restarting, we need to pass the workspace key in a temporary file.

    # So now, it restarts, cleanly, if it's detached from the tty, e.g., if --output_log
    # is set. I may not be able to do any better than that. I can't figure
    # out how to get it to respond to the kbd after restart in Windows;
    # when I said it strands the console above, I really meant that
    # it shares stdout and catches signals, but doesn't share stdin.
    # And I need to continue to own stdin.

    def _do_cherrypy_execv_for_win32(self, engine):
        import os
        if sys.stdout.isatty() and (os.path.splitext(sys.argv[0])[1] in [".cmd", ".bat"]):
            engine.log("Respawning not supported at the terminal for .cmd and .bat files. Exiting.")
        else:
            # We STILL can't do the default thing, because I can't call Python
            # on the .cmd file. But I CAN execv a .cmd file. So I have to copy _do_execv
            # from the guts of CherryPy.
            args = sys.argv[:]
            engine.log('Re-spawning %s' % ' '.join(args))
            args[0] = os.path.abspath(args[0])
            # This deals with spaces in filenames FAR better than os.execv.
            import subprocess
            subprocess.Popen(args)

    def _do_cherrypy_execv(self, engine):
        # If there's a command line option for --workspace_key, remove it.
        # Ditto --workspace_key_file, --workspace_key_file_is_temporary.
        try:
            i = sys.argv.index("--workspace_key")
            sys.argv[i:i+2] = []
        except ValueError:
            pass
        try:
            i = sys.argv.index("--workspace_key_file")
            sys.argv[i:i+2] = []
        except ValueError:
            pass
        try:
            i = sys.argv.index("--workspace_key_file_is_temporary")
            sys.argv[i:i+1] = []
        except ValueError:
            pass
        # Now, save the workspace key file to a temporary file.
        # Make sure the file is readable only by the user.
        import tempfile
        handle, fName = tempfile.mkstemp()
        # I can't figure out how to properly interact with this handle,
        # so we'll close it and start over...
        os.close(handle)
        fp = open(fName, "w")
        # Write utf-8-encoded bytes.
        fp.write(WORKSPACE_KEY.encode('utf-8'))
        fp.close()
        sys.argv += ["--workspace_key_file", fName, "--workspace_key_file_is_temporary"]
        if sys.platform == "win32":
            self._do_cherrypy_execv_for_win32(engine)
        else:
            cherrypy.process.wspbus.Bus._do_execv(engine)

    def run(self):

        cherrypy.engine._do_execv = lambda: self._do_cherrypy_execv(cherrypy.engine)

        # First thing: log rotation. This should happen before the
        # logs are removed; in other words, log rotation is like clearing the logs.
        # This has to happen before cherrypy updates the config, or knows
        # anything about the log files.

        if self.logRotationCount is not None:
            # Keep the last n logs.
            for f in self.allLogs:
                self._rotateLog(f, self.logRotationCount)
            
        if self.clearLogs:
            for f in self.allLogs:
                if os.path.exists(f):
                    os.remove(f)
            
        cherrypy.config.update(self.siteConf)

        # What this staticdir conf says is for ANY directory under here, if there's
        # an index.html file, use it.

        # Now, redirect stdout/stderr. Do it this way
        # so any C extensions that write to stdout/stderr will
        # do the right thing. This way, the workspace key will be in the
        # log if I redirect first. And if you close, you have to use os.close,
        # otherwise the dup will give you an IO error.
        
        if self.outputLog:
            fp = open(self.outputLog, "a")
            sys.stdout.flush()
            sys.stderr.flush()
            os.close(sys.stdout.fileno())
            os.close(sys.stderr.fileno())
            os.dup2(fp.fileno(), sys.stdout.fileno())
            os.dup2(fp.fileno(), sys.stderr.fileno())

        # The css, js, doc and resources are never invoked by any other path.
        # workbench, cgi, xmlrpc will, though.

        if self.runCmdLoop:
            cmdLoop = WebLoop(cherrypy.engine, self.port,
                              disableInteractiveRestart = self.disableInteractiveRestart)
            cmdLoop.subscribe()
        else:
            print "Workspace key is %s" % WORKSPACE_KEY
            sys.stdout.flush()

        if self.runTaggerService:
            if self.taggerLog:
                outputFp = open(self.taggerLog, "a")
            else:
                outputFp = sys.stdout
            MAT.Tagger.TAGGER_BROKER = CherryPyTaggerBroker(cherrypy.engine, stdout = outputFp)
            MAT.Tagger.TAGGER_BROKER.subscribe()

        if self.midnightRestart:
            # Introduce a timer thread which restarts the engine at midnight.
            # It's gotta be between 0 and 5 minutes after midnight, and we
            # ensure that we don't start checking until 10 minutes after midnight
            # (to avoid multiple restarts).
            DelayedRestarter(cherrypy.engine).subscribe()

        cherrypy.quickstart(CookielessApplication(self.rootClass()), config = self.config)

    def _rotateLog(self, logFile, countSuffix):
        # Don't rotate if the file doesn't exist.
        if not os.path.exists(logFile):
            return
        import glob
        for f in glob.glob(os.path.join(logFile, ".*")):
            suff = os.path.splitext(f)[1]
            if suff:
                try:
                    i = int(suff[1:])
                    # Remove everything that is beyond the count - 1.
                    if i > countSuffix - 1:
                        os.remove(file)
                except:
                    pass
        # Now, move all the files from n - 1 to n, descending.
        # This range will go down to 2.
        for i in range(countSuffix - 1, 1, -1):
            path = logFile + "." + str(i - 1)
            if os.path.exists(path):
                os.rename(path, logFile + "." + str(i))
        os.rename(logFile, logFile + ".1")
