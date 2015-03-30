# Copyright (C) 2007 - 2012 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# SAM 6/12/12: I've moved the document pairer into its own file.

# SAM 5/9/12: Added initial support for doing alignment via Kuhn-Munkres.

from munkres import Munkres, make_cost_matrix

import MAT.Document
from MAT.Annotation import AnnotationAttributeType

#
# Utilities.
#

class PairingError(Exception):
    pass

# Track, in a dictionary, whether something is a content tag or not.

def _cacheContentType(contentDict, atype, task, contentAnnotations, tokenAnnotations):
    label = atype.lab
    if not contentDict.has_key(label):
        contentDict[label] = [atype.hasSpan, None]
        if task:
            contentDict[label][1] = task.getCategoryForLabel(label)
        elif contentAnnotations and label in contentAnnotations:
            contentDict[label][1] = "content"
        elif tokenAnnotations and label in tokenAnnotations:
            contentDict[label][1] = "token"
    elif contentDict[label][0] != atype.hasSpan:
        raise PairingError, ("label '%s' is both spanned and spanless in the label cache" % label)
    return contentDict[label][1]

def checkContentTag(contentDict, label, task, contentAnnotations = None, tokenAnnotations = None):
    return _cacheContentType(contentDict, label, task, contentAnnotations, tokenAnnotations) == "content"

def checkLexTag(contentDict, label, task, contentAnnotations = None, tokenAnnotations = None):
    return _cacheContentType(contentDict, label, task, contentAnnotations, tokenAnnotations) == "token"    

#
# PAIRING
#

# I'm going to use the Kuhn-Munkres algorithm as the basis for my annotation pairing.
# It will be enhanced in a number of ways.

# First, we're going to have similarity profiles which describe the
# dimensions which are going to contribute to the similarity, and
# the weights assigned to each value, and the pairing method we'll use.
# Ultimately, this will be XML-declarable in the task.xml file. But right
# now, we'll just ask the task. We'll have declared methods for
# the various attribute types and dimensions, and the possibility
# of defining your own. We'll allow each dimension to return a set
# of error tokens, which will be accumulated to indicate how many times an error
# of that type is encountered. You'll have the possibility of
# multiple errors for a given mismatch. For sets, we'll use (2 x intersection) / size(set1) + size(set2),
# and for lists, we'll do the same with the longest common subsequence instead of
# the intersection. We'll have to adjust that for some of the more
# complex equality operations; I may need to do Kuhn-Munkres with the equality
# operation, in fact.

# Second, we're going to stratify the pairing. Because I need to use pairing information between
# annotations during computation of the contribution of annotation-valued attributes,
# the types which are pointed to must be paired before the types that point to them.
# Note that this is a TYPE-level operation, not an instance-level evaluation; if
# the FOO tag is a label restriction on the BAR attribute of the BAZ tag,
# even if no FOOs are ever values of the BAR attribute, FOOs must be paired first.
# This means that we have to have strata defined. We could deduce them, but
# that might not cohere with the user intent, and I want to force the user to
# realize that if FOO and BAZ are in different strata, they CAN'T pair with
# each other, even if they overlap. And you could imagine a scenario where the
# user wishes to force the possible pairing, even if it means using
# unstable scoring (next bullet).

# Third, we're going to have the possibility of unstable scoring. If
# annotation values are compared before they're paired, we'll have a fallback
# scoring mechanism which is unstable - it may reflect similarities contributing
# to the pairing, but between annotations which will ultimately not be paired.

# Fourth, we're going to have to watch explicitly for cycles - if you're
# comparing two annotations, and you encounter that pair again while you're
# comparing it, the second comparison should either contribute a 0 similarity
# or raise an error. Not sure what the right thing to do here is; raise an
# error until we figure it out.

# Fifth, we're going to need some sort of fallback in the case of more than
# two documents. We can't do the n-wise pairing, so we'll need a "pivot" document,
# which can be arbitrarily chosen, I suppose, to which all the other
# documents will be compared. But in the case where the pairs relate to a spurious
# element in the non-pivot, we'll have elements which might be reconcilable with
# EACH OTHER which result in separate pairwise spurious relations. I'm
# not sure what to do about that; should I start iterating through the
# other documents and try to "swallow" the spurious elements? Not sure.

# First step: refactor the scorer to have a separate pairer. The inputs that are
# relevant to the pairer are:

# task
# contentAnnotations
# tokenAnnotations
# equivalenceClasses
# labelsToIgnore

# For each document, when we add it, we need to specify, perhaps, which segments
# are pairable.

# If there's no task, we use the default similarity for the spanned or spanless
# annotation.

# So here's the thing about equivalence classes: you can only use them when
# determining the value of the label dimension - never when you're choosing
# the similarity. The similarity always works on the true label anyway.

class PairState:

    def __init__(self, task = None, contentAnnotations = None,
                 tokenAnnotations = None, equivalenceClasses = None,
                 labelsToIgnore = None, similarityProfile = None,
                 skipTokens = False):
        self.task = task
        self.contentAnnotations = contentAnnotations
        self.tokenAnnotations = tokenAnnotations
        self.equivalenceClasses = equivalenceClasses
        self.labelsToIgnore = (labelsToIgnore and set(labelsToIgnore)) or None
        if labelsToIgnore and equivalenceClasses:
            for lab in labelsToIgnore:
                if equivalenceClasses.has_key(lab):
                    print "Ignoring label '%s' in equivalence classes" % lab
                    del equivalenceClasses[lab]
        self.contentTags = {}
        self.simEngine = SimilarityEngine(self, similarityProfile = similarityProfile)
        # For each document tuple added in addDocumentTuples (minus the
        # ones that are skipped because the signals don't match), we
        # create a final entry. If there are more than two docs in each
        # tuple, we'll do the postprocessing to unify the pairs.
        self.numDocs = None
        self.resultEntries = []
        self.skipTokens = skipTokens
        # See _computeImpliedSpan.
        self.impliedSpans = {}

    # Each element in the list of tuples is a n-ary list of
    # pairs: each pair is (filename, doc). Each entry in the list must
    # be the same length. If segFilters is not None, it must be the same length
    # as the entries, and must be a function which filters the segments in the
    # corresponding doc.

    # We also assume that the "pivot" document is the first document in each
    # tuple.
    
    def addDocumentTuples(self, tupleList, segFilters = None):
        # Not sure who'd pass an empty tuple list, but it shouldn't break.
        if not tupleList:
            return
        if self.numDocs is None:
            self.numDocs = len(tupleList[0])
            # Temporary blockage.
            if self.numDocs > 2:
                raise PairingError, "Pairer doesn't work yet with more than two documents; stay tuned."
        for elt in tupleList:
            if len(elt) != self.numDocs:
                raise PairingError, "Not all document comparisons have the same number of documents"
        if (segFilters is not None) and (len(segFilters) != self.numDocs):
            raise PairingError, "Number of segment filters differs from the number of documents in the comparisons"

        # 8/11/08: We need a very, very different algorithm for computing
        # this information, because of how we need to align the overlapping
        # but not matching elements. We also need to collect token-level
        # numbers. So once we determine it's the same document, we need to
        # separate lex tags from content tags, sort both, and number the lex tags,
        # indexed by start and end indexes (so we can figure out how many
        # tokens are covered by an annotation). Then we need to walk through
        # the context tags for one document, comparing them point by point
        # with annotations from the other document, classifying them according
        # to one of the six bins described above.

        # Of course, sometimes we don't have tokens, in which case
        # (a) we can't report token-level scores, and (b) we can't use
        # the token indices to root the content tags.

        # Finally, if there's a task, we should really use the zone annotations
        # in the reference document as a filter on what we should score.

        if self.task:
            annotLabeler = lambda ann: self.task.getEffectiveAnnotationLabel(ann, useExtraDistinguishingAttributes = True,
                                                                             restrictToCategory = "content")
        else:
            annotLabeler = lambda ann: ann.atype.lab
            
        if self.equivalenceClasses:
            coreAnnotLabeler = annotLabeler
            def annotLabeler(ann):
                lab = coreAnnotLabeler(ann)
                return self.equivalenceClasses.get(lab, lab)            

        # Check for signals matching.
        finalTupleList = []
        for tpl in tupleList:
            sig = tpl[0][1].signal
            sigsMatch = True
            for file, doc in tpl:
                if doc.signal != sig:
                    sigsDontMatch = False
                    break                
            if not sigsMatch:
                print "Signals don't match among documents %s; skipping." % ", ".join([t[0] for t in tuple])
            else:
                finalTupleList.append(tpl)
            
        # For some reason, I think because I only want to compute the true task zone
        # info once, I call processableRegions on whole bunches of documents.

        # Now, if there are no segFilters above, then we don't need to filter the annotations.
        # If there ARE seg filters, we should get the processable regions
        # of the first doc if there WERE no seg filters, and in that case, see if each region list
        # for each doc is the same as the bare one. If it is, then every doc is zoned the same
        # way and everything's used; otherwise, we can't pair spanless annotations, because we
        # don't know which ones "appear" in those zones.

        # Well, nothing is every THAT simple. I STILL have to filter by the zones,
        # in case there are perversely annotations outside the zones which should be
        # ignored. But I DO need to know whether regions were limited or not.

        firstFilterList = MAT.Document.AnnotatedDoc.processableRegions([tpl[0][1] for tpl in finalTupleList],
                                                                       task = self.task)
        # I need this for spanless annotations, maybe. We'll use the
        # same maxRegion for each document in each tuple.
        maxRegionHash = {}
        for i in range(self.numDocs):
            maxRegionHash.update(dict([(d, (firstFilter[0][0], firstFilter[-1][1]))
                                       for (d, firstFilter)
                                       in zip([tpl[i][1] for tpl in finalTupleList], firstFilterList)]))
        if segFilters is None:
            filterRegionList = [(f, False) for f in firstFilterList]
        else:
            # Slice this by columns, so we can pass in a single segment filter function.
            regionColumnLists = [MAT.Document.AnnotatedDoc.processableRegions([tpl[i][1] for tpl in finalTupleList], task = self.task,
                                                                              segmentFilterFn = segFilters[i])
                                 for i in range(self.numDocs)]
            filterRegionList = []
            for j in range(len(finalTupleList)):
                tpl = finalTupleList[j]
                firstFilter = firstFilterList[j]
                regionFilters = [elt[j] for elt in regionColumnLists]
                changedFilter = self._reduceFilters(firstFilter, regionFilters)
                if changedFilter:
                    filterRegionList.append((changedFilter, True))
                else:
                    filterRegionList.append((firstFilter, False))
            
        for j in range(len(tupleList)):
            regionFilters, filterChanged = filterRegionList[j]
            self._addDocumentTuple(tupleList[j], annotLabeler, regionFilters, filterChanged, maxRegionHash)

    # Here, I see if the region filters are all identical to the first
    # filter, and if they are, I return None, because we don't need to
    # filter. If at any point, the lists differ, I return the actual region list,
    # which is the intersection of all the region filters.
    
    def _reduceFilters(self, firstFilter, regionFilters):

        filterChanged = False
        pivotRegions = firstFilter
        for otherRegions in regionFilters:
            if pivotRegions == otherRegions:
                continue
            else:
                filterRegions = []
                filterChanged = True
                # Merge the ref and hyp regions. The algorithm is pretty simple. Both the lists
                # will be in order. In each case, we loop while pivotRegions and otherRegions
                # are both present. If one ends before the other, discard it.
                # If the start of one precedes the other, move the
                # earlier one forward. If they start at the same point, find the
                # earliest end and add that as a region. Discard the shorter one
                # and move the start index of the longer one.
                while pivotRegions and otherRegions:
                    if pivotRegions[0][1] <= otherRegions[0][0]:
                        pivotRegions[0:1] = []
                    elif otherRegions[0][1] <= pivotRegions[0][0]:
                        otherRegions[0:1] = []
                    elif otherRegions[0][0] < pivotRegions[0][0]:
                        otherRegions[0][0] = pivotRegions[0][0]
                    elif pivotRegions[0][0] < otherRegions[0][0]:
                        pivotRegions[0][0] = otherRegions[0][0]
                    elif pivotRegions[0][1] < otherRegions[0][1]:
                        # They start at the same point, but ref ends earlier.
                        filterRegions.append((pivotRegions[0][0], pivotRegions[0][1]))
                        otherRegions[0][0] = pivotRegions[0][1]
                        pivotRegions[0:1] = []
                    elif otherRegions[0][1] < pivotRegions[0][1]:
                        # They start at the same point, but hyp ends earlier.
                        filterRegions.append((otherRegions[0][0], otherRegions[0][1]))
                        pivotRegions[0][0] = otherRegions[0][1]
                        otherRegions[0:1] = []
                    else:
                        # They start and end at the same point.
                        filterRegions.append((pivotRegions[0][0], pivotRegions[0][1]))
                        pivotRegions[0:1] = []
                        otherRegions[0:1] = []
                pivotRegions = filterRegions
        if filterChanged:
            return pivotRegions
        else:
            # We don't need a filter, because the firstFilter is the filter
            # without segfilters, and represents the whole doc.
            return None

    def _addDocumentTuple(self, tpl, annotLabeler, filterRegions, filterChanged, maxRegionHash):
        
        ref, rDoc = tpl[0]
        
        # This will be a list of pairs (spannedList, spanlessList) of annotations
        # from the doc. This will
        # be assured of being the same length as the hypStrata below;
        # if there's no strata declared, there will be one stratum, and
        # if there are strata declared, they'll be applied to both docs.

        refStrata = self.simEngine.getDocStrata(rDoc, filterChanged)
        # You can't filter spanless annotations. Actually, you can, by computing their
        # implied regions.
        filteredSpanned, filteredSpanless = self.filterByRegions(filterRegions, spannedLists = [p[0] for p in refStrata],
                                                                 spanlessLists = [p[1] for p in refStrata],
                                                                 maxRegionHash = maxRegionHash)
        refStrata = zip(filteredSpanned, filteredSpanless)

        finalRefStrata = []
        for rSpanContent, rSpanlessContent in refStrata:
            rSpanContent = [(annotLabeler(ann), ann) for ann in rSpanContent]
            rSpanlessContent = [(annotLabeler(ann), ann) for ann in rSpanlessContent]
            if self.labelsToIgnore:
                rSpanContent = [(lab, ann) for (lab, ann) in rSpanContent if lab not in self.labelsToIgnore]
                rSpanlessContent = [(lab, ann) for (lab, ann) in rSpanlessContent if lab not in self.labelsToIgnore]
            finalRefStrata.append((rSpanContent, rSpanlessContent))
        
        finalPairLists = []
        finalTokPairLists = []
        
        for target, tDoc in tpl[1:]:

            pairs = []
            finalPairLists.append(pairs)
            pairsTokLevel = []
            finalTokPairLists.append(pairsTokLevel)
            
            hStrata = self.simEngine.getDocStrata(tDoc, filterChanged)

            # Use the new processableRegions method to retrieve all the
            # useable annotations. By default, everything is used, but we should
            # be able to filter on gold annotations.

            filteredSpanned, filteredSpanless = self.filterByRegions(filterRegions, spannedLists = [p[0] for p in hStrata],
                                                                     spanlessLists = [p[1] for p in hStrata],
                                                                     maxRegionHash = maxRegionHash)
            hStrata = zip(filteredSpanned, filteredSpanless)

            for (rSpanContent, rSpanlessContent), (hSpanContent, hSpanlessContent) in zip(finalRefStrata, hStrata):
                    
                hSpanContent = [(annotLabeler(ann), ann) for ann in hSpanContent]
                hSpanlessContent = [(annotLabeler(ann), ann) for ann in hSpanlessContent]
                if self.labelsToIgnore:
                    hSpanContent = [(lab, ann) for (lab, ann) in hSpanContent if lab not in self.labelsToIgnore]
                    hSpanlessContent = [(lab, ann) for (lab, ann) in hSpanlessContent if lab not in self.labelsToIgnore]

                self._addDocumentTupleStratum(rSpanContent, hSpanContent, True, pairs, pairsTokLevel)
                self._addDocumentTupleStratum(rSpanlessContent, hSpanlessContent, False, pairs, pairsTokLevel)

        self._integratePairs(tpl, filterRegions, finalPairLists, finalTokPairLists)

    def _addDocumentTupleStratum(self, rContent, hContent, isSpan, pairs, pairsTokLevel):

        if not (rContent or hContent):
            return

        # What about overlaps and multiple spans on each side? The original
        # algorithm didn't take that into account. In fact, the way it's sorted
        # in multiple places clearly shows that all sorts of things would
        # break.

        # Tokens are going to be the same in both docs, so
        # I only need to analyze one of them. But I only need to
        # do this if the tokens are being collected. And if either
        # the reference or the hypothesis doesn't have tokens, we
        # shouldn't try, because it'll break and we don't
        # have tokens.

        # GAAAA. I have to make sure that whatever pairing I
        # apply for the tags applies to the tokens as well. So
        # the token algorithm has to change, completely. Ditto
        # for the pseudo-tokens and characters. EVERYTHING
        # starts with the annotation pairings. 

        # We'll collect triples of (ref, hyp, status),
        # where status is one of "match", "tagclash", "undermark", "overmark",
        # "tagplusundermark", "tagplusovermark", "overlap",
        # "missing", "spurious". We'll loop through the ref, since
        # we have no reason to pick one or the other. In some cases, we have to
        # do this from the point of view of one side or the other.
        # updateTagDetail() does it from the point of view of the hypothesis.

        # In order to do this by tag, I have to subdivide the
        # results by tag.

        # We're going to collect both character counts and pseudo-tokens (see below).

        thesePairs = self._pairAnnotations(rContent, hContent, isSpan = isSpan)
        pairs += thesePairs

        # print [(label, (ann and ann.start), (ann and ann.end), hLabel,
        #        (hAnn and hAnn.start), (hAnn and hAnn.end), refMatchStatus, hypMatchStatus)
        #       for [label, ann, refMatchStatus, hLabel, hAnn, hypMatchStatus] in pairs]

        if isSpan and (not self.skipTokens):
            self._pairTokenSpans(thesePairs, pairsTokLevel)

    def _pairTokenSpans(self, pairs, pairsTokLevel):
        # OK. Easy case first. Let's process the tag-level pairs. And, at the same time,
        # collect the appropriate intervals for the token level. I need to do
        # another round of pairing up on the non-overlapping sections, because
        # things like this should be fine at the token level:

        # ref: <TAG>a b c d</TAG>
        # hyp: <TAG>a b</TAG> <TAG>c d</TAG>

        # Don't forget: only the spanned annotations should be processed on
        # the token level. Let's collect the misbehaving partial spans for
        # later computation.

        missingTokLevel = []
        spuriousTokLevel = []
        # This is a list where the entries are even longer than the pairs:
        # [rLab, rAnn, rStatus, hLab, hAnn, hStatus, start, end]
        # I'll need this as I move to more elaborate scoring.

        remainingTokIndexes = set()
        
        for [label, ann, refMatchStatus, hLabel, hAnn, hypMatchStatus] in pairs:
            hEntry = (hLabel, hAnn)
            if refMatchStatus == "missing":
                missingTokLevel.append((label, ann, ann.start, ann.end))
                remainingTokIndexes.update([ann.start, ann.end])
            elif hypMatchStatus == "spurious":
                spuriousTokLevel.append((hLabel, hAnn, hAnn.start, hAnn.end))
                remainingTokIndexes.update([hAnn.start, hAnn.end])
            else:
                # Ultimately, we want to be able to report all counts. But what
                # should the report look like for the clash cases? I need
                # a couple of different categories: "refclash" and "hypclash".
                # "spanclash" gets one of each on the given tag;
                # the other clashes get one of each on the corresponding
                # tag.
                if ann.start < hAnn.start:
                    missingTokLevel.append((label, ann, ann.start, hAnn.start))
                    remainingTokIndexes.update([ann.start, hAnn.start])
                elif ann.start > hAnn.start:
                    spuriousTokLevel.append((hLabel, hAnn, hAnn.start, ann.start))
                    remainingTokIndexes.update([hAnn.start, ann.start])
                if ann.end > hAnn.end:
                    missingTokLevel.append((label, ann, hAnn.end, ann.end))
                    remainingTokIndexes.update([hAnn.end, ann.end])
                elif ann.end < hAnn.end:
                    spuriousTokLevel.append((hLabel, hAnn, ann.end, hAnn.end))
                    remainingTokIndexes.update([ann.end, hAnn.end])
                # I used to be able to make some assertion about the
                # match status of the spans in the overlap, but no
                # longer, with the new profiles - they have to
                # go through the same matching as all the others.
                pairsTokLevel += self._pairRemainingTokSpans(max(hAnn.start, ann.start), min(hAnn.end, ann.end), [[label, ann]], [[hLabel, hAnn]])

        # Now, let's do the tokens. The way we do this is we create a
        # mapping from the token starts and ends to its interval. Then, we can
        # figure out what to add for each pair.

        # At the same time, we can do the pseudo-tokens and the characters,
        # because they're all span-free.

        # But I also need to do the accumulations for pseudotag and character counts. Note the
        # comment above; these:

        # ref: <TAG>a b c d</TAG>
        # hyp: <TAG>a b</TAG> <TAG>c d</TAG>

        # should score perfectly. Because the phrase-level loop pairs annotations,
        # I have to do collection ONLY during the loop, and then update the accumulation dictionaries
        # afterward. The collection can be the same for both pseudotag and character, and is just
        # the relevant indices and then what label was found in the ref and content.

        # What this means is that I can't just go through the pairs as is, because
        # they will fail in the case above. I need to maintain the label pairs,
        # because they need to be consistent with the tag level scoring; but the span
        # boundaries need to be erased before anything else happens.

        # What this amounts to is that I need to regenerate the intervals, but
        # I need to take spurious and missing, AFTER I'VE FIGURED OUT THE PORTIONS
        # THAT CORRESPOND TO THEM, and pair THEM up.

        # Do these need to be paired differently for tokens and pseudo tokens and
        # characters? At one point, I recognized that I needed to strip whitespace
        # from the edges of pseudo tokens to pair them up correctly, but not from
        # characters.

        # Yeah. Here's the problem:
        # ref: <TAG>a b c d</TAG>
        # hyp: <TAG>a b</TAG> <TAG>c d e</TAG>

        # If I pair them, the second ref is missing - but if I work
        # through the pairs, rather than the annotation indices, I'll never be able
        # to match the remainders. I thought maybe I'd have to do tokens separately,
        # but I think if at any point, I can't find a token boundary for the annotation
        # boundary, I'll bail on token scoring.

        # So we have to do another round of pairing. Do I try to use _pairAnnotations?
        # I think not. The fit is not great. I need first to segment the regions
        # I've collected based on the available indices. In each region, I perform
        # my pairing algorithm.

        remainingTokIndexes = list(remainingTokIndexes)
        remainingTokIndexes.sort()

        # Can't use enumerate() because the mapping needs to be reversed.
        tokIdxMapping = {}
        j = 0
        for i in remainingTokIndexes:
            tokIdxMapping[i] = j
            j += 1

        # Mapping from intervals to label-annotation pairs.
        intervals = {}
        for lab, ann, start, end in missingTokLevel:
            allIndexes = remainingTokIndexes[tokIdxMapping[start]:tokIdxMapping[end] + 1]
            i = 1
            while i < len(allIndexes):
                intvl = (allIndexes[i - 1], allIndexes[i])
                try:
                    intervals[intvl][0].append((lab, ann))
                except KeyError:
                    intervals[intvl] = [(lab, ann)], []
                i += 1

        for lab, ann, start, end in spuriousTokLevel:
            allIndexes = remainingTokIndexes[tokIdxMapping[start]:tokIdxMapping[end] + 1]
            i = 1
            while i < len(allIndexes):
                intvl = (allIndexes[i - 1], allIndexes[i])
                try:
                    intervals[intvl][1].append((lab, ann))
                except KeyError:
                    intervals[intvl] = [], [(lab, ann)]
                i += 1

        # Now, pair the remaining spans.

        for (start, end), (rEntries, hEntries) in intervals.items():
            pairsTokLevel += self._pairRemainingTokSpans(start, end, rEntries, hEntries)

    def _integratePairs(self, t, filterRegions, finalPairLists, finalTokPairLists):
        if (len(finalPairLists) == 1) and (len(finalTokPairLists) == 1):
            finalPairs = finalPairLists[0]
            finalTokPairs = finalTokPairLists[0]
        else:
            raise PairingError, "Can't integrate pairs from more than two documents"
        # The filter regions are needed downstream in the scorer.
        self.resultEntries.append({"pairs": finalPairs, "tokenPairs": finalTokPairs, "tuple": t, "filterRegions": filterRegions})

    # entries are refstart, refend, hstart, hend

    @staticmethod
    def _buildIndexTable(rContent, hContent, startEndTbl):

        indexTbl = {}
        for label, ann in rContent:
            start, end = startEndTbl[ann]
            try:
                indexTbl[start][0].append((label, ann))
            except KeyError:
                indexTbl[start] = [[(label, ann)], [], [], []]
            try:
                indexTbl[end][1].append((label, ann))
            except KeyError:
                indexTbl[end] = [[], [(label, ann)], [], []]

        for label, ann in hContent:
            start, end = startEndTbl[ann]
            try:
                indexTbl[start][2].append((label, ann))
            except KeyError:
                indexTbl[start] = [[], [], [(label, ann)], []]
            try:
                indexTbl[end][3].append((label, ann))
            except KeyError:
                indexTbl[end] = [[], [], [], [(label, ann)]]

        # OK, all sorted by indexes.

        allIndices = indexTbl.keys()
        allIndices.sort()

        return indexTbl, allIndices

    # Kuhn-Munkres algorithm. The idea is that we find all the annotations
    # which are overlap chunks: contiguous spans where the "cover count" remains > 0.
    # Then if the r dimension is empty, they're missing; if h is empty, they're spurious;
    # if it's one-to-one, pair them; otherwise, run Kuhn-Munkres.

    # If they're spanless, we compute the start and end spans by
    # finding the implied extent of the annotation, by looking at the
    # first start and last end of the annotations they point to.
    # If that fails, they have to match by label, and THOSE
    # are paired.

    def _pairAnnotations(self, rContent, hContent, isSpan = True):

        pairs = []
            
        if isSpan:

            self._pairSpannedAnnotations(rContent, hContent, pairs,
                                         dict([(a, (a.start, a.end)) for (lab, a) in rContent] + \
                                              [(a, (a.start, a.end)) for (lab, a) in hContent]))

        else:
            impliedSpanRContent = []
            impliedSpanHContent = []                
            # From labels to accumulated reference and hypothesis.
            labDict = {}
            startEndTbl = {}
            
            for lab, ann in rContent:
                start, end = self._computeImpliedSpan(ann, self.impliedSpans)
                if start is None:
                    try:
                        labDict[ann.atype.lab][0].append((lab, ann))
                    except KeyError:
                        labDict[ann.atype.lab] = ([(lab, ann)], [])
                else:
                    impliedSpanRContent.append((lab, ann))
                    startEndTbl[ann] = (start, end)

            for lab, ann in hContent:
                start, end = self._computeImpliedSpan(ann, self.impliedSpans)
                if start is None:
                    try:
                        labDict[ann.atype.lab][1].append((lab, ann))
                    except KeyError:
                        labDict[ann.atype.lab] = ([], [(lab, ann)])
                else:
                    impliedSpanHContent.append((lab, ann))
                    startEndTbl[ann] = (start, end)

            if impliedSpanRContent or impliedSpanHContent:
                self._pairSpannedAnnotations(impliedSpanRContent, impliedSpanHContent, pairs, startEndTbl)

            for lab, (accumRef, accumHyp) in labDict.items():                
                pairs += self._pairAnnotationsAtInterval(accumRef, accumHyp)

        return pairs

    def _pairSpannedAnnotations(self, rContent, hContent, pairs, startEndTbl):

        indexTbl, allIndices = self._buildIndexTable(rContent, hContent, startEndTbl)

        curRef = set()
        curHyp = set()
        accumRef = []
        accumHyp = []

        for i in allIndices:
            [rStart, rEnd, hStart, hEnd] = indexTbl[i]
            preSize = len(curRef) + len(curHyp)
            if rEnd:
                curRef -= set(rEnd)
            if hEnd:
                curHyp -= set(hEnd)
            if (not curRef) and (not curHyp) and (preSize > 0):
                pairs += self._pairAnnotationsAtInterval(accumRef, accumHyp)
                accumRef = []
                accumHyp = []
            if rStart:
                accumRef += rStart
                curRef |= set(rStart)
            if hStart:
                accumHyp += hStart
                curHyp |= set(hStart)

    # This is used for the spanless annotations.
    @classmethod
    def _computeImpliedSpan(cls, a, impliedSpans):
        if a.atype.hasSpan:
            return (a.start, a.end)
        else:
            try:
                return impliedSpans[a]
            except KeyError:
                start = end = None
                for attrObj, val in zip(a.atype.attr_list, a.attrs):
                    if (attrObj._typename_ == "annotation") and (val is not None):
                        if not attrObj.aggregation:
                            thisStart, thisEnd = cls._computeImpliedSpan(val, impliedSpans)
                            if (start is None) or (thisStart < start):
                                start = thisStart
                            if (end is None) or (thisEnd > end):
                                end = thisEnd
                        else:
                            for subval in val:
                                thisStart, thisEnd = cls._computeImpliedSpan(subval, impliedSpans)
                                if (start is None) or (thisStart < start):
                                    start = thisStart
                                if (end is None) or (thisEnd > end):
                                    end = thisEnd
                # Might be (None, None)
                impliedSpans[a] = (start, end)
                return (start, end)
    
    def _pairAnnotationsAtInterval(self, accumRef, accumHyp, duringTokenRemainder = False):
        if not accumHyp:
            return [[lab, ann, "missing", None, None, None] for (lab, ann) in accumRef]
        elif not accumRef:
            return [[None, None, None, lab, ann, "spurious"] for (lab, ann) in accumHyp]
        else:
            if (len(accumHyp) == 1) and (len(accumRef) == 1):
                hLab, hAnn = accumHyp[0]
                rLab, rAnn = accumRef[0]
                # They pair with each other, but we definitely need to compute
                # their similarity.
                r, dimSim, errToks = self.simEngine.computeSimilarity(accumRef[0], accumHyp[0],
                                                                      useTokenSimilarity = duringTokenRemainder)
                # If their similarity is 0, we don't actually care - these things
                # MUST pair with each other. Actually, when we run
                # Kuhn-Munkres, we make these missing and spurious, so
                # we should do the same here. But we have to be sure that
                # in the token case, the span counts as matching.
                if r == 0:
                    return [[rLab, rAnn, "missing", None, None, None],
                            [None, None, None, hLab, hAnn, "spurious"]]
                else:
                    rStatus, hStatus = self._computePairStatuses(r, errToks)
                    if not duringTokenRemainder:
                        self.simEngine.recordPair(rAnn, hAnn)
                    return [[rLab, rAnn, rStatus, hLab, hAnn, hStatus]]
            else:
                # Run Kuhn-Munkres. 
                return self._kuhnMunkres(accumRef, accumHyp,
                                         duringTokenRemainder = duringTokenRemainder)

    def _kuhnMunkres(self, accumRef, accumHyp, duringTokenRemainder = False):
        # one row for each item in the accumRef, one column for each item in
        # accumHyp. Compute similarity for each pair. Note that the computeSimilarity
        # method returns a triple, and in the cost matrix, I only want the first value.
        computeSimilarity = self.simEngine.computeSimilarity
        matrix = make_cost_matrix([[computeSimilarity(r, h,
                                                      useTokenSimilarity = duringTokenRemainder)[0] for h in accumHyp]
                                   for r in accumRef],
                                  lambda cost: 1.0 - cost)
        newPairs = []
        # If accumRef and accumHyp are not the same length, some of them might
        # not be matched.
        indexPairs = Munkres().compute(matrix)
        # print "result", indexPairs, simVals
        for row, column in indexPairs:
            try:
                rLab, rAnn = accumRef[row]
            except IndexError:
                # hyp matched with nothing. Handle later.
                continue
            try:
                hLab, hAnn = accumHyp[column]
            except IndexError:
                # ref matched with nothing. Handle later.
                continue
            r, dimSim, errToks = self.simEngine.similarityCache[(rAnn, hAnn)]
            if r == 0:
                # Not sure if this can ever happen, but I'm pretty sure it can.
                newPairs += [[rLab, rAnn, "missing", None, None, None],
                             [None, None, None, hLab, hAnn, "spurious"]]
            else:
                # Compute the status from the errToks. Soon, this will be
                # passed right through.
                rStatus, hStatus = self._computePairStatuses(r, errToks)
                newPairs.append([rLab, rAnn, rStatus, hLab, hAnn, hStatus])
                # We need to record the pair so that the similarity engine knows
                # later what was paired.
                if not duringTokenRemainder:
                    self.simEngine.recordPair(rAnn, hAnn)
        if len(accumHyp) < len(accumRef):
            # Some of the refs aren't matched. Collect all possible indices
            # of the refs and remove the row indices.
            newPairs += [list(accumRef[i]) + ["missing", None, None, None]
                         for i in set(range(len(accumRef))) - set([p[0] for p in indexPairs])]
        elif len(accumRef) < len(accumHyp):
            # Some of the hyps aren't matched. Collect all possible indices
            # of the hyps and remove the column indices.
            newPairs += [[None, None, None] + list(accumHyp[i]) + ["spurious"]
                         for i in set(range(len(accumHyp))) - set([p[1] for p in indexPairs])]
        return newPairs

    # Unless it's missing or spurious or match, there's going to be a set of
    # tokens in the errToks.
    
    def _computePairStatuses(self, r, errToks):
        if r == 1.0:
            return "match", "match"
        elif not errToks:
            # These don't match, but we don't know why.
            return set(["unknownclash"]), set(["unknownclash"])
        else:
            rToks, hToks = errToks
            return rToks, hToks

    # Remember, spans are no longer a candidate comparison, so
    # we just compare by label.
    
    def _pairRemainingTokSpans(self, start, end, rEntries, hEntries):
        # reminder for pairsTokLevel:
        # [rLab, rAnn, rStatus, hLab, hAnn, hStatus, start, end]
        return [r + [start, end] for r in self._pairAnnotationsAtInterval(rEntries, hEntries,
                                                                          duringTokenRemainder = True)]

    # In order to deal with spanless annotations via their implied spans,
    # I'm going to do some fancy dancing.

    @classmethod
    def filterByRegions(cls, orderedRegionList, spannedLists = None, spanlessLists = None, maxRegionHash = None):

        # Ensure the annot lists are ordered, and collect the things that
        # we can get implied spans for. If we can't compute a span,
        # use the max region extents for the document.

        spannedTuples = []
        
        if spannedLists:
            for l in spannedLists:
                l.sort(cmp, lambda x: x.start)
            spannedTuples = [[(a, a.start, a.end) for a in spannedList] for spannedList in spannedLists]

        spanlessTuples = []
        
        if spanlessLists:
            impliedSpans = {}
            for spanlessList in spanlessLists:
                tupleList = []
                for a in spanlessList:
                    start, end = cls._computeImpliedSpan(a, impliedSpans)
                    if start is not None:
                        tupleList.append((a, start, end))
                    else:
                        try:
                            start, end = maxRegionHash[a.doc]
                            tupleList.append((a, start, end))
                        except KeyError:
                            pass
                tupleList.sort(cmp, lambda x: x[1])
                spanlessTuples.append(tupleList)

        annotLists = spannedTuples + spanlessTuples

        annotListCount = len(annotLists)
        idxList = [0] * annotListCount
        finalLists = [[] for l in annotLists]
        
        rI = 0
        
        while rI < len(orderedRegionList):
            curRegion = orderedRegionList[rI]
            rI += 1
            j = 0
            while j < annotListCount:
                annotTupleList = annotLists[j]
                finalList = finalLists[j]
                while idxList[j] < len(annotTupleList):
                    curA, start, end = annotTupleList[idxList[j]]
                    if start < curRegion[0]:
                        # discard.
                        idxList[j] += 1
                    elif end <= curRegion[1]:
                        # keep.
                        finalList.append(curA)
                        idxList[j] += 1
                    else:
                        # wait.
                        break
                j += 1
        # So we need to return the spanned tuples and the spanless tuples
        # separately.
        return tuple(finalLists[:len(spannedTuples)]), tuple(finalLists[len(spannedTuples):])

# Next, we need to deal with the similarity profiles.

# What will be the shape of this? The engine should deal with all the types.
# What gets passed in? The strata are above the level of the individual profile.
# <similarity_profile labels="...">
#   <stratum>label,label...</stratum> // if not defined, use labels
#   <tag_profile labels="...">
#      <dimension name="..." weight="..." method="..."/>
# We should barf if the annotations require stratification but currently
# aren't stratified. The similarity profiles and tag profiles will all be
# by actual label, not effective label. The similarities between non-matching
# labels in a stratum should be the lesser of the two similarities in each
# direction (i.e., assuming any attribute dimensions don't match).

# The default profile, whatever it is, only applies to spanned annotations.
# If there's no task, we have to figure this out on a document-by-document basis.
# And if it's already been determined and it's different in the current doc,
# we should scream.

# If there's no task, there can't be a profile. If there's no profile, there's
# very little you can do; you can basically use the default spanned comparator
# for the spanned annotations, and that's it. Not awful, but not much.

class SimilarityEngine:

    def __init__(self, pairer, similarityProfile = None):
        self.pairer = pairer
        self.strata = None
        self.profileName = similarityProfile
        # This is a map from string labels to an index into the
        # list of strata. Used to determine whetner labels are
        # on the same stratum or not.
        self.labelToStratumIdx = {}
        self.profile = None
        # This is a map from pairs of atype labels (NOT effective labels) to 
        # params to the computeSimilarity method.
        self.methodMap = {}
        # This is a map from atype labels (NOT effective labels) to
        # params to the computSimilarity method. It differs from the
        # one above because it should (a) lack the attribute annotations
        # (which are never paired for labels which don't share a tag profile)
        # and (b) have use_dead_weight set.
        self.unpairedMethodMap = {}
        self._spannedDefault = {"dimensions": [LabelComparisonClass(self, [], "_label", None, .1,
                                                                    {"true_residue": .5},
                                                                    None, None),
                                               SpanComparisonClass(self, [], "_span", None, .9,
                                                                   {}, None, None),
                                               NonAnnotationAttributeRemainderClass(self, [], "_nonannotation_attribute_remainder",
                                                                                    None, .1, {}, None, None),
                                               AnnotationAttributeRemainderClass(self, [], "_annotation_attribute_remainder",
                                                                                 None, .1, {}, None, None)
                                               ]}
        self._spanlessDefault = {"dimensions": [LabelComparisonClass(self, [], "_label", None, .2,
                                                                     {"true_residue": .5},
                                                                     None, None),
                                                NonAnnotationAttributeRemainderClass(self, [], "_nonannotation_attribute_remainder",
                                                                                     None, .2, {}, None, None),
                                                AnnotationAttributeRemainderClass(self, [], "_annotation_attribute_remainder",
                                                                                  None, .6, {}, None, None)
                                                ]}
        if pairer.task:
            self.profile = pairer.task.getSimilarityProfile(name = self.profileName) or {}
            self._compileStrata()
            self._compileProfile()
        else:
            self.computeSimilarity = self.computeSimilarityTaskless
        # This is a mapping from pairs of annotations to similarities.
        self.similarityCache = {}
        self.pairCache = set()

    def _compileProfile(self):
        atp = self.pairer.task.getAnnotationTypeRepository()
        recordedLabels = set()
        for tp in self.profile.get("tag_profiles", []):
            # These are all the labels to which the profile applies.
            labs = tp["true_labels"]
            attrEquivs = tp["attr_equivalences"] or {}
            # Check to make sure that an attribute
            # occurs only once.
            reverseEquivs = {}
            for eqv, names in attrEquivs.items():
                for name in names:
                    if reverseEquivs.has_key(name):
                        raise PairingError, ("a tag profile in a similarity profile in task '%s' specifies the attribute '%s' in more than one attribute equivalence" % (self.pairer.task.name, name))
                    reverseEquivs[name] = eqv
            allAtypes = []
            for l in labs:
                recordedLabels.add(l)
                atype = atp.get(l)
                if not atype:
                    raise PairingError, ("label '%s' in tag profile for similarity profile in task %s is unknown" % \
                                         (l, self.pairer.task.name))
                allAtypes.append(atype)

            labEntry = {"dimensions": [], "dead_weight": 0}
            totalWeight = 0

            if not tp["dimensions"]:
                raise PairingError, ("no dimensions in tag profile in task %s" % self.pairer.task.name)
            
            for dim in tp["dimensions"]:
                dimName = dim["name"]
                dimWeight = float(dim["weight"])
                totalWeight += dimWeight
                # This has a default.
                dimMethod = dim.get("method")
                # If this is an attribute, and it's an aggregation, and you don't
                # want to use the default aggregation techniques, do this.
                dimAggregatorMethod = dim.get("aggregator_method")
                dimParams = dim.get("params") or {}
                # This can be defined, but is optional. If not present,
                # the params are treated as strings, which may not be
                # very efficient if your custom method has params which
                # should be digested into floats or something.
                dimDigester = dim.get("param_digester_method")
                self._compileDimensionComparator(labEntry, allAtypes, attrEquivs,
                                                 dimName, dimWeight, dimMethod,
                                                 dimAggregatorMethod, dimParams, dimDigester)

            if totalWeight == 0:
                # There won't be any denominator.
                raise PairingError, ("tag profile in task '%s' has a total weight of 0" % self.pairer.task.name)
            
            # By now we've confirmed that every one of these labels has the dimensions
            # specified, so we record all these pairs. For pairs that do NOT exist,
            # if the labels are in the same stratum, we compare them without the
            # attributes, using the dead weight, and take the minimum; otherwise,
            # we return 0.
            
            for lab in labs:
                # Assemble the dead weight from the attributes for the unpairedMethodMap.
                self.unpairedMethodMap[lab] = {"dimensions": [d for d in labEntry["dimensions"]
                                                              if not isinstance(d, AttributeComparisonClass)],
                                               "use_dead_weight": True,
                                               "dead_weight": sum([d.weight for d in labEntry["dimensions"]
                                                                   if isinstance(d, AttributeComparisonClass)])}
                for otherLab in labs:
                    self.methodMap[(lab, otherLab)] = labEntry
                    self.methodMap[(otherLab, lab)] = labEntry

        # WHAT ABOUT DEFAULTS? There are two levels: what happens when you have
        # no task, and what happens when you have a task but no similarity.
        # The "no task" case is handled elsewhere. Here, we should record every
        # possible annotation listed in the strata. Use the default comparison
        # whenever there's no entry.
        
        for spanned, spanless in self.strata:
            spannedSet = set(spanned)
            spannedSet -= recordedLabels
            spanlessSet = set(spanless)
            spanlessSet -= recordedLabels
            # And finally, there needs to be an unpaired method
            # map for all of these as well.
            for l in spannedSet:
                entry = self._spannedDefault
                self.unpairedMethodMap[l] = {"dimensions": [d for d in entry["dimensions"]
                                                            if not isinstance(d, AttributeComparisonClass)],
                                             "use_dead_weight": True,
                                             "dead_weight": sum([d.weight for d in entry["dimensions"]
                                                                 if isinstance(d, AttributeComparisonClass)])}                
                for l2 in spannedSet:
                    # All elements in the same stratum which are unprofiled
                    # labels can be compared to each other.
                    self.methodMap[(l, l2)] = entry
                    self.methodMap[(l2, l)] = entry
            for l in spanlessSet:
                entry = self._spanlessDefault
                self.unpairedMethodMap[l] = {"dimensions": [d for d in entry["dimensions"]
                                                            if not isinstance(d, AttributeComparisonClass)],
                                             "use_dead_weight": True,
                                             "dead_weight": sum([d.weight for d in entry["dimensions"]
                                                                 if isinstance(d, AttributeComparisonClass)])}                

                for l2 in spanlessSet:
                    self.methodMap[(l, l2)] = entry
                    self.methodMap[(l2, l)] = entry

    # Each dimMethod is a function(rVal, hVal, **dimParams) -> (sim between 0 and 1, optional list of (error token from ref POV, error token from hyp POV))
    
    def _compileDimensionComparator(self, labEntry, allAtypes, attrEquivs,
                                    dimName, dimWeight, dimMethod,
                                    dimAggregatorMethod, dimParams, dimDigester):
        comparisonClass = _SPECIAL_COMPARISON_TYPES.get(dimName)
        if comparisonClass:
            c = comparisonClass(self, allAtypes, dimName, dimMethod, dimWeight, dimParams, 
                                dimAggregatorMethod, dimDigester)
        else:
            if dimName.find(",") > -1:
                # Multiple attributes. Our comparison class will be MultiAttributeComparisonClass.
                dimNames = [s.strip() for s in dimName.split(",")]
                attrAggrTriples = [self._ensureCommonAttrData(allAtypes, attrEquivs, d) for d in dimNames]
                c = MultiAttributeComparisonClass(self, dimNames, attrAggrTriples,
                                                  dimMethod, dimWeight, dimParams,
                                                  dimAggregatorMethod, dimDigester)
            else:
                attrType, aggrType, dimMap = self._ensureCommonAttrData(allAtypes, attrEquivs, dimName)                
                comparisonClass = _ATTR_COMPARISON_TYPES[attrType]
                c = comparisonClass(self, dimName, aggrType,
                                    dimMap, dimMethod, dimWeight, dimParams, 
                                    dimAggregatorMethod, dimDigester)
            
        labEntry["dimensions"].append(c)

    def _ensureCommonAttrData(self, allAtypes, attrEquivs, candidateDimName):
        # It's gotta be an attribute type.
        # Make sure all the types are the same.
        # If the dimName appears in the attrEquivs, the atype
        # has to have one of the attrs in the equiv.
        dimMapRequired = False
        try:
            dimNames = attrEquivs[candidateDimName]
            dimMapRequired = True
        except KeyError:
            dimNames = [candidateDimName]
        attrType = None
        # I need to start out with something that isn't None.
        aggrType = 0
        # From label to true attr.
        dimMap = {}
        for atype in allAtypes:
            dimName = None
            for dn in dimNames:
                if atype.attr_table.has_key(dn):
                    dimName = dn
            if not dimName:
                raise PairingError, ("The attribute '%s' specified as a dimension for label '%s' in the tag profile in a similarity profile for task %s is unknown" % (candidateDimName, atype.lab, self.pairer.task.name))
            attr = atype.attr_list[atype.attr_table[dimName]]
            if (attrType is not None) and (attrType != attr._typename_):
                raise PairerError, ("The attribute '%s' specified as a dimension for label '%s' in the tag profile in a similarity profile for task %s has a different type than it does in another label in that tag_profile" % (dimName, atype.lab, self.pairer.task.name))
            if (aggrType is not 0) and (aggrType != attr.aggregation):
                raise PairerError, ("The attribute '%s' specified as a dimension for label '%s' in the tag profile in a similarity profile for task %s has a different aggregation type than it does in another label in that tag_profile" % (dimName, atype.lab, self.pairer.task.name))
            attrType = attr._typename_
            aggrType = attr.aggregation
            dimMap[atype.lab] = dimName
        return attrType, aggrType, ((dimMapRequired and dimMap) or None)

    # If there's no task, I can't check stratification, really, because I have no
    # document-independent way of assessing the elements. However, I only need to
    # stratify if any of the annotations referenced in the tag profiles have
    # annotation-valued attributes which are being compared; and that can't
    # happen if there's no task.

    # It ought to be a bug to not assign some content annotations to strata.
    # You need to pair everything that's pointed to by other things; that's
    # part of what's checked in the compilation. 

    def _compileStrata(self):
        try:
            strata = self.profile["strata"]
        except KeyError:
            strata = [self.pairer.task.getAnnotationTypesByCategory("content")]
        # Each compiled stratum is a pair of (spanned, spanless). They may never
        # pair with each other. The spanned are always done first; that should
        # make for a useful default if we ever develop a default comparison
        # for spanless annotations.
        globalTable = self.pairer.task.getAnnotationTypeRepository()
        strataToCheck = []
        self.strata = []        
        self.labelToStratumIdx = {}
        for s in strata:
            stratum = ([], [])
            aLabStratum = ([], [])
            for aLab in s:
                if self.labelToStratumIdx.has_key(aLab):
                    raise PairingError, ("label '%s' appears more than once in similarity stratum for task %s" % \
                                         (aLab, self.pairer.task.name))
                self.labelToStratumIdx[aLab] = len(self.strata)
                atype = globalTable.get(aLab)
                if atype is None:
                    raise PairingError, ("unknown label '%s' in similarity stratum for task %s" % (aLab, self.pairer.task.name))
                # Don't need the other arguments. This may be redundant, because if there are no
                # strata, we don't need to check this, since we know that it's already
                # content. But this will get it into the table, which is also useful.
                if not checkContentTag(self.pairer.contentTags, atype, self.pairer.task, None, None):
                    raise PairingError, ("label '%s' in similarity stratum for task %s is not a content tag" % \
                                         (aLab, self.pairer.task.name))
                if atype.hasSpan:
                    stratum[0].append(atype)
                    aLabStratum[0].append(aLab)
                else:
                    stratum[1].append(atype)
                    aLabStratum[1].append(aLab)
            strataToCheck.append(stratum)
            self.strata.append(aLabStratum)
        self._checkStratification(strataToCheck)

    # If there are no strata, we have to compile the local strata
    # and check the stratification. At one point, we were filtering
    # out spanless annotations when we were filtering regions, because
    # the spans couldn't be computed, but now that I'm computing
    # implied spans, that should work fine. Can we still end up
    # in a situation where spanless annotations in stratum n + 1
    # point to things that weren't paired because they were filtered
    # out in stratum n? No, because implied spans is transitive,
    # sort of - if you point to an annotation, your implied span
    # is at least the implied span of that annotation. So if
    # annotation A is filtered out in stratum n, anything that
    # points to it will be filtered out in stratum n + 1.
    
    def getDocStrata(self, doc, filterChanged):
       if self.strata is None:
           onlyStratum = ([], [])
           for atype in doc.atypeDict.keys():
               if checkContentTag(self.pairer.contentTags, atype, None,
                                  self.pairer.contentAnnotations, self.pairer.tokenAnnotations):
                   if atype.hasSpan:
                       onlyStratum[0].append(atype)
                   else:
                       onlyStratum[1].append(atype)
           self._checkStratification([onlyStratum])
           # If no error is raised, build the annotation strata.
           content = ([], [])
           for spanned in onlyStratum[0]:
               content[0].extend(doc.atypeDict[spanned])
           for spanless in onlyStratum[1]:
               content[1].extend(doc.atypeDict[spanless])
           strata = [content]
       else:            
           strata = []
           for spanned, spanless in self.strata:
               s = ([], [])
               strata.append(s)
               for lab in spanned:
                   atype = doc.anameDict.get(lab)
                   if atype is not None:
                       s[0].extend(doc.atypeDict[atype])
               for lab in spanless:
                   atype = doc.anameDict.get(lab)
                   if atype is not None:
                       s[1].extend(doc.atypeDict[atype])
       return strata

   # These strata are lists of lists of atype objects. Each atype
   # which points to another atype has to have that atype in a previous
   # stratum (stratified) or in the current stratum (unstratified). Otherwise,
   # it's an error. For that matter, right now, unstratified won't be handled.
   # Also, we're going to always process spanned before spanless, so
   # we can take that into account here.
    def _checkStratification(self, strata):
        alreadyFound = set()
        def checkAtypeSetStratification(atypeSet):
            atypeLabSet = set([atype.lab for atype in atypeSet])
            for atype in atypeSet:
               if atype.hasAnnotationValuedAttributes:
                   for attr in atype.attr_list:
                       if isinstance(attr, AnnotationAttributeType):
                           labs = attr.atomicLabelRestrictions
                           if attr.complexLabelRestrictions:
                               if not labs:
                                   labs = set([p[0] for p in attr.complexLabelRestrictions])
                               else:
                                   labs = labs.copy()
                                   labs.update([p[0] for p in attr.complexLabelRestrictions])
                           if labs:
                               for l in labs:
                                   if l not in alreadyFound:
                                       if l in atypeLabSet:
                                           raise PairingError, ("label %s is stratified in task %s with an annotation type which refers to it" % (l, self.pairer.task.name))
                                       else:
                                           raise PairingError, ("label %s is referenced in task %s in a stratum before it's paired" % (l, self.pairer.task.name))
            alreadyFound.update(atypeLabSet)                                    
        for (spanned, spanless) in strata:
            checkAtypeSetStratification(spanned)
            checkAtypeSetStratification(spanless)

    # If the label pair is known, run the method entry. If it's not,
    # but the annotations are in the same stratum, then run each one
    # with the dead weight enabled, and then take the minimum.
    # Otherwise, return 0.
    
    def computeSimilarity(self, rPair, hPair, useTokenSimilarity = False):
        rLab, rAnnot = rPair
        hLab, hAnnot = hPair
        # Token similarity is just like regular similarity, except (a) it
        # doesn't compare the span, and (b) it doesn't store the results.
        if not useTokenSimilarity:
            try:
                return self.similarityCache[(rAnnot, hAnnot)]
            except KeyError:
                pass
        labPair = (rAnnot.atype.lab, hAnnot.atype.lab)
        try:
            labEntry = self.methodMap[labPair]
            r = self._computeSimilarity(rLab, rAnnot, hLab, hAnnot,
                                        useTokenSimilarity = useTokenSimilarity, **labEntry)
        except KeyError:
            # You'd think this should already have been checked, but
            # sometimes we need the similarity between elements in
            # values of attributes, which won't have been comparison segmented
            # necessarily.
            rStratum = self.labelToStratumIdx.get(labPair[0])
            hStratum = self.labelToStratumIdx.get(labPair[1])
            if (rStratum is None) or (hStratum is None):
                # One or the other can't be compared.
                r = 0, None, None
            elif rStratum != hStratum:
                r = 0, None, None
            elif rAnnot.atype.hasSpan != hAnnot.atype.hasSpan:
                r = 0, None, None
            else:
                # Now, compare the two elements, first from the point of view of
                # the reference (using its method map) and then from the point
                # of view of the hypothesis (using its method map). Take the minimum.
                # The errTokens from _computeSimilarity if not None, is a pair
                # of error token sets or lists, from the point of view of each side.
                # We glom them together, being careful to reverse the hErrTokens.
                # And we have to say SOMEthing about the recorded dimensions.
                # Let's take the dimensions from the "winning" comparison.
                # So then we DON'T merge the errtokens.
                rComp, dimStatus, errTokens = self._computeSimilarity(rLab, rAnnot, hLab, hAnnot,
                                                                      useTokenSimilarity = useTokenSimilarity,
                                                                      **self.unpairedMethodMap[labPair[0]])
                hComp, hDimStatus, hErrTokens = self._computeSimilarity(hLab, hAnnot, rLab, rAnnot,
                                                                        useTokenSimilarity = useTokenSimilarity,
                                                                        **self.unpairedMethodMap[labPair[1]])
                if hComp < rComp:
                    dimStatus = hDimStatus
                    if hErrTokens:
                        errTokens = (hErrTokens[1], hErrTokens[0])
                    else:
                        errTokens = None
                r = min(rComp, hComp), dimStatus, errTokens
        if not useTokenSimilarity:
            self.similarityCache[(rAnnot, hAnnot)] = r
        return r

    # Without a task, we'll use the default span comparison.
    
    def computeSimilarityTaskless(self, r, h, useTokenSimilarity = False):
        rLab, rAnnot = r
        hLab, hAnnot = h
        if rAnnot.atype.hasSpan:
            dflt = self._spannedDefault
        else:
            dflt = self._spanlessDefault
        # Token similarity is just like regular similarity, except (a) it
        # doesn't compare the span, and (b) it doesn't store the results.
        if not useTokenSimilarity:
            try:
                return self.similarityCache[(rAnnot, hAnnot)][0]
            except KeyError:
                pass
        res = self._computeSimilarity(rLab, rAnnot, hLab, hAnnot, useTokenSimilarity = useTokenSimilarity, **dflt)
        if not useTokenSimilarity:
            self.similarityCache[(rAnnot, hAnnot)] = res
        return res

    # And here's the real magic work. We need to capture the results of
    # this comparison.
    
    # So there's one odd thing that can happen here: if the annotations
    # are in a set that's induced by sequences of overlaps,
    # the rLab and hLab may not overlap at all. In this case, their
    # similarity HAS to be 0.

    # So the first thing this function has to do is compare the
    # implied spans, and if they both have implied spans and they don't
    # overlap, the answer is 0. We have to ask the pairer for that information.

    def _computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity = False, use_dead_weight = False,
                           dimensions = None, dead_weight = None):
        rStart, rEnd = self.pairer._computeImpliedSpan(rAnnot, self.pairer.impliedSpans)
        hStart, hEnd = self.pairer._computeImpliedSpan(hAnnot, self.pairer.impliedSpans)
        if (rStart is not None) and (hStart is not None) and \
            ((rEnd <= hStart) or (rStart >= hEnd)):
            # Nope.
            return 0, {}, None
        dimResults = {}
        numerator = 0
        denominator = 0
        totalErrToks = set()
        # I'm not going to futz around with whether .99999999 == 1.0;
        # let's track whether the individual dimensions are 1.0 or not.
        # And if there are no dimensions, I don't want to be dividing by 0...
        itsPerfect = True
        if dimensions:
            for dimension in dimensions:
                if isinstance(dimension, SpanComparisonClass) and useTokenSimilarity:
                    # Originally, I just skipped this, but the fact of the matter is,
                    # the span DOES match. This interacts with _pairAnnotationsAtInterval,
                    # which ought to reject a pair, even if it's the only possible pair,
                    # if its similarity is zero. So I want to add the weight to the
                    # numerator.
                    denominator += dimension.weight
                    numerator += dimension.weight
                    continue
                if (not isinstance(dimension, AttributeComparisonClass)) or (not use_dead_weight):
                    # If you use the dead weight, you skip the attributes.
                    r, weight, errToks = dimension.computeSimilarity(rLab, rAnnot, hLab, hAnnot, useTokenSimilarity)
                    dimResults[dimension.dimName] = (r, errToks)
                    if r < 1.0:
                        itsPerfect = False
                    denominator += weight
                    numerator += (r * weight)
                    if errToks:
                        totalErrToks.update(errToks)
        if use_dead_weight and dead_weight:
            itsPerfect = False
            denominator += dead_weight

        if itsPerfect:
            return 1.0, dimResults, None
        elif not totalErrToks:
            return float(numerator) / float(denominator), dimResults, None
        else:
            # Accumulate the tokens for each annotation.
            return float(numerator) / float(denominator), dimResults, \
                   (set([t[0] for t in totalErrToks]), set([t[1] for t in totalErrToks]))

    def recordPair(self, rAnn, hAnn):
        self.pairCache.add((rAnn, hAnn))
    
#
# Here are the various magic comparison classes. 
#

class SimilarityEngineComparisonClass(object):

    def __init__(self, simEngine, dimName, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester,
                 defaultMethod, methodTable):
        self.simEngine = simEngine
        self.defaultMethod = defaultMethod
        self.methodTable = methodTable
        self.dimName = dimName
        self.weight = dimWeight
        self.computedMethod = None
        self.computedParams = None
        if not dimMethod:
            dimMethod = self.methodTable[self.defaultMethod]
            dimDigester = None
            if type(dimMethod) is tuple:
                dimMethod, dimDigester = dimMethod
        elif self.methodTable.has_key(dimMethod):
            # First, see if the method is a known one.
            dimMethod = self.methodTable[dimMethod]
            dimDigester = None
            if type(dimMethod) is tuple:
                dimMethod, dimDigester = dimMethod
        else:
            # If we don't know it, try to evaluate it.
            try:
                dimMethod = eval(dimMethod)
            except (NameError, AttributeError):
                raise PairingError, ("Custom dimension method '%s' in similarity profile for task '%s' is unknown" % (dimMethod, self.simEngine.pairer.task.name))
            # We only need digesters for custom methods.
            if dimDigester:
                try:
                    dimDigester = eval(dimDigester)
                except (NameError, AttributeError):
                    # OK, try it in the plugin.
                    import MAT.PluginMgr
                    try:
                        dimDigester = MAT.PluginMgr.FindPluginObject(dimDigester, self.simEngine.pairer.task.name)
                    except MAT.PluginMgr.PluginError:
                        raise PairingError, ("Custom dimension method parameter digester '%s' in similarity profile for task '%s' is unknown" % (dimDigester, self.simEngine.pairer.task.name))
        # Now, if we have the aggregator method, apply it.
        if dimAggregatorMethod:
            origDimMethod = dimMethod
            dimMethod = lambda rVal, hVal, **params: dimAggregatorMethod(rVal, hVal, origDimMethod, **params)
        # At this point, we have a mapper and an optional parameter digester for this entry.
        if dimDigester:
            dimParams = dimDigester(**dimParams)
        self.computedMethod = dimMethod
        self.computedParams = dimParams

class SpanComparisonClass(SimilarityEngineComparisonClass):

    def __init__(self, simEngine, allAtypes, dimName, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester):
        if dimAggregatorMethod:
            raise PairingError, "Can't define an aggregator method on the _span dimension in a similarity profile"
        for atype in allAtypes:
            if not atype.hasSpan:
                raise PairingError, ("Can't define a _span dimension in a similarity profile on type '%s', because it has no span" % atype.lab)
        # Ignore dimDigester.
        SimilarityEngineComparisonClass.__init__(self, simEngine, dimName, dimMethod, dimWeight, dimParams, 
                                                 None, dimDigester, "overlap",
                                                 {"overlap": (self._similaritySpanOverlap, self._similarityDimDigester)})
        

    def computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity):
        r, errToks = self.computedMethod((rAnnot.start, rAnnot.end), (hAnnot.start, hAnnot.end),
                                         **(self.computedParams or {}))
        return r, self.weight, errToks

    def _similarityDimDigester(self, **params):
        if params.get("overlap_match_lower_bound") is not None:
            params["overlap_match_lower_bound"] = float(params["overlap_match_lower_bound"])
        if params.get("overlap_mismatch_upper_bound") is not None:
            params["overlap_mismatch_upper_bound"] = float(params["overlap_mismatch_upper_bound"])
        return params
    
    # Here, rVal and hVal are both span pairs.
    # overlap_match_lower_bound is the threshold above which
    # it counts as 1.0.
    # overlap_mismatch_upper_bound is the threshold below which
    # it counts as 0.0.
    @staticmethod
    def _similaritySpanOverlap(rVal, hVal, overlap_match_lower_bound = None, overlap_mismatch_upper_bound = None, **params):
        rStart, rEnd = rVal
        hStart, hEnd = hVal
        overlapPct = float(min(rEnd, hEnd) - max(rStart, hStart))/float(max(rEnd, hEnd) - min(rStart, hStart))
        if (overlap_match_lower_bound is not None) and (overlapPct > overlap_match_lower_bound):
            overlapPct = 1.0
        elif (overlap_mismatch_upper_bound is not None) and (overlapPct < overlap_mismatch_upper_bound):
            overlapPct = 0.0
        if overlapPct == 1.0:
            return 1.0, None
        else:
            # Figure out what the overlap error is.
            if (hStart <= rStart) and \
                (hEnd >= rEnd):
                # The hyp is larger than the ref (remember, we've factored out equality already)
                return overlapPct, [("undermark", "overmark")]
            elif (hStart >= rStart) and \
                  (hEnd <= rEnd):
                # The hyp is smaller than the ref
                return overlapPct, [("overmark", "undermark")]
            else:
                return overlapPct, [("overlap", "overlap")]


class LabelComparisonClass(SimilarityEngineComparisonClass):
        
    def __init__(self, simEngine, allAtypes, dimName, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester):
        if dimAggregatorMethod:
            raise PairingError, "Can't define an aggregator method on the _label dimension in a similarity profile"
        SimilarityEngineComparisonClass.__init__(self, simEngine, dimName, dimMethod, dimWeight, dimParams, 
                                                 None, dimDigester,
                                                 "label_equality",
                                                 {"label_equality": (self._similarityLabelEquality,
                                                                     self._similarityLabelEqualityParamDigester)})

    def computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity):
        r, errToks = self.computedMethod((rAnnot, rLab), (hAnnot, hLab),
                                         **(self.computedParams or {}))
        return r, self.weight, errToks

    @staticmethod
    def _similarityLabelEqualityParamDigester(**params):
        for k, v in params.items():
            if k == "true_residue":
                params[k] = float(v)
        return params
                
    @staticmethod
    def _similarityLabelEquality(rPair, hPair, true_residue = None, **params):
        rAnnot, rVal = rPair
        hAnnot, hVal = hPair
        if rVal == hVal:
            return 1.0, None
        elif rAnnot.atype.lab != hAnnot.atype.lab:
            return 0.0, [("tagclash", "tagclash")]
        elif true_residue is not None:
            return true_residue, [("computedtagclash", "computedtagclash")]
        return 0.0, [("tagclash", "tagclash")]

class AttributeComparisonClass(SimilarityEngineComparisonClass):

    # aggrType may be 0, to distinguish it from None.
    
    def __init__(self, simEngine, attrName, aggrType,
                 dimMap, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester,
                 defaultMethod, methodTable):
        if aggrType is not None:
            # It's an aggregation, so we need an aggregation function to apply to the
            # method.
            if dimAggregatorMethod:
                try:
                    dimAggregatorMethod = eval(dimAggregatorMethod)
                except (NameError, AttributeError):
                    raise PairingError, ("Custom dimension aggregator method '%s' in similarity profile for task '%s' is unknown" % (dimAggregatorMethod, simEngine.pairer.task.name))
            elif aggrType == "set":
                dimAggregatorMethod = self._similaritySetAggregation
            elif aggrType == "list":
                dimAggregatorMethod = self._similarityListAggregation
        elif dimAggregatorMethod:
            raise PairingError, ("Can't define an aggregator method for non-aggregating dimension '%s' in a similarity profile for task '%s'" % (dimAggregatorMethod, simEngine.pairer.task.name))
        SimilarityEngineComparisonClass.__init__(self, simEngine, attrName, dimMethod, dimWeight, dimParams, 
                                                 dimAggregatorMethod, dimDigester,
                                                 defaultMethod, methodTable)
        self.dimMap = dimMap

    def computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity):
        if self.dimMap:
            rVal = rAnnot.get(self.dimMap[rAnnot.atype.lab])
            hVal = hAnnot.get(self.dimMap[hAnnot.atype.lab])
        else:
            rVal = rAnnot.get(self.dimName)
            hVal = hAnnot.get(self.dimName)
        # If they're both None, good on them.
        if (rVal is None) and (hVal is None):
            return 1.0, self.weight, None
        elif (rVal is not None) and (hVal is not None):
            r, errToks = self.computedMethod(rVal, hVal, useTokenSimilarity = useTokenSimilarity,
                                             **(self.computedParams or {}))
            return r, self.weight, errToks
        else:
            return 0.0, self.weight, None
    
    @staticmethod
    def _similarityEquality(rVal, hVal, **params):
        if rVal == hVal:
            return 1.0, None
        else:
            return 0.0, None

    @staticmethod
    def _similaritySetAggregation(rVal, hVal, itemComp, useTokenSimilarity = False, **params):
        if itemComp is AttributeComparisonClass._similarityEquality:
            v = len(rVal & hVal)/float(len(rVal | hVal))
            # This is wrong, because it only works for exact equality, but what the hell.
            if v == 1.0:
                return 1.0, None
            else:
                return v, [("setclash", "setclash")]
        else:
            # I think the right thing to do is compute the pairwise
            # similarity, and then run Kuhn-Munkres.
            # the itemComp method returns a pair, and in the cost matrix, I only want the first value.
            matrix = make_cost_matrix([[itemComp(r, h, useTokenSimilarity = useTokenSimilarity)[0] for h in hVal]
                                       for r in rVal],
                                      lambda cost: 1.0 - cost)
            indexPairs = Munkres().compute(matrix)
            # Sum of the similarities. Now, how to get
            # some sensible value out of this? First, make sure
            # we re-invert the results.
            rawSum = sum([1.0 - matrix[row][column] for (row, column) in indexPairs])
            maxSum = max(len(hVal), len(rVal))
            if rawSum == maxSum:
                return 1.0, None
            else:
                return (rawSum / float(maxSum)), [("setclash", "setclash")]

    @staticmethod
    def _similarityListAggregation(rVal, hVal, itemComp, **params):
        raise PairingError, "haven't implemented list aggregation for pairing yet"
        return 0.0, None

    def _getDeclaredAttributes(self):
        # This is required by the remainder stuff.
        if self.dimMap:
            return self.dimMap.values()
        else:
            return [self.dimName]

class NonAnnotationAttributeComparisonClass(AttributeComparisonClass):

    def __init__(self, simEngine, attrName, aggrType,
                 dimMap, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester):
        AttributeComparisonClass.__init__(self, simEngine, attrName, aggrType,
                                          dimMap, dimMethod, dimWeight, dimParams, 
                                          dimAggregatorMethod, dimDigester,
                                          "equality",
                                          {"equality": self._similarityEquality})

class StringAttributeComparisonClass(NonAnnotationAttributeComparisonClass):

    pass

class IntAttributeComparisonClass(NonAnnotationAttributeComparisonClass):

    pass

class FloatAttributeComparisonClass(NonAnnotationAttributeComparisonClass):

    pass

class BooleanAttributeComparisonClass(NonAnnotationAttributeComparisonClass):

    pass

class AnnotationAttributeComparisonClass(AttributeComparisonClass):

    def __init__(self, simEngine, attrName, aggrType,
                 dimMap, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester):
        AttributeComparisonClass.__init__(self, simEngine, attrName, aggrType,
                                          dimMap, dimMethod, dimWeight, dimParams, 
                                          dimAggregatorMethod, dimDigester,
                                          "similarity",
                                          {"similarity": self._similarityAnnotationSimilarity})

    # This one isn't static, because it has to use the cache.
    # Right now, we don't support unstratified, so we'll always
    # have an entry for this in the cache. If they're not paired,
    # the result is 0; otherwise, it's the contents of the cache.
    
    def _similarityAnnotationSimilarity(self, rVal, hVal, **params):
        e = self.simEngine
        if (rVal, hVal) not in e.pairCache:
            return 0.0, [("annattributenotpaired", "annattributenotpaired")]
        else:
            # Ignore the dimension results and error tokens.
            r = e.similarityCache[(rVal, hVal)][0]
            if r == 1.0:
                return 1.0, None
            else:
                return r, [("annclash", "annclash")]

# This has to be an element of AttributeComparisonClass, because
# its dead weight must contribute in the unpaired case.            

class MultiAttributeComparisonClass(AttributeComparisonClass):

    def __init__(self, simEngine, dimNames, attrAggrTriples,
                 dimMethod, dimWeight, dimParams,
                 dimAggregatorMethod, dimDigester):
        dimName = ",".join(dimNames)
        # There had better be a comparison method.        
        if dimMethod is None:
            raise PairingError, ("The dimension '%s' in the tag profile in a similarity profile for task %s is a multi-attribute comparison, but it has no method specified" % (dimName, simEngine.pairer.task.name))
        if dimAggregatorMethod is not None:
            raise PairingError, "Can't define an aggregator method on the multi-attribute dimension in a similarity profile"
        if len(dimNames) < 2:
            raise PairingError, "Can't define a multi-attribute dimension on fewer than two dimensions"
        KNOWN_METHODS = {
            "_annotation_set_similarity": self._similarityAnnotationSetSimilarity
            }
        AttributeComparisonClass.__init__(self, simEngine, dimName,
                                          None, None, dimMethod, dimWeight,
                                          dimParams, None, dimDigester,
                                          None, KNOWN_METHODS)
        self.dimNames = dimNames
        dimMaps = [c for (a, b, c) in attrAggrTriples]        
        if not [dm for dm in dimMaps if dm is not None]:            
            # If none of them are not none (i.e., all of them are none),
            # don't store the dimMaps.
            self.dimMaps = None
        else:
            self.dimMaps = dimMaps
        self.attrAggrPairs = [(a, b) for (a, b, c) in attrAggrTriples]
        
    def computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity):
        # Get the vals. Make sure to use the dimMaps if appropriate.
        # Use the true labels.
        if self.dimMaps:
            rVals = [rAnnot.get(dmap[rAnnot.atype.lab]) for dmap in self.dimMaps]
            hVals = [hAnnot.get(dmap[hAnnot.atype.lab]) for dmap in self.dimMaps]
        else:
            rVals = [rAnnot.get(d) for d in self.dimNames]
            hVals = [hAnnot.get(d) for d in self.dimNames]
        if (not [v for v in rVals if v is not None]) and \
           (not [v for v in hVals if v is not None]):
            # If they're both all Nones, good on them.
            return 1.0, self.weight, None
        else:
            r, errToks = self.computedMethod(rVals, hVals,
                                             useTokenSimilarity = useTokenSimilarity,
                                             **(self.computedParams or {}))
            return r, self.weight, errToks

    # For this case, I'm going to use the set similarity.
    
    def _similarityAnnotationSetSimilarity(self, rVals, hVals, useTokenSimilarity = False,
                                           **params):
        if not getattr(self, "_checkedAggrPairs", False):
            for (attr, aggr) in self.attrAggrPairs:
                if aggr is not None:
                    raise PairingError, "can't use _annotation_set_similarity to compare attributes which are aggregates themselves"
                if attr != "annotation":
                    raise PairingError, "can't use _annotation_set_similarity to compare attributes which aren't annotation attributes"
            self._checkedAggrPairs = True
            self._annotationCompInst = AnnotationAttributeComparisonClass(self.simEngine, self.dimNames[0], None, (self.dimMaps and self.dimMaps[0]) or None, None, 0, None, None, None)
        
        # Now, I know I have an _annotationCompInst, and I can use
        # the set similarity from above.

        return self._similaritySetAggregation(set([v for v in rVals if v is not None]),
                                              set([v for v in hVals if v is not None]),
                                              self._annotationCompInst._similarityAnnotationSimilarity,
                                              useTokenSimilarity = useTokenSimilarity)
    def _getDeclaredAttributes(self):
        if self.dimMaps:
            res = []
            for dm in self.dimMaps:
                res += dm.values()
            return res
        else:
            return self.dimNames

# This one is interesting. It collects up all the non-annotation attributes which
# are neither (a) an effective label, or (b) already specified in
# an existing dimension, and aggregates their results. This works
# across tag profiles as well as within them, unlike the explicitly
# declared attributes. I'm going to use this in the defaults, as well
# as allowing it to be created explicitly.

# Oh, and the attributes need to be globally declared.

# Oh, and if it has no attributes to match, its weight should be 0.

# Note, too, that this must be able to be called when there's no task.

class NonAnnotationAttributeRemainderClass(SimilarityEngineComparisonClass):

    def __init__(self, simEngine, allAtypes, dimName, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester):
        if dimAggregatorMethod:
            raise PairingError, ("Can't define an aggregator method on the %s dimension in a similarity profile" % dimName)
        SimilarityEngineComparisonClass.__init__(self, simEngine, dimName, dimMethod, dimWeight, dimParams, 
                                                 None, dimDigester, "overlap",
                                                 {"overlap": self._similarityAttributeOverlap})
        # I need to partition these by reference label.
        # This is a mapping from reference true labels to triples of
        # a mapping from attribute names to attribute objects for all
        # relevant attributes; a mapping from attribute names to comparison
        # classes for those same attributes; and a mapping from
        # hypothesis labels to their checkable attributes.
        self.checkableCache = {}

    def computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity):
        return self.computedMethod((rLab, rAnnot), (hLab, hAnnot),
                                   useTokenSimilarity = useTokenSimilarity,
                                   **(self.computedParams or {}))

    # This can't be a static method, since I need to reach waaaay back to the simEngine.
    def _similarityAttributeOverlap(self, rVal, hVal, useTokenSimilarity = False, **params):
        rLab, rAnnot = rVal
        hLab, hAnnot = hVal
        try:
            annotRemainder, comparers, checkableDict = self.checkableCache[rAnnot.atype.lab]
        except KeyError:
            # We haven't computed it yet. If there's a task, filter
            # the types by what's declared.
            if self.simEngine.pairer.task:
                mTable = self.simEngine.methodMap[(rAnnot.atype.lab, rAnnot.atype.lab)]
                # Which ones are declared? Remove them from contention.
                declared = set()
                for d in mTable["dimensions"]:
                    if isinstance(d, NonAnnotationAttributeComparisonClass) or \
                       isinstance(d, MultiAttributeComparisonClass):
                        declared.update(d._getDeclaredAttributes())
                globAtype = self.simEngine.pairer.task.getAnnotationTypeRepository()[rAnnot.atype.lab]
            else:
                declared = set()
                globAtype = rAnnot.atype
            annotRemainder = dict([(a.name, a) for a in globAtype.attr_list
                                   if (a.name not in declared) and \
                                      (not a.effectiveLabelAttribute) and \
                                      (a._typename_ != "annotation")])                
            comparers = dict([(a.name, _ATTR_COMPARISON_TYPES[a._typename_](self.simEngine, a.name, a.aggregation, None, None, 1, None, None, None))
                              for a in annotRemainder.values()])
            checkableDict = {}
            self.checkableCache[rAnnot.atype.lab] = (annotRemainder, comparers, checkableDict)
        if len(annotRemainder.keys()) == 0:
            # It weighs nothing
            return 1.0, 0.0, None
        try:
            checkable = checkableDict[hAnnot.atype.lab]
        except KeyError:
            # So now, for the hAnnot, we need to ensure that the
            # other attribute in question is (a) not an effective label attribute,
            # (b) not an annotation attribute, (c) matches the type and aggregation
            # of the local one. ONLY then do they count toward something that
            # can match.
            if self.simEngine.pairer.task:
                hGlobAtype = self.simEngine.pairer.task.getAnnotationTypeRepository()[hAnnot.atype.lab]
            else:
                hGlobAtype = hAnnot.atype
            checkable = [a.name for a in hGlobAtype.attr_list
                         if (annotRemainder.has_key(a.name)) and \
                            (not a.effectiveLabelAttribute) and \
                            (a._typename_ == annotRemainder[a.name]._typename_) and \
                            (a.aggregation == annotRemainder[a.name].aggregation)]
            checkableDict[hAnnot.atype.lab] = checkable
        # Now, look through each of the checkable annotations. VERY similar
        # to _computeSimilarity. I thought of bypassing all the boilerplate and
        # going directly to the equality method, but if there's an aggregation
        # involved, I don't want to have to compute that here too.
        numerator = 0
        denominator = 0
        totalErrToks = set()
        itsPerfect = True
        for dimensionName in checkable:
            dimension = comparers[dimensionName]
            r, weight, errToks = dimension.computeSimilarity(rLab, rAnnot, hLab, hAnnot, useTokenSimilarity)
            if r < 1.0:
                itsPerfect = False
            denominator += weight
            numerator += (r * weight)
            if errToks:
                totalErrToks.update(errToks)

        # OK, we've done them all. Now, we add the dead weight of
        # the ones in the local remainder that couldn't be checked remotely.

        localSize = len(annotRemainder.keys())
        remainder = localSize - len(checkable)
        if remainder > 0:
            itsPerfect = False
            denominator += remainder

        if itsPerfect:
            return 1.0, self.weight, None
        elif not totalErrToks:
            return float(numerator) / float(denominator), self.weight, None
        else:
            # Accumulate the tokens for each annotation.
            return float(numerator) / float(denominator), self.weight, totalErrToks

# For the annotation remainder, we're going to take all the annotation
# attributes and assume the names don't mean anything. So we do the best
# alignment between the annotations which share aggregations.

class AnnotationAttributeRemainderClass(SimilarityEngineComparisonClass):

    def __init__(self, simEngine, allAtypes, dimName, dimMethod, dimWeight, dimParams, 
                 dimAggregatorMethod, dimDigester):
        SimilarityEngineComparisonClass.__init__(self, simEngine, dimName, dimMethod, dimWeight, dimParams, 
                                                 None, dimDigester, "overlap",
                                                 {"overlap": self._similarityAttributeOverlap})
        self.checkableCache = {}
        self.aggrs = dict([(aggr, AnnotationAttributeComparisonClass(self.simEngine, "<null>", aggr,
                                                                     None, None, 1.0, None, None, None))
                           for aggr in [None, "set", "list"]])
    
    def computeSimilarity(self, rLab, rAnnot, hLab, hAnnot, useTokenSimilarity):
        return self.computedMethod((rLab, rAnnot), (hLab, hAnnot),
                                   useTokenSimilarity = useTokenSimilarity,
                                   **(self.computedParams or {}))

    def _getCheckableCacheEntry(self, annot):
        try:
            return self.checkableCache[annot.atype.lab]
        except KeyError:
            # We haven't computed it yet. If there's a task, filter
            # the types by what's declared.
            if self.simEngine.pairer.task:
                mTable = self.simEngine.methodMap[(annot.atype.lab, annot.atype.lab)]
                # Which ones are declared? Remove them from contention.
                declared = set()
                for d in mTable["dimensions"]:
                    if isinstance(d, AnnotationAttributeComparisonClass) or \
                       isinstance(d, MultiAttributeComparisonClass):
                        declared.update(d._getDeclaredAttributes())
                globAtype = self.simEngine.pairer.task.getAnnotationTypeRepository()[annot.atype.lab]
            else:
                declared = set()
                globAtype = annot.atype
            # We want a comparer for each aggregation type. So first, we sort them
            # into aggregation types.
            aggrDict = {None: [], "set": [], "list": []}
            valSize = 0
            for a in globAtype.attr_list:
                if (a.name not in declared) and (a._typename_ == "annotation"):
                    aggrDict[a.aggregation].append(a)
                    valSize += 1
            self.checkableCache[annot.atype.lab] = (aggrDict, valSize)
            return aggrDict, valSize

    # This can't be a static method, since I need to reach waaaay back to the simEngine.
    # This is very similar, in some ways, to the nonattribute case.
        
    def _similarityAttributeOverlap(self, rVal, hVal, useTokenSimilarity = False, **params):
        rLab, rAnnot = rVal
        hLab, hAnnot = hVal
        rAggrDict, rValSize = self._getCheckableCacheEntry(rAnnot)
        if rValSize == 0:
            # It weighs nothing.
            return 1.0, 0.0, None
        hAggrDict, hValSize = self._getCheckableCacheEntry(hAnnot)
        # Now, we need to deploy Kuhn-Munkres, I think, in each
        # aggregation type. But first, I need to get the values
        # for the corresponding annotations, and then run the
        # default comparison for the itemComp. None shouldn't
        # count as a match here, I don't think - it doesn't
        # help anything in any case.
        valSize = max(rValSize, hValSize)
        simSum = 0
        for aggr in [None, "set", "list"]:
            rAggr = [v for v in [rAnnot.get(a.name) for a in rAggrDict[aggr]] if v is not None]
            hAggr = [v for v in [hAnnot.get(a.name) for a in hAggrDict[aggr]] if v is not None]
            if rAggr and hAggr:
                itemComp = self.aggrs[aggr]
                # the itemComp method returns a triple, and in the cost matrix, I only want the first value.
                data = [[itemComp.computedMethod(rVal, hVal, useTokenSimilarity = useTokenSimilarity,
                                                 **(itemComp.computedParams or {}))[0] for hVal in hAggr]
                        for rVal in rAggr]
                matrix = make_cost_matrix(data, lambda cost: 1.0 - cost)
                indexPairs = Munkres().compute(matrix)
                # Note that these need to be picked out of the data, not the
                # matrix. The matrix computes the lowest cost, and I want the
                # highest, which is why we apply the inverse when we build the matrix.
                rawSum = sum([data[row][column] for (row, column) in indexPairs])
                simSum += rawSum
        
        # The denominator is valSize.
        if simSum == valSize:
            return 1.0, self.weight, None
        else:
            return (simSum / float(valSize)), self.weight, None
    
_SPECIAL_COMPARISON_TYPES = {
    "_span": SpanComparisonClass,
    "_label": LabelComparisonClass,
    "_nonannotation_attribute_remainder": NonAnnotationAttributeRemainderClass,
    "_annotation_attribute_remainder": AnnotationAttributeRemainderClass
    }

_ATTR_COMPARISON_TYPES = {
    "string": StringAttributeComparisonClass,
    "int": IntAttributeComparisonClass,
    "float": FloatAttributeComparisonClass,
    "boolean": BooleanAttributeComparisonClass,
    "annotation": AnnotationAttributeComparisonClass
    }
