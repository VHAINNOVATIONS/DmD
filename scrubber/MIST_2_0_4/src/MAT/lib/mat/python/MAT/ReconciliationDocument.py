# Copyright (C) 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import MAT.DocumentIO, MAT.Document, sys

SPECIAL_VOTE_VALUES = ["ignore", "bad boundaries"]

class ReconciliationError(Exception):
    pass

# Right now, we're working with SEGMENT annotations and
# augmented content annotations. Later, we'll work directly
# with administrative information. Right now, there's a
# "status" element too on the content annotation, and other
# info like confidence measures (or slots for them). I'm not sure
# how to filter these, except to specify them.

# Every doc MUST have a task table.

class _NullWriter:

    def write(self, msg):
        pass

# Here's an object I'm going to need in multiple places. It's populated
# by the administrative attrs and the atypes for any eligible documents,
# and then extracts vectors from annotations
# which can be used for comparison purposes.

class AnnotationEquivalenceClassifier:

    def __init__(self, task):

        # Originally, I was taking all the attributes and removing
        # those judged to be superfluous. Because the range of use
        # of reconciliation is now beyond the original workspace
        # usage, I'm going to store the information about equivalence
        # on the tags in the task directly. If there are no
        # attributes judged to be distinguishing,
        # we'll look for attrs mentioned in subgroups for
        # viewing, and interpret those as being distinguishing.
        # (This is taken care of in PluginMgr.py.)
        # Otherwise, no attributes will be used.
        
        self.labDict = {}
        t = task.getAnnotationTypeRepository()
        for lab, atype in t.items():
            self.labDict[lab] = atype.getDistinguishingAttributesForEquality()

    # Originally, we were letting the annotations decide what the
    # attributes available were. But now, we're taking it from the task
    # explicitly. 
    
    def generateAnnotVector(self, a):
        return (a.start, a.end, a.atype.lab) + tuple([a.get(attr) for attr in self.labDict[a.atype.lab]])
        
    def newAnnotation(self, outDoc, vect):            
        aStart, aEnd, aLab = vect[:3]
        features = vect[3:]
        return outDoc.createAnnotation(aStart, aEnd, aLab, dict(zip(self.labDict[aLab], features)), blockAdd = True)
        
class ReconciliationDoc(MAT.Document.AnnotatedDoc):

    @classmethod
    def generateReconciliationDocument(cls, task, docs, verbose = sys.stdout):

        if verbose in [None, False]:
            verbose = _NullWriter()

        equivClasser = AnnotationEquivalenceClassifier(task)
        contentTypes = task.getAnnotationTypesByCategory("content")
        zoneTypes = task.getAnnotationTypesByCategory("zone")

        for doc in docs[1:]:
            if doc.signal != docs[0].signal:
                raise ReconciliationError, "docs don't all have the same signal"
            for atype in doc.atypeDict.keys():
                if (atype.lab in contentTypes) and atype.hasAnnotationValuedAttributes:
                    raise ReconciliationError, "at least one doc has a content annotation type with annotation-valued attributes"

        signalLength = len(docs[0].signal)

        # And now, the guts. First, let's copy one of the
        # docs, but remove all the SEGMENT annotations and content annotations.
        # The easiest way to do this, frankly, is to read it again.
        # Make sure you pass in the task, and make the tag table available.

        # Let's render the JSON to a hash, then add the reconciliation doc
        # and make a seed of this class, rather than go all the way to the
        # Unicode string.
        
        _jsonIO = MAT.DocumentIO.getDocumentIO("mat-json")

        # Actually, we have to be careful which to pick from: if one of the docs
        # has no token annotations, then we shouldn't use that one.

        thisDoc = docs[0]
        for d in docs:
            if d.getAnnotations(task.getAnnotationTypesByCategory("token")):
                thisDoc = d
                break

        # At this point, either we'll have a document which has tokens, or
        # none of them will.                

        h = _jsonIO.renderJSONObj(thisDoc)
        h["metadata"]["reconciliation_doc"] = True
        outDoc = task.newDocument(docClass = cls)
        # For the moment.
        outDoc.unlockAtypeRepository()
        _jsonIO._deserializeFromJSON(h, outDoc)

        # outDoc = _jsonIO.readFromUnicodeString(_jsonIO.writeToUnicodeString(docs[0]),
        #                                       taskSeed = task)
        # outDoc.metadata["reconciliation_doc"] = True
        
        outDoc.removeAnnotations(contentTypes)
        # NOT NECESSARILY A COPY. BUG.
        segAnnots = outDoc.getAnnotations(["SEGMENT"])[:]
        outDoc.removeAnnotationGroup(segAnnots)
        
        # Need these for when we're generating ignore regions.
        # The TooCAAn core task excludes SEGMENT and VOTE for this category.
        txtZones = [(a.start, a.end) for a in outDoc.orderAnnotations(zoneTypes)]

        allAnnotators = set()

        # OK, it's ready.

        # Step 1: find all the human gold regions, and then
        # find their overlap. I've realized that I need to collect the content annotation
        # indices as well, because if an annotation in one of the docs straddles the
        # putative HAS boundary, the region must be adjusted, because annotations may
        # never straddle a HAS boundary. We have to monitor this on both
        # ends.

        allIndices = {}

        # If one of the regions is really reconciled and it overlaps with
        # gold (which can happen when you have another annotator joining later),
        # that's ALSO a region of interest. So it looks like it's going to get a little
        # more complicated to construct the overlaps. We'll just collect
        # all the regions which are gold or reconciled and use the function
        # _regionsQualify to sort them out later.

        # Actually, the way the loop that calls regionsQualify is written,
        # nothing will happen, at all, if all regions are reconciled. That's a problem.
        # Furthermore, on the odd chance that someone has managed to modify a
        # reconciled region, we should just make all the gold and reconciled
        # regions candidates and let the common/not-common calculation figure
        # out the rest.

        def _regionsQualify(pairSet):
            # For a set of regions to qualify, at least one of them must be
            # either human gold or below the reconciliation threshold.
            #for doc, a in pairSet:
            #    if a["status"] == "human gold":
            #        return True
            #return False
            return True

        # Should only be called for SEGMENTs now - no longer adding annotator
        # attributes for individual content annotations.
        def _addAnnotator(a, annotatorSet):
            found = _getListValue(a, "annotator")
            annotatorSet.update(found)
            return found

        # We need a temporary structure - it's getting a bit messy to have
        # just a list of lists.

        class IndexEntry:

            def __init__(self, idx, segStart = None, segEnd = None, contentStart = None,
                         contentEnd = None, zoneStart = None, zoneEnd = None, transitionCandidate = False):
                self.index = idx
                self.segStart = []
                if segStart is not None:
                    self.segStart += segStart
                self.segEnd = []
                if segEnd is not None:
                    self.segEnd += segEnd
                self.contentStart = []
                if contentStart is not None:
                    self.contentStart += contentStart
                self.contentEnd = []
                if contentEnd is not None:
                    self.contentEnd += contentEnd
                self.zoneStart = []
                if zoneStart is not None:
                    self.zoneStart += zoneStart
                self.zoneEnd = []
                if zoneEnd is not None:
                    self.zoneEnd += zoneEnd
                self.transitionCandidate = transitionCandidate
                self.ignoreStart = False
                self.ignoreEnd = False
                self.goldStart = False
                self.goldEnd = False
                self.goldAnnotators = None
            def _setGoldStart(self, pairs):
                self.goldStart = True
                # We need to collect these when goldStart
                # is set, because the information vanishes.
                self.goldAnnotators = set()
                for doc, a in pairs:
                    _addAnnotator(a, self.goldAnnotators)

        # The trick here is that we have to record, for all the
        # content annotations, which segment they're in.

        numDocs = len(docs)
        for doc in docs:
            # NOT NECESSARILY A COPY.        
            segs = doc.orderAnnotations(["SEGMENT"])[:]
            for a in segs:
                _addAnnotator(a, allAnnotators)
                if a["status"] in ["human gold", "reconciled"]:
                    try:
                        allIndices[a.start].segStart.append((doc, a))
                    except KeyError:
                        allIndices[a.start] = IndexEntry(a.start, segStart = [(doc, a)])
                    try:
                        allIndices[a.end].segEnd.append((doc, a))
                    except KeyError:
                        allIndices[a.end] = IndexEntry(a.end, segEnd = [(doc, a)])
            for a in doc.orderAnnotations(contentTypes):
                # Figure out what segment we're on.
                while segs and (segs[0].end < a.start):
                    segs[0:1] = []
                if not segs:
                    # Oops, that's a REAL problem.
                    raise ReconciliationError, "content annotation after all segments"
                if segs[0].start > a.start:
                    raise ReconciliationError, "content annotation between segments"
                try:
                    allIndices[a.start].contentStart.append((doc, a, segs[0].get("annotator")))
                except KeyError:
                    allIndices[a.start] = IndexEntry(a.start, contentStart = [(doc, a, segs[0].get("annotator"))])
                # Don't care about the annotator for the content end - we're just counting the
                # length, currently.
                try:
                    allIndices[a.end].contentEnd.append((doc, a))
                except KeyError:
                    allIndices[a.end] = IndexEntry(a.end, contentEnd = [(doc, a)])
        # Assume the zones for everyone are the same.
        for a in outDoc.orderAnnotations(zoneTypes):
            try:
                allIndices[a.start].zoneStart.append(a)
            except KeyError:
                allIndices[a.start] = IndexEntry(a.start, zoneStart = [a])
            try:
                allIndices[a.end].zoneEnd.append(a)
            except KeyError:
                allIndices[a.end] = IndexEntry(a.end, zoneEnd = [a])        

        # OK, now we have a dictionary with all the indices.

        indices = allIndices.keys()
        indices.sort()

        # Now, we loop through the indices, marking how many docs
        # cover the interval. We're going to assume that the segments
        # never overlap, so we can just count how many things
        # there are in the table. We also  keep track of whether we're
        # in an annotation or not.

        # The gold overlap is more of a guide than an absolute
        # boundary, because the reconciliation process can add gold
        # annotations. So we want to be a bit generous here. If, for instance,
        # the gold boundary is at an annotation, we should set the gold
        # region to include the boundary annotation, rather than exclude it.
        # Also, because boundary changes can be made, we want to include
        # all the annotations, not just the ones in the gold.

        # So first pass: find the transition candidates. Don't bother
        # collecting content annotations yet.

        curDocs = 0
        curDocSet = set()
        numAnnotations = 0
        lastZeroAnnotation = None
        inZone = False
        inGoldRegion = False
        inIgnoreRegion = False

        for index in indices:
            indexEntry = allIndices[index]
            # Compute the number of regions.
            curDocs -= len(indexEntry.segEnd)
            for p in indexEntry.segEnd:
                curDocSet.remove(p)
            curDocs += len(indexEntry.segStart)
            for p in indexEntry.segStart:
                curDocSet.add(p)
            # Now, REDUCE the annotation count.
            numAnnotations -= len(indexEntry.contentEnd)
            if numAnnotations == 0:
                indexEntry.transitionCandidate = True
                lastZeroAnnotation = indexEntry
            curNumAnnotations = numAnnotations
            numAnnotations += len(indexEntry.contentStart)
            enteringZone = leavingZone = False
            if (not inZone) and indexEntry.zoneStart:
                if curNumAnnotations != 0:
                    raise ReconciliationError, "content annotations != 0 at zone start"
                inZone = True
                print >> verbose, "Entering zone at", index
                enteringZone = True
            elif (inZone) and indexEntry.zoneEnd:
                if curNumAnnotations != 0:
                    raise ReconciliationError, "content annotations != 0 at zone end"
                inZone = False
                print >> verbose, "Leaving zone at", index
                leavingZone = True
            print >> verbose, "Starting at", index, ":", "cur docs", curDocs, "num annots", numAnnotations, \
                  "about to start", len(indexEntry.contentStart), "in zone", inZone
            # OK, now that we have all the information we need, we get to the rules.
            # At any point, as long as we're in a zone, we're either in an ignore region or a
            # gold region. Our goal is to identify the transitions, which can only happen
            # at zero annotations.
            if inZone:
                if curDocs == numDocs:
                    # All the documents are represented. Let's see if we're about
                    # to start a gold region.
                    if (not inGoldRegion) and _regionsQualify(curDocSet):
                        if curNumAnnotations == 0:
                            iEntry = indexEntry
                        else:
                            # If numAnnotations isn't zero, then use the last zero annotation.
                            iEntry = lastZeroAnnotation
                        if inIgnoreRegion:
                            print >> verbose, "Ending ignore region at", iEntry.index
                            iEntry.ignoreEnd = True
                            inIgnoreRegion = False                
                        print >> verbose, "Starting gold region at", iEntry.index
                        iEntry._setGoldStart(curDocSet)
                        inGoldRegion = True
                elif curDocs < numDocs:
                    if inGoldRegion and (curNumAnnotations == 0):
                        # End it. We're out of the region and we've passed the last
                        # annotation that straddles the boundary.
                        print >> verbose, "Ending gold region at", index
                        indexEntry.goldEnd = True
                        inGoldRegion = False
                    if not inIgnoreRegion:
                        # We're just entering a zone, probably, or the gold region above has just ended.
                        print >> verbose, "Starting ignore region at", index
                        indexEntry.ignoreStart = True
                        inIgnoreRegion = True
            elif leavingZone:
                # Exit everything.
                if inGoldRegion:
                    print >> verbose, "Ending gold region at", index
                    indexEntry.goldEnd = True
                    inGoldRegion = False
                elif inIgnoreRegion:
                    print >> verbose, "Ending ignore region at", index
                    indexEntry.ignoreEnd = True
                    inIgnoreRegion = False

        outContent = []
        outRegion = []
        outVote = []
        segType = outDoc.findAnnotationType("SEGMENT")
        voteType = outDoc.findAnnotationType("VOTE", hasSpan = False)

        # Pass 2: gather the regions and annotations. 

        curAnnotations = []
        regionStart = None
        regionType = None
        regions = []

        for index in indices:
            iEntry = allIndices[index]
            if regionStart:
                if iEntry.goldEnd:
                    regions.append((regionStart.index, index, "gold", curAnnotations, regionStart.goldAnnotators))
                    print >> verbose, "Recording gold region from", regionStart.index, "to", index, \
                          "with", len(curAnnotations), "annotations"
                    regionStart = None
                    curAnnotations = []
                elif iEntry.ignoreEnd:
                    regions.append((regionStart.index, index, "ignore", curAnnotations, None))
                    print >> verbose, "Recording ignore region from", regionStart.index, "to", index, \
                          "with", len(curAnnotations), "annotations"
                    regionStart = None
                    curAnnotations = []
            # Assume that the transitions are all clean. If there's a start, start.
            if iEntry.goldStart or iEntry.ignoreStart:
                print >> verbose, "Starting region for recording at", index
                regionStart = iEntry
                curAnnotations = []
            # Now that we have all the starts, we should collect the starting
            # annotations.
            if regionStart:
                curAnnotations += iEntry.contentStart
                print >> verbose, "Adding", len(iEntry.contentStart), "annotations starting at", index

        # Now, we have the regions, and the annotations inside them.
        # Next, for each region, I need to isolate the non-administrative annotation
        # attributes, and group them to see how many documents they cover. For the
        # gold regions, I need to do the same trick as above: order by index, and then collect the
        # regions that are reconciled at those points where we enter and exit
        # complete document coverage.

        # Here's a utility function to use when we start
        # looping through the gold regions.
        # At one point, I thought the new segment wouldn't
        # need any annotator information, but I need that in
        # order to parcel out the cross-validation assignments
        # (and the UI needs it to focus the assignment).
        # In order to do this, I need to know the annotator set
        # for this region intersection. If there's no set, it's
        # an ignore region, and I'm not going to bother
        # tracking the local annotators or assigning "vote for nothing".

        # So now, we have a new way of dealing with voting. We
        # introduce a new annotation named VOTE, which has:
        # - content (either a comma-separated sequence of annotation IDs, or the 
        # string "ignore", or the string "bad boundaries", or the empty string)
        # - an annotator (comma-separated string)
        # an explicit vote slot (so we can tell who voted)    
        # - a pointer back to the segment
        # And annotations now need IDs, so they can be referred to in the votes.

        def _addRegionAndContents(region, status, annotEquivs, annotatorSet):
            start, end, regionVecs = region
            # We don't really care about the annotators or anything else
            # here. I suppose if there are no regionVecs, we should probably
            # have all the annotators vote for an empty HAS, but I'm not
            # sure there's a point to that. But I'm going to do it anyway.
            newSeg = outDoc.createAnnotation(start, end, segType,
                                             {"status": status,
                                              "to_review": None,
                                              "reviewed_by": ""},
                                             blockAdd = True)
            localAnnotators = None
            if annotatorSet:
                localAnnotators = annotatorSet.copy()
                newSeg["annotator"] = ",".join(annotatorSet)
            outRegion.append(newSeg)
            # OK, we have to create each annotation, and each vote. But we
            # only bother with the votes for the non-reconciled ones.
            voteDict = {}
            for regionVec in regionVecs:
                annotAnnotators = set()
                # This is a list of doc, annot, annotators (from segment)
                regionEquivs = annotEquivs[regionVec]
                newA = equivClasser.newAnnotation(outDoc, regionVec)
                curId = newA.getID()
                for doc, a, annotators in regionEquivs:
                    if annotators:
                        aList = annotators.split(",")
                        annotAnnotators.update(aList)
                        for annotator in aList:
                            try:
                                voteDict[annotator].append(curId)
                            except KeyError:
                                voteDict[annotator] = [curId]
                if localAnnotators is not None:
                    localAnnotators -= annotAnnotators
                outContent.append(newA)

            # Only generate votes for human gold case.
            if status == "human gold":
                # Now, turn these into VOTE annotations. Anchor them
                # at 0, 0 - nobody cares, and I'm pretty sure I'll need to
                # force them to have integers.
                # Let's turn vote patterns into lists of voters.
                patDict = {}
                for voter, pattern in voteDict.items():
                    pattern = tuple(pattern)
                    try:
                        patDict[pattern].append(voter)
                    except KeyError:
                        patDict[pattern] = [voter]
                segVotes = []
                # The "reviewed" annotation should ultimately have all the
                # annotators who reviewed it. No document has been completed
                # by a user unless that user has reviewed all the segments
                # s/he is assigned to.
                for pattern, voters in patDict.items():
                    v = outDoc.createSpanlessAnnotation(voteType, {"content": ",".join([str(i) for i in pattern]),
                                                                   "annotator": ",".join(voters),
                                                                   "segment": newSeg,
                                                                   "chosen": "no",
                                                                   "comment": None},
                                                        blockAdd = True)
                    outVote.append(v)

                if localAnnotators:
                    print >> verbose, "Adding empty vote"
                    # If we still have any local annotators who haven't
                    # piped up here, then add a vote for nothing.
                    v = outDoc.createSpanlessAnnotation(voteType, {"content": "",
                                                                   "annotator": ",".join(localAnnotators),
                                                                   "chosen": "no",
                                                                   "segment": newSeg,
                                                                   "comment": None},
                                                        blockAdd = True)
                    outVote.append(v)

        for [start, end, rType, annotTriples, annotators] in regions:

            print >> verbose, "For", rType, "region", start, end, ":"

            # First, calculate and collect the equivalents.
            annotEquivs = {}        
            for doc, a, contentAnnotators in annotTriples:
                vec = equivClasser.generateAnnotVector(a)
                try:
                    annotEquivs[vec].append((doc, a, contentAnnotators))
                except KeyError:
                    annotEquivs[vec] = [(doc, a, contentAnnotators)]

            # If we're in an ignore region, we're done; we just need to
            # generate the region. If we're in a gold region, we have to
            # find sequences of common and non-common vectors.

            if rType == "ignore":
                annotationID = _addRegionAndContents((start, end, annotEquivs.keys()),
                                      "ignore during reconciliation", annotEquivs,
                                      None)
                print >> verbose, "  ", [(vec, "%d of %d" % (len(annotEquivs[vec]), numDocs)) for vec in annotEquivs.keys()]
            else:

                annotIndices = {}
                # Next, collect the indices of the annotations.

                for vect, appearances in annotEquivs.items():
                    try:
                        annotIndices[vect[0]][0].append(vect)
                    except KeyError:
                        annotIndices[vect[0]] = [[vect], []]
                    try:
                        annotIndices[vect[1]][1].append(vect)
                    except KeyError:
                        annotIndices[vect[1]] = [[], [vect]]

                # Now, I have to use this information to find the shortest
                # stretches of non-common annotations. I want to make sure
                # I keep track of the perverse possibility that annotations
                # which are all in common overlap with annotations which
                # aren't (this shouldn't happen right now, but might eventually).
                # The way we do this is we look through the indexes, and
                # we see whether we have any non-common annotations starting
                # or ending. The boundaries of the non-common regions start
                # when the number is above 0, and end when the number is 0,
                # except that it has to extend on each end to a point
                # where there are no annotations at all.

                # And while we're at it, we might as well partition the annots.

                indexList = annotIndices.keys()
                indexList.sort()

                # Remember, we've already computed the transition candidates.

                numConflictingAnnotations = 0
                regionVecs = []
                commonRegions = []
                nonCommonRegions = []
                commonRegionStart = start
                nonCommonRegionStart = None

                for index in indexList:
                    [startVecs, endVecs] = annotIndices[index]
                    transitionCandidate = allIndices[index].transitionCandidate
                    for vec in endVecs:
                        if len(annotEquivs[vec]) < numDocs:
                            numConflictingAnnotations -= 1
                    for vec in startVecs:
                        if len(annotEquivs[vec]) < numDocs:
                            numConflictingAnnotations += 1
                    # First, we figure out what type of region we're in.
                    # It may be a transition.
                    if transitionCandidate and (numConflictingAnnotations > 0) and \
                        (commonRegionStart is not None):
                        if index > commonRegionStart:
                            commonRegions.append((commonRegionStart, index, regionVecs))
                        commonRegionStart = None
                        nonCommonRegionStart = index
                        regionVecs = []
                    elif transitionCandidate and (numConflictingAnnotations == 0) and \
                         (nonCommonRegionStart is not None):
                        # Transition to nonconfliction.
                        if index > nonCommonRegionStart:
                            nonCommonRegions.append((nonCommonRegionStart, index, regionVecs))
                        nonCommonRegionStart = None
                        commonRegionStart = index
                        regionVecs = []
                    # Accumulate the start vecs.
                    regionVecs += startVecs

                # And finally, the end termination case.
                if (commonRegionStart is not None) and (end > commonRegionStart):
                    commonRegions.append((commonRegionStart, end, regionVecs))
                elif (nonCommonRegionStart is not None) and (end > nonCommonRegionStart):
                    nonCommonRegions.append((nonCommonRegionStart, end, regionVecs))

                # Now, we need to enhance the out doc with the results. All the annotations
                # have to be credited to whoever created them. We need to know who all the
                # annotators are so we can set up the non-common regions appropriately, since
                # some of the annotators 

                # And voila.
                print >> verbose, "  Common regions:", commonRegions
                print >> verbose, "  Non-common regions:"
                for start, end, regionVecs in nonCommonRegions:
                    print >> verbose, "    ", start, end, [(vec, "%d of %d" % (len(annotEquivs[vec]), numDocs)) for vec in regionVecs]

                for region in commonRegions:
                    annotationID = _addRegionAndContents(region, "reconciled", annotEquivs, annotators)

                for region in nonCommonRegions:
                    annotationID = _addRegionAndContents(region, "human gold", annotEquivs, annotators)

        outRegion.sort(cmp, lambda a: a.start)
        outContent.sort(cmp, lambda a: a.start)

        for reg in outRegion:
            outDoc._addAnnotation(reg)
        for c in outContent:
            outDoc._addAnnotation(c)
        for c in outVote:
            outDoc._addAnnotation(c)

        return outDoc

    # And now, the reverse. We need the task for the tag table.

    def export(self, task):
        if not self._allSegmentsReconciled():
            raise ReconciliationError, "not all segments are reconciled"
        # Copy yourself, drop the votes, make a single gold segment, and call updateSourceDocuments.
        newD = self.copy()
        del newD.metadata["reconciliation_doc"]
        newD.removeAnnotations(["VOTE"])
        segs = newD.orderAnnotations(["SEGMENT"])[:]
        zones = []
        for a in segs:
            if zones and (zones[-1][1] == a.start):
                zones[-1][1] = a.end
            else:
                zones.append([a.start, a.end])
        newD.removeAnnotationGroup(segs)
        for [s, e] in zones:
            newD.createAnnotation(s, e, "SEGMENT", {"status": "human gold"})
        self.updateSourceDocuments(task, [newD], verbose = None)
        return newD        

    def updateSourceDocuments(self, task, sourceDocs, verbose = sys.stdout):

        recDoc = self

        if verbose in [None, False]:
            verbose = _NullWriter()

        print >> verbose, "Entering updateSourceDocuments"

        # So the elements which are interesting are the SEGMENTs which are reconciled which
        # have a VOTE which is chosen. And that's the vote whose contents we need to
        # use, which, oddly enough, is not what I did the first time.

        # Actaully, that's not quite enough. We're also interested in those regions which
        # marked as reconciled because they AGREED when the reconciliation document
        # was created, and are thus also reconciled. In that case, there are
        # no votes to modify, so I to put them on a separate list.

        winningVotes = []

        # We have to sort the segments by the votes. Or
        # do we? The segments which don't have any votes
        # are the segments which are already reconciled.

        interestingSegmentSet = set()
        alreadyReconciledSegments = set([a for a in recDoc.getAnnotations(["SEGMENT"]) if a["status"] == "reconciled"])
        segmentsToIgnore = set()

        for vote in recDoc.getAnnotations(["VOTE"]):
            # These are spanless.
            # Any segment pointed to by a vote can't be already reconciled.
            alreadyReconciledSegments.discard(vote["segment"])
            if vote.get("chosen") == "yes":
                interestingSegmentSet.add(vote["segment"])
                winningVotes.append(vote)
                if vote.get("content") == "ignore":
                    segmentsToIgnore.add(vote["segment"])

        print >> verbose, "Interesting segments", list(interestingSegmentSet)
        print >> verbose, "Already reconciled segments", list(alreadyReconciledSegments)

        if not (interestingSegmentSet or alreadyReconciledSegments):
            return

        allSegments = interestingSegmentSet | alreadyReconciledSegments

        interestingSegments = list(interestingSegmentSet)
        # Order them.
        interestingSegments.sort(cmp, lambda x: x.start)

        # Next, I collect all the annotations which are in each segment.
        # Remember, the reconciliation doc doesn't appear to have access
        # to the annotation type category.

        def _getSegmentAnnots(interestingSegments, doc):
            curSegIndex = 0
            curSeg = interestingSegments[0]
            segAnnots = []

            # In this loop, we want to find all annotations which OVERLAP
            # with the segment. In the reconciliation doc, there will be
            # no boundary overlap, but when we get back to the source
            # documents, there might be, and otherwise, the algorithm is the same.

            for a in doc.orderAnnotations(task.getAnnotationTypesByCategory("content")):
                done = False
                while a.start >= curSeg.end:
                    if curSegIndex == len(interestingSegments) - 1:
                        # Out of segments.
                        done = True
                        break
                    curSegIndex += 1
                    curSeg = interestingSegments[curSegIndex]
                if done:
                    break
                elif a.end <= curSeg.start:
                    continue
                else:
                    # Found one. a.start < curSeg.end and a.end > curSeg.start.
                    segAnnots.append(a)
            return segAnnots

        segAnnots = []
        for v in winningVotes:
            aIds = _getListValue(v, "content")
            if (len(aIds) != 1) or (aIds[0] not in SPECIAL_VOTE_VALUES):
                for id in aIds:
                    segAnnots.append(recDoc.getAnnotationByID(id))

        # Now, I want to look at each source doc.
        # I want to remove all content annotations that overlap the
        # segment specified, and I want to ensure that the segment
        # boundaries are respected, and I want to collapse adjacent
        # segments with the same owners, and I want to insert copies
        # of the annotations into the source document.

        # Note that what will happen here with "ignore" (which can
        # win a vote) is that all annotations will be removed
        # from that region. "bad boundaries" will never be a winning
        # vote. But "ignore" is a winning vote, and it has to be
        # noted in the target docs.

        for sourceDoc in sourceDocs:
            # We want to remove all annotations which overlap any of the
            # affected segments. We can use the interestingSegments list
            # here, since we're only using the offsets and the offsets
            # are the same. (Originally, I'd written _getSegmentAnnots
            # for another purpose, but the only application left now is here).
            if interestingSegments:
                sourceAnnots = _getSegmentAnnots(interestingSegments, sourceDoc)
                # Remove all these.
                for a in sourceAnnots:
                    print >> verbose, "Removing annotation", a.atype.lab, a.start, a.end
                sourceDoc.removeAnnotationGroup(sourceAnnots)
                # Add copies of all the ones we found.
                for a in segAnnots:
                    print >> verbose, "Adding annotation", a.atype.lab, a.start, a.end
                sourceDoc.importAnnotationGroup(segAnnots)

            # Now, we have to loop through all the segments in this document.
            sourceSegs = sourceDoc.orderAnnotations(["SEGMENT"])
            # The idea is that we want to preserve annotator attribution - importing
            # the annotators from the reconciled segments is kind of pointless
            # because the whole point of the reconciliation is to involve
            # lots of people. So the annotator attribute will be for core
            # annotation, not for reconciliation. We want to loop through
            # and concatenate adjacent segments with the same status and annotator.

            # But this is too hard to do all at the same time. So first,
            # we collect all the indexes, with what annotations are
            # starting or ending.
            # Elements in the dictionary are segstart, segend, entering rec/status,
            # exiting rec.

            segDict = {}
            for seg in sourceSegs:
                try:
                    segDict[seg.start][0] = seg
                except:
                    segDict[seg.start] = [seg, None, None, None]
                try:
                    segDict[seg.end][1] = seg
                except:
                    segDict[seg.end] = [None, seg, None, None]
            for seg in allSegments:
                statusToIssue = (((seg in segmentsToIgnore) and "ignore") or "reconciled")
                try:
                    segDict[seg.start][2] = statusToIssue
                except:
                    segDict[seg.start] = [None, None, statusToIssue, None]
                try:
                    segDict[seg.end][3] = True
                except:
                    segDict[seg.end] = [None, None, None, True]

            indices = segDict.keys()
            indices.sort()

            # Now, what do I do with this data? The easiest thing
            # would be to completely reconstruct the segment
            # annotations of the source document. Let's do that.

            inRec = None

            annotSpecs = []
            # start, end, status, annotator
            curSpec = None
            inSeg = None

            for i in indices:
                [segStart, segEnd, recEnterStatus, recExit] = segDict[i]
                print >> verbose, "Seg dict", i, segDict[i]
                if segEnd:
                    # Don't care about reconciliation exit or not.
                    curSpec[1] = segEnd.end
                    curSpec = None
                    inSeg = None
                    # If we're also exiting reconciliation, set it
                    # to false.
                    if recExit:
                        inRec = None
                        # Turn it off, because we're going to
                        # consult it again in a moment.
                        recExit = False
                # Now the slate is clean.
                if segStart:
                    inSeg = segStart
                    curSpec = [segStart.start, segStart.end,
                               set(_getListValue(segStart, "annotator")),
                               segStart.get("status")]
                    if inRec or recEnterStatus:
                        curSpec[3] = inRec or recEnterStatus
                        inRec = recEnterStatus
                    if annotSpecs and (annotSpecs[-1][3] == curSpec[3]) and \
                       (annotSpecs[-1][2] == curSpec[2]):
                        curSpec = annotSpecs[-1]
                    else:
                        annotSpecs.append(curSpec)
                elif recExit or recEnterStatus:

                    # Now, if we're not at a segment start, but we're
                    # exiting and/or entering reconciliation, make the
                    # same calculation.

                    # If we're both exiting and entering, and the
                    # new enter status is the same as the old, nothing needs to happen.

                    if recExit and recEnterStatus and (recEnterStatus == inRec):
                        continue

                    else:
                        # First, end the current segment here. We'd better
                        # damn well be in a segment, but just in case...
                        if curSpec:
                            curSpec[1] = i
                            curSpec = None

                        if inSeg:
                            # Now, we create a new segment. We'd better
                            # damn well be in a segment, but just in case...

                            # This can all probably be optimized, but I'm
                            # preferring the explicit version.
                            if recEnterStatus:
                                inRec = recEnterStatus
                                curSpec = [i, inSeg.end,
                                           set(_getListValue(inSeg, "annotator")),
                                           recEnterStatus]
                                if annotSpecs and (annotSpecs[-1][3] == curSpec[3]) and \
                                       (annotSpecs[-1][2] == curSpec[2]):
                                    curSpec = annotSpecs[-1]
                                else:
                                    annotSpecs.append(curSpec)
                            else:
                                inRec = None
                                curSpec = [i, inSeg.end,
                                           set(_getListValue(inSeg, "annotator")),
                                           inSeg.get("status")]
                                if annotSpecs and (annotSpecs[-1][3] == curSpec[3]) and \
                                       (annotSpecs[-1][2] == curSpec[2]):
                                    curSpec = annotSpecs[-1]
                                else:
                                    annotSpecs.append(curSpec)

            print >> verbose, "Annot specs", annotSpecs
            # Now, remove all the segment annotations, and reconstruct.
            segType = sourceDoc.findAnnotationType("SEGMENT")
            # Make sure to copy the list, because orderAnnotations may
            # not copy.
            sourceDoc.removeAnnotationGroup(sourceSegs[:])

            for [start, end, annotators, status] in annotSpecs:
                # It may have the empty string in it.
                annotators.discard("")
                sourceDoc.createAnnotation(start, end, segType,
                                           {"status": status,
                                            "annotator": ",".join(annotators)})
                # And we're done.

    def _votesForSegments(self):
        docObj = self
        d = {}
        for v in docObj.getAnnotations(["VOTE"]):
            try:
                d[v["segment"]].append(v)
            except KeyError:
                d[v["segment"]] = [v]
        return d

    def _allSegmentsReconciled(self):
        docObj = self
        for a in docObj.getAnnotations(["SEGMENT"]):
            if a["status"] == "human gold":
                return False
        # human gold is the only one that can mess us up.
        return True

# No reason to have to find this function as a method every time it's run.

def _getListValue(a, key):
    v = a.get(key)
    if not v:
        return []
    else:
        return v.split(",")
