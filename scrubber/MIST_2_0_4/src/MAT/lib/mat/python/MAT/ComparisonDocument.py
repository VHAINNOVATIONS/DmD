# Copyright (C) 2012 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Here's where I generate a comparison document. This document will store
# all the comparison information in metadata. We couldn't do that with Callisto,
# but we CAN do that with the MAT UI. What we need is a set of pairs,
# with a pivot and comparison for each pair, a boolean indicating if the pair
# matches or not, and a list of matching dimensions for use if the pair doesn't
# match. We also need to know what dimensions were considered during the match,
# and we can save the similarity profile information to handle that.

import MAT.Pair

def generateComparisonDocument(task, pivot, others, similarityProfile = None,
                               pivotLabel = None, otherLabels = None):

    # Set up the outbound document.
    outD = MAT.Document.AnnotatedDoc(signal = pivot.signal, globalTypeRepository = task.getAnnotationTypeRepository())
    pairer = MAT.Pair.PairState(task = task, similarityProfile = similarityProfile, skipTokens = True)

    docMap = [(((otherLabels and (len(otherLabels) > i) and otherLabels[i]) or "d"+str(i+1)), other) \
              for (other, i) in zip(others, range(len(others)))]

    pairer.addDocumentTuples([(((pivotLabel or "d0"), pivot), p) for p in docMap])
    
    # Now, let's set up a cache for the compared annotations in each doc.
    copyCache = dict([(o, set()) for o in others])
    # We're going to import all the pivot annotations at once.
    pivotSet = set()
    copyCache[pivot] = pivotSet

    # So we've paired everything up, and we have an output document.
    for d in pairer.resultEntries:
        (pivotDname, pivotD), (compDname, compD) = d["tuple"]
        pairs = d["pairs"]
        # How do we create the new document? First, we want to import all
        # the compared annotations. But what about the case where
        # some of the arguments aren't compared? I think that we have to
        # ensure that if you're copied, everything you point to is copied.
        # And how do we produce the mapping between the originals and the copies?
        # Voila! importAnnotationGroup deals with all of this.
        # So the first thing we need to do is find all the annotations which
        # have been paired for each doc.
        compSet = copyCache[compD]
        for [label, ann, refMatchStatus, hLabel, hAnn, hypMatchStatus] in pairs:
            if ann: pivotSet.add(ann)
            if hAnn: compSet.add(hAnn)

    # Now, let's see if the import works. Be sure to capture the mappings!
    mappingCache = {}
    for d, s in copyCache.items():
        mappingCache[d] = outD.importAnnotationGroup(list(s))

    # When I assemble the comparisons, I need to make sure that everything mentioned
    # in the comparisons has a public ID. So let's go through the results again,
    # and collect the outcomes.

    allPairs = []

    pivotMapping = mappingCache[pivot]
    for d in pairer.resultEntries:
        (pivotDname, pivotD), (compDname, compD) = d["tuple"]
        pairs = d["pairs"]
        pairEntry = {"pivot": pivotDname, "other": compDname, "pairs": []}
        allPairs.append(pairEntry)
        compMapping = mappingCache[compD]
        for [label, ann, refMatchStatus, hLabel, hAnn, hypMatchStatus] in pairs:
            if ann and hAnn:
                # rescue the dimension similarity.
                ignore, dimSim, errToks = pairer.simEngine.similarityCache[(ann, hAnn)]
                dimMatch = [dim for (dim, status) in dimSim.items() if status[0] == 1.0]
            else:
                dimMatch = None
            if ann:
                ann = pivotMapping[ann]
            if hAnn:
                hAnn = compMapping[hAnn]
            pairEntry["pairs"].append({"pivot": ann and ann.getID(), "comparison": hAnn and hAnn.getID(),
                                       # Any pairs will be in the same stratum, so we only need to check the
                                       # stratum for one side or the other. And remember, we can't use
                                       # label or hLabel, because the strata are in terms of TRUE labels.
                                       "stratum": pairer.simEngine.labelToStratumIdx[(ann and ann.atype.lab) or hAnn.atype.lab],
                                       "match": refMatchStatus == "match", "dimensions_match": dimMatch})

    # Now, we record the pairs in the metadata, along with the dimensions considered.

    dimensionsConsidered = {}
    for (lLabel, rLabel), d in pairer.simEngine.methodMap.items():
        # d is a dictionary which contains span_weight, label_weight, and attr_dimensions,
        # among other things.
        attrsConsidered = d.get("attr_dimensions", {}).keys()
        if d.get("span_method") is not None:
            attrsConsidered.append("_span")
        if d.get("label_method") is not None:
            attrsConsidered.append("_label")
        # We're going to need to record this for labels in both directions, but
        # the symmetry is already present in the method map.
        try:
            lEntry = dimensionsConsidered[lLabel]
        except KeyError:
            lEntry = {}
            dimensionsConsidered[lLabel] = lEntry
        lEntry[rLabel] = attrsConsidered
    
    outD.metadata["comparison"] = {"similarity_profile": similarityProfile or "<default>",
                                   "pairs": allPairs,
                                   "dimensions_considered": dimensionsConsidered}
        
    # And what about importing zones and tokens? Pick the first document that has some.
    tokTypes = task.getAnnotationTypesByCategory("token")
    if tokTypes:
        for d in [pivot] + others:
            toks = d.getAnnotations(tokTypes)
            if toks:
                outD.importAnnotationGroup(toks)
                break
    zoneTypes = task.getAnnotationTypesByCategory("zone")
    if zoneTypes:
        for d in [pivot] + others:
            zones = d.getAnnotations(zoneTypes)
            if zones:
                outD.importAnnotationGroup(zones)
                break
    return outD
