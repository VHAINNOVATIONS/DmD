# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import os, shutil

from MAT.Operation import OptionBearer, OpArgument
import MAT.DocumentIO, MAT.Score, MAT.ExecutionContext

class ModelBuilderError(Exception):
    pass

# I inherit from OptionBearer so I can get command line arguments
# into MATModelBuilder.

class ModelBuilder(OptionBearer):

    argList = [OpArgument("partial_training_on_gold_only",
                          help = "When the trainer is presented with partially tagged documents, by default MAT will ask it to train on all annotated segments, completed or not. If this flag is specified, only completed segments should be used for training.")]
               
    def __init__(self, task, buildInfo, file_type = 'mat-json', partial_training_on_gold_only = False, **kw):
        OptionBearer.__init__(self)        
        # Task is required. All the elements will override whatever happens
        # to be in the task.
        if task is None:
            raise ModelBuilderError, "task is required"
        self.task = task
        self.buildInfo = buildInfo
        self.partialTrainingOnGoldOnly = partial_training_on_gold_only
        self.reader = MAT.DocumentIO.getDocumentIO(file_type, task = self.task, **kw)

    # docTmpDir is a temporary directory to put the documents in, in case
    # the caller wants to inspect them for some reason. tmpDir is the
    # tmp directory to use for everything, except for the docTmpDir if it's
    # provided.

    def _run(self, modelOutputFile, fileList, docTmpDir, tmpDir, oStream):
        raise ModelBuilderError, "not implemented"

    def _clearDir(self, d):
        # For everything in the directory, remove it. I could try to
        # remove the directory tree and then recreate it, but it's possible
        # that this directory is writeable by me and not its parent.
        for p in os.listdir(d):
            p = os.path.join(d, p)
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
    
    def run(self, modelOutputFile, fileList, docTmpDir = None,
            tmpDir = None, oStream = None, collectCorpusStatistics = False): 

        if tmpDir:
            # Clear the temp directory.
            if oStream:
                print >> oStream, "Clearing temp directory..."
            self._clearDir(tmpDir)
            self._runInTmpdirScope(modelOutputFile, fileList, docTmpDir, tmpDir, oStream, collectCorpusStatistics)
        else:
            with MAT.ExecutionContext.Tmpdir() as tmpDir:
                self._runInTmpdirScope(modelOutputFile, fileList, docTmpDir, tmpDir, oStream, collectCorpusStatistics)

    def _runInTmpdirScope(self, modelOutputFile, fileList, docTmpDir, tmpDir, oStream, collectCorpusStatistics):
    
        if docTmpDir:
            # Clearing the temp directory.
            if oStream:
                print >> oStream, "Clearing document temp directory..."
            self._clearDir(docTmpDir)
        else:
            docTmpDir = os.path.join(tmpDir, "docs")
            os.mkdir(docTmpDir)

        self._run(modelOutputFile, fileList, docTmpDir, tmpDir, oStream)
        if collectCorpusStatistics:
            self.collectCorpusStatistics(fileList, docTmpDir)

    # More things you can override. Originally, this code was in the
    # experiment engine, because that's where it's used, but in some rare
    # situations, the corpus that's passed in to the model builder is not
    # exactly the corpus that's used to build the model. This situation might
    # arise if you have a special model builder you're using in experiments
    # which incrementally builds the model on the last one, or has to do
    # some extensive computation to prepare the corpus, which changes the
    # corpus statistics. So I've moved the code here, so it can be
    # overridden by these special model builders. Most people will never,
    # ever have to touch it.

    def reportCorpusStatistics(self):
        if hasattr(self, "corpusStatistics"):
            return self.corpusStatistics
        else:
            return {"totalDocuments": 0,
                    "totalItems": 0,
                    "totalTokens": 0,
                    "totalItemTokens": 0,
                    "totalItemsByTag": {},
                    "totalItemTokensByTag": {}}

    def collectCorpusStatistics(self, fileList, docTmpDir):
        totalDocuments = len(fileList)
        totalItems = 0
        totalTokens = 0
        totalItemTokens = 0
        totalItemsByTag = {}
        totalItemTokensByTag = {}
        for f in fileList:            
            thisTotalItems, thisTotalItemTokens, thisTotalItemsByTag, \
                            thisTotalTokens, thisTotalItemTokensByTag = self.collectFileStatistics(f, docTmpDir)
            totalItems += thisTotalItems
            totalTokens += thisTotalTokens
            totalItemTokens += thisTotalItemTokens
            for k, v in thisTotalItemsByTag.items():
                try:
                    totalItemsByTag[k] += v
                except KeyError:
                    totalItemsByTag[k] = v
            for k, v in thisTotalItemTokensByTag.items():
                try:
                    totalItemTokensByTag[k] += v
                except KeyError:
                    totalItemTokensByTag[k] = v
        self.corpusStatistics = {"totalDocuments": totalDocuments,
                                 "totalItems": totalItems,
                                 "totalTokens": totalTokens,
                                 "totalItemTokens": totalItemTokens,
                                 "totalItemsByTag": totalItemsByTag,
                                 "totalItemTokensByTag": totalItemTokensByTag}

    # This is the important one, I think. For each document, we open it up
    # and loop through the content and lex tags. But we need to do it within
    # a particular region, say, zones.
    
    def collectFileStatistics(self, trainingF, docTmpDir):

        f = os.path.join(docTmpDir, os.path.basename(trainingF))
        _jsonIO = MAT.DocumentIO.getDocumentIO('mat-json', task = self.task)
        doc = _jsonIO.readFromSource(f)

        return self.collectDocumentStatistics(doc, [(zone.start, zone.end)
                                                    for zone in doc.orderAnnotations(self.task.getAnnotationTypesByCategory("zone"))])

    # collectDocumentStatistics needs to do something sensible for
    # spanless annotations. So what I'm going to do is compute the
    # implied span of the spanless content annotations, and those
    # which have no span will be assigned the start index of the
    # first zone, and the end index of the last. Then, we
    # filter by regions.

    def collectDocumentStatistics(self, doc, orderedRegionList):
        
        contentTags = {}
        totalItems = 0
        totalByTag = {}
        totalToksByTag = {}
        totalToks = 0
        totalItemToks = 0
        task = self.task
        
        localToks = []
        localSpannedContent = []
        localSpanlessContent = []
        for atype, annots in doc.atypeDict.items():
            if MAT.Score.checkLexTag(contentTags, atype, task):
                localToks += annots
            elif MAT.Score.checkContentTag(contentTags, atype, task):
                if atype.hasSpan:
                    localSpannedContent += annots
                else:
                    localSpanlessContent += annots

        maxRegionHash = {}
        if localSpanlessContent:
            regionList = MAT.Document.AnnotatedDoc.processableRegions([doc], task = task)[0]
            maxRegionHash[doc] = (regionList[0][0], regionList[-1][1])            

        # Now we have all the relevant objects. We need to use the same
        # algorithm from Score.py to filter by regions. 

        (localSpannedContent, localToks), (localSpanlessContent,) = \
                              MAT.Pair.PairState.filterByRegions(orderedRegionList,
                                                                 spannedLists = [localSpannedContent, localToks],
                                                                 spanlessLists = [localSpanlessContent],
                                                                 maxRegionHash = maxRegionHash)
        
        localContent = localSpannedContent + localSpanlessContent

        localContent = [(task.getEffectiveAnnotationLabel(annot), annot) for annot in localContent]

        # Now, they're filtered and labeled. I can finally collect the statistics.

        totalToks = len(localToks)
        totalItems = len(localContent)

        for lab, annot in localContent:
            if totalByTag.has_key(lab):
                totalByTag[lab] += 1
            else:
                totalByTag[lab] = 1

        # Sort the tokens, and label them using the same algorithm
        # from Score.py. Be aware that there may be no tokens.

        if localToks:
            tStartMap = {}
            tEndMap = {}

            j = 0
            for t in localToks:
                tStartMap[t.start] = j
                tEndMap[t.end] = j
                j += 1
            for label, ann in localContent:
                # What should we do if the indices don't line up?
                # Keep going backward and/or forward until you
                # find something that works? What a mess. Either
                # that, or we'd have to abort collecting the statistics.
                s = ann.start
                noTokens = False
                while True:
                    try:
                        startI = tStartMap[s]
                        break
                    except KeyError:
                        # Let's say the start doesn't line up.
                        # What to do? Start shrinking it.
                        # If you can't find a token that starts
                        # in the annotation, there are no
                        # tokens.
                        s += 1
                    if s >= ann.end:
                        noTokens = True
                        break
                if not noTokens:
                    e = ann.end
                    while True:
                        try:
                            endI = tEndMap[e]
                            break
                        except KeyError:
                            # Shrink the end.
                            e -= 1
                        if e <= ann.start:
                            noTokens = True
                            break
                if noTokens:
                    tokIncrement = 0
                else:
                    tokIncrement = 1 + (endI - startI)
                try:
                    totalToksByTag[label] += tokIncrement
                except KeyError:
                    totalToksByTag[label] = tokIncrement
                totalItemToks += tokIncrement

        return totalItems, totalItemToks, totalByTag, totalToks, totalToksByTag
