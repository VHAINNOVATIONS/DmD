# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import sys

import Command

class OverlapError(Exception):
    pass

from MAT.Annotation import Annotation, DocumentAnnotationTypeRepository, SpanlessAnnotation, \
     AnnotationCore, AttributeValueSequence, AnnotationAttributeType

# This really ought to be in DocumentIO.py after the
# refactor, but there are too many odd dependencies.

class LoadError(Exception):
    pass

class DumpError(Exception):
    pass

class DocumentError(Exception):
    pass

# The metadata is only used when reading the document in
# from a file. Otherwise, Python will never see the metadata.

# Everything that refers to AMS should be here, just in case we
# need to factor it out.

class AnnotatedDoc:

    def __init__(self, signal = None, globalTypeRepository = None):

        # There are too many levels here, but I've made the simplest
        # modification to try to get the old global annotation type
        # records to work here - it can't be global because we have
        # potential threading issues with Web services.
        self.atypeRepository = DocumentAnnotationTypeRepository(self, globalTypeRepository = globalTypeRepository)
        self.atypeDict = {}
        self.anameDict = self.atypeRepository
        self.signal = ""
        self.metadata = {}

        if signal is not None:
            if type(signal) is not type(u''):
                raise LoadError, "signal must be Unicode"
            self.signal = signal

    def truncate(self):
        self.atypeDict = {}
        self.anameDict.clear()

    # We have to unlock the repository, AND the atypes
    # which have already been used.
    
    def unlockAtypeRepository(self):
        self.atypeRepository.forceUnlock()
        for k, v in self.anameDict.items():
            if v.repository is not self.atypeRepository:
                # Copy (which will create an unlocked local copy) and update.
                newV = v.copy(repository = self.atypeRepository)
                if self.atypeDict.has_key(v):
                    self.atypeDict[newV] = self.atypeDict[v]
                    del self.atypeDict[v]
                self.anameDict[k] = newV

    # There's really no reason to have another level of indirection
    # here. But we have it.
    
    def findAnnotationType(self, tname, hasSpan = True, create = True):
        if self.anameDict.has_key(tname):
            return self.anameDict[tname]
        else:
            atype = self.atypeRepository.findAnnotationType(tname, hasSpan = hasSpan, create = create)
            if atype is not None:
                self.atypeDict[atype] = []
            return atype

    # blockAdd is backward compatibility. There are some cases where
    # I suspect that I might not want to add when I create. All the cases
    # in the code where they happen together have been converted.
    
    def createAnnotation(self, start, end, type, attrs = None, blockAdd = False):
        a = Annotation(self, start, end, type, attrs)
        if not blockAdd:
            self._addAnnotation(a)
        return a

    # blockAdd is backward compatibility.
    def createSpanlessAnnotation(self, type, attrs = None, blockAdd = False):
        a = SpanlessAnnotation(self, type, attrs)
        if not blockAdd:
            self._addAnnotation(a)
        return a

    # now only to be used in special cases.
    
    def _addAnnotation(self, a):
        if self.atypeDict.has_key(a.atype):
            self.atypeDict[a.atype].append(a)   
        else:
            self.atypeDict[a.atype] = [a]

    # If someone points to it, raise an error.
    
    def removeAnnotation(self, a):
        if self.atypeDict.has_key(a.atype):
            # Try this first. This can fail if someone points to it.
            self.atypeRepository.removeAnnotationIDs([a])
            try:
                self.atypeDict[a.atype].remove(a)
            except ValueError:
                pass

    # All the IDs must not be pointed to by anyone outside
    # the group.
    
    def removeAnnotationGroup(self, aGroup, forceDetach = False):
        self.atypeRepository.removeAnnotationIDs(aGroup, forceDetach = forceDetach)
        for a in aGroup:
            if self.atypeDict.has_key(a.atype):
                try:
                    self.atypeDict[a.atype].remove(a)
                except ValueError:
                    pass

    # At one point, I had a pure copy, but it doesn't make
    # any sense in the context of the system. So we now have
    # an import.
    
    def importAnnotation(self, a):
        # Copying from another document. We have to use strings
        # and a dictionary instead of the actual atype and a list of attrs.
        # Slower, but correct.
        return self._importAnnotations({a.atype: [a]})
        
    # This is used to get around the annotation pointer issue.
    # Namely, you can't import them individually if they point to each other -
    # because you can't import a group of annots which points to an annot
    # that isn't mentioned.
    
    def importAnnotationGroup(self, aGroup):
        # First, sort by atype. Then, collapse with copyAnnotations.
        atypeMap = {}
        for a in aGroup:
            try:
                atypeMap[a.atype].append(a)
            except KeyError:
                atypeMap[a.atype] = [a]
        return self._importAnnotations(atypeMap)

    def importAnnotations(self, sourceDocument, atypes = None, offset = 0):
        if atypes is None:
            atypeMap = sourceDocument.atypeDict
        else:
            atypeMap = {}
            for a in atypes:
                try:
                    atypeMap[sourceDocument.anameDict[a]] = sourceDocument.atypeDict[sourceDocument.anameDict[a]]
                except KeyError:
                    # There may not be any of them.
                    pass
        return self._importAnnotations(atypeMap, offset = offset)
        
    # This list is UNORDERED.
    
    def recordStep(self, phaseName):
        if not self.metadata.has_key("phasesDone"):
            self.metadata["phasesDone"] = [phaseName]
        elif phaseName not in self.metadata["phasesDone"]:
            self.metadata["phasesDone"].append(phaseName)

    # If ordered is True, can't do spanless.
    # I've been bitten once too often by the bug where I'm
    # looping through the result of getAnnotations and removing
    # them, but the list I'm looping through is the list I'm removing
    # things from. So I wasn't copying by default, but I'm
    # sick of this bug.
    
    def getAnnotations(self, atypes = None, strict = False, ordered = False,
                       spannedOnly = False, spanlessOnly = False):
        if spannedOnly and spanlessOnly:
            raise DocumentError, "Can restrict to either spanned or spanless, not both"
        if ordered or strict:
            if spanlessOnly:
                raise DocumentError, "Can't restrict to spanless if ordered or strict"
            spannedOnly = True
        # Order them by start. If the end of one is
        # after the start of the next and we've asked for strict,
        # raise OverlapError.
        # Let atypes is None fall all the way through, for efficiency.
        if atypes is not None:
            # Remember, the atype may not exist.
            atypes = [self.anameDict[a] for a in atypes if self.anameDict.has_key(a)]
        if spannedOnly or spanlessOnly:
            if atypes is None:
                if spannedOnly:
                    atypes = [atype for atype in self.anameDict.values() if atype.hasSpan]
                else:
                    atypes = [atype for atype in self.anameDict.values() if not atype.hasSpan]
            elif spannedOnly:
                atypes = [atype for atype in atypes if atype.hasSpan]
            else:
                atypes = [atype for atype in atypes if not atype.hasSpan]
        if atypes is None:
            annotList = self.atypeDict.values()
        else:
            annotList = []
            for a in atypes:
                try:
                    annotList.append(self.atypeDict[a])
                except KeyError:
                    # There may not be any of them.
                    pass
        if len(annotList) == 1:
            allAnnots = annotList[0][:]
        elif annotList:
            allAnnots = reduce(lambda x, y: x + y, annotList)
        else:
            allAnnots = []
        # We will have already checked for spanless.
        if ordered:
            allAnnots.sort(cmp, lambda x: x.start)
        if strict:
            lastEnd = None
            for a in allAnnots:
                if (lastEnd is not None) and \
                   (a.start < lastEnd):
                    raise OverlapError
                lastEnd = a.end
        return allAnnots

    def getAnnotationByID(self, aID):
        return self.atypeRepository.getAnnotationByID(aID)

    # This returns a list of labels.
    def getAnnotationTypes(self):
        return self.atypeRepository.keys()

    # This will only return spanned annotations.
    def orderAnnotations(self, atypes = None, strict = False):
        return self.getAnnotations(atypes = atypes, strict = strict, ordered = True)

    def hasAnnotations(self, atypes):
        for a in atypes:
            if self.anameDict.has_key(a):
                if self.atypeDict.get(self.anameDict[a]):
                    return True
        return False

    # Copying the document should import the global type repository.
    def copy(self, removeAnnotationTypes = None, signalInterval = None):
        # First, copy the signal.
        if signalInterval:
            newStart, newEnd = signalInterval
            newD = AnnotatedDoc(self.signal[newStart:newEnd])
        else:
            newStart = 0
            newD = AnnotatedDoc(self.signal)
        # Next, copy the metadata. This has to be a RECURSIVE copy.
        newD.metadata = self._recursiveCopy(self.metadata)
        # Now, import the annotation types.
        newAtypes = newD.atypeRepository.importAnnotationTypes(self, removeAnnotationTypes = removeAnnotationTypes)
        # Now, the annotations. If there's a signal interval,
        # we need to exclude all annotations which are outside the
        # interval. Ditto any annotations in removeAnnotationTypes.
        # And since we know we've copied the atypes, we can use the actual
        # lists of attributes.
        # If we're filtering annotations, or grabbing a signal interval, we have to 
        # ensure that the annotations which are going to be copied
        # don't refer to annotations outside the set. Otherwise, we don't
        # need to check. So, collect all the old ones first.
        # Also, if we're taking an interval, none of the annotations
        # to be copied can be spanless.
        annotMap = {}
        justCreated = set(newAtypes)       
        for atype in newAtypes:
            if signalInterval and (not atype.hasSpan):
                raise DocumentError, "Can't copy with a filtered signal and spanless annotations"
            # These are the already filtered atypes.
            if self.anameDict.has_key(atype.lab) and \
               self.atypeDict.has_key(self.anameDict[atype.lab]):
                oldAtype = self.anameDict[atype.lab]
                # If there are any annotations to copy:
                if signalInterval is None:
                    annotMap[oldAtype] = self.atypeDict[oldAtype]
                else:
                    annotMap[oldAtype] = [a for a in self.atypeDict[self.anameDict[atype.lab]]
                                          if (a.start >= newStart) and (a.end <= newEnd)]
        newD._importAnnotations(annotMap, justCreated = justCreated,
                                failOnReferenceCheck = removeAnnotationTypes or signalInterval,
                                copyIDs = True,
                                offset = -newStart)
        return newD

    # I'm going to have this return a mapping from the old annotations to
    # the new. I'm going to need this when I create the comparison documents.
    
    def _importAnnotations(self, annotMap, justCreated = None,
                           failOnReferenceCheck = True, offset = 0,
                           copyIDs = False):
        # See what annotations are being pointed to.
        referencedAnnots = set()
        allAnnots = []
        for aGroup in annotMap.values():
            allAnnots += aGroup
            for a in aGroup:
                for attr in a.attrs:
                    if isinstance(attr, AnnotationCore):
                        referencedAnnots.add(attr)
                    elif isinstance(attr, AttributeValueSequence) and attr.ofDocAndAttribute and \
                         isinstance(attr.ofDocAndAttribute[1], AnnotationAttributeType):
                        for subval in attr:
                            referencedAnnots.add(subval)
        # If there are referenced annotations which aren't being copied, barf.
        if failOnReferenceCheck and referencedAnnots and (not set(allAnnots).issuperset(referencedAnnots)):
            raise DocumentError, "Can't copy annotations if they point to annotations which aren't included"

        resultMap = {}

        # Now, for each atype, find it in the new doc, and if it's either been just created
        # or you can't find it, you can use the sequence method. Otherwise, you need the
        # dictionary method. If there are reference annotations, use the dMap; otherwise, no.
        # If you use the dMap, you'll have to record which method to copy the attrs with.
        if referencedAnnots:
            dMap = {}
        for sourceAtype, sourceAnnots in annotMap.items():
            useSequenceMethod = True
            atype = self.atypeRepository.findAnnotationType(sourceAtype.lab, hasSpan = sourceAtype.hasSpan, create = False)
            if atype is None:
                atype = self.atypeRepository.importAnnotationType(sourceAtype)
            elif justCreated and (atype in justCreated):
                pass
            else:
                for t in sourceAtype.attr_list:
                    atype.importAttribute(t)
                useSequenceMethod = False
            # So now, we have the new atype.
            # copyID is True when we're copying documents, not when we're
            # importing annotations elsewhere. I'm PRETTY sure that the default
            # should be False.
            # I actually can't afford to fail to copy any attributes - later, when I
            # copy in the annotation-valued attributes, I'll need to already have
            # the elements which allow the label restrictions to be satisfied. So
            # I only want to postpone the annotation-valued attributes. And in that
            # case, we can't use the sequence method.
            if referencedAnnots:
                targetAnnots = []
                for a in sourceAnnots:
                    annotAttrs = {}
                    foundAnnotAttrs = False
                    allAttrs = []
                    for attr, av in zip(sourceAtype.attr_list, a.attrs):
                        if attr._typename_ == "annotation":
                            # Postpone.
                            if av is not None:
                                annotAttrs[attr.name] = av
                                foundAnnotAttrs = True
                            # Placeholder.
                            allAttrs.append(None)
                        elif isinstance(av, AttributeValueSequence):
                            allAttrs.append(av.copy())
                        else:
                            allAttrs.append(av)
                    targetAnnot = a.copy(doc = self, offset = offset, copyID = copyIDs,
                                         atype = atype,
                                         attrs = allAttrs)
                    # We only need to postpone those things which point to
                    # other annotations.
                    if foundAnnotAttrs:
                        dMap[a] = (targetAnnot, annotAttrs)
                    targetAnnots.append(targetAnnot)
            elif useSequenceMethod:
                targetAnnots = [a.copy(doc = self, offset = offset,
                                       atype = atype, copyID = copyIDs)
                                for a in sourceAnnots]
            else:
                # Special case: the annotation values, if they're sequences, CANNOT BE REUSED.
                # There are no referenced annotations in the set of annotations we're copying.
                targetAnnots = [a.copy(doc = self, offset = offset, copyID = copyIDs,
                                       atype = atype,
                                       attrs = dict(zip([attr.name for attr in sourceAtype.attr_list],
                                                        [((isinstance(av, AttributeValueSequence) and av.copy()) or av)
                                                         for av in a.attrs])))
                                for a in sourceAnnots]
            # Now, add the target annotations to the new document.
            try:
                self.atypeDict[atype] += targetAnnots
            except KeyError:
                self.atypeDict[atype] = targetAnnots
            resultMap.update(zip(sourceAnnots, targetAnnots))
        # We've postponed copying the annotation attributes, because we have referenced
        # annotations and we need to use the newly created correspondents.
        # Don't forget to copy the attribute value sequences, and if
        # it happens to be an annotation attribute value, look up the
        # correspondents.
        if referencedAnnots:
            for sourceA, (targetA, annotAttrDict) in dMap.items():
                for attr, a in annotAttrDict.items():
                    # This checks the label restrictions, even though it's
                    # not necessary, but I can't bypass that.
                    if isinstance(a, AnnotationCore):
                        targetA[attr] = resultMap[a]
                    else:
                        targetA[attr] = a.__class__([resultMap[subA] for subA in a])
        return resultMap
    
    def _recursiveCopy(self, d):
        if type(d) is dict:
            return dict([(k, self._recursiveCopy(v)) for k, v in d.items()])
        elif type(d) is list:
            return [self._recursiveCopy(v) for v in d]
        else:
            return d            
        
    # This list is UNORDERED.
    
    def setStepsDone(self, steps):
        self.metadata["phasesDone"] = steps

    def stepUndone(self, step):
        try:
            self.metadata["phasesDone"].remove(step)
        except ValueError:
            pass

    def getStepsDone(self):
        try:
            return self.metadata["phasesDone"]
        except KeyError:
            return []

    def removeAnnotations(self, atypes = None):
        if atypes is None:
            self.atypeDict = {}
            self.anameDict.clear()
        else:
            aGroup = []
            for atype in atypes:
                try:
                    atypeObj = self.anameDict[atype]
                    annots = self.atypeDict[atypeObj]
                    aGroup += annots
                except KeyError:
                    pass
            # Remove the annotation IDs as a bundle, to make
            # sure they're not externally referenced.
            self.atypeRepository.removeAnnotationIDs(aGroup)
            for atype in atypes:
                try:
                    del self.atypeDict[self.anameDict[atype]]
                except KeyError:
                    pass
    
    # Cleaning up the document.

    def adjustTagsToTokens(self, task, doPrompt = False, doReport = False):

        # Sometimes, Lord help us, the tokens and tags get out of alignment,
        # and this can be a very bad thing. Perhaps we're importing tags from
        # another tagger, and using this tokenizer, or perhaps something went
        # wrong with hand tagging, or (in the de-identification case) the tokenizer
        # does unexpected things on resynthesized text.

        # This code was taken directly from the de-identification task.

        # I have to make sure that (believe it
        # or not) no tags mismatch the annotation boundaries. If they do,
        # I need to expand the annotation boundaries to match the nearest
        # token. This is a messy computation.

        # Copy it, because in some rare cases I'm going to have to
        # delete annotations.
        # I really want there to be a task object, because it's the task that's the
        # authority about the annotation types. If a document, for instance, was processed
        # by a task which didn't have the token annotation listed, and then you add the
        # token annotation, bad things will happen.
        contentAnnots = self.orderAnnotations(task.getAnnotationTypesByCategory('content'))[:]
        lexAnnots = self.orderAnnotations(task.getAnnotationTypesByCategory('token'))

        lexAnnotIndex = 0
        maxLex = len(lexAnnots)

        # And to complicate matters, it's possible that the adjustment
        # might lead to overlapping annotations, if entities abut each
        # other. That can't happen.

        # And a final complexity. Not all the text is covered by tokens, and
        # sometimes, if a replacer replaces a newline, a newline is added
        # at the end of the replacement. So we have to be aware that
        # there may be untokenized whitespace that we can TRIM, rather
        # than always assuming a boundary. has to be moved to SPREAD.

        # The old algorithm was overly complex and missed some edge conditions.
        # So:
        # (1) Digest all the tokens which are completely before the annotation.
        # (2) Check left edge. Adjust if necessary.
        # (3) Digest tokens entirely within the annotation.
        # Remember, it can be the same lex as the left boundary.
        # (4) Check right edge. Adjust if necessary.
        # This algorithm only works if we have no overlapping annotations.
        # Actually, the way to adjust for overlapping annots is to
        # keep track of the right edges we expand, and if a left
        # edge needs to be moved, only expand if it doesn't cross a
        # newly-created right edge.

        # Don't forget about boundary conditions: what if the current annotation
        # starts or ends after the last token?

        annotationsToDelete = []

        # Let's do this in a couple stages, since I want to use this code to
        # diagnose as well as to repair. So first, we take all the lexes
        # and we generate start and end tables.

        tStartMap = {}
        tEndMap = {}
        j = 0
        for t in lexAnnots:
            tStartMap[t.start] = j
            tEndMap[t.end] = j
            j += 1

        badAnnots = []

        # So we should check to repair, if we're prompting, and we should
        # report, if we're reporting.

        def presentPrompt(s):
            while True:
                w = raw_input(s)
                if w in ['y', 'Y']:
                    return True
                elif w in ['n', 'N']:
                    return False
                else:
                    print "Please answer 'y' or 'n'."
        
        for cIndex in range(len(contentAnnots)):
            cAnnot = contentAnnots[cIndex]
            if not (tStartMap.has_key(cAnnot.start) and tEndMap.has_key(cAnnot.end)):
                if (not doPrompt) or \
                   presentPrompt("Annotation %s from %d to %d does not align with token boundaries. Repair? (y/n) " % (cAnnot.atype.lab, cAnnot.start, cAnnot.end)):
                    badAnnots.append(cAnnot)
                if doReport:
                    print "Annotation is %s from %d to %d." % (cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                    annString = self.signal[cAnnot.start:cAnnot.end]
                    import string
                    chars = []
                    for c in annString:
                        if c in string.uppercase:
                            chars.append('A')
                        elif c in string.lowercase:
                            chars.append('a')
                        elif c in string.digits:
                            chars.append('0')
                        else:
                            chars.append(c)
                    print "Text pattern is '%s'." % "".join(chars)
                    if cIndex > 0:
                        prevString = self.signal[contentAnnots[cIndex-1].end:cAnnot.start]
                    else:
                        prevString = self.signal[:cAnnot.start]
                    print "Non-annotated text on left side is: '%s' (%d characters, %d - %d)" % (prevString, len(prevString), cAnnot.start - len(prevString), cAnnot.start)
                    if cIndex < (len(contentAnnots) - 1):
                        nextString = self.signal[cAnnot.end:contentAnnots[cIndex+1].start]
                    else:
                        nextString = self.signal[cAnnot.end:]
                    print "Non-annotated text on right side is: '%s' (%d characters, %d - %d)" % (nextString, len(nextString), cAnnot.end, cAnnot.end + len(nextString))
                    print "Tokens in neighborhood are:" 
                    iStart = cAnnot.start - 30
                    if iStart < 0:
                        iStart = 0
                    iEnd = cAnnot.end + 30
                    if iEnd > len(self.signal):
                        iEnd = len(self.signal)
                    while iStart < iEnd:
                        if tStartMap.has_key(iStart):
                            lex = lexAnnots[tStartMap[iStart]]
                            print ("%d - %d" % (lex.start, lex.end)),
                            import sys
                            sys.stdout.flush()
                        iStart += 1
                    print

        # Now, we have all the ones we should repair.
        # Note that we want to avoid creating overlaps where there were
        # none previously, but we shouldn't avoid overlaps entirely.
        # What this means is that if I expand a right edge, I should
        # make sure that any left edge that I expand doesn't cross
        # any new right edge. If it does, I want to shrink rather than grow.

        usedRightEdgeToks = set([])

        for cAnnot in badAnnots:

            # (1) digest all tokens which are completely before the annotation.
            # The annotations are in start index order, so that should work.
                        
            while True:
                if lexAnnotIndex >= maxLex:
                    # Oops, we ran out of lexes before we reached
                    # the annotation. Remove it.
                    if doReport:
                        print "Ran out of lexes before %s from %d to %d" % (cAnnot, cAnnot.start, cAnnot.end)
                    annotationsToDelete.append(cAnnot)
                    break
                curLex = lexAnnots[lexAnnotIndex]
                if curLex.end > cAnnot.start:
                    # Encroaching.
                    break
                lexAnnotIndex += 1

            # OK, now we've advanced lexAnnotIndex up to where we
            # need it.

            localIndex = lexAnnotIndex

            # (2) Check left edge. Adjust if necessary.
            # If the annotation precedes all tokens, we have to be careful
            # not to just shift it onto the existing token.

            if curLex.start >= cAnnot.end:
                # Delete the annotation.
                if doReport:
                    print "First available lex (%d - %d) >= end of %s from %d to %d; deleting" % \
                          (curLex.start, curLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                annotationsToDelete.append(cAnnot)
                continue
            elif curLex.start < cAnnot.start:
                # Lex spans annotation start. Adjust left if it's not less than a newly created right
                # edge, otherwise adjust right.
                foundNewlyCreated = False
                if curLex in usedRightEdgeToks:
                    if localIndex + 1 >= maxLex:
                        if doReport:
                            print "Ran out of lexes before %s from %d to %d" % (cAnnot, cAnnot.start, cAnnot.end)
                        annotationsToDelete.append(cAnnot)
                    else:
                        nextLex = lexAnnots[lexAnnotIndex + 1]
                        if doReport:
                            print "First available lex (%d - %d) < start of %s from %d to %d; shrinking annot start to avoid previous use of left token" % \
                                  (nextLex.start, nextLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                        cAnnot.start = nextLex.start
                else:
                    if doReport:
                        print "First available lex (%d - %d) < start of %s from %d to %d; expanding annot start" % \
                              (curLex.start, curLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                    cAnnot.start = curLex.start
            elif curLex.start > cAnnot.start:
                # Gap between tokens, or first token starts
                # after first annotation. Adjust right.
                if doReport:
                    print "First available lex (%d - %d) > start of %s from %d to %d; shrinking annot start" % \
                          (curLex.start, curLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                cAnnot.start = curLex.start

            # (3) Digest tokens entirely within the annotation.
            # Remember, it can be the same lex as the left boundary.
            # We transition to the local index now.
            
            while True:
                if localIndex >= maxLex:
                    # Oops, we ran out of lexes before we
                    # reached the end of the annotation.
                    # Use the last lex.
                    cAnnot.end = curLex.end
                    break
                curLex = lexAnnots[localIndex]
                if curLex.end >= cAnnot.end:
                    # Encroaching.
                    break
                localIndex += 1

            # (4) Check right edge. Adjust if necessary.
            # Worry about the case where the next annotation
            # starts immediately afterward. Probably, the way
            # to do that is to advance the lexAnnotIndex because
            # we've "consumed" the token.

            if curLex.start >= cAnnot.end:
                # It's possible that the next tokens
                # starts entirely after the current annotation.
                # Then we need to shrink the current annotation
                # to the end of the previous token.
                if localIndex > 0:
                    if doReport:
                        print "Last available lex start (%d - %d) > end of %s from %d to %d; shrinking end" % \
                              (curLex.start, curLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                    cAnnot.end = lexAnnots[localIndex - 1].end
                else:
                    # This is the first token. How we got an annotation
                    # which ends after the first token is a mystery,
                    # but out it goes.
                    if doReport:
                        print "Last available lex start (%d - %d) > end of %s from %d to %d, but no preceding lex; deleting" % \
                              (curLex.start, curLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                    annotationsToDelete.append(cAnnot)
            elif curLex.end > cAnnot.end:
                # If there had been a token which ended
                # exactly on the annotation boundary, we would
                # have seen it. So we expand the annotation.
                if doReport:
                    print "Last available lex end (%d - %d) > end of %s from %d to %d; expanding end" % \
                          (curLex.start, curLex.end, cAnnot.atype.lab, cAnnot.start, cAnnot.end)
                cAnnot.end = curLex.end
                usedRightEdgeToks.add(curLex)

        # we delete the annotation. Actually, we'd better make sure that the
        # annotations are detached first.

        self.removeAnnotationGroup(annotationsToDelete, forceDetach = True)
        
        return len(badAnnots)

    def avoidWhitespaceInTags(self, task):

        # Even in the case where we have no tokens, because it's a 
        # pattern-redacted document, we might have situations where the
        # tags cover leading or trailing whitespace. Here, we shrink the
        # whitespace without reference to the lexes. So you need to be careful
        # when you call this.

        import string
        
        contentAnnots = self.orderAnnotations(task.getAnnotationTypesByCategory('content'))
        for c in contentAnnots:
            signal = self.signal[c.start:c.end]
            iStart = 0
            while signal[iStart] in string.whitespace:
                iStart += 1
            iEnd = -1
            while signal[iEnd] in string.whitespace:
                iEnd -= 1
            iEnd += 1
            c.start += iStart
            c.end += iEnd

    def removeOverlaps(self, collisionList):
        # Emergency stopgap. Occasionally, we get overlapping
        # content tags, which we might not want. collisionList
        # is a list of annotation names which can't have
        # any overlaps among them.
        indexDict = {}
        for aName in collisionList:
            try:
                aType = self.anameDict[aName]
                annots = self.atypeDict[aType]
            except KeyError:
                continue
            # Ignore the overlaps for types which aren't spanned,
            # in the unlikely event that someone chooses them.
            if not aType.hasSpan:
                continue
            # Zero it out.
            self.atypeDict[aType] = []
            for a in annots:
                if indexDict.has_key(a.start):
                    # Take the shortest.
                    if a.end < indexDict[a.start].end:
                        print >> sys.stderr, "Warning: discarding %s from %d to %d in favor of shorter overlapping annotation" % (indexDict[a.start].atype.lab, a.start, indexDict[a.start].end)
                        indexDict[a.start] = a
                    else:
                        print >> sys.stderr, "Warning: discarding %s from %d to %d in favor of shorter overlapping annotation" % (a.atype.lab, a.start, a.end)
                else:
                    indexDict[a.start] = a
        indexes = indexDict.keys()
        indexes.sort()
        end = 0
        for i in indexes:
            # There will only be one.
            annot = indexDict[i]
            if i < end:
                # Now, we keep the annotation that's already started.
                print >> sys.stderr, "Warning: discarding %s from %s to %d in favor of annotation which starts earlier" % (annot.atype.lab, annot.start, annot.end)
                del indexDict[i]
            else:
                end = annot.end
        # Now, we've removed all the overlapping ones.
        # Reconstruct the annot sets.
        indexes = indexDict.keys()
        indexes.sort()
        for i in indexes:
            a = indexDict[i]
            self.atypeDict[a.atype].append(a)
        
    # I wanted this to be on the document, rather than the task,
    # because it's a document operation. But I want to call it
    # on bunches of documents.

    # Note that for the purposes of Carafe, at the moment this doesn't
    # return the zone information, so Carafe can't exploit that zone
    # region type as a feature. But we return it anyway.
    
    @classmethod
    def processableRegions(cls, annotSets, task = None, segmentFilterFn = None):
        zType, rAttr, regions = None, None, None
        if task is not None:
            zType, rAttr, regions = task.getTrueZoneInfo()

        regionLists = []
        for d in annotSets:
            segs = d.orderAnnotations(["SEGMENT"])
            if zType is not None:
                zones = d.orderAnnotations([zType])
            else:
                zones = None
            # If there's no segment filter function, there's no point
            # in looking at the segments - just use the zones. Not going to
            # bother filtering on zones, because the segments wouldn't be
            # there otherwise.
            if segs and segmentFilterFn:
                segs = [seg for seg in segs if segmentFilterFn(seg)]
                regionList = []
                # Loop through the segments. Each time we find one which is an
                # extension of a previous machine-annotatable segment, ignore the
                # new segment and extend the old.
                currentDigestibleRegion = None
                currentSeg = None
                currentZoneIndex = None
                if zones:
                    currentZoneIndex = 0
                for seg in segs:
                    if currentDigestibleRegion and (currentDigestibleRegion[1] == seg.start) and \
                       ((currentZoneIndex is None) or (zones[currentZoneIndex].end <= seg.end)):
                        currentDigestibleRegion[1] = seg.end
                    else:
                        # Try to move forward.
                        if currentZoneIndex is not None:
                            while seg.start >= zones[currentZoneIndex].end:
                                currentZoneIndex += 1
                                if currentZoneIndex == len(zones):
                                    currentZoneIndex = None
                                    break                        
                        currentDigestibleRegion = [seg.start, seg.end,
                                                   ((currentZoneIndex is not None) and (rAttr is not None) and \
                                                    [rAttr, zones[currentZoneIndex].get(rAttr)])
                                                   or None]
                        regionList.append(currentDigestibleRegion)
                regionLists.append(regionList)
                    
            elif zones:
                # Don't filter zones for segments above, but DO filter it here.
                regionLists.append([[z.start, z.end, ((rAttr is not None) and [rAttr, z.get(rAttr)]) or None]
                                    for z in zones if (rAttr is None) or (z.get(rAttr) in regions)])
                
            else:
                # No zoning at all has happened. Just use the whole document.
                regionLists.append([[0, len(d.signal), None]])
        return regionLists

#
# This is a structure which provides a view into a document, by
# smallest region. It looks into all the segments, and records
# for each smallest region, what annotations are stacked over
# that region. It's set up to manage multiple documents simultaneously
# (as long as they have the same signal), and so that
# you can augment the regions with features based on
# what's stacked there. It also records whether an annotation
# that's stacked there is ending there or not.
# The documents are also assumed to share a task, so
# they're subdivided by effective label and category, which
# may or may not be the right thing to do.
# If there's no task, there's a bunch of things we can't do.
#

# When we collect the docs, we can only collect the indices.
# It doesn't turn into the slices until we ask.

class DocSliceError(Exception):
    pass

class SignalCacheEntry:

    def __init__(self, cache, eType, doc, a, label, category):
        self.cache = cache
        self.eType = eType
        self.doc = doc
        self.annot = a
        self.label = label
        self.category = category        

class SignalIndexCache:

    def __init__(self, nth):
        self.nth = nth
        self.labelMap = {}

    def addEntry(self, eType, doc, a, label, category):
        e = SignalCacheEntry(self, eType, doc, a, label, category)
        try:
            self.labelMap[(label, category)].append(e)
        except KeyError:
            self.labelMap[(label, category)] = [e]

    def get(self, label = None, category = None):
        r = []
        for (l, c), entries in self.labelMap.items():
            if ((label is None) or (l == label)) and \
               ((category is None) or (c == category)):
                r += entries
        return r

    def removeEntry(self, e):
        # This is the actual entry that comes back from get().
        # So it will be the proper entry in the label map.
        try:
            self.labelMap[(e.label, e.category)].remove(e)
        except ValueError:
            pass
        except KeyError:
            pass

class SignalRegion(SignalIndexCache):

    STARTS, ENDS, MATCHES, WITHIN = 0, 1, 2, 3

    def __init__(self, nth, start, end):
        self.start = start
        self.end = end
        SignalIndexCache.__init__(self, nth)

class SignalIndex(SignalIndexCache):

    STARTS, ENDS, CROSSES = 0, 1, 2

    def __init__(self, nth, i):
        self.index = i
        SignalIndexCache.__init__(self, nth)

class DocSliceManager:

    # The skip table is a hash of doc => [(label, category), ...]
    def __init__(self, docs, task = None, categoryMap = None,
                 skipTable = None, keepTable = None):
        self.task = task
        # The categoryMap is a map from the label (NOT the effective label) to
        # one of the categories.
        self.categoryMap = categoryMap or {}
        # We want to know the effective label and the category.
        # What we should do is populate the category map
        # with the effective label as we go along, IF there's
        # either a task, or a task table in the document (I'm really not comfortable
        # with the latter, and I'd like to phase it out).
        # Actually, I'm going to liberate myself - I'm going to
        # ignore the task table in the document here completely.
        # Gotta start sometime...
        self.docs = []
        # Intermediate cache.
        self._indexCache = {}
        # Final cache. Regions are in order.
        self.regions = []
        if docs is not None:
            for doc in docs:
                self.addDocument(doc, (skipTable and skipTable.get(doc)), (keepTable and keepTable.get(doc)))

    # skipList and keepList are decisive. If both are provided (why would
    # you do that?) and something's not in the skip list but not in the
    # keep list, it's skipped.
    def addDocument(self, doc, skipList = None, keepList = None):
        if self.docs:
            if doc.signal != self.docs[0].signal:
                raise DocSliceError, "document signals must be identical"
        if doc in self.docs:
            raise DocSliceError, "document is already in slicer"
        self.docs.append(doc)

        if skipList:
            skipList = set(skipList)
        if keepList:
            keepList = set(keepList)
        # Let's gather info about the annotation.
        if self.task:
            mData = self.task
            labeler = self.task.getEffectiveAnnotationLabel
        else:
            mData = None
            labeler = lambda ann: ann.atype.lab
        for a in doc.getAnnotations(spannedOnly = True):
            # Find the label and category. Note that the category will be
            # the category of the annotation descriptor that the label
            # is defined in; if it's an effective label, that's the category
            # you'll get.
            label = labeler(a)
            try:
                category = self.categoryMap[label]
            except KeyError:
                category = None
                if mData is not None:
                    try:
                        category = mData.getCategoryForLabel(label)
                    except KeyError:
                        pass
                self.categoryMap[label] = category
            if skipList and (((label, category) in skipList) or \
                             ((label, None) in skipList) or \
                             ((None, category) in skipList)):
                continue
            if keepList and (((label, category) not in keepList) and \
                             ((label, None) not in keepList) and \
                             ((None, category) not in keepList)):
                continue
            entry = (doc, a, label, category)
            try:
                self._indexCache[a.start][0].append(entry)
            except KeyError:
                h = [[entry], []]
                self._indexCache[a.start] = h
            try:
                self._indexCache[a.end][1].append(entry)
            except KeyError:
                h = [[], [entry]]
                self._indexCache[a.end] = h                

    def getRegions(self):
        allIndices = self._indexCache.keys()
        allIndices.sort()
        if not allIndices:
            return []
        curEntries = set()
        # For each index, if it's not the final index,
        # start a region. The region ends all the annotations
        # that are ending, inherits all the annotations which
        # are underway, and starts all the annotations which
        # are starting.
        lastIndex = allIndices[-1]
        firstIndex = allIndices[0]
        justStarted = []
        previousIndex = -1
        regions = []
        j = 0
        for i in allIndices:
            [startEntries, endEntries] = self._indexCache[i]
            if i == lastIndex:
                if startEntries:
                    raise DocSliceError, "Can't start any annotations on the last index"
            if i == firstIndex:
                if endEntries:
                    raise DocSliceError, "Can't end any annotations on the first index"
            else:
                # At this point, I'm going to close the previous index.
                r = SignalRegion(j, previousIndex, i)
                j += 1
                regions.append(r)
                for endEntry in endEntries:
                    if endEntry in justStarted:
                        r.addEntry(SignalRegion.MATCHES, *endEntry)
                    else:
                        r.addEntry(SignalRegion.ENDS, *endEntry)
                for startEntry in justStarted:
                    if startEntry not in endEntries:
                        r.addEntry(SignalRegion.STARTS, *startEntry)
                for coveringEntry in curEntries:
                    if (coveringEntry not in justStarted) and (coveringEntry not in endEntries):
                        r.addEntry(SignalRegion.WITHIN, *coveringEntry)
                # The final trick is the ones which this region is within.
                # Those are the ones which are still going,
                # but weren't just started.
            # Cache these for the next interval.
            justStarted = startEntries
            previousIndex = i
            curEntries -= set(endEntries)
            curEntries |= set(startEntries)
        if curEntries:
            raise DocSliceError, "entries remain after all indices are processed"
        return regions
            
    def getIndexes(self):
        allIndices = self._indexCache.keys()
        allIndices.sort()
        if not allIndices:
            return []
        curEntries = set()
        # For each index, if it's not the final index,
        # start a region. The region ends all the annotations
        # that are ending, inherits all the annotations which
        # are underway, and starts all the annotations which
        # are starting.
        lastIndex = allIndices[-1]
        firstIndex = allIndices[0]
        previousIndex = -1
        indexes = []
        j = 0
        for i in allIndices:
            [startEntries, endEntries] = self._indexCache[i]
            if i == lastIndex:
                if startEntries:
                    raise DocSliceError, "Can't start any annotations on the last index"
            if i == firstIndex:
                if endEntries:
                    raise DocSliceError, "Can't end any annotations on the first index"
            else:
                # At this point, I'm going to close the previous index.
                r = SignalIndex(j, i)
                j += 1
                indexes.append(r)
                for endEntry in endEntries:
                    r.addEntry(SignalIndex.ENDS, *endEntry)
                for startEntry in startEntries:
                    r.addEntry(SignalIndex.STARTS, *startEntry)
                for coveringEntry in curEntries:
                    if (coveringEntry not in endEntries):
                        r.addEntry(SignalIndex.CROSSES, *coveringEntry)
            curEntries -= set(endEntries)
            curEntries |= set(startEntries)
        if curEntries:
            raise DocSliceError, "entries remain after all indices are processed"
        return indexes

#
# AnnotationReporter
#

# I hope this will be more successful than the DocSliceManager...

# This code was excised from the guts of MATReport. I believe I'm going to
# need it elsewhere; the first application is for the conversion reporter in MATTransducer.

# I think the idea is that for each row, there may be multiple 
# annotations (e.g., perhaps they're paired) and there may be a different
# configuration of headers for each.

class AnnotationReporter:

    CONCORDANCE_WINDOW = 32

    def __init__(self, partitionByLabel = False):
        self.partitionByLabel = partitionByLabel
        self.positions = []
        self.rows = []
        self.rowsByLabel = {}
        self.convertedPartitionedHeadersAndRows = None
        
    def addPosition(self, headerPrefix = None, concordanceContext = False, concordanceWindow = None,
                    showText = True):
        posDesc = {"doConcordance": concordanceContext, "showText": showText, "headerPrefix": headerPrefix}
        if showText and concordanceContext:
            if concordanceWindow is None:
                posDesc["concordanceWindow"] = self.CONCORDANCE_WINDOW
            elif concordanceWindow < 1:
                raise DocumentError, "concordance window must be 1 or greater"
            else:
                posDesc["concordanceWindow"] = concordanceWindow
        if not showText:
            posDesc["headers"] = ["start", "end", "label", "description"]
        elif concordanceContext:
            posDesc["headers"] = ["start", "end", "left context", "text", "label", "description", "right context"]
        else:
            posDesc["headers"] = ["start", "end", "text", "label", "description"]
        if len(self.positions) == 0:
            # first position. Do something special for the partition headers.
            if not showText:
                posDesc["bylabel_headers"] = ["start", "end", "id", "attrs"]
            elif concordanceContext:
                posDesc["bylabel_headers"] = ["start", "end", "id", "left context", "text", "attrs", "right context"]
            else:
                posDesc["bylabel_headers"] = ["start", "end", "id", "text", "attrs"]
        else:
            posDesc["bylabel_headers"] = posDesc["headers"][:]            
        self.positions.append(posDesc)

    def addDocument(self, doc, basename, aNames, includeSpanless = False):
        annotLabCounts = {}
        if len(self.positions) != 1:
            raise DocumentError, "positions != 1 when adding document is not permitted"
        if self.positions[0]["headers"][0] != "basename":
            self.positions[0]["headers"][0:0] = ["basename"]
        if self.positions[0]["bylabel_headers"][0] != "basename":
            self.positions[0]["bylabel_headers"][0:0] = ["basename"]
        if aNames:
            # We'll have something to add.
            # orderAnnotations will retrieve JUST the spanned annotations.
            for a in doc.orderAnnotations(aNames):
                self.addRow([a])
                self.rows[-1][0:0] = [basename]
                if self.partitionByLabel:
                    self.rowsByLabel[a.atype.lab]["rows"][-1][0:0] = [basename]
                try:
                    annotLabCounts[a.atype.lab] += 1
                except KeyError:
                    annotLabCounts[a.atype.lab] = 1
            if includeSpanless:
                for a in doc.getAnnotations(atypes = aNames, spanlessOnly = True):
                    self.addRow([a])
                    self.rows[-1][0:0] = [basename]
                    if self.partitionByLabel:
                        self.rowsByLabel[a.atype.lab]["rows"][-1][0:0] = [basename]
                    try:
                        annotLabCounts[a.atype.lab] += 1
                    except KeyError:
                        annotLabCounts[a.atype.lab] = 1
        return annotLabCounts

    # Partition by label partitions by the FIRST ELEMENT.
    # The first element position will use the keys as part of the columns.
    # The other positions will be appropriate for the position.
    
    def addRow(self, row):
        if len(row) != len(self.positions):
            raise DocumentError, "row is different length than positions"
        rowRes = []
        partitionRes = []
        self.rows.append(rowRes)
        i = 0
        # The annotation may be null, if it's not paired.
        while i < len(row):
            a = row[i]
            posDesc = self.positions[i]
            if a is None:
                # Pad it.
                rowRes += [None] * len(posDesc["headers"])
                i += 1
                continue
            doConcordance = posDesc["doConcordance"]
            showText = posDesc["showText"]
            # Create a composite label.
            labName = a.atype.lab
            leftWindow = rightWindow = start = end = None
            if a.atype.hasSpan:
                txt = a.doc.signal[a.start:a.end]
                if doConcordance:
                    leftEdge = max(0, a.start - posDesc["concordanceWindow"])
                    leftWindow = a.doc.signal[leftEdge:a.start]
                    rightWindow = a.doc.signal[a.end:a.end+posDesc["concordanceWindow"]]
                start = a.start
                end = a.end
            else:
                txt = self._computeSpanlessText(a)
            if not showText:
                localSubportion = [start, end, labName, a.describe()]
            elif doConcordance:
                localSubportion = [start, end, leftWindow, txt, labName, a.describe(), rightWindow]
            else:
                localSubportion = [start, end, txt, labName, a.describe()]
            rowRes += localSubportion
            if self.partitionByLabel:
                if i == 0:
                    try:
                        entry = self.rowsByLabel[labName]
                        entry["rows"].append(partitionRes)
                    except KeyError:
                        entry = {"keys": set(), "rows": [partitionRes]}
                        self.rowsByLabel[labName] = entry
                    aDict = dict([(attr.name, attr.toStringNonNull(val)) for (attr, val) in \
                                  zip(a.atype.attr_list, a.attrs) if val is not None])
                    entry["keys"].update(aDict.keys())
                    if not showText:
                        partitionRes += [start, end, a.id, aDict]
                    elif doConcordance:
                        partitionRes += [start, end, a.id, leftWindow, txt, aDict, rightWindow]
                    else:
                        partitionRes += [start, end, a.id, txt, aDict]
                else:
                    partitionRes += localSubportion                    
            i += 1

    def getHeadersAndRows(self):
        h = []
        for p in self.positions:
            headers = p["headers"]
            if p["headerPrefix"]:
                h += [p["headerPrefix"] + " " + s for s in headers]
            else:
                h += headers
        return h, self.rows

    def getPartitionedHeadersAndRows(self):
        self._ensurePartitionConversion()
        return self.convertedPartitionedHeadersAndRows

    def _ensurePartitionConversion(self):
        if (self.convertedPartitionedHeadersAndRows is None) and (self.partitionByLabel):
            # The first position will have attrs.
            self.convertedPartitionedHeadersAndRows = {}
            for lab, entry in self.rowsByLabel.items():
                h = []
                attrIndex = self.positions[0]["bylabel_headers"].index("attrs")
                for p in self.positions:
                    headers = p["bylabel_headers"]
                    if p["headerPrefix"]:
                        h += [p["headerPrefix"] + " " + s for s in headers]
                    else:
                        h += headers
                # Those are all the headers.
                attrIndex = h.index("attrs")
                # Don't do the prefix substitutions with the keys. 
                keys = list(entry["keys"])
                keys.sort()
                h = h[0:attrIndex] + keys + h[attrIndex+1:]
                rows = [row[0:attrIndex] + [row[attrIndex].get(key) for key in keys] + row[attrIndex+1:]
                        for row in entry["rows"]]
                self.convertedPartitionedHeadersAndRows[lab] = (h, rows)                

    # The way we compute the text for a spanless
    # annotation is to find the spanned annotations which are
    # referenced, and define a window around it. Then,
    # we collapse the windows if they overlap.

    def _computeSpanlessText(self, a):
        spannedAnnots = {}
        for attrObj, val in zip(a.atype.attr_list, a.attrs):
            if (attrObj._typename_ == "annotation") and (val is not None):
                if not attrObj.aggregation:
                    if val.atype.hasSpan:
                        try:
                            spannedAnnots[val].add(attrObj.name)
                        except KeyError:
                            spannedAnnots[val] = set([attrObj.name])
                else:
                    for subval in val:
                        if subval.atype.hasSpan:
                            try:
                                spannedAnnots[subval].add(attrObj.name)
                            except KeyError:
                                spannedAnnots[subval] = set([attrObj.name])
        if spannedAnnots:
            # OK, now we have a mapping from spanned annotations
            # to the attrs they cover. Don't forget they can
            # overlap each other. Grrr.
            # First thing we do: let's have a window of 20 characters on
            # each side.
            annotKeys = spannedAnnots.keys()
            annotKeys.sort(key = lambda a: a.start)
            intervals = []
            signalLen = len(a.doc.signal)
            # There's no guarantee that the annot ENDS are in order.
            # So the only safe thing to do is gather all the starts and
            # ends first.
            toInsert = {}
            for annot, attrList in spannedAnnots.items():
                startStr = " [" + ",".join(attrList) + " "
                try:
                    toInsert[annot.start][0].append(startStr)
                except KeyError:
                    # Not less than 0.
                    toInsert[annot.start] = [[startStr], []]
                try:
                    toInsert[annot.end][1].append(" ] ")
                except KeyError:
                    # Not more than the length of the signal.
                    toInsert[annot.end] = [[], [" ] "]]
            # I want to see all the text; so multiple successive
            # starts just keep extending the interval. It's only
            # when the covered tags go down to 0 that we start
            # skipping stuff.
            allIndices = list(toInsert.keys())
            allIndices.sort()
            covering = 0
            for index in allIndices:
                [starts, ends] = toInsert[index]
                if ends:
                    covering -= len(ends)
                    # We're ending some stuff.
                    # Not more than the length of the signal.
                    right = min(index + 20, signalLen)
                    if covering == 0:
                        # Set the right index of the current interval
                        intervals[-1][1] = right                        
                if starts:
                    if covering == 0:
                        # Not less than 0.
                        left = max(index - 20, 0)
                        if intervals and ((intervals[-1][1] + 10) >= left):
                            # If it's within 10 of the last interval, just
                            # add it.
                            intervals[-1][1] = right
                        else:
                            intervals.append([left, index])
                    covering += len(starts)
            # Now, we have all the indices we need.
            bracketKeys = toInsert.keys()
            bracketKeys.sort()
            # There can be multiple annotations inside
            # a given interval, don't forget.
            docSignal = a.doc.signal
            strs = ["..."]
            for [left, right] in intervals:
                if len(strs) > 1: strs.append("...")
                start = left
                while bracketKeys and \
                      (bracketKeys[0] > left) and \
                      (bracketKeys[0] < right):
                    strs.append(docSignal[start:bracketKeys[0]])
                    [bStart, bEnd] = toInsert[bracketKeys[0]]
                    strs += bEnd
                    strs += bStart
                    start = bracketKeys[0]
                    bracketKeys[0:1] = []
                strs.append(docSignal[start:right])
            strs.append("...")
            # Get rid of all the newlines by splitting at
            # whitespace and reconstructing.
            return " ".join("".join(strs).split())
        else:                        
            return None
