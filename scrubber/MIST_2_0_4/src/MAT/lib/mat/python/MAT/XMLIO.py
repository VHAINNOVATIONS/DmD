# Copyright (C) 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# XML reader/writer.

from MAT.DocumentIO import declareDocumentIO, DocumentFileIO, SaveError
from MAT.Document import LoadError
from MAT.Annotation import AnnotationAttributeType, StringAttributeType, FloatAttributeType, \
     BooleanAttributeType, IntAttributeType, AttributeValueList, AttributeValueSet

import xml.parsers.expat, xml.sax.saxutils, re, base64
import sys
from MAT import json

# We need to know what the annotations are in the task,
# if we're supposed to filter out the "junk" tags and only translate
# the tags for the task.

# There are going to be a couple special things in here
# now. First, there will be the <_mat:atypes> element, which
# optionally declares all the available annotation types and
# their attributes and types. This is important for recording
# spanless annotations and for recording annotations which have
# annotation-valued attributes (and the attribute for that will be
# _mat:id). So <_mat:atypes> looks like this:
# <_mat:atypes><atype name="..." hasSpan="yes|no"><attr name="..." type="string|attribute"/>...</atype></atypes>
# It will have no whitespace at all, so it doesn't count toward
# the offsets, and it should appear, if it appears at all,
# before the first annotation. If I can, when I render, I'll
# put it at the beginning of the document, but if it's
# an overlay, it'll go immediately before the first annotation.

class _ParserState:

    def __init__(self, annotDoc, inputIsOverlay, translateAll):
        self.inputIsOverlay = inputIsOverlay
        self.xmlTranslateAll = translateAll
        if self.xmlTranslateAll:
            # The annotDoc will likely come in with an annotation repository.
            # It's not enough to cut it off from the global repository;
            # we have to convince it that the annotation types it ALREADY
            # has are not closed.
            annotDoc.unlockAtypeRepository()
        self.annotDoc = annotDoc
        # The parser expects BYTES, not unicode characters.
        # The documentation does not make this clear at all.
        self.parser = xml.parsers.expat.ParserCreate("UTF-8")
        self.parser.StartElementHandler = self._startElement
        self.parser.EndElementHandler = self._endElement
        self.parser.CharacterDataHandler = self._handleCdata
        self.parser.CommentHandler = self._handleComment
        self.parser.DefaultHandler = self._handleDefault
        self.stack = []
        self.pos = 0
        self.signalChunks = []
        self._digestingAtypes = False
        self._digestedAtypes = False
        self._curAtype = None
        # The annotation attributes must be postponed, because some of
        # them may be annotation-valued.
        self._annotPairs = []
        self._idMap = {}

    def _addSignalChunk(self, chunk):
        self.signalChunks.append(chunk)
        self.pos += len(chunk)

    # VERY subtle bug. Because inputIsOverlay counts in BYTES,
    # and because I have to pass a byte string to the parser, I
    # can't store the input as a Unicode string; I have to encode
    # it into UTF-8 first.
    
    def parse(self, s):
        # Boy, this is hideous. XML doesn't permit CRLF - each
        # XML processor is obligated to convert them to LF. The
        # only way to block that is to replace \r with the
        # appropriate entity - but then the parser barfs on any
        # &#xD outside the toplevel tag, because it's not actual whitespace.
        # Poo.
        # So the answer is to do the replacement ONLY inside the
        # toplevel tag. That's easy enough.
        if s.find("\r") > -1:
            # Find the first toplevel tag.
            # Exclude ! (comment and doctype) and ? (xmldesc and processing instruction).
            # This will barf if there's nothing in the toplevel tag.
            mStart = re.search("<([^!?][^\s>]*)", s)
            if mStart is not None:
                # Gotta be something in the toplevel tag in order for
                # me to care.
                topStart = mStart.start()
                topEnd = re.search("</" + mStart.group(1) + ">", s).end()
                s = s[:topStart] + s[topStart:topEnd].replace("\r", "&#xD;") + s[topEnd:]
        self.input = s.encode('utf-8')
        self.parser.Parse(self.input, True)
        # Now that we're done parsing, we have to update all the
        # attributes for those which have annotation-valued attributes.
        atypeAttrHash = {}
        for newAnnot, attrDict in self._annotPairs:
            atype = newAnnot.atype
            try:
                attrHash = atypeAttrHash[atype]
            except KeyError:
                attrHash = {}
                for t in atype.attr_list:
                    # Barf.
                    if isinstance(t, AnnotationAttributeType):
                        # The IDs are all strings. We need to look
                        # them up in the _idMap.
                        if t.aggregation == "list":
                            attrHash[t.name] = lambda x: AttributeValueList([self._idMap[v] for v in x.split(",")])
                        elif t.aggregation == "set":
                            attrHash[t.name] = lambda x: AttributeValueSet([self._idMap[v] for v in x.split(",")])
                        else:
                            attrHash[t.name] = lambda x: self._idMap[x]
                    elif isinstance(t, StringAttributeType):
                        if t.aggregation == "set":
                            attrHash[t.name] = lambda x: AttributeValueSet(x.split(","))
                        elif t.aggregation == "list":
                            attrHash[t.name] = lambda x: AttributeValueList(x.split(","))
                        else:
                            attrHash[t.name] = lambda x: x
                    else:
                        if isinstance(t, FloatAttributeType):
                            mapper = float
                        elif isinstance(t, IntAttributeType):
                            mapper = int
                        elif isinstance(t, BooleanAttributeType):
                            mapper = lambda x: x == "yes"
                        if t.aggregation == "set":
                            attrHash[t.name] = lambda x: AttributeValueSet([mapper(v) for v in x.split(",")])
                        elif t.aggregation == "list":
                            attrHash[t.name] = lambda x: AttributeValueList([mapper(v) for v in x.split(",")])
                        else:
                            attrHash[t.name] = mapper
                atypeAttrHash[atype] = attrHash
            for k, v in attrDict.items():
                newAnnot[k] = attrHash[k](v)
        newSignal = "".join(self.signalChunks)
        if self.annotDoc.signal and (self.annotDoc.signal != newSignal):
            raise LoadError, "signal from XML file doesn't match original signal"
        self.annotDoc.signal = newSignal
        if self.inputIsOverlay:
            self.annotDoc.metadata["signal_type"] = "xml"            

    def _startElement(self, eltName, attrDict):
        if eltName == "_mat:atype":
            if not self._digestingAtypes:
                raise LoadError, "found _mat:atype outside _mat:atypes"
            self._digestAtype(attrDict)
            return
        elif eltName == "_mat:attr":
            if not self._digestingAtypes:
                raise LoadError, "found _mat:attr outside _mat:atypes"
            self._digestAttr(attrDict)
            return
        elif eltName == "_mat:atypes":
            self._digestingAtypes = True
            return
        if (not self.xmlTranslateAll) and (not self.annotDoc.findAnnotationType(eltName, create = False)):
            if self.inputIsOverlay:
                # There doesn't appear to be any way of finding the
                # end of the element in the input from the parser bindings, grrr.
                # So we have to look for ">" in the signal.
                tag = self.input[self.parser.CurrentByteIndex:self.input.find(">", self.parser.CurrentByteIndex) + 1]
                self._addSignalChunk(tag)
            return
        # If the atypes were declared, you don't want to check the attributes.
        t = self.annotDoc.findAnnotationType(eltName, create = not self._digestedAtypes)
        if not self._digestedAtypes:
            for key in attrDict.keys():
                if key != "_mat:id":
                    t.ensureAttribute(key)
        if t.hasSpan:
            newAnnot = self.annotDoc.createAnnotation(self.pos, self.pos, t, blockAdd = True)
        else:
            newAnnot = self.annotDoc.createSpanlessAnnotation(t, blockAdd = True)
        id = attrDict.get("_mat:id")
        if id is not None:
            newAnnot.setID(id)
            self._idMap[id] = newAnnot
            del attrDict["_mat:id"]
        self._annotPairs.append((newAnnot, attrDict))
        self.stack[0:0] = [newAnnot]

    def _digestAtype(self, attrDict):
        self._curAtype = self.annotDoc.findAnnotationType(attrDict["name"], hasSpan  = attrDict["hasSpan"] == "yes")

    def _digestAttr(self, attrDict):
        self._curAtype.ensureAttribute(attrDict["name"], aType = attrDict.get("type"),
                                       aggregation = attrDict.get("aggregation"))

    def _endElement(self, eltName):
        if eltName in ("_mat:attr", "_mat:atype"):
            return
        elif eltName == "_mat:atypes":
            self._digestingAtypes = False
            self._digestedAtypes = True
            return
        if (not self.xmlTranslateAll) and (not self.annotDoc.findAnnotationType(eltName, create = False)):
            if self.inputIsOverlay:
                tag = self.input[self.parser.CurrentByteIndex:self.input.find(">", self.parser.CurrentByteIndex) + 1]
                self._addSignalChunk(tag)
            return
        if self.stack[0].atype.lab == eltName:
            if self.stack[0].atype.hasSpan:
                self.stack[0].end = self.pos
            self.annotDoc._addAnnotation(self.stack[0])
            self.stack[0:1] = []
        else:
            raise LoadError, "annotation close doesn't match annotation open"

    # I'm going to do something special with comments: I'm going to
    # dump the document metadata in a comment when I encounter it. I believe
    # the comment can appear after the final tag, so I'll put it at the very
    # end of the file.

    METADATA_PAT = re.compile("^ _mat_metadata_ (.*) $")
    
    def _handleComment(self, data):
        m = self.METADATA_PAT.match(data)
        if m is None:
            if self.inputIsOverlay:
                # Pass through the comment.
                self._addSignalChunk("<!--")
                self._addSignalChunk(data)
                self._addSignalChunk("-->")
        else:
            # We've got the metadata.
            jsonMetadata = base64.b64decode(m.group(1))
            self.annotDoc.metadata = json.loads(jsonMetadata)

    def _handleCdata(self, data):
        if self.inputIsOverlay:
            data = xml.sax.saxutils.escape(data)
        self._addSignalChunk(data)

    # Pass through anything you find if it's a default.
    def _handleDefault(self, data):
        if self.inputIsOverlay:
            self._addSignalChunk(data)

from MAT.Operation import OpArgument, OptionTemplate

class XMLDocumentIO(DocumentFileIO):

    def __init__(self, xml_input_is_overlay = False, xml_translate_all = False, signal_is_xml = False,
                 xml_output_tag_exclusions = None, xml_output_exclude_metadata = False,
                 encoding = None, **kw):
        # Changing the default encoding.
        if encoding is None:
            encoding = "utf-8"
        DocumentFileIO.__init__(self, encoding = encoding, **kw)
        if xml_input_is_overlay:
            signal_is_xml = True
        self.excludeMetadata = xml_output_exclude_metadata
        self.xmlInputIsOverlay = xml_input_is_overlay
        self.tagExclusions = None
        if xml_output_tag_exclusions is not None:
            if type(xml_output_tag_exclusions) is str:
                xml_output_tag_exclusions = xml_output_tag_exclusions.split(",")
                if xml_output_tag_exclusions == [""]:
                    xml_output_tag_exclusions = []
            self.tagExclusions = dict([(t, True) for t in xml_output_tag_exclusions])
        self.signalIsXML = signal_is_xml
        self.xmlTranslateAll = xml_translate_all

    # This must be implemented by the children. s is a Unicode string.
    # annotDoc is an annotated document.
    
    def deserialize(self, s, annotDoc):
        # If there's no global annotation type repository, we want xmlTranslateAll to be True.
        state = _ParserState(annotDoc, self.xmlInputIsOverlay, self.xmlTranslateAll or (not annotDoc.atypeRepository.globalTypeRepository))
        state.parse(s)        
    
    def writeToUnicodeString(self, annotDoc):
        signalIsXML = self.signalIsXML or \
                      (annotDoc.metadata.has_key("signal_type") and
                       annotDoc.metadata["signal_type"] == "xml")
        # Get all the annotations. Let's not care about overlap right now,
        # since overlap will happen if I'm writing everything out, because
        # it'll be nested. So just get the annotations and then
        # sort them, and if we ever get a crossing dependency, we'll
        # have to check otherwise.
        # Split the atypes into spanned and spanless.
        spanned = []
        spanless = []
        # I used to remove the tag exclusions when I collect the
        # indices, but I need to do it earlier in order to figure out
        # if I need a top element or not.        
        annots = []
        spanlessAnnots = []
        for atype in annotDoc.atypeDict.keys():
            if self.tagExclusions and self.tagExclusions.has_key(atype.lab):
                continue
            if atype.hasSpan:
                spanned.append(atype.lab)
            else:
                spanless.append(atype.lab)
        if spanned:
            annots = annotDoc.getAnnotations(atypes = spanned)
        if spanless:
            spanlessAnnots = annotDoc.getAnnotations(atypes = spanless)
        # We now know they can nest. So let's sort them.        
        # Sort them first by earliest start, latest end.
        annots.sort(self._cmpAnnot)
        # Now, I can loop through the annots, and keep a stack,
        # and we know when to pop the stack because of
        # how the indexes work.
        indices = {}
        lastAnnot = None
        for annot in annots:
            if lastAnnot and \
               (((lastAnnot.start < annot.start) and (lastAnnot.end < annot.end)) or \
                ((lastAnnot.start > annot.start) and (lastAnnot.end > annot.end))):
                raise SaveError, "crossing dependencies"
            try:
                indices[annot.start][0].append(annot)
            except KeyError:
                indices[annot.start] = [[annot], []]
            try:
                indices[annot.end][1].append(annot)
            except KeyError:
                indices[annot.end] = [[], [annot]]
        indexList = indices.keys()
        indexList.sort()
        segs = []
        # So we need to add a toplevel XML tag if we don't already have one, and if
        # we're not adding our own info.
        # The signal is not XML, and
        # There are no spanless annotations, or
        # The maximal annotation starts after the beginning, or
        # the maximal annotation ends before the end, or
        # there are spanless annots, which will be inserted as zero-length
        # annots before the first spanned annotation, or
        # we add metadata, which will insert the annotation types
        # in a similar position.
        addTop = (not signalIsXML) and \
                 ((not annots) or \
                  (annots[0].start > 0) or \
                  (annots[0].end < len(annotDoc.signal)) or \
                  spanlessAnnots or \
                  (not self.excludeMetadata))
        if addTop:
            segs.append("<__top>")
        pos = 0
        atypesInserted = False
        for i in indexList:
            if pos < i:
                seg = annotDoc.signal[pos:i]
                if not signalIsXML:
                    seg = xml.sax.saxutils.escape(seg)
                segs.append(seg)
                pos = i
            [starts, ends] = indices[i]
            # Reverse the ends.
            ends.reverse()
            for endAnnot in ends:
                segs.append("</" + endAnnot.atype.lab + ">")
            for startAnnot in starts:
                if not atypesInserted:
                    if not self.excludeMetadata:
                        segs.append(self._formatAtypes(annotDoc))
                    atypesInserted = True
                    if spanlessAnnots:
                        for sAnnot in spanlessAnnots:
                            segs.append(self._formatAnnot(sAnnot, spanless = True))
                segs.append(self._formatAnnot(startAnnot))
        if pos < len(annotDoc.signal):
            seg = annotDoc.signal[pos:]
            if not signalIsXML:
                seg = xml.sax.saxutils.escape(seg)
            segs.append(seg)
        if addTop:
            segs.append("</__top>")
        if not self.excludeMetadata:
            segs.append("<!-- _mat_metadata_ "+ base64.b64encode(json.dumps(annotDoc.metadata)) + " -->")
        return "".join(segs)

    def _cmpAnnot(self, ann1, ann2):
        return cmp(ann1.start, ann2.start) or -cmp(ann1.end, ann2.end)

    def _formatAtypes(self, annotDoc):
        segs = ["<_mat:atypes>"]
        for atype in annotDoc.atypeDict.keys():
            segs.append("<_mat:atype name='%s' hasSpan='%s'>" %
                        (atype.lab, (atype.hasSpan and "yes") or "no"))
            for attr in atype.attr_list:
                segs.append("<_mat:attr name='%s' type='%s' aggregation='%s'/>" % (attr.name, attr._typename_, attr.aggregation or "none"))
            segs.append("</_mat:atype>")
        segs.append("</_mat:atypes>")
        return "".join(segs)

    def _formatAnnot(self, annot, spanless = False):
        elts = ["<", annot.atype.lab]
        if annot.attrs:
            for attr, val in zip(annot.atype.attr_list, annot.attrs):
                if val is not None:
                    # Handle annotations specially.
                    if attr._typename_ == "annotation":
                        if attr.aggregation:
                            v = ",".join([str(a.id) for a in val])
                        else:
                            v = str(val.id)
                    else:
                        v = attr.toStringNonNull(val)
                    elts.append(" " + attr.name + "="+ xml.sax.saxutils.quoteattr(v))
        if annot.id is not None:
            elts.append(" _mat:id=" + xml.sax.saxutils.quoteattr(annot.id))
        if spanless:
            elts.append("/>")
        else:
            elts.append(">")
        return "".join(elts)

    # Best to use the OpArgument infrastructure, so we can extract
    # arguments cleanly from CGI and cmdline.

    inputArgs = OptionTemplate([OpArgument("xml_input_is_overlay",
                                           help = "If specified, the input XML will be treated as a mix of task-relevant annotations and underlying XML, and the extracted signal will be a well-formed XML file"),
                                OpArgument("xml_translate_all",
                                           help = "If specified, all tags will be converted, whether or not they're found in whatever task is specified")],
                               heading = "Options for XML input")
                               
    outputArgs = OptionTemplate([OpArgument("signal_is_xml",
                                            help = "If specified, the underlying signal will be treated as a well-formed XML file when the output file is rendered. If the input file type is also 'xml-inline', use the --xml_input_is_overlay flag to control this setting instead."),
                                 OpArgument("xml_output_tag_exclusions",
                                            help = "A comma-delimited list of annotation labels to exclude from the XML output",
                                            hasArg = True),
                                 OpArgument("xml_output_exclude_metadata",
                                            help = "Normally, the XML writer saves the document metadata inside an XML comment, so it can be read back in by the XML reader. This flag causes the metadata not to be written.")],
                                heading = "Options for XML output")

declareDocumentIO("xml-inline", XMLDocumentIO, True, True)

#
# And now, the "fake" version, for when somebody just randomly inserted SGML-ish tags.
#

# ONLY a reader.

class FakeXMLIO(DocumentFileIO):

    def writeToUnicodeString(self, annotDoc):
        raise NotImplementedError

    # In fake xml IO, it's just SGML-ish tags.
    
    def deserialize(self, s, annotDoc):
        signalStrings = []
        startI = 0
        contentLen = 0
        for m in self.TAG_LOCATOR.finditer(s):            
            startTag, content, endTag = m.groups()
            # Let's do all the bookkeeping first.
            prefix = s[startI:m.start()]
            contentLen += len(prefix)
            signalStrings.append(prefix)
            annotStart = contentLen
            signalStrings.append(content)
            contentLen += len(content)
            annotEnd = contentLen
            startI = m.end()
            # Now, let's take the startTag eapart.
            labToks = startTag.split(None, 1)
            if labToks[0] != endTag:
                raise LoadError, ("mismatched start and end tags (%s vs. %s) at %d" % (labToks[0], endTag, m.start()))
            t = annotDoc.findAnnotationType(endTag, create = True)
            attrs = {}
            if len(labToks) > 1:
                # There are attributes. Grab a token (no whitespace, no =), then
                # look for an =, then find the following value.
                attrStr = labToks[1]
                while attrStr:
                    m = self.ATTR_NAME_LOCATOR.match(attrStr)
                    if m is None:
                        raise LoadError, ("ill-formed attribute string '%s'" % labToks[1])
                    attr = m.group(1)
                    t.ensureAttribute(attr)
                    attrStr = attrStr[m.end():]
                    # Now, we need a value.
                    m = self.ATTR_VALUE_LOCATOR.match(attrStr)
                    if m is None:
                        raise LoadError, ("ill-formed attribute string '%s'" % labToks[1])
                    val = m.group(2)
                    # Since this sucks up trailing whitespace, it should
                    # terminate the string when we reach the end of it.
                    attrStr = attrStr[m.end():]
                    attrs[attr] = val
            # OK, now we add the annotation.
            annotDoc.createAnnotation(annotStart, annotEnd, t, attrs)
        signalStrings.append(s[startI:])
        annotDoc.signal = "".join(signalStrings)            

    TAG_LOCATOR = re.compile("\<([^>]+)\>", re.S)
    ATTR_NAME_LOCATOR = re.compile("^\s*([^\s=]+)\s*=\s*")
    # The escape for the double quote isn't strictly necessary,
    # but it works better with the Python Emacs mode.
    ATTR_VALUE_LOCATOR = re.compile("""^([\"'])(.*?)\\1\s*""")

    # We can't quite do this the way we did the fake XML IO reader, because
    # we have (a) null annotations and (b) nested annotations. So we need
    # to look for the tags, and keep gathering input.

    # Because this is pseudo-XML, there may be <> in the signal. So if
    # we find a tag which we can't parse, assume it's signal.

    def _parseTag(self, startTag):
        labToks = startTag.split(None, 1)
        attrs = {}
        if len(labToks) > 1:
            # There are attributes. Grab a token (no whitespace, no =), then
            # look for an =, then find the following value.
            attrStr = labToks[1]
            while attrStr:
                m = self.ATTR_NAME_LOCATOR.match(attrStr)
                if m is None:
                    # Attribute string is ill-formed.
                    return None, None
                attr = m.group(1)
                attrStr = attrStr[m.end():]
                # Now, we need a value.
                m = self.ATTR_VALUE_LOCATOR.match(attrStr)
                if m is None:
                    # Attribute string is ill-formed.
                    return None, None
                val = m.group(2)
                # Since this sucks up trailing whitespace, it should
                # terminate the string when we reach the end of it.
                attrStr = attrStr[m.end():]
                attrs[attr] = val
        return labToks[0], attrs

    # Toplevel.
    def deserialize(self, s, annotDoc):

        annotations = []
        tagStack = []

        signalStrings = []
        startI = 0
        contentLen = 0

        NULL, OPEN, CLOSE = 0, 1, 2

        while True:
            m = self.TAG_LOCATOR.search(s, startI)

            if m is None:
                signalStrings.append(s[startI:])
                break

            tagContent = m.group(1)

            # If it starts with a /, it's an end tag.
            # if it ends with a /, it's a null tag.
            if tagContent[-1] == "/":
                tagLiteral = tagContent[:-1]
                tagStatus = NULL
            elif  tagContent[0] == "/":
                tagLiteral = tagContent[1:]
                tagStatus = CLOSE
            else:
                tagLiteral = tagContent
                tagStatus = OPEN

            if tagStatus in (NULL, OPEN):
                label, attrs = self._parseTag(tagLiteral)
                if label is None:
                    # Probably actually signal instead. Skip it. Well, don't
                    # skip the WHOLE thing; the pattern may have captured
                    # a real tag too.
                    print >> sys.stderr, "Found bogus tag match '%s'; treating first character as text and trying again." % s[m.start():m.end()].encode('ascii', 'replace')
                    signalStrings.append(s[startI:m.start() + 1])
                    contentLen += ((m.start() + 1) - startI)
                    startI = m.start() + 1
                    continue

            # So now, we know it's a non-bogus tag.

            prefix = s[startI:m.start()]
            contentLen += len(prefix)
            signalStrings.append(prefix)
            annotLoc = contentLen
            startI = m.end()

            if tagStatus is NULL:
                annotations.append([label, attrs, annotLoc, annotLoc])
            elif tagStatus is CLOSE:
                # Gotta match what's on the top of the stack.
                tagContent = tagContent[1:]
                if not tagStack:
                    raise IOError, "no start tag for end tag"
                elif tagStack[-1][0] != tagContent:
                    raise IOError, "mismatch start and end tags (%s vs %s)" % (tagStack[-1][0], tagContent)
                else:
                    [label, attrs, startIdx] = tagStack[-1]
                    tagStack[-1:] = []
                    annotations.append([label, attrs, startIdx, annotLoc])
            else:
                label, attrs = self._parseTag(tagContent)
                tagStack.append([label, attrs, annotLoc])

        # OK, now we add the annotations.
        for t, attrs, annotStart, annotEnd in annotations:
            annotDoc.createAnnotation(annotStart, annotEnd, t, attrs)
        annotDoc.signal = "".join(signalStrings)

declareDocumentIO('fake-xml-inline', FakeXMLIO, True, False)
