# Copyright (C) 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Here, we define a bunch of stuff to manage reconciliation phases.
# This has to work in the workspaces, AND at least the human decision phase needs to
# work outside the workspace. Arrgh.

from MAT.ReconciliationDocument import _getListValue, AnnotationEquivalenceClassifier, \
     SPECIAL_VOTE_VALUES
from MAT.Operation import OpArgument, Option

class ReconciliationPhase(object):

    argList = []

    def __init__(self, **kw):
        self.pData = {}

    # In general, adding votes is permitted.
    # But I'm not ruling out a situation where
    # it won't be.
    addingVotesPermitted = True

    def prepPhase(self, **kw):
        pass

    def createAssignments(self, recDoc, phaseUsers, **kw):
        return []

    @classmethod
    def checkOrder(cls, pList):
        pass

    def reconcile(self, docObj, user, vDict, **kw):
        pass

    # True if the segment needs to be reviewed by the
    # user in this current round.
    
    def userReviewExpected(self, user, segment):
        return True

    # This is the wrapper code around the function above.
    def currentUserIsDone(self, docObj, user):
        # So how do we know this?

        # It depends on the phase. In the cross-validation challenge, the
        # user needs to review each segment she has partial ownership of.
        # In the other phases, the user needs to review every phase.
        
        # In each phase the user needs to review, 
        # there must be at least one vote that the user has voted for
        # which has been reviewed by the user.

        for a in docObj.getAnnotations(["SEGMENT"]):
            if a["status"] == "human gold":
                # If it still must be reviewed, fail.
                if self.userReviewExpected(user, a) and \
                   user not in _getListValue(a, "reviewed_by"):
                    return False
        # All the segments check out.
        return True

    # True if the user must review the segment, whether
    # or not it's been reviewed already.

    def forceReviewByUser(self, user, segment, votes):
        return False

    # If the user is an idiot and creates a pattern identical to an
    # existing pattern, we should detect that. Note that this will happen
    # every time the document is saved, even if it's not closed. The motivation
    # for this is that when the document is reopened, it should have the right
    # form, so if the browser crashes, for instance, nothing awful will happen
    # except you have to unlock the transaction.

    # Also, I want to ensure that the value of "to_review" on the segments is
    # None now that we're saving. And if there's a new vote, then the
    # values for reviewed_by on that segment should be ONLY the
    # annotators of that vote, and we need to force everyone who's
    # invalidated to redo the current phase.
    
    # Updating to conform to MAT 2.0 annotation structure. VOTES point to
    # SEGMENTs, but have no ids; content annotations have IDs and are listed
    # in the content list. I don't have a notion of "lists of annotations" as
    # a possible attribute value, which is a bit of a problem here, but
    # we'll just manipulate it the way we manipulated it previously.
 
    # We're going to modify the protocol, so that new VOTEs have "new" = "yes".
    # So we won't need to replace IDs, or to make a mess for empty new VOTEs.
      
    def updateSavedSegments(self, task, annotObj, **kw):
 
        vDict = annotObj._votesForSegments()
 
        segmentsToRepair = set()
 
        for a, vList in vDict.items():
            a["to_review"] = None
            # And if one of the votes is new, we need to
            # clear the reviewed_by slot for the segment,
            # and add in only those annotators in that
            # set, and take the reviewers who have
            # been invalidated, and mark them as not
            # having done their review in the DB.
            newVotes = []
            for v in vList:
                if v.get("new") == "yes":
                    newVotes.append(v)
                    segmentsToRepair.add(a)
            if newVotes:
                annotators = set()
                for v in newVotes:
                    annotators.update(_getListValue(v, "annotator"))
                curReviewedBy = _getListValue(a, "reviewed_by")
                a["reviewed_by"] = ",".join(annotators)
                self.forceRedo(list(set(curReviewedBy) - annotators), **kw)
    
        # And here's the point we want to check for duplication. Any segment that
        # needs repairing is a segment with a new vote. Any new vote will have all
        # new annotations. So for each segment, we look see whether the vote
        # to be repaired is identical to any vote that DOESN'T need to be repaired.
        if segmentsToRepair:
            equivClasser = AnnotationEquivalenceClassifier(task)
            for a in segmentsToRepair:
                # Find the new votes and the old votes. THEN, for each new vote,
                # and for each old vote of the same length, see if the vectors
                # are pairwise identical. If they are, then delete that vote annotation
                # and replace all references to it with the other vote. But transfer
                # the voters. Grrrr.
                votesToCheck = []
                oldVotes = []
                for v in vDict[a]:
                    if v.get("new") == "yes":
                        votesToCheck.append(v)
                        v["new"] = None
                    else:
                        oldVotes.append(v)
                if votesToCheck and oldVotes:
                    # Hash by vote length.
                    annotLengths = {}
                    for vAnnot in votesToCheck:
                        # It's already been replaced in the ids.
                        aIds = _getListValue(vAnnot, "content")
                        if (len(aIds) != 1) or (aIds[0] not in SPECIAL_VOTE_VALUES):
                            try:
                                annotLengths[len(aIds)][1].append((vAnnot, aIds))
                            except KeyError:
                                annotLengths[len(aIds)] = [[], [(vAnnot, aIds)]]

                    for vAnnot in oldVotes:
                        aIds = _getListValue(vAnnot, "content")
                        if (len(aIds) != 1) or (aIds[0] not in SPECIAL_VOTE_VALUES):
                            try:
                                annotLengths[len(aIds)][0].append((vAnnot, aIds))
                            except KeyError:
                                annotLengths[len(aIds)] = [[(vAnnot, aIds)], []]
                            
                    for aLen, [oldVotes, vToCheckList] in annotLengths.items():
                        if vToCheckList and oldVotes:
                            # Now, we do the real work. We've found new votes and
                            # old votes of equal length. Ask the equivClasser for the
                            # hashes for all the old votes, and then for each
                            # of the new votes, see if THOSE segments match any
                            # of the existing ones. If they do, then we collapse the
                            # new vote with the old one.
                            oldVotes = [(vAnnot, [equivClasser.generateAnnotVector(annotObj.getAnnotationByID(id)) for id in aIds])
                                        for (vAnnot, aIds) in oldVotes]
                            for vAnnot, aIds in vToCheckList:
                                vects = [equivClasser.generateAnnotVector(annotObj.getAnnotationByID(id)) for id in aIds]
                                for oldVAnnot, oldVects in oldVotes:
                                    if vects == oldVects:
                                        # OK, we've found a match. Collapse.
                                        # Add the voters from vAnnot to oldVAnnot, and
                                        # map the replacer for vAnnot to the id for oldVAnnot,
                                        # and delete vAnnot and all the new content annotations.
                                        # And clean up the ids.
                                        if oldVAnnot["annotator"]:
                                            oldVAnnot["annotator"] = ",".join(set(_getListValue(oldVAnnot, "annotator") +
                                                                                  _getListValue(vAnnot, "annotator")))
                                        else:
                                            oldVAnnot["annotator"] = vAnnot["annotator"]
                                        # We want to remove the one we replaced.
                                        # The vAnnot has already been updated.
                                        annotObj.removeAnnotation(vAnnot)
                                        for aId in aIds:
                                            annotObj.removeAnnotation(annotObj.getAnnotationByID(aId))
                                        break

    # What to do when you have to redo things when you're updating above.. Workspaces do something special.

    def forceRedo(self, annotatorsToRepeat, **kw):
        pass

class ReconciliationError(Exception):
    pass

# The human decision phases is absolute - whatever
# decisions are made here are permanent. Note that I still
# have the code to force the review, in the context where
# there may be multiple phases (e.g., workspaces).

class HumanDecisionPhase(ReconciliationPhase):

    argList = [Option("--human_decision_user", type="string", help="if the human_decision phase is enabled, a randomly-selected user with the human_decision role handles the decisions, unless a substitute is specified here")]

    roleIncludedInDefault = False

    def __init__(self, human_decision_user = None, **kw):
        ReconciliationPhase.__init__(self, **kw)
        self.pData["human_decision_user"] = human_decision_user

    def createAssignments(self, recDoc, phaseUsers):
        human_decision_user = self.pData.get("human_decision_user")
        if human_decision_user is not None:
            if human_decision_user not in phaseUsers:
                raise ReconciliationError, ("user '%s' does not have the human_decision role" % human_decision_user)
            return [("human_decision", human_decision_user)]
        elif not phaseUsers:
            raise ReconciliationError, "no human_decision users available"
        else:
            import random
            return [("human_decision", random.choice(phaseUsers))]            

    @classmethod
    def checkOrder(cls, pList):
        if not issubclass(pList[-1], cls):
            # Gotta be last
            raise ReconciliationError, "human decision phase must be last"

    # The special value "bad boundaries" CANNOT be a winning vote.

    def reconcile(self, docObj, user, vDict, **kw):
        # For each segment, choose the vote of the user
        # passed in. No one else will be looking at this document.
        for annot, segVotes in vDict.items():
            # The vDict only contains segments which have votes,
             # so we shouldn't have to check this, but what the hell.
            if annot["status"] != "human gold":
                continue
            if segVotes:
                for vote in segVotes:
                    if vote.get("content") == "bad boundaries":
                        continue
                    annotators = _getListValue(vote, "annotator")
                    if annotators and (user in annotators):
                        # We're good.
                        annot["status"] = "reconciled"
                        vote["chosen"] = "yes"
                        # No need to look at any other votes
                        # for this segment.
                        break

    # This case is trickier. If the user is the decider, we
    # want to make sure that, if the user has already reviewed it,
    # no other vote has MORE voters (excluding MACHINE).
    # And, also, if the winning vote is "bad boundaries".

    def forceReviewByUser(self, user, segment, allVotes):
        reviewerVoters = 0
        otherVoters = 0
        # bad boundaries votes don't have to collapse, so
        # we need to count them.
        otherBadBoundariesVoters = 0
        if allVotes:
            for v in allVotes:
                annotators = set(_getListValue(v, "annotator"))
                if user in annotators:
                    if v["content"] == "bad boundaries":
                        # If you're the winning vote, you're going to need to review,
                        # because "bad boundaries" always needs to be reviewed.
                        # If you're not the winning vote, you're going to need to
                        # review anyway, because you're not the winning vote.
                        return True
                    reviewerVoters = len(annotators - set(["MACHINE"]))
                else:
                    numAnnotators = len(annotators - set(["MACHINE"]))
                    otherVoters = max(otherVoters, numAnnotators)
                    if v["content"] == "bad boundaries":
                        otherBadBoundariesVoters += numAnnotators
        # If reviewerVoters less than otherVoters, you must review.
        return (reviewerVoters < otherVoters) or (reviewerVoters < otherBadBoundariesVoters)
