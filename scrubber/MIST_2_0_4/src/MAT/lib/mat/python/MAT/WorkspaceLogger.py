# Copyright (C) 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# The workspace logger is invoked from every saveFile and
# every call to import and every call to the DB which doesn't
# return anything (that's all the updates). It depends on having
# a transaction lock. When the transaction commits, everything
# for the transaction is written.

import os, shutil, codecs
from MAT import json
import MAT

class WorkspaceLogger:

    loggerDir = "_checkpoint"
    
    def __init__(self, workspace):
        self.workspace = workspace
        self.reset()
        self._maybePopulateSeed()

    def _maybePopulateSeed(self):
        # When the logger is instantiated, it looks for the appropriate
        # logger folder. If it doesn't find it, it creates it and makes
        # a seed directory which contains the DB and a copy of the
        # folders.
        path = os.path.join(self.workspace.dir, self.loggerDir)
        if not os.path.exists(path):
            # Create the archiving directory.
            os.mkdir(path)
            # Import the DB and all the folders.            
            p = os.path.join(path, "seed")
            os.mkdir(p)
            shutil.copytree(os.path.join(self.workspace.dir, "folders"),
                            os.path.join(p, "folders"))
            dbFile = self.workspace.getDB().wsDBFile
            shutil.copyfile(dbFile, os.path.join(p, os.path.basename(dbFile)))
            fp = codecs.open(os.path.join(path, "event_log"), "w", "utf-8")
            fp.close()

    def reset(self):
        # When the workspace is opened programmatically, and it
        # spans multiple transactions, it needs to reset itself
        # when a new transaction starts.        
        self.dbUpdates = []
        self.fileActions = []
        self.configActions = []
        self.logs = []
        self.logCount = 0
        self.actionCount = 0
        
    def logDBUpdate(self, q, args, isMany):
        self.dbUpdates.append((q, args, isMany))

    # I'm keeping up an action count in the bizarre situation where there
    # may be multiple saves of the same file in a transaction.

    def logImport(self, folder, basenames):
        self.fileActions.append(("import", folder, self.actionCount, basenames))
        self.actionCount += 1

    # This logs the actual file basename. Consult the
    # DB for the basename without the assignment.
    
    def logSaveFile(self, doc, folder, docName):
        self.fileActions.append(("save", folder, self.actionCount, doc, docName))
        self.actionCount += 1

    def logRemoveFile(self, folder, trueBasename):
        self.fileActions.append(("remove", folder, self.actionCount, trueBasename))
        self.actionCount += 1

    # Someday, this may not be the true basenames. Depending on whether
    # I ever need "move" again. Right now, here for completeness.
    def logMove(self, folder, targetFolderName, trueBasenames):
        self.fileActions.append(("move", folder, self.actionCount, targetFolderName, trueBasenames))
        self.actionCount += 1

    def logCopy(self, sourceFolder, sourceBasename, targetFolder, targetBasename):
        self.fileActions.append(("copy", sourceFolder, self.actionCount, sourceBasename, targetFolder.folderName, targetBasename))
        self.actionCount += 1

    def logLog(self, log, logFormat, timestamp):
        lFile = "log" + str(self.logCount)
        self.logCount += 1
        self.logs.append((log, logFormat, lFile, timestamp))

    def logEnablePrioritization(self, prioAlias):
        self.configActions.append(("enable_prioritization", self.actionCount, prioAlias))
        self.actionCount += 1

    def logDisablePrioritization(self):
        self.configActions.append(("disable_prioritization", self.actionCount))
        self.actionCount += 1

    def commit(self, wsOp):
        # Create a checkpoint dir.
        import datetime
        now = datetime.datetime.now()
        dirName = now.strftime("%Y%m%d_%H%M%S") + "_" + ("%06d" % now.microsecond)
        p = os.path.join(self.workspace.dir, self.loggerDir, dirName)
        os.mkdir(p)
        os.mkdir(os.path.join(p, "saves"))
        os.mkdir(os.path.join(p, "imports"))        
        os.mkdir(os.path.join(p, "logs"))
        # Write the diffed files to saves; the imports to imports; the logs to logs;
        # and a record of everything, including the db updates,
        # to the event_log, with the timestamp.        
        # Write JSON to the log. It will contain no line breaks.
        actions = []
        for a in self.fileActions:
            if a[0] == "save":
                # This one needs to be truncated.
                actions.append(("save", a[1].folderName, a[2], a[4]))
            else:
                actions.append((a[0], a[1].folderName) + a[2:])
        for a in self.configActions:
            actions.append(a)
        jDir = {"timestamp": dirName, "db_updates": self.dbUpdates,
                "actions": actions,
                "operation": self._describeOperation(wsOp),
                "logs": [(lFile, logFormat, timestamp) for (log, logFormat, lFile, timestamp) in self.logs]}
        # Save the imports.
        db = self.workspace.getDB()
        for ignore, folder, count, basenames in [a for a in self.fileActions if a[0] == "import"]:
            # Since this is after the transaction, the basenames
            # have been converted and assigned and the basenames are
            # in the DB.
            d = db.documentsForBasenames(basenames = basenames)
            for bs in basenames:
                for b in d[bs]:
                    shutil.copyfile(os.path.join(folder.dir, b),
                                    os.path.join(p, "imports", "%s_%d_%s" % (folder.folderName, count, b)))
        # Save the logs.
        for log, logformat, lFile, timestamp in self.logs:
            # The log had better be a Unicode string.
            fp = codecs.open(os.path.join(p, "logs", lFile), "w", "utf-8")
            fp.write(log)
            fp.close()
        # Save the saves. This is going to be a bit complicated. What we want to
        # do is remove all the clutter: the lexes, the zones other than SEGMENT and VOTE,
        # the metadata, the signal.
        _jsonIO = MAT.DocumentIO.getDocumentIO('mat-json', task = self.workspace.task)
        typesToSave = self.workspace.task.getAnnotationTypesByCategory("content") + ["SEGMENT", "VOTE"]
        for ignore, folder, count, doc, trueBasename in [a for a in self.fileActions if a[0] == "save"]:
            jDict = _jsonIO.renderJSONObj(doc)
            d = {"asets": [t for t in jDict["asets"] if t["type"] in typesToSave]}
            fp = codecs.open(os.path.join(p, "saves", "%s_%d_%s" % (folder.folderName, count, trueBasename)), "w", "utf-8")
            fp.write(json.dumps(d, ensure_ascii = False))
            fp.close()
        fp = codecs.open(os.path.join(self.workspace.dir, self.loggerDir, "event_log"), "a", "utf-8")
        fp.write(json.dumps(jDir) + "\n")
        fp.close()
        # And then reset yourself.
        self.reset()

    # This function should move to the operations when we integrate.
    def _describeOperation(self, wsOp):
        d = {"name": wsOp.name,
             "parameters": dict([(k, str(v)) for (k, v) in wsOp.parameters.items()])}
        if wsOp.name in ("save", "upload_ui_log"):
            if d["parameters"].has_key("doc"):
                d["parameters"]["doc"] = "[deleted]"
            if d["parameters"].has_key("log"):
                d["parameters"]["log"] = "[deleted]"                
        if isinstance(wsOp, MAT.Workspace.WorkspaceToplevelOperation):
            d.update({"type": "toplevel",
                      "args": [str(x) for x in wsOp.args]})
        else:
            d.update({"type": "folder",
                      "folder": wsOp.folder.folderName,
                      "inputBasenames": wsOp.inputBasenames})
        return d        

class WorkspaceLoggerError(Exception):
    pass

# The rerunner dir has a state file, which says where it
# stopped when it was rerunning (so it can be restarted)
# and a workspace dir. It's inside the workspace checkpoint
# directory. Only one person can be rerunning a workspace
# at a given point, and it's transaction-locked in the RERUNNING
# workspace. Note that this is "live", in the sense that it's reading
# from the log, which could possible be being augmented AS THE
# WORKSPACE IS BEING RERUN. Each line is its own transaction,
# so there's no danger of reading a partial transaction, I don't think.

class WorkspaceRerunner:

    def __init__(self, workspace, restart = False):
        # If there's a log in this directory.
        self.sourceWorkspace = workspace
        self.wsLog = os.path.join(workspace.dir, WorkspaceLogger.loggerDir)
        if not os.path.exists(self.wsLog):
            raise WorkspaceLoggerError, "no workspace log"
        self.rerunningDir = os.path.join(self.wsLog, "_rerun")
        self.stateFile = os.path.join(self.rerunningDir, "statefile")
        self.wsdir = os.path.join(self.rerunningDir, "workspace")
        if restart and os.path.exists(self.rerunningDir):
            shutil.rmtree(self.rerunningDir)
        if not os.path.exists(self.rerunningDir):
            self.ws = self._seed()
        else:
            self.ws = MAT.Workspace.Workspace(self.wsdir)            

    def _seed(self):
        # The clean way to do this is to create a new workspace in the target
        # directory. This may give me a circular import when I migrate this into the core.
        w = MAT.Workspace.Workspace(self.wsdir, create = True, taskName = self.sourceWorkspace.task.name,
                                    _fromRerunner = True)
        # Make sure logging is DISabled.
        w._disableLogging()
        # Replace the workspace DB with the one in seed, and ditto for
        # the folders.
        dbFile = w.getDB().wsDBFile
        w.closeDB()
        shutil.copyfile(os.path.join(self.wsLog, "seed", os.path.basename(dbFile)), dbFile)
        shutil.rmtree(os.path.join(w.dir, "folders"))
        shutil.copytree(os.path.join(self.wsLog, "seed", "folders"), os.path.join(w.dir, "folders"))
        return w

    # The state is the last state rerun.
    def _readState(self):
        if os.path.exists(self.stateFile):
            fp = open(self.stateFile, "r")
            curState = fp.read().strip()
            fp.close()
            return curState
        else:
            return None

    def _writeState(self, state):
        fp = open(self.stateFile, "w")
        fp.write(state)
        fp.close()

    def rollForward(self, stopAt = None, verbose = False):
        # Roll forward. 
        # The entries in the DB log will be in order, one entry per transaction.        
        fp = codecs.open(os.path.join(self.wsLog, "event_log"), "r", "utf-8")
        db = self.ws.getDB()
        currentTransaction = None
        oldState = self._readState()
        skip = (oldState is not None)
        if verbose:
            self._reportRerunState()
        _jsonIO = MAT.DocumentIO.getDocumentIO('mat-json', task = self.ws.task)
        for line in fp.readlines():
            jDict = json.loads(line.strip())
            if skip:
                if jDict["timestamp"] == oldState:
                    skip = False
                continue
            if jDict["timestamp"] == stopAt:
                break
            p = os.path.join(self.wsLog, jDict["timestamp"])
            # The file actions are in order.
            for a in jDict["actions"]:
                if a[0] == "save":
                    fName, count, docName = a[1:]
                    fp = codecs.open(os.path.join(p, "saves", "%s_%d_%s" % (fName, count, docName)), "r", "utf-8")
                    frag = json.loads(fp.read())
                    fp.close()
                    # The document will already be there, because assign copies and
                    # removes first.
                    fp = codecs.open(os.path.join(self.ws.folders[fName].dir, docName), "r", "utf-8")
                    docJson = json.loads(fp.read())
                    fp.close()
                    # Now, update the asets.
                    d = dict([(a["type"], a) for a in docJson["asets"]])
                    for a in frag["asets"]:
                        d[a["type"]] = a
                    docJson["asets"] = d.values()
                    fp = codecs.open(os.path.join(self.ws.folders[fName].dir, docName), "w", "utf-8")
                    fp.write(json.dumps(docJson, ensure_ascii = False))
                elif a[0] == "import":
                    fName, count, basenames = a[1:]
                    for b in basenames:
                        shutil.copyfile(os.path.join(p, "imports", "%s_%d_%s" % (fName, count, b)),
                                        os.path.join(self.ws.folders[fName].dir, b))
                elif a[0] == "remove":
                    fName, count, trueBasename = a[1:]
                    os.remove(os.path.join(self.ws.folders[fName].dir, trueBasename))
                elif a[0] == "move":
                    fName, count, targetFolderName, trueBasenames = a[1:]
                    tFolder = self.ws.folders[targetFolderName]
                    sFolder = self.ws.folders[fName]
                    for b in trueBasenames:
                        shutil.move(os.path.join(sFolder.dir, b), os.path.join(tFolder.dir, b))
                elif a[0] == "copy":
                    sName, count, sourceBasename, tName, targetBasename = a[1:]
                    shutil.copyfile(os.path.join(self.ws.folders[sName].dir, sourceBasename),
                                    os.path.join(self.ws.folders[tName].dir, targetBasename))
                elif a[0] == "enable_prioritization":
                    self.ws._db = db
                    self.ws._enablePrioritization(a[2])
                    db = self.ws.getDB()
                elif a[0] == "disable_prioritization":
                    self.ws._db = db
                    self.ws._disablePrioritization()
                    db = self.ws.getDB()                    
            db.beginTransaction()
            for q, args, isMany in jDict["db_updates"]:
                db._execute(q, params = args, many = isMany, retrieval = False)
            db.commitTransaction()
            self._writeState(jDict["timestamp"])
            if verbose:
                self._reportRerunState()
            # transaction-final operations.
            self._doTransactionOperations(jDict)
        self.ws.closeDB()
        fp.close()

    def _reportRerunState(self):
        state = self._readState()
        if state is None:
            print "\n### At seed:\n"
        else:
            print "\n### At %s:\n" % state
        o = self.ws.getOperation("dump_database")
        o.fromCmdline = True
        o.do()
        o = self.ws.getOperation("workspace_configuration")
        o.fromCmdline = True
        o.do()

    def _doTransactionOperations(self, jDict):
        # At each point, we run modelbuild/autotag just to make sure
        # that everything is OK. Eventually, we'll be generating scores against
        # test conditions.
        pass
