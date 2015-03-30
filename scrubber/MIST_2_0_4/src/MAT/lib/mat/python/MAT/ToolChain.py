# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import os, sys, traceback, codecs
from MAT import Error, PluginMgr, DocumentIO, Document

class ConfigurationError(Exception):
    pass

class ShortUsageConfigurationError(ConfigurationError):
    pass

class NoUsageConfigurationError(ConfigurationError):
    pass

# No error checking yet.

# Steps can be things like "zone", "tag".

# Input for zone is the signal; output for render is the signal.
# All other inputs and outputs are the annotation set.

# Moving all the configuration digestion into here: finding
# named tasks, loading files, etc.

# New configuration for MATEngine. task is now taskObj, and it's now
# a keyword. The names of the keys have to match the command line.

# I want to be able to default to a single known task, and a single
# known workflow in that task. I think I'll handle that in the engine
# itself. Well, we can't default to a single workflow, because in
# order to default, you need to have computed the operational task,
# which we don't do until runtime. Actually, if the known task
# only has one workflow of its own, it should default to it, but
# there's no guarantee that the child will implement it. So we can default.

from MAT.Operation import XMLOpArgumentAggregator, OpArgument
import MAT.ExecutionContext

class MATEngine:

    def __init__(self, taskObj = None, workflow = None, task = None, pluginDir = None):
        self.taskObj = taskObj
        if self.taskObj is None:
            # We need to find one.
            pluginDir = pluginDir or PluginMgr.LoadPlugins()
            if task is None:
                allTasks = pluginDir.getAllTasks()
                if len(allTasks) == 1:
                    self.taskObj = allTasks[0]
                else:
                    # Nada.
                    raise ShortUsageConfigurationError, (self, "task not specified")
            else:
                self.taskObj = pluginDir.getTask(task)
                if self.taskObj is None:
                    raise ShortUsageConfigurationError, (self, "unknown task '%s'" % task)
        # At this point, there's a task obj. Later, we'll get the operational task.
        # When we run.
        self.operationalTask = None
        self.workFlow = workflow
        if self.workFlow is None:
            # We'll default to a single workflow, but even that workflow
            # won't be guaranteed to work.
            wfList = self.taskObj.getWorkflows().keys()
            if len(wfList) == 1:
                self.workFlow = wfList[0]
            else:
                raise ConfigurationError, (self, "workflow must be specified")

    def _ensureOperationalTask(self, steps, **params):
        if self.operationalTask is None:
            try:                
                self.operationalTask = self.taskObj.getTaskImplementation(self.workFlow,
                                                                          steps or [], **params)
                if self.operationalTask is None:
                    raise NoUsageConfigurationError, (self, "couldn't find task implementation for the given parameters")
            except KeyError:
                raise NoUsageConfigurationError, (self, "couldn't find task implementation for the given parameters")
            except PluginMgr.PluginError, e:
                raise ConfigurationError, (self, "Plugin error: %s" % e)

    # Here's a version of the Run() method below which can be called with
    # an aggregator. The aggregator is going to have all sorts of
    # arguments. We need: input_file, input_dir, input_file_re,
    # input_encoding, input_file_type, output_file, output_dir,
    # output_fsuff, output_file_type, output_encoding, workflow, steps,
    # print_steps, undo_through. I suppose I should be adding these
    # by making the MATEngine an option bearer, but that's just not
    # in the cards at the moment.

    def _input_file_type_enhancer(option, optstring, value, parser):
        inCls = None
        try:
            inCls = DocumentIO.getInputDocumentIOClass(value)
        except KeyError:
            if getattr(parser, "failOnFileTypes", False):
                raise ConfigurationError, (self, "input_file_type must be one of " + ", ".join(["'"+x+"'" for x in DocumentIO.allInputDocumentIO()]))
        if inCls is not None:
            inCls.addOptions(parser.aggregator, values = parser.values)

    def _output_file_type_enhancer(option, optstring, value, parser):
        outCls = None
        try:
            outCls = DocumentIO.getOutputDocumentIOClass(value)
        except KeyError:
            if getattr(parser, "failOnFileTypes", False):
                raise ConfigurationError, (self, "output_file_type must be one of " + ", ".join(["'"+x+"'" for x in DocumentIO.allOutputDocumentIO()]))
        if outCls is not None:
            outCls.addOptions(parser.aggregator, values = parser.values)

    INTERNAL_ARGS = [OpArgument("input_file", hasArg = True),
                     OpArgument("input_dir", hasArg = True),
                     OpArgument("input_file_re", hasArg = True),
                     OpArgument("input_encoding", hasArg = True),
                     OpArgument("input_file_type", hasArg = True,
                                side_effect_callback = _input_file_type_enhancer),
                     OpArgument("output_file", hasArg = True),
                     OpArgument("output_dir", hasArg = True),
                     OpArgument("output_fsuff", hasArg = True),
                     OpArgument("output_file_type", hasArg = True,
                                side_effect_callback = _output_file_type_enhancer),
                     OpArgument("output_encoding", hasArg = True),
                     OpArgument("workflow", hasArg = True),
                     OpArgument("steps", hasArg = True),
                     OpArgument("print_steps", hasArg = True),
                     OpArgument("undo_through", hasArg = True)]
    
    def aggregatorExtract(self, aggregator, failOnFileTypes = False, **params):
        aggregator.addOptions(self.INTERNAL_ARGS)
        # First, start with the task.
        self.taskObj.addOptions(aggregator)
        # Now, we extract.
        return aggregator.extract(defaults = params)

    # The problem here is that there are OTHER arguments to aggregatorRun
    # which aren't part of the internal args, and never come out of
    # a command line parse. This wasn't a problem before, but
    # now it is.
    
    def aggregatorRun(self, aggregator, inputFileList = None, **params):
        return self.Run(inputFileList = inputFileList,
                        **self.aggregatorExtract(aggregator, failOnFileTypes = True, **params))

    # The Run method is the most convenient public face of the
    # engine. It allows you to configure all sorts of things about
    # where the files are read from and where they go.

    # The keyword arguments here must match the option argument names
    # on the command line. Some of them are intended only to be used
    # internally, such inputFileList. 

    def Run(self, input_file = None, input_dir = None, input_file_re = None,
            input_encoding = None, input_file_type = None, steps = None, undo_through = None,
            output_file = None, output_file_type = None, output_dir = None,
            output_fsuff = None, output_encoding = None,
            # These three parameters might be passed in when this is called
            # programmatically, but not from the command line.
            inputFileList = None, inputFileType = None, outputFileType = None,
            **params):
        
        # First, preprocess some of the arguments.
        if steps is not None:
            if type(steps) is str:
                steps = steps.split(",")
                if steps == ['']:
                    steps = []

        # Make sure we have a task.
        self._ensureOperationalTask(steps, **params)

        dm = DocumentIO.DocumentIOManager(task = self.operationalTask)
        try:
            dm.configure(input_file = input_file, input_dir = input_dir,
                         input_file_re = input_file_re,
                         input_encoding = input_encoding, input_file_type = input_file_type, 
                         output_file = output_file, output_file_type = output_file_type,
                         output_dir = output_dir,
                         output_fsuff = output_fsuff, output_encoding = output_encoding,
                         inputFileList = inputFileList,
                         inputFileType = inputFileType,
                         outputFileType = outputFileType,
                         **params)
        except DocumentIO.ManagerError, e:
            raise ConfigurationError, (self, str(e))

        from MAT.ExecutionContext import _DEBUG

        try:
            # Now, create the idata pairs. We're not going to keep going,
            # so we ignore the skipPairs.
            inputPairs, ignore = dm.loadPairs()
        except Exception, e:
            if _DEBUG:
                raise
            else:
                raise NoUsageConfigurationError, (self, str(e))

        # Central call. This is where the work gets done.
        
        iDataPairs = self.RunDataPairs(inputPairs, steps, undoThrough = undo_through, **params)
        resultTable = {}
        for fname, iData in iDataPairs:
            resultTable[fname] = iData

        # And then the end.

        if dm.isWriteable():
            # The complexity here is that the output may not be in the
            # appropriate format to save. That is, if it's raw, then
            # we have to turn the signal into a document. If the
            # output file type is mat-json, utf-8 is automatically enforced.
            for fname, idata in inputPairs:
                Output = resultTable[fname]
                if type(Output) is type(""):
                    Output = Document.AnnotatedDoc(signal = Output.decode('ascii'))
                elif type(Output) is type(u''):
                    Output = Document.AnnotatedDoc(signal = Output)
                elif not isinstance(Output, Document.AnnotatedDoc):
                    raise NoUsageConfigurationError, (self, "Output is neither text nor a document")
                try:
                    dm.writeDocument(fname, Output)
                except Exception, e:
                    if _DEBUG:                        
                        raise
                    else:
                        raise NoUsageConfigurationError, (self, "Error opening file %s for writing." % fname)

        return iDataPairs

    # OK, time to introduce batch processing. Let's make iData 
    # a little more complicated than before; it should be a sequence
    # of (<fname>, <docobj>) pairs. The idea is that each step
    # can have a tagStep or tagBatchStep method. If it has the
    # latter, I pass in the iDataPairs; otherwise, I loop through
    # the pairs myself.

    # More on the relation between the steps and the steps already
    # in the document: the steps don't all need to be in the workflow,
    # since the things that can be done in a given workflow are a
    # subset of what can be done to a document. The only restriction
    # is that if there's a step to be done which hasn't been
    # done yet, but there are later steps that HAVE been done,
    # you should barf. Well, I can't know this. It may be that
    # there are steps done which logically precede the steps
    # that the engine should do which have been skipped, and
    # we really SHOULD be at the end, but we don't know it.
    # I think we should treat the document phases done as
    # an unordered set, and rely on the system to ensure the
    # operational order.

    def RunDataPairs(self, iDataPairs, steps = None, 
                     undoThrough = None, **params):

        self._ensureOperationalTask(steps, **params)

        if not self.operationalTask.getWorkflows().has_key(self.workFlow):
            raise Error.MATError(
                "[init]", "workflow %s not found (choices are %s)" % (self.workFlow, ", ".join(self.operationalTask.getWorkflows().keys())))

        workflow = self.operationalTask.getWorkflows()[self.workFlow]

        if undoThrough is not None:
            try:
                successors = self.operationalTask.getStepSuccessors()[undoThrough]
            except KeyError:
                raise Error.MATError(
                    "[init]", "no step %s to undo through" % undoThrough)
            successors = successors[:]
            successors.reverse()
            successors.append(undoThrough)
            # For step, for each document, if the document has done the
            # step, undo it. We reverse the successors, so we undo them in order.
            # If the current workflow doesn't have the step, we have to
            # use the default step from the step implementation.
            stepDict = {}
            for stepObj in workflow.stepList:
                stepDict[stepObj.stepName] = stepObj
            for successor in successors:
                try:
                    successorStep = stepDict[successor]
                except KeyError:
                    # This workflow doesn't have this step. Get the default step.
                    successorStep = self.operationalTask.getDefaultStep(successor)
                try:
                    for fname, iData in iDataPairs:
                        if successor in iData.getStepsDone():
                            successorStep.undo(iData)
                            iData.stepUndone(successor)
                    self.ReportBatchUndoStepResult(successorStep, iDataPairs)
                except Exception, e:
                    if MAT.ExecutionContext._DEBUG:
                        raise
                    else:
                        raise Error.MATError(successor, str(e), show_tb = True)

        if not steps:
            return iDataPairs
        else:
            # Copy it, because we're going to surgically alter it.
            steps = steps[:]
        
        for stepObj in workflow.stepList:
            
            stepName = stepObj.stepName

            if steps and (steps[0] == stepName):
            
                localParams = params
                if stepObj.runSettings:
                    # So we have to be very, very careful not to have
                    # extra values in either the stepObj params or in the
                    # cmdline params. At one point, the cmdline params
                    # were reporting defaults too aggressively,  and it wasn't
                    # possible to distinguish between an explicitly specified
                    # value and a default value. Now,  it should be cleanly
                    # managed. I've also fixed the same thing for
                    # the step values.
                    localParams = stepObj.enhanceAndExtract(XMLOpArgumentAggregator(stepObj.runSettings))
                    # NOW we can override with the command line.
                    for key, val in params.items():
                        if val is not None:
                            localParams[key] = val
                
                # Filter the ones which need to be done. 
                pairsToDo = [(fname, iData) for fname, iData in iDataPairs
                             if stepObj.stepCanBeDone(iData)]
                if pairsToDo: 
                    fOrder = [fname for fname, iData in iDataPairs]
                    d = dict(iDataPairs)

                    try:
                        pairsDone = stepObj.doBatch(pairsToDo, **localParams)
                    except Exception, e:
                        if MAT.ExecutionContext._DEBUG:
                            raise
                        else:
                            raise Error.MATError(stepName, str(e), show_tb = True)

                    # Update the dictionary and reconstitute iDataPairs.
                    # Only record the step done if the output object is the same as
                    # the input object.
                    for fname, iData in pairsDone:
                        oldData = d[fname]
                        if (iData is oldData) and \
                           isinstance(iData, Document.AnnotatedDoc):
                            iData.recordStep(stepName)
                        d[fname] = iData
                    self.ReportBatchStepResult(stepObj, pairsDone)
                    iDataPairs = [(fname, d[fname]) for fname in fOrder]
                
                steps[0:1] = []

        if steps:
            raise Error.MATError("[engine]", "Unknown step " + steps[0])

        return iDataPairs

    def ReportBatchStepResult(self, stepObj, iDataPairs):
        # This can be overridden, if desired.
        for fname, iData in iDataPairs:
            self.ReportStepResult(stepObj, fname, iData)

    def ReportBatchUndoStepResult(self, stepObj, iDataPairs):
        # This can be overridden, if desired.
        for fname, iData in iDataPairs:
            self.ReportUndoStepResult(stepObj, fname, iData)

    def ReportStepResult(self, stepObj, fname, iData):
        pass

    def ReportUndoStepResult(self, stepObj, fname, iData):
        pass

