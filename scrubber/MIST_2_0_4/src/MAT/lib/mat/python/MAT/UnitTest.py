# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# In this file, I extend unittest to handle a couple things for me.
# (1) I really want to use TestLoader.LoadTestsFromModule, but
# it doesn't play nicely with classes which shouldn't be instantiated.
# So I am going to add a way of marking classes as not instantiable,
# and filtering them out.

import unittest, os, sys, shutil

import MAT.Config

class TestLoader(unittest.TestLoader):

    def __init__(self, *args, **kw):
        unittest.TestLoader.__init__(self, *args, **kw)
        self.classNamesPat = None
        self.testNamesPat = None

    def filterClassNames(self, pat):
        import re
        self.classNamesPat = re.compile("^" + pat + "$")

    def filterTestNames(self, pat):
        import re
        self.testNamesPat = re.compile("^" + pat + "$")

    def loadTestsFromTestCase(self, testCaseClass):
        # If the class has a local value for "instantiable"
        # (which we can find with __dict__ but NOT with dir())
        # then use its value.
        loadable = True
        if testCaseClass.__dict__.has_key("instantiable"):
            loadable = testCaseClass.instantiable
        if loadable and (self.classNamesPat is not None):
            loadable = (self.classNamesPat.match(testCaseClass.__name__) is not None)
        if not loadable:
            return self.suiteClass([])
        elif self.testNamesPat is None:
            return unittest.TestLoader.loadTestsFromTestCase(self, testCaseClass)
        else:
            # We can load this class, but we have to check the names.            
            testNames = set(self.getTestCaseNames(testCaseClass))
            attrs = [attr for attr in testNames if self.testNamesPat.match(attr) is not None]
            if not attrs:
                return self.suiteClass([])
            else:
                # This is the hard one. We need to BLOCK tests which shouldn't
                # be applied. I'm going to use delattr, which can delete things
                # from the parent, too; but if the method doesn't match, it doesn't match.                
                for t in testNames - set(attrs):
                    delattr(testCaseClass, t)
                return unittest.TestLoader.loadTestsFromTestCase(self, testCaseClass)

# Common temp directory. This idiotic thing where setup/teardown
# happens for each test drives me nuts. We're going to use a
# common resource. I want a temp directory for everyone, which we can
# block from getting torn down.

# It would be nice for debug to block teardown, or to block teardown
# separately. It should all depend on the global state.

class TestContext(dict):

    def __init__(self, tmpDir = None, blockTeardown = False):
        self["TMPDIR"] = None
        self["MAT_PKG_HOME"] = MAT.Config.MATConfig["MAT_PKG_HOME"]
        self.blockTeardown = blockTeardown
        self.foundPluginFile = None
        if tmpDir:
            self.setTmpDir(tmpDir)
        self.localDir = {}

    def setLocal(self, d):
        for key, val in d.items():
            self.localDir[key] = val
            self[key] = val

    def clearLocal(self, keys):
        for key in keys:
            del self.localDir[key]
            del self[key]

    def setTmpDir(self, dir = None):
        if not self["TMPDIR"]:
            import tempfile
            if dir:
                self["TMPDIR"] = tempfile.mkdtemp("", tempfile.gettempprefix(), dir)
            else:
                self["TMPDIR"] = tempfile.mkdtemp()
            self.msg("Created temp directory %s." % self["TMPDIR"])

    def tearDown(self):
        if self["TMPDIR"] and (not self.blockTeardown):
            import shutil
            self.msg("Removing temporary directory.")
            shutil.rmtree(self["TMPDIR"])
        self.restorePlugins()
    
    def msg(self, str):
        print "\n##\n## %s\n##\n" % str

    # Move the current plugin list aside.
    def backupPlugins(self):
        # Don't do it if you've already done it.
        if self.foundPluginFile is None:
            matDir = os.path.split(os.path.abspath(__file__))[0]

            pluginFile = os.path.join(matDir, "Plugins", "plugins.txt")
        
            if os.path.exists(pluginFile):
                # Move the file.
                self.foundPluginFile = pluginFile
                shutil.move(pluginFile, pluginFile + ".bak")

    def restorePlugins(self):
        if self.foundPluginFile is not None:
            shutil.move(self.foundPluginFile + ".bak", self.foundPluginFile)
            self.foundPluginFile = None

_TEST_CONTEXT = None

def getTestContext(*args, **keys):
    global _TEST_CONTEXT
    if not _TEST_CONTEXT:
        _TEST_CONTEXT = TestContext(*args, **keys)
    return _TEST_CONTEXT

class MATTestCase(unittest.TestCase):

    instantiable = False

    def __init__(self, *args, **kw):
        unittest.TestCase.__init__(self, *args, **kw)
        self.testContext = getTestContext()
        # Grab the local settings.
        self.localSettings = self.testContext.localDir.copy()

    
    def _printDoc(self, doc, task):
        _jsonIO = MAT.DocumentIO.getDocumentIO("mat-json", task = task)
        _jsonIO.writeToTarget(doc, "-")
        # And now, let's get the JSON object and format a table.
        jObj = _jsonIO.renderJSONObj(doc)
        for aset in jObj["asets"]:
            if len(aset["annots"]) > 0:
                # Print the table.
                print aset["type"]
                print "=" * len(aset["type"])
                cols = []
                if aset["hasSpan"]:
                    cols += ["start", "end"]
                if aset["hasID"]:
                    cols.append("id")
                cols += [a["name"] for a in aset["attrs"]]
                strData = [[str(a) for a in r] + [""] * (len(cols) - len(r)) for r in aset["annots"]]
                widths = [max([len(cols[i])] + [len(r[i]) for r in strData]) for i in range(len(cols))]
                fmtString = "  ".join(["%-"+str(i)+"s" for i in widths])
                print fmtString % tuple(cols)
                print fmtString % tuple(["-"*i for i in widths])
                for row in strData:
                    print fmtString % tuple(row)
                print

    
    def _taskFromXML(self, name, xmlString):

        from MAT.PluginMgr import TASK_DESC, PluginTaskDescriptor
        from MAT.XMLNode import XMLNodeFromString
        t = PluginTaskDescriptor(name, "/tmp")
        xmlString = "<task name=''><workflows/>" + xmlString + "</task>"
        t.fromXML(XMLNodeFromString(xmlString, {"task": TASK_DESC}))
        return t

# Support for sequences of command lines. That's where I'll start.

class CmdlineTestMixin(MATTestCase):

    def __init__(self, *args, **kw):
        MATTestCase.__init__(self, *args, **kw)
        self.dirsToRemove = []

    def runCmdblock(self, header = None, tmpdir = None, cmd = None,
                    cmds = None, expectFailure = False):

        if header:
            print "\n# " + header + "\n"
        if tmpdir:
            self.testContext.setLocal(self.localSettings)
            try:
                tmpdir = tmpdir % self.testContext
            except KeyError, e:
                self.testContext.clearLocal(self.localSettings.keys())
                self.fail("unit test requires a setting for '%s'" % e.message)
            self.testContext.clearLocal(self.localSettings.keys())
            self.dirsToRemove.append(tmpdir)
            os.makedirs(tmpdir)
        if cmd:
            cmds = [cmd]
        for cmd in cmds:
            self.testContext.setLocal(self.localSettings)
            if type(cmd) is dict:
                # It has an availability section.
                if not cmd["availability"]:
                    continue
                cmd = cmd["cmd"]
            try:
                cmdToks = [ tok % self.testContext for tok in cmd]
            except KeyError, e:
                self.testContext.clearLocal(self.localSettings.keys())
                self.fail("unit test requires a setting for '%s'" % e.message)
            self.testContext.clearLocal(self.localSettings.keys())
            print "\n# Cmd: %s\n" % " ".join(cmdToks)
            # Execute and see what happens.
            # If we're on Windows, and the executable is a Python
            # executable, we have to add .cmd AND we have to
            # call python -x (because just calling the batch file
            # doesn't return the error properly; it appears
            # to be doing "cmd /c" under the hood somewhere, and that
            # returns errors from .exe but not from .bat). -x
            # skips the first line.
            if (sys.platform == "win32") and \
               (os.path.basename(os.path.dirname(cmdToks[0])) == "bin") and \
               (os.path.basename(os.path.dirname(os.path.dirname(cmdToks[0]))) == "MAT"):
                cmdToks[0] = cmdToks[0]+".cmd"
                cmdToks[0:0] = [sys.executable, "-x"]
            self.assertTrue(self._checkCmdResult(cmdToks, expectFailure))

    def _checkCmdResult(self, cmd, expectFailure):
        import subprocess
        exitStatus = subprocess.call(cmd)       
        if exitStatus != 0:
            return expectFailure
        else:
            return not expectFailure

    def tearDown(self):
        MATTestCase.tearDown(self)
        for dir in self.dirsToRemove:
            shutil.rmtree(dir)

class CmdlinesTestCase(CmdlineTestMixin):

    instantiable = False

    cmdBlock = None

    def runTest(self, expectFailure = False):
        
        if self.cmdBlock:
            self.runCmdblock(expectFailure = expectFailure, **self.cmdBlock)

# A test case using the sample domain will set up the plugin
# environment to use that directory, and tear it down again
# later. We might also want an initial test to make sure the
# environment setup/teardown works.

import MAT.PluginMgr
import shutil

class SampleTestCase(MATTestCase):

    instantiable = False    

    def setUp(self):

        # Do this in the context, not here, in case
        # the unittest fails and we need to restore on shutdown.
        self.testContext.backupPlugins()

    def tearDown(self):
        self.testContext.restorePlugins()

# And now, something which will allow me to run a Web service
# against a test. This is pretty much derived from start_with_callback in
# cherrypy/process/wspbus.py

import MAT.CherryPyService, cherrypy, threading

class CherryPyTestMixin:

    def runFunctionUnderCherryPy(self, f, wsKey, taggerService = False,
                                 threadCleanup = None):

        # Find an open port.
        import MAT.Utilities
        port = MAT.Utilities.findPort(7979)

        svc = MAT.CherryPyService.CherryPyService(port, localhostOnly = True,
                                                  workspaceKey = wsKey,
                                                  runTaggerService = taggerService)
        errDict = {"type": None, "info": None}
        
        def _callback(errDict):
            cherrypy.engine.wait(cherrypy.process.wspbus.states.STARTED)
            try:
                try:
                    f(port, wsKey)
                except self.failureException:
                    errDict["type"] = "fail"
                    if hasattr(self, "_exc_info"):
                        # Python 2.6.
                        errDict["info"] = self._exc_info()
                    else:
                        errDict["info"] = sys.exc_info()
                except KeyboardInterrupt:
                    errDict["type"] = "interrupt"
                except:
                    errDict["type"] = "err"
                    if hasattr(self, "_exc_info"):
                        # Python 2.6.
                        errDict["info"] = self._exc_info()
                    else:
                        errDict["info"] = sys.exc_info()
            finally:
                cherrypy.engine.exit()
                if threadCleanup:
                    threadCleanup()

        t = threading.Thread(target = _callback, args = (errDict,))
        t.start()

        svc.run()

        if errDict["type"] in ["fail", "err"]:
            raise errDict["info"][0], errDict["info"][1], errDict["info"][2]
        elif errDict["type"] == "interrupt":
            raise

class ThreadTest:

    def __init__(self, test):
        self.test = test

    def start(self, f, *args):
        
        self.errDict = {"type": None, "info": None}
        
        def _callback(errDict):
            try:
                f(*args)
            except self.test.failureException:
                errDict["type"] = "fail"
                if hasattr(self.test, "_exc_info"):
                    # Python 2.6.
                    errDict["info"] = self.test._exc_info()
                else:
                    errDict["info"] = sys.exc_info()
            except KeyboardInterrupt:
                errDict["type"] = "interrupt"
            except:
                errDict["type"] = "err"
                if hasattr(self.test, "_exc_info"):
                    # Python 2.6.
                    errDict["info"] = self.test._exc_info()
                else:
                    errDict["info"] = sys.exc_info()

        self.thread = threading.Thread(target = _callback, args = (self.errDict,))
        self.thread.start()

    def join(self):
        self.thread.join()
        if self.errDict["type"] in ["fail", "err"]:
            raise self.errDict["info"][0], self.errDict["info"][1], self.errDict["info"][2]
        elif self.errDict["type"] == "interrupt":
            raise
        
