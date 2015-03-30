# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Carafe is a central part of our tool suite. I'm going
# to make available a class to manage the Carafe servers, so
# the various domains don't need to worry about it.

# This file used to contain only the guts of the Carafe tagger server, but
# I've expanded it to contain all the plugin steps as well. This will
# necessitate updating virtually all the task.xml files, but I
# probably should have done this a while ago.

import os, sys, shutil

import MAT.Config
from MAT.Command import _SUB_RUNNING, _SUB_PRESTART, _SUB_SUCCESS, \
     FileSystemCmdlineLocalProcess, FileSystemCmdlineAsynchronousProcess, \
     FileSystemLocalProxy, _jarInvocation, SimpleLocalProcess, LocalProcess
from MAT.Error import TaggerConfigurationError
from MAT.DocumentIO import getDocumentIO
from MAT.Tagger import Tagger
from MAT.PluginMgr import CmdlineTokenizationStep, CmdlineTagStep, PluginError

# SAM 12/27/10: Temporary shim to keep Ben from having to worry
# about MAT 2.0, and to keep me moving. Actually, we've decided to keep this.

_jsonIO = getDocumentIO('mat-json-v1')

#
# Tokenization
#

def _jCarafeJarInvocation(**kw):
    return _jarInvocation(MAT.Config.MATConfig["JAVA_BIN"], MAT.Config.MATConfig["JCARAFE_JAR"], **kw)

from MAT.Operation import OpArgument

class CarafeTokenizationStep(CmdlineTokenizationStep):

    argList = [OpArgument("heap_size", hasArg = True, help = "If present, specifies the -Xmx argument for the Java JVM"),
               OpArgument("stack_size", hasArg = True, help = "If present, specifies the -Xss argument for the Java JVM"),
               OpArgument("handle_tags", help = "If present, treat the signal as XML and tokenize XML elements as single tokens"),
               OpArgument("tokenizer_patterns", hasArg = True, help = "See the jCarafe docs on --tokenizer-patterns.")
               ]

    def doBatch(self, iDataPairs, handle_tags = False, tokenizer_patterns = None, **kw):
        if iDataPairs == []:
            return iDataPairs
        # We're only going to deal with the true zone type.
        zType, rAttr, regions = self.descriptor.getTrueZoneInfo()
        # For almost all applications, this will be called from
        # the zoner. But it could be a standalone step, no problem.
        import MAT.Config, MAT.Document
        from MAT.Command import FileSystemCmdlineLocalProcess
        # regionStr = ":".join(regions)
        # Adding double-quotes for those situations where there are spaces in pathnames.
        cmdContainer = _jCarafeJarInvocation(cls = "org.mitre.jcarafe.tokenizer.FastTokenizer",
                                             task = self.descriptor,
                                             **kw)        
        cmdContainer.extend(['--json', '--input-dir',
                             "%(tok_in)s", '--output-dir',
                             "%(tok_out)s"],
                            {"tok_in": None, "tok_out": None})

        if rAttr:
            for region in regions:
                cmdContainer.extend(["--region", "%s:%s=%s" % (zType, rAttr, region)])
        else:
            cmdContainer.extend(["--region", zType])

        if handle_tags:
            cmdContainer.extend(["--handle-tags"])

        if tokenizer_patterns:
            cmdContainer.extent(["--tokenizer_patterns", tokenizer_patterns])
        
        cmd = FileSystemCmdlineLocalProcess(cmdContainer,
                                            inVar = "tok_in", outVar = "tok_out",
                                            fileDumper = _jsonIO,
                                            fileLoader = _jsonIO,
                                            argsAreDirectories = True)
        # SAM 12/27/10: exploiting the filterer temporarily to free me from having to worry
        # about Ben updating Carafe. See _jsonIO above too.
        # If the document HAPPENS to be tokenized, bad things will
        # happen: if we use mergeOnOutput alone, the tokens will be copied
        # into the document sent to Carafe, and then the document
        # will come back with two sets of tokens: one from the original
        # tokenization, and one from the new one. Then BOTH will
        # be merged, which will give you three sets of tokens. So
        # we have to make sure we remove them in case they're already
        # there (this is a perverse case, in which something was
        # tokenized but there's nothing in the phases to indicate
        # it, and this bug will vanish when we start inferring the "done"
        # state properly, but right now, this is probably something
        # we should be doing, just to be safe).
        lexTags = self.descriptor.getAnnotationTypesByCategory("token")
        cmd.processAnnotSets([x[1] for x in iDataPairs],
                             removeOnInput = lexTags,
                             truncateAndMergeOnOutput = lexTags
                             # mergeOnOutput = lexTags
                             )
        return iDataPairs

    def do(self, annotSet, **kw):
        return self.doBatch([(None, annotSet)], **kw)[0][1]

#
# Core tagging capability
#

MAT_SERVER_PORT = int(MAT.Config.MATConfig["HTTP_PORT"])

class CarafeTagger(Tagger):

    def __init__(self, task, stepName, tagger_local = False,
                 tagger_model = None, heap_size = None, stack_size = None, prior_adjust = None,
                 tagging_pre_models = None, add_tokens_internally = False,
                 capture_token_confidences = False, capture_sequence_confidences = False,
                 parallel = False, nthreads = None,
                 **args):
        Tagger.__init__(self, **args)

        self.task = task
        self.addTokensInternally = add_tokens_internally
        self.captureConfidences = []
        if capture_token_confidences:
            self.captureConfidences.append("tok_confidence")
        if capture_sequence_confidences:
            self.captureConfidences.append("seq_confidence")            
        
        if tagger_model is None:
            defaultModel = self.task.getDefaultModel()
            if defaultModel and os.path.exists(defaultModel):
                tagger_model = defaultModel
        
        if tagger_model is None:
            raise TaggerConfigurationError, "no model specified"
        self.taggerModel = tagger_model
        self.heapSize = heap_size
        self.stackSize = stack_size
        if prior_adjust is not None:
            self.priorAdjust = prior_adjust
        else:
            # Slight recall bias.
            self.priorAdjust = "-1.0"
        self.nthreads = nthreads
        self.parallel = parallel
        self.preModels = None
        if tagging_pre_models is not None:
            modelPats = tagging_pre_models.split(",")
            import glob
            self.preModels = []
            for pat in modelPats:
                self.preModels += glob.glob(pat)

        self.serverName = stepName
        
        self.fileDumper = self.fileLoader = _jsonIO
        # For the moment, this will always be local.
        self.local = tagger_local

    # I want to efficiently support batch processing. This means that
    # processAnnotSet needs to do the right thing. If it's remote,
    # it should do it file by file, but if it's local, it should
    # do it by directory, no matter how many files are present.

    # Now, the other thing here is that I don't want to use the zones
    # in the document, but rather the SEGMENTs. And the things I
    # want to tag are those SEGMENTs which are owned by MACHINE, or
    # not owned by anyone at all. And since Carafe doesn't update
    # the annotator slot, I'm going to kill 2 birds with one stone
    # by consolidating those SEGMENTs together AND marking them
    # anticipatorily as owned by MACHINE. Realistically, there aren't
    # going to be both types of segments, I don't think - if the document
    # is machine annotated, all the segments which were originally
    # owned by nobody will now be owned by MACHINE anyway. But
    # it doesn't hurt to do it anyway.

    # Well, there's another problem, where Carafe can't match
    # annotations which have more than one attribute/value pair.
    # So for now, I need to create a new annotation, rather than
    # reuse the SEGMENTs. Actually, this isn't the reason I need to
    # create CARAFE_INSTRUCTION - at the point of tagging, I'd only
    # have SEGMENT:annotator=MACHINE. See below.

    def Process(self, annotSets, removeOverlaps = None, argsAreDirectories = True):

        # At the moment, Carafe behaves as if it has a single region
        # for the whole document if it encounters no matching regions.
        # So I have to be careful not to pass annotSets with no
        # taggable regions. For training,  I've defaulted to using zones
        # or the whole doc if there are no segments; here, I'm going to
        # do the same thing. I'd rather not, but it seems important for the
        # flexibility of the tool.

        # Don't cross zones when you do segment computation.

        # I've thought for a while about whether I really need to add the CARAFE_INSTRUCTION
        # annotation. I've concluded that I should. First, I have to do the
        # collapsing of the None and Machine segments anyway. So I can't get around
        # that bit of work. More important, if some of the annotSets have
        # segments, others zones, and others nothing, I'd like this to work
        # transparently, rather than having to issue multiple tagging commands.
        # It's not because of worrying about crossing segment boundaries; if I
        # weren't merging, I'd have to pass in different region information depending
        # on whether I had zones, segments or nothing, but I'd be able to do it,
        # modulo the multiple invocations.

        # Finally, Carafe is liberated from having to worry about MAT-JSON v2, if
        # it doesn't want to worry about it.

        def usableSeg(seg):
            return seg.get("annotator") in [None, "MACHINE"]

        regionLists = MAT.Document.AnnotatedDoc.processableRegions(annotSets, task = self.task,
                                                                   segmentFilterFn = usableSeg)

        origAnnotSets = annotSets
        annotSets = []

        contentTags = self.task.getAnnotationTypesByCategory("content")
        tagsToMerge = contentTags[:]

        if self.captureConfidences:
            tagsToMerge += self.captureConfidences

        for regionList, d in zip(regionLists, origAnnotSets):
            if regionList:
                annotSets.append(d)
                # For each doc that has a regionList, we need to update the segments as
                # follows: extend the segments which start at any of the regions to
                # the end of the region, remove the ones which are in the region
                # but don't start it, and 
                # mark the extended segments as MACHINE. I'd love to do this while
                # computing processableRegions, but it's more important for that code to be
                # general.
                t = d.findAnnotationType("CARAFE_INSTRUCTION")
                for [start, end, ignore] in regionList:
                    d.createAnnotation(start, end, t)
                starts = dict([(p[0], p[1]) for p in regionList])
                toRemove = []
                curSeg = None
                for seg in d.orderAnnotations(["SEGMENT"]):
                    try:
                        seg.end = starts[seg.start]
                        seg["annotator"] = "MACHINE"
                        curSeg = seg
                    except KeyError:
                        if curSeg and (seg.end <= curSeg.end):
                            toRemove.append(seg)
                # And we also need to remove all the content annotations
                # which are in any of the regions. The regions will
                # be ordered.
                rIndex = 0
                curRegion = regionList[0]
                for annot in d.orderAnnotations(contentTags):
                    while curRegion and (annot.start >= curRegion[1]):
                        rIndex += 1
                        if rIndex == len(regionList):
                            curRegion = None
                        else:
                            curRegion = regionList[rIndex]
                    if curRegion is None:
                        break
                    # At this point, we know the annotation starts
                    # before the region ends. If it starts after the region
                    # starts, then let's not bother checking to make sure it
                    # ends before the region ends, and just assume we need to
                    # toss it.
                    if annot.start >= curRegion[0]:
                        toRemove.append(annot)                
                
                if toRemove:
                    d.removeAnnotationGroup(toRemove)

        if self.local:
            cmd = SynchronousCarafeTagger(self._LocalInvocation(),
                                          inVar = "carafe_in", outVar = "carafe_out",
                                          fileDumper = self.fileDumper,
                                          fileLoader = self.fileLoader,
                                          argsAreDirectories = argsAreDirectories)
        elif MAT.Tagger.TAGGER_BROKER is not None:
            # Do a local proxy.
            cmd = AsynchronousCarafeTagger(self).localProxy(MAT.Tagger.TAGGER_BROKER,
                                                            self.fileDumper, self.fileLoader)
        else:
            cmd = AsynchronousCarafeTagger(self).remoteProxy("localhost", MAT_SERVER_PORT,
                                                             self.fileDumper, self.fileLoader)

        # So here's the problem with partial annotation. First, Carafe doesn't know what
        # to do with things that already have annotations in them - it adds another
        # annotation type, rather than checking to see if there is one there already.
        # So if I don't remove the annotations from those regions, then I've got
        # two of the annotations. Then, if I merge on output, I get duplicates again.
        # So I need to do several things: first, I need to remove all annotations
        # in the SEGMENTs I'm about to tag (I don't think I have to do it in the segmentless
        # case, because it'll never get to this point, due to the stepCanBeDone() check).
        # Second, I need to filter out all the content annotations.
        
        # SAM 12/27/10: exploiting the filterer temporarily to free me from having to worry
        # about Ben updating Carafe. See _jsonIO above too.
        
        cmd.processAnnotSets(annotSets,
                             # Only pass annotations which AREN'T the content annotations.
                             removeOnInput = contentTags,
                             mergeOnOutput = tagsToMerge)
        for annotSet in annotSets:
            annotSet.removeAnnotations(atypes = ["CARAFE_INSTRUCTION"])
            if removeOverlaps is not None:
                annotSet.removeOverlaps(removeOverlaps)

    def _enhanceCmdline(self, s):
        s.extend(["--mode", "json", "--model", "%(tagger_model)s", "--region", "CARAFE_INSTRUCTION"],
                 {"tagger_model": self.taggerModel})
        if self.priorAdjust is not None:
            s.extend(["--prior-adjust", str(self.priorAdjust)])
        if self.preModels is not None:
            # We need a separate binding for each model, because
            # the dictionary requires separate values.
            i = 0
            for m in self.preModels:
                s.extend(['--pre-model', "%%(preModel%d)s" % i],
                         {"preModel"+str(i): m})
                i += 1

        # No longer. We're standardizing on CARAFE_INSTRUCTION above.
        #zType, rAttr, regionTypes = self.task.getTrueZoneInfo()
        #if rAttr:
        #    for regionType in regionTypes:
        #        s.extend(["--region", "%s:%s=%s" % (zType, rAttr, regionType)])
        #else:
        #    s.extend(["--region", zType])

        if not self.addTokensInternally:
            s.extend(['--no-pre-proc'])
        
        if self.captureConfidences:
            s.extend(["--confidences"])

        if self.parallel:
            s.extend(['--parallel'])
            if self.nthreads is not None:
                s.extend(['--nthreads', str(self.nthreads)])

        return s
            
    def _ServerInvocation(self):
        cmdContainer = _jCarafeJarInvocation(heap_size = self.heapSize,
                                             stack_size = self.stackSize,
                                             cls = "org.mitre.jcarafe_xmlrpc.tagging.JarafeTaggerServer",
                                             task = self.task)
        # The port isn't determined until runtime. 
        cmdContainer.extend(["%(jarafePort)s"])
        # At the moment, this won't work yet, because the server
        # doesn't accept things like prior_adjust. But now it does!
        return self._enhanceCmdline(cmdContainer)

    # Always a batch invocation.
    
    def _LocalInvocation(self):
        # regionStr = ":".join(regions)
        # Adding double-quotes for those situations where there are spaces in pathnames.
        cmdContainer = _jCarafeJarInvocation(heap_size = self.heapSize, stack_size = self.stackSize,
                                             cls = "org.mitre.jcarafe.tagger.GenericTagger",
                                             task = self.task)
        cmdContainer.extend(['--input-dir', "%(carafe_in)s",
                             '--output-dir', "%(carafe_out)s"],
                            {'carafe_in': None, 'carafe_out': None})

        return self._enhanceCmdline(cmdContainer)

    def createService(self):
        return AsynchronousCarafeTagger(self)

#
# This class is used internally to manage a Carafe server instance.
# All the information relating to understanding what Carafe prints out
# in server mode is here.
#

import re

class SynchronousCarafeTagger(FileSystemCmdlineLocalProcess):

    PROCESSINGFAILUREPATS = [(re.compile("java\.lang\.OutOfMemoryError: Java heap space"), False, "Java tagger ran out of memory (try increasing the heap size with the --heap_size command line argument or the heap_size attribute of your tagging step in your task.xml file)"),
                             (re.compile("java\.lang\.StackOverflowError"), False, "Java tagger ran out of stack space (try increasing the stack size with the --stack_size command line argument or the stack_size attribute of your tagging step in your task.xml file)")
                             ]

    # We want to be able to override some of these errors.

    def Fail(self, reason):
        if self.duringExit and hasattr(self, "ignoreRemainingReason") and self.ignoreRemainingReason:
            FileSystemCmdlineLocalProcess.Fail(self, "")
        else:
            FileSystemCmdlineLocalProcess.Fail(self, reason)            

    def ErrorLines(self, *lines):
        for line in lines:
            for p, extractFromGroup, msg in self.PROCESSINGFAILUREPATS:
                m = p.search(line)
                if m is not None:
                    self.ignoreRemainingReason = True
                    if extractFromGroup:
                        self.Fail(m.group(1))
                        return
                    else:
                        self.Fail(msg)
                        return
        FileSystemCmdlineLocalProcess.ErrorLines(self, *lines)

# Java Carafe is an XMLRPC server, which means that we need to
# bypass the InputLines and OutputLines.

import xmlrpclib, base64

# This guy creates a tmpDir in Command.py, but I have no use for it.

# We have to be VERY careful here. We might end up wanting to start
# up multiple model servers, so we have to check the port first
# to see if it's available - if it's not, we move on to the next
# port. Otherwise, we start up and then wait for it to
# respond, and the problem is that one that's already running
# will respond, rather than the one we started up; and the one
# we started up will fail with AddressAlreadyInUse AFTER the
# "successful" response is sent. But for all we know, another
# server will claim the port before we get there. We can't do
# anything about it.

# The subprocess doesn't get created until RunAsynchronous is called.
# So I have to do the port determination right before RunAsynchronous
# is called, which means I have to patch the cmdline.

class AsynchronousCarafeTagger(FileSystemCmdlineAsynchronousProcess):    

    PROCESSINGFAILUREPATS = [(re.compile("^Usage: .*$"), False, "Carafe command line error"),
                             (re.compile("java\.lang\.OutOfMemoryError: Java heap space"), False, "Java tagger ran out of memory (try increasing the heap size with the --heap_size command line argument or the heap_size attribute of your tagging step in your task.xml file)"),
                             (re.compile("java\.lang\.StackOverflowError"), False, "Java tagger ran out of stack space (try increasing the stack size with the --stack_size command line argument or the stack_size attribute of your tagging step in your task.xml file)"),
                             (re.compile("^Exception in .*$"), False, "Java execution error")]
    
    def __init__(self, carafeApp):
        FileSystemCmdlineAsynchronousProcess.__init__(
            self, carafeApp._ServerInvocation(),
            (carafeApp.task.name,
             carafeApp.serverName),
            None,
            verbose = 1,
            interleave_error = True,
            # prestart = True,
            failure_pats = [],
            inVar = "carafe_in", outVar = "carafe_out")
    def RunAsynchronous(self, *args, **kw):
        import MAT.Utilities
        jarafePort = MAT.Utilities.configurationFindPort("JCARAFE_SERVER_PORT")
        self.proxyString = "http://127.0.0.1:" + str(jarafePort) + "/xmlrpc"
        self.proxy = xmlrpclib.ServerProxy(self.proxyString)
        self.cmdline.extend([], substDict = {"jarafePort": str(jarafePort)})
        FileSystemCmdlineAsynchronousProcess.RunAsynchronous(self, *args, **kw)
        # And now, we poll until the server responds. But to keep the
        # server from barfing, I need to give it a well-formatted document.
        from MAT.Document import AnnotatedDoc
        pingDoc = base64.b64encode(_jsonIO.writeToByteSequence(MAT.Document.AnnotatedDoc(signal = u"")))
        import socket, time
        while True:
            try:
                self.proxy.jarafe.processBase64String(pingDoc)
            except socket.error, (errNum, msg):
                # See if it failed.
                exitStatus = self.statusHandle.Status()
                if exitStatus not in [ _SUB_RUNNING, _SUB_PRESTART ] :
                    # Read from the read handlers, which should force
                    # the exit appropriately.
                    break
                else:
                    time.sleep(.1)
                    continue
            # It's running, and it processed the empty document correctly.
            break

    def clientSubmit(self, docSerialization):
        self.curRequestData = docSerialization
        try:
            s = base64.b64decode(self.proxy.jarafe.processBase64String(base64.b64encode(docSerialization)))
            self.curRequestData = s
            self.clientSucceed()
        except xmlrpclib.Fault, e:
            self.clientFail(e.faultString)

    def clientSucceed(self):
        if self.curRequestData is not None:
            replyString = self.curRequestData
            self.curRequestData = None
            if self.requester:
                # Pull out the result serialization
                self.commandServer.clientSucceed(self.requester, replyString)
    
    def OutputLines(self, *lines):
        for line in lines:
            for p, extractFromGroup, msg in self.PROCESSINGFAILUREPATS:
                m = p.search(line)
                if m is not None:
                    if extractFromGroup:
                        self.clientFail(m.group(1))
                        break
                    else:
                        self.clientFail(msg)
                        break

    ErrorLines = OutputLines

#
# Tagging step
#

class CarafeTagStep(CmdlineTagStep):

    argList = CmdlineTagStep.argList + [OpArgument("prior_adjust", help = "Bias the Carafe tagger to favor precision (positive values) or recall (negative values). Default is -1.0 (slight recall bias). Practical range of values is usually +-6.0.", hasArg = True),
                                        OpArgument("heap_size", hasArg = True, help = "If present, specifies the -Xmx argument for the Java JVM"),
                                        OpArgument("stack_size", hasArg = True, help = "If present, specifies the -Xss argument for the Java JVM"),
                                        OpArgument("tagging_pre_models", hasArg = True, 
                                                   help = "if present, a comma-separated list of glob-style patterns specifying the models to include as pre-taggers."),
                                        OpArgument("parallel", help = "Parallelizes the decoding"),
                                        OpArgument("nthreads", hasArg = True, help = "If --parallel is used, controls the number of threads used for decoding."),
                                        OpArgument("add_tokens_internally", help = "If present, Carafe will use its internal tokenizer to tokenize the document before tagging. If your workflow doesn't tokenize the document, you must provide this flag, or Carafe will have no tokens to base its tagging on. We recommend strongly that you tokenize your documents separately; you should not use this flag."),
                                        OpArgument("capture_token_confidences", help = "If present, Carafe will capture token confidence metrics for later exploitation."),
                                        OpArgument("capture_sequence_confidences", help = "If present, Carafe will capture sequence confidence metrics for later exploitation.")]

    #
    # Carafe support.
    #
    
    # This is all taken from the AMIA tagger. There ought to be generic
    # support for AMIA tagger is kind of complex. I've tried to generalize
    # it.

    # I'm not ruling out the possibility that heap_size, etc., can be
    # provided as createSettings in step_implementation.

    def tagWithCarafe(self, annotSets, heap_size = None, stack_size = None, prior_adjust = None,
                      tagging_pre_models = None, add_tokens_internally = False, capture_token_confidences = False,
                      capture_sequence_confidences = False,
                      parallel = False, nthreads = None, **kw):
        if heap_size is None and self.initSettings.has_key("heap_size"):
            heap_size = self.initSettings["heap_size"]
        if stack_size is None and self.initSettings.has_key("stack_size"):
            stack_size = self.initSettings["stack_size"]
        if prior_adjust is None and self.initSettings.has_key("prior_adjust"):
            prior_adjust = self.initSettings["prior_adjust"]
        if tagging_pre_models is None and self.initSettings.has_key("tagging_pre_models"):
            tagging_pre_models = self.initSettings["tagging_pre_models"]
        if nthreads is None and self.initSettings.has_key("nthreads"):
            nthreads = self.initSettings["nthreads"]
        if nthreads is not None:
            nthreads = int(nthreads)
        parallel = parallel or self.initSettings.get("parallel", False)
        add_tokens_internally = add_tokens_internally or self.initSettings.get("add_tokens_internally", False)
        capture_token_confidences = capture_token_confidences or self.initSettings.get("capture_token_confidences", False)
        capture_sequence_confidences = capture_sequence_confidences or self.initSettings.get("capture_sequence_confidences", False)
        try:
            s = CarafeTagger(self.descriptor, self.stepName, heap_size = heap_size, stack_size = stack_size,
                             prior_adjust = prior_adjust, tagging_pre_models = tagging_pre_models,
                             add_tokens_internally = add_tokens_internally,
                             capture_token_confidences = capture_token_confidences,
                             capture_sequence_confidences = capture_sequence_confidences,
                             parallel = parallel, nthreads = nthreads, **kw)
            s.Process(annotSets)
        except TaggerConfigurationError, e:
            raise PluginError, "Carafe not configured properly for this task and workflow: " + str(e)

    def do(self, annotSet, **kw):
        self.tagWithCarafe([annotSet], **kw)
        return annotSet

    def doBatch(self, iDataPairs, **kw):
        self.tagWithCarafe([x[1] for x in iDataPairs], **kw)
        return iDataPairs
    
    def createTaggerService(self, heap_size = None, stack_size = None, **kw):
        # Do the same computation about heap size.
        if heap_size is None and self.initSettings.has_key("heap_size"):
            heap_size = self.initSettings["heap_size"]
        if stack_size is None and self.initSettings.has_key("stack_size"):
            stack_size = self.initSettings["stack_size"]
        return CarafeTagger(self.descriptor, self.stepName, heap_size = heap_size, stack_size = stack_size, **kw).createService()

    def stepCanBeDone(self, annotSet):
        # You can tag Carafe as long as it's (a) untagged, or (b) it has segments
        # and one of the segments is null or MACHINE.
        return CmdlineTagStep.stepCanBeDone(self, annotSet) or \
               (len([a for a in annotSet.getAnnotations(["SEGMENT"]) if a.get("annotator") in (None, "MACHINE")]) > 0)

#
# Model building
#

class CarafeModelBuilderError(Exception):
    pass

import MAT.Config, MAT.ModelBuilder, MAT.DocumentIO
from MAT.ModelBuilder import ModelBuilderError

# The arguments are a mix of camelCase and underscores because
# I'm pulling the arguments sometimes directly from XML attributes,
# where I'm using underscores instead of camelCase.

# How do you turn off PSA? That is, how do you override the default
# if PSA is set? Pass in "" or False.

class CarafeModelBuilder(MAT.ModelBuilder.ModelBuilder):

    argList = MAT.ModelBuilder.ModelBuilder.argList + \
              [OpArgument("feature_spec", hasArg = True,
                          help = "path to the Carafe feature spec file to use. Optional if feature_spec is set in the <build_settings> for the relevant model config in the task.xml file for the task."),
               OpArgument("training_method", hasArg = True,
                          help = "If present, specify a training method other than the standard method. Currently, the only recognized value is psa. The psa method is noticeably faster, but may result in somewhat poorer results. You can use a value of '' to override a previously specified training method (e.g., a default method in your task)."),
               OpArgument("max_iterations", hasArg = True,
                          help = "number of iterations for the optimized PSA training mechanism to use. A value between 6 and 10 is appropriate. Overrides any possible default in <build_settings> for the relevant model config in the task.xml file for the task."),
               OpArgument("lexicon_dir", hasArg = True,
                          help = "If present, the name of a directory which contains a Carafe training lexicon. This pathname should be an absolute pathname, and should have a trailing slash. The content of the directory should be a set of files, each of which contains a sequence of tokens, one per line. The name of the file will be used as a training feature for the token. Overrides any possible default in <build_settings> for the relevant model config in the task.xml file for the task."),
               OpArgument("parallel", help = "If present, parallelizes the feature expectation computation, which reduces the clock time of model building when multiple CPUs are available"),
               OpArgument("nthreads", hasArg = True, help = "If --parallel is used, controls the number of threads used for training."),
               OpArgument("gaussian_prior", hasArg = True,
                          help = "A positive float, default is 10.0. See the jCarafe docs for details."),
               OpArgument("no_begin", help = "Don't introduce begin states during training. Useful if you're certain that you won't have any adjacent spans with the same label. See the jCarafe documentation for more details."),
               OpArgument("l1", help = "Use L1 regularization for PSA training. See the jCarafe docs for details."),
               OpArgument("l1_c", hasArg = True,
                          help = "Change the penalty factor for the L1 regularizer. See the jCarafe docs for details."),
               OpArgument("heap_size", hasArg = True,
                          help = "If present, specifies the -Xmx argument for the Java JVM"),
               OpArgument("stack_size", hasArg = True,
                          help = "If present, specifies the -Xss argument for the Java JVM"),
               OpArgument("tags", hasArg = True,
                          help = "if present, a comma-separated list of tags to pass to the training engine instead of the full tag set for the task (used to create per-tag pre-tagging models for multi-stage training and tagging)"),
               OpArgument("pre_models", hasArg = True, 
                          help = "if present, a comma-separated list of glob-style patterns specifying the models to include as pre-taggers."),
               OpArgument("add_tokens_internally", help = "If present, Carafe will use its internal tokenizer to tokenize the document before training. If your workflow doesn't tokenize the document, you must provide this flag, or Carafe will have no tokens to base its training on. We recommend strongly that you tokenize your documents separately; you should not use this flag."),
               OpArgument("word_properties", hasArg = True, help = "See the jCarafe docs for --word-properties."),
               OpArgument("word_scores", hasArg = True, help = "See the jCarafe docs for --word-scores."),
               OpArgument("learning_rate", hasArg = True, help = "See the jCarafe docs for --learning-rate."),
               OpArgument("disk_cache", hasArg = True, help = "See the jCarafe docs for --disk_cache.")]

    def __init__(self, task, buildInfo, feature_spec = None, max_iterations = None,
                 parallel = False, nthreads = None,
                 training_method = None, gaussian_prior = None,
                 no_begin = False, l1 = False, l1_c = None,
                 lexicon_dir = None, heap_size = None, stack_size = None, 
                 tags = None, pre_models = None, add_tokens_internally = False,
                 word_properties = None, word_scores = None, learning_rate = None, disk_cache = None,
                 **kw):
        MAT.ModelBuilder.ModelBuilder.__init__(self, task, buildInfo, **kw)
        self.addTokensInternally = add_tokens_internally
        self.featureSpec = feature_spec        
        if self.featureSpec is None:
            # Use the default one.
            self.featureSpec = os.path.join(os.path.dirname(MAT.Config.MATConfig["JCARAFE_JAR"]),
                                            "resources", "default.fspec")
        if not os.path.isabs(self.featureSpec):
            self.featureSpec = os.path.join(self.task.taskRoot, self.featureSpec)
        # So you can shut off lexicon_dir.
        self.lexiconDir = lexicon_dir
        if (self.lexiconDir is not None) and (not os.path.isabs(self.lexiconDir)):
            self.lexiconDir = os.path.join(self.task.taskRoot, self.lexiconDir)
        self.maxIterations = max_iterations
        self.parallel = parallel
        self.nthreads = nthreads
        if self.nthreads is not None:
            self.nthreads = int(self.nthreads)
        self.passThroughArgs = {
            "--word-properties": word_properties,
            "--word-scores": word_scores,
            "--learning-rate": learning_rate,
            "--disk-cache": disk_cache
            }
        # Make sure you can use the empty string to override.
        self.trainingMethod = training_method
        if self.trainingMethod == "":
            self.trainingMethod = None 
        if (self.trainingMethod is not None) and (self.trainingMethod not in ["psa"]):
            raise ModelBuilderError, ("unknown training method '%s'" % self.trainingMethod)
        # It can be passed in as an int or a string.
        if self.maxIterations is not None:
            self.maxIterations = int(self.maxIterations)
        self.heapSize = heap_size
        self.stackSize = stack_size
        self.tags = None
        if tags is not None:
            self.tags = tags.split(",")
        self.preModels = None
        pre_models = pre_models
        if pre_models is not None:
            modelPats = pre_models.split(",")
            import glob
            self.preModels = []
            for pat in modelPats:
                self.preModels += glob.glob(pat)
        self.gaussianPrior = gaussian_prior
        self.noBegin = no_begin
        self.dol1Regularization = l1
        self.l1Penalty = l1_c

    # So. We may need two different temp directories. The first (maybe) is for the files, the second
    # is for the tag_set (maybe).

    # docTmpDir is a temporary directory to put the documents in, in case
    # the caller wants to inspect them for some reason. tmpDir is the
    # tmp directory to use for everything, except for the docTmpDir if it's
    # provided.
        
    def _run(self, modelOutputFile, fileList, docTmpDir, tmpDir, oStream):

        if not self.tags:
            tagSetFile = self._createTagSetFile(tmpDir)
        else:
            tagSetFile = None

        self._prepareDocuments(fileList, docTmpDir, oStream)

        cmdContainer = self._prepareJavaCmd(modelOutputFile, docTmpDir, tagSetFile)

        if oStream:
            print >> oStream, "Cmdline is", cmdContainer.createCmdline()

        # For the moment, until the modeler writes to stdout only, we'll
        # interleave error in the case where we're subprocess monitoring.
        cmd = SimpleLocalProcess(cmdContainer)
        # stdout can't be None.
        exitStatus, errMsg = cmd.RunSynchronous(stdout = oStream or sys.stdout)

        if exitStatus != _SUB_SUCCESS:
            raise ModelBuilderError, ("Command failure during model training (%s); cmdline was %s" % (errMsg, cmdContainer.createCmdline()))

    # Support methods. Might be overridden below.

    def _createTagSetFile(self, tmpDir):

        # Build the tag set file. Use a temporary directory,
        # because access to temp files across platforms isn't
        # guaranteed, according to the Python docs.
        tagSetFile = os.path.join(tmpDir, "tag_set")
        # A tag set file should contain only the names of
        # the tags, one per line, no newlines. If the tags
        # have attr sets, make sure you create a special
        # tag set file which has the proper attr syntax.
        # If there's more than one attr in the attr set,
        # it can't be done.
        # Opening "wb" because it appears that \n\r on Windows
        # hoses Java Carafe. Well, now it doesn't; the OTHER one hoses it on
        # Windows.
        fp = open(tagSetFile, "w")
        # First, do all the effective info. If the true label isn't in
        # trueL, it's an error unless the label category is "token".
        # Then, for all labels which aren't already mentioned, add the labels.
        # If there are attributes which aren't effective labels, 
        # ignore them. If any of the labels are spanless, then barf.
        trueL, attrMap, effectiveInfo = self.task.getLabelsAndAttributesForCategory("content")
        r = self.task.getAnnotationTypeRepository()
        spannedTrueL = set([t for t in trueL if r[t].hasSpan])
        trueLRemainder = set(trueL)
        okToks = set()
        for eName, (trueLabel, attr, val) in effectiveInfo.items():
            if trueLabel not in spannedTrueL:
                continue
            if (trueLabel not in trueL) and (trueLabel not in okToks):
                if self.task.getCategoryForLabel(trueLabel) != "token":
                    raise ModelBuilderError, ("can't build Carafe model for effective labels (%s) whose true label isn't in the same category, unless it's a token" % eName)
                else:
                    okToks.add(trueLabel)
            fp.write("%s:%s=%s\n" % (trueLabel, attr, val))
            trueLRemainder.discard(trueLabel)
        for name in (trueLRemainder & spannedTrueL):
            fp.write(name + "\n")
        fp.close()
        return tagSetFile

    # Ensure that the documents, in case they have the same names, are distinguished.
    # But don't change them unless you have to (test suite barfs, etc.).

    # Actually, things have gotten a bit more complicated. Now that I'm using SEGMENT
    # annotations, the system can train on any segment that isn't owned by MACHINE
    # and has been annotated. We might restrict it further to gold or reconciled.
    # So we never use copy anymore.

    # We're also coding around two bugs of Ben's: first, that Carafe will train
    # against everything if no regions are found, and second, that Carafe won't
    # match a region if it has more than one attribute-value pair.

    # Note that we need CARAFE_INSTRUCTION for the latter reason.
    
    def _prepareDocuments(self, fileList, docTmpDir, oStream):

        basenameMap = {}

        if self.reader.__class__ is not MAT.DocumentIO.JSONDocumentIO:
            if oStream:
                print >> oStream, "Converting files to MAT JSON format..."
        else:
            if oStream:
                print >> oStream, "Copying files..."

        foundDocs = False
        docEntries = []
        for f in fileList:
            bname = os.path.basename(f)
            try:
                basenamePrefix = str(basenameMap[f]) + "_"
                basenameMap[f] += 1
            except KeyError:
                basenamePrefix = ""
                basenameMap[f] = 1
            docEntries.append([f, bname, basenamePrefix, self.reader.readFromSource(f)])

        # It used to be the case that we could just copy over documents which
        # were already in the right format. But now we have to find those segments
        # which are useable, and mark them.
        
        def usableSeg(seg):
            if (seg.get("annotator") in [None, "MACHINE"]) or \
               (self.partialTrainingOnGoldOnly and (seg.get("status") == "non-gold")):
                return False
            else:
                return True

        regionLists = MAT.Document.AnnotatedDoc.processableRegions([d for [f, bname, basenamePrefix, d] in docEntries],
                                                                   task = self.task,
                                                                   segmentFilterFn = usableSeg)
        
        for regionList, [f, bname, basenamePrefix, d] in zip(regionLists, docEntries):
            if regionList:
                # At the moment, Carafe ignores region markings if there are no regions at all. So
                # we can only use docs where segs were found.
                foundDocs = True
                t = d.findAnnotationType("CARAFE_INSTRUCTION")
                for [start, end, ignore] in regionList:
                    d.createAnnotation(start, end, t)
                _jsonIO.writeToTarget(d, os.path.join(docTmpDir, basenamePrefix + bname))
                
        if not foundDocs:
            raise ModelBuilderError, "No appropriate segments found for model building"

    def _prepareJavaCmd(self, modelOutputFile, docTmpDir, tagSetFile):

        # regionStr = ":".join(regions)
        # Adding double-quotes for those situations where there are spaces in pathnames.
        cmdContainer = _jCarafeJarInvocation(heap_size = self.heapSize, stack_size = self.stackSize,
                                             cls = "org.mitre.jcarafe.tagger.GenericTagger",
                                             task = self.task)
        cmdContainer.extend(['--mode', 'json', '--train',
                             '--input-dir', "%(input)s",
                             '--model', "%(model)s", 
                             '--fspec', "%(fspec)s",
                             "--region", "CARAFE_INSTRUCTION"],
                            {'input': docTmpDir,
                             'model': modelOutputFile,
                             'fspec': self.featureSpec})

        if not self.addTokensInternally:
            cmdContainer.extend(['--no-pre-proc'])

        # No need. We're standardizing on CARAFE_INSTRUCTION above.
        #zType, rAttr, regions = self.task.getTrueZoneInfo()
        #if rAttr:
        #    for region in regions:
        #        cmdContainer.extend(["--region", "%s:%s=%s" % (zType, rAttr, region)])
        #else:
        #    cmdContainer.extend(["--region", zType])
        
        # Either the tag set, or a set of tags.
        if self.tags is not None:
            for t in self.tags:
                cmdContainer.extend(['--tag', t])
        else:
            cmdContainer.extend(['--tagset', "%(tagset)s"],
                                {'tagset': tagSetFile})
        if self.gaussianPrior is not None:
            cmdContainer.extend(['--gaussian-prior', self.gaussianPrior])
        if self.lexiconDir is not None:
            cmdContainer.extend(['--lexicon-dir', "%(lexicon)s"],
                                {'lexicon': self.lexiconDir})
        if self.preModels is not None:
            # We need a separate binding for each model, because
            # the dictionary requires separate values.
            i = 0
            for m in self.preModels:
                cmdContainer.extend(['--pre-model', "%%(preModel%d)s" % i],
                                    {"preModel"+str(i): m})
                i += 1
        if self.parallel:
            cmdContainer.extend(['--parallel'])
            if self.nthreads is not None:
                cmdContainer.extend(['--nthreads', str(self.nthreads)])
        if self.noBegin:
            cmdContainer.extend(['--no-begin'])
        if self.maxIterations is not None:
            cmdContainer.extend(['--max-iters',
                                 "%d" % self.maxIterations])
        if self.trainingMethod is not None:
            cmdContainer.extend(["--"+self.trainingMethod])
            if self.dol1Regularization:
                cmdContainer.extend(['--l1'])
                if self.l1Penalty is not None:
                    cmdContainer.extend(['--l1-C', str(self.l1Penalty)])
        for key, val in self.passThroughArgs.items():
            if val is not None:
                cmdContainer.extend([key, val])
        return cmdContainer

    # Corpus statistics. We want to include just those documents which have at least
    # one CARAFE_INSTRUCTION segment, and just those segments. This should ultimately
    # be promoted to ModelBuilder, but the world doesn't necessarily know about
    # this yet.

    def collectCorpusStatistics(self, fileList, docTmpDir):
        # We're relying here on the fact that all collectCorpusStatistics does
        # is loop through the file list and call collectFileStatistics. So I can
        # open the docs here. And, by the way, some of the files won't be there,
        # because no segments were found. So we don't have to test the segments
        # here, because we know that any document that's present will have
        # segments.
        trueFileList = []
        for trainingF in fileList:
            f = os.path.join(docTmpDir, os.path.basename(trainingF))
            if os.path.exists(f):
                doc = _jsonIO.readFromSource(f)
                trueFileList.append(doc)
        return MAT.ModelBuilder.ModelBuilder.collectCorpusStatistics(self, trueFileList, docTmpDir)

    def collectFileStatistics(self, doc, docTmpDir):
        # doc is an actual document object - see above.
        return self.collectDocumentStatistics(doc, [(zone.start, zone.end)
                                                    for zone in doc.orderAnnotations(["CARAFE_INSTRUCTION"])])

    
