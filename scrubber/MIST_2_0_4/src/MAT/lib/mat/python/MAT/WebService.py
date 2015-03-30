# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# In this file, I'm going to put most of the guts of the Web services,
# so that I can maintain a CGI script as I migrate to CherryPy.

# Utilities, to mimic getfirst and getlist for CGI forms.

import os, sys

def _getfirst(val):
    if val is None:
        return None
    elif type(val) in (list, tuple):
        return val[0]
    else:
        return val

def _getlist(val):
    if val is None:
        return None
    elif type(val) in (list, tuple):
        return val
    else:
        return [val]

import MAT

_jsonIO = MAT.DocumentIO.getDocumentIO('mat-json')

# For optionsFromCGI. There's probably a better
# way of doing this, but right now I don't want to
# fiddle with the rest of the code.

class FakeFieldStorage:

    def __init__(self, d, **kw):
        self.dict = d
        self.dict.update(kw)

    def keys(self):
        return self.dict.keys()

    def getfirst(self, key, default = None):
        try:
            return _getfirst(self.dict[key])
        except KeyError:
            return default

    def getlist(self, key, default = None):
        try:
            return _getlist(self.dict[key])
        except KeyError:
            return default        

def _readFile(path):
    fp = open(path, "r")
    s = fp.read()
    fp.close()
    return s

def filePatternExpand(file, **kw):

    # Create and render a page.
    s = _readFile(file)

    # Now, we need to replace
    # PAT_YUI_DIRECTORY
    # at least.

    replDir = {"PAT_YUI_DIRECTORY": os.path.basename(MAT.Config.MATConfig["YUI_JS_LIB"])}

    replDir.update(kw)

    for key, val in replDir.items():
        s = s.replace(key, val)

    return s

# This function simply checks to ensure that the
# client and server are the same machine. It APPEARS
# that when I ask for localhost, both remote and local
# addresses are 127.0.0.1.

class WSInfo:

    def __init__(self, svc, # These two are provided internally.
                 checkFolder = False, checkFile = False,
                 # The rest of these are from the kw args of the operation.
                 workspace_key = None, workspace_dir = None,
                 read_only = None, folder = None, file = None,
                 workspace_search_dirs = None,
                 **kw):
        self.svc = svc
        self.file = None
        self.folder = None
        self.success = True
        self.error = None
        self.aggregator = None
        self.workspace = None
        self.wsDirSuffix = None
        
        # Keys.

        wsKey = _getfirst(workspace_key)
        wsDir = _getfirst(workspace_dir)
        self.readOnly = readOnly = _getfirst(read_only) == "yes"

        if not self.svc._checkWorkspaceAccess():
            # Who knows how we might have gotten here.
            self.success = False
            self.error = "Server and client are not on the same machine, and remote access is not enabled."            
        elif (wsKey != self.svc.wsKey):
            self.success = False
            self.error = "Workspace key is incorrect"
        elif (wsDir is None) or (wsDir.strip() == ""):
            self.success = False
            self.error = "No workspace specified"
        elif (workspace_search_dirs is None) and (not os.path.isabs(wsDir)):
            self.success = False
            self.error = "Workspace directory path must be absolute."
        elif (workspace_search_dirs is not None) and os.path.isabs(wsDir):
            self.success = False
            self.error = "Workspace directory path cannot be absolute (workspace search dirs are specified)"
        else:
            try:
                # Now, try to find a workspace.
                if os.path.isabs(wsDir):
                    w = self.workspace = MAT.Workspace.Workspace(wsDir)
                    self.wsDirSuffix = self.workspace.dir
                else:
                    oneIsAbsolute = False
                    w = None
                    for d in workspace_search_dirs:
                        if os.path.isabs(d):
                            oneIsAbsolute = True
                            # Ugh. We have to be very paranoid here. If wsDir
                            # starts with .., you have to make sure you can't
                            # escape. The abspath of the search dir has to be
                            # a prefix of the abspath of the joined dir.
                            newD = os.path.abspath(os.path.join(d, wsDir))
                            if not newD.startswith(os.path.abspath(d)):
                                continue
                            try:
                                w = self.workspace = MAT.Workspace.Workspace(newD)
                                self.wsDirSuffix = wsDir
                                wsDir = newD
                                break
                            except:
                                # Nope, can't open it.
                                continue
                    if not oneIsAbsolute:
                        self.success = False
                        self.error = "None of the workspace container directories are absolute pathnames"
                    elif w is None:
                        self.success = False
                        self.error = "Couldn't find an openable workspace at path '%s' in any of the workspace container directories" % wsDir
                if self.success:
                    if not w.dirsAccessible(forWriting = not readOnly):
                        self.success = False
                        self.error = "Server does not have appropriate permissions on workspace."
                    else:
                        if checkFolder:
                            folder = self.folder = _getfirst(folder)
                            if not w.folders.has_key(folder):
                                self.success = False
                                self.error =  "Unknown folder '%s'." % folder
                                return
                        if checkFile:
                            file = self.file = _getfirst(file)
                            if file is None:
                                self.success = False
                                self.error = "No file basename specified."
                                return
                        form = FakeFieldStorage(kw.copy(), folder = folder, file = file)
                        self.aggregator = MAT.Operation.CGIOpArgumentAggregator(form)
                        self.params = kw
            except MAT.Workspace.WorkspaceError, e:
                self.success = False
                self.error = str(e)
            except IOError, e:
                self.success = False
                self.error = "File access error while opening workspace: " + str(e)

class WebService:

    def __init__(self, remoteAddr, localAddr, wsKey, plugins = None,
                 allowRemoteWorkspaceAccess = False):
        self.remoteAddr = remoteAddr
        self.localAddr = localAddr
        self.allowRemoteWorkspaceAccess = allowRemoteWorkspaceAccess
        self.wsKey = wsKey
        # If this is specified, the plugins will be loaded, but only
        # those from this plugin dir basename will be returned.
        self.plugins = plugins
        if self.plugins is None:
            self.plugins = MAT.PluginMgr.LoadPlugins()

    #
    # Utility methods.
    #

    def _checkWorkspaceAccess(self):
        return self.allowRemoteWorkspaceAccess or (self.remoteAddr == self.localAddr)
    
    # This utility is used both by load and by steps. The file we're
    # loading may come from a demo, in which case I want to use the demo
    # prefix rather than the task.

    def _checkTaskInformation(self, steps, input = None, input_file = None,
                              demo = None, task = None, workflow = None,
                              workflowCanBeNull = False,
                              **kw):

        TASK = _getfirst(task)

        WORKFLOW = _getfirst(workflow)

        if (TASK is None) or ((WORKFLOW is None) and (not workflowCanBeNull)):

            return False, "app or workflow not specified", None
        
        plugins = self.plugins

        literalTaskObj = plugins.getTask(TASK)

        if literalTaskObj is None:
            return False, ("task %s not found" % TASK), None

        INPUT = _getfirst(input)

        if INPUT is None:

            f = _getfirst(input_file)
            if f is not None:
                # It's either an absolute path, or it's somewhere underneath
                # the task or the demo, if there is a demo.
                if not os.path.isabs(f):
                    if demo is not None:
                        root = plugins.getRecorded(demo)[0]
                    else:
                        root = literalTaskObj.taskRoot
                    f = os.path.join(root, f)
                try:
                    INPUT = _readFile(f)
                except IOError, e:
                    return False, str(e), None

        if INPUT is None:

            return False, "no input", None

        # Start with the nominal task to get the parameters. The
        # operational task we get later.
        form = FakeFieldStorage(kw.copy(), input = input, task = task, workflow = workflow)
        aggregator = MAT.Operation.CGIOpArgumentAggregator(form)
        literalTaskObj.addOptions(aggregator)
        pDir = aggregator.extract()
        try:
            TASK_OBJ = literalTaskObj.getTaskImplementation(WORKFLOW, steps, **pDir)
            if TASK_OBJ is None:
                return False, ("operational task for %s not found" % TASK), None
        except KeyError:
            return False, ("operational task for %s not found" % TASK), None
        except MAT.PluginMgr.PluginError, e:
            return False, ("operational task for %s not found: %s" % (TASK, str(e))), None
        return True, None, (plugins, pDir, TASK_OBJ, INPUT, WORKFLOW)

    import re

    INITSPACE = re.compile("^[ ]+")

    def _shortHTMLBacktrace(self, (t, val, tb)):
        finalList = []
        import traceback, cgi
        for s in traceback.format_tb(tb):
            s = cgi.escape(s)
            m = self.INITSPACE.match(s)
            if m is not None:
                s = ("&nbsp;" * m.end()) + s[m.end():]
            s = s.replace("\n", "<br>")
            finalList.append(s)
        return "<div>" + "\n".join(finalList) + "</div>"

    def show_main_page(self, **kw):
        
        # In order to find the web template, we need to compute
        # the root from where we are, which is lib/mat/python/MAT
        # in the distribution. We want web/templates/.

        return self.show_page(os.path.join("web", "templates", "workbench_tpl.html"), **kw)

    def show_demo_page(self, demo, **kw):
        
        from MAT import json
        kw.update(PAT_DEMO_TITLE = demo.name,
                  PAT_DEMO_DESCRIPTION = demo.description,
                  PAT_DEMO_NAME = demo.webDir,
                  PAT_DEMO_CONFIGURATION = json.dumps(demo.activities))
        
        # In order to find the web template, we need to compute
        # the root from where we are, which is lib/mat/python/MAT
        # in the distribution. We want web/templates/.

        return self.show_page(os.path.join("web", "templates", "demo_tpl.html"), **kw)

    def show_page(self, page, inline_js = True, tasksOfInterest = None, **kw):

        matDir = os.path.dirname(os.path.abspath(__file__))

        MAT_PKG_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(matDir))))

        # Now, we need to replace
        # PAT_TASK_JAVASCRIPT
        # PAT_TASK_CSS
        # PAT_TASKS_OF_INTEREST
        
        replDir = {"PAT_TASKS_OF_INTEREST": "null"}

        if tasksOfInterest is not None:
            from MAT import json
            replDir["PAT_TASKS_OF_INTEREST"] = json.dumps(tasksOfInterest)            

        # The first few are in the settings; the last two are the contents of all the
        # files for all the tasks we know of.

        # Odd: PAT_ used to be MF_, but that worked for the second two
        # and not for the first, in CGI. Outside CGI, it worked fine.
        # No clue.

        plugins = self.plugins

        allJS = plugins.getJSFiles()
        allCSS = plugins.getCSSFiles()

        # print >> sys.stderr, "Plugging in JS files:", " ".join(allJS)
        # print >> sys.stderr, "Plugging in CSS files:", " ".join(allCSS)

        jsString = '<script type="text/javascript">\n' + "\n".join([_readFile(p) for p in allJS]) + "\n</script>"
        cssString = '<style type="text/css">\n' + "\n".join([_readFile(p) for p in allCSS]) + "\n</style>"

        replDir["PAT_TASK_JAVASCRIPT"] = jsString
        replDir["PAT_TASK_CSS"] = cssString
        replDir["PAT_MAT_VERSION"] = MAT.Config.MATConfig.getMATVersion()

        replDir.update(kw)
    
        # Create and render a page.
        return filePatternExpand(os.path.join(MAT_PKG_HOME, page), **replDir)

    # Currently, input is a JSON string. Returns the contents of the file
    # and the recommended filename.

    def _computeSaveFilename(self, filename):
        fname = _getfirst(filename)
        if not fname:
            return "foo.txt"
        else:
            return os.path.split(fname)[1]        
    
    def save(self, input = "", filename = None, out_type = None, task = None, **kw):

        TASK = _getfirst(task)        
        plugins = self.plugins
        literalTaskObj = plugins.getTask(TASK)
        
        # Rich JSON documents are ALWAYS saved as utf-8.

        INPUT = _getfirst(input)
        outType = _getfirst(out_type)
        # INPUT is a JSON rich document. If the out type is
        # mat-json, then just echo the input. Otherwise, digest it
        # and write out the appropriate format.
        INPUT = INPUT.decode('utf-8')        
        if outType == "mat-json":
            return {"success": True, "bytes": INPUT.encode('utf-8'), "filename": self._computeSaveFilename(filename)}
        else:
            INPUT = _jsonIO.readFromUnicodeString(INPUT, taskSeed = literalTaskObj)
            return self._save(INPUT, outType, filename, literalTaskObj, **kw)

    def _save(self, doc, outType, filename, literalTaskObj, **kw):
        
        # Convert the CGI keywords into useful keyword arguments.
        ioCls = MAT.DocumentIO.getDocumentIOClass(outType)
        form = FakeFieldStorage(kw.copy())
        aggregator = MAT.Operation.CGIOpArgumentAggregator(form)
        ioCls.addOutputOptions(aggregator)
        pDir = aggregator.extract()

        return {"success": True,
                "bytes": ioCls(task = literalTaskObj, **pDir).writeToByteSequence(doc, encoding = "utf-8"),
                "filename": self._computeSaveFilename(filename)}

    # In order to save a reconciliation document, we need to first run it through its
    # updates, and then return the document to the frontend for redisplay, and THEN
    # the frontend can do a generic save.

    def _updateAndReconcile(self, literalTaskObj, recDoc):
        
        from MAT.ReconciliationPhase import HumanDecisionPhase
        # The annotator that the non-workspace stuff uses is "unknown human"
        pObj = HumanDecisionPhase(human_decision_user = "unknown human")
        pObj.updateSavedSegments(literalTaskObj, recDoc)
        vDict = recDoc._votesForSegments()
        # Reconcile. We don't need to check if it's all done.
        pObj.reconcile(recDoc, "unknown human", vDict)
    
    def update_reconciliation_document(self, input = None, task = None, **kw):
        
        TASK = _getfirst(task)        
        plugins = self.plugins
        literalTaskObj = plugins.getTask(TASK)

        INPUT = _jsonIO.readFromUnicodeString(_getfirst(input).decode('utf-8'), taskSeed = literalTaskObj)

        # So now we have a reconciliation document.

        self._updateAndReconcile(literalTaskObj, INPUT)        

        # Now, every segment in the reconciliation doc should be marked "to review".
        # NO! Only the segments which are human gold. The reason I have to do this
        # is that it's as if the document is being "reopened" - updateSavedSegments
        # clears out to_review.
        for seg in INPUT.getAnnotations(["SEGMENT"]):
            if seg["status"] == "human gold":
                seg["to_review"] = "yes"

        return {"success": True, "doc": _jsonIO.renderJSONObj(INPUT)}

    # If it's not fully reconciled, this should barf, I think. Actually, I
    # think export() should barf.
    
    def export_reconciliation_doc(self, input = "", filename = None, out_type = None, task = None, for_save = False, **kw):

        from MAT.ReconciliationDocument import ReconciliationError
        
        TASK = _getfirst(task)        
        plugins = self.plugins
        literalTaskObj = plugins.getTask(TASK)

        # Rich JSON documents are ALWAYS saved as utf-8.

        outType = _getfirst(out_type)
        recDoc = _jsonIO.readFromUnicodeString(_getfirst(input).decode('utf-8'), taskSeed = literalTaskObj)
        # Just in case. This should already have been done, but just in case.
        self._updateAndReconcile(literalTaskObj, recDoc)
        try:
            exportedDoc = recDoc.export(literalTaskObj);
            if for_save:
                return self._save(exportedDoc, outType, filename, literalTaskObj, **kw)
            else:
                return {"success": True, "doc": _jsonIO.renderJSONObj(exportedDoc)}
        except ReconciliationError, e:
            return {"success": False, "error": str(e)}

    # Currently, log is a JSON string (not an object). Returns the
    # contents of the CSV file.

    def save_log(self, log = None, **kw):

        # I'm going to do the log mangling here, because it's really not
        # relevant to anything else in the system. Not much; originally I
        # was doing some raw logging in the frontend and augmenting it
        # here, but that turned out to be unwieldy, so I moved all the
        # ugliness into the frontend, and here we just turn it into CSV.

        from MAT import json
        log = json.loads(_getfirst(log))
        import datetime
        fname = datetime.datetime.now().strftime("log_%Y%m%d_%H_%M_%S.csv")

        # The logs consist of a couple messages which the Yahoo logger itself
        # provides, but mostly ours. It's a list of hashes. Most of them have
        # details like gesture, file, etc., but some like log_start, etc., don't.

        # NOTE: the msg entries will only be objects for the log
        # elements we saved. We'll also be getting other stuff from
        # the log, which are just strings. We'll be skipping these.

        convertedLogs = []
        headers = ["timestamp", "rel_seconds", "gesture", "file", "folder", "workspace", "window", "action"]
        extraHeaders = []

        startTime = None

        import time

        for msg in log:
            # Let's not deal with that awful overflow.
            # Let's do our calculations in ms, and then
            # move the decimal point.
            t = msg["ms"]
            if startTime is None:
                startTime = t
                diffTime = "0.0"
            else:
                # I want to ensure that the time is
                # consistently marked in ms.
                diffTime = "%04d" % (t - startTime,)
                diffTime = diffTime[:-3] + "." + diffTime[-3:]
            remainderStr = "%.03f" % (float(t) / 1000.0,)
            remainder = remainderStr[remainderStr.find("."):]
            # For some reason, Excel barfs on the time string when
            # it has a space in it.
            ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(float(t) / 1000.0)) + remainder
            # Now, get rid of the milliseconds.
            del msg["ms"]
            msg["timestamp"] = ts
            msg["rel_seconds"] = diffTime

            for key in msg.keys():
                if (key not in headers) and (key not in extraHeaders):
                    extraHeaders.append(key)

            convertedLogs.append(msg)

        extraHeaders.sort()

        hDict = dict([(a, a) for a in headers + extraHeaders])

        convertedLogs[0:0] = [hDict]

        import csv, cStringIO

        output = cStringIO.StringIO()
        
        csv.DictWriter(output, headers + extraHeaders, "").writerows(convertedLogs)
        v = output.getvalue()
        output.close()
        return {"success": True, "bytes": v, "filename": fname}

    # Returns an object suitable for converting to JSON.
    
    def fetch_tasks(self, **kw):

        try:
            plugins = self.plugins
            # Now, we serialize that information appropriately.
            dir = plugins.getCGIMetadata()
            if not dir:
                pNames = [False, "Error: no tasks found"]
            else:
                pNames = [True, {"metadata": dir, "workspace_access": self._checkWorkspaceAccess() } ]
        except Exception, e:
            # pNames = [False, str(e) + "\n" + "".join(traceback.format_tb(sys.exc_info()[2]))]
            pNames = [False, str(e) + "\n" + self._shortHTMLBacktrace(sys.exc_info())]

        return pNames

    # "Loads" a file, in other words, converts it into an object suitable
    # for rendering to JSON.

    def load(self, file_type = None, encoding = None, **kw):

        result = {"success": True,
                  "error": None}

        success, errStr, res = self._checkTaskInformation([], file_type = file_type,
                                                          workflowCanBeNull = True,
                                                          encoding = encoding, **kw)

        if not success:
            result["success"] = False
            result["error"] = errStr

        else:
            ignore, ignore, TASK_OBJ, INPUT, WORKFLOW = res
            FILE_TYPE = _getfirst(file_type)

            ENCODING = _getfirst(encoding)
            
            # Convert the CGI keywords into useful keyword arguments.
            ioCls = MAT.DocumentIO.getDocumentIOClass(FILE_TYPE)
            form = FakeFieldStorage(kw.copy())
            aggregator = MAT.Operation.CGIOpArgumentAggregator(form)
            ioCls.addInputOptions(aggregator)
            pDir = aggregator.extract()
            ioObj = ioCls(encoding = ENCODING, task = TASK_OBJ, **pDir)
            
            try:
                INPUT = ioObj.readFromByteSequence(INPUT)
                result["doc"] = _jsonIO.renderJSONObj(INPUT)
            except (MAT.Document.LoadError, MAT.Annotation.AnnotationError), e:
                result["success"] = False
                result["error"] = str(e)
            except LookupError, e:
                result["success"] = False
                result["error"] = str(e)

        return result

    # steps goes forward, undo_through goes backward. They have almost
    # the same signature and procedure, except steps has steps and
    # undo_through has undo_through. Duh. undo_through won't call
    # setSuccess.
        
    def steps(self, steps = None, undo_through = None, **kw):

        OutputObj = {"error": None,
                     "errorStep": None,
                     "successes": []}

        STEPS = []

        v = _getfirst(steps)

        if v:
            STEPS = v.split(",")

        UNDO_THROUGH = None

        INPUT = self._stepsCore(OutputObj, STEPS, UNDO_THROUGH, **kw)

        # Make sure all the annotated documents are encoded.

        for entry in OutputObj["successes"]:
            if isinstance(entry["val"], MAT.Document.AnnotatedDoc):
                entry["val"] = _jsonIO.renderJSONObj(entry["val"])

        return OutputObj

    def undo_through(self, steps = None, undo_through = None, **kw):

        OutputObj = {"error": None,
                     "errorStep": None,
                     "stepsUndone": []}
        STEPS = []

        UNDO_THROUGH = _getfirst(undo_through)

        INPUT = self._stepsCore(OutputObj, STEPS, UNDO_THROUGH, **kw)

        # Insert the modified document.
        OutputObj["doc"] = _jsonIO.renderJSONObj(INPUT)

        return OutputObj

    def _stepsCore(self, outputObj, steps, undoThrough, **kw):

        STEPS = steps
        UNDO_THROUGH = undoThrough
        OutputObj = outputObj

        def setError(obj, err, step):
            obj["error"] = err
            obj["errorStep"] = step

        LoadFailed = False

        success, errStr, res = self._checkTaskInformation(STEPS, **kw)

        if not success:
            setError(OutputObj, errStr, "[init]")
            LoadFailed = True

        INPUT = None

        if not LoadFailed:

            plugins, pDir, TASK_OBJ, INPUT, WORKFLOW = res

            # Here's the output format. It's a hash of three elements: error (None if
            # there's no error), errorStep (None if there's no error), and
            # a list of success hashes, which have a val and steps.
            # See OutputObj above. An error always terminates the processing,
            # so on the client, you process the successes and then the error.
            # The steps should be in order of execution, and so should the
            # successes. It's not EXACTLY enforced.

            from MAT.ToolChain import MATEngine

            class CGIMATEngine(MATEngine):

                # Ignore the possibility of batch processing for the moment.

                def __init__(self, oObj, *args, **kw):
                    self.oObj = oObj
                    MATEngine.__init__(self, *args, **kw)

                def ReportStepResult(self, stepObj, fname, iData):
                    stepName = stepObj.stepName
                    # Errors are raised if the step isn't successful.
                    # If the step is a multi-step, the steps it's a
                    # proxy for must also be reported; otherwise
                    # the front end won't capture that those "true" steps
                    # were created, and we'll encounter a bug where
                    # you can't undo the multistep unless there's been
                    # an explicit special multistep undo class introduced.
                    # But this is only necessary for the forward
                    # direction. Well, maybe not.
                    steps = [stepName]
                    if isinstance(stepObj, MAT.PluginMgr.MultiStep):
                        steps += [p.stepName for p in stepObj.proxies]
                    obj = self.oObj
                    for entry in obj["successes"]:
                        if iData is entry["val"]:
                            entry["steps"] += steps
                            return
                    obj["successes"].append({"val": iData, "steps": steps})

                def ReportBatchUndoStepResult(self, stepObj, iDataPairs):
                    steps = [stepObj.stepName]
                    if isinstance(stepObj, MAT.PluginMgr.MultiStep):
                        steps += [p.stepName for p in stepObj.proxies]
                    self.oObj["stepsUndone"] += steps

            try:
                INPUT = _jsonIO.readFromByteSequence(INPUT, taskSeed = TASK_OBJ)
            except MAT.Document.LoadError, e:
                LoadFailed = True
                setError(OutputObj, str(e), "[init]")

            if not LoadFailed:
                try:
                    engine = CGIMATEngine(OutputObj, taskObj = TASK_OBJ,
                                          workflow = WORKFLOW)
                    engine.RunDataPairs([("<cgi>", INPUT)], steps = STEPS[:],
                                        pluginDir = plugins, undoThrough = UNDO_THROUGH, **pDir)
                except MAT.Error.MATError, e:
                    if e.errstr == "":
                        errstr = "<no information>"
                    elif e.errstr is None:
                        errstr = "<unknown>"
                    else:
                        errstr = str(e.errstr)
                        #import traceback
                        #errstr = errstr + traceback.format_exc()
                    setError(OutputObj, errstr, e.phase)

        return INPUT

    def document_reconciliation(self, **kw):
        
        result = {"success": True,
                  "error": None}

        success, errStr, res = self._checkTaskInformation([], workflowCanBeNull = True, **kw)

        if not success:
            result["success"] = False
            result["error"] = errStr

        else:

            plugins, pDir, TASK_OBJ, INPUT, WORKFLOW = res
            # INPUT is a string which is a LIST of document JSON objects.
            from MAT import json
            docs = None
            try:
                docs = []
                for d in json.loads(INPUT.decode('utf-8')):
                    doc = TASK_OBJ.newDocument()
                    docs.append(doc)
                    _jsonIO._deserializeFromJSON(d, doc)
            except MAT.Document.LoadError, e:
                result["success"] = False
                result["error"] = str(e)

            if docs is not None:
                # So here, what we do is create a reconciliation document. The issue with
                # this is that we need to figure out which portions of the incoming
                # documents should be considered "gold". We may want an option to
                # preserve the incoming segmentation, and otherwise just assign a single
                # document-size segment with the document itself as the annotator.

                # We'll have two options to save: either to save this directly as
                # a reconciliation document, or to export it as a reconciled document.
                # The other issue is what happens when we load - the reconciliation document
                # should automatically open a reconciliation pane, which means that
                # we'd need to deal with the panes in the load callback, rather than
                # in the load prep. But otherwise, how do I load a reconciliation document?
                # I'd need a separate menu item. Hmmm.
                from MAT.ReconciliationDocument import ReconciliationDoc

                # Preprocess the documents. In this case, all the documents
                # must be marked human gold, and the annotator should be
                # the document itself.
                i = 1
                wholeZoneStep = None
                for doc in docs:
                    annotator = "doc" + str(i)
                    i += 1
                    segs = doc.getAnnotations(["SEGMENT"])
                    if not segs:
                        zones = doc.getAnnotations(TASK_OBJ.getAnnotationTypesByCategory("zone"))
                        if zones:
                            # Segment it.
                            for z in zones:
                                doc.createAnnotation(z.start, z.end, "SEGMENT",
                                                     {"annotator": annotator, "status": "human gold"})
                        else:
                            # If there are no zones and no segments, then make one big zone and segment.
                            if not wholeZoneStep:
                                wholeZoneStep = MAT.PluginMgr.WholeZoneStep("zone", TASK_OBJ, None)
                            wholeZoneStep.do(doc)
                            for seg in doc.getAnnotations(["SEGMENT"]):
                                seg["annotator"] = annotator
                                seg["status"] = "human gold"
                    else:
                        for seg in segs:
                            seg["annotator"] = annotator
                            seg["status"] = "human gold"
                
                recDoc = ReconciliationDoc.generateReconciliationDocument(TASK_OBJ, docs,  verbose = None)

                # Now, every segment in the reconciliation doc should be marked "to review".
                # NO! Only the segments which are human gold.
                for seg in recDoc.getAnnotations(["SEGMENT"]):
                    if seg["status"] == "human gold":
                        seg["to_review"] = "yes"
                
                result["doc"] = _jsonIO.renderJSONObj(recDoc)
        
        return result

    def document_comparison(self, labels = None, **kw):
        
        result = {"success": True,
                  "error": None}

        success, errStr, res = self._checkTaskInformation([], workflowCanBeNull = True, **kw)

        if not success:
            result["success"] = False
            result["error"] = errStr

        else:

            plugins, pDir, TASK_OBJ, INPUT, WORKFLOW = res
            # INPUT is a string which is a LIST of document JSON objects.
            from MAT import json
            docs = None
            try:
                docs = []
                for d in json.loads(INPUT.decode('utf-8')):
                    doc = TASK_OBJ.newDocument()
                    docs.append(doc)
                    _jsonIO._deserializeFromJSON(d, doc)
            except MAT.Document.LoadError, e:
                result["success"] = False
                result["error"] = str(e)

            if docs is not None:
                # So here, what we do is create a comparison document.
                from MAT.ComparisonDocument import generateComparisonDocument
                pivotLabel = None
                otherLabels = None
                if labels:
                    pivotLabel = labels[0]
                    otherLabels = labels[1:]
                try:
                    compDoc = generateComparisonDocument(TASK_OBJ, docs[0], docs[1:],
                                                         pivotLabel = pivotLabel, otherLabels = otherLabels)
                
                    result["doc"] = _jsonIO.renderJSONObj(compDoc)
                except MAT.Pair.PairingError, e:
                    result["success"] = False
                    result["error"] = str(e)
        
        return result

    # Now, the workspace stuff. I don't want to keep duplicating code,
    # so I'm going to refactor this so that the checks are progressive.
    # First, we need to check the workspace. If that passes, we may need
    # to check the folder, and if that passes, we may need to check the
    # file. Then there's creating the appropriate field storage.

    def open_workspace(self, user = None, **kw):

        wsInfo = WSInfo(self, **kw)

        if not wsInfo.success:
            result = {"success": False,
                      "error": wsInfo.error}
        else:
            # First, we have to check if the workspace is being
            # opened with a user. If it's being opened read-only,
            # you don't need one, but if not, you do, and the
            # user has to be registered. I check it here and not in
            # WSInfo because the logic is dealt with separately
            # when a document is opened.

            if user:
                user = user.strip()

            if user and (not wsInfo.workspace.getDB().userIsRegistered(user)):
                result = {"success": False,
                          "error": "User '%s' is not registered in workspace" % user}
            elif (not user) and (not wsInfo.readOnly):
                # Can omit a user only if it's read-only.
                result = {"success": False,
                          "error": "No user provided for writeable workspace"}
            else:
                # We need to notify the frontend of the appropriate
                # display config, because it turns out that we're
                # not going down to the leaves here. In order to make
                # this work, I've imposed a restriction that the display
                # config can't be reset within the scope of a visible
                # task. 
                result = {"success": True,
                          "workspace_dir": wsInfo.wsDirSuffix,
                          "logging_enabled": wsInfo.workspace.loggingEnabled,
                          "task": wsInfo.workspace.task.name}

        return result

    def list_workspace_folder(self, **kw):

        wsInfo = WSInfo(self, checkFolder = True, **kw)

        if not wsInfo.success:
            result = {"success": False,
                      "error": wsInfo.error}
        else:
            folder = wsInfo.folder
            try:
                result = wsInfo.workspace.runOperation("list", (folder,), fromCmdline = False,
                                                       resultFormat = MAT.Workspace.WEB_RESULT)
            except MAT.Workspace.WorkspaceError, e:
                result = {"success": False,
                          "error": str(e)}
        return result

    def open_workspace_file(self, **kw):

        wsInfo = WSInfo(self, checkFolder = True, checkFile = True, **kw)

        if not wsInfo.success:
            result = {"success": False,
                      "error": wsInfo.error}

        else:
            # Get a document.
            folder = wsInfo.folder
            file = wsInfo.file
            try:
                result = wsInfo.workspace.runOperation("open_file", (folder, file),
                                                       fromCmdline = False,
                                                       resultFormat = MAT.Workspace.WEB_RESULT,
                                                       aggregator = wsInfo.aggregator,
                                                       read_only = wsInfo.readOnly,
                                                       **wsInfo.params)
            except MAT.Workspace.WorkspaceError, e:
                result = {"success": False,
                          "error": str(e)}
        return result

    # Doc here is a MAT-JSON document. So the encoding argument
    # is irrelevant.
    
    def import_into_workspace(self, doc = None, **kw):

        wsInfo = WSInfo(self, checkFolder = True, checkFile = True, **kw)

        if not wsInfo.success:
            return {"success": False,
                    "error": wsInfo.error}
        
        # This is a bit awful, since I'm making a temporary
        # directory just so I can cache this file, because the
        # logic of the workspace file import would be awfull
        # hard to unwind. But whatever.
        # Get a document.

        file = wsInfo.file
        folder = wsInfo.folder
        doc = _getfirst(doc)
        if doc is None:
            return {"success": False,
                    "error": "No document content specified."}

        with MAT.ExecutionContext.Tmpdir(preserveTempfiles = False) as tmpDir:
            import codecs

            # The cleanest way to do this is to create a temp directory,
            # save the file under the basename, and then import it into
            # this folder.

            outPath = os.path.join(tmpDir, file)
            # It's already a UTF-8 encoded byte sequence.
            fp = codecs.open(outPath, "w", "utf-8")
            fp.write(doc.decode("utf-8"))
            fp.close()
            from MAT import json
            try:
                return wsInfo.workspace.runOperation("import", (folder, outPath),
                                                     aggregator = wsInfo.aggregator,
                                                     resultFormat = MAT.Workspace.WEB_RESULT,
                                                     fromCmdline = False,
                                                     **wsInfo.params)
            except MAT.Workspace.WorkspaceError, e:
                return {"success": False,
                        "error": str(e)}
            
    # This is kind of hideous. My only options for ordered arguments, which
    # the toplevel workspace operation has, is to have either a JSON-encoded list
    # object or to do arg1, etc...

    # This result may contain:
    # affected_folders, target, doc (import)
    # files (list)
    # doc (open)
    
    def do_toplevel_workspace_operation(self, ws_operation = None, **kw):

        wsInfo = WSInfo(self, **kw)

        if not wsInfo.success:
            return {"success": False,
                    "error": wsInfo.error}

        else:
            try:
                wsOperation = _getfirst(ws_operation)
                w = wsInfo.workspace
                args = []
                i = 1
                while True:
                    v = wsInfo.params.get("arg"+str(i))
                    if v is None:
                        break
                    args.append(v)
                    del wsInfo.params["arg"+str(i)]
                    i += 1
                return w.runOperation(wsOperation, args, aggregator = wsInfo.aggregator,
                                      resultFormat = MAT.Workspace.WEB_RESULT, fromCmdline = False,
                                      **wsInfo.params)

            except (MAT.Workspace.WorkspaceError, MAT.Operation.OperationError), e:
                return {"success": False,
                        "error": str(e)}
            except MAT.ToolChain.ConfigurationError, (engine, e):
                return {"success": False,
                        "error": str(e)}
                
    def do_workspace_operation(self, ws_operation = None, **kw):

        wsInfo = WSInfo(self, checkFolder = True, checkFile = True, **kw)

        if not wsInfo.success:
            result = {"success": False,
                      "error": wsInfo.error}
        else:
            try:
                wsOperation = _getfirst(ws_operation)
                basenames = [wsInfo.file]
                folder = wsInfo.folder
                w = wsInfo.workspace
                result = w.runFolderOperation(folder, wsOperation, aggregator = wsInfo.aggregator,
                                              basenames = basenames,
                                              resultFormat = MAT.Workspace.WEB_RESULT,
                                              **wsInfo.params)

            except (MAT.Workspace.WorkspaceError, MAT.Operation.OperationError), e:
                result = {"success": False,
                          "error": str(e)}
            except MAT.ToolChain.ConfigurationError, (engine, e):
                result = {"success": False,
                          "error": str(e)}
        
        return result

    # Let's do an arbitrarily defined operation in a task.
    
    def do_task_operation(self, task = None, task_operation = None, **kw):
        
        TASK = _getfirst(task)

        if TASK is None:

            return {"success": False, "error": "task not specified"}

        task_operation = _getfirst(task_operation)
        
        if task_operation is None:

            return {"success": False, "error": "task operation not specified"}
        
        plugins = self.plugins

        literalTaskObj = plugins.getTask(TASK)

        if literalTaskObj is None:
            return {"success": False,
                    "error": "task %s not found" % TASK}

        # Now, let's see if we've defined the web operation.
        if not hasattr(literalTaskObj, task_operation):
            return {"success": False,
                    "error": "task object does not have the %s attribute" % task_operation}

        meth = getattr(literalTaskObj, task_operation)
        import types
        if type(meth) is not types.MethodType:
            return {"success": False,
                    "error": "task object attribute %s is not a method" % task_operation}
        if not getattr(meth, "web_operation", False):
            return {"success": False,
                    "error": "task method %s is not a web operation" % task_operation}
        try:
            return {"success": True,
                    "result": meth(**kw)}
        except Exception, e:
            return {"success": False,
                    "error": "task method encountered an error: " + str(e)}

#
# Handling documentation. This is used both in the live
# CherryPy provision and when generating static documentation.
#

# Toplevel document transformer.

def enhanceRootDocIndex(matPkgRoot, taskDirs = None):
    path = os.path.join(matPkgRoot, "web", "htdocs", "doc", "html", "index.html")
    fp = open(path, "r")
    s = fp.read()    
    fp.close()

    # When I use this when I'm generating my static apps, I need to
    # look at the apps I'm including, not the apps that are installed.
    
    def _enhanceString(p, s, taskDirs = None):
        # Now, get the plugins, and traverse down from the root. Every time
        # you find a class with a docEnhancementClass, instantiate and process.
        if p.docEnhancementClass and ((taskDirs is None) or (p.taskRoot in taskDirs)):
            e = p.docEnhancementClass(os.path.basename(p.taskRoot), s)
            e.process()
            s = e.finish()
        for child in p.children:
            s = _enhanceString(child, s, taskDirs = taskDirs)
        return s

    if taskDirs is None:
        s = _enhanceString(MAT.PluginMgr.LoadPlugins().getRootTask(), s)
    else:
        # Create a new plugins directory. Make sure these taskdirs
        # are included, and then limit the taskdirs as you recurse.
        pDict = MAT.PluginMgr.LoadPlugins(*taskDirs)
        s = _enhanceString(pDict.getRootTask(), s,
                           taskDirs = [os.path.realpath(os.path.abspath(path)) for path in taskDirs])
        
    # If there's a BUNDLE_LICENSE in matPkgRoot, make a link
    # to it available.
    if os.path.exists(os.path.join(matPkgRoot, "BUNDLE_LICENSE")):
        s = s.replace("class='invisible bundle_license'", "class='bundle_license'", 1)
    return s
    
# And here's the static document creator, in case I need it somewhere other
# than the installer.

import shutil

def createStaticDocumentTree(matPkgRoot, taskRoots, jCarafeRoot, targetRoot):
    shutil.copytree(os.path.join(matPkgRoot, "web", "htdocs", "doc"), targetRoot)
    # Enhance the root.
    s = enhanceRootDocIndex(matPkgRoot, taskDirs = taskRoots)
    fp = open(os.path.join(targetRoot, "html", "index.html"), "w")
    fp.write(s)
    fp.close()
    # Copy the license.
    shutil.copy(os.path.join(matPkgRoot, "LICENSE"),
                os.path.join(targetRoot, "html"))
    # This will be true of MAT directories in bundled distributions.
    if os.path.exists(os.path.join(matPkgRoot, "BUNDLE_LICENSE")):
            shutil.copy(os.path.join(matPkgRoot, "BUNDLE_LICENSE"),
                        os.path.join(targetRoot, "html"))
    # Copy the jCarafe documentation, since the Web pages
    # refer to it.
    os.makedirs(os.path.join(targetRoot, "html", "jcarafe_resources"))
    shutil.copy(os.path.join(jCarafeRoot, "resources", "jCarafeUsersGuide.pdf"),
                os.path.join(targetRoot, "html", "jcarafe_resources"))
    for taskRoot in taskRoots:
        if os.path.isdir(os.path.join(taskRoot, "doc")):
            shutil.copytree(os.path.join(taskRoot, "doc"),
                            os.path.join(targetRoot, "html", "tasks", os.path.basename(taskRoot), "doc"))

