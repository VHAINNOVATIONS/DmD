# Copyright (C) 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Readers and writers for documents.

import sys, codecs, re

# I started out with cjson, but it turns out that cjson
# doesn't decode "\/" correctly. So I've switched to
# simplejson. simplejson also appears to do the right thing
# with Unicode.

from MAT import json

class NotImplementedError(StandardError):
    pass

# Toplevel getter.

_IO_LIB = {}

def declareDocumentIO(name, cls, input, output):
    global _IO_LIB
    _IO_LIB[name] = cls, input, output

def getDocumentIO(name, **kw):
    return _IO_LIB[name][0](**kw)

def getDocumentIOClass(name):
    return _IO_LIB[name][0]

def getInputDocumentIOClass(name):
    v = _IO_LIB[name]
    if not v[1]:
        raise KeyError
    return v[0]

def getOutputDocumentIOClass(name):
    v = _IO_LIB[name]
    if not v[2]:
        raise KeyError
    return v[0]

def documentIODeclared(name):
    return _IO_LIB.has_key(name)

def inputDocumentIODeclared(name):
    return _IO_LIB.has_key(name) and _IO_LIB[name][1]

def outputDocumentIODeclared(name):
    return _IO_LIB.has_key(name) and _IO_LIB[name][2]

def allDocumentIO(exclusions = None):
    return [k for k in _IO_LIB.keys() if ((exclusions is None) or (k not in exclusions))]

def allInputDocumentIO(exclusions = None):
    return [name for (name, (cls, input, output)) in _IO_LIB.items()
            if input and ((exclusions is None) or (name not in exclusions))]

def allOutputDocumentIO(exclusions = None):
    return [name for (name, (cls, input, output)) in _IO_LIB.items()
            if output and ((exclusions is None) or (name not in exclusions))]

from MAT.Document import AnnotatedDoc, LoadError

class SaveError(Exception):
    pass

#
# Base class.
#

from MAT.Operation import OptionBearer, OptionTemplate
import MAT.ExecutionContext

class DocumentIO(OptionBearer):

    # Because of the way class methods interact with
    # private variables, calling _ensureArgs() on the parent
    # of this class just doesn't work.

    @classmethod
    def _ensureArgs(cls, **kw):
        cls._consolidateArgs()
        super(DocumentIO, cls)._ensureArgs(**kw)
        
    @classmethod
    def _consolidateArgs(cls):        
        if not hasattr(cls, "args"):
            args = None
            if hasattr(cls, "inputArgs") or hasattr(cls, "outputArgs"):
                args = OptionTemplate(options = [])
                if hasattr(cls, "inputArgs"):
                    args.options += cls.inputArgs.options
                if hasattr(cls, "outputArgs"):
                    args.options += cls.outputArgs.options
            cls.args = args

    @classmethod
    def addOptions(cls, aggregator, **kw):
        cls._ensureArgs(**kw)
        super(DocumentIO, cls).addOptions(aggregator, **kw)                

    @classmethod
    def addInputOptions(cls, aggregator, **kw):
        cls._ensureArgs(**kw)
        super(DocumentIO, cls).addOptions(aggregator, subtype = "inputArgs", **kw)

    @classmethod
    def addOutputOptions(cls, aggregator, **kw):
        cls._ensureArgs(**kw)
        super(DocumentIO, cls).addOptions(aggregator, subtype = "outputArgs", **kw)

    @classmethod
    def findAll(cls, d = None, filters = None):
        global _IO_LIB
        if d is None: d = {}
        if "inputArgs" in filters:
            d.update(dict([(name, cls) for name, (cls, input, output) in _IO_LIB.items()
                           if input]))
        elif "outputArgs" in filters:
            d.update(dict([(name, cls) for name, (cls, input, output) in _IO_LIB.items()
                           if input]))
        else:
            d.update(dict([(name, cls) for name, (cls, input, output) in _IO_LIB.items()]))
        if "excluderaw" in filters:
            try:
                del d["raw"]
            except KeyError:
                pass
        return d
    
#
# All file-based IO modules.
#

# SAM 1/12/11: I'm going to add a capability to transform the document
# before it's written, or after it's read. This is to do things like
# promote annotations from ENAMEX type=X to X or other conversions.
# I'm going to do it on a document basis because I need to convert the
# annotation types, etc. This means that (a) the deserialize method
# must get a tag table, not the task, because the tag table might be
# different; and (b) the reader seed has to be handled carefully, because
# it shouldn't be polluted with the "incorrect" annotation structure, and
# (c) side effect changes in writers won't make any difference.

# The way you use the convertor is to make an instance of it when
# the file IO is created. This means that you have to register a separate
# file IO which is the combination of the convertor and the IO. This doesn't
# bother me; I don't have time or resources to promote the convertor to
# the command line, and that degree of flexibility isn't necessary anyway,
# because we'll be working with stable sources of data.

# Because we now need to copy the input to the output for inputConvert()
# we can no longer have a default null operator - it has to know that
# it's a null operator. 

class DocumentConvertor:

    def __init__(self):
        self.annotationTypeRepository = self.createAnnotationTypeRepository()

    def createAnnotationTypeRepository(self):
        return None

    def getInputTagTable(self, taskTagTable):
        return taskTagTable

    def deserializeAndConvert(self, docIO, s, seedDocument):
        if hasattr(self, "inputConvert"):
            d = MAT.Document.AnnotatedDoc(globalTypeRepository = self.annotationTypeRepository)
            docIO.deserialize(s, d)
            self.inputConvert(d, seedDocument)
            # Make sure that the phasesDone are preserved. Other metadata
            # we probably don't care about.
            if d.metadata.has_key("phasesDone"):
                # Is this right? Should it be a set union? I'm going
                # to say no, for the moment.
                seedDocument.metadata["phasesDone"] = d.metadata["phasesDone"][:]
        else:
            docIO.deserialize(s, seedDocument)

    # No longer called for side effect. A seed document is now
    # passed. The targetDoc will have the global repository
    # if available.

    # Not defined unless it's needed. Can't think of
    # another way of indicating that it's a no-op.
    
    # def inputConvert(self, sourceDoc, targetDoc)

    # Changes by side effect.

    def perhapsConvert(self, annotDoc):
        if hasattr(self, "outputConvert"):
            d = MAT.Document.AnnotatedDoc(globalTypeRepository = self.annotationTypeRepository)
            # Make sure that the phasesDone are preserved. Other metadata
            # we probably don't care about.
            self.outputConvert(annotDoc, d)
            if annotDoc.metadata.has_key("phasesDone"):
                d.metadata["phasesDone"] = annotDoc.metadata["phasesDone"][:]
            return d
        else:
            return annotDoc

    # def outputConvert(self, annotDoc, targetDoc)

#
# You should be able to register a convertor for a given task.
#

# This can only live on children of DocumentFileIO.

class RegistrationError(Exception):
    pass

_FILEIO_CONVERTORS = {}

def registerConvertorInstructionSet(ioName, taskName, cls = None, file = None, xml = None):
    global _FILEIO_CONVERTORS
    iocls = getDocumentIOClass(ioName)
    if not issubclass(iocls, DocumentFileIO):
        raise RegistrationError, "convertors can be registered only on DocumentFileIO classes"
    if not (cls or file or xml):
        raise RegistrationError, "none of cls or file or xml are provided"
    if ((cls and file) or (cls and xml) or (xml and file)):
        raise RegistrationError, "only one of cls or file or xml may be provided"
    # What goes in here is a function which returns an instruction set engine.
    if cls:
        if not issubclass(cls, DocumentInstructionSetEngine):
            raise RegistrationError, "cls must be a subclass of DocumentInstructionSetEngine"
        _FILEIO_CONVERTORS[(iocls, taskName)] = cls
    elif file:
        if not os.path.isabs(file):
            raise RegistrationError, "file must be an absolute pathname"
        _FILEIO_CONVERTORS[(iocls, taskName)] = lambda: DocumentInstructionSetEngine(instructionSetFile = file)
    else:
        _FILEIO_CONVERTORS[(iocls, taskName)] = lambda: DocumentInstructionSetEngine(instructionSetXML = xml)

# And now, the convertible class itself.

class DocumentFileIO(DocumentIO):

    def __init__(self, encoding = None, task = None, convertor = None, **kw):
        # The command line tool may provide an explicit None
        # as an argument, which is almost never a good thing
        if encoding is None:
            encoding = 'ascii'
        self.encoding = encoding
        self.truncateOnUpdate = True
        self.task = task
        self.convertor = convertor
        if (convertor is None) and task:
            instructionSetEngineFactory = _FILEIO_CONVERTORS.get((self.__class__, task.name))
            if instructionSetEngineFactory is not None:
                isEngine = instructionSetEngineFactory()
                self.convertor = DocumentInstructionSetEngineConvertor(isEngine)

    #
    # Reading
    #

    # We can read from a byte sequence, or from a Unicode string,
    # or from a file. 
    
    def readFromSource(self, source, sourceName = None, **kw):
        closeIt = False
        if hasattr(source, "readline"):
            # Already a file pointer. If it's been
            # open with codecs.open, or it's sys.stdin, it'll have
            # an encoding set. But sys.stdin only reads byte sequences,
            # not Unicode strings, unlike codecs.open.
            fp = source
        elif source == "-":
            fp = sys.stdin
        else:
            fp = codecs.open(source, "r", self.encoding)
            closeIt = True
        try:
            if fp is sys.stdin:
                # read from a byte stream, but it's got an encoding.
                annotDoc = self.readFromByteSequence(fp.read(), encoding = fp.encoding, **kw)
            elif fp.encoding is not None:
                annotDoc = self.readFromUnicodeString(fp.read(), **kw)
            else:
                annotDoc = self.readFromByteSequence(fp.read(), **kw)
            if closeIt:
                fp.close()
        except Exception, e:
            if True or MAT.ExecutionContext._DEBUG:
                raise
            else:
                if isinstance(e, UnicodeDecodeError):
                    eStr = self._unicodeErrorString(e, fp.encoding or self.encoding)
                else:
                    eStr = str(e)
                raise LoadError, "Error loading from source " + str(source) + ": " + eStr
        return annotDoc

    # Internal function.
    
    def _unicodeErrorString(self, e, curEncoding):
        cands = set(["ascii", "latin1", "utf-8", "windows-1252"])
        if curEncoding:
            cands.discard(curEncoding)
        return "The document doesn't appear to be in the expected encoding (%s). The offending character sequence starts at character %d and ends at character %d. Try a different encoding (for English, other likely candidates are %s)." % (curEncoding, e.start, e.end, ", ".join(cands))

    def readFromByteSequence(self, s, encoding = None, **kw):
        if type(s) is type(u''):
            return self.readFromUnicodeString(s, **kw)
        else:
            try:
                return self.readFromUnicodeString(s.decode(encoding or self.encoding), **kw)
            except UnicodeDecodeError, e:                
                # Catch this here as well as in readFromSource(), just in case.
                raise LoadError, self._unicodeErrorString(e, encoding or self.encoding)
    
    # As a consequence of the new convertors, it will not be permitted
    # to have a convertor AND a seedDocument if the document isn't truncated.
    
    def readFromUnicodeString(self, s, seedDocument = None, taskSeed = None,
                              update = False):
        if type(s) is not type(u''):
            raise LoadError, "input to Unicode deserialization is not Unicode"
        taskSeed = taskSeed or self.task
        if seedDocument and self.convertor and not (update and self.truncateOnUpdate):
            raise LoadError, "Can't have a convertor and a seed document if you're not truncating"
        if taskSeed:
            globalRepository = taskSeed.getAnnotationTypeRepository()
        else:
            globalRepository = None
        if seedDocument is not None:
            if update and self.truncateOnUpdate:
                seedDocument.truncate()
            if taskSeed:
                if not seedDocument.atypeRepository.globalTypeRepository:
                    seedDocument.atypeRepository.globalTypeRepository = globalRepository
                elif seedDocument.atypeRepository.globalTypeRepository != globalRepository:
                    raise LoadError, "global type repository for seed document doesn't match task"
        else:
            seedDocument = MAT.Document.AnnotatedDoc(globalTypeRepository = globalRepository)
        # If there's a convertor, we REALLY don't want to use the global
        # type repository - we want to find whatever we can. But then
        # inputConvert maybe should migrate from one document to another?
        # Yes. So we create an empty document, without a repository,
        # and deserialize IT.
        if self.convertor:
            self.convertor.deserializeAndConvert(self, s, seedDocument)
        else:
            self.deserialize(s, seedDocument)
        # If we've got a task, we should try to infer the phases
        # done, if not available. The same step type may be checked
        # more than once, but because the effects of each step with the
        # same name should be the same, there should be no harm done,
        # because the steps are a set.
        # Hm. I was checking only the current workflow, if mentioned. But
        # what if the step I'm interested in isn't in the current workflow?
        # For instance, a workflow to zone and align pre-tagged documents.
        # These documents are being read in from other taggers, and won't
        # have any phases done, but they'll be tagged, but the tag step
        # isn't in this workflow. And steps are global anyway. So do them all.
        # It's a bit wasteful, but screw it.
        if taskSeed is not None and (not seedDocument.metadata.has_key("phasesDone")):
            stepsChecked = set([])            
            wfTable = taskSeed.getWorkflows()
            wfList = wfTable.values()
            # It shouldn't matter which one we encounter; the
            # check should be identical.
            # But if there are multisteps, we have to look at
            # each proxy individually, AS WELL as the overall step.
            # And because proxies are recorded locally, we
            # shouldn't pay attention to stepsChecked.
            for wf in wfList:
                for step in wf.stepList:
                    if isinstance(step, MAT.PluginMgr.MultiStep):
                        # Don't look at stepsChecked, or register it.
                        if step.isDone(seedDocument):
                            seedDocument.recordStep(step.stepName)
                        # And loop through the proxies, and register
                        # THEM.
                        for p in step.proxies:
                            if p.stepName not in stepsChecked:
                                stepsChecked.add(p.stepName)
                                if p.isDone(seedDocument):
                                    seedDocument.recordStep(p.stepName)
                    elif step.stepName not in stepsChecked:
                        stepsChecked.add(step.stepName)
                        if step.isDone(seedDocument):
                            seedDocument.recordStep(step.stepName)
        
        return seedDocument

    # This must be implemented by the children. s is a Unicode string.
    # annotDoc is an annotated document.
    
    def deserialize(self, s, annotDoc):
        raise NotImplementedError

    #
    # Writing
    #

    def writeToTarget(self, annotDoc, target):
        closeIt = False
        if hasattr(target, "writelines"):
            fp = target
        elif target == "-":
            fp = sys.stdout
        else:
            fp = codecs.open(target, "w", self.encoding)
            closeIt = True
        try:
            if self.convertor:
                annotDoc = self.convertor.perhapsConvert(annotDoc)
            if fp is sys.stdout:
                # write to a byte stream, but it's got an encoding.
                fp.write(self.writeToByteSequence(annotDoc, encoding = fp.encoding))
            elif fp.encoding is not None:
                fp.write(self.writeToUnicodeString(annotDoc))
            else:
                fp.write(self.writeToByteSequence(annotDoc))
            fp.flush()
        except UnicodeEncodeError, e:
            raise SaveError, str(e)
        if closeIt:
            fp.close()

    def writeToByteSequence(self, annotDoc, encoding = None):
        return self.writeToUnicodeString(annotDoc).encode(encoding or self.encoding)

    # Returns a Unicode string.
    
    def writeToUnicodeString(self, annotDoc):
        raise NotImplementedError

#
# JSON reading/writing
#

from MAT.Annotation import AnnotationCore, StringAttributeType, \
     AttributeValueList, AttributeValueSet, AttributeValueSequence, \
     AnnotationAttributeType
from MAT.ReconciliationDocument import ReconciliationDoc

class JSONDocumentIO(DocumentFileIO):

    def __init__(self, encoding = None, legacyWriter = False, **kw):
        # ALWAYS utf-8.
        self.legacyWriter = legacyWriter
        DocumentFileIO.__init__(self, 'utf-8', **kw)

    def readFromByteSequence(self, s, encoding = None, **kw):
        # Never allow the encoding to be changed.
        return DocumentFileIO.readFromByteSequence(self, s, **kw)

    def deserialize(self, s, annotDoc):
        try:
            d = json.loads(s)
        except ValueError:
            raise LoadError, "input doesn't appear to be JSON"
        self._deserializeFromJSON(d, annotDoc)

    # This is seldom used as a separate function, but the
    # WebClient needs it.

    # One problem is that JSON, itself, doesn't have a distinction
    # between float and int, but I do. In the browser, if you type
    # 6.0, it gets evaluated as 6. So every value associated with
    # a float slot needs to be coerced to a float, if it's an int.
    # This should happen on decode.
    
    def _deserializeFromJSON(self, d, annotDoc):
        # Check for the version. If it's greater than 1, barf.
        version = d.get("version", 1)
        if version > 2:
            raise LoadError, "MAT-JSON version is later than version 2"
        # New for JSON in 2.0: see if reconciliation is set.
        # If it is, make the object a ReconciliationDocument object.
        # If the annotDoc isn't empty, raise an error.
        # Note that we're not requiring that metadata be present,
        # even though the spec really says it should be.
        if d.has_key("metadata") and d["metadata"].get("reconciliation_doc"):
            if not isinstance(annotDoc, ReconciliationDoc):
                if annotDoc.signal:
                    raise LoadError, "Can't turn a previously instantiated doc into a reconciliation document"
                annotDoc.__class__ = ReconciliationDoc
        try:
            annotDoc.signal = d["signal"]
        except KeyError:
            pass
        try:
            annotDoc.metadata = d["metadata"]
        except KeyError:
            pass

        # Deal with the float thing.
        def make_float(x):
            if (x is not None) and (type(x) is int):
                return float(x)
            else:
                return x
            
        if d.has_key("asets"):
            annotMap = {}
            aPairs = []
            for adir in d["asets"]:
                hasSpan = adir.get("hasSpan", True)
                hasID = adir.get("hasID", False)
                t = annotDoc.findAnnotationType(adir["type"], hasSpan = hasSpan)
                
                # TEMPORARY SHIM.
                attrIndices = None
                attrTypes = None
                annotIndices = None
                digesters = None
                annotDigesters = None
                maybeAnnotVals = False
                if adir["attrs"]:
                    attrIndices = []
                    annotIndices = []
                    digesters = []
                    annotDigesters = []
                    for attr in adir["attrs"]:
                        if type(attr) in (str, unicode):
                            tName = attr
                            tType = tAggr = None
                        else:
                            tName = attr["name"]
                            tType = attr.get("type")
                            tAggr = attr.get("aggregation")
                        # When we decode, we have to make sure that
                        # the attributes are ordered appropriately. They may
                        # have been defined otherwise for other documents.
                        # And this will be a threading problem, of course...
                        # This should no longer be a problem, since the
                        # annotations are now local to a document.
                        attrIndex = t.ensureAttribute(tName, aType = tType, aggregation = tAggr)
                        attrIndices.append(attrIndex)
                        # We need to deal with the float/int issue here.
                        if tType == "annotation":
                            # The IDs are all strings. We need to look
                            # them up in the annotMap. Eventually.
                            maybeAnnotVals = True
                            annotIndices.append(attrIndex)
                            if tAggr == "list":
                                digesters.append(lambda x: ((x is not None) and AttributeValueList([annotMap[v] for v in x])) or None)
                            elif tAggr == "set":
                                digesters.append(lambda x: ((x is not None) and AttributeValueSet([annotMap[v] for v in x])) or None)
                            else:
                                digesters.append(lambda x: ((x is not None) and annotMap[x]) or None)
                            annotDigesters.append(digesters[-1])
                        elif tType == "float":
                            if tAggr == "list":
                                digesters.append(lambda x: ((x is not None) and AttributeValueList([make_float(v) for v in x])) or None)
                            elif tAggr == "set":
                                digesters.append(lambda x: ((x is not None) and AttributeValueSet([make_float(v) for v in x])) or None)
                            else:
                                digesters.append(make_float)
                        elif tAggr == "set":
                            digesters.append(lambda x: ((x is not None) and AttributeValueSet(x)) or None)
                        elif tAggr == "list":
                            digesters.append(lambda x: ((x is not None) and AttributeValueList(x)) or None)
                        else:
                            digesters.append(lambda x: x)
                # Do postponement of creating attributes, just in case
                # there are annotation-valued attributes. And this has
                # to be done all the way to the end of the asets loop.
                for a in adir["annots"]:
                    aI = 0
                    if hasSpan:
                        newAnnot = annotDoc.createAnnotation(a[0], a[1], t, blockAdd = True)
                        aI = 2
                    else:
                        newAnnot = annotDoc.createSpanlessAnnotation(t, blockAdd = True)
                    if hasID:
                        if a[aI] is not None:
                            newAnnot.setID(a[aI])
                            annotMap[a[aI]] = newAnnot
                        aI += 1
                    # If you have some attributes, loop through
                    # all the attr values, and add it at the appropriate
                    # index. Postpone if there may be annotation-valued attributes.
                    # Actually, postpone ONLY the annotation-valued attributes themselves;
                    # otherwise, if you have an annotation with an effective label
                    # AND annotation-valued attributes, if it's a value of
                    # some other annotation-valued attribute which expects the
                    # effective label to be set, you'll be hosed.
                    if attrIndices is not None:
                        annotVals = []
                        i = 0
                        for val in a[aI:]:
                            thisIdx = attrIndices[i]
                            if thisIdx in annotIndices:
                                annotVals.append(val)
                            else:
                                newAnnot[attrIndices[i]] = digesters[i](val)
                            i += 1
                        if annotVals:
                            aPairs.append((newAnnot, annotVals, annotIndices, annotDigesters))
                    annotDoc._addAnnotation(newAnnot)
            # And now, this is for the annot values.
            for newAnnot, attrInput, attrIndices, digesters in aPairs:
                i = 0
                for val in attrInput:
                    newAnnot[attrIndices[i]] = digesters[i](val)
                    i += 1

    # I need this because of the special role it plays in the Web services.

    # In order to serialize annotations which have IDs and spans, we need
    # to modify this. Then, we'll need to convert annotations in annotation-valued
    # attribute slots into IDs.

    # I've added a legacyWriter flag for my own convenience. All spanless
    # annotations will be dropped, and all annotation-valued attributes will be
    # nulled out,  and all attrs will be strings. Anyone who uses this writer
    # will have to use the fancy operations in brokerAnnotations to absorb the
    # results, of course...

    def _renderAnnotationSingleValue(self, v):
        if v is None:
            return None
        else:
            return v.id

    def _renderSequence(self, v):
        if v is None:
            return v
        else:
            return list(v)

    def _renderAnnotationSequence(self, v):
        if v is None:
            return v
        else:
            return [a.id for a in v]
    
    def renderJSONObj(self, annotDoc):
        d = {"signal": annotDoc.signal,
             "metadata": annotDoc.metadata,
             "asets": []}
        if not self.legacyWriter:
            d["version"] = 2
        asets = d["asets"]
        for aType, annots in annotDoc.atypeDict.items():
            hasSpan = aType.hasSpan
            # Don't use any() here - the list comprehension evaluates
            # everything.
            hasID = False
            for a in annots:
                if a.id is not None:
                    hasID = True
                    break
            aD = {"type": aType.lab}
            if self.legacyWriter:
                if not hasSpan:
                    continue
                aD["attrs"] = [a.name for a in aType.attr_list]
                # Anything that's an aggregation or a non-string value should be None
                meths = []
                for attr in aType.attr_list:
                    if (attr.aggregation is None) and isinstance(attr, StringAttributeType):
                        meths.append(lambda x: x)
                    else:
                        meths.append(lambda x: None)
                aD["annots"] = [[annot.start, annot.end] +
                                [meth(v) for (meth, v) in zip(meths, annot.attrs)]
                                for annot in annots]
            else:
                # Just store the type and aggregation. All the WFC stuff has already
                # been checked.
                attrList = aType.attr_list
                aD.update({"hasID": hasID,
                           "hasSpan": hasSpan,
                           "attrs": [{"name": t.name, "type": t._typename_, "aggregation": t.aggregation}
                                     for t in attrList]})
                # Assume the annotation is well-formed.
                meths = []
                for attr in attrList:
                    if isinstance(attr, AnnotationAttributeType):
                        if (attr.aggregation is None):
                            meths.append(self._renderAnnotationSingleValue)
                        else:
                            meths.append(self._renderAnnotationSequence)
                    elif attr.aggregation is not None:
                        meths.append(self._renderSequence)
                    else:
                        meths.append(lambda x: x)
                if hasID and hasSpan:                
                    aD["annots"] = [[annot.start, annot.end, annot.id] + 
                                    [meth(v) for (meth, v) in zip(meths, annot.attrs)]
                                    for annot in annots]
                elif hasID:
                    aD["annots"] = [[annot.id] + [meth(v) for (meth, v) in zip(meths, annot.attrs)]
                                    for annot in annots]
                elif hasSpan:
                    aD["annots"] = [[annot.start, annot.end] + [meth(v) for (meth, v) in zip(meths, annot.attrs)]
                                    for annot in annots]
                else:
                    aD["annots"] = [[meth(v) for (meth, v) in zip(meths, annot.attrs)] for annot in annots]
            asets.append(aD)
        return d

    def writeToUnicodeString(self, annotDoc):
        # Let's put the actual characters in there. Makes it
        # easier to examine the docs, and they're shorter.
        return json.dumps(self.renderJSONObj(annotDoc), ensure_ascii = False)

# Make the legacy writer visible to the command line.

class LegacyJSONDocumentIO(JSONDocumentIO):

    def __init__(self, legacyWriter = True, **kw):
        JSONDocumentIO.__init__(self, legacyWriter = True, **kw)

declareDocumentIO("mat-json", JSONDocumentIO, True, True)
declareDocumentIO("mat-json-v1", LegacyJSONDocumentIO, False, True)

#
# Raw reading/writing
#

class RawDocumentIO(DocumentFileIO):

    def deserialize(self, s, annotDoc):
        annotDoc.signal = s

    def writeToUnicodeString(self, annotDoc):
        return annotDoc.signal

declareDocumentIO("raw", RawDocumentIO, True, True)

#
# A manager for file pairing, currently used by MATEngine and MATTransducer.
# Eventually, this will be superseded by the corpus manager.
#

# The task is NOT required, but it's passed to all the readers and writers
# if it IS provided.

class ManagerError(Exception):

    pass

import os

class DocumentIOManager:

    def __init__(self, task = None):

        self.task = task

    def configure(self, input_file = None, input_dir = None, input_file_re = None,
                  input_encoding = None, input_file_type = None, steps = None, undo_through = None,
                  output_file = None, output_file_type = None, output_dir = None,
                  output_fsuff = None, output_encoding = None,
                  inputFileList = None, inputFileType = None, outputFileType = None,
                  **params):
        
        # Do some sanity checking.
        if inputFileType is None:
            if not inputDocumentIODeclared(input_file_type):
                raise ManagerError, ("input_file_type must be one of " + ", ".join(["'"+x+"'" for x in allInputDocumentIO()]))
        if (output_file_type is not None) and \
           (not outputDocumentIODeclared(output_file_type)):
            raise ManagerError, ("output_file_type must be one of " + ", ".join(["'"+x+"'" for x in allOutputDocumentIO()]))
        if ((output_file is not None) or (output_dir is not None)) and (output_file_type is None) and (outputFileType is None):
            raise ManagerError, "output_file or output_dir specified without output_file_type"
        if output_file is not None and (not input_file):
            raise ManagerError, "Can't specify output_file without input_file"

        if output_file and self._outputIsInWorkspace(os.path.dirname(output_file)):
            raise ManagerError, "document manager can't write to a workspace"

        if output_dir and self._outputIsInWorkspace(output_dir):
            raise ManagerError, "document manager can't write to a workspace"

        if inputFileList is None:
            if input_file and input_dir:
                raise ManagerError, "can't specify both input_file and input_dir."
            if not (input_file or input_dir):
                raise ManagerError, "one of input_file or input_dir must be specified"
        elif (output_file is not None) or (output_dir is not None):
            raise ManagerError, "can't specify output file or dir with inputFileList"
        
        self.input_file = input_file
        self.input_dir = input_dir
        self.input_file_re = input_file_re
        self.input_encoding = input_encoding
        self.input_file_type = input_file_type
        self.output_file = output_file
        self.output_file_type = output_file_type
        self.output_dir = output_dir
        self.output_fsuff = output_fsuff
        self.output_encoding = output_encoding
        self.inputFileList = inputFileList
        self.inputFileType = inputFileType
        self.outputFileType = outputFileType
        self.writeable = (input_file and output_file) or (input_dir and output_dir)
        
        if self.inputFileType is None:
            self.inputFileType = getDocumentIO(self.input_file_type, encoding = self.input_encoding,
                                               task = self.task, **params)
        # Load the writer, while I'm at it. A bit perverse, but this is where I get the
        # params.

        if self.writeable:
            if self.outputFileType is None:
                self.outputFileType = getDocumentIO(self.output_file_type, encoding = self.output_encoding,
                                                    task = self.task, **params)
                
    # Utility.
    def _outputIsInWorkspace(self, p):
        # p may be a folder. That means that its dirname would
        # be "folders", and the parent of "folders" would have
        # a properties.txt file.
        return (os.path.basename(os.path.dirname(p)) == "folders") and \
               os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(p)), "ws_db.db"))
    
    def isWriteable(self):
        return self.writeable
   
    # The loading should probably be a generator, but let's not bother with that right now.
    # This yields a list of pairs of <fullpath>, <matdocument>.

    def loadPairs(self, keepGoing = False):

        inputFileList = self._processInputFileList()

        docPairs = []
        skipPairs = []

        if MAT.ExecutionContext._DEBUG:
            keepGoing = False
        
        for f in inputFileList:
            if keepGoing:
                try:
                    docPairs.append((f, self._loadFile(f)))
                except Exception, e:
                    skipPairs.append((f, str(e)))
            else:
                docPairs.append((f, self._loadFile(f)))

        return docPairs, skipPairs

    # And here's the long awaited generator. This yields a 3-tuple (<fullpath>, <matdoc>, <error>).
    # error is set if matdoc is None, which is only possible if keepGoing is True.

    def loadPairsIncrementally(self, keepGoing = False):

        inputFileList = self._processInputFileList()

        docPairs = []
        skipPairs = []

        if MAT.ExecutionContext._DEBUG:
            keepGoing = False
        
        for f in inputFileList:
            if keepGoing:                
                try:
                    yield (f, self._loadFile(f), None)
                except Exception, e:
                    yield (f, None, str(e))
            else:
                yield (f, self._loadFile(f), None)
        
    def _processInputFileList(self):
        if self.inputFileList is not None:
            return self.inputFileList
        elif self.input_file is not None:
            return [self.input_file]
        else:
            input_file_re = self.input_file_re
            if input_file_re is not None:
                input_file_re = re.compile("^"+input_file_re+"$")
            files = os.listdir(self.input_dir)
            inputFileList = []
            for f in files:
                fullP = os.path.join(self.input_dir, f)
                if (not os.path.isdir(fullP)) and ((input_file_re is None) or (input_file_re.match(f))):
                    inputFileList.append(fullP)
            return inputFileList

    def _loadFile(self, p):
        try:
            return self.inputFileType.readFromSource(p, taskSeed = self.task)
        except IOError:
            if MAT.ExecutionContext._DEBUG:
                raise
            else:
                raise ManagerError, ("Error opening file %s for reading." % p)
        except LoadError, e:
            if MAT.ExecutionContext._DEBUG:
                raise
            else:
                raise ManagerError, ("Load error: " + str(e))

    def writeDocument(self, fName, doc):
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if self.output_file:
            oFile = self.output_file
        else:
            oFile = os.path.join(self.output_dir, os.path.basename(fName))
            if self.output_fsuff:
                oFile += self.output_fsuff
        try:
            self.outputFileType.writeToTarget(doc, oFile)
        except SaveError, e:
            if MAT.ExecutionContext._DEBUG:
                raise
            else:
                raise ManagerError, ("Error saving file %s: %s" % (oFile, str(e)))

#
# DocumentMappings
#

# These are used by document convertors, or by themselves
# (e.g., in MATTransducer). This is an XML-configurable
# object.


from MAT.XMLNode import XMLNodeDescFromFile, XMLNodeFromFile, XMLNodeFromString

import os

# The idea is that the document instruction set has a number of
# methods which filter on labels, or on attributes, or on attribute values.
# The resulting sequences are themselves classes which implement
# various operations and return themselves. So we can chain
# these, and they're always referring back to the original
# instruction set and modifying it.

DIS_DESC = {"instructions": XMLNodeDescFromFile(os.path.join(os.path.dirname(__file__), "doc_convertor_template.xml"))}

from MAT.Document import AnnotationReporter, DocumentError

class ConversionReporter(AnnotationReporter):

    def __init__(self):
        AnnotationReporter.__init__(self, partitionByLabel = False)
        self.addPosition(headerPrefix = "source", concordanceContext = True)
        self.addPosition(headerPrefix = "target", showText = False)
        self.reasons = []
        
    def addRow(self, row):
        if len(row) != 3:
            raise DocumentError, "row is different length than positions"
        AnnotationReporter.addRow(self, row[:2])
        self.reasons.append(row[2])

    def getHeadersAndRows(self):
        headers, rows = AnnotationReporter.getHeadersAndRows(self)
        return headers + ["removal reason"], [a + [b] for (a, b) in zip(rows, self.reasons)]

class DocumentInstructionSetEngine:

    def __init__(self, instructionSetFile = None, instructionSetXML = None,
                 recordConversions = False):
        self.instructionSetFile = instructionSetFile
        self.instructionSetXML = instructionSetXML
        if instructionSetFile and instructionSetXML:
            raise LoadError, "Can't have both instructionSetFile and instructionSetXML"
        if instructionSetFile:
            self._digestInstructionDom(XMLNodeFromFile(instructionSetFile, DIS_DESC))
        elif instructionSetXML:
            self._digestInstructionDom(XMLNodeFromString(instructionSetXML, DIS_DESC))
        self.recordConversions = False
        self.conversionRecorder = None
        self.conversionList = []
        if recordConversions:
            self.enableConversionRecording()

    def enableConversionRecording(self):
        self.recordConversions = True
        self.conversionRecorder = ConversionReporter()

    def _digestInstructionDom(self, domResult):
        # So the game is that the instructions are ALMOST exactly what we
        # call, but it has to be massaged just a bit in places.
        self.instructions = []
        for instr in domResult.orderedChildren:
            instrName = instr.label
            if instrName == "labels":
                self.instructions.append(self._digestLabelInstructions(instr))
            else:
                self.instructions.append((instrName, instr.attrs, None))

    def _digestLabelInstructions(self, labelInstructionNode):
        childInstructions = []
        kv = labelInstructionNode.attrs.copy()
        for instr in labelInstructionNode.orderedChildren:
            instrName = instr.label
            if instrName == "with_attrs":
                try:
                    kv["with_attrs"].append(instr.wildcardAttrs)
                except KeyError:
                    kv["with_attrs"] = [instr.wildcardAttrs]
            elif instrName == "of_attr":
                newV = {"label": instr.attrs["label"],
                        "label_re": instr.attrs["label_re"],
                        "attr": instr.attrs["attr"],
                        "attr_re": instr.attrs["attr_re"]}
                try:
                    kv["of_attr"].append(newV)
                except KeyError:
                    kv["of_attr"] = [newV]                                          
            elif instrName == "apply":
                # Make sure the function exists.
                instrAttrs = instr.attrs.copy()
                try:
                    instrAttrs["fn"] = eval(instrAttrs["fn"])
                except:
                    raise LoadError, ("Can't find function named %s" % instrAttrs["fn"])
                childInstructions.append(("apply", instrAttrs, None))
            elif instrName in ("discard_attrs", "discard_if_null"):
                instrAttrs = instr.attrs.copy()
                instrAttrs["attrs"] = [s.strip() for s in instrAttrs["attrs"].split(",")]
                childInstructions.append((instrName, instrAttrs, None))
            elif instrName == "split_attr":
                instrAttrs = instr.attrs.copy()
                instrAttrs["target_attrs"] = [s.strip() for s in instrAttrs["target_attrs"].split(",")]
                childInstructions.append((instrName, instrAttrs, None))
            elif instrName == "join_attrs":
                instrAttrs = instr.attrs.copy()
                instrAttrs["source_attrs"] = [s.strip() for s in instrAttrs["source_attrs"].split(",")]
                childInstructions.append((instrName, instrAttrs, None))
            elif instrName == "attrs":
                childInstructions.append(self._digestAttrInstructions(instr))
            else:
                childInstructions.append((instrName, instr.attrs, None))
        return ("labels", kv, childInstructions or None)

    def _digestAttrInstructions(self, attrInstructionNode):
        childInstructions = []
        for instr in attrInstructionNode.orderedChildren:
            if instr.label == "values":
                childInstructions.append(self._digestValueInstructions(instr))
            elif instr.label == "split":
                instrAttrs = instr.attrs.copy()
                instrAttrs["target_attrs"] = [s.strip() for s in instrAttrs["target_attrs"].split(",")]
                childInstructions.append((instr.label, instrAttrs, None))                
            else:
                childInstructions.append((instr.label, instr.attrs, None))
        return ("attrs", attrInstructionNode.attrs, childInstructions or None)

    def _digestValueInstructions(self, valueInstructionNode):
        return ("values", valueInstructionNode.attrs,
                [(instr.label, instr.attrs, None) for instr in valueInstructionNode.orderedChildren] or None)

    def _execute(self, sourceDoc, targetDoc):
        instSet = DocumentMappingPair(sourceDoc, targetDoc, self)
        self.execute(instSet)
        instSet.instantiateAnnotations()
    
    # Override execute() if you're writing your instructions by hand.
    
    def execute(self, mappingPair):
        self._executeInstructions(mappingPair, self.instructions)
        
    def recordConversion(self, row):
        self.conversionRecorder.addRow(row)
        self.conversionList.append(row)

    def _executeInstructions(self, bundle, instructions):
        for name, kv, childInstrs in instructions:
            r = getattr(bundle, name)(**kv)
            if childInstrs:
                self._executeInstructions(r, childInstrs)

from MAT.Annotation import AttributeValueSequence, AnnotationError

# Bleah. There are three problems with my original implementation:
# First, it's hard to understand and code against; two, it
# requires a bunch of mostly redundant code; and three, it 
# makes it really, really expensive to figure out the current
# state of an annotation which is a value of an annotation attribute
# (because it doesn't point back to the new label).
# Its main virtue is efficiency. 

# So I need to fix this, in a way that will permit me to 
# do the right thing now, and recode later. 

# OK. The solution is that nobody, but NOBODY, should update
# allEntries except via _incorporateEntry (except the DocumentMappingPair
# initializer, of course). So far, no one does, and I don't
# think I can enforce this, but. I won't have solved the complex
# coding or code duplication problem, but I'm time-limited
# at the moment and there's a LOT of code here. You can only
# do what you can do.

# Actually, I can do one more thing: I can convert a bunch of
# these things into structures, and give them __setattr__ and
# __getattr__ so the current implementation will still work.
# This will give me the opportunity to ensure that no one
# can use the original implementation to update
# the annotation type annots list without
# doing the appropriate updates, for instance.

class DMAnnotationType:

    def __init__(self, label, hasSpan, dmAnnots):
        self.label = label
        self.hasSpan = hasSpan
        for annot in dmAnnots:
            annot.atype = self
        self.annots = set(dmAnnots)

    def maybeCopy(self, lab):
        if lab == self.label:
            return self
        else:
            return DMAnnotationType(lab, self.hasSpan, self.annots)

    def incorporateEntry(self, entry):
        if self.hasSpan != entry.hasSpan:
            raise LoadError, ("hasSpan values collide for label %s" % self.label)
        else:
            for annot in entry.annots:
                annot.atype = self
            self.annots |= entry.annots

    def removeAnnots(self, annots):
        self.annots -= set(annots)
    
    # These are for backward compatibility, until I have
    # a chance to rewrite the code.

    def __getitem__(self, key):
        if key in ("label", "hasSpan", "annots"):
            return getattr(self, key)
        else:
            raise KeyError, key

    def __setitem__(self, key, val):
        if key in ("label", "hasSpan"):
            setattr(self, key, val)
        else:
            # Can't set the annots this way.
            raise KeyError, key + " not settable"            

class DMAnnotation:

    def __init__(self, instr, a):
        self.annot = a
        # Note that these values are still source annotation values.
        # Especially sets, lists and annotations.
        self.attrs = dict([(attr.name, val) for (attr, val) in zip(a.atype.attr_list, a.attrs)
                           if val is not None])
        self.touched = False
        self.atype = None
        self.removalReason = None
        instr._dmAnnotationMap[a] = self

    # These are for backward compatibility, until I have
    # a chance to rewrite the code.
    
    def __getitem__(self, key):
        if key in ("annot", "attrs", "touched"):
            return getattr(self, key)
        else:
            raise KeyError, key

    def __setitem__(self, key, val):
        if key in ("attrs", "touched"):
            setattr(self, key, val)
        else:
            # You can't set the atype this way, or the annot.
            raise KeyError, key + " not settable"

class DocumentMappingPair:

    def __init__(self, sourceDoc, targetDoc, engine):
        self.allEntries = {}
        self.engine = engine
        self.signal = sourceDoc.signal
        self.sourceDoc = sourceDoc
        self.targetDoc = targetDoc
        self.discardFailedDuringConversion = None
        self._dmAnnotationMap = {}
        for lab, atype in sourceDoc.atypeRepository.items():
            # Unpack the annotations, so I can operate on them without worrying
            # about wellformedness conditions.
            self.allEntries[lab] = DMAnnotationType(lab, atype.hasSpan,
                                                    [DMAnnotation(self, annot)
                                                     for annot in sourceDoc.getAnnotations(atypes = [lab])])

    #
    # Public filter method
    #

    # with_attrs is a list of dictionaries. The values in the dictionary
    # are values to match, with special handling for annotation labels.
    # of_attr is a list of dictionaries with the keys label, label_re,
    # attr, attr_re which describe the location(s) in which the existing
    # annotations must appear (the CURRENT label and attr, mind you,
    # so, not so efficient yet, because I have to keep mapping back
    # from the true to the DM).

    def labels(self, source = None, source_re = None, excluding = None, excluding_re = None,
               with_attrs = None, of_attr = None):
        if source is not None:
            if self.allEntries.has_key(source):
                labs = [source]
            else:
                labs = []
        else:
            if source_re is not None:
                if type(source_re) in (str, unicode):
                    source_re = re.compile("^(" + source_re + ")$")
                labs = [lab for lab in self.allEntries.keys() if source_re.match(lab)]
            else:
                labs = self.allEntries.keys()
            # Don't look at excluding if we started with source - makes no sense.
            if excluding is not None:
                try:
                    labs.remove(excluding)
                except ValueError:
                    pass
            elif excluding_re is not None:
                if type(excluding_re) in (str, unicode):
                    excluding_re = re.compile("^(" + excluding_re + ")$")
                labs = [lab for lab in labs if not excluding_re.match(lab)]


        if (with_attrs) is None and (of_attr is None):
            # Return a sequence of labels.
            # SAM 1/17/13: I originally thought that I could
            # do this by labels alone, but the problem is that
            # the label sequence uses the GLOBAL cache every
            # time it executes an operation; so if it, e.g.,
            # maps to a label that was already mapped to,
            # the next operations in that block would
            # access all the annotations mapped to that label,
            # not just the ones mapped in that block. So
            # doing this by labels is just not going to
            # work. And I have to make sure to copy the
            # annotation set, so it isn't the same as
            # the one in the reference.
            return _DISLabPairSequence(self, [(lab, list(self.allEntries[lab]["annots"])) for lab in labs])
        else:
            # Return a sequence of (lab, annotations).
            # As a special case, I'm going to allow
            # the values to be compared to the current labels of
            # annotation-valued attributes. And only the
            # label - no specifying attr-val pairs for
            # the value.
            # For each attrDict, the annotations I test
            # have to match everything.
            # But first, collect the candidate annotations.
            candAttrs = None
            if of_attr:
                # First, if there's an of_attr, collect all
                # the annotations this could possibly be.
                # These are ACTUAL annotations.
                candAttrs = set()                
                for ofAttrEntry in of_attr:
                    self._augmentCandAttrValues(candAttrs, **ofAttrEntry)
            pairs = []            
            for lab in labs:
                annots = []
                for annot in self.allEntries[lab]["annots"]:
                    # If we have some context established, if
                    # the annotation isn't in it, bail. And
                    # if there are no attrs to check, just
                    # accept it and continue.
                    if candAttrs is not None:
                        if annot["annot"] not in candAttrs:
                            continue
                        elif with_attrs is None:
                            annots.append(annot)
                            continue
                    # for each annot, let's cache the converted
                    # values, just in case. The conversion is
                    # the same no matter what.
                    attrCache = {}
                    # For each attrDict, all the values have to match.
                    for attrDict in with_attrs:
                        ok = True
                        for k, v in attrDict.items():
                            try:
                                av, conv = attrCache[k]
                            except KeyError:
                                # Convert them to strings. I imagine
                                # bad things will happen with floats,
                                # but I'm not about to worry about it
                                # at the moment. Lists and sets will never match.
                                av = annot["attrs"].get(k)
                                conv = None
                                if av is not None:
                                    if isinstance(av, AnnotationCore):
                                        # Find its current label value.
                                        av = self._dmAnnotationMap[av].atype.label
                                    elif type(av) in (int, float, str):
                                        av = str(av)
                                    elif type(av) is bool:
                                        if av is True:
                                            av = "yes"
                                        else:
                                            av = "no"
                                        conv = lambda x: x.lower()
                                    attrCache[k] = av, conv
                            if conv: v = conv(v)
                            if v != av:
                                ok = False
                                break
                        if ok:
                            # All the key/val pairs work.
                            annots.append(annot)
                            # Break out of the list of with_attrs.
                            break
                if annots:
                    pairs.append((lab, annots))
            return _DISLabPairSequence(self, pairs)

    def _augmentCandAttrValues(self, candSet, label = None, label_re = None,
                               attr = None, attr_re = None):
        if label is not None:
            if self.allEntries.has_key(label):
                entries = [self.allEntries[label]]
            else:
                entries = []
        else:
            if label_re is not None:
                if type(label_re) in (str, unicode):
                    label_re = re.compile("^(" + label_re + ")$")
                entries = [e for (lab, e) in self.allEntries.items() if label_re.match(lab)]
            else:
                entries = self.allEntries.values()
        # Now, the attrs.
        for entry in entries:
            okAttrs = set()

            if attr is not None:
                okAttrs.add(attr)
            else:
                if (attr_re is not None) and (type(attr_re) in (str, unicode)):
                    attr_re = re.compile("^(" + attr_re + ")$")
            for annot in entry["annots"]:
                for k, v in annot["attrs"].items():
                    if not v:
                        continue
                    doIt = False
                    if k in okAttrs:
                        doIt = True
                    elif (attr is None) and ((attr_re is None) or attr_re.match(k)):
                        okAttrs.add(k)
                        doIt = True
                    if doIt:
                        if isinstance(v, AnnotationCore):
                            candSet.add(v)
                        elif isinstance(v, AttributeValueSequence):
                            v = list(v)
                            if isinstance(v[0], AnnotationCore):
                                candSet.update(v)                        

    def discard_untouched(self):
        for lab, instr in self.allEntries.items():
            annotsToRemove = [a for a in instr["annots"] if not a["touched"]]
            for a in annotsToRemove:
                a.removalReason = "discard_untouched rule"
            instr.removeAnnots(annotsToRemove)
            if not instr["annots"]:
                del self.allEntries[lab]

    def instantiateAnnotations(self):
        targetDoc = self.targetDoc
        targetDoc.signal = self.signal
        discardFailed = self.discardFailedDuringConversion
        instructionSet = self.allEntries
        annotAttrValuesToAdd = []
        annotMap = {}
        for lab, instr in instructionSet.items():
            lab = instr["label"]
            hasSpan = instr["hasSpan"]
            t = targetDoc.findAnnotationType(lab, hasSpan = hasSpan)
            # Just in case we already have attributes defined.
            nonAnnotAttrs = set()
            annotAttrs = set()
            for attrObj in t.attr_list:
                if attrObj._typename_ != "annotation":
                    nonAnnotAttrs.add(attrObj.name)
            for aBundle in instr["annots"]:
                annot = aBundle["annot"]                
                attrSeed = aBundle["attrs"]
                # So how do we copy the annotations? What if
                # there are references? To do the references,
                # I probably need to put off those particular updates.
                # If we're holding an annotation value, or a list or
                # set of them, or if the attribute is known and 
                for attr, val in attrSeed.items():
                    if isinstance(val, AnnotationCore):
                        if attr in nonAnnotAttrs:
                            raise LoadError, "found attribute type clash during conversion"
                        # Sequence or not, we postpone it.
                        annotAttrValuesToAdd.append((aBundle, annot, attr, val))
                        del attrSeed[attr]                        
                    elif isinstance(val, AttributeValueSequence):
                        if (len(val) > 0) and isinstance(list(val)[0], AnnotationCore):
                            if attr in nonAnnotAttrs:
                                raise LoadError, "found attribute type clash during conversion"
                            annotAttrValuesToAdd.append((aBundle, annot, attr, val))
                            del attrSeed[attr]
                        else:         
                            attrSeed[attr] = val.copy()
                            if len(val) > 0:
                                nonAnnotAttrs.add(attr)
                    else:
                        nonAnnotAttrs.add(attr)
                if hasSpan:
                    annotMap[annot] = targetDoc.createAnnotation(annot.start, annot.end, t, attrSeed)
                else:
                    annotMap[annot] = targetDoc.createSpanlessAnnotation(t, attrSeed)

        # We want to have the option of discarding anything that
        # wasn't completely mapped, either because of some
        # selectional restriction or because of an unmapped filler.

        failedSourceAnnots = set()
        
        for dmAnnot, annot, attrName, sourceVal in annotAttrValuesToAdd:
            targetAnnot = annotMap[annot]
            failAnnot = False
            if isinstance(sourceVal, AttributeValueSequence):
                members = list(sourceVal)
                newMembers = []
                for m in members:
                    newMember = annotMap.get(m)
                    if newMember:
                        newMembers.append(newMember)
                    else:                        
                        failAnnot = True
                        dmAnnot.removalReason = "marked for failure because of missing element of sequence value for %s attribute" % attrName
                        break
                if not failAnnot:
                    try:
                        targetAnnot[attrName] = sourceVal.__class__(newMembers)
                    except AnnotationError, e:
                        dmAnnot.removalReason = "marked for failure because of error in setting %s attribute: %s" % (attrName, str(e))
                        failAnnot = True
            else:
                newValue = annotMap.get(sourceVal)
                if newValue:
                    try:
                        targetAnnot[attrName] = newValue
                    except AnnotationError, e:
                        dmAnnot.removalReason = "marked for failure because of error in setting %s attribute: %s" % (attrName, str(e))
                        failAnnot = True
                else:
                    dmAnnot.removalReason = "marked for failure because of missing value for %s attribute" % attrName
                    failAnnot = True
            if failAnnot and discardFailed and (targetAnnot.atype.lab in discardFailed):
                targetDoc.removeAnnotation(targetAnnot)
                failedSourceAnnots.add(annot)

        if self.engine.recordConversions:
            # Report what happened to the annotations.
            for a in self.sourceDoc.getAnnotations():
                if annotMap.get(a) and (a not in failedSourceAnnots):
                    self.engine.recordConversion([a, annotMap[a], None])
                else:
                    # Look up the source annot in the dmAnnotation map,
                    # and see if there's a removal reason.
                    removalReason = None
                    dmA = self._dmAnnotationMap.get(a)
                    if dmA and dmA.removalReason:
                        removalReason = dmA.removalReason
                    self.engine.recordConversion([a, None, removalReason])
                    
    #
    # Utility functions
    #
    
    def _newEntry(self, lab, hasSpan, annots):
        return DMAnnotationType(lab, hasSpan, annots)

    # entry is a DMAnnotationType, as is curEntry.
    def _incorporateEntry(self, lab, entry):
        curEntry = self.allEntries.get(lab)
        if curEntry is None:
            self.allEntries[lab] = entry.maybeCopy(lab)
        else:
            curEntry.incorporateEntry(entry)

    def _convertValueInternal(self, val, targetType):
        if targetType == "int":
            return int(val)
        elif targetType == "float":
            return float(val)
        elif targetType == "boolean":
            # Note that the source can be either a string, in which
            # case we do the string conversion, or a boolean, in
            # which case we keep it.
            if type(val) in (str, unicode):
                return ((val == "yes") and True) or False
            elif val:
                # Anything that's not False, e.g. 1
                return True
            else:
                return False
        else:
            return str(val)

    def _convertValue(self, val, targetType, targetAggregation):
        # The incoming values will likely be strings, but you never know.
        # If the incoming value is a list or a set or an AttributeValueList or an AttributeValueSet,
        # we have to convert all the values in the list. THEN do the aggregation conversion.
        if targetAggregation is None:
            tval = type(val)
            if tval is list:
                return AttributeValueList([self._convertValueInternal(v, targetType) for v in val])
            elif tval is set:
                return AttributeValueSet([self._convertValueInternal(v, targetType) for v in val])
            elif tval is AttributeValueList:
                return AttributeValueList([self._convertValueInternal(v, targetType) for v in val])
            elif tval is AttributeValueSet:
                return AttributeValueSet([self._convertValueInternal(v, targetType) for v in val])
            else:
                return self._convertValueInternal(val, targetType)
        elif targetType is None:
            if targetAggregation == "set":
                if type(val) in (list, AttributeValueList, set):
                    return AttributeValueSet(val)
                elif type(val) is not AttributeValueSet:
                    return AttributeValueSet([val])
                else:
                    return val
            elif targetAggregation == "list":
                if type(val) in (list, AttributeValueSet, set):
                    return AttributeValueList(val)
                elif type(val) is not AttributeValueList:
                    return AttributeValueList([val])
                else:
                    return val
            elif targetAggregation == "singleton":
                if type(val) in (list, AttributeValueList):
                    return val[0]
                elif type(val) in (set, AttributeValueSet):
                    return val.pop()
                else:
                    return val
        else:
            if type(val) in (list, set, AttributeValueList, AttributeValueSet):
                val = [self._convertValueInternal(v, targetType) for v in val]                
            if targetAggregation == "set":
                if type(val) is list:
                    return AttributeValueSet(val)
                else:
                    return AttributeValueSet([val])
            elif targetAggregation == "list":
                if type(val) is list:
                    return AttributeValueList(val)
                else:
                    return AttributeValueList([val])
            elif targetAggregation == "singleton":
                if type(val) is list:
                    return val[0]
                else:
                    return val
                
    # Any of target_value, target_type, target, target_aggregation may be null.    
    def _mapAttrs(self, annotPairs, target, target_value, target_type, target_aggregation):
        if (target_type is not None) and (target_type not in ('int', 'float', 'boolean', 'string')):
            raise LoadError, ("unknown target_type '%s' (must be int, float, boolean, string)" % target_type)
        if (target_aggregation is not None) and (target_aggregation not in ("set", "list", "singleton")):
            raise LoadError, ("unknown target_aggregation '%s' (must be set, list, singleton)" % target_type)
        if (target is None) and (target_type is None) and (target_value is None) and (target_aggregation is None):
            raise LoadError, "one of target, target_type, target_value, target_aggregation must be provided"

        # First, map the value if you need to.
        if (target_value is not None) and ((target_type is not None) or (target_aggregation is not None)):
            target_value = self._convertValue(target_value, target_type, target_aggregation)

        # So we want to be able to convert existing values from type to type,
        # but what comes in is a different format than what's already set. So
        # we have to be careful.
        
        for annot, keys in annotPairs:
            for key in keys:
                if annot["attrs"].has_key(key):
                    v = target_value
                    if v is None:
                        v = annot["attrs"][key]
                    if (target_type is not None) or (target_aggregation is not None):
                        v = self._convertValue(v, target_type, target_aggregation)
                    if target is not None:
                        del annot["attrs"][key]
                    annot["attrs"][target or key] = v
                    annot["touched"] = True

    def _removeAnnots(self, lab, annots):
        instr = self.allEntries[lab]
        instr.removeAnnots(annots)
        hasSpan = instr.hasSpan
        if not instr.annots:
            del self.allEntries[lab]
        # This may be the only bit of info I need from the old entry.
        return hasSpan

class _DISLabPairSequence:

    def __init__(self, dis, labAnnotPairs):
        self.docPair = dis
        self.pairs = labAnnotPairs

    # Operations supported: apply, demote, discard, discard_failed, touch, untouch, map,
    # map_attr, map_attrs, promote_attr, discard_attr, split_attr, join_attrs, set_attr,
    # discard_attrs, attrs.

    # For compatibility with DISLabPairSequence, fn accepts an entry
    # and must return a list of entries. The fn takes responsibility for
    # touching, etc.
    
    def apply(self, fn = None):
        if fn is None:
            raise LoadError, "fn is required"
        pairs = self.pairs
        self.pairs = []
        pairDict = {}
        entryUpdates = []
        for lab, annots in pairs:
            if annots:
                hasSpan = self.docPair._removeAnnots(lab, annots)
                newEntries = fn(self.docPair._newEntry(lab, hasSpan, annots))
                for newInstr in newEntries:
                    entryUpdates.append(newInstr)
                    try:
                        pairDict[newInstr["label"]] += list(newInstr["annots"])
                    except KeyError:
                        pairDict[newInstr["label"]] = list(newInstr["annots"])
        for newInstr in entryUpdates:
            self.docPair._incorporateEntry(newInstr["label"], newInstr)
        self.pairs = pairDict.items()
        return self

    def demote(self, target_label = None, target_attr = None):
        if target_label is None:
            raise LoadError, "target_label is required"
        if target_attr is None:
            raise LoadError, "target_attr is required"
        pairs = self.pairs
        self.pairs = []
        outAnnots = []
        entryUpdates = []
        for lab, annots in pairs:
            if annots:
                outAnnots += annots
                for a in annots:
                    a["touched"] = True
                    a["attrs"][target_attr] = lab
                if lab != target_label:                    
                    hasSpan = self.docPair._removeAnnots(lab, annots)
                    entryUpdates.append(self.docPair._newEntry(target_label, hasSpan, annots))
        if outAnnots:
            self.pairs.append((target_label, outAnnots))
        for instr in entryUpdates:
            self.docPair._incorporateEntry(target_label, instr)
        return self

    def promote_attr(self, source = None):
        if source is None:
            raise LoadError, "source is required"
        pairs = self.pairs
        self.pairs = []
        entryUpdates = []
        pairDict = {}
        for lab, annots in pairs:
            # For each annot, if it has the attribute, remove it
            # and promote it.
            annotsToRemove = [annot for annot in annots if annot["attrs"].has_key(source)]
            if annotsToRemove:
                hasSpan = self.docPair._removeAnnots(lab, annotsToRemove)
                for annot in annotsToRemove:
                    targetLabel = annot["attrs"][source]
                    del annot["attrs"][source]
                    annot["touched"] = True
                    entryUpdates.append(self.docPair._newEntry(targetLabel, instr["hasSpan"], [annot]))
                    try:
                        pairDict[targetLabel].append(annot)
                    except KeyError:
                        pairDict[targetLabel] = [annot]
            if len(annotsToRemove) < len(annots):
                # There are still some left.
                try:
                    pairDict[lab] += list(set(annots) - set(annotsToRemove))
                except KeyError:
                    pairDict[lab] = list(set(annots) - set(annotsToRemove))
        self.pairs = pairDict.items()
        for instr in entryUpdates:
            self.docPair._incorporateEntry(instr["label"], instr)
        return self

    def discard(self):
        pairs = self.pairs
        self.pairs = []
        for lab, annots in pairs:
            if annots:
                for a in annots:
                    a.removalReason = "discard rule"
                self.docPair._removeAnnots(lab, annots)
        return self

    def discard_if_null(self, attrs = None):
        if attrs is None:
            raise LoadError, "attrs is None"
        pairs = self.pairs
        self.pairs = []
        for lab, annots in pairs:
            toRemove = []
            toKeep = []
            for a in annots:
                removed = False
                for attr in attrs:
                    if a["attrs"].get(attr) is None:
                        toRemove.append(a)
                        a.removalReason = "discard_if_null rule"
                        removed = True
                        break
                if not removed:
                    toKeep.append(a)
            if toRemove:
                self.docPair._removeAnnots(lab, toRemove)
            if toKeep:
                self.pairs.append((lab, toKeep))
        return self

    def discard_failed(self):
        labs = [p[0] for p in self.pairs]
        if self.docPair.discardFailedDuringConversion is None:
            self.docPair.discardFailedDuringConversion = set(labs)
        else:
            self.docPair.discardFailedDuringConversion.update(labs)
        return self

    def touch(self):
        for lab, annots in self.pairs:
            for a in annots:
                a["touched"] = True
        return self

    def untouch(self):
        for lab, annots in self.pairs:
            for a in annots:
                a["touched"] = False
        return self

    def map(self, target = None):
        if target is None:
            raise LoadError, "target is required"
        pairs = self.pairs
        self.pairs = []
        outAnnots = []
        entryUpdates = []
        for lab, annots in pairs:
            if annots:
                for a in annots:
                    a["touched"] = True
                outAnnots += annots
                if lab != target:
                    hasSpan = self.docPair._removeAnnots(lab, annots)                    
                    entryUpdates.append(self.docPair._newEntry(target, hasSpan, annots))
        if outAnnots:
            self.pairs.append((target, outAnnots))
        for instr in entryUpdates:
            self.docPair._incorporateEntry(target, instr)
        return self

    def make_spanless(self, demoted_label = None, demoted_attr = None):
        if (demoted_label or demoted_attr) and not (demoted_label and demoted_attr):
            raise LoadError, "if demoted_label or demoted_attr are specified, both must be specified"
        # We have to be careful here. If any of the entries
        # are subsets of the full list of annotations for that label,
        # we can't do it.
        for lab, annots in self.pairs:
            instr = self.docPair.allEntries.get(lab)
            if (instr is not None) and (set(annots) != instr["annots"]):
                raise LoadError, "can't make a subset of a label spanless"
        # Now, do it again.
        newAnnots = []
        for lab, annots in self.pairs:
            instr = self.docPair.allEntries.get(lab)
            if instr is not None:
                instr["hasSpan"] = False
                for a in instr["annots"]:
                    if (demoted_label is not None) and (a["annot"].start is not None):
                        # Add an annotation. A REAL one in the argument position,
                        # because that's what we currently have, and a
                        # local one for the reconstitution. This will get
                        # copied, so it's kind of wasteful, but that's the
                        # way the code currently works. So use the target doc's
                        # atype (creating if necessary - after all, we WILL
                        # be creating these eventually, unless some later
                        # operation changes the label, in which case there will
                        # be a stray, empty annotation type in the target doc,
                        # which I can live with), but don't add the annotation
                        # to the target doc.
                        trueAnnot = self.docPair.targetDoc.createAnnotation(a["annot"].start, a["annot"].end, demoted_label, blockAdd = True)
                        dmAnnot = DMAnnotation(self.docPair, trueAnnot)
                        # Touch it!
                        dmAnnot["touched"] = True
                        newAnnots.append(dmAnnot)
                        a["attrs"][demoted_attr] = trueAnnot
                    a["touched"] = True
        if newAnnots:
            self.docPair._incorporateEntry(demoted_label, self.docPair._newEntry(demoted_label, True, newAnnots))
        return self

    def map_attr(self, source = None, target = None, target_type = None, target_aggregation = None):
        if source is None:
            raise LoadError, "source is required"
        annotPairs = []
        for lab, annots in self.pairs:
            annotPairs += [(a, [source]) for a in annots]
        self.docPair._mapAttrs(annotPairs, target, None, target_type, target_aggregation)
        return self
    
    def map_attrs(self, map = None):
        if map is None:
            raise LoadError, "map is required"
        allAnnots = []
        for lab, annots in self.pairs:
            allAnnots += annots
        for source, target in map.items():
            self.docPair._mapAttrs([(a, [source]) for a in allAnnots], target, None, None, None)
        return self
            
    def discard_attr(self, source = None):
        if source is None:
            raise LoadError, "source is required"
        for lab, annots in self.pairs:
            for annot in annots:
                try:
                    del annot["attrs"][source]
                    annot["touched"] = True
                except KeyError:
                    pass
        return self
    
    def set_attr(self, attr = None, value = None, value_type = None,
                 value_aggregation = None):
        if attr is None:
            raise LoadError, "attr is required"
        if value is None:
            raise LoadError, "value is required"
        
        # If the aggregation is not None, we really have to create it
        # each time.

        convertedV = None
        if value_aggregation is None:
            convertedV = self.docPair._convertValue(value, value_type, None)

        for lab, annots in self.pairs:
            for annot in annots:
                if value_aggregation is None:
                    annot["attrs"][attr] = convertedV
                else:
                    annot["attrs"][attr] = self.docPair._convertValue(value, value_type, value_aggregation)
                annot["touched"] = True
        
        return self

    def discard_attrs(self, attrs = None):
        if attrs is None:
            raise LoadError, "attrs is required"
        for lab, annots in self.pairs:
            for annot in annots:
                for source in attrs:
                    try:
                        del annot["attrs"][source]
                        annot["touched"] = True
                    except KeyError:
                        pass                    
        return self

    def split_attr(self, attr = None, target_attrs = None):
        if attr is None:
            raise LoadError, "attr is required"
        if target_attrs is None:
            raise LoadError, "target_attrs is required"
        for lab, annots in self.pairs:
            for annot in annots:
                v = annot["attrs"].get(attr)
                if v is not None:
                    # If it's a set or list, map each
                    # value to the target attributes. If
                    # it's a singleton, map it to the first one.
                    # Whatever you run out of first is where you stop.
                    del annot["attrs"][attr]
                    annot["touched"] = True
                    if isinstance(v, AttributeValueSequence):
                        v = list(v)
                        for tv, ta in zip(v, target_attrs):
                            annot["attrs"][ta] = tv
                    elif target_attrs:
                        annot["attrs"][target_attrs[0]] = v                            
        return self

    def join_attrs(self, attr = None, source_attrs = None, target_aggregation = None):
        if attr is None:
            raise LoadError, "attr is required"
        if source_attrs is None:
            raise LoadError, "target_attrs is required"
        if target_aggregation not in ("list", "set"):
            raise LoadError, "target_aggregation must be one of list, set"
        for lab, annots in self.pairs:
            for annot in instr["annots"]:
                newV = []
                found = False
                for sa in source_attrs:
                    v = annot["attrs"].get(sa)
                    if v is not None:
                        found = True
                        if isinstance(v, AttributeValueSequence):
                            newV += list(v)
                        else:
                            newV.append(v)
                        del annot["attrs"][sa]
                if found:
                    if target_aggregation == "set":
                        newV = AttributeValueSet(newV)
                    else:
                        newV = AttributeValueList(newV)
                    annot["attrs"][attr] = newV
                    annot["touched"] = True
        return self
    
    def attrs(self, source = None, source_re = None, excluding = None, excluding_re = None):

        okAttrs = set()
        forbiddenAttrs = set()

        if source is not None:
            okAttrs.add(source)
            # We're never going to use these.
            source_re = excluding = excluding_re = None
        else:
            if excluding is not None:
                forbiddenAttrs.add(excluding)
                excluding_re = None
            if (source_re is not None) and (type(source_re) in (str, unicode)):
                source_re = re.compile("^(" + source_re + ")$")
            if (excluding is None) and (excluding_re is not None) and (type(excluding_re) in (str, unicode)):
                excluding_re = re.compile("^(" + excluding_re + ")$")

        labPairs = []
        for lab, annots in self.pairs:
            # Note that the same annotation can conceivably be tickled by more than one
            # of these attributes. But I don't want to push the annotation more than once;
            # if I operate on it, I want to operate on it once.
            if annots:
                tuples = []
                for a in annots:
                    resAttrs = []
                    for k in a["attrs"].keys():
                        if k in okAttrs:
                            resAttrs.append(k)
                        elif k in forbiddenAttrs:
                            continue
                        elif (excluding_re is not None) and excluding_re.match(k):
                            # Here, we have to deal with the case where there's no
                            # source, as well as the excluding case.
                            forbiddenAttrs.add(k)
                            continue
                        elif (source is None) and ((source_re is None) or source_re.match(k)):
                            # If source was not None, we would have been approved
                            # by okAttrs already. So if source_re is ALSO None,
                            # there's nothing to block approval, so we approve.
                            okAttrs.add(k)
                            resAttrs.append(k)
                    if resAttrs:
                        tuples.append((a, resAttrs))
                if tuples:
                    labPairs.append((lab, tuples))
        return _DISAttrSequence(self.docPair, labPairs)

class _DISAttrSequence:

    # pairs are (lab, [(annot, keys), ...])
    
    def __init__(self, dis, labAnnotAttrTuples):
        self.docPair = dis
        self.pairs = labAnnotAttrTuples

    # Operations supported: promote, discard, split, map, values.

    def promote(self):
        # For promote, only use the first attr found. AND you return an
        # empty list, since you can't really chain after this.
        pairs = self.pairs
        self.pairs = []
        entryUpdates = []
        for lab, annotPairs in pairs:
            if annotPairs:
                hasSpan = self.docPair._removeAnnots(lab, [annot for (annot, keys) in annotPairs])
                for annot, keys in annotPairs:
                    k = keys[0]
                    targetLabel = annot["attrs"][k]
                    del annot["attrs"][k]
                    annot["touched"] = True
                    # This deals with the hasSpan stuff transparently, although
                    # it's probably a bit verbose.
                    entryUpdates.append(self.docPair._newEntry(targetLabel, hasSpan, [annot]))
        for instr in entryUpdates:
            self.docPair._incorporateEntry(instr["label"], instr)
        return self                    

    # This is discarding the ATTRIBUTE.
    def discard(self):        
        for lab, annotPairs in self.pairs:
            for annot, keys in annotPairs:
                for k in keys:
                    del annot["attrs"][k]
        return self

    def split(self, target_attrs = None):
        if target_attrs is None:
            raise LoadError, "target_attrs is required"
        for lab, annotPairs in self.pairs:
            for annot, keys in annotPairs:
                for attr in keys:
                    v = annot["attrs"].get(attr)
                    if v is not None:
                        # If it's a set or list, map each
                        # value to the target attributes. If
                        # it's a singleton, map it to the first one.
                        # Whatever you run out of first is where you stop.
                        del annot["attrs"][attr]
                        annot["touched"] = True
                        if isinstance(v, AttributeValueSequence):
                            v = list(v)
                            for tv, ta in zip(v, target_attrs):
                                annot["attrs"][ta] = tv
                        elif target_attrs:
                            annot["attrs"][target_attrs[0]] = v                            
        return self

    def discard_annot(self):
        for lab, annotPairs in self.pairs:
            toRemove = [annot for (annot, keys) in annotPairs]
            for a in toRemove:
                a.removalReason = "discard_annot rule"
            self.docPair._removeAnnots(lab, toRemove)
        self.pairs = []
        return self

    def discard_annot_if_null(self):
        pairs = self.pairs
        self.pairs = []
        for lab, annotPairs in self.pairs:
            toKeep = []
            toRemove = []
            for annot, keys in annotPairs:
                removed = False
                for key in keys:
                    if annot["attrs"].get(key) is None:
                        toRemove.append(annot)
                        annot.removalReason = "discard_annot_if_null rule"
                        removed = True
                        break
                if not removed:
                    toKeep.append((annot, keys))
            if toRemove:
                self.docPair._removeAnnots(lab, toRemove)
            if toKeep:
                self.pairs.append((lab, toKeep))
        return self

    def values(self, source = None, source_re = None, excluding = None, excluding_re = None):
        
        okVals = set()
        forbiddenVals = set()

        if source is not None:
            okVals.add(source)
            # We're never going to use these.
            source_re = excluding = excluding_re = None
        else:
            if excluding is not None:
                forbiddenVals.add(excluding)
                excluding_re = None
            if (source_re is not None) and (type(source_re) in (str, unicode)):
                source_re = re.compile("^(" + source_re + ")$")
            if (excluding is None) and (excluding_re is not None) and (type(excluding_re) in (str, unicode)):
                excluding_re = re.compile("^(" + excluding_re + ")$")

        # Now, what do we do? We basically filter this list and return a new one of these.
        # You'll be able to map as a perverse case of attrs(), but that's OK.

        labPairs = []
        for lab, annotPairs in self.pairs:
            tuples = []
            for annot, keys in annotPairs:
                resKeys = []
                for k in keys:
                    # It's possible that this attr no longer exists,
                    # if you're mapping multiple values to some other
                    # attribute and this value has already been mapped.
                    v = annot["attrs"].get(k)
                    # We need to use a very small subset of
                    # values: just int, float, str, unicode, boolean.
                    # Just the ones we can convert to a string.
                    if v is None:
                        continue
                    if type(v) in (int, float, str, unicode, bool):
                        if v is False:
                            v = "no"
                        elif v is True:
                            v = "yes"
                        elif type(v) in (int, float):
                            v = str(v)
                        # Now, evaluate it.
                        if v in okVals:
                            resKeys.append(k)
                        elif v in forbiddenVals:
                            continue
                        elif (excluding_re is not None) and excluding_re.match(v):
                            # Here, we have to deal with the case where there's no
                            # source, as well as the excluding case.
                            forbiddenVals.add(v)                                
                            continue
                        elif (source is None) and ((source_re is None) or source_re.match(v)):
                            # If source was not None, we would have been approved
                            # by okAttrs already. So if source_re is ALSO None,
                            # there's nothing to block approval, so we approve.
                            okVals.add(v)
                            resKeys.append(k)                
                if resKeys:                    
                    tuples.append((annot, resKeys))
            if tuples:
                labPairs.append((lab, tuples))

        return _DISAttrSequence(self.docPair, labPairs)

    def map(self, target = None, target_value=None, target_type = None, target_aggregation = None):
        # In this case, we know that the annots have the keys, because they've already
        # been filtered. We don't always know that.
        if self.pairs:
            allAnnotKeyPairs = []
            for lab, annotPairs in self.pairs:
                allAnnotKeyPairs += annotPairs
            self.docPair._mapAttrs(allAnnotKeyPairs, target, target_value, target_type, target_aggregation)
        return self

class DocumentInstructionSetEngineConvertor(DocumentConvertor):

    def __init__(self, engine):
        self.engine = engine
        DocumentConvertor.__init__(self)

    def inputConvert(self, sourceDoc, targetDoc):
        self.engine._execute(sourceDoc, targetDoc)
