# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This file will deal with encapsulations for training and for scoring
# the resulting runs. This is all specific
# to Carafe.

# On top of this, we want to build a facility for preparing the
# data set: splitting it up into train and test, etc.

import glob, os, random, shutil, time, datetime, csv, sys, codecs, weakref, re

random.seed()

class ExperimentError(Exception):
    pass

class FlushingOutStream:

    def __init__(self, stream):
        self.stream = stream

    def write(self, s):
        self.stream.write(s)
        self.stream.flush()

flushedStdout = FlushingOutStream(sys.stdout)

import MAT.Config, MAT.ToolChain
from MAT.PropertyCache import PropertyCache

MAT_PKG_HOME = MAT.Config.MATConfig["MAT_PKG_HOME"]

#
# The training run.
#

# The training run is either instantiated from an existing run dir,
# or from a document training set.

# trainingEngine: the path to the training engine, following MAT_CRF_BIN.
# trainingIncrement: if not None, an integer to
# represent how many pots to break up the files into
# for incremental training.

# Do the training run if the directory doesn't exist, or if
# it wasn't finished.

def _markDone(dir):
    fp = open(os.path.join(dir, "_done"), "w")
    fp.close()

def _unmarkDone(dir):
    if os.path.isfile(os.path.join(dir, "_done")):
        os.remove(os.path.join(dir, "_done"))

def _isDone(dir):
    return os.path.isfile(os.path.join(dir, "_done"))

def _stringSplit(s, *args):
    r = s.split(*args)
    if r == ['']:
        return []
    else:
        return r

def _stringPairWithNone(s, *args):
    r = s.split(*args)
    if r == ['']:
        return []
    elif r[1] == "None":
        return [r[0], None]
    else:
        return r

# Now that we can have multiple training corpora, we need to
# store and retrieve them, by directory name. trainingCorpora is
# a list of pairs of <corpusobj>, <partition>.

import MAT.Bootstrap

class TrainingRunInstance(MAT.Bootstrap.TrainingRunInstance):
    
    def setContext(self, engine):

        self._updateFromEngine(engine)
        
        # The kw is attributes from the model class in the task.
        # I need to store the attributes using the PropertyCache.
        
        self.pCache = PropertyCache(self, os.path.join(self.modelDir, "properties.txt"),
                                    ("date", lambda obj, v: None,
                                     lambda obj, v: datetime.datetime.now().ctime()),
                                    ("engineSettings", None, None),
                                    ("corpusSettings", None, None))

        if os.path.isdir(self.modelDir) and os.path.exists(self.pCache.file):
            self.pCache.load()
        else:
            if not os.path.exists(self.modelDir):
                print >> flushedStdout, "Creating model directory", self.modelDir, "..."
                os.makedirs(self.modelDir)
            
            self.pCache.save()

        self._configureBuilder()
        
        if self.engine.markDone:
            _markDone(self.modelDir)
    
    # The trainer requires all the files in a single directory, so we
    # take the files and put them somewhere random.
    # The format of the model output dir is a file containing
    # the file list at the toplevel, and a subdir for each increment.
    # I'm going to use the modelOutputDir also as the temp location,
    # because that's the safest thing to do - that location will have
    # to be appropriately protected for sensitive data.
    
    def train(self, interleave = False, **kw):

        task = self.engine.task
        force = self.engine.force

        if (not force) and _isDone(self.modelDir):
            print >> flushedStdout, "Model already built."
            return
        else:
            _unmarkDone(self.modelDir)

        MAT.Bootstrap.TrainingRunInstance.train(self, interleave = interleave, collectCorpusStatistics = True, **kw)

        _markDone(self.modelDir)

# The model needs to track the annotation counts for each training element,
# and compute the counts for each model run.

# Note that one of the problems we need to deal with is that
# when the training run restarts, it needs to capture the
# seed corpus that was stored, IN ORDER, because of the
# potential for iterators.

class TrainingRun(MAT.Bootstrap.TrainingRun):

    def __init__(self, mName, instanceClass = TrainingRunInstance, flushedStdout = flushedStdout, **kw):

        MAT.Bootstrap.TrainingRun.__init__(self, mName, instanceClass = instanceClass,
                                           flushedStdout = flushedStdout, **kw)
        
    def _collectTrainingSet(self, engine):

        # Let's either cache the partitions or load them, using the PropertyCache.
        pFile = engine.getModelDirPrefix(self) + "_properties.txt"
        tFile = engine.getModelDirPrefix(self) + "_training_set.txt"
        self.pCache = PropertyCache(self, pFile,
                                    ("configName", None, None),
                                    ("trainingCorpora", lambda obj, v: [_stringPairWithNone(x, ",")
                                                                        for x in _stringSplit(v, "|")],
                                     lambda obj, v: "|".join(["%s,%s" % (a, b) for a, b in v])))

        if os.path.exists(self.pCache.file):
            if self.trainingCorpora is not None:
                print >> flushedStdout, "Warning: ignoring trainingCorpora in favor of modelDir"
            self.pCache.load()
            fp = open(tFile, "rb")
            elts = []
            for line in fp.readlines():
                # print line,
                dsetName, partition, f = line.strip().split("|")
                elts.append(((dsetName, partition or None), f))
            fp.close()
            return elts
        else:
            if self.trainingCorpora is None:
                raise ExperimentError, "training corpora required"
            if not os.path.isdir(os.path.dirname(pFile)):
                print >> flushedStdout, "Creating training directory", os.path.dirname(pFile), "..."
                os.makedirs(os.path.dirname(pFile))
            self.pCache.save()
            elts = MAT.Bootstrap.TrainingRun._collectTrainingSet(self, engine)
            # Must save this away, because the order needs to be retained.
            # The list is ((dsetName, partition) f) elements.
            fp = open(tFile, "wb")
            for ((dsetName, partition), f) in elts:
                fp.write("|".join([dsetName, partition or "", f]) + "\n")
            fp.close()
            return elts

#
# The test object.
#

# The engineOptions is just the arguments to select the
# task and workflow. Input/output will be handled by the test
# utility. It should be possible to do this on a saved model
# directory, by instantiating the TrainingSet object on an
# existing model output directory.

# The test run should do a couple things. First, we need to know
# the number of tags in each training increment. Second, we need to
# track, for each tag and for the total, what the various values
# are at each increment.

import MAT.DocumentIO, MAT.Score

from MAT.Score import LiteralScoreColumn, ComputedScoreColumn, FakeScoreColumn

class ExperimentSummaryResultTable(MAT.Score.SummaryScoreResultTable):
    
    def __init__(self, computeConfidenceData = False, **kw):
        self.numDocs = 0
        self.totalToks = 0
        self.tagTable = {}
        self.numTrainingItems = 0
        selfProxy = weakref.proxy(self)
        # Always compute confidence data.
        MAT.Score.SummaryScoreResultTable.__init__(self, computeConfidenceData = computeConfidenceData, **kw)
        self._addColumn(ComputedScoreColumn("train docs", 
                                            colKey = "train_docs",
                                            inputs = [],
                                            computeFn = lambda scorer: selfProxy.numDocs),
                        after = "tag")
        self._addColumn(ComputedScoreColumn("train toks", 
                                            colKey = "train_toks",
                                            inputs = [],
                                            computeFn = lambda scorer: selfProxy.totalToks),
                        after = "train docs")
        self._addColumn(ComputedScoreColumn("train items", 
                                            colKey = "train_items",
                                            inputs = ["tag"],
                                            computeFn = lambda scorer, tag: selfProxy.computeTrainingItems(scorer, tag)),
                        after = "train toks")

    def setTotals(self, numDocs, totalToks, tagTable, numTrainingItems):
        self.numDocs = numDocs
        self.totalToks = totalToks
        self.tagTable = tagTable
        self.numTrainingItems = numTrainingItems

    def computeTrainingItems(self, scorer, tag):

        if tag.data == "<all>":
            return self.numTrainingItems
        elif self.tagTable.has_key(tag.data):
            return self.tagTable[tag.data]
        else:
            return 0

    def _newInstance(self):        
        newCopy = MAT.Score.SummaryScoreResultTable._newInstance(self)
        newCopy.numDocs = self.numDocs
        newCopy.totalToks = self.totalToks
        newCopy.numTrainingItems = self.numTrainingItems
        newCopy.tagTable = self.tagTable
        return newCopy

class ExperimentDetailResultTable(MAT.Score.DetailScoreResultTable):

    def __init__(self, **kw):
        self.numDocs = 0
        MAT.Score.DetailScoreResultTable.__init__(self, **kw)
        selfProxy = weakref.proxy(self)
        self.addColumn(ComputedScoreColumn("training docs", 
                                           colKey = "training_docs",
                                           inputs = [],
                                           computeFn = lambda scorer, **kw: selfProxy.numDocs))

    def setTotals(self, numDocs):
        self.numDocs = numDocs

class TestRunInstance(MAT.Bootstrap.TestRunInstance):

    def __init__(self, *args, **kw):
        MAT.Bootstrap.TestRunInstance.__init__(self, *args, **kw)
        self.scoreOptions = self.template.scoreOptions
        self.csvTagScorer = None
        self.csvTokenScorer = None
        self.detailScorer = None
        self.scoreObjs = []
        self.scoresSaved = False
        self._incrementCache = None

    def setContext(self, engine, mInstance):

        MAT.Bootstrap.TestRunInstance.setContext(self, engine, mInstance)
        
        self.computeConfidence = engine.computeConfidence
        self.pCache = PropertyCache(self, os.path.join(self.runDir, "properties.txt"),
                                    ("engineOptions", None, None),
                                    ("scoreOptions", None, None),
                                    ("enginePrepOptions", None, None))

        if os.path.isdir(self.runDir) and os.path.exists(self.pCache.file):
            self._configureFromRunDir()
        else:
            if not os.path.isdir(self.runDir):
                print >> flushedStdout, "Creating run directory", self.runDir, "..."
                os.makedirs(self.runDir)
            if self.engineOptions is None:
                raise ExperimentError, "engine options are missing"
            self.pCache.save()

    def _configureFromRunDir(self):
        self.pCache.load()

    def prepareTest(self, markDoneIsFalse = False):

        expEngine = self.engine
        force = expEngine.force

        markDone = expEngine.markDone
        if markDoneIsFalse:
            markDone = False
        
        if markDone:
            _markDone(self.runDir)
        print >> flushedStdout, "\n### Preparing run", self.runName

        runInputTestDir = os.path.join(self.runDir, "run_input")

        if (not force) and _isDone(self.runDir):
            # Must deconflict, since the scorer expects it to have happened.
            self.testSet._deconflict()
            print >> flushedStdout, "Run already completed."
            if self.engine.rescoreRuns:
                self.reportScores()
            return
        else:
            # Just remove and recreate the run dir.
            if os.path.isdir(self.runDir):
                shutil.rmtree(self.runDir)
                os.makedirs(self.runDir)

        self._prepareTestCorpus()

        self._initializeScorers()

    def _initializeScorers(self):
        task = self.engine.task
        format = self.engine.scoreFormat
        self.csvTagScorer = task.augmentTagSummaryScoreTable(ExperimentSummaryResultTable(format = format, computeConfidenceData = self.computeConfidence))
        self.csvTokenScorer = task.augmentTokenSummaryScoreTable(ExperimentSummaryResultTable(forTokens = True, format = format, computeConfidenceData = self.computeConfidence))
        self.detailScorer = task.augmentDetailScoreTable(ExperimentDetailResultTable(format = format))
        # I need to hold onto these until all the increments are written, so the
        # weakrefs to the corpus aggregates hang around.
        self.scoreObjs = []

    def test(self, **kw):

        if _isDone(self.runDir):
            return

        MAT.Bootstrap.TestRunInstance.test(self, **kw)

        self._scoreHypothesis()

    def finishTest(self):

        if _isDone(self.runDir):
            return
        
        _markDone(self.runDir)
        self.saveScores()

    def saveScores(self):
        if not self.scoresSaved:
            print >> flushedStdout, "Saving results for run %s..." % self.runName
            self._writeScorers()
            self.scoresSaved = True
            
    def _writeScorers(self):
        self.csvTagScorer.writeCSVByFormat(self.runDir, "bytag")
        self.csvTokenScorer.writeCSVByFormat(self.runDir, "bytoken")
        self.detailScorer.writeCSV(os.path.join(self.runDir, "details.csv"))
        self.engine._augmentCumulativeScorers(self)
        # Delete the scorers and the score objects, to free the memory.
        self.csvTagScorer = self.csvTokenScorer = self.detailScorer = None
        self.scoreObjs = []

    def reportScores(self):

        # We want to interleave score reporting with running,
        # so we'll decompose this.

        self._initializeScorers()
        
        self._scoreHypothesis()
        print >> flushedStdout, "Saving results..."
        self._writeScorers()

    def _scoreHypothesis(self):

        print >> flushedStdout, "Scoring hypothesis for %s and %s..." % (self.runSubdir, self.model.modelSubdir)
        stats = self.model.builder.reportCorpusStatistics()
        
        i = stats["totalDocuments"]

        incrementTots = stats["totalItems"]
        incrementItemTokTots = stats["totalItemTokens"]
        incrementTotsByTag = stats["totalItemsByTag"]
        totalToks = stats["totalTokens"]
        incrementTotsByToken = stats["totalItemTokensByTag"]
        
        csvRows = []
        hypDir = os.path.join(self.runDir, "hyp")
        # Create a list of (hyp, ref) filename pairs. We need to make sure
        # that all the training tags are referenced in the scorer, even those
        # that don't appear.
        self.csvTagScorer.setTotals(i, totalToks,
                                    incrementTotsByTag,
                                    incrementTots)
        self.csvTokenScorer.setTotals(i, totalToks,
                                      incrementTotsByToken,
                                      incrementItemTokTots)
        self.detailScorer.setTotals(i)
        scoreOpts = self.scoreOptions or {}
        scoreObj = MAT.Score.Score(tagSeedList = incrementTotsByTag.keys(),
                                   tagResultTable = self.csvTagScorer,
                                   tokenResultTable = self.csvTokenScorer,
                                   detailResultTable = self.detailScorer,
                                   task = self.engine.task, **scoreOpts)
        scoreObj.addFilenamePairs([(os.path.join(hypDir, b + ".prepped.tag.json"), f) for (f, b) in self.testSet.deconflictions.items()])
        print >> flushedStdout, scoreObj.formatResults(byToken = False, detail = False)
        self.scoreObjs.append(scoreObj)

class TestRun(MAT.Bootstrap.TestRun):

    def __init__(self, rName, instanceClass = TestRunInstance, flushedStdout = flushedStdout,
                 scoreOptions = None, **kw):
        MAT.Bootstrap.TestRun.__init__(self, rName, instanceClass = instanceClass,
                                       flushedStdout = flushedStdout, **kw)
        self.scoreOptions = scoreOptions

    def _configureTestCorpus(self, engine):
        # We load the partitions from the PropertyCache, or save them there.
        pFile = engine.getRunDirPrefix(self) + "_properties.txt"
        self.pCache = PropertyCache(self, pFile,
                                    ("modelName", None, None),
                                    ("testCorpora", lambda obj, v: [_stringPairWithNone(x, ",")
                                                                    for x in _stringSplit(v, "|")],
                                     lambda obj, v: "|".join(["%s,%s" % (a, b) for a, b in v])))

        if os.path.exists(self.pCache.file):
            self.pCache.load()
        else:
            if not os.path.isdir(os.path.dirname(pFile)):
                print >> flushedStdout, "Creating run directory", os.path.dirname(pFile), "..."
                os.makedirs(os.path.dirname(pFile))                
            if self.modelName is None:
                raise ExperimentError, "model is missing"
            if self.testCorpora is None:
                raise ExperimentError, "test corpora are missing"
            self.pCache.save()
        return MAT.Bootstrap.TestRun._configureTestCorpus(self, engine)

#
# The experiment corpus object.
#

# This object starts with a document set, splits it up
# into training and test document sets, preprocessing
# both components if appropriate.

# Or, we can have a specially set-aside test corpus.
# We might use this test corpus for lots of experiments.
# How do we prep it?

# I think we need to separate the corpus types from
# the actual processing.

# We also need to cap the number of files if we end up
# with a partial amount (e.g., an extra 3 out of 50)
# which would force an additional round of learning.

# If sourceCorpusDir is set, then the various prep settings
# (asTrain, testFraction, prepOptions, maxCorpusSize,
# truncateFirst) should override
# what's in the source corpus. So we need to manage the processing
# very carefully. 

from MAT.Bootstrap import DocumentSet

class PreparedCorpus(DocumentSet):

    def __init__(self, corpusName, prepOptions = None, maxCorpusSize = None,
                 truncateFirst = False, sourceCorpusDir = None,
                 partitions = None, partitionIsFixed = False, **kw):

        # NOTE THAT WE DON'T CALL THE DocumentSet.__init__ until setContext()
        # is called.

        # (self, corpusDir, inputDocumentSet = None, asTrain = False,
        #         prepOptions = None, maxCorpusSize = None,
        #         testFraction = None, truncateFirst = False, sourceCorpusDir = None):

        # First problem: if this has a sourceCorpusDir, it doesn't do the _populate step.
        # See the implementation of the _populate method. And we don't appear to
        # want to do the partitions quite yet, so we've captured them above. But
        # that means I need to store them.

        # Actually, now that I'm actually creating the objects in fromXML,
        # I need to postpone just about everything except storing the variables.

        # And because of the ad-hoc way I'm storing the partition information
        # "None" can't be the name of a partition.

        if partitions is not None:
            for k, v in partitions:
                if v == "None":
                    raise ExperimentError, "'None' is not a legal corpus partition name"                
        
        self.sourceCorpusDir = sourceCorpusDir
        self.corpusName = corpusName
        self.prepOptions = prepOptions
        self.maxCorpusSize = maxCorpusSize
        self.truncateFirst = truncateFirst
        self.sourceCorpus = None
        # Partitions are retrieved from the cache as a list.
        # And the rest of the code assumes it's a list.
        self.partitionList = partitions or []
        self.partitionIsFixed = partitionIsFixed
        self.filesPrepared = False
        self._kw = kw
        self._limitTable = None

    def setContext(self, engine):

        self.engine = engine
        self.corpusDir = engine.getCorpusDir(self)

        # For some reason, we don't appear to be cacheing the input
        # file patterns for the document set, quite yet. I'm going to bet
        # that, ultimately, we're not going to be cacheing the
        # partitions right here, but rather storing them when
        # we produce the file seed.
        
        self.pCache = PropertyCache(self, os.path.join(self.corpusDir, "properties.txt"),
                                    # ("asTrain", lambda obj, v: v == "True", None),
                                    ("prepOptions", None, None),
                                    ("maxCorpusSize", lambda obj, v: int(v), None),
                                    ("partitionList", lambda obj, v: [(a, float(b)) for a, b in [_stringSplit(x, ",") for x in _stringSplit(v, "|")]],
                                     lambda obj, v: "|".join(["%s,%s" % (a, b) for a, b in v])),
                                    ("partitionIsFixed", lambda obj, v: v == "True", None),
                                    ("truncateFirst", lambda obj, v: v == "True", None),
                                    ("sourceCorpusDir", None, None))
        
        if os.path.isdir(self.corpusDir) and os.path.exists(self.pCache.file):
            self._configureFromCorpusDir()
        else:
            DocumentSet.__init__(self, self.corpusName, **self._kw)

            # The directory will contain a file list,
            # after all the preparation is done, unless
            # there's a source corpus.            

            if not os.path.isdir(self.corpusDir):
                print >> flushedStdout, "Creating corpus directory", self.corpusDir, "..."
                os.makedirs(self.corpusDir)

            if self.sourceCorpusDir is None:
                self._prepareFileSeed()
            else:
                self.sourceCorpus = PreparedCorpus(self.sourceCorpusDir)
                self.engine.corpusDirs[self.sourceCorpusDir] = self.sourceCorpusDir
                self.sourceCorpus.setContext(self.engine)
            self.pCache.save()

        if engine.markDone:
            _markDone(self.corpusDir)
        
    
    def _populate(self, filePats, fileFile, fileList, prefix, flushedStdout, skipRemoteCorpus = True):
        if (not skipRemoteCorpus) or (not self.sourceCorpusDir):
            DocumentSet._populate(self, filePats, fileFile, fileList, prefix, flushedStdout)

    # This is an operation that isn't required on the parent. We need to
    # clomp down on all the partitions, if they exist, and then
    # reconstitute the files. If there are no partitions, we just
    # clomp down on the files. I don't think that the corpus will
    # have been partitioned by the point of the only current use of
    # this method, but it can't hurt to be thorough.

    # In order to truncate, we always limit first.
    
    def truncate(self, maxCorpusSize):
        total = len(self.files)
        if total <= maxCorpusSize:
            return
        # If it's already been partitioned...
        if self.partitionDict is not None:
            raise ExperimentError, "truncate should never follow partitioning"
        # Remove all references to these.
        for f in self.files[maxCorpusSize:]:
            del self._filesSeen[f]
        self.files[maxCorpusSize:] = []

    # When we limit, we need to ensure that the documents
    # in the file list, if there is a partition list,
    # are the union of the documents in the limited
    # portion of each partition.

    # We also have to be careful to ensure that if
    # the partition is fixed, the right things happen.
    # In this case, the total of the non-remainder partitions
    # must be less than the max corpus size.
    
    def _limit(self):
        if self.maxCorpusSize is None:
            return
        if self.maxCorpusSize >= len(self.files):
            return
        if len(self.partitionList) == 0:
            # No need to do anything.
            return
        # All we're storing is the integers. But we have to make
        # sure the files are in the proper order.
        self._limitTable = {}
        pairs = self.partitionList
        files = self.files
        if self.partitionIsFixed:
            if sum([val for pName, val in pairs if val != self.FIXED_PARTITION_REMAINDER]) > self.maxCorpusSize:
                raise ExperimentError, "Can't limit fixed partition below the total of the non-remainder partitions"
            # There may or may not be a fixed partition. Reorder
            # the files so the first n correspond to the things in the
            # partition dict.
            self.files = []
            tot = 0
            remainder = None
            for pName, val in pairs:
                if val != self.FIXED_PARTITION_REMAINDER:
                    self.files += self.partitionDict[pName]
                    tot += val
                    self._limitTable[pName] = val
                else:
                    remainder = pName
            remainingFiles = list(set(files) - set(self.files))
            # Put the remaining files at the end. If there's
            # a remainder, put the rest of what's permitted in
            # that partition.
            self.files += remainingFiles            
            if remainder:
                self._limitTable[pName] = self.maxCorpusSize - tot
                self.partitionDict[remainder] = remainingFiles[:self.maxCorpusSize - tot]
        else:
            # Better reorder them.
            self.files = []
            otherFiles = []
            soFar = 0
            for p in pairs:
                pName, share = p
                if p is pairs[-1]:
                    thisLen = self.maxCorpusSize - soFar
                    self._limitTable[pName] = thisLen
                else:
                    # Odd things happen if you let .5 always round up.
                    amt = share * self.maxCorpusSize
                    if (round(amt) == (amt + .5)) and random.choice([True, False]):
                        thisLen = int(round(amt)) - 1
                    else:
                        thisLen = int(round(amt))
                    self._limitTable[pName] = thisLen
                    soFar += thisLen
                self.files += self.partitionDict[pName][:thisLen]
                otherFiles += self.partitionDict[pName][thisLen:]
            self.files += otherFiles                

    def getFiles(self, partition = None):
        files = DocumentSet.getFiles(self, partition = partition)
        if self.maxCorpusSize is None:
            return files
        elif (partition is not None) and (self._limitTable is not None):
            # If we got this far, there's a partition; but there
            # may not be any limit.
            return files[:self._limitTable[partition]]
        else:
            return files[:self.maxCorpusSize]
    
    def _prepareFileSeed(self):
        
        # Here, we randomize the documents, truncate first, if appropriate,
        # and then deconflict basenames, and finally save out a file seed.
        # The file seed will now be consistent across reprocessings.
        # The corpus will already have been partitioned, by virtue of the
        # parent __init__ function. This is only called if sourceCorpusDir
        # is None.

        maxCorpusSize = self.maxCorpusSize
        corpusDir = self.corpusDir
        basenameCopyDir = os.path.join(corpusDir, "renamed")

        if (maxCorpusSize is not None) and self.truncateFirst:
            print >> flushedStdout, self.corpusDir, ":", "Truncating corpus first..."
            self.truncate(maxCorpusSize)

        # Previously, we did deconfliction here, but I'm thinking that I never
        # need that until it's time to consolidate, which it isn't yet. OK, I'm
        # wrong; in order to inherit remote splits, we need to be able to
        # do the basename mapping, which means this needs to happen very early.
        # And, in fact, we need to defeat the deconfliction a bit, because
        # we'll actualy be moving some files.
        print >> flushedStdout, self.corpusDir, ":", "Deconflicting basenames..."
        self._deconflict()
        foundConflicts = False
        fp = None
        for k, v in self.deconflictions.items():
            if v != os.path.basename(k):
                if not foundConflicts:
                    # First one.
                    fp = open(os.path.join(corpusDir, "renamed.txt"), "w")
                    foundConflicts = True
                # It was moved.
                newFilename = os.path.join(basenameCopyDir, v)
                fp.write("%s|%s" % (k, newFilename))
                shutil.copy(k, newFilename)
                # And replace it in the files. Assuming we have no partition here yet.
                self.files[self.files.index(k)] = newFilename
                del self.deconflictions[k]
                self.deconflictions[newFilename] = v
        if fp is not None: fp.close()
        
        # Finally, save out the file seed. There ain't no partition here yet.
        self.savePaths(os.path.join(corpusDir, "file_seed.txt"))

    def getSourceCorpusMaxCorpusSize(self):
        if self.sourceCorpus:
            if self.sourceCorpus.maxCorpusSize:
                return self.sourceCorpus.maxCorpusSize
            else:
                return self.sourceCorpus.getSourceCorpusMaxCorpusSize()
        else:
            return None

    def getSourceCorpusWithPartition(self):

        # Can we be arbitrarily remote? I think so, because the basenames are
        # deconflicted at the very beginning, and that's what we use to inherit
        # the split.

        if self.sourceCorpus:
            if self.sourceCorpus.partitionList:
                return self.sourceCorpus
            else:
                return self.sourceCorpus.getSourceCorpusWithPartition()
        else:
            return None        

    def prepare(self, outPrefix = ""):

        task = self.engine.task
        force = self.engine.force
        corpusDir = self.corpusDir
        prepDir = os.path.join(corpusDir, "preprocessed")

        # Make sure the source corpus is prepared, if it exists.
        if self.sourceCorpus:
            # Try to build and prepare the corpus.
            self.sourceCorpus.prepare(outPrefix = "Source corpus: ")
        
        if (not force) and _isDone(self.corpusDir):
            print >> flushedStdout, outPrefix + "Corpus already prepared."
            return
        else:
            _unmarkDone(self.corpusDir)
            if os.path.isdir(prepDir):
                shutil.rmtree(prepDir)
            # Gotta undo everything except the seed.
            preparedFile = os.path.join(self.corpusDir, "prepared_files.txt")
            if os.path.isfile(preparedFile):
                os.remove(preparedFile)
            partitionFile = os.path.join(self.corpusDir, "file_partition.txt")
            if os.path.isfile(partitionFile):
                os.remove(partitionFile)
            self._initVars()
            if self.sourceCorpusDir is None:
                self._populate(None, os.path.join(self.corpusDir, "file_seed.txt"), None, None, flushedStdout,
                               skipRemoteCorpus = False)
        
        # OK, we're now at a point where we have a file seed either for
        # the local corpus or the remote corpus. Furthermore, the remote
        # corpus, if present, has had its split and preprocessing done.
        # Now, I have to combine them.

        # At this point, either the local or remote preprocessing is
        # reflected in the inFiles list. 

        #
        # Interlude: getDocumentSet, which can be folded right into prepare().
        # Or not, because it's recursive.
        #

        # So let's say prepare() is called on a source corpus, and
        # this corpus ITSELF has a source corpus. How do we make
        # sure the right things happen with respect to the document
        # space? The problem is that it's gotta configure itself appropriately,
        # but only prepare() knows about the source corpus. That
        # might be the problem.

        # I don't want simply to cache the values from the source
        # corpus here, because, for instance, I want to inherit a
        # source corpus split if there is one, rather than redo the split
        # locally.

        # Recursive getters, using the source corpus.
        
        if not self.filesPrepared:

            if self.prepOptions is not None:

                # Try to do it as batch, if possible.
                inDir = os.path.join(prepDir, "in")
                outDir = os.path.join(prepDir, "out")
                os.makedirs(inDir)
                os.makedirs(outDir)

                # Get the OUTPUT of the processing for the source corpus.
                # So we can do prep on top of prep, if there's a sourceCorpus.
                
                prepDocSet = self.sourceCorpus or self
                prepDocSet.consolidate(inDir, lambda inf, outf: shutil.copy(inf, outf))
                inFiles = [os.path.join(outDir, basename) for basename in prepDocSet.deconflictions.values()]

                # Now, preprocess them as a batch.
                print >> flushedStdout, outPrefix + self.corpusDir, ":", "Preprocessing documents..."

                # We control all the locations, and the output file type.
                for key in ["output_file_type", "input_file", "input_dir", "output_file",
                            "output_dir", "input_file_re", "output_fsuff", "output_encoding"]:
                    if self.prepOptions.has_key(key):
                        raise ExperimentError, ("%s not permitted in corpus prep step" % key)
                
                t = time.time()

                print >> flushedStdout, "Invoking MATEngine:", " ".join(['%s: "%s"' % pair for pair in self.prepOptions.items()])
                # The workflow had better be there. This will raise an error if it
                # isn't, most likely.
                e = MAT.ToolChain.MATEngine(taskObj = task, workflow = self.prepOptions.get("workflow"))
                e.Run(output_file_type = "mat-json", input_dir = inDir, output_dir = outDir, **self.prepOptions)
                
                print >> flushedStdout, outPrefix + "Preprocessing completed in %.2f seconds." % (time.time() - t,)
                # Replace the list of files.
                self.files = []
                self._filesSeen = {}
                for f in inFiles:
                    self._addFile(f)
                self.deconflictions = None

            elif self.sourceCorpus:
                # Replace the list of files.
                self.files = []
                self._filesSeen = {}
                for f in self.sourceCorpus.files:
                    self._addFile(f)
                self.deconflictions = None
                # Make sure that EXPLICIT local truncations are imposed before
                # we partition or limit.
                if (self.maxCorpusSize is not None) and self.truncateFirst:
                    self.truncate()

            # At this point, either the local or remote preprocessing is
            # reflected in the inFiles list. 

            self.savePaths(os.path.join(self.corpusDir, "prepared_files.txt"))
            self.filesPrepared = True

        # Now, we impose the local partition
        # settings: partitioning, maxCorpusSize,
        # truncateFirst. We also must be
        # sensitive to the REMOTE settings. Note that in order for
        # there to be any local overrides, partitions
        # or maxCorpusSize MUST be set.

        # What's the logic? We can truncate here as well as at the
        # beginning if truncateFirst is set; it'll just be a no-op here.
        # Actually, we should be more careful about it, because of
        # the complex logic.

        # Do you split first, or truncate first? If we split first and
        # then truncate, we'll have to keep around two copies of the
        # splits: the truncated and the untruncated. But if we
        # truncate and then split, we can't reuse the split; any
        # late truncation would trigger a re-split if there's a remote
        # split. Is this tolerable? No.

        # First you split, then you truncate. If you have a local
        # truncate and a remote split, you can just impose the 
        # truncation proportionally on the split that's already
        # been done. If you have a remote truncate and a local split,
        # do the split randomly and impose the remote truncation. 
        
        # If you have a remote truncate and no split, use it.
        # You can't "turn off" a remote truncate, any more than you
        # can "turn off" a remote prep.

        # I need to make sure I INHERIT THE REMOTE PROPERTIES.
        # Otherwise, when the corpus is reloaded, it won't have
        # any idea that, e.g., it should be split, or limited.

        if len(self.partitionList) > 1:
            # There's a local split.
            self._partition(self.partitionList, self.partitionIsFixed)
            self.savePartition(outPrefix = outPrefix)
        else:
            sourceCorpusWithPartition = self.getSourceCorpusWithPartition()
            if sourceCorpusWithPartition:
                # And make sure to save the partition markup locally.
                self._inheritRemotePartition(sourceCorpusWithPartition)
                self.savePartition(outPrefix = outPrefix)

        # Finally, truncate.

        if self.maxCorpusSize is None:
            limiterMaxSize = self.getSourceCorpusMaxCorpusSize()
            if limiterMaxSize is not None:
                self.maxCorpusSize = limiterMaxSize

        self._limit()

        _markDone(self.corpusDir)

    # This is some nasty work. The split shares are in the sourceCorpus.
    # And so is the split. What we apparently need to do is
    # match up the basenames. THIS is why the basenames need to be
    # updated for the rename, presumably. Is it? I think so.
    
    def _inheritRemotePartition(self, sourceCorpus):
        localDir = {}
        for f in self.files:
            localDir[os.path.basename(f)] = f
        self.partitionList = sourceCorpus.partitionList[:]
        self.partitionDict = {}
        for pName, files in sourceCorpus.partitionDict.items():
            self.partitionDict[pName] = [localDir[os.path.basename(f)] for f in files]
        
    def savePartition(self, outPrefix = ""):

        outFile = os.path.join(self.corpusDir, "file_partition.txt")
        print >> flushedStdout, outPrefix + self.corpusDir, ":", "Creating partitions..."
        DocumentSet.savePartition(self, outFile)

    def _configureFromCorpusDir(self):

        print "Configuring from corpus dir", self.corpusDir

        self._initVars()

        # OK, this is going to be a bit trickier now that we've refactored
        # the document set. We no longer have a distinction between
        # the prepared corpus and the document set, and the prepared files
        # replace the original ones. So we should first check to see
        # if there's prepared files, and if there is, load that.

        # What I don't understand is how the corpus may ever get not to
        # be prepared. I anticipate that possibility.
        
        self.pCache.load()
        
        if self.sourceCorpusDir is not None:
            self.sourceCorpus = PreparedCorpus(self.sourceCorpusDir)
            self.engine.corpusDirs[self.sourceCorpusDir] = self.sourceCorpusDir
            self.sourceCorpus.setContext(self.engine)

        # So no matter what, there's going to be a prepared_files.txt file.
        # As far as I can tell. There will NOT be a file_seed.txt file
        # if there's a sourceCorpusDir. But _populate is disabled if
        # sourceCorpusDir is present. Is this right? Actually, I think
        # the right thing to do is to always load from _populate. But this
        # needs to be suppressed in the DocumentSet.__init__ call, so I have
        # to do something special when there's a sourceCorpusDir.
        
        preparedFile = os.path.join(self.corpusDir, "prepared_files.txt")
        if not os.path.isfile(preparedFile):
            raise ExperimentError, "There should always be a prepared_files.txt file"
        self._populate(None, os.path.join(self.corpusDir, "prepared_files.txt"), None, None, flushedStdout,
                       skipRemoteCorpus = False)

        # Note that we DO NOT call _partition() here - so the randomization
        # that's saved is preserved.

        partitionFile = os.path.join(self.corpusDir, "file_partition.txt")

        if os.path.isfile(partitionFile):
            self.loadPartition(partitionFile)

        if self.maxCorpusSize is None:
            limiterMaxSize = self.getSourceCorpusMaxCorpusSize()
            if limiterMaxSize is not None:
                self.maxCorpusSize = limiterMaxSize

        self._limit()

#
# Workspace corpora. These are "virtual"; they're just used to
# generate prepared corpora with a particular list of files.
#

import MAT.Workspace
import fnmatch

class WorkspaceCorpusSet:

    def __init__(self, workspaceDir,
                 documentStatuses = None, users = None,
                 includeUnassigned = True, basenameSets = None,
                 basenamePatterns = None,
                 workspaceCorpora = None,
                 corpusClass = PreparedCorpus):
        self.corpusClass = corpusClass
        self.workspaceDir = workspaceDir
        if documentStatuses is not None:
            if type(documentStatuses) in (str, unicode):
                documentStatuses = [s.strip() for s in documentStatuses.split(",")]
            self.documentStatuses = set(documentStatuses)
        else:
            self.documentStatuses = set(["partially corrected", "partially gold", "gold", "reconciled"])
        self.includeUnassigned = includeUnassigned
        self.basenameSets = None
        if basenameSets is not None:
            if type(basenameSets) in (str, unicode):
                basenameSets = [s.strip() for s in basenameSets.split(",")]
            self.basenameSets = set(basenameSets)
        self.basenamePatterns = None
        if basenamePatterns is not None:
            if type(basenamePatterns) in (str, unicode):
                basenamePatterns = [s.strip() for s in basenamePatterns.split(",")]
            self.basenamePatterns = basenamePatterns
        self.users = None
        if users is not None:
            if type(users) in (str, unicode):
                users = [s.strip() for s in users.split(",")]
            self.users = set(users)
        self.workspaceCorpora = workspaceCorpora
        foundRemainder = False
        if workspaceCorpora is None:
            raise ExperimentError, "no workspace corpus specified for workspace corpora"
        # Make sure the remainder corpus is last.
        remainderCorpus = None
        self.workspaceCorpora = []
        for w in workspaceCorpora:
            if w.useWorkspaceRemainder:
                if remainderCorpus:
                    raise ExperimentError, "can't have more than one remainder in workspace corpora"
                remainderCorpus = w
            else:
                self.workspaceCorpora.append(w)
        if remainderCorpus:
            self.workspaceCorpora.append(remainderCorpus)

    # Turns out that in Windows, we MUST make sure
    # we close the workspace DB so that the DB is freed.
    
    def convertToPreparedCorpora(self, task):
        corpusClass = self.corpusClass
        # Open the workspace.
        try:
            w = MAT.Workspace.Workspace(self.workspaceDir)
        except MAT.Workspace.WorkspaceError, e:
            raise ExperimentError, ("error opening workspace: " + str(e))
        if w.task.name != task:
            raise ExperimentError, ("workspace task '%s' is not the same as the experiment task '%s'" % (w.task.name, task))
        # We need to retrieve a bunch of info for the child corpora to digest,
        # namely: all the eligible documents, their basenames, their assignments,
        # their statuses, and which basename sets they're in.
        db = w.getDB()
        # This does some extra work, but I'm not about to modify the API just
        # for this purpose.
        # Let's invert this.
        try:
            basenamesToSets = {}
            for setName, basenames in db.getBasenameSetMap().items():
                for basename in basenames:
                    try:
                        basenamesToSets[basename].add(setName)
                    except KeyError:
                        basenamesToSets[basename] = set([setName])
            filteredBasenameInfo = []
            documentStatuses = self.documentStatuses
            users = self.users
            basenameSets = self.basenameSets
            basenamePatterns = self.basenamePatterns
            includeUnassigned = self.includeUnassigned
            for docName, basename, status, assignedUser, ignore in db.basenameInfo(db.allBasenames()):
                setInfo = basenamesToSets.get(basename) or set()
                if (not includeUnassigned) and (assignedUser is None):
                    continue
                # There are always document statuses.
                if status not in documentStatuses:
                    continue
                # Exclude None. That's handled with includeUnassigned.
                if users and assignedUser and (assignedUser not in users):
                    continue
                if basenameSets and (not (basenameSets & setInfo)):
                    continue
                if basenamePatterns and not any([p for p in basenamePatterns if fnmatch.fnmatch(basename, p)]):
                    continue
                # The final False is for whether it's been claimed or not (for remainder)
                filteredBasenameInfo.append([docName, basename, status, assignedUser, setInfo, False])
            preparedCorpora = []
            prefix = w.getFolder("core").dir
            # The remainder corpus is last.
            for wc in self.workspaceCorpora:
                preparedCorpora.append(wc.convertToPreparedCorpus(filteredBasenameInfo, prefix, corpusClass))
            return preparedCorpora
        finally:
            w.closeDB()

class WorkspaceCorpus:

    def __init__(self, name,
                 documentStatuses = None, users = None,
                 includeUnassigned = None, basenameSets = None,
                 basenamePatterns = None,
                 useWorkspaceRemainder = False, **kw):
        self.corpusKw = kw
        if useWorkspaceRemainder and \
           ((documentStatuses is not None) or \
            (users is not None) or \
            (includeUnassigned is not None) or \
            (basenameSets is not None)):
            raise ExperimentError, "remainder must be specified alone"
        self.name = name
        self.useWorkspaceRemainder = useWorkspaceRemainder
        self.documentStatuses = None
        if documentStatuses is not None:
            if type(documentStatuses) in (str, unicode):
                documentStatuses = [s.strip() for s in documentStatuses.split(",")]
            self.documentStatuses = set(documentStatuses)
        self.basenameSets = None
        if basenameSets is not None:
            if type(basenameSets) in (str, unicode):
                basenameSets = [s.strip() for s in basenameSets.split(",")]
            self.basenameSets = set(basenameSets)
        self.basenamePatterns = None
        if basenamePatterns is not None:
            if type(basenamePatterns) in (str, unicode):
                basenamePatterns = [s.strip() for s in basenamePatterns.split(",")]
            self.basenamePatterns = basenamePatterns
        self.users = None
        if users is not None:
            if type(users) in (str, unicode):
                users = [s.strip() for s in users.split(",")]
            self.users = set(users)
        # Note that this is None, NOT FALSE. We need the distinction below.
        self.includeUnassigned = includeUnassigned

    def convertToPreparedCorpus(self, basenameInfo, prefix, corpusClass):
        if self.useWorkspaceRemainder:
            # The remainder corpus is last.
            docList = [i[0] for i in basenameInfo if not i[5]]
        else:
            documentStatuses = self.documentStatuses
            users = self.users
            basenameSets = self.basenameSets
            includeUnassigned = self.includeUnassigned
            basenamePatterns = self.basenamePatterns
            docList = []
            for bInfo in basenameInfo:
                [docName, basename, status, assignedUser, setInfo, alreadyUsed] = bInfo
                if (includeUnassigned is False) and (assignedUser is None):
                    continue
                if documentStatuses and (status not in documentStatuses):
                    continue
                # Exclude None. That's handled with includeUnassigned.
                if users and assignedUser and (assignedUser not in users):
                    continue
                if basenameSets and (not (basenameSets & setInfo)):
                    continue
                if basenamePatterns and not any([p for p in basenamePatterns if fnmatch.fnmatch(basename, p)]):
                    continue
                bInfo[5] = True
                docList.append(docName)
        if not docList:
            raise ExperimentError, "no documents in workspace corpus"
        # Now I have a doc list.
        return corpusClass(self.name, prefix = prefix, fileList = docList,
                           **self.corpusKw)

#
# Updating the iterators to take option arguments.
#

import MAT.Operation, optparse
from MAT.Operation import OptionBearer

# Base for other folks to define their own iterators.

class Iterator(MAT.Bootstrap.BootstrapIterator, OptionBearer):

    pass

# We need a new optparse type.

def _check_int_or_float(option, opt, value):
    try:
        return optparse._parse_int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            raise optparse.OptionValueError("option %s: invalid int or float value %r" % (opt, value))

class Option(MAT.Operation.Option):

    TYPES = ("int_or_float",) + MAT.Operation.Option.TYPES
    TYPE_CHECKER = MAT.Operation.Option.TYPE_CHECKER.copy()
    TYPE_CHECKER["int_or_float"] = _check_int_or_float    

class IncrementIterator(MAT.Bootstrap.IncrementIterator, OptionBearer):

    argList = [Option("--attribute", dest="attribute", action="store",
                      help = "The attribute of the relevant option set to update. Required."),
               Option("--start_val", dest="startVal", action="store",
                      type="int_or_float",
                      help = "The value to start from. Required."),
               Option("--end_val", dest="endVal", action="store",
                      type="int_or_float",
                      help = "The value to end at. Required."),
               Option("--increment", dest="increment", action="store",
                      type="int_or_float",
                      help = "The increment on each iteration. Required."),
               Option("--force_last", dest="forceLast", action="store",
                      type="boolean", default=False,
                      help = "If true, force the last value to be processed, even if it's not exactly an increment")]

    def __init__(self, optionKey, attribute = None, startVal = None, endVal = None,
                 increment = None, forceLast = False):
        if (attribute is None) or (startVal is None) or (endVal is None) or (increment is None):
            raise ExperimentError, "increment iterator must specify all of attribute, start_val, end_val, increment"
        MAT.Bootstrap.IncrementIterator.__init__(self, optionKey, attribute, startVal,
                                                 endVal, increment, forceLast = forceLast)

class CorpusSizeIterator(MAT.Bootstrap.CorpusSizeIterator, OptionBearer):

    argList = [Option("--start_val", dest="startVal", action="store",
                      type="int_or_float",
                      help = "The corpus size to start from. Default is the increment value."),
               Option("--end_val", dest="endVal", action="store",
                      type="int_or_float",
                      help = "The value to end at. Default is the corpus size."),
               Option("--increment", dest="increment", action="store",
                      type="int_or_float",
                      help = "The increment on each iteration. Required."),
               Option("--force_last", dest="forceLast", action="store",
                      type="boolean", default=False,
                      help = "If true, force the last value to be processed, even if it's not exactly an increment")]

    def __init__(self, startVal = None, endVal = None, increment = None, forceLast = False):
        if increment is None:
            raise ExperimentError, "corpus size iterator must specify increment"
        MAT.Bootstrap.CorpusSizeIterator.__init__(self, increment, startVal = startVal, endVal = endVal, forceLast = forceLast)

class ValueIterator(MAT.Bootstrap.ValueIterator, OptionBearer):

    argList = [Option("--attribute", dest="attribute", action="store",
                      help = "The attribute of the relevant option set to update. Required."),
               Option("--values", dest="values", action="store",
                      help = "A comma-delimited list of values to iterate over. Required."),
               Option("--value_type", dest="valueType", action="store",
                      help = "A type for interpreting the elements in values. Options are float, str, int. Default is str.")]

    def __init__(self, optionKey, attribute = None, values = None, valueType = "str"):
        # Values must be a non-zero string.
        if (attribute is None) or (not values):
            raise ExperimentError, "value iterator must define both attribute and values"
        if valueType not in ["str", "float", "int"]:
            raise ExperimentError, ("unknown value iterator value type '%s'" % valueType)
        vals = values.split(",")
        if valueType == "float":
            vals = [float(v) for v in vals]
        elif valueType == "int":
            vals = [int(V) for v in vals]
        MAT.Bootstrap.ValueIterator.__init__(self, optionKey, attribute, vals)

#
# And finally, the experiment itself. This used to be glommed
# together with the prepared corpus, but it seemed wiser to separate
# them.
#

#
# XML description
#

# See XMLNode.py, and PluginMgr.py for another example.

from xml.dom import Node
from MAT.XMLNode import XMLNodeDescFromFile, XMLNodeFromFile
from MAT.Operation import XMLOpArgumentAggregator

EXP_DESC = XMLNodeDescFromFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "exp_template.xml"))

import MAT.XMLNode, MAT.PluginMgr

# The issue here is that the models can't even be
# instantiated, much less run, until the corpora have been
# prepared, because the model needs to know how many files
# are in the corpus in order to build its increments. So all we can
# really do is check well-formedness when we load the XML - we
# can't actually build the objects. So it's all kind of
# useless. But it's OK, because it's restartable.

# What we'll collect is the keywords which would
# instantiate the engine.

def _engineOptionsToKV(task, attrs):
    e = MAT.ToolChain.MATEngine(taskObj = task, workflow = attrs.get("workflow"))
    aggr = XMLOpArgumentAggregator(attrs)
    return e.aggregatorExtract(aggr)

def fromXML(xmlFile, dir = None, corpusPrefix = None,
            corpusClass = PreparedCorpus,
            modelClass = TrainingRun,
            runClass = TestRun, bindingDict = None):

    expDesc = XMLNodeFromFile(xmlFile, {"experiment": EXP_DESC})
    if expDesc is None:
        raise ExperimentError, ("Couldn't find experiment in %s" % xmlFile)

    kw = {}
    dir = expDesc.attrs["dir"] or dir    

    if dir is None:
        raise ExperimentError, "No experiment directory specified"
    else:
        dir = os.path.abspath(dir)

    # Later in fromXML, we create a tag_set file, so self.dir
    # had better be a directory by then. Oops. not anymore - that's
    # Carafe-specific, and it's more complicated than I originally thought.

    if os.path.isfile(dir):
        raise ExperimentError, "Experiment directory is not a directory"
    if not os.path.isdir(dir):
        # Create it if it doesn't exist, before we copy the XML file.
        os.makedirs(dir)

    if not os.path.isfile(os.path.join(dir, os.path.basename(xmlFile))):
        import shutil
        shutil.copy(xmlFile, dir)

    kw["dir"] = dir

    taskName = expDesc.attrs["task"]

    pDir = MAT.PluginMgr.LoadPlugins()

    if not pDir.has_key(taskName):
        raise ExperimentError, ("unknown task '%s'. Exiting." % taskName)
    task = pDir[taskName]

    kw["task"] = task

    corpusDirs = {}
    modelDirs = {}
    runDirs = {}
    corpora = []
    wsCorpusSets = []
    models = []
    runs = []

    kw["corpusDirs"] = corpusDirs
    kw["modelDirs"] = modelDirs
    kw["runDirs"] = runDirs
    kw["corpora"] = corpora
    kw["workspaceCorpusSets"] = wsCorpusSets
    kw["models"] = models
    kw["runs"] = runs

    # Bindings first.

    bindings = {"EXP_DIR": dir}
    if corpusPrefix is not None:
        bindings["PATTERN_DIR"] = corpusPrefix
    for binding in expDesc.children["binding"]:
        bindings[binding.attrs["name"]] = binding.attrs["value"]
    if bindingDict is not None:
        bindings.update(bindingDict)

    # Now, process the bindings. $() is the pattern. If
    # it isn't found, just keep what you have.
    varPat = re.compile("\$\((.+?)\)")
    def _varRepl(m):
        try:
            return bindings[m.group(1)]
        except KeyError:
            return m.group(0)
    def _updateVals(bNode):
        for k, v in bNode.attrs.items():
            if v is not None:
                bNode.attrs[k] = varPat.sub(_varRepl, v)
        if bNode.text is not None:
            bNode.text = varPat.sub(_varRepl, bNode.text)
        if bNode.wildcardAttrs is not None:
            for k, v in bNode.wildcardAttrs.items():
                if v is not None:
                    bNode.wildcardAttrs[k] = varPat.sub(_varRepl, v)
        for c in bNode.orderedChildren:
            _updateVals(c)

    for c in expDesc.orderedChildren:
        if c.label != "binding":
            _updateVals(c)

    # Corpora first.

    for corpusSet in expDesc.children["corpora"]:
        cDir = corpusSet.attrs["dir"]

        # Now, the build defaults for all these corpora.
        maxSize = None
        prepOptions = None
        truncateFirst = False
        partitionIsFixed = False
        corpusSplits = []
        if corpusSet.children["size"] is not None:
            bNode = corpusSet.children["size"]
            if bNode.attrs["max_size"] is not None:
                maxSize = int(bNode.attrs["max_size"])
            if bNode.attrs["truncate_document_list"] == "yes":
                truncateFirst = True
        for p in corpusSet.children["partition"]:
            splitFraction = float(p.attrs["fraction"])
            pName = p.attrs["name"]
            corpusSplits.append((pName, splitFraction))
        if corpusSplits and corpusSet.children["fixed_partition"]:
            raise ExperimentError, "can't specify both partitions and fixed partitions"
        for p in corpusSet.children["fixed_partition"]:
            partitionIsFixed = True
            splitSize = p.attrs["size"]
            pName = p.attrs["name"]
            if splitSize == "remainder":
                splitSize = PreparedCorpus.FIXED_PARTITION_REMAINDER
            else:
                splitSize = int(splitSize)
            corpusSplits.append((pName, splitSize))

        if corpusSet.children["prep"] is not None:
            # The build settings are now wildcard settings.
            # I can't convert them to actual engine arguments until
            # I have the chance to digest some of the params, and
            # I don't want to do that until we call the engine.
            # So we'll set up an option for the engine where
            # we can pass in an aggregator instead of a kv dict.
            # Well, no. It turns out that if I want to think about calling
            # this from code, this really needs to be converted to what the
            # kv pairs ought to look like. So I'm just going to have
            # to create an engine and throw it away.
            prepOptions = _engineOptionsToKV(task, corpusSet.children["prep"].wildcardAttrs)

        # Now, build individual corpora.
        for corpus in corpusSet.children["corpus"]:
            cName = corpus.attrs["name"]
            # Check the name duplication in the actual bootstrap creation,
            # not here.
            sourceDir = corpus.attrs["source_corpus_dir"]
            if (sourceDir is not None):
                if (not os.path.isabs(sourceDir)):
                    sourceDir = os.path.join(dir, sourceDir)

            # If there's a sourceDir, then we ignore any patterns. We use the
            # remote corpus, but we need to store a local pointer (in case
            # someone else points to IT), so we
            # can't simply use the remote corpus directly.

            # If there are patterns, get them.
            filePats = None
            if corpus.children["pattern"] is not None:
                if sourceDir is not None:
                    print >> flushedStdout, "Warning: ignoring patterns for corpus '%s' with source_corpus_dir" % cName
                else:
                    filePats = [a.text for a in corpus.children["pattern"]]

            corpora.append(corpusClass(cName, filePats = filePats,
                                       prefix = corpusPrefix,
                                       partitions = corpusSplits,
                                       partitionIsFixed = partitionIsFixed,
                                       prepOptions = prepOptions,
                                       maxCorpusSize = maxSize,
                                       truncateFirst = truncateFirst,
                                       sourceCorpusDir = sourceDir))
            if cDir:
                corpusDirs[cName] = cDir

    # Workspace corpora next.
    
    for corpusSet in expDesc.children["workspace_corpora"]:
        cDir = corpusSet.attrs["dir"]
        wsCorpora = []

        for corpus in corpusSet.children["workspace_corpus"]:
            # The size and partition info is INSIDE the corpus, rather
            # than outside, because the workspace corpus sets up
            # the context using a workspace, not other shared properties.
            maxSize = None
            truncateFirst = False
            partitionIsFixed = False
            corpusSplits = []
            if corpus.children["size"] is not None:
                bNode = corpus.children["size"]
                if bNode.attrs["max_size"] is not None:
                    maxSize = int(bNode.attrs["max_size"])
                if bNode.attrs["truncate_document_list"] == "yes":
                    truncateFirst = True
            for p in corpus.children["partition"]:
                splitFraction = float(p.attrs["fraction"])
                pName = p.attrs["name"]
                corpusSplits.append((pName, splitFraction))
            if corpusSplits and corpus.children["fixed_partition"]:
                raise ExperimentError, "can't specify both partitions and fixed partitions"
            for p in corpus.children["fixed_partition"]:
                partitionIsFixed = True
                splitSize = p.attrs["size"]
                pName = p.attrs["name"]
                if splitSize == "remainder":
                    splitSize = PreparedCorpus.FIXED_PARTITION_REMAINDER
                else:
                    splitSize = int(splitSize)
                corpusSplits.append((pName, splitSize))
            
            cName = corpus.attrs["name"]

            # Check the duplicate corpus names in the bootstrapper, not here.
            includeUnassigned = None
            if corpus.attrs["include_unassigned"] is not None:
                includeUnassigned = (corpus.attrs["include_unassigned"] != "no")

            wsCorpora.append(WorkspaceCorpus(cName,
                                             documentStatuses = corpus.attrs["document_statuses"],
                                             users = corpus.attrs["users"],
                                             includeUnassigned = includeUnassigned,
                                             basenameSets = corpus.attrs["basename_sets"],
                                             basenamePatterns = corpus.attrs["basename_patterns"],
                                             useWorkspaceRemainder = (corpus.attrs["use_remainder"] == "yes"),
                                             partitions = corpusSplits,
                                             partitionIsFixed = partitionIsFixed,
                                             maxCorpusSize = maxSize,
                                             truncateFirst = truncateFirst))
            if cDir:
                corpusDirs[cName] = cDir

        wsCorpusSets.append(WorkspaceCorpusSet(corpusSet.attrs["workspace_dir"],
                                               documentStatuses = corpusSet.attrs["document_statuses"],
                                               users = corpusSet.attrs["users"],
                                               includeUnassigned = (corpusSet.attrs["include_unassigned"] != "no"),
                                               basenameSets = corpusSet.attrs["basename_sets"],
                                               basenamePatterns = corpusSet.attrs["basename_patterns"],
                                               workspaceCorpora = wsCorpora,
                                               corpusClass = corpusClass))
        
    # Model sets next.

    # I was creating a tag set file here, but I now realize that
    # this is Carafe-specific. And so was using the Carafe training
    # engine itself. 

    for modelSets in expDesc.children["model_sets"]:

        trainingIncrement = None
        truncateToIncrement = False
        engineSettings = {}
        corpusSettings = {}
        configName = None
        buildIterators = []
        corpusIterators = []
        
        mDir = modelSets.attrs["dir"]

        # For the moment, we're going to translate the current XML
        # into the appropriate bootstrap iterator. Later, we'll clean
        # up the XML.

        # These settings have to override the task settings,
        # if there are any.

        if modelSets.children["build_settings"] is not None:
            bNode = modelSets.children["build_settings"]
            modelClassName = bNode.attrs["model_class"]
            configName = bNode.attrs["config_name"]
            if modelClassName and configName:
                raise ExperimentError, "can't specify both model_class and config_name for model build config"
            if modelClassName:
                m = MAT.PluginMgr.FindPluginClass(modelClassName, task.name)
                buildInfo = MAT.Bootstrap.ModelInfo(task, m)
            else:
                # configName can be none, in which case it gets the default.
                buildInfo = task.getModelInfo(configName = configName)
                if buildInfo is None:
                    raise ExperimentError, ("unknown model build config setting %s" % configName)
                m = buildInfo.getModelClass()
            engineSettings = m.enhanceAndExtract(XMLOpArgumentAggregator(bNode.wildcardAttrs))
            for iterator in bNode.children["iterator"]:
                iType = iterator.attrs["type"]
                iArgs = ()
                if iType == "increment":
                    iClass = IncrementIterator
                    iArgs = ("engineSettings",)
                elif iType == "value":
                    iClass = ValueIterator
                    iArgs = ("engineSettings",)
                elif iType == "corpus_size":
                    raise ExperimentError, "corpus_size iterator only permitted in model set corpus settings"
                else:
                    # This will raise an error
                    try:
                        iClass = MAT.PluginMgr.FindPluginClass(iType, task.name)
                    except MAT.PluginMgr.PluginError:
                        raise ExperimentError, ("unknown plugin class '%s' specified in model set build settings iterator" % iType)
                iteratorKw = iClass.enhanceAndExtract(XMLOpArgumentAggregator(iterator.wildcardAttrs))
                # Don't build it yet.
                buildIterators.append((iClass, iArgs, iteratorKw))

        if modelSets.children["corpus_settings"] is not None:
            cNode = modelSets.children["corpus_settings"]
            size = cNode.attrs["size"]
            if size is not None:
                corpusSettings["size"] = int(size)
            for iterator in cNode.children["iterator"]:
                iType = iterator.attrs["type"]
                if iType in ["increment", "value"]:                    
                    raise ExperimentError, "increment and value iterators not permitted in model set corpus settings"
                elif iType == "corpus_size":
                    iClass = CorpusSizeIterator
                else:
                    # This will raise an error
                    try:
                        iClass = MAT.PluginMgr.FindPluginClass(iType, task.name)
                    except MAT.PluginMgr.PluginError:
                        raise ExperimentError, ("unknown plugin class '%s' specified in model set corpus settings iterator" % iType)
                iteratorKw = iClass.enhanceAndExtract(XMLOpArgumentAggregator(iterator.wildcardAttrs))
                # Don't build it yet.
                corpusIterators.append((iClass, (), iteratorKw))

        for modelSet in modelSets.children["model_set"]:
            trainingCorpora = []
            mName = modelSet.attrs["name"]
            # Check the duplicate model set names in the bootstrapper, not here.
            for tCorpus in modelSet.children["training_corpus"]:
                mCorpus = tCorpus.attrs["corpus"]
                mPart = tCorpus.attrs["partition"] # might be None.
                # Check for missing corpus names in the bootstrapper, not here.
                trainingCorpora.append((mCorpus, mPart))
            # At the moment, the only examples of "innermost" iterators I have are
            # the model iterators which depend on the previous model - i.e., buildIterators.
            # So those MUST appear last. In other words, it's not possible to have an
            # innermost corpus iterator if there's a build iterator of any kind.
            iterators = [iClass(*iArgs, **iKw) for (iClass, iArgs, iKw) in corpusIterators] + \
                        [iClass(*iArgs, **iKw) for (iClass, iArgs, iKw) in buildIterators]
            models.append(modelClass(mName, engineSettings = engineSettings,
                                     corpusSettings = corpusSettings,
                                     configName = configName,
                                     iterators = iterators,
                                     trainingCorpora = trainingCorpora))
            if mDir:
                modelDirs[mName] = mDir

    # Done with the model sets. But they're NOT PREPARED YET, just configured for
    # build - they can't be built and then trained until the corpora are
    # actually prepared.

    # Finally, the runs.

    for runDesc in expDesc.children["runs"]:

        rDir = runDesc.attrs["dir"]

        # SAM 8/5/09: Now, because I've cleaned up the MATEngine
        # command line and made it more progressive, --task has to
        # come before any task-specific custom flags (e.g.,
        # step flags). I really ought to revise this so that
        # this slot no longer takes a command line, but calls
        # the engine directly; but for today, I need to move
        # the task to here.

        # The build settings are now wildcard settings.
        # I can't convert them to actual engine arguments until
        # I have the chance to digest some of the params, and
        # I don't want to do that until we call the engine.
        # So we'll set up an option for the engine where
        # we can pass in an aggregator instead of a kv dict.
        # Well, no. It turns out that if I want to think about calling
        # this from code, this really needs to be converted to what the
        # kv pairs ought to look like. So I'm just going to have
        # to create an engine and throw it away.

        prepOptions = None
        runOptions = _engineOptionsToKV(task, runDesc.children["run_settings"].children["args"].wildcardAttrs)
        if runDesc.children["run_settings"].children["prep_args"]:
            prepOptions = _engineOptionsToKV(task, runDesc.children["run_settings"].children["prep_args"].wildcardAttrs)

        scoreOptions = None
        if runDesc.children["run_settings"].children["score_args"]:
            scoreArgs = runDesc.children["run_settings"].children["score_args"]
            if scoreArgs.attrs["gold_only"] == "yes":
                scoreOptions = {"restrictRefToGoldSegments": True}
            if scoreArgs.attrs["similarity_profile"] is not None:
                if not scoreOptions:
                    scoreOptions = {}
                scoreOptions["similarityProfile"] = scoreArgs.attrs["similarity_profile"]
            if scoreArgs.attrs["score_profile"] is not None:
                if not scoreOptions:
                    scoreOptions = {}
                scoreOptions["scoreProfile"] = scoreArgs.attrs["score_profile"]                

        runIterators = []
        for iterator in runDesc.children["run_settings"].children["iterator"]:
            iType = iterator.attrs["type"]
            iArgs = ()
            if iType == "increment":
                iClass = IncrementIterator
                iArgs = ("engineOptions",)
            elif iType == "value":
                iClass = ValueIterator
                iArgs = ("engineOptions",)
            elif iType == "corpus_size":
                raise ExperimentError, "corpus_size iterator only permitted in model set corpus settings"
            else:
                # This will raise an error
                try:
                    iClass = MAT.PluginMgr.FindPluginClass(iType, task.name)
                except MAT.PluginMgr.PluginError:
                    raise ExperimentError, ("unknown plugin class '%s' specified in run settings iterator" % iType)
            iteratorKw = iClass.enhanceAndExtract(XMLOpArgumentAggregator(iterator.wildcardAttrs))
            # Don't build it yet.
            runIterators.append((iClass, iArgs, iteratorKw))
                
        for run in runDesc.children["run"]:

            rName = run.attrs["name"]
            # Check for duplicate run names in the bootstrapper, not here.
            
            rModel = run.attrs["model"]
            runCorpora = []
            for cNode in run.children["test_corpus"]:
                rCorpus = cNode.attrs["corpus"]
                rPart = cNode.attrs["partition"]

                # Check for missing models and corpora in the bootstrapper, not here.
                runCorpora.append((rCorpus, rPart))

            runs.append(runClass(rName, 
                                 model = rModel,
                                 iterators = [iClass(*iArgs, **iKw) for (iClass, iArgs, iKw) in runIterators], 
                                 testCorpora = runCorpora,
                                 engineOptions = runOptions,
                                 scoreOptions = scoreOptions,
                                 enginePrepOptions = prepOptions))
            if rDir:
                runDirs[rName] = rDir
            
    # Done with XML configuration.
    return kw

class ExperimentEngine(MAT.Bootstrap.Bootstrapper):

    def __init__(self, computeConfidence = True, task = None,
                 workspaceCorpusSets = None, corpora = None, **kw):

        if workspaceCorpusSets is not None:
            if corpora is None:
                corpora = []
            for wsCorpusSet in workspaceCorpusSets:
                corpora += wsCorpusSet.convertToPreparedCorpora(task.name)
        
        MAT.Bootstrap.Bootstrapper.__init__(self, flushedStdout = flushedStdout,
                                            task = task, corpora = corpora, **kw)
        self.computeConfidence = computeConfidence

    # rescoreRuns should only be disabled for debugging purposes,
    # since the completed runs which aren't rescored won't be accumulated.
    
    def run(self, force = False, interleave = True, markDone = False,
            format = None, rescoreRuns = True):

        if format is None:
            format = MAT.Score.ScoreFormat()
        self.scoreFormat = format

        self.force = force
        self.markDone = markDone
        self.rescoreRuns = rescoreRuns

        # Set up the cumulative tagger. We want to be able to
        # create the scores for each run and then discard them, because the
        # confidence computation takes up a gigantic amount of memory.
        
        cumulativeTagScorer = self.task.augmentTagSummaryScoreTable(ExperimentSummaryResultTable(format = format, computeConfidenceData = self.computeConfidence)).extractGlobalSummary()
        cumulativeTagScorer.addColumn(LiteralScoreColumn("run family",
                                                         colKey = "run_family"))
        cumulativeTagScorer.addColumn(LiteralScoreColumn("run"), after = "run family")
        cumulativeTagScorer.addColumn(LiteralScoreColumn("model family",
                                                         colKey = "model_family"),
                                      after = "run")
        cumulativeTagScorer.addColumn(LiteralScoreColumn("model"), after = "model family")
        cumulativeTagScorer.addColumn(LiteralScoreColumn("train corpora", 
                                                         colKey = "train_corpora"),
                                      after = "model")
        cumulativeTagScorer.addColumn(LiteralScoreColumn("test corpora", 
                                                         colKey = "test_corpora"),
                                      after = "train corpora")
        cumulativeTokenScorer = self.task.augmentTokenSummaryScoreTable(ExperimentSummaryResultTable(forTokens = True, format = format, computeConfidenceData = self.computeConfidence)).extractGlobalSummary()
        cumulativeTokenScorer.addColumn(LiteralScoreColumn("run family",
                                                           colKey = "run_family"))
        cumulativeTokenScorer.addColumn(LiteralScoreColumn("run"), after = "run family")
        cumulativeTokenScorer.addColumn(LiteralScoreColumn("model family",
                                                           colKey = "model_family"),
                                        after = "run")
        cumulativeTokenScorer.addColumn(LiteralScoreColumn("model"), after = "model family")
        cumulativeTokenScorer.addColumn(LiteralScoreColumn("train corpora", 
                                                           colKey = "train_corpora"),
                                        after = "model")
        cumulativeTokenScorer.addColumn(LiteralScoreColumn("test corpora", 
                                                           colKey = "test_corpora"),
                                        after = "train corpora")

        self.cumulativeTagScorer = cumulativeTagScorer
        self.cumulativeTokenScorer = cumulativeTokenScorer

        # We can't do interleaved scoring runs if some of the models are
        # already done. So I need to check first.

        if markDone:
            interleave = False
        else:
            # The problem is that with the new bootstrapper, the models
            # are templates, and the actual instances aren't produced until
            # the models are built. So we need to use the prefixes and
            # do a glob.
            import glob
            for m in self.modelSetList:
                mDirPrefix = self.getModelDirPrefix(m)
                for mDir in glob.glob(mDirPrefix + "*"):
                    if _isDone(mDir):
                        interleave = False
                        break
                if interleave is False:
                    break

        MAT.Bootstrap.Bootstrapper.run(self, interleave = interleave)

    def finish(self, origT):

            # Collecting the cumulative results at the end simplifies a
            # couple things, among them saving cumulative information
            # if the user aborts in the middle of a number of model
            # iterations in interleaved mode. It also keeps the
            # iterations for each run together in the cumulative scorer.

            # AND, make sure the incremental scores are saved.

            if self.runList:
                print >> flushedStdout, "Saving cumulative results..."

                self.cumulativeTagScorer.writeCSVByFormat(self.dir, "allbytag")
                self.cumulativeTokenScorer.writeCSVByFormat(self.dir, "allbytoken")

            newT = time.time()

            print >> flushedStdout, "Experiment ended at", time.ctime(newT)
            print >> flushedStdout, "Experiment took %.2f seconds." % (newT - origT,)

    def _formatPartitions(self, pPairs):

        def pName(partition):
            if partition is None:
                return "(all)"
            else:
                return "(partition %s)" % partition

        return ", ".join(["%s %s" % (c, pName(partition))
                          for (c, partition) in pPairs])

    def _augmentCumulativeScorers(self, r):
        if r and r.csvTagScorer:
            # The problem is that we don't know what corpus each document in the training
            # and test runs came from. We're not tracking that. But by the same token,
            # here we're just collecting the global summaries.
            trainingCorpora = self._formatPartitions(r.model.template.trainingCorpora)
            testCorpora = self._formatPartitions(r.template.testCorpora)
            self.cumulativeTagScorer.importRows(r.csvTagScorer.extractGlobalSummary(),
                                                run_family = r.runName,
                                                run = r.runSubdir,
                                                model_family = r.model.modelName,
                                                model = r.model.modelSubdir,
                                                train_corpora = trainingCorpora,
                                                test_corpora = testCorpora)
            self.cumulativeTokenScorer.importRows(r.csvTokenScorer.extractGlobalSummary(),
                                                  run_family = r.runName,
                                                  run = r.runSubdir,
                                                  model_family = r.model.modelName,
                                                  model = r.model.modelSubdir,
                                                  train_corpora = trainingCorpora,
                                                  test_corpora = testCorpora)
