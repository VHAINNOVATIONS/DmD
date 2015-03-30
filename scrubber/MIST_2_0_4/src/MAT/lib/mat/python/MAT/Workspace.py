# Copyright (C) 2008-11 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Here, we define the various aspects of a workspace.

# The workspace structure is pretty simple: it contains a number of
# predefined folders, each of which contains files. It also contains
# a properties file, and a model directory. The name of the file is
# consistent across folders, so, e.g., "foo" in the "core"
# folder would be the same as "foo" in the "reconciliation" folder.

# The core folders will be:

# core: this is where documents are imported to. They must be converted to mat-json
# on import.
# reconciliation: this folder exists for reconciliation operations between
# different versions in core. It is not used in the initial 2.0
# implementation - it's part of the TooCAAn extensions.
# export: where completed, frozen documents optionally go. Also not used yet.

# This set should be extensible.

# Each folder can have a predefined set of operations. The operations can be applied
# to the entire contents of the folder, or a subset.

# The workspace will impose a number of restrictions which aren't imposed
# in the bare MATEngine. For a given task, the workflows and step sequences
# for each of the batch operations is predefined, as well as the default
# arguments for the model construction. There's only
# one current model at a time, and whether or not previous models are removed
# is a global setting on the workspace (it'll be on by default, because these
# models are huge). If email notification is desired, the appropriate outgoing
# SMTP server will need to be set (can't require a password).

# The command-line tool will support the following actions:

# - configure a new workspace: creates the directory structure, sets the global properties.
# - load documents into a workspace
# - do a workspace operation: with options to do it on all eligible documents
# or a subset of names listed in a file; send email to the invoker or not

# Email invocation isn't implemented yet.

import os, shutil, sys, time

class WorkspaceError(Exception):
    pass

class WorkspaceUserLockError(WorkspaceError):
    pass

class WorkspaceFileLockedError(WorkspaceError):
    pass

#
# Transactions
#

# Transactions are implemented as atomic operations across the DB
# and file system. They support commit and rollback.

class WorkspaceTransaction:

    def __init__(self, ws, op, filesToPreserve = None, filesToAdd = None, filesToRemove = None):
        self.workspace = ws
        self.op = op
        self.filesToPreserve = []
        if filesToPreserve is not None:
            self.addFilesToPreserve(filesToPreserve)
        self.filesToAdd = []
        if filesToAdd is not None:
            self.addFilesToAdd(filesToAdd)
        self.filesToRemove = []
        if filesToRemove is not None:
            self.addFilesToRemove(filesToRemove)
        self.db = self.workspace.getDB()
        self.db.beginTransaction()
        if self.workspace.logger:
            self.workspace.logger.reset()

    # These functions will raise an error if they can't
    # stash the right backup file. This is the appropriate behavior
    # even if the transaction has been started (it'll be rolled back).

    def addFilesToPreserve(self, paths, check = False):
        for curPath in paths:
            curPath = os.path.realpath(curPath)
            if check and curPath in self.filesToPreserve:
                continue
            if not os.path.exists(curPath):
                raise WorkspaceError, ("couldn't find existing pathname %s to preserve for transaction" % curPath)
            try:
                shutil.copyfile(curPath, curPath + ".bak")
            except Exception, e:
                raise WorkspaceError, ("couldn't cache copy of existing pathname %s for transaction (error was: %s)" % (curPath, e))
            self.filesToPreserve.append(curPath)

    def addFilesToAdd(self, paths, check = False):
        for curPath in paths:
            curPath = os.path.realpath(curPath)
            if check and curPath in self.filesToPreserve:
                continue
            self.filesToAdd.append(curPath)

    def addFilesToRemove(self, paths, check = False):
        for curPath in paths:
            curPath = os.path.realpath(curPath)
            if check and curPath in self.filesToPreserve:
                continue
            if not os.path.exists(curPath):
                raise WorkspaceError, ("couldn't find existing pathname %s to remove for transaction" % curPath)
            try:
                shutil.copyfile(curPath, curPath + ".bak")
            except Exception, e:
                raise WorkspaceError, ("couldn't cache copy of existing pathname %s for transaction (error was: %s)" % (curPath, e))
            self.filesToRemove.append(curPath)

    def commit(self):
        self.db.commitTransaction()
        for p in self.filesToPreserve:
            try:
                os.remove(p + ".bak")
            except:
                pass
        for p in self.filesToRemove:
            try:
                os.remove(p + ".bak")
            except:
                pass
        if self.workspace.logger:
            self.workspace.logger.commit(self.op)
        self.workspace.currentTransaction = None

    def rollback(self):
        try:
            self.db.rollbackTransaction()
        except Exception, e:
            print >> sys.stderr, ("Warning: failed to rollback DB (error was: %s)" % e)
        for p in self.filesToPreserve:
            try:
                shutil.copyfile(p + ".bak", p)
            except Exception, e:
                print >> sys.stderr, ("Warning: failed to restore %s during rollback (error was: %s)" % (p, e))
            try:
                os.remove(p + ".bak")
            except:
                pass
        for p in self.filesToRemove:
            try:
                shutil.copyfile(p + ".bak", p)
            except Exception, e:
                print >> sys.stderr, ("Warning: failed to restore %s during rollback (error was: %s)" % (p, e))
            try:
                os.remove(p + ".bak")
            except:
                pass
        for p in self.filesToAdd:
            if os.path.exists(p):
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
                except Exception, e:
                    print >> sys.stderr, ("Warning: failed to remove %s during rollback" % p)
        self.workspace.currentTransaction = None

#
# WorkspaceFolder
#

# Each folder has a set of operations. We can add a folder to a workspace.
# Each folder corresponds to a directory which is a subdir of the
# workspace dir.

from MAT.DocumentIO import getDocumentIO

class WorkspaceFolder:

    def __init__(self, workspace, folderName, operations = None,
                 description = "", importTarget = True,
                 prettyName = None):
        self.workspace = workspace
        self.folderName = folderName
        self.prettyName = prettyName or self.folderName
        self.description = description
        # These are a holdover from when there could be raw files
        # in the workspace. Now, there's nothing but the rich file type.
        self.fileType = self.workspace.richFileType
        self.docIO = self.workspace.richFileIO
        self.importTarget = importTarget
        self.dir = os.path.join(self.workspace.folderDir, folderName)
        self.operations = {}
        if operations is not None:
            for op in operations:
                self.addOperation(op.name, op)

    def create(self):
        os.makedirs(self.dir)
    
    # So the logic here should be that we try to load the document
    # using the workspace's rich file type, as a test. We can't
    # realistically guess in all cases when it's a rich file but
    # we imported raw, so we'll have to settle for trying the
    # workspace's default rich format (which, so far, is mat-json).

    # By the time we get here, in the new workspaces, we will have
    # been guaranteed that the files are already in the rich
    # format of the workspace - and should be a document object.

    # In other words, all of the complexity of this is gone.

    def importFile(self, doc, basename):
        self.workspace.richFileIO.writeToTarget(doc, os.path.join(self.dir, basename))

    # This is an instance of a child of MAT.Operation.

    def addOperation(self, name, op):
        if op.name is None:
            raise WorkspaceError, ("operation class '%s' has no name attribute" % op.__name__)
        if self.workspace.toplevelOperations.has_key(op):
            raise WorkspaceError, ("can't define folder operation '%s', since it's already defined as a toplevel operation" % op.name)
        self.operations[name] = op

    def addOptions(self, aggregator):
        for op in self.getCmdlineOperations():
            op.addOptions(aggregator)

    def getCmdlineOperations(self, debug = False):
        if debug:
            avail = CMDLINE_DEBUG_AVAILABLE_MASK
        else:
            avail = CMDLINE_AVAILABLE_MASK
        return [op for op in self.operations.values() if (op.availability & avail)]

    def clear(self, basenames = None):
        # Remove all documents from the folder.
        files = os.listdir(self.dir)
        for f in files:
            if (basenames is None) or (f in basenames):
                self.removeFile(f)

    def removeFile(self, f):
        p = os.path.join(self.dir, f)
        if os.path.isfile(p):
            os.remove(p)
        if self.workspace.logger:
            self.workspace.logger.logRemoveFile(self, f)

    def move(self, targetFolderName, basenames = None):
        try:
            targetFolder = self.workspace.folders[targetFolderName]
        except KeyError:
            raise WorkspaceError, ("can't move files to unknown target folder '%s'" % targetFolderName)

        files = os.listdir(self.dir)
        moved = []
        for f in files:
            if (basenames is None) or (f in basenames):
                p = os.path.join(self.dir, f)
                if os.path.isfile(p):
                    shutil.move(p, os.path.join(targetFolder.dir, f))
                    moved.append(f)
        if self.workspace.logger:
            self.workspace.logger.logMove(self, targetFolderName, basenames)
        return moved    

    def getFiles(self, basenames = None):
        # Returns a list of all the full paths for all the files
        # in the folder, or just the files listed in the list
        # of basenames. Let's go completely bonkers with list
        # comprehensions. I check with the workspace so
        # any stray files in the directory don't get passed along.
        return [os.path.join(self.dir, b) for b in self.getBasenames(basenames)]

    def openFile(self, basename):
        basenameExists = self.getBasenames(basenames = [basename])
        if basenameExists:
            return self._openFileBasename(basename)
        else:
            return None

    # saveFile semantics: expects a fileBasename.

    def saveFile(self, doc, basename):
        self.docIO.writeToTarget(doc, os.path.join(self.dir, basename))
        if self.workspace.logger:
            self.workspace.logger.logSaveFile(doc, self, basename)
            
    def getBasenames(self, basenames = None):
        d = os.listdir(self.dir)
        return [b for b in self.workspace.getBasenames(basenames) if b in d]

    # Stub for core folder, below. This must filter
    # out bad basenames.

    def fileBasenameForUser(self, basename, user):
        if self.getBasenames([basename]):
            return basename
        else:
            return None
    
    def fileBasenameLocked(self, fileBasename):
        return None

    def prepareForEditing(self, doc, fileBasename, user, lockId):
        raise WorkspaceError, "folder is not editable"

    # This is needed when I can't check the basenames yet, in import.
    # It's also needed in Workspace._openFile, where we compute
    # the basename and do all the actual checking before we load.
    
    def _openFileBasename(self, fileBasename):
        p = os.path.join(self.dir, fileBasename)
        return self.docIO.readFromSource(p, taskSeed = self.workspace.task)

    def basenameForDocname(self, docName):
        return docName

    def getOperation(self, operationName, basenames = None, transaction = None):
        try:
            cls = self.operations[operationName]
        except KeyError:
            raise OperationError, ("no operation named '%s' in folder '%s'" % (operationName, self.folderName))
        # Instantiate the class.
        return cls(self, basenames = basenames, transaction = transaction)

    def listContents(self, basenames):
        return [{"basename": basename} for basename in basenames]

    def updateOpenFileWebResultSeed(self, doc, basename, seed):
        return

# And now, the core workspace folder. It relies a LOT on the DB to
# find basenames, etc. 

class CoreWorkspaceFolder(WorkspaceFolder):
        
    # Every basename is in core - you can only import to core.
    # No need to look at the directory listing - you'd just
    # have to dismantle the filenames for the assigned users.
    
    def getBasenames(self, basenames = None):
        allBasenames = self.workspace.getDB().allBasenames()
        if basenames is None:
            return allBasenames
        else:
            return list(set(basenames) & set(allBasenames))

    # getFiles() semantics: return a fleshed-out list of
    # all the actual pathnames for the basenames listed.
    # This is NOT sensitive to users; it returns ALL of them.

    def getFiles(self, basenames = None):
        d = self.workspace.getDB().documentsForBasenames(basenames)
        r = []
        for v in d.values():
            r += v
        return [os.path.join(self.dir, p) for p in r]

    def fileBasenameForUser(self, basename, user):
        # So the idea here is to return the docname which
        # is appropriate for this user. If the user is None,
        # it should be the raw basename. But we also
        # have to ensure the file is present. Well, this is the
        # core folder - of COURSE it's present.
        return self.workspace.getDB().documentForBasenameAndUser(basename, user)

    def basenameForDocname(self, docName):
        return self.workspace.getDB().basenameForDocname(docName)

    def fileBasenameLocked(self, fileBasename):
        return self.workspace.getDB().coreDocumentLocked(fileBasename)

    def prepareForEditing(self, doc, fileBasename, user, lockId):
        db = self.workspace.getDB()
        db.lockCoreDocument(lockId, fileBasename, user)

    def listContents(self, basenames):
        db = self.workspace.getDB()
        bPairs = []
        for docName, basename, status, assignedUser, lockedBy in db.basenameInfo(basenames):
            info = {"basename": basename, "status": status}                    
            if assignedUser:
                info["assigned to"] = assignedUser
            if docName != basename:
                info["doc name"] = docName
            if lockedBy:
                info["locked by"] = lockedBy
            bPairs.append(info)
        return bPairs

    def updateOpenFileWebResultSeed(self, doc, basename, seed):
        seed["status"] = self.workspace._documentStatus(doc)
        
#
# Individual folders and their operations. Also, workspace-level operations.
#

from MAT.Operation import Operation, OpArgument, OperationError, XMLOpArgumentAggregator, Option

# Each of the operations controls what its command-line and Web
# results look like. I need to do this here so we can specialize the
# operation structure for individual tasks.

NULL_RESULT, FN_RESULT, WEB_RESULT = 0, 1, 2
_jsonIO = getDocumentIO('mat-json')

# Originally, the toplevel workspace operations weren't actual operation
# objects, but then I fixed that, because I needed to be able to specialize
# them. Rather than rename WorkspaceOperation everywhere (even though I
# probably should), I've introduced a toplevel WorkspaceGeneralOperation.

# CMDLINE_AVAILABLE covers 2 bit positions - i.e., everything that
# is CMDLINE_AVAILABLE is CMDLINE_DEBUG_AVAILABLE.

NOT_AVAILABLE, UI_AVAILABLE, CMDLINE_DEBUG_AVAILABLE, CMDLINE_AVAILABLE = 0, 1, 2, 6
UI_AVAILABLE_MASK, CMDLINE_DEBUG_AVAILABLE_MASK, CMDLINE_AVAILABLE_MASK = 1, 2, 4

class WorkspaceGeneralOperation(Operation):

    availability = UI_AVAILABLE | CMDLINE_AVAILABLE

    def __init__(self, *args, **kw):
        Operation.__init__(self, *args, **kw)
        self.parameters = {}
        # See _runOperation below.
        self.fromCmdline = False
        
    # I'm going to use the option where we create instances of
    # each operation when we run. 

    # I need this because some of the information is
    # required sometime when the operation is called
    # (i.e., from the UI) and other times not, and I don't
    # want to have to compute the whole thing each time, since
    # it can get expensive. So I'll return a result object from
    # which the necessary results can be calculated. One of the
    # important parts is to store the operation and the folder
    # AND the digested options.

    # So first, let's be sure to stash the parameters.
    
    def enhanceAndValidate(self, aggregator, **params):
        self.parameters = super(WorkspaceGeneralOperation, self).enhanceAndValidate(aggregator, **params)

    def doOperation(self):
        self.do(**self.parameters)

    @classmethod
    def customizeUsage(self, w):
        return None

    def fnResult(self):
        return None

    def webResult(self):
        return None

    @classmethod
    def getUsage(cls, w):
        return "No usage available for %s." % cls.name

class WorkspaceToplevelOperation(WorkspaceGeneralOperation):

    availability = CMDLINE_AVAILABLE

    def __init__(self, workspace, args, transaction = None):
        WorkspaceGeneralOperation.__init__(self)
        self.workspace = workspace
        self.args = args
        self.transaction = transaction

    def getWorkspace(self):
        return self.workspace
    
    def getOperationSettings(self):
        return self.workspace.getOperationSettings(self.name)

class WorkspaceOperation(WorkspaceGeneralOperation):

    def __init__(self, folder, basenames = None, transaction = None):
        WorkspaceGeneralOperation.__init__(self)
        self.transaction = transaction
        self.folder = folder
        self.state = None
        # We need to know EXACTLY what basenames were operated on
        # in order to report the document output. But sometimes,
        # we need to recalculate it. It MUST be fixed before
        # the operation, because we use _getTargetDocuments()
        # to report on the documents that made it into the target
        # folder, based on the documents that were in this folder
        # BEFORE the operation happened. But we only
        # want to do that if inputBasenames was None.
        self.inputBasenames = basenames
        self.affectedBasenames = self.folder.getBasenames(self.inputBasenames)

    def getWorkspace(self):
        return self.folder.workspace
    
    def getOperationSettings(self):
        return self.folder.workspace.getOperationSettings(self.name)

    def getAffectedFolders(self):
        return []

    def getTargetFolderAndDocuments(self):
        return None, []

    # By default, we get all of them.
    def getAffectedFileBasenames(self):
        # Invert the dictionary.
        docDict = self.folder.workspace.getDB().documentsForBasenames(self.affectedBasenames)
        baseDict = {}
        for k, vals in docDict.items():
            for v in vals:
                baseDict[v] = k
        return baseDict

    # In order to get the target documents, we have to know
    # which basenames were actually accessed, which is a complication
    # when None was passed in. See __init__.
    
    def _getTargetDocuments(self, folderName):
        target = self.folder.workspace.folders[folderName]        
        return [(basename, fileBasename, target._openFileBasename(fileBasename))
                for (fileBasename, basename) in self.getAffectedFileBasenames().items()]

    @classmethod
    def getUsage(cls, w):
        return cls._getUsage(cls.name, w)

    @classmethod
    def _getUsage(cls, clsName, w):
        return """Usage: %prog [options] <dir> """ + clsName + """ [operation_options] <folder> [ <basename> ... ]

<folder>: The name of the folder to operate on.
<basename>: (optional) The basename or basenames to restrict the operation to."""

    def webResult(self):
        affectedFolders = self.getAffectedFolders()
        targetFolder, affectedDocuments = self.getTargetFolderAndDocuments()
        result = {"success": True,
                  "affected_folders": affectedFolders}
        # We also need the target folder and the document contents
        # from that folder. There may be no target (either no
        # documents were affected or the folder hasn't changed).
        if targetFolder:
            result["target"] = targetFolder
        if affectedDocuments:
            basename, fileBasename, doc = affectedDocuments[0]
            result["basename"] = basename
            result["file_basename"] = fileBasename
            if basename != fileBasename:
                result["assigned_to"] = fileBasename[len(basename) + 1:]
            result["doc"] = _jsonIO.renderJSONObj(doc)
            result["status"] = self.getWorkspace()._documentStatus(doc)
        return result

#
# toplevel
#

import MAT.DocumentIO

# We should factor out the code to handle the engine-based operations,
# so that other folks downstream can consume it.

class MATEngineExecutionWorkspaceOperationMixin:

    # Required methods: allPaths(), wrapup(), getRunParameters()

    def do(self, checkPathsAffected = True):

        operationSettings = self.getOperationSettings()
        
        if operationSettings is None:        
            raise WorkspaceError, ("no operation settings in task '%s' for operation '%s'" % (self.getWorkspace().task.name, self.name))

        # Now, we've got our settings. At least workflow and steps are defined.

        try:        
            workflow = operationSettings["workflow"]
        except KeyError:
            raise WorkspaceError, ("workflow undefined in operation settings for operation '%s'" % self.name)
        
        operationSettings = operationSettings.copy()
        del operationSettings["workflow"]
        
        # Now, we run the engine, either on the specified
        # files (which should be just basenames), or on
        # everything in the folder.
        allPaths = self.allPaths()
        
        if (not allPaths) and checkPathsAffected:
            raise WorkspaceError, "no paths affected"

        # Now, run the operation. Note that aggregatorRun() will
        # use the runParameters which are passed both as defaults
        # for the original values and as defaults to be overridden,
        # so any values that need to be futzed with will be futzed with.

        aggr = XMLOpArgumentAggregator(operationSettings)
        import MAT.ToolChain, MAT.Error
        try:
            e = MAT.ToolChain.MATEngine(workflow = workflow, task = self.getWorkspace().task.name)
            dataPairs = e.aggregatorRun(aggr, inputFileList = allPaths,
                                        **self.getRunParameters(operationSettings))
        except (MAT.Error.MATError, MAT.ToolChain.ConfigurationError), exc:
            from MAT.ExecutionContext import _DEBUG
            if _DEBUG:
                raise
            else:
                if isinstance(exc, MAT.Error.MATError):
                    errstr = exc.errstr
                else:
                    ignore, errstr = exc
            raise WorkspaceError, (self.name + " operation failed: " + errstr)    
        self.wrapup(dataPairs)

# First engine-based operation: import.

# Can we import to anything besides core? In the basic situation, no. And I can't think of a case
# where you should be able to import to anything else. But I'm not going to enforce
# that quite yet.


class ImportOperation(WorkspaceToplevelOperation, MATEngineExecutionWorkspaceOperationMixin):

    name = "import"

    @staticmethod
    def _fileTypeCallback(optionObj, flag, value, parser):
        try:
            cls = MAT.DocumentIO.getInputDocumentIOClass(value)
            cls.addInputOptions(parser.aggregator, values = parser.values)
        except KeyError:
            raise OperationError, ("file_type must be one of " + ", ".join(["'"+x+"'" for x in MAT.DocumentIO.allInputDocumentIO()]))

    # GRRRR. If this is called when the class is DEFINED, I have
    # no guarantee that all the document IO is available yet.
    
    @classmethod
    def _createArgList(cls):
        return [Option("--strip_suffix", action="store",
                       dest="strip_suffix",
                       help="remove this suffix from the file name when determining the basename for the file in the workspace. By default, the original file basename is used."),
                Option("--encoding", action = "store",
                       dest="encoding",
                       help="for raw documents, input encoding. Default is ASCII. All imported raw documents will be converted to utf-8."),
                # The file type is the default for the folder, which is JSON for rich folders,
                # raw for raw folders.
                Option("--file_type", dest = "file_type",
                       side_effect_callback = cls._fileTypeCallback,
                       metavar = " | ".join(MAT.DocumentIO.allInputDocumentIO()),
                      help = "The file type of the document. One of " + ", ".join(MAT.DocumentIO.allInputDocumentIO()) + ". The default file type is mat-json."),
                Option("--workflow", dest = "workflow",
                       type = "string", metavar = "workflow",
                       help = "By default, the workflow used during import is the one specified in the settings for the import operation in the <workspace> block in your task.xml file. Use this flag to overwrite that value."),
                Option("--steps", dest = "steps",
                       type = "string", metavar = "step(,step...)",
                       help = "By default, the steps used during import are the ones specified in the settings for the import operation in the <workspace> block in your task.xml file. To overwrite that value, specify a comma-separated sequence of steps with this option."),
                Option("--users", dest = "users",
                       type="string", metavar = "user(,user...)",
                       help = "By default, the document state of a document is inferred from the document itself. But when the document has been annotated already, the workspace may not be able to tell what user the annotations should be attributed to. You can use this flag to fix the attribution. If the document has been tagged automatically but not corrected by a human, use MACHINE as your value; otherwise, use the name of the registered workspace user. This value will overwrite any attributions that are already in the document. The import process will usually signal an error if there are annotated segments which are not attributed."),
                Option("--document_status",
                       type = "choice", choices = ["reconciled", "gold"],
                       help = "By default, the document status of a document is inferred from  the document itself. But when the document has been annotated, the workspace sometimes can't distinguish between documents which has been partially annotated, documents which are gold standard documents (reconciled), and documents which are simply asserted by a user to be completed (gold). The default is to judge the document to be incomplete; use this flag to override that default. If the document is already explicitly marked as gold or reconciled, this setting will be ignored (so you can't use it, for instance, to import a reconciled document as merely gold)."),
                Option("--assign", type="boolean",
                       help = "If present, assign the imported document to the specified user or users in the --users option. MACHINE is not an eligible target. Ignored if --document_status is reconciled."),
                Option("--add_to_basename_set", dest = "add_to_basename_set",
                       type = "string", metavar="setname",
                       help = "Add the basenames to a given basename set. You might want to do this if, e.g., you were importing gold-standard documents which you wanted to set aside for evaluation.")]

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> import [import_options] <folder> <file> ...

<folder>: The name of the folder to import documents into.
<file>: The file to import into the folder (can be repeated).

Available folders are:\n\n""" + w.describeFolders(importableOnly = True)

    def fnResult(self):
        return self.imported

    def webResult(self):
        import codecs
        from MAT import json
        folder = self.args[0]
        # Only want the first basename.
        fp = codecs.open(os.path.join(self.workspace.folders[folder].dir, self.basenames[0]), "r", "utf-8")
        s = fp.read()
        fp.close()
        return {"success": True,
                "affected_folders": [folder],
                "target": folder,
                "doc": json.loads(s)}

    # This is the stuff for the engine mixin.
    
    def allPaths(self):
        return self.filePairs.keys()

    def getRunParameters(self, operationSettings):
        for key in ["output_file_type", "output_encoding"]:
            if operationSettings.has_key(key):
                raise WorkspaceError, ("import operation settings don't permit %s option to MATEngine", key)
        return self.runParameters

    def wrapup(self, dataPairs):
        # _storePreparedFiles picks up on this.
        self.dataPairs = dict(dataPairs)

    # So we can overwrite workflow and steps if we want.
    def getOperationSettings(self):
        settings = WorkspaceToplevelOperation.getOperationSettings(self)
        if settings is not None:
            settings = settings.copy()
            if self.workflow is not None:
                settings["workflow"] = self.workflow
            if self.steps is not None:
                settings["steps"] = self.steps
        return settings

    # For the transaction, we want to make sure we plan to remove those files.
    
    # mark_human_gold = None, mark_gold_standard_reference = False,
    
    def do(self, assign = False,
           users = None, document_status = None,
           encoding = "ascii", file_type = None, fileIO = None, strip_suffix = None, workflow = None,
           steps = None, add_to_basename_set = None, **kw):

        #
        # First section: set up the context.
        #
        
        # We need to apply the import operation settings here. It's essentially
        # identical to the old tagprep. We'll use the mixin, and then the wrapup()
        # operation will deal with the actual save.
        
        files = self.args[1:]
        self.folderName = self.args[0]
        self.markGold = (document_status == "gold") 
        self.markReconciled = (document_status == "reconciled")
        if assign:
            if self.markReconciled:
                raise WorkspaceError, "can't assign reconciled documents to users"
            if users is None:
                raise WorkspaceError, "can't assign documents if users aren't specified"
            if "MACHINE" in users.split(","):
                raise WorkspaceError, "can't assign documents to MACHINE"
        if self.markGold:
            if users is None:
                raise WorkspaceError, "can't mark gold without users"
            if len(users.split(",")) > 1:
                raise WorkspaceError, "can't attribute gold documents to more than one user"
            if "MACHINE" in users.split(","):
                raise WorkspaceError, "can't attribute gold documents to MACHINE"
        self.users = users
        self.assignDocuments = assign
        fromCmdline = self.fromCmdline
        stripSuffix = strip_suffix
        if (fileIO is None) and (file_type is None):
            fileIO = self.workspace.richFileIO
        self.workflow = workflow
        self.steps = steps
        self.basenameSet = add_to_basename_set

        #
        # Second section: check folders.
        #
        
        try:
            folder = self.workspace.folders[self.folderName]
        except KeyError:
            raise WorkspaceError, ("can't import files into unknown folder %s" % self.folderName)

        if not folder.importTarget:
            raise WorkspaceError, ("can't import into unimportable folder '%s'" % self.folderName)
            
        # There can't be more than one file with the same
        # name in a workspace. So I need to maintain
        # a hash.

        #
        # Third section: preprocessing the filenames.
        #
        
        # Make sure I get the most up-to-date.
        # If there are multiple imports going on simultaneously,
        # we're hosed. Locks will take care of this.

        # For ease of interaction, let's check all the basenames
        # first, so we can raise an error.

        fileNamesRead = False

        fileHash = self.workspace._readFileNames()
        fileNamesRead = True

        filePairs = {}
        alreadyExist = []

        for file in files:
            # No whitespace, dudes.
            basename = os.path.basename(file).strip()
            if (stripSuffix is not None) and \
               basename.endswith(stripSuffix):
                basename = basename[:-len(stripSuffix)]
            # Remove all spaces so we can space-concatenate
            # basenames on the command line and when
            # we list the contents.
            basename = basename.replace(" ", "_")
            if filePairs.has_key(basename) or fileHash.has_key(basename):
                alreadyExist.append(file)
            else:
                filePairs[file] = basename

        if alreadyExist:
            raise WorkspaceError, ("Basenames for files %s already exist in workspace; no files imported." % ", ".join(alreadyExist))

        # allPaths uses this, as does _storePreparedFiles().
        
        self.filePairs = filePairs

        #
        # Fourth section: actual import and DB update
        #

        self.runParameters = {"input_encoding": encoding,
                              "output_file_type": self.workspace.richFileType,
                              "output_encoding": "utf-8",
                              "input_file_type": file_type,
                              "inputFileType": fileIO}

        # Now, run the MAT engine to do the prep and import. The
        # import itself will happen in wrapup(). This is the only stuff
        # that needs to be in the transaction.
        
        t = self.workspace.beginTransaction(self)
        try:
            self.transaction = t
            MATEngineExecutionWorkspaceOperationMixin.do(self)
            self._storePreparedFiles()
            self.transaction = None
            t.commit()
        except:
            self.transaction = None
            t.rollback()
            raise

        imported = len(self.filePairs.keys())

        if fromCmdline:
            if imported == 1:
                plural = ""
            else:
                plural = "s"
            print "Imported %d file%s into folder '%s' in workspace %s." % (imported, plural, self.folderName, self.workspace.dir)

        self.imported = imported
        self.basenames = self.filePairs.values()

    # Obviously, this can only be called from within a transaction.
    
    def _storePreparedFiles(self):
        
        f = self.workspace.getFolder(self.folderName)

        # At this point, if the document has not been assigned segments,
        # we MUST assign one segment per zone.
        
        for path, iData in self.dataPairs.items():
            if not iData.getAnnotations(["SEGMENT"]):
                for zone in iData.getAnnotations(self.workspace.task.getAnnotationTypesByCategory("zone")):
                    # What else can we do?
                    iData.createAnnotation(zone.start, zone.end, "SEGMENT",
                                           {"annotator": None, "status": "non-gold"})
            b = self.filePairs[path]
            f.importFile(iData, b)

        basenames = self.filePairs.values()
        if self.workspace.logger:
            self.workspace.logger.logImport(f, basenames)
        db = self.workspace.getDB()
        for b in basenames:
            # openFile is not available until insertDocument is called, because
            # it now uses the DB.
            d = f._openFileBasename(b)
            db.insertDocument(b, b, self.workspace._documentStatus(d))
        if self.markGold:
            # Get all the imported basenames, and submit them to the markGold operation.
            o = f.getOperation("markgold", basenames = basenames, transaction = self.transaction)
            if self.fromCmdline:
                print "Marking gold", " ".join(basenames)
            o.do(user = self.users)
        elif self.markReconciled:
            self.workspace._updateDocumentStatuses(basenames, f,
                                                   self.transaction,
                                                   # Which segment annots do we update?
                                                   ["non-gold", "human gold"],
                                                   # What do we update them to?
                                                   "reconciled",
                                                   # Who do we attribute it to?
                                                   "GOLD_STANDARD")
        else:
            # We want to make sure that every annotated segment has an attribution.
            for b in basenames:
                doc = f._openFileBasename(b)
                # Copy them, because I'm going to modify the list, probably.
                segAnnots =  doc.orderAnnotations(["SEGMENT"])[:]
                modified = False
                for annot in doc.orderAnnotations(self.workspace.task.getAnnotationTypesByCategory('content')):
                    while segAnnots and (annot.start >= segAnnots[0].end):
                        segAnnots[0:1] = []
                    # If we run out of segment annotations, punt.
                    if not segAnnots:
                        break
                    # So we know the annotation starts before the current segment
                    # ends, and it can't actually be before it, can it? Let's check,
                    # just to be paranoid.
                    if (annot.start >= segAnnots[0].start) and \
                       (annot.end <= segAnnots[0].end):
                        # Now, the real work. If there's an annotation,
                        # either (a) the segment has to have an attribution,
                        # or (b) there has to be self.users. If neither,
                        # it's an error.
                        if self.users is not None:
                            segAnnots[0]["annotator"] = self.users
                            modified = True
                        elif not segAnnots[0].get("annotator"):
                            raise WorkspaceError, "imported document has annotated segment without an annotator (use the --user option to correct this error)"
                if modified:
                    f.saveFile(doc, b)
                    db.updateDocumentStatus(b, self.workspace._documentStatus(doc))
            
        # OK, everything is imported, marked and updated. Now, let's assign
        # users.
        if self.assignDocuments:
            o = self.workspace.getOperation("assign", basenames, transaction = self.transaction)
            if self.fromCmdline:
                print "Assigning", self.users
            o.do(user = self.users, fromImport = True)

        # And now, let's add them to a basename set.
        if self.basenameSet:
            # I don't see a reason not to do this directly.
            self.workspace._addToBasenameSet(self.basenameSet, *basenames)

#
# The more sophisticated list operation. Note that if I want
# the toplevel getFolderBasenames to do something comparable,
# I need to specialize that, too. Let's fix that.
#

class ListOperation(WorkspaceToplevelOperation):

    availability = UI_AVAILABLE | CMDLINE_AVAILABLE

    name = "list"

    @classmethod
    def getUsage(self, w):
        
        return """Usage: %prog [options] <dir> list ( <folder> ...)

<folder>: (optional) the name of the folder to list the contents of. For certain folders,
  extended information will be shown. If no folders are named, all folders will be listed.

Available folders are:\n\n""" + w.describeFolders()

    # For each basename, get the status in the DB. Note that
    # the "IN" keyword has no support in parameter substitution,
    # apparently for good reasons having to do with query plans.
    # I can either write an adaptor (which isn't possible because
    # I don't have access to a method that converts the parameters
    # to internal string literals) or I can format the string myself.
    
    def do(self):
        basenameDict = self.workspace._getFolderBasenames(*(self.args or self.workspace.folders.keys()))
        # I want to rewrite the basename dict so that it contains a pair of
        # the basename and the info.
        self.basenameDict = {}
        for key, basenames in basenameDict.items():
            folder = self.workspace.getFolder(key)
            bInfo = []
            self.basenameDict[key] = bInfo
            if basenames:
                bInfo += folder.listContents(basenames)
                        
        if self.fromCmdline:
            for key, bInfo in self.basenameDict.items():
                print key + ":"
                for info in bInfo:
                    basename = info["basename"]
                    del info["basename"]
                    if info:
                        print "  %s (%s)" % (basename, ", ".join([k + " " + v for k, v in info.items()]))
                    else:
                        print "  %s" % basename
                print                    
        
    def fnResult(self):
        return self.basenameDict

    def webResult(self):
        folder = self.args[0]
        return {"success": True,
                "basename_info": self.basenameDict[folder]}

class RemoveOperation(WorkspaceToplevelOperation):

    name = "remove"

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> remove <basename> ...

<basename>...: the basename(s) to be removed from the workspace.

Available basenames are:\n\n""" + " ".join(w.getBasenames())

    def do(self):
        t = self.workspace.beginTransaction(self)
        try:
            # I was just calling the core remove, but unfortunately, I need
            # to pass in the transaction.
            self.removed = self.workspace._removeBasenames(t, basenameList = self.args)
            if self.fromCmdline:
                if self.removed:
                    print "Removed", " ".join(self.removed), "."
                else:
                    print "No basenames removed."
            t.commit()
        except:
            t.rollback()
            raise

class OpenFileOperation(WorkspaceToplevelOperation):

    availability = CMDLINE_DEBUG_AVAILABLE | UI_AVAILABLE

    name = "open_file"

    argList = [Option("--user", type="string",
                      help = "open the file with a particular user. Required unless --read_only is present."),
               Option("--read_only", type="boolean", default=False,
                      help = "if present, open the document for reading and don't lock it")]

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> open_file [open_options] folder basename

<folder>: the folder to find the file in
<basename>: the basename to open

Available basenames are:\n\n""" + " ".join(w.getBasenames())

    def do(self, user = None, read_only = False, fromCmdline = True):
        # First, see if the document is locked.
        folder, basename = self.args
        t = self.workspace.beginTransaction(self)
        try:
            self.doc, fileBasename, lockId = self.workspace._openFile(folder, basename, user, read_only)
            t.commit()
        except:
            t.rollback()
            raise
        if fromCmdline and lockId:
            print "Locking %s with lock ID %s" % (basename, lockId)
        self.webResultSeed = {"read_only": read_only, "lock_id": lockId}
        if basename != fileBasename:
            self.webResultSeed["assigned_to"] = fileBasename[len(basename) + 1:]

    def webResult(self):
        doc = self.doc
        folder, file = self.args
        if doc is None:
            d = {"success": False,
                 "error": "Couldn't find basename '%s' in folder '%s'" % (file, folder)}
        else:
            d = {"success": True,
                 "doc": _jsonIO.renderJSONObj(doc)}
        d.update(self.webResultSeed)
        self.workspace.folders[folder].updateOpenFileWebResultSeed(doc, file, d)
        return d

    # Believe it or not, this is ONLY called in test suites.
    def fnResult(self):
        return self.doc, self.webResultSeed["lock_id"]

#
# Here's the assignment operator.
#

# Can we assign a document if it's locked? Only if we're copying an
# assigned document and not renaming an unassigned document.

class AssignOperation(WorkspaceToplevelOperation):

    name = "assign"
    
    argList = [Option("--user", type="string",
                      help = "assign the basename to the named user or users (comma-separated). Required.")]

    @classmethod
    def getUsage(self, w):
        
        return """Usage: %prog [options] <dir> assign [assign_options] <basename>... 

<basename>...: the basename(s) to be assigned to the specified users."""


    def do(self, user = None, fromImport = False):
        _in_transaction = self.transaction
        db = self.workspace.getDB()
        if user is None:
            raise WorkspaceError, "Can't assign a document without a user"
        users = user.split(",")
        for user in users:
            # And it better be a kosher user.
            if not db.userIsRegistered(user):
                raise WorkspaceError, ("can't lock a document using unregistered user '%s'" % user)
            if not db.userHasRole(user, "core_annotation"):
                raise WorkspaceError, "can't assign documents to a user without the core_annotation role"
        if _in_transaction:
            self._do(db, _in_transaction, users, fromImport)
        else:
            t = self.workspace.beginTransaction(self)
            try:
                self._do(db, t, users, fromImport)
                t.commit()
            except:
                t.rollback()
                raise

    def _do(self, db, t, users, fromImport):
        coreFolder = self.workspace.getFolder("core")
        basenames = self.args        
        curUserMap = db.usersForBasenames(basenames)
        for basename in basenames:
            # First, we check the assignments and status for the basename.
            curUsers = curUserMap[basename]
            if not curUsers:
                raise WorkspaceError, ("unknown basename %s" % basename)
            elif curUsers == [None]:
                # If it's unassigned, it must not be locked in order to continue,
                # and if fromImport is False, it must be either unannotated or uncorrected.
                if db.coreDocumentLocked(basename):
                    raise WorkspaceError, ("can't assign unassigned basename %s because it's locked" % basename)
                status = db.coreDocumentStatus(basename)
                if (not fromImport) and (status not in ["unannotated", "uncorrected"]):
                    raise WorkspaceError, ("can't assign unassigned basename %s because it's already been at least partially annotated" % basename)
                # OK, we're clear. Rename the document, assign the basename.
                # Make a copy for each user.
                # The pattern we're going to use is basename_<username>.
                # We do NOT try to get
                # it into the autotagger for segmenting and active learning,
                # since only workspace-wide autotagging can do that.
                t.addFilesToPreserve([os.path.join(coreFolder.dir, basename)])
                for user in users:
                    userBasename = basename + "_" + user
                    shutil.copyfile(os.path.join(coreFolder.dir, basename),
                                    os.path.join(coreFolder.dir, userBasename))
                    if self.workspace.logger:
                        self.workspace.logger.logCopy(coreFolder, basename, coreFolder, userBasename)
                    t.addFilesToRemove([os.path.join(coreFolder.dir, userBasename)])
                    db.insertDocument(userBasename, basename, status, user)
                coreFolder.removeFile(basename)
                db.removeUnassignedBasenameEntry(basename)
            elif None in curUsers:
                raise WorkspaceError, ("basename % is both assigned and unassigned" % basename)            
            else:
                if fromImport:
                    raise WorkspaceError, ("basename %s can't be already assigned if it's just been imported" % basename)
                # If it's already assigned,  it can't be assigned to the user already.
                # We don't care if it's locked.
                basenameHash = db.documentsForBasenames(basenames)
                importSettings = self.workspace.getOperationSettings("import")
                try:
                    workflow = importSettings["workflow"]
                except KeyError:
                    raise WorkspaceError, "workflow undefined in operation settings for import operation"
                # And we have to preprocess the steps, because of how we're
                # calling the engine.
                steps = importSettings.get("steps", None)
                if steps is not None:
                    steps = steps.split(",")
                    if steps == ['']:
                        steps = []
                importSettings = importSettings.copy()
                del importSettings["workflow"]
                try:
                    del importSettings["steps"]
                except KeyError:
                    pass
                for basename in basenames:
                    userOverlap = set(users) & set(curUserMap[basename])
                    if userOverlap:
                        raise WorkspaceError, ("users %s already assigned to basename %s" % \
                                               (",".join(userOverlap), basename))
                    # For already assigned documents, we want to prepare a document
                    # to save. We apply the steps in the import action. This
                    # has the unlikely possibility of introducing inconsistencies,
                    # but it's a little prettier than trying to undo the
                    # steps we find in the autotag operation.
                    # Then, we save that document as the
                    # new user basename for each user. We do NOT try to get
                    # it into the autotagger for segmenting and active learning,
                    # since only workspace-wide autotagging can do that.
                    
                    # Open one of them, doesn't matter which one.
                    d = coreFolder._openFileBasename(basenameHash[basename][0])
                    newD = self.workspace.task.newDocument(signal = d.signal)
                    # Maybe the engines are reusable - I'm not sure, and I'm
                    # not about to try to figure it out.
                    e = MAT.ToolChain.MATEngine(workflow = workflow, taskObj = self.workspace.task)
                    aggr = MAT.Operation.XMLOpArgumentAggregator(importSettings)
                    e.RunDataPairs([("<doc>", newD)], steps = steps,
                                   **e.aggregatorExtract(aggr, **importSettings))
                    # At this point, the new document should be ready to write, to each user.
                    for user in users:
                        userBasename = basename + "_" + user
                        coreFolder.saveFile(newD, userBasename)
                        t.addFilesToRemove([os.path.join(coreFolder.dir, userBasename)])
                        db.insertDocument(userBasename, basename, "unannotated", user)
        
# Users have roles: one for core annotation, and the rest for each reconciliation phase.

class RegisterUserOperation(WorkspaceToplevelOperation):

    name = "register_users"
    
    @classmethod
    def _createArgList(cls):
        recPhases = findReconciliationPhases()
        return [Option("--roles", type="string",
                       help = "Available roles. If omitted, roles will be core_annotation,%s. The string 'all' adds all roles. Otherwise, a comma-separated list of roles. Available roles are: core_annotation %s" % (",".join([r.name for r in recPhases.values() if r.roleIncludedInDefault]), " ".join(recPhases.keys())))]

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> register_users [register_user_options] <user>...

<user>: the name of a user to register for the workspace."""

    def do(self, roles = None):
        # Workspace is already locked. I'm not sure
        # this is going to be supported except on the command line.
        t = self.workspace.beginTransaction(self)
        try:            
            self.workspace._registerUsers(self.args, self._computeRoles(roles))
            t.commit()
        except:
            t.rollback()
            raise

    def _computeRoles(self, roles):
        recPhases = findReconciliationPhases()
        if roles is None:
            roles = ["core_annotation"] + [r.name for r in recPhases.values() if r.roleIncludedInDefault]
        elif roles == "all":
            roles = ["core_annotation"] + recPhases.keys()
        else:
            roles = roles.split(",")
            for role in roles:
                if (role != "core_annotation") and \
                   (not recPhases.has_key(role)):
                    raise WorkspaceError, ("Unknown user role '%s', not registering users." % role)
        return roles

class ListUserOperation(WorkspaceToplevelOperation):

    argList = [OpArgument("no_roles",
                          help = "don't show the roles")]
    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> list_users [list_user_options]"""

    name = "list_users"

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> list_users"""

    def do(self, no_roles = False):
        # Workspace is already locked. I'm not sure
        # this is going to be supported except on the command line.
        users = self.workspace._listUsers(no_roles = no_roles)
        if no_roles:
            if self.fromCmdline:
                for u in users: print u
            self.users = users
        else:
            if self.fromCmdline:
                for u, roles in users.items():
                    print u, ":", " ".join(roles)
            self.users = users

    # No way yet to add new toplevel operations to the Web service, unfortunately.
    
    def fnResult(self):
        return self.users

    def webResult(self):
        # I never return roles.
        users = self.users
        if type(users) is dict:
            users = users.keys()
        return {"success": True,
                "users": users}
                
#
# Here's a debugging object for you
#

class DumpDatabaseOperation(WorkspaceToplevelOperation):

    name = "dump_database"

    @classmethod
    def getUsage(self, w):
        db = w.getDB()
        return """Usage: %prog [options] <dir> dump_database [<table>...]

<table>: the name of a table to dump. If none are provided, the entire database will be dumped. Table names are: """ + " ".join(db.getTables())

    def do(self):
        db = self.workspace.getDB()
        data = db.dumpDatabase(tables = self.args or None)
        if self.fromCmdline:
            for d in data:
                print d["table"]
                print "=" * len(d["table"])
                strData = [[str(a) for a in r] for r in d["data"]]
                widths = [max([len(d["columns"][i])] + [len(r[i]) for r in strData]) for i in range(len(d["columns"]))]
                fmtString = "  ".join(["%-"+str(i)+"s" for i in widths])
                print fmtString % tuple(d["columns"])
                print fmtString % tuple(["-"*i for i in widths])
                for row in strData:
                    print fmtString % tuple(row)
                print

# For reference and completeness, I'm putting this here, even though
# it shows nothing interesting besides the list of users in MAT 2.0 initial.

class WorkspaceConfigurationOperation(WorkspaceToplevelOperation):
    
    name = "workspace_configuration"

    @classmethod
    def getUsage(self, w):
        return "Usage: %prog [options] <dir> workspace_configuration"

    def do(self):
        self.users = self.workspace.getDB().listUsers()
        self.phases = [p.name for p in self.workspace.reconciliationPhases]
        self.prioritizationName = self.workspace.getPrioritizationClassName()
        if self.fromCmdline:
            print "Task:", self.workspace.task.name
            print "Users:", ", ".join(self.users)
            print "Reconciliation phases:", ", ".join(self.phases)
            print "Logging:", (self.workspace.loggingEnabled and "yes") or "no"
            print "Prioritization:", (self.prioritizationName or "no")
            if self.prioritizationName:
                print "Prioritization mode:", self.workspace.getPrioritizationMode()

    def webResult(self):
        return {"success": True,
                "task": self.workspace.task.name,
                "users": self.users,
                "prioritization_class": self.prioritizationName,
                "prioritization_mode": self.workspace.getPrioritizationMode(),
                "logging_enabled": self.workspace.loggingEnabled,
                "available_phases": self.phases}

# Stuff for experiments.

class ListBasenameSetsOperation(WorkspaceToplevelOperation):

    availability = CMDLINE_AVAILABLE

    name = "list_basename_sets"

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> list_basename_sets ( <set_name>... )

<set_name>: the name of a basename set"""

    def do(self):
        setMap = self.workspace.getDB().getBasenameSetMap()
        if self.fromCmdline:
            for setName, setContents in setMap.items():
                if (not self.args) or (setName in self.args):
                    print "Basename set:", setName
                    print "Basenames:", ", ".join(setContents)
                    print

class AddToBasenameSetOperation(WorkspaceToplevelOperation):

    availability = CMDLINE_AVAILABLE

    name = "add_to_basename_set"

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> add_to_basename_set <set_name> <basename>...

<set_name>: the name of a basename set
<basename>: a known workspace basename"""

    def do(self):
        t = self.workspace.beginTransaction(self)
        try:
            self.workspace._addToBasenameSet(self.args[0], *self.args[1:])
            t.commit()
        except:
            t.rollback()
            raise

class RemoveFromBasenameSetOperation(WorkspaceToplevelOperation):

    availability = CMDLINE_AVAILABLE

    name = "remove_from_basename_set"

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> remove_from_basename_set <set_name> <basename>...

<set_name>: the name of a basename set
<basename>: a workspace basename"""

    def do(self):
        t = self.workspace.beginTransaction(self)
        try:
            self.workspace._removeFromBasenameSet(self.args[0], *self.args[1:])
            t.commit()
        except:
            t.rollback()
            raise

from MAT.CarafeTrain import TestRun, TrainingRun, ExperimentEngine, \
     WorkspaceCorpusSet, WorkspaceCorpus, fromXML

class RunExperimentOperation(WorkspaceToplevelOperation):

    availability = CMDLINE_AVAILABLE

    name = "run_experiment"

    # Either we have an experiment_file and an workspace_binding, or we define test_users,
    # test_basename_sets, test_basename_patterns, test_document_statuses, test_exclude_unassigned,
    # and everything else is the remainder.
    argList = [Option("--experiment_file", type="string",
                      help = "Specify an experiment file to use. If specified, --workspace_binding is also required. Either this or one of the --test_* parameters must be provided."),
               Option("--workspace_binding", type="string",
                      help = "variable in the workspace experiment file to which this workspace should be bound. Required if --experiment_file is present."),
               Option("--test_users", type="string",
                      metavar="user(,user...)",
                      help = "A comma-separated sequence of users to restrict the test corpus to. Not permitted if --experiment_file is provided."),
               Option("--test_basename_sets", type="string",
                      metavar="set(,set...)",
                      help = "A comma-separated sequence of basename set names to restrict the test corpus to. Not permitted if --experiment_file is provided."),
               Option("--test_basename_patterns", type="string",
                      metavar="pat(,pat...)",
                      help = "A comma-separated sequence of glob-style basename patterns to restrict the test corpus to. Not permitted if --experiment_file is provided."),
               Option("--test_document_statuses", type="string",
                      metavar="status(,status...)",
                      help = "A comma-separated sequence of document statuses to restrict the test corpus to. The background corpus will already be resetricted to 'partially gold,gold,reconciled'. Not permitted if --experiment_file is provided."),
               OpArgument("test_exclude_unassigned",
                          help = "If present, exclude unassigned documents from the test corpus. Not permitted if --experiment_file is provided."),
               OpArgument("workflow", hasArg = True,
                          help = "If --experiment_file is not present, this must be a workflow which contains a tagging step, specified in --tag_step."),
               OpArgument("tag_step", hasArg = True,
                          help = "If --experiment_file is not present, this must be a tag step in the workflow specified in --workflow."),
               OpArgument("csv_formula_output", hasArg = True,
                          help = "The format for the CSV output files. See the MATScore documentation for details.")]
               
    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> run_experiment [options]"""

    def do(self, experiment_file = None, workspace_binding = None, test_users = None,
           test_basename_sets = None, test_basename_patterns = None, test_document_statuses = None,
           test_exclude_unassigned = False, workflow = None, tag_step = None, csv_formula_output = None):
        # Doesn't require a transaction.
        if experiment_file and \
           (test_users or test_basename_sets or test_basename_patterns or
            test_document_statuses or test_exclude_unassigned or tag_step or workflow):
            raise WorkspaceError, ("can't specify experiment file as well as any of the test_* parameters, tag_step, workflow")
        if (experiment_file is not None) != (workspace_binding is not None):
            raise WorkspaceError, ("either both experiment_file and workspace_binding must be provided, or neither")
        if (not experiment_file) and \
           (not (test_users or test_basename_sets or test_basename_patterns or
                 test_document_statuses or test_exclude_unassigned)):
            raise WorkspaceError, ("no experiment_file, but also no specification of test corpus")
        if (not experiment_file) and \
           (not (workflow and tag_step)):
            raise WorkspaceError, ("both tag_step and workflow must be present if experiment_file is not")
        # Create an experiment directory.
        if not os.path.exists(os.path.join(self.workspace.dir, "experiments")):
            os.makedirs(os.path.join(self.workspace.dir, "experiments"))
        import datetime
        now = datetime.datetime.now()
        dirName = os.path.join(self.workspace.dir, "experiments",
                               now.strftime("%Y%m%d_%H%M%S") + "_" + ("%06d" % now.microsecond))
        self.experimentDir = dirName
        if experiment_file:
            e = ExperimentEngine(**fromXML(experiment_file, dir = dirName,
                                           bindingDict = {workspace_binding: self.workspace.dir}))
        else:
            testCorpus = WorkspaceCorpus("test",
                                         documentStatuses = test_document_statuses,
                                         basenameSets = test_basename_sets,
                                         users = test_users,
                                         includeUnassigned = not test_exclude_unassigned,
                                         basenamePatterns = test_basename_patterns)
            trainCorpus = WorkspaceCorpus("train", useWorkspaceRemainder = True)
            e = ExperimentEngine(dir = dirName, task = self.workspace.task,
                                 workspaceCorpusSets = [WorkspaceCorpusSet(self.workspace.dir,
                                                                           documentStatuses = "partially gold,gold,reconciled",
                                                                           workspaceCorpora = [testCorpus, trainCorpus])],
                                 models = [TrainingRun("exp_model", trainingCorpora = [("train", None)],
                                                       engineSettings = {"partial_training_on_gold_only": True})],
                                 runs = [TestRun("exp_run", model = "exp_model",
                                                 testCorpora = [("test", None)],
                                                 engineOptions = {"steps": tag_step, "workflow": workflow},
                                                 scoreOptions = {"restrictRefToGoldSegments": True},
                                                 enginePrepOptions = {"undo_through": tag_step,
                                                                      "workflow": workflow,
                                                                      "output_file_type": "mat-json"})])
        fmt = MAT.Score.ScoreFormat(csvFormulaOutput = csv_formula_output)
        e.run(format = fmt)

    def fnResult(self):
        return self.experimentDir

#
# core folder
#

# Autotag. Operation on "core".
# Tags the documents, marks them as uncorrected.

# Uses the current model. Whether or not it's local depends on
# how it's invoked. By default, it uses the server, but it might
# be local. Right now, it's always local.

# The autotag operation applies to all documents, and tags those
# SEGMENTs which are either unassigned or assigned to MACHINE.

# What if there are basenames specified to autotag? We
# don't want to mix documents autotagged by previous models, but we
# don't want to affect too many documents.

# If specific files are requested, the file-level behavior
# (gathering all the documents) is bypassed.

class AutotagOperation(WorkspaceOperation, MATEngineExecutionWorkspaceOperationMixin):

    name = "autotag"
    
    # I was hoping to be able to get away without specifying this, but
    # the Web service requires it in order to extract the arguments from the CGI request.
    
    argList = [Option("--lock_id", type="string", help="lock ID (if document is locked)")]

    def getAffectedFolders(self):        
        if self.state == "initial":
            return []
        else:
            return ["core"]

    def getTargetFolderAndDocuments(self):
        return "core", self._getTargetDocuments("core")

    def getAffectedFileBasenames(self):
        if hasattr(self, "affectedFileBasename"):
            return {self.affectedFileBasename: self.affectedBasenames[0]}
        else:
            return WorkspaceOperation.getAffectedFileBasenames(self)

    def allPaths(self):
        if hasattr(self, "affectedFileBasename"):
            paths = [os.path.join(self.folder.dir, self.affectedFileBasename)]
        else:
            paths = self.folder.getFiles(self.affectedBasenames)
        self.transaction.addFilesToPreserve(paths)
        return paths

    # lock_id is only
    # used from the UI. If the requested basenames have a lock that doesn't
    # match the lock ID, you can't do anything.
    
    def do(self, checkPathsAffected = True, lock_id = None):
        _in_transaction = self.transaction
        db = self.folder.workspace.getDB()
        if db.taggableDocumentsLocked():
            # In this situation, the only way we can proceed is if
            # there's a lock_id passed in and there's only one
            # affected basename and it's locked with that lock_id.
            if (lock_id is None) or (len(self.affectedBasenames) > 1):
                raise WorkspaceError, "can't autotag while documents are locked"
            idInfo = db.coreGetLockIDInfo(lock_id)
            if idInfo[1] != self.affectedBasenames[0]:
                raise WorkspaceError, "can't autotag while documents are locked"
            # Otherwise, make sure that the affected file basenames are just
            # the one for the lock info.
            self.affectedFileBasename = idInfo[0]
        if _in_transaction:
            self._do(checkPathsAffected = checkPathsAffected)
        else:
            t = self.folder.workspace.beginTransaction(self)
            self.transaction = t
            try:
                self._do(checkPathsAffected = checkPathsAffected)
                t.commit()
            except:
                t.rollback()
                raise
            
    def _do(self, checkPathsAffected = True):
        self.state = "initial"
        try:
            MATEngineExecutionWorkspaceOperationMixin.do(self, checkPathsAffected = checkPathsAffected)
        except:
            raise

    def getRunParameters(self, operationSettings):

        model = os.path.join(self.folder.workspace.modelDir, "model")
        if not os.path.exists(model):
            raise WorkspaceError, ("can't autotag because there's no model")

        self.state = "autotag"

        # In order to process the command lines really correctly, we
        # pass the operationSettings to an XMLOpArgumentAggregator.
        for key in ["tagger_local", "tagger_model",
                    "input_file", "input_file_type", "output_file",
                    "output_dir", "input_file_re", "input_encoding",
                    "input_dir", "output_file_type", "output_encoding",
                    "output_fsuff"]:
            if operationSettings.has_key(key):
                raise WorkspaceError, ("workspace operation settings don't permit %s option to MATEngine", key)
            
        return {"tagger_local": True,
                "tagger_model": model,
                "input_file_type": self.folder.fileType,
                "input_encoding": "utf-8"}

    def wrapup(self, dataPairs):
        db = self.folder.workspace.getDB()
        # Next, we'd better check to make sure that we can write each file.
        # If we can't, we want to raise an error. We should check each
        # individual file, because we don't want ANYthing to happen
        # if the writes can fail.
        if not os.access(self.folder.dir, os.W_OK | os.X_OK):
            raise WorkspaceError, ("folder %s not available for writing" % self.folder.folderName)
        for p, iData in dataPairs:
            fileBasename = os.path.basename(p)
            if not os.access(p, os.W_OK):
                raise WorkspaceError, ("file %s in folder %s not available for writing" % (fileBasename, self.folder.folderName))
            self.folder.saveFile(iData, fileBasename)
            db.updateDocumentStatus(fileBasename, self.folder.workspace._documentStatus(iData))

# The save operation has to do save the document, but ALSO it has to
# check to see whether the document should pop the queue. And if all
# the segments are no longer marked MACHINE, and there's at least one SEGMENT,
# mark it completed.

# This save operation is ONLY for the core folder. There's a separate
# save operation for the reconciliation.

# From a transaction point of view, I need to ensure that when we roll
# back, we roll back to the original content of the file. So I ALWAYS
# have to stash the original file somewhere.

# For experimental purposes, we can get log fragments on every save.
# The first log fragments, at the moment, are XML, from Callisto (ugh). I'd
# really prefer to get CSV logs, but beggars can't be choosers. If 
# --log is present (and I'm declaring it in the argList ONLY
# so I can get it via the Web service), I need to stash the file
# being saved, along with the log fragment, somewhere, checkpointed.

# When you save, and the document status changes, you have to return
# info that forces a folder update.

class SaveOperation(WorkspaceOperation):

    name = "save"

    argList = [OpArgument("doc", help = "document to save, as a JSON string", hasArg = True),
               Option("--lock_id", type="string", help="transaction ID for save"),
               Option("--release_lock", type="boolean", default=False, help="release the lock after save"),
               OpArgument("log", help = "log fragment (from UI) to trigger fine-grained progress monitoring", hasArg = True),
               OpArgument("log_format", help = "the format of the log fragment", hasArg = True),
               OpArgument("timestamp", help = "millisecond timestamp of log upload from the UI's point of view", hasArg = True),
               OpArgument("next_op", hasArg = True, help = "JSON string describing operation to perform after the save (for UI connectivity, mostly)")]

    availability = CMDLINE_DEBUG_AVAILABLE | UI_AVAILABLE

    def __init__(self, *args, **kw):
        WorkspaceOperation.__init__(self, *args, **kw)
        self.statusOp = None

    def getAffectedFolders(self):
        # Only markgold.
        if self.state == "statusop":
            return self.statusOp.getAffectedFolders()
        elif self.state == "statuschanged":
            return [self.folder.prettyName]
        else:
            return []

    def getTargetFolderAndDocuments(self):
        if self.state == "statusop":
            return self.statusOp.getTargetFolderAndDocuments()
        elif self.state == "statuschanged":
            return self.folder.prettyName, self._getTargetDocuments(self.folder.prettyName)
        else:
            return None, []

    def do(self, doc = None, next_op = None, lock_id = None, release_lock = False,
           log = None, log_format = None, timestamp = None):
        if lock_id is None:
            raise WorkspaceError, "can't save without lock ID"
        # Now we get the basename. Must check to ensure that
        # the lock ID matches. Need to get the file basename
        # from the transaction.
        db = self.folder.workspace.getDB()
        fileBasename, basename, user = db.coreGetLockIDInfo(lock_id)
        if basename != self.affectedBasenames[0]:
            raise WorkspaceError, ("wrong lock ID %s for basename %s" % (lock_id, self.affectedBasenames[0]))
        self.affectedFileBasename = fileBasename        
        t = self.folder.workspace.beginTransaction(self, filesToPreserve = [os.path.join(self.folder.dir, fileBasename)])
        try:
            curDocStatus = db.coreDocumentStatus(fileBasename)
            # Do this as early as possible, so that the timings are as close to
            # the final log entry in the UI as we can make them.
            # NOTE: Logging is not supported in 2.0 initial.
            if log and self.folder.workspace.logger:
                self.folder.workspace.logger.logLog(log, log_format, timestamp)
            if doc is not None:
                # It can be none, if it's not dirty.
                # First, make it into a document. The document
                # string is almost certainly not Unicode yet.
                docObj = self.folder.docIO.readFromByteSequence(doc, 'utf-8')

                # There damn well better only be one basename.
                self.folder.saveFile(docObj, fileBasename)
            else:
                docObj = self.folder._openFileBasename(fileBasename)

            # It used to  be that if the document had no segments
            # in the priority queue, it was done. But that's not really right.
            # The segments may not have been assigned a priority, and now
            # we have explicit markings on the document.
            # NOTE: Prioritizing is not supported in 2.0 initial. This code
            # is here because it'll be used eventually, and at the moment
            # it's too hard to excise it.
            segmenter = self.folder.workspace.getPrioritizer()
            if segmenter:
                segmenter.updateFromDoc(docObj, fileBasename)
            
            if next_op:
                from MAT import json
                nextOp = json.loads(next_op)
                opName = nextOp["operation"]
                del nextOp["operation"]
                o = self.folder.getOperation(opName, basenames = [basename], transaction = t)
                self.statusOp = o
                # Again, we hit the bug where in Python < 2.6.5,
                # the keys of **args can't be Unicode strings.
                nextOp = dict([(k.encode('ascii', 'replace'), v) for k, v in nextOp.items()])
                o.do(**nextOp)
                self.state = "statusop"
            else:
                newStatus = self.folder.workspace._documentStatus(docObj)
                db.updateDocumentStatus(fileBasename, newStatus)
                if newStatus != curDocStatus:
                    self.state = "statuschanged"
            if release_lock:
                if self.fromCmdline:
                    print "Releasing lock ID %s" % lock_id
                o = self.folder.getOperation("release_lock",
                                             basenames = [basename],
                                             transaction = t)
                o.do(lock_id = lock_id)
            t.commit()
        except:
            t.rollback()
            raise

    # Only used opening the the affected files, I hope.
    def getAffectedFileBasenames(self):
        return {self.affectedFileBasename: self.affectedBasenames[0]}

# Build a model. Operation on gold only.
# Optionally autotag the result.

class ModelBuildOperation(WorkspaceOperation):

    name = "modelbuild"

    argList = [OpArgument("config_name", help = "use a model settings configuration other than the default.", hasArg = True),
               OpArgument("do_autotag", help = "apply the autotag operation after the model is constructed."),
               OpArgument("autotag_basenames",
                          help = "(optional) if autotagging, a space-separated sequence of basenames to autotag. By default, all available files are autotagged.",
                          hasArg = True),
               OpArgument("autotag_basename",
                          action = "append",
                          help = "(optional) if autotagging, a single basename to autotag. By default, all available files are autotagged. Can be repeated.",
                          dest = "autotag_basename_list",
                          hasArg = True)]

    def __init__(self, *args, **kw):
        WorkspaceOperation.__init__(self, *args, **kw)
        self.autotagOps = []
    
    def getAffectedFolders(self):
        if self.state == "autotag":
            setA = set()
            for o in self.autotagOps:
                setA.add(o.getAffectedFolders())
            return list(setA)
        else:
            return []

    def allPaths(self):
        return self.folder.getFiles(self.affectedBasenames)

    def do(self, do_autotag = False, config_name = None,
           autotag_basenames = None, autotag_basename_list = None):

        if autotag_basename_list or autotag_basenames:
            autotag_basename_list = autotag_basename_list or []
            if type(autotag_basenames) is str:
                for b in autotag_basenames.split():
                    if b not in autotag_basename_list:
                        autotag_basename_list.append(b)

        operationSettings = self.getOperationSettings()
        
        if operationSettings is None:        
            raise WorkspaceError, ("no operation settings in task '%s' for operation '%s'" % (self.folder.workspace.task.name, self.name))

        # Only train on gold segments.
        operationSettings["partial_tagging_on_gold_only"] = True
        
        # Copy all the files to the tempdir.

        allPaths = self.allPaths()
        if not allPaths:
            raise WorkspaceError, "modelbuild: no paths affected"
        import MAT.ExecutionContext
        with MAT.ExecutionContext.Tmpdir(specifiedParent = self.folder.workspace.dir) as tmpDir:
            # Now, run the model engine.
            buildInfo = self.folder.workspace.task.getModelInfo(configName = config_name)
            if buildInfo is None:
                raise WorkspaceError, "unknown model build settings config"
            m = buildInfo.buildModelBuilder(**operationSettings)
            # Move old models aside, or delete them. 
            # Place the model in the "model" file. Put the basenames
            # in "model_basenames".
            modelPath = os.path.join(self.folder.workspace.modelDir, "model")
            m.run(modelPath, allPaths, tmpDir = tmpDir)
            fp = open(os.path.join(self.folder.workspace.modelDir, "model_basenames"), "w")
            for p in allPaths:
                fp.write(os.path.basename(p) + "\n")
            fp.close()

        # And now, let's see if we can do autotagging. We want to do it in the 
        # most conservative way, so we'll first see if the rich, incoming folder
        # has the autotag operation, and if it does, use that one. Otherwise,
        # use raw, unprocessed.

        # If autotag basenames were specified, I need to call BOTH folders, because
        # they're local operations. Otherwise, I need to call the most
        # conservative one, namely the rich, incoming folder.

        # Right now, if there are no paths affected, an error will be raised.
        # So I need to check that here and catch it.
        
        if do_autotag:
            self.state = "autotag"
            self.autotag_coda(autotag_basename_list)
        
    def autotag_coda(self, autotag_basename_list):
        o = self.folder.getOperation("autotag", basenames = autotag_basename_list)
        self.autotagOps = [o]
        o.doOperation()
        if not o.affectedBasenames:
            raise WorkspaceError, "autotag: no paths affected"

# And the markcompleted operation on autotagged must ensure that the
# affected basenames all have SEGMENTs none of which are MACHINE. And the segmenter
# has to be cleared.

class MarkGoldOperation(WorkspaceOperation):

    availability = CMDLINE_DEBUG_AVAILABLE | UI_AVAILABLE

    name = "markgold"

    argList = [OpArgument("user", hasArg = True,
                          help = "specify a user responsible for the gold marking"),
               Option("--lock_id", type="string", help="lock ID for marking gold (obligatory if document is locked)")]

    def getAffectedFolders(self):
        return [self.folder.prettyName]

    def getTargetFolderAndDocuments(self):
        return "core", self._getTargetDocuments("core")

    def getAffectedFileBasenames(self):
        return self.affectedFileBasenames

    def do(self, user = None, lock_id = None):
        _in_transaction = self.transaction
        if user is None:
            raise WorkspaceError, "markgold requires a user"
        # lock_id can be None, but it's gotta match what's in the DB.
        # if it IS none, no need to lock the document.
        db = self.folder.workspace.getDB()
        if not db.userIsRegistered(user):
            raise WorkspaceError, ("unknown user %s" % user)
        # If we have a lock_id, use it to collect the fileBasenames.
        # Otherwise, collect them yourself.
        if lock_id is not None:
            fileBasenames = {}
            # There had better be only one of these, otherwise this will
            # break...
            fileBasename, basename, lockingUser = db.coreGetLockIDInfo(lock_id)
            for b in self.affectedBasenames:
                if (b != basename) or (lockingUser != user):
                    raise WorkspaceError, ("wrong lock ID %s for basename %s" % (lock_id, b))
            fileBasenames[fileBasename] = basename
        else:
            fileBasenames = {}
            for b in self.affectedBasenames:
                fileBasename = self.folder.fileBasenameForUser(b, user)
                if self.folder.fileBasenameLocked(fileBasename):
                    raise WorkspaceError, ("can't marked locked file %s gold without lock ID" % fileBasename)
                fileBasenames[fileBasename] = b
        self.affectedFileBasenames = fileBasenames
        if _in_transaction:
            self._do(db, fileBasenames.keys(), user, _in_transaction)
        else:
            t = self.folder.workspace.beginTransaction(self)
            try:
                self._do(db, fileBasenames.keys(), user, t)
                t.commit()
            except:
                t.rollback()
                raise

    def _do(self, db, fileBasenames, user, transaction):
        self.folder.workspace._updateDocumentStatuses(fileBasenames, self.folder,
                                                      transaction,
                                                      # Which segment annots do we update?
                                                      ["non-gold"],
                                                      # What do we update them to?
                                                      "human gold",
                                                      # Who do we attribute it to?
                                                      user)

# I need this operation, really. Ultimately, this should happen
# segment by segment, but until I expose the segment boundaries and
# allow that, this will be a required option. Unlike markgold,
# I don't think we need to attribute a user here. But we need
# a user for validating the operation.

class UnmarkGoldOperation(WorkspaceOperation):

    availability = CMDLINE_DEBUG_AVAILABLE | UI_AVAILABLE

    name = "unmarkgold"

    argList = [OpArgument("user", hasArg = True,
                          help = "specify a user for the lock ID"),
               Option("--lock_id", type="string", help="lock ID for unmarking gold (obligatory if document is locked)")]

    def getAffectedFolders(self):
        return [self.folder.prettyName]

    def getTargetFolderAndDocuments(self):
        return "core", self._getTargetDocuments("core")

    def getAffectedFileBasenames(self):
        return self.affectedFileBasenames

    def do(self, user = None, lock_id = None):
        _in_transaction = self.transaction
        if user is None:
            raise WorkspaceError, "markgold requires a user"
        # lock_id can be None, but it's gotta match what's in the DB.
        # if it IS none, no need to lock the document.
        db = self.folder.workspace.getDB()
        if not db.userIsRegistered(user):
            raise WorkspaceError, ("unknown user %s" % user)
        # If we have a lock_id, use it to collect the fileBasenames.
        # Otherwise, collect them yourself.
        if lock_id is not None:
            fileBasenames = {}
            # There had better be only one of these, otherwise this will
            # break...
            fileBasename, basename, lockingUser = db.coreGetLockIDInfo(lock_id)
            for b in self.affectedBasenames:
                if (b != basename) or (lockingUser != user):
                    raise WorkspaceError, ("wrong lock ID %s for basename %s" % (lock_id, b))
            fileBasenames[fileBasename] = basename
        else:
            fileBasenames = {}
            for b in self.affectedBasenames:
                fileBasename = self.folder.fileBasenameForUser(b, user)
                if self.folder.fileBasenameLocked(fileBasename):
                    raise WorkspaceError, ("can't marked locked file %s gold" % fileBasename)
                fileBasenames[fileBasename] = b
        self.affectedFileBasenames = fileBasenames
        if _in_transaction:
            self._do(db, fileBasenames.keys(), user, _in_transaction)
        else:
            t = self.folder.workspace.beginTransaction(self)
            try:
                self._do(db, fileBasenames.keys(), user, t)
                t.commit()
            except:
                t.rollback()
                raise
            
    def _do(self, db, fileBasenames, user, transaction):
        self.folder.workspace._updateDocumentStatuses(fileBasenames, self.folder,
                                                      transaction,
                                                      # Which segment annots do we update?
                                                      ["human gold", "reconciled"],
                                                      # What do we update them to?
                                                      "non-gold",
                                                      # Who do we attribute it to?
                                                      None)
        
class ReleaseLockOperation(WorkspaceOperation):

    name = "release_lock"

    availability = NOT_AVAILABLE

    argList = [Option("--lock_id", type="string", help="lock ID")]

    def do(self, lock_id = None):
        _in_transaction = self.transaction
        if lock_id is None:
            raise WorkspaceError, "Can't release a lock without an ID"
        db = self.folder.workspace.getDB()
        # I'm wrapping this because I don't know whether this
        # operation is going to remain atomic.
        if _in_transaction:
            self._do(db, lock_id)
        else:
            t = self.folder.workspace.beginTransaction(self)
            try:
                self._do(db, lock_id)
                t.commit()
            except:
                t.rollback()
                raise

    def _do(self, db, lock_id):
        db.unlockCoreLock(lock_id)

# Finally, the emergency force unlock.

# Originally, I coded this in such a way that it was more fragile
# than was appropriate. 

class ForceUnlockOperation(WorkspaceOperation):

    name = "force_unlock"

    availability = CMDLINE_AVAILABLE

    argList = [OpArgument("user", hasArg = True,
                          help = "the user who's locked the basename")]

    def do(self, user = None):
        if user is None:
            raise WorkspaceError, "can't force unlock a basename without a user"
        t = self.folder.workspace.beginTransaction(self)
        try:
            self._do(user)
            t.commit()
        except:
            t.rollback()
            raise

    def _do(self, user):
        if self.folder.folderName == "core":
            db = self.folder.workspace.getDB()
            unlocked = db.forceUnlockCoreBasenames(user, self.affectedBasenames)
            if self.fromCmdline:
                if unlocked:
                    print "Unlocked core documents:", " ".join(unlocked)
                else:
                    print "Unlocked no documents."
        elif self.folder.folderName == "reconciliation":
            db = self.folder.workspace.getDB()
            unlocked = db.forceUnlockReconciliationBasenames(user, self.affectedBasenames)
            if self.fromCmdline:
                if unlocked:
                    print "Unlocked reconciliation basenames:", " ".join(unlocked)
                else:
                    print "Unlocked no basenames."

#
# Reconciliation phases
#

from MAT.ReconciliationDocument import ReconciliationDoc, \
     _getListValue, SPECIAL_VOTE_VALUES
from MAT.ReconciliationPhase import ReconciliationPhase, HumanDecisionPhase, ReconciliationError

# I don't list these explicitly because I want the opportunity
# to define others.

_AVAILABLE_RECONCILIATION_PHASES = None

def findReconciliationPhases():
    global _AVAILABLE_RECONCILIATION_PHASES
    if _AVAILABLE_RECONCILIATION_PHASES is None:
        _AVAILABLE_RECONCILIATION_PHASES = WorkspaceReconciliationPhase.findVisible()
    return _AVAILABLE_RECONCILIATION_PHASES

# We're going to make these all be classmethods.

class WorkspaceReconciliationPhase(ReconciliationPhase):

    name = None
    # This is LOCAL, because we're looking in
    # the class dict (below), and not just
    # checking an attribute, which may be inherited.
    visible = False
    
    @classmethod
    def findVisible(cls, d = None):
        visible = True
        if cls.__dict__.has_key("visible"):
            visible = cls.visible
        if d is None:
            d = {}
        if visible:
            d[cls.name] = cls
        for subCls in cls.__subclasses__():
            subCls.findVisible(d)
        return d

    def __init__(self, db, **kw):
        self.db = db
        ReconciliationPhase.__init__(self, **kw)

    multipleDocumentsRequired = True
    # In general, adding votes is permitted.
    # But I'm not ruling out a situation where
    # it won't be.
    addingVotesPermitted = True

    roleIncludedInDefault = True

    # These methods have different signatures.

    def prepPhase(self, op, basenameHash, basenames, **kw):
        ReconciliationPhase.prepPhase(self, **kw)

    def reconcile(self, docObj, user, vDict, basename, **kw):
        ReconciliationPhase.reconcile(self, docObj, user, vDict, **kw)

    def forceRedo(self, annotatorsToRepeat, basename = None):
        self.db.forceReconciliationRedo(basename, annotatorsToRepeat)

# Originally, I was importing TestRun and TrainingRun from MAT.Bootstrap,
# but I use the ones from MAT.CarafeExperiment in run_experiment, so...

import MAT.Bootstrap

class CrossValidationPhase(WorkspaceReconciliationPhase):

    argList = [Option("--folds", type="int", help="if cross-validation is enabled, number of cross-validation folds")]

    name = "crossvalidation_challenge"

    multipleDocumentsRequired = False

    DEFAULT_FOLDS = 8

    def __init__(self, db, folds = None, **kw):
        WorkspaceReconciliationPhase.__init__(self, db, **kw)
        self.pData["folds"] = folds
    
    # OK, so first, we prepare a document set for ALL the basenames,
    # and partition it randomly, according to the number of folds.
    
    def prepPhase(self, op, basenameHash, basenames, **kw):
        db = self.db
        folds = self.pData.get("folds")
        params = op.getOperationSettings()
        if (folds is None) and (params is not None):
            # Not on the command line.
            folds = params.get("folds")
        if folds is not None:
            folds = int(folds)
        else:
            # Use default folds.
            folds = self.DEFAULT_FOLDS
        # Split up all the basenames into <folds> partitions.
        dSet = MAT.Bootstrap.DocumentSet("cv", partitions = [("p%d" % i, 1) for i in range(folds)],
                                         prefix = op.folder.dir, fileList = basenameHash.keys())
        # Then, we need to (a) figure out which partitions need to be
        # cross-validated (just those which contain something from basenames) and
        # (b) replace in the document set all the docnames for the appropriate
        # basenames.

        # The problem is that we need all the docs for a given basename in the same
        # document set, because of how we're doing the cross-validation. This may
        # skew the size of the sets a bit. The other problem is that we actually
        # only need to tag ONE of the basenames in the target. So we'll tag them all,
        # and then pick the first.

        # Remember, the set has to be deconflicted (probably using consolidate())
        # before it's run. Actually, there's no need in this case, because all
        # the files are already in the core directory, so they have to be
        # deconflicted already.

        # So first, find the partitions to test.

        # Actually, the simplest way to deal with the replacement problem
        # is to generate a whole new set of document sets, one for each
        # partition, based on the partitions.
        
        bSet = set(basenames)
        partitionsToTest = []
        convertedSets = {}
        basenameToPartition = {}
        for p, files in dSet.partitionDict.items():
            # If the seed set was small enough, files may be an empty list.
            bList = [os.path.basename(f) for f in files]
            if set(bList) & bSet:
                partitionsToTest.append(p)
            docs = []
            if bList:
                for b in bList:
                    for docName in basenameHash[b]:
                        docs.append(docName)
                    if b in basenames:
                        # I only need the first one.
                        basenameToPartition[b] = (p, basenameHash[b][0])            
                convertedSets[p] = MAT.Bootstrap.DocumentSet(p, prefix = op.folder.dir, fileList = docs)

        allPartitions = convertedSets.keys()

        # OK. Now I have a bunch of document sets, and they have the files I need.
        # Next, we want to configure a bootstrapper.
        bsDir = os.path.join(op.folder.workspace.dir, "crossvalidation_dir")
        if os.path.exists(bsDir):
            shutil.rmtree(bsDir)

        engineOptions = {}
        prepOptions = {"output_file_type": op.folder.fileType}
        modelOptions = {}

        if params is not None:
            for p, val in params.items():
                if p.startswith("model_"):
                    modelOptions[p[len("model_"):]] = val
                elif p.startswith("engine_"):
                    engineOptions[p[len("engine_"):]] = val
                elif p.startswith("prep_"):
                    prepOptions[p[len("prep_"):]] = val
        else:
            # We need some defaults here. So by default, I
            # think we'll go get the workspace settings for autotag,
            # and undo through that setting.
            settings = op.getWorkspace().getOperationSettings("autotag")
            if not settings.get("workflow"):
                raise WorkspaceError, "can't find workflow default for crossvalidation by looking in autotag settings"
            engineOptions["workflow"] = settings["workflow"]
            prepOptions["workflow"] = settings["workflow"]
            if not settings.get("steps"):
                raise WorkspaceError, "can't find steps default for crossvalidation by looking in autotag settings"
            steps = settings.get('steps').split(",")
            if steps == ['']:
                steps = []
            if not steps:
                raise WorkspaceError, "can't find steps default for crossvalidation by looking in autotag settings"
            prepOptions["undo_through"] = steps[0]
            engineOptions["steps"] = ",".join(steps)
        e = MAT.Bootstrap.Bootstrapper(dir = bsDir, task = op.folder.workspace.task,
                                       corpora = convertedSets.values(),
                                       models = [MAT.Bootstrap.TrainingRun("model_excluding_" + p,
                                                                           trainingCorpora = [(otherP, None) for otherP in allPartitions
                                                                                              if otherP != p],
                                                                           engineSettings = modelOptions or None)
                                                 for p in partitionsToTest],
                                       runs = [MAT.Bootstrap.TestRun("test_" + p, model = "model_excluding_" + p,
                                                                     testCorpora = [(p, None)],
                                                                     engineOptions = engineOptions or None,
                                                                     enginePrepOptions = prepOptions or None)
                                               for p in partitionsToTest])
        e.run()
        # Now that we're done, we want to collect a single instance
        # of each basename.
        os.makedirs(os.path.join(bsDir, "cv_input"))
        _jsonIO = MAT.DocumentIO.getDocumentIO('mat-json', task = op.folder.workspace.task)
        for b, (p, doc) in basenameToPartition.items():
            # It's not enough just to copy the file. The test
            # step will produce segments which are non-gold, so we
            # have to mark them gold.
            d = _jsonIO.readFromSource(os.path.join(bsDir, "runs", "test_" + p, "model_excluding_" + p, "hyp", doc+".prepped.tag.json"))
            for annot in d.getAnnotations(["SEGMENT"]):
                annot["status"] = "human gold"
            _jsonIO.writeToTarget(d, os.path.join(bsDir, "cv_input", b))
        # And now, add the documents for each basename to the basenameHash.
        # Later, we're going to do an os.path.join(), but it turns out that
        # if the pathname is absolute, os.path.join() is a no-op on the suffix.
        for basename in basenames:
            basenameHash[basename].append(os.path.join(op.folder.workspace.dir,
                                                       "crossvalidation_dir", "cv_input", basename))

    def createAssignments(self, recDoc, phaseUsers, **kw):
        cvUsers = set()
        # Find all the segments which are about to be adjudicated,
        # collect the users.
        for annot in recDoc.getAnnotations(["SEGMENT"]):
            cvUsers.update(_getListValue(annot, "annotator"))
        # Remove all the users that aren't in phaseUsers.
        cvUsers = cvUsers & set(phaseUsers)
        return [("crossvalidation_challenge", u) for u in cvUsers if u != "MACHINE"]

    @classmethod
    def checkOrder(cls, pList):
        if cls is not pList[0]:
            # Gotta be first.
            raise WorkspaceError, "crossvalidation phase must be first"

    # The special value "bad boundaries" CANNOT be a winning vote.
    
    def reconcile(self, docObj, user, vDict, basename, **kw):
        # Reconcile if the segment MACHINE vote also
        # has the reviewed votes for all the other owners of the segment.
        # We only want to consider segments which actually have votes,
        # which is what vDict contains.
        for annot, segVotes in vDict.items():
            if annot["status"] != "human gold":
                continue
            if segVotes:
                owners = _getListValue(annot, "annotator")
                if owners:
                    # The list of owners will include MACHINE.
                    ownerSet = set(owners)
                    for vote in segVotes:
                        annotators = _getListValue(vote, "annotator")
                        if annotators:
                            if ("MACHINE" in annotators) and \
                               (vote.get("content") != "bad boundaries") and \
                               (ownerSet == set(annotators)):
                                # We're good.
                                annot["status"] = "reconciled"
                                vote["chosen"] = "yes"
                                # No need to look at any other votes
                                # for this segment.
                                break

    def userReviewExpected(self, user, segment):
        return user in _getListValue(segment, "annotator")

class HumanVotePhase(WorkspaceReconciliationPhase):

    name = "human_vote"

    def createAssignments(self, recDoc, phaseUsers):
        return [("human_vote", u) for u in phaseUsers]

    # The special value "bad boundaries" CANNOT be a winning vote.
    def reconcile(self, docObj, user, vDict, basename, **kw):
        # Let's reconcile if one vote has the majority of all users voting.
        # Not counting MACHINE, of course.
        for annot, segVotes in vDict.items():
            # This will never be in there, of course, because it's
            # only a dictionary of segments which actually have votes.
            # But we'll still check.
            if annot["status"] != "human gold":
                continue
            if segVotes:
                allVoters = _getListValue(annot, "reviewed_by")
                # Can't reconcile a segment unless it has a voter.
                if len(allVoters) > 0:
                    import math
                    limit = len(allVoters) / 2.0
                    for vote in segVotes:
                        annotators = _getListValue(vote, "annotator")
                        if annotators:
                            # Note that looking at only the actual voters
                            # rules out "fake" assignments like CROSSVALIDATION_USER.
                            votesFor = set(allVoters) & set(annotators)
                            # The number of voters has to be more than half.
                            if (len(votesFor) > limit) and \
                               (vote.get("content") != "bad boundaries"):
                                # If "bad boundaries" won, the segment
                                # CAN'T be reconciled. So we break anyway.
                                annot["status"] = "reconciled"
                                vote["chosen"] = "yes"
                                break

# Inherits from HumanDecisionPhase, THEN WorkspaceReconciliationPhase.
# So I have to be VERY careful that I overwrite the HumanDecisionPhase
# methods that have the "wrong" signature.

class WorkspaceHumanDecisionPhase(HumanDecisionPhase, WorkspaceReconciliationPhase):

    name = "human_decision"

    roleIncludedInDefault = False

    def __init__(self, db, human_decision_user = None, **kw):
        if (human_decision_user is not None) and \
               not db.userIsRegistered(human_decision_user):
            raise WorkspaceError, ("human_decision user '%s' not registered" % human_decision_user)
        WorkspaceReconciliationPhase.__init__(self, db, **kw)
        self.pData["human_decision_user"] = human_decision_user

    def createAssignments(self, *args):
        try:
            return HumanDecisionPhase.createAssignments(self, *args)
        except ReconciliationError, msg:
            raise WorkspaceError, msg

    @classmethod
    def checkOrder(cls, pList):
        try:
            HumanDecisionPhase.checkOrder(pList)
        except ReconciliationError, msg:
            raise WorkspaceError, msg

    def reconcile(self, docObj, user, vDict, basename, **kw):
        HumanDecisionPhase.reconcile(self, docObj, user, vDict, **kw)

#
# Reconciliation folder and operations
#

class ReconciliationWorkspaceFolder(WorkspaceFolder):

    def fileBasenameLocked(self, fileBasename):
        return self.workspace.getDB().reconciliationBasenameLocked(fileBasename)

    # The semantics of "reviewed_by" are such that the frontend
    # can rely on the contents of that value to see whether
    # that segment has been reviewed. So in the ase where a review
    # is forced by the user, we have to make sure that the
    # user is not in the reviewed_by list.

    def prepareForEditing(self, doc, fileBasename, user, lockId):
        # lock it.
        db = self.workspace.getDB()
        db.lockReconciliationBasename(lockId, fileBasename, user)
        # Now, we have to augment the document with indications of
        # which segments the user should review. This should happen
        # whenever you open a file, whether or not nextdoc is involved.
        pObj = findReconciliationPhases()[db.reconciliationPhaseForBasename(fileBasename)](db)
        vDict = doc._votesForSegments()
        for a in doc.getAnnotations(["SEGMENT"]):
            # If the user should review the segment but it hasn't
            # been reviewed, set to_review.
            if (a["status"] == "human gold") and pObj.userReviewExpected(user, a):
                reviewIt = False
                if user not in _getListValue(a, "reviewed_by"):
                    reviewIt = True
                elif pObj.forceReviewByUser(user, a, vDict.get(a)):
                    a["reviewed_by"] = ",".join([u for u in _getListValue(a, "reviewed_by") if u != user])
                    reviewIt = True
                if reviewIt:
                    a["to_review"] = "yes"

    def listContents(self, basenames):
        db = self.workspace.getDB()
        bPairs = []
        for basename, currentPhase, lockedBy, currentAssignments in db.reconciliationInfo(basenames):
            info = {"basename": basename, "current phase": currentPhase}
            if lockedBy:
                info["locked by"] = lockedBy
            if currentAssignments:
                info["assigned to"] = ",".join(currentAssignments)
            bPairs.append(info)
        return bPairs

class ReconciliationSaveOperation(SaveOperation):

    argList = [OpArgument("doc", help = "document to save, as a JSON string", hasArg = True),
               Option("--lock_id", type="string", help="lock ID for save"),
               Option("--release_lock", type="boolean", default=False, help="release the lock after save")]
    
    def do(self, doc = None, lock_id = None, release_lock = False):
        if lock_id is None:
            raise WorkspaceError, "can't save without lock ID"
        # Now we get the basename. Must check to ensure that
        # the transaction ID matches.
        basename = self.affectedBasenames[0]
        db = self.folder.workspace.getDB()
        if not db.reconciliationLockIDMatches(lock_id, basename):
            raise WorkspaceError, ("wrong lock ID %s for basename %s" % (lock_id, basename))

        t = self.folder.workspace.beginTransaction(self, filesToPreserve = [os.path.join(self.folder.dir, basename)])
        try:

            if doc is not None:
                # It can be none, if it's not dirty.
                # First, make it into a document. The document
                # string is almost certainly not Unicode yet.

                docObj = self.folder.docIO.readFromByteSequence(doc, 'utf-8')

                basename, user, recPhase = db.reconciliationGetLockInfo(lock_id)
                pObj = findReconciliationPhases()[recPhase](db)
                pObj.updateSavedSegments(self.folder.workspace.task, docObj, basename = basename)
                
                # There damn well better only be one basename. If I'm going
                # to save the document, I had better update the IDs, in case
                # some yahoo has to forcibly unlock it.

                self.folder.saveFile(docObj, basename)

            if release_lock:
                if self.fromCmdline:
                    print "Releasing lock %s" % lock_id
                o = self.folder.getOperation("release_lock",
                                             basenames = [basename],
                                             transaction = t)
                o.do(lock_id = lock_id)
                
            t.commit()
        except:
            t.rollback()
            raise

class ReconciliationReleaseLockOperation(WorkspaceOperation):

    name = "release_lock"

    availability = NOT_AVAILABLE

    argList = [Option("--lock_id", type="string", help="lock ID")]

    def do(self, lock_id = None):
        _in_transaction = self.transaction
        if lock_id is None:
            raise WorkspaceError, "Can't release a lock without an ID"
        db = self.folder.workspace.getDB()
        # We may need this later, and we're unlocking the transaction now.
        # I need the basename info to cache the current basename to
        # rollback the transaction if necessary.
        basename, user, recPhase = db.reconciliationGetLockInfo(lock_id)
        if basename is None:
            raise WorkspaceError, ("Couldn't find an active basename for lock ID '%s'" % lock_id)

        if _in_transaction:
            self._do(db, lock_id, basename, user, recPhase, _in_transaction)
        else:            
            t = self.folder.workspace.beginTransaction(self, filesToPreserve = [os.path.join(self.folder.dir, basename)])
            try:
                self._do(db, lock_id, basename, user, recPhase, t)
                t.commit()
            except:
                t.rollback()
                raise

    def _do(self, db, lock_id, basename, user, recPhase, transaction):

        db.unlockReconciliationLock(lock_id)

        # At this point, we need to check a bunch of things. First,
        # we need to update all the created IDs. Next, we want
        # to know whether the current user is done with this document.
        # If the user is done, we want to know whether all users have
        # looked at the document. If they have, we want to see if any
        # of the segments are now reconciled (which is a phase-specific
        # check). If all segments are now reconciled, or if there are no
        # more phases, the document exits reconciliation.

        # Update the created IDs. This is probably necessary ONLY
        # if doc is not None (i.e., if it comes from the UI), but
        # I'm not completely convinced, so let's check it anyway.

        # Load it, because we need to do a lot with it.
        docObj = self.folder.openFile(basename)
        vDict = docObj._votesForSegments()

        # Here's why this algorithm doesn't loop. In human voting, you
        # can add votes, which means that the next folks who see it
        # will need to review the segment again. (Obviously, this
        # means that the previous users in the round implicitly voted
        # against the option, but they ALREADY did that by choosing
        # not to add the vote).

        # Well, maybe we can salvage this. It SHOULD loop if this is
        # the only user - if no one else can add anything, it's done.
        # It should also loop if no one else can add anything.

        pObj = findReconciliationPhases()[recPhase](db)
        userAssignedToPhase = True
        while True:
            if userAssignedToPhase and (not pObj.currentUserIsDone(docObj, user)):
                break
            else:
                if userAssignedToPhase:
                    print "Current user is done", user, basename, recPhase
                    # Mark the user as done in the DB.
                    # Mark it done in the phase, so the user never
                    # gets this document again.
                    db.reconciliationUserDoneInPhase(user, basename, recPhase)
                # Are ALL users done with this document?
                # Note that in some scenarios, this is irrelevant - e.g., if
                # you know how many human voters you have, and a majority has
                # already voted. I'm not going to implement that yet, although
                # I could. Later, we may be doing on-demand assignment, in which
                # case the option wouldn't be available anyway.
                if not db.reconciliationDocumentDoneInPhase(basename, recPhase):
                    break
                else:
                    print "Current document is done", user, basename, recPhase
                    pObj.reconcile(docObj, user, vDict, basename)
                    # If it's the last phase, or all the segments are reconciled,
                    # exit. Otherwise, advance the document to the next phase.
                    phases = self.folder.workspace.reconciliationPhases
                    allSegsReconciled = docObj._allSegmentsReconciled()
                    if (pObj.__class__ is phases[-1]) or allSegsReconciled:
                        # Exit.
                        if allSegsReconciled:
                            print "Current document is reconciled", user, basename, recPhase
                        else:
                            print "Current document is exiting without being completely reconciled", user, basename, recPhase
                        self._exitReconciliation(docObj, basename, transaction)
                        break
                    else:
                        # Move to the next phase.
                        # Be sure to save out the document. pObj.reconcile() ALSO
                        # modifies the document, but we only need to save it if
                        # we're not exiting reconciliation.
                        self.folder.saveFile(docObj, basename)
                        pObj = phases[phases.index(pObj.__class__) + 1](db)
                        recPhase = pObj.name
                        print "Current document is advancing", user, basename, recPhase
                        db.advanceReconciliationDocument(basename, recPhase)
                        # Can we keep looping? The condition is that (a) there must
                        # be only one user, or (b) you can't add annotations on the
                        # next phase. The crossvalidation challenge phase is tricky,
                        # because there's the added twist that only the annotator
                        # gets to see it; but sometimes, in double annotation, you might
                        # get the same segment with multiple annotators (reviewed in
                        # different copies of the same document). In this case, conveniently,
                        # crossvalidation challenge is the first phase anyway,
                        # and this check only applies to non-initial phases.
                        usersForPhase = db.usersAvailableForPhase(basename, recPhase)
                        if len(usersForPhase) > 1 and \
                           pObj.addingVotesPermitted:
                            break
                        else:
                            userAssignedToPhase = user in usersForPhase

    def _exitReconciliation(self, docObj, basename, transaction):
        # Save the damn document first, because later I read it.
        self.folder.saveFile(docObj, basename)
        # First, merge the document in with its sources in the core folder.
        # Finally, get it out of the reconciliation folder.
        self.folder.workspace._removeFromReconciliation([basename], self.folder, transaction, verbose = self.fromCmdline)


# Here's an emergency operation for you. I coded this much
# too fragilely in the first round. For instance, I can't
# pay attention to the affectedBasenames, since the file may have
# not made it into the folder due to an error.

class RemoveFromReconciliationOperation(WorkspaceOperation):

    availability = CMDLINE_AVAILABLE

    name = "remove_from_reconciliation"

    argList = [OpArgument("dont_reintegrate",
                          help = "By default, reconciliation updates are integrated back into the core documents. Use this flag to skip that step.")]

    def do(self, dont_reintegrate = False):
        # Disabled a bunch of tests, too. See WorkspaceReconciliationTestCase in
        # test/mat_workspace_unittest.py. This must be re-enabled when we get
        # this working.
        raise WorkspaceError, "workspace reconciliation has no UI support yet - postponed to next release"

        # Let's first start by getting EITHER the inputBasenames
        # (those which were listed explicitly, whether or not they're in the
        # folder) OR the affectedBasenames. The effect of this is when
        # there was an explicit list, we ALWAYS use it.
        basenames = self.inputBasenames or self.affectedBasenames
        if not basenames:
            print "No basenames requested for removal."
            return
        t = self.folder.workspace.beginTransaction(self)
        try:
            self.folder.workspace._removeFromReconciliation(basenames, self.folder, t,
                                                            verbose = self.fromCmdline,
                                                            reintegrate = not dont_reintegrate)
            t.commit()
        except:
            t.rollback()
            raise

# Rules: if there's only one basename for the document, and cross-validation
# isn't present, then there's no need to reconcile.

# In the transaction, all we need to worry about is the file we're about to add.

class SubmitToReconciliationOperation(WorkspaceOperation):
    
    availability = CMDLINE_AVAILABLE
               
    name = "submit_to_reconciliation"

    # Let's postpone the creation of the arglist.
    @classmethod
    def _createArgList(cls):
        recPhases = findReconciliationPhases()
        allOptions = []
        for p in recPhases.values():
            allOptions += p.argList
        allOptions.append(Option("--score_common_regions", type="boolean", default=False,
                                 help = "if present, generate a pairwise score of all the common regions"))
        return allOptions
    
    def do(self, score_common_regions = False, **kw):
        # Disabled a bunch of tests, too. See WorkspaceReconciliationTestCase in
        # test/mat_workspace_unittest.py. This must be re-enabled when we get
        # this working.
        raise WorkspaceError, "workspace reconciliation has no UI support yet - postponed to next release"
        if not self.folder.workspace.reconciliationPhases:
            raise WorkspaceError, "Can't submit basenames to reconciliation: no reconciliation phases declared"
        basenames = self.affectedBasenames
        # First things first: lock them for reconciliation, and
        # enter them in the reconciliation table.
        # First, they can't be locked.
        db = self.folder.workspace.getDB()
        phases = self.folder.workspace.reconciliationPhases
        multipleDocumentsRequired = True
        phaseObjList = []
        for p in phases:
            if not p.multipleDocumentsRequired:
                multipleDocumentsRequired = False
            phaseObjList.append(p(db, **kw))
        # I need the whole DB, if I'm going to do the cross-validation.
        basenameHash = db.documentsForBasenames()
        for basename in basenames:
            docs = basenameHash[basename]           
            if multipleDocumentsRequired and (len(docs) == 1):
                raise WorkspaceError, ("no basenames submitted: basename '%s' only has one document to reconcile" % basename)
            if db.coreDocumentLocked(basename):
                raise WorkspaceFileLockedError, ("no basenames submitted: can't submit locked document '%s' for reconciliation" % basename)

        # Up to this point, we're just checking things, not changing anything.

        t = self.folder.workspace.beginTransaction(self)
        try:
            for p in phaseObjList:
                p.prepPhase(self, basenameHash, basenames)
            assignmentDict = dict([(p.name, db.listUsersForRole(p.name)) for p in phases])
            print "assignment dict", assignmentDict
            recFolder = self.folder.workspace.folders["reconciliation"]
            params = self.getOperationSettings()
            adminAttrs = None
            try:
                adminAttrs = _getListValue(params, "rec_admin_attrs")
            except:
                pass
            scoreInputs = []
            for basename in basenames:
                # No transaction ID here.
                for d in basenameHash[basename]:
                    db.lockCoreDocument(None, d, "RECONCILIATION")
                # We have to collect all the basenames and create a reconciliation
                # document.
                docs = [self.folder._openFileBasename(d) for d in basenameHash[basename]]
                recDoc = ReconciliationDoc.generateReconciliationDocument(self.folder.workspace.task, docs,
                                                                          verbose = (self.fromCmdline and sys.stdout) or None)
                if score_common_regions:
                    scoreInputs.append((basename, recDoc, zip(basenameHash[basename], docs)))
                t.addFilesToAdd([os.path.join(recFolder.dir, basename)])
                recFolder.saveFile(recDoc, basename)
                # Now, we want to prepare the assignments. For
                # the crossvalidation_challenge, it's the users who
                # own the segments to be reviewed in the reconciliation doc.
                # For human_vote, it's every registered user. For
                # human_decision, it's either a randomly chosen user with the role or
                # a specially-assigned user.
                # Now, we want to enter it in the reconciliation table.
                assignments = []
                for p in phaseObjList:
                    assignments += p.createAssignments(recDoc, assignmentDict[p.name])
                db.submitToReconciliation(basename, phases[0].name, assignments)
            if score_common_regions:
                # Note that this HACKS THE DOCS. If you need the value of docs after
                # this, you should make sure to rewrite _scoreCommonRegions.
                self._scoreCommonRegions(db, scoreInputs)
            t.commit()
        except:
            t.rollback()
            raise
        
        if self.fromCmdline:
            print "Submitted basenames to reconciliation:", " ".join(basenames)

        # Now, what we want to do is eject the reconciled documents from reconciliation.
        # It can be a new transaction. Note that we also eject the documents which
        # don't have anything overlapping. That is, if we don't have any human gold
        # segments, because they're all either reconciled or "ignore during reconciliation",
        # boot them out.

        t = self.folder.workspace.beginTransaction(self)
        try:
            for basename in basenames:
                docObj = recFolder.openFile(basename)
                if len([a for a in docObj.getAnnotations(["SEGMENT"]) if a["status"] == "human gold"]) == 0:
                    # human gold is the only one that can mess us up.
                    self.folder.workspace._removeFromReconciliation([basename], recFolder,
                                                                    t, verbose = self.fromCmdline)
            t.commit()
        except:
            t.rollback()
            raise

    def _scoreCommonRegions(self, db, scoreInputs):
        import datetime, MAT.Score
        # So here's the idea. First, make sure the score directory exists. Next,
        # create a new output directory for this run.
        scoreDir = os.path.join(self.folder.workspace.dir, "scores")
        if not os.path.exists(scoreDir):
            os.makedirs(scoreDir)
        thisScoreDir = os.path.join(scoreDir, datetime.datetime.now().strftime("%Y%m%dH%H%M%S.%f"))
        os.makedirs(thisScoreDir)
        # Now, we figure out the common regions, which are the segments in the scoreInputs
        # which are gold or reconciled. Then, we copy the docs, remove all zones from the
        # docs, and "cheat" by re-adding those common regions. We also need to separate the
        # docs by who annotated them, which will break down into crossvalidation, assigned
        # users, or the unassigned category. Then, for each pair, we find the common
        # documents and run a score.
        basenames = [e[0] for e in scoreInputs]
        # This returns doc_name, basename, status, assigned_user, locked_by
        info = db.basenameInfo(basenames)
        docNameDict = {}
        for doc_name, basename, status, assigned_user, locked_by in info:
            docNameDict[doc_name] = (basename, assigned_user)
        statusToBasename = {}
        pairToDoc = {}        
        zoneTypes = self.folder.workspace.task.getAnnotationTypesByCategory("zone")
        scoreZoneType, rAttr, regionTypes = self.folder.workspace.task.getTrueZoneInfo()
        for basename, recDoc, dPairs in scoreInputs:
            zones = [(a.start, a.end) for a in recDoc.orderAnnotations(["SEGMENT"])
                     if (a["status"] == "human gold") or (a["status"] == "reconciled")]
            for docName, doc in dPairs:
                # If the path is crossvalidation input, then use that as the status.
                if docName.find(os.sep + "crossvalidation_dir" + os.sep + "cv_input" + os.sep) > -1:
                    status = "crossvalidation"
                else:
                    try:
                        status = docNameDict[docName][1]
                    except KeyError:
                        status = "unassigned"
                    if status is None:
                        status = "unassigned"
                try:
                    statusToBasename[status].add(basename)
                except KeyError:
                    statusToBasename[status] = set([basename])
                pairToDoc[(basename, status)] = doc
                # Now, mangle the doc so that its zones are correct.
                doc.removeAnnotations(zoneTypes)                
                for start, end in zones:
                    if rAttr is None:
                        doc.createAnnotation(start, end, scoreZoneType)
                    else:
                        doc.createAnnotation(start, end, scoreZoneType, {rAttr: regionTypes[0]})
        # Now, get all the keys.
        statuses = statusToBasename.keys()
        if len(statuses) < 2:
            if self.fromCmdline:
                print "Skipping scoring because there aren't any elements to compare"
                return
        # Generate all possible pairs.
        for i in range(len(statuses)):
            lPair = statuses[i]
            for rPair in statuses[i+1:]:
                intersectionBasenames = statusToBasename[lPair] & statusToBasename[rPair]
                if len(intersectionBasenames) > 0:
                    fullPath = os.path.join(thisScoreDir, "%s_as_hyp_vs_%s_as_ref" % (lPair, rPair))
                    os.makedirs(fullPath)
                    if self.fromCmdline:
                        print "Scoring in", fullPath
                    s = MAT.Score.Score(task = self.folder.workspace.task, computeConfidenceData = True)
                    s.addDocumentPairlist([((basename, pairToDoc[(basename, lPair)]),
                                            (basename, pairToDoc[(basename, rPair)])) for basename in intersectionBasenames])
                    s.writeCSV(fullPath)        

#
# User roles and reconciliation config
#

class AddUserRoleOperation(WorkspaceToplevelOperation):

    name = "add_roles"

    @classmethod
    def _createArgList(cls):
        recPhases = findReconciliationPhases()
        return [Option("--roles", type="string",
                       help = "Roles to add. The string 'all' adds all roles. Otherwise, a comma-separated list of roles. Available roles are: core_annotation %s" % " ".join(recPhases.keys()))]

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> add_roles [add_roles_options] <user>...

<user>: the name of a user to update the roles for."""

    def do(self, roles = None):
        # Workspace is already locked. I'm not sure
        # this is going to be supported except on the command line.
        t = self.workspace.beginTransaction(self)
        recPhases = findReconciliationPhases()
        try:
            if roles is None:
                raise WorkspaceError, "Must specify roles to add"
            elif roles == "all":
                roles = ["core_annotation"] + recPhases.keys()
            else:
                roles = roles.split(",")
                for role in roles:
                    if (role != "core_annotation") and \
                       (not recPhases.has_key(role)):
                        raise WorkspaceError, ("Unknown user role '%s', not adding roles." % role)
            self.workspace._addRoles(self.args, roles)
            t.commit()
        except:
            t.rollback()
            raise

class RemoveUserRoleOperation(WorkspaceToplevelOperation):

    name = "remove_roles"

    @classmethod
    def _createArgList(cls):
        recPhases = findReconciliationPhases()
        return [Option("--roles", type="string",
                       help = "Roles to remove. The string 'all' removes all roles. Otherwise, a comma-separated list of roles. Available roles are: core_annotation %s" % " ".join(recPhases.keys()))]

    @classmethod
    def getUsage(self, w):
        return """Usage: %prog [options] <dir> remove_roles [remove_roles_options] <user>...

<user>: the name of a user to update the roles for."""

    def do(self, roles = None):
        # Workspace is already locked. I'm not sure
        # this is going to be supported except on the command line.
        t = self.workspace.beginTransaction(self)
        recPhases = findReconciliationPhases()
        try:
            if roles is None:
                raise WorkspaceError, "Must specify roles to remove"
            elif roles == "all":
                roles = ["core_annotation"] + recPhases.keys()
            else:
                roles = roles.split(",")
                for role in roles:
                    if (role != "core_annotation") and \
                       (not recPhases.has_key(role)):
                        raise WorkspaceError, ("Unknown user role '%s', not removing roles." % role)
            self.workspace._removeRoles(self.args, roles)
            t.commit()
        except:
            t.rollback()
            raise

#
# And another one: configuring reconciliation
#

# You can only reconfigure reconciliation if the reconciliation folder
# is empty. Not sure what the options are yet.

class ConfigureReconciliationOperation(WorkspaceToplevelOperation):

    name = "configure_reconciliation"
    
    @classmethod
    def getUsage(self, w):
        phases = findReconciliationPhases()
        return """Usage: %prog [options] <dir> configure_reconciliation [reconciliation_options] <phase> ...

<phase>: the name of a reconciliation phase to enable. Available phases are: """ + " ".join([p.name for p in phases.values()])

    def do(self):
        # Disabled a bunch of tests, too. See WorkspaceReconciliationTestCase in
        # test/mat_workspace_unittest.py. This must be re-enabled when we get
        # this working.
        raise WorkspaceError, "workspace reconciliation has no UI support yet - postponed to next release"
        t = self.workspace.beginTransaction(self)
        try:
            self.workspace._configureReconciliation(self.args)
            t.commit()
        except:
            t.rollback()
            raise


#
# Logging operations
#

import MAT.WorkspaceLogger

class EnableLoggingOperation(WorkspaceToplevelOperation):

    name = "enable_logging"

    @classmethod
    def getUsage(cls, w):
        return """Usage: %prog [options] <dir> enable_logging"""

    def do(self):
        self.workspace._enableLogging()

class DisableLoggingOperation(WorkspaceToplevelOperation):

    argList = [OpArgument("remove_log", help = "if provided, the log will be removed when logging is disabled. Otherwise, the log is stored separately, so that when logging is enabled again, a new log is created.")]

    name = "disable_logging"

    @classmethod
    def getUsage(cls, w):
        return """Usage: %prog [options] <dir> disable_logging"""
    
    def do(self, remove_log = False):
        self.workspace._disableLogging(removeLog = remove_log)

class RerunLogOperation(WorkspaceToplevelOperation):
    
    argList = [OpArgument("stop_at", help = "the log timestamp to stop immediately before", hasArg = True),
               OpArgument("restart", help = "go back to the beginning"),
               OpArgument("verbose", help = "describe the state of the workspace at each point")]

    name = "rerun_log"

    @classmethod
    def getUsage(cls, w):
        return """Usage: %prog [options] <dir> [rerun_options] rerun_log"""

    def do(self, stop_at = None, restart = False, verbose = False):
        self.workspace._rerunLog(stopAt = stop_at, restart = restart, verbose = verbose)

# Here's a separate operation to upload the log.

class UploadUILogOperation(WorkspaceToplevelOperation):

    name = "upload_ui_log"

    availability = NOT_AVAILABLE

    argList = [OpArgument("log", help = "log fragment (from UI) to trigger fine-grained progress monitoring", hasArg = True),
               OpArgument("log_format", help = "the format of the log fragment", hasArg = True),
               OpArgument("timestamp", help = "millisecond timestamp of log upload from the server's point of view", hasArg = True)]

    def do(self, log = None, log_format = None, timestamp = None):

        t = self.workspace.beginTransaction(self)
        try:
            if log and self.workspace.logger:
                self.workspace.logger.logLog(log, log_format, timestamp)
            t.commit()
        except:
            t.rollback()
            raise

    def webResult(self):
        return {"success": True}

#
# Lock object
#


# Try to obtain the lock. The open operation is cross-platform
# (looking forward) and atomic. Thanks to
# http://www.evanfosmark.com/2009/01/cross-platform-file-locking-support-in-python/

# We don't need to keep the file open. For debugging, we want it closed, in fact.

import errno, time

class WorkspaceLock:

    def __init__(self, operation, dir, timeout = None):
        self.lockfile = os.path.join(dir, "opLockfile")
        
        start_time = time.time()
        
        # If timeout is None, don't wait at all.
        # The idea is to raise an error if the file exists (os.O_EXCL).

        try:
            res = self._lock(operation, dir, timeout)
        except Exception, e:
            # If anything, anything at all, goes wrong in here, bail.
            self.unlock()
            raise WorkspaceError, ("encountered error trying to lock workspace: %s" % e)
        if res is False:
            # Read the lockfile.
            fp = open(self.lockfile, "r")
            s = fp.read()
            fp.close()
            raise WorkspaceError, ("workspace is currently unavailable (processing other request: %s)" % s)
        
    def _lock(self, operation, dir, timeout):
        while True:
            try:                
                fd = os.open(self.lockfile, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                break
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
                if (timeout is None) or \
                   ((time.time() - start_time) >= timeout):
                    return False
                time.sleep(.05)
        # For some reason, fdopen doesn't work here.
        # fp = os.fdopen(fd, "rw")
        # fp.write("%s by %s @ %s" % (operation, os.getlogin(), time.ctime()))
        # fp.close()
        # os.getlogin() isn't portable. getpass.getuser() appears to be the only option.
        import getpass
        os.write(fd, "%s by %s @ %s" % (operation, getpass.getuser(), time.ctime()))
        os.close(fd)
        return True

    def unlock(self):
        # If this goes pear-shaped, we're in real trouble anyway.
        try:
            os.remove(self.lockfile)
        except:
            pass
            
                
#
# Workspace
#

# Each workspace will have a set of folders, and also
# a properties file, and a model directory, and a list
# of files which are the file names which have been
# imported.

# We have to be able to add folders before we init.
# Belay that. Pass the create flag to addFolder, from
# the __init__ method.

import MAT.PluginMgr

import MAT.WorkspaceDB

# _fromRerunner will be True if we're creating a workspace from
# the workspace rerunner. In this case, we DO NOT CHECK for initial users.
# The logger will either be initialized in workspaceCustomize, in which
# case the registerUsers action will be captured in the log, or it
# will be initialized after the initial users were captured, and thus they'll
# already be in the DB.

class Workspace:

    def __init__(self, dir, create = False, taskName = None, maxOldModels = 0,
                 pluginDir = None, initialUsers = None, _fromRerunner = False):
        
        self.dir = os.path.abspath(dir)
        self.task = None
        pluginDir = pluginDir or MAT.PluginMgr.LoadPlugins()
        self.maxOldModels = maxOldModels
        self.folderDir = os.path.join(self.dir, "folders")
        self.modelDir = os.path.join(self.dir, "models")

        # Many of these settings here look forward to future versions
        # of MAT 2.
        self._db = None
        self.currentTransaction = None
        self.loggingEnabled = False
        self.logger = None
        self._prioritizer = None
        self.prioritizationClass = None
        self.reconciliationPhases = []
        self.toplevelOperations = {}

        createWorkspace = False
        if not os.path.isdir(self.dir):
            if create:
                self.task = self._findTask(taskName, pluginDir)
                createWorkspace = True                
            else:
                raise WorkspaceError, ("no workspace at %s" % self.dir)
        elif create:
            raise WorkspaceError, "can't create a workspace in an existing directory"
        elif not os.access(self.dir, os.X_OK | os.R_OK):
            # If the user can't list or read the directory,
            # we've got trouble. Later, we'll test other things.
            raise WorkspaceError, ("insufficient permissions on workspace '%s'" % self.dir)
        elif not self._isWorkspace():
            raise WorkspaceError, ("directory %s is not a legal workspace" % self.dir)
        else:
            self._configureFromDir(pluginDir)

        # By this point, all the metadata is instantiated. Now we can
        # configure the IO.
        
        if not self.task:
            raise WorkspaceError, "no task for workspace"
        self.richFileType = 'mat-json'
        self.richFileIO = getDocumentIO(self.richFileType, task = self.task)

        self.folders = {
            "core":
            CoreWorkspaceFolder(self, "core", description = "for all files during normal annotation",
                                operations = [MarkGoldOperation,
                                              UnmarkGoldOperation,
                                              ReleaseLockOperation,
                                              SaveOperation,
                                              ModelBuildOperation,
                                              AutotagOperation,
                                              ForceUnlockOperation,
                                              SubmitToReconciliationOperation]),
            "export":
            WorkspaceFolder(self, "export", description = "for exported files",
                            importTarget = False,
                            operations = []),
            "reconciliation":
            ReconciliationWorkspaceFolder(self, "reconciliation", 
                                          description = "for reconciliation files",
                                          importTarget = False,
                                          operations = [RemoveFromReconciliationOperation,
                                                        ReconciliationSaveOperation,
                                                        ReconciliationReleaseLockOperation,
                                                        ForceUnlockOperation])
        
            }
            
        # Not adding the OpenFile operation, yet. Don't want it available
        # on the command line, but it's available to be added and specialized
        # by tasks.
        
        self.addToplevelOperations(dict([(c.name, c) for c in
                                         [ImportOperation, RemoveOperation, ListOperation,
                                          AssignOperation, RegisterUserOperation,
                                          DumpDatabaseOperation, ListUserOperation,
                                          OpenFileOperation, WorkspaceConfigurationOperation,
                                          ListBasenameSetsOperation, AddToBasenameSetOperation,
                                          RemoveFromBasenameSetOperation,
                                          RunExperimentOperation, EnableLoggingOperation,
                                          DisableLoggingOperation,
                                          RerunLogOperation,
                                          UploadUILogOperation,
                                          AddUserRoleOperation,
                                          RemoveUserRoleOperation,
                                          ConfigureReconciliationOperation]]))

        if createWorkspace:
            if (initialUsers is None) and (not _fromRerunner):
                raise WorkspaceError, "you must provide at least one user name to create a workspace (on the command line, use the --initial_users option)"
            self._createWorkspace()            
        
        self.task.workspaceCustomize(self, create = create)
        
        if createWorkspace and (not _fromRerunner):
            self.registerUsers(initialUsers)

    def getDB(self):
        if self._db is None:
            self._db = MAT.WorkspaceDB.WorkspaceDB(self)
            if self.prioritizationClass:
                self.prioritizationClass.enhanceDB(self._db)
        return self._db

    def closeDB(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    # These three return nothing in MAT 2. Someday, we may move over the prioritization
    # from TooCAAn, but not right now.
    
    def getPrioritizer(self):
        return None
    
    def getPrioritizationClassName(self):
        return None

    def getPrioritizationMode(self):
        return None

    def describeFolders(self, importableOnly = False):
        if importableOnly:
            importValues = [True]
        else:
            importValues = [True, False]
        return "\n".join(["%s: %s" % (key, val.description)
                          for key, val in self.folders.items()
                          if val.importTarget in importValues])

    def _findTask(self, taskName, plugins):
        
        # Find the task, first and foremost.

        if len(plugins.values()) == 0:
            raise WorkspaceError, "no tasks available"

        if taskName is None:
            if len(plugins.values()) == 1:
                return plugins.values()[0]
            else:
                raise WorkspaceError, "no task specified"
        
        t = plugins.getTask(taskName)
        if t is None:
            raise WorkspaceError, ("unknown task '%s'" % taskName)
        else:
            return t

    def _configureFromDir(self, pluginDir):
        db = self.getDB()
        self.task = self._findTask(db.getTaskName(), pluginDir)
        self.loggingEnabled = db.loggingEnabled()
        if self.loggingEnabled:
            self.logger = MAT.WorkspaceLogger.WorkspaceLogger(self)
        self.maxOldModels = db.getMaxOldModels()
        pClass = db.getPrioritizationClass()
        if pClass:
            # Gotta reopen the DB.
            self.closeDB()
            from MAT.PluginMgr import FindPluginClass
            self.prioritizationClass = FindPluginClass(pClass, self.task.name)

        phases = findReconciliationPhases()
        self.reconciliationPhases = [phases[e] for e in db.getReconciliationPhases()]
                
    def _createWorkspace(self):
        
        os.makedirs(self.dir)
        os.makedirs(self.folderDir)
        os.makedirs(self.modelDir)
        for folder in self.folders.values():
            folder.create()
        
        db = self.getDB()
        db.initializeWorkspaceState(self.task.name, [], self.loggingEnabled,
                                    self.prioritizationClass, self.maxOldModels)

    def _isWorkspace(self):
        # It's gotta have a folders subdir and a models subdir.
        return os.path.isdir(self.folderDir) and \
               os.path.isdir(self.modelDir)

    def _readFileNames(self):
        # This is a dictionary with one key per basename.
        return dict([(b, True) for b in self.getDB().allBasenames()])

    # The possible statuses:

    # "reconciled" - all HASs are reconciled
    # "gold" - all HASs are gold
    # "partially gold" - at least one HAS is gold
    # "partially corrected" - at least one AI is not owned by MACHINE
    # "uncorrected" - no AI is not owned by MACHINE
    # "unannotated" - there are no content annotations

    def _documentStatus(self, doc):
        segStatuses = [seg["status"] for seg in doc.getAnnotations(["SEGMENT"])]
        s = set(segStatuses)
        if len(s) == 1:
            if "reconciled" in s:
                return "reconciled"
            elif "human gold" in s:
                return "gold"
        elif (len(s) == 2) and ("reconciled" in s) and ("human gold" in s):
            return "gold"
        if ("reconciled" in s) or ("human gold" in s):
            # At least one of them is gold.
            return "partially gold"
        # It can only be unannotated if no annotator has touched it.
        contentAnnots = doc.getAnnotations(self.task.getAnnotationTypesByCategory('content'))
        owners = set([a.get("annotator") for a in doc.getAnnotations(["SEGMENT"])])
        # What if there are None elements in there? There shouldn't be.
        # But there might be. It certainly doesn't count as machine.
        if (len(owners) == 1) and "MACHINE" in owners:
            # It's the only thing.
            return "uncorrected"
        elif (len(owners) > 1) or (list(owners) != [None]) or contentAnnots:
            return "partially corrected"
        else:
            return "unannotated"        

    def _registerUsers(self, userList, roles):
        if not userList:
            raise WorkspaceError, "register_users requires at least one user"
        if not roles:
            raise WorkspaceError, "register_users requires at least one role"
        if type(userList) in (unicode, str):
            userList = [userList]
        for u in userList:
            if u.startswith("__"):
                raise WorkspaceError, ("can't register user %s: leading double underscore forbidden" % u)
            if "," in u:
                raise WorkspaceError, ("can't register user %s: comma forbidden" % u)
            # No whitespace, either.
            import re
            if re.search("\s", u):
                raise WorkspaceError, ("can't register user %s: whitespace forbidden" % u)
        db = self.getDB()
        existingUsers = db.listUsers()
        overlap = set(userList) & set(existingUsers)
        if overlap:
            raise WorkspaceError, ("can't register users %s: already registered" % ", ".join(overlap))
        db.registerUsers(userList, roles)

    def _listUsers(self, no_roles = False):
        db = self.getDB()
        if no_roles:
            return db.listUsers()
        else:
            return db.listUsersAndRoles()

    def _addRoles(self, userList, roles):
        if not userList:
            raise WorkspaceError, "add_roles requires at least one user"
        if not roles:
            raise WorkspaceError, "add_roles requires at least one role"
        if type(userList) in (unicode, str):
            userList = [userList]
        db = self.getDB()
        existingUsers = db.listUsers()
        if set(userList) - set(existingUsers):
            raise WorkspaceError, "can't update user roles: some users not registered"
        db.addUserRoles(userList, roles)
        
    def _removeRoles(self, userList, roles):
        if not userList:
            raise WorkspaceError, "remove_roles requires at least one user"
        if not roles:
            raise WorkspaceError, "remove_roles requires at least one role"
        if type(userList) in (unicode, str):
            userList = [userList]
        db = self.getDB()
        existingUsers = db.listUsers()
        if set(userList) - set(existingUsers):
            raise WorkspaceError, "can't update user roles: some users not registered"
        # Can't remove some roles when they're being used.
        docAssigned, docLocked, recLocked, recAssignedPairs = db.usersInUse()
        why = []
        for user in userList:            
            for role in roles:
                if role == "core_annotation":
                    if user in docAssigned:
                        why.append("%s assigned to core documents" % user)
                    elif user in docLocked:
                        why.append("%s editing core document" % user)
                elif user in recLocked:
                    why.append("%s editing a reconciliation document" % user)
                elif (user, role) in recAssignedPairs:
                    why.append("%s has an assignment in reconciliation phase %s" % (user, role))
        if why:
            raise WorkspaceError, ("can't remove roles: %s" % (", ".join(why)))
        db.removeUserRoles(userList, roles)

    # To configure reconciliation, first we have to ensure that
    # there are no documents in the reconciliation folder.

    def _configureReconciliation(self, phaseList):
        if self.folders["reconciliation"].getBasenames():
            raise WorkspaceError, "can't configure reconciliation; reconciliation folder is not empty"
        pDict = findReconciliationPhases()
        for p in phaseList:
            if not pDict.has_key(p):
                raise WorkspaceError, ("unknown reconciliation phase '%s'" % p)
        # Make sure they're in a legal order. Cross-validation is first, human decision is last.
        # I originally reordered th phaselist as it came in, but it occurs to me that
        # there may ultimately be more than one phase that must be first or last.
        # So I should take the order as given, and check.
        phaseList = [pDict[p] for p in phaseList]
        for p in phaseList:
            p.checkOrder(phaseList)
        self.reconciliationPhases = phaseList
        self.getDB().setReconciliationPhases([p.name for p in phaseList])

    def configureReconciliation(self, *phases):
        self.runOperation("configure_reconciliation", phases)    

    # We need to take the document which has been removed from reconciliation
    # and reintegrate the votes into the core documents.

    # We're always going to be in a transaction. If the
    # transaction fails, we want to ensure that the reconciliation
    # document is restored (and it may already be in the list of documents
    # which we need to preserve), and if we reintegrate, we have
    # to ensure the core docs are preserved too.
    
    def _removeFromReconciliation(self, basenames, recFolder, transaction, verbose = False, reintegrate = True):
        db = self.getDB()
        reintegrationDocs = {}
        docsForBasename = None
        for basename in basenames:
            if not db.beingReconciled(basename):
                print "Warning: the DB doesn't know that basename '%s' is being reconciled." % basename
            elif db.reconciliationBasenameLocked(basename):
                raise WorkspaceFileLockedError, ("no basenames removed from reconciliation: basename '%s' locked for reconciliation review" % basename)
            else:
                transaction.addFilesToPreserve([os.path.join(recFolder.dir, basename)], check = True)
        for basename in basenames:
            db.removeFromReconciliation(basename)
        db.forceUnlockCoreBasenames("RECONCILIATION", basenames)
        if reintegrate:
            # Load the documents before you remove them from the reconciliation
            # folder if you need to reintegrate.
            docsForBasenames = db.documentsForBasenames(basenames = basenames)
            for basename in basenames:
                recDoc = recFolder.openFile(basename)
                if recDoc is not None:
                    reintegrationDocs[basename] = recDoc
        recFolder.clear(basenames = basenames)
        if verbose:
            print "Removed basenames from reconciliation:", " ".join(basenames)
        if reintegrate:
            coreFolder = self.getFolder("core")
            # Step 1: find the regions in the reconciliation document which
            # have been completed.
            for basename in basenames:
                sourceDocNames = docsForBasenames[basename]
                transaction.addFilesToPreserve([os.path.join(coreFolder.dir, n) for n in sourceDocNames])
                sourceDocs = [coreFolder._openFileBasename(n) for n in sourceDocNames]
                try:
                    recDoc = reintegrationDocs[basename]
                except KeyError:
                    # There's no entry, because the document wasn't found.
                    continue
                recDoc.updateSourceDocuments(self.task, sourceDocs)
                for n, doc in zip(sourceDocNames, sourceDocs):
                    coreFolder.saveFile(doc, n)

    # fileBasenames is the actual file name, not the workspace basename.
    
    def _updateDocumentStatuses(self, fileBasenames, folder, transaction, segStatuses, newSegStatus,
                                responsibleUser):
        # This is used to update things to human gold and reconciled - so
        # when the doc is updated, everything in the doc can be removed from
        # the segmenter.
        # And, fixed it so that it can mark documents non-gold too - in this
        # case, they're already gold, so removing them from the segmenter is
        # superfluous. Also, if they're already gold, we don't want to change
        # the responsible user.
        if responsibleUser is None and ("non-gold" in segStatuses):
            raise WorkspaceError, "updating non-gold statuses requires a user"
        segmenter = None
        db = self.getDB()
        for b in fileBasenames:
            doc = folder._openFileBasename(b)
            modified = False
            # Gotta mark all the segments gold, and attribute all
            # the annotations which are attributed to MACHINE to the
            # relevant person. 
            segAnnots =  doc.getAnnotations(["SEGMENT"], ordered = True)
            for annot in segAnnots:
                if annot["status"] in segStatuses:
                    if newSegStatus is not None:
                        annot["status"] = newSegStatus
                        modified = True
                    # FOR THE MOMENT, IN ORDER TO TICKLE THE TRAINER, WE NEED
                    # TO MARK THE SEGMENT.
                    if responsibleUser is not None:
                        annot["annotator"] = responsibleUser
                    modified = True
            if modified:
                transaction.addFilesToPreserve([os.path.join(folder.dir, b)], check = True)
                if segmenter is None:
                    segmenter = self.getPrioritizer()
                folder.saveFile(doc, b)
                if segmenter is not None:
                    segmenter.removeDoc(b)
                # None means compute it. You only need to update the status
                # if something changed.
                db.updateDocumentStatus(b, self._documentStatus(doc))

    # _openFile, by itself, needs no transaction. It only does DB updates
    # in any case, so the transaction stuff must be left to the callers.
    # We have to enforce that we require a user if it's not read only.

    def _openFile(self, folderName, basename, user, readOnly):
        folder = self.folders[folderName]
        fileBasename = folder.fileBasenameForUser(basename, user)
        # This can happen if we're called from the toplevel. It should
        # always be an error.
        if fileBasename is None:
            raise WorkspaceError, ("user %s can't open basename %s because no appropriate document was found" % (user, basename))
        return self._openFileBasename(folder, fileBasename, user, readOnly)

    # If the user is the same as the locking user, then free that lock
    # and relock. Don't reuse the lock - we want to make sure that previous
    # opens are cancelled.
    
    def _openFileBasename(self, folder, fileBasename, user, readOnly, doc = None):
        db = self.getDB()
        if not readOnly:
            lockingUser = folder.fileBasenameLocked(fileBasename)
            if lockingUser is not None:
                # If it's locked, mark it read only unless it has to be writeable,
                # in which case raise an error.
                if lockingUser != user:
                    # If the locking user is the same as the requesting user,
                    # ignore the lock - it'll get overwritten below.
                    raise WorkspaceFileLockedError, "can't open a locked document for writing"
            # Make sure the specified user exists.
            if user is None:
                raise WorkspaceUserLockError, "can't open document with unknown user"
            if not db.userIsRegistered(user):
                raise WorkspaceUserLockError, ("can't open a document using unregistered user '%s'" % user)
            # If the user is not assigned to this basename, then check                    
            # to make sure the user has the core_annotation role. If it's
            # already assigned, we assume the check was done there (later we'll
            # unwind this, when we do on-demand assignment). Nah, just
            # check it always.
            if not db.userHasRole(user, "core_annotation"):
                raise WorkspaceError, ("user %s can't open %s for writing because the user doesn't have the core_annotation role" % (user, fileBasename))                       

        # This can't fail.
        doc = doc or folder._openFileBasename(fileBasename)
        lockId = None
        if not readOnly:            
            lockId = self._generateLockID()
            folder.prepareForEditing(doc, fileBasename, user, lockId)
        return doc, fileBasename, lockId

    def _generateLockID(self):
        import random, string
        return "".join([random.choice(string.ascii_letters + string.digits) for i in range(32)])

    def _addToBasenameSet(self, setName, *basenames):
        db = self.getDB()
        relevantBasenames = set(db.allBasenames(basenames = basenames))
        if set(basenames) != relevantBasenames:            
            raise WorkspaceError, ("unknown basename(s) %s" % ",".join(set(basenames) - relevantBasenames))        
        for b in basenames:
            db.addBasenameToBasenameSet(b, setName)

    def _removeFromBasenameSet(self, setName, *basenames):
        db = self.getDB()
        for b in basenames:
            db.removeBasenameFromBasenameSet(b, setName)

    # Three logging methods.
    def _enableLogging(self):
        if not self.loggingEnabled:
            self.loggingEnabled = True
            self.logger = MAT.WorkspaceLogger.WorkspaceLogger(self)
            self.getDB().enableLogging()

    def _disableLogging(self, removeLog = False):
        if self.loggingEnabled:
            self.logger = None
            # Remove or move aside the log. If we enable it again, it'll start
            # with a fresh seed. Otherwise, we might lose stuff
            # in the middle while it's temporarily disabled.
            loggerP = os.path.join(self.dir, MAT.WorkspaceLogger.WorkspaceLogger.loggerDir)
            if os.path.exists(loggerP):
                if removeLog:
                    shutil.rmtree(loggerP)
                else:
                    # Move it aside.
                    i = 0
                    while True:
                        p = loggerP + "_" + str(i)
                        if not os.path.exists(p):
                            shutil.move(loggerP, p)
                            break
                        i = i + 1
            self.loggingEnabled = False      
            self.getDB().disableLogging()

    def _rerunLog(self, stopAt = None, restart = False, verbose = False):
        r = MAT.WorkspaceLogger.WorkspaceRerunner(self, restart = restart)
        r.rollForward(stopAt = stopAt, verbose = verbose)
    
    # We need to keep track of the transactions because we need
    # to access the workspace logging, possibly.
    
    def beginTransaction(self, op, **kw):
        self.currentTransaction = WorkspaceTransaction(self, op, **kw)
        return self.currentTransaction

    #
    # Public methods
    #

    # Use this method to add a folder to the workspace.
    # This is meant to be called after super __init__
    # is called.

    def addFolder(self, name, dirName, folderClass = WorkspaceFolder, create = False, **kw):
        folder = folderClass(self, dirName, prettyName = name, **kw)
        self.folders[name] = folder
        if create:
            folder.create()
        elif not os.path.isdir(folder.dir):
            raise WorkspaceError, ("no folder named %s in workspace at %s" %
                                   (name, self.dir))

    # This method imports files.

    # Toplevel operation. MUST BE LOCKED. Originally, the core of the import
    # operation was also implemented here, but it now involves a MAT engine
    # operation, so we've moved it all to the toplevel operation itself.

    def importFiles(self, files, folderName, **kw):
        return self.runOperation("import", (folderName,) + tuple(files),
                                 fromCmdline = False, resultFormat = FN_RESULT,
                                 **kw)

    # This function returns all the legal basenames.
    # Overriding because the core behavior is now really
    # inefficient.

    def getBasenames(self, basenameList = None):
        return self.getDB().allBasenames(basenames = basenameList)

    # Toplevel operation. MUST BE LOCKED.

    def getFolderBasenames(self, *folderNames):

        return self.runOperation("list", folderNames, resultFormat = FN_RESULT)

    # Corresponding internal function.

    def _getFolderBasenames(self, *folderNames):
        return dict([(folderName, self.folders[folderName].getBasenames())
                     for folderName in folderNames if self.folders.has_key(folderName)])

    # Toplevel operation. MUST BE LOCKED. This can't use
    # runOperation because it's not registered as an operation.

    def openWorkspaceFile(self, folder, basename, **kw):
        
        return self.runOperation("open_file", (folder, basename),
                                 resultFormat = FN_RESULT,
                                 **kw)

    # Toplevel operation. MUST BE LOCKED. Provided for backward compatibility.

    def removeBasenames(self, basenameList = None):

        return self.runOperation("remove", basenameList or [])

    def removeAllBasenames(self):

        return self.runOperation("remove", self.getBasenames())

    # COMPLETELY rewritten from the previous version, because I need
    # the transaction in here. And, I need to worry about getting files
    # from folders. And we no longer need to check the file list via
    # the previous method, AND we ought to migrate the call to discardBasenames
    # into here.

    def _removeBasenames(self, transaction, basenameList = None):

        # For ease of interaction, let's check all the basenames
        # first, so we can raise an error.

        logger = self.logger
        for f in self.folders.values():
            # This was f.clear(), but I have to copy it
            # to  get the transactions to work.
            for p in f.getFiles(basenameList):
                if os.path.isfile(p):
                    transaction.addFilesToPreserve([p], check = True)
                    os.remove(p)
                    if logger:
                        self.logger.logRemoveFile(f, os.path.basename(p))
        
        # Let's find the actual basenames we're removing.
        db = self.getDB()            
        basenamesRemoved = db.allBasenames()
        if basenameList is not None:
            basenamesRemoved = list(set(basenamesRemoved) & set(basenameList))

        db.discardBasenames(basenamesRemoved)

        return basenamesRemoved

    def getFolder(self, folderName):
        try:
            return self.folders[folderName]
        except KeyError:
            raise WorkspaceError, ("unknown folder %s" % folderName)

    def getFolderOperation(self, folderName, operationName, basenames = None, transaction = None):
        folder = self.getFolder(folderName)
        return folder.getOperation(operationName, basenames = basenames, transaction = transaction)

    # We're going to change the search method. Operations will no longer
    # require a folder, except when a dispatch is required. Furthermore,
    # you can define operations with the same name on different folders.
    
    def getOperation(self, operationName, args, transaction = None):
        try:
            cls = self.toplevelOperations[operationName]
            # Instantiate the class.
            return cls(self, args, transaction = transaction)
        except KeyError:
            if not args:
                raise WorkspaceError, "no folder specified for folder operation"
            folderName = args[0]
            basenames = args[1:] or None
            return self.getFolderOperation(folderName, operationName, basenames = basenames, transaction = transaction)

    # We're going to use these classes to create separate command line option groups.
    # You shouldn't be able to add a folder operation which already exists
    # as a toplevel operation, or vice versa. I've now guaranteed that.
    
    def getOperationClasses(self, operationName):
        try:
            return [("<toplevel>", self.toplevelOperations[operationName])]
        except KeyError:
            return [(fName, f.operations[operationName]) for fName, f in self.folders.items()
                    if f.operations.has_key(operationName)]

    def getCmdlineOperationNames(self, debug = False):
        s = set()
        for f in self.folders.values():
            s.update([o.name for o in f.getCmdlineOperations(debug = debug)])
        if debug:
            avail = CMDLINE_DEBUG_AVAILABLE_MASK
        else:
            avail = CMDLINE_AVAILABLE_MASK
        return [o.name for o in self.toplevelOperations.values() if (o.availability & avail)] + list(s)

    # Toplevel operation. MUST BE LOCKED.

    def runOperation(self, operationName, otherArgs,
                     aggregator = None, resultFormat = NULL_RESULT,
                     fromCmdline = False, **params):
        
        # This will raise an error if you can't get the lock.
        lock = WorkspaceLock("%s on %s" % (operationName, ", ".join(otherArgs)) , self.dir)

        try:
            o = self.getOperation(operationName, otherArgs)
            return self._runOperation(o, aggregator = aggregator, resultFormat = resultFormat,
                                      fromCmdline = fromCmdline,
                                      **params)
        finally:
            lock.unlock()

    # Toplevel convenience utility, for backward compatibility.

    def runFolderOperation(self, folderName, operationName,
                           aggregator = None, basenames = None, resultFormat = NULL_RESULT,
                           fromCmdline = False,
                           **params):

        lock = WorkspaceLock("%s on %s" % (operationName, folderName) , self.dir)

        try:
            o = self.getFolderOperation(folderName, operationName, basenames = basenames)
            return self._runOperation(o, aggregator = aggregator, resultFormat = resultFormat,
                                      fromCmdline = fromCmdline,
                                      **params)
        finally:
            lock.unlock()

    # Internal utilities. THESE MUST ALWAYS BE CALLED FROM A LOCKED FUNCTION.

    # OOOH, this is hideous. I have to
    # ensure that there's always a user. So for every operation, I have
    # to check this. What a waste. Of course, unless the operation is
    # registerUsers. Perhaps this can go away when create takes a user. And it has.

    def _runOperation(self, o, aggregator = None, resultFormat = NULL_RESULT, fromCmdline = False,
                      **params):
        try:
            o.enhanceAndValidate(aggregator, **params)
            o.fromCmdline = fromCmdline
            o.doOperation()
            if resultFormat == WEB_RESULT:
                return o.webResult()
            elif resultFormat == FN_RESULT:
                return o.fnResult()
            else:
                return None
        finally:
            self.closeDB()
            
    # This function is used to ensure that the current user can access the
    # workspace. It's used primarily in the CGI call. The other files
    # need to have been checked earlier.

    # On Windows, it doesn't appear that you can rely on os.access -
    # it will return True for writing even when the directory flags
    # have been disabled. Not sure what to do about this.
    
    def dirsAccessible(self, forWriting = True):
        if forWriting:
            flags = os.R_OK | os.W_OK
        else:
            flags = os.R_OK
        r = os.access(self.dir, os.X_OK | flags) and \
            os.access(self.folderDir, os.X_OK | flags) and \
            os.access(self.modelDir, os.X_OK | flags) and \
            len([folder for folder in self.folders.values()
                 if not os.access(folder.dir, os.X_OK | flags)]) == 0
        if r:
            if forWriting:
                flags = os.R_OK | os.W_OK
            else:
                flags = os.R_OK
            return os.access(self.getDB().wsDBFile, flags)
        else:
            return False

    def getOperationSettings(self, name):
        try:
            return self.task.getWorkspaceOperations()[name]
        except KeyError:
            return None

    def registerUsers(self, userList, roles = None):
        if type(userList) in (unicode, str):
            userList = [userList]
        self.runOperation("register_users", userList, roles = roles)

    def listUsers(self):
        return self.runOperation("list_users", (), fromCmdline = False, resultFormat = FN_RESULT)

    def addToplevelOperations(self, opDict):
        for opName, op in opDict.items():
            # If it's already a folder operation, barf.
            for fName, f in self.folders.items():
                if f.operations.has_key(opName):
                    raise WorkspaceError, ("Can't add toplevel operation '%s', because it's already defined in folder '%s'" % (opName, fName))
            self.toplevelOperations[opName] = op
