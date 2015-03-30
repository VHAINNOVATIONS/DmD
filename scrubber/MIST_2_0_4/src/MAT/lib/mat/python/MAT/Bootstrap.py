# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This file contains all the basic pieces to do bootstrapping:
# build a corpus, build a model, run a test. The experiment engine
# is an extension of this now.

import sys, os, shutil, random, glob, time
# I don't think this is necessary, but it doesn't hurt.
random.seed()

# We actually need to create a better abstraction of document
# sets - we may end up using them in multiple places, but the first
# use is going to be for the experiment engine and cross-validation.

# These document sets should support a bunch of things:
# - randomly split into multiple sets
# - consolidate to a single directory, with disambiguated file names
# - instantiate from a number of different types of sources, such as
# a list of files, a file which contains a list of files, or pattern + prefix

class DocumentSetError(Exception):
    pass

#
# The document set object.
#

# filePats: a list of glob expressions which picks out
# a candidate set of training docs.
# fileFile: a file which contains filenames, one per line.
# use either this or filePats/randomSubset.

# Two ways of providing a list of files: either filePats and a
# size, or a file of filenames, or a list of the files directly.

class DocumentSet:
    
    def __init__(self, corpusName, partitionFile = None, filePats = None,
                 fileFile = None, fileList = None,
                 prefix = None,
                 partitions = None, partitionIsFixed = False,
                 flushedStdout = sys.stdout):

        self.corpusName = corpusName
        # Can't use sets, because I really need the order to be maintained.
        self._initVars()
        if partitionFile is not None:
            self.loadPartition(partitionFile)
        else:
            self._populate(filePats, fileFile, fileList, prefix, flushedStdout)
            self._partition(partitions, partitionIsFixed)

    def _initVars(self):
        
        self.files = []
        self._filesSeen = {}
        self.partitionDict = None
        self.deconflictions = None

    def _populate(self, filePats, fileFile, fileList, prefix, flushedStdout):

        # In the general case, who cares how many of these you use.

        if (fileList is None) and (filePats is None) and (fileFile is None):
            raise DocumentSetError, "neither fileFile nor filePats nor fileList is specified"
        if prefix is not None:
            if not os.path.isabs(prefix):
                raise DocumentSetError, "prefix must be absolute"
        if fileList:
            for f in fileList:
                if os.path.isabs(f):
                    self._addFile(f)
                elif prefix is None:
                    raise DocumentSetError, "fileList contains relative pathnames, but there's no prefix"
                else:
                    self._addFile(os.path.join(prefix, f))
        elif fileFile:
            fp = open(fileFile, "r")
            for f in [line.strip() for line in fp.readlines()]:
                if os.path.isabs(f):
                    self._addFile(f)
                else:
                    # The justification for this is that a file which contains
                    # pathnames will have been archived by the save() method.
                    raise DocumentSetError, "fileFile must contain absolute pathnames"
            fp.close()
        else:
            files = []
            if type(filePats) is type(""):
                filePats = [filePats]
            # Remove duplicates
            for p in filePats:
                i = 0
                if not os.path.isabs(p):
                    if prefix is None:
                        raise DocumentSetError, "filePats contains relative pathnames, but there's no prefix"
                    p = os.path.join(prefix, p)
                for f in glob.glob(p):
                    if not os.path.isfile(f):
                        raise DocumentSetError, ("file %s specified by pattern %s is not a regular file" % (p, f))
                    self._addFile(f)
                    i += 1
                if i == 0:
                    print >> flushedStdout, "Warning: pattern %s did not pick out any files" % p

        if not self.files:
            raise DocumentSetError, "document set is empty"

    def _addFile(self, f):
        if not self._filesSeen.has_key(f):
            self.files.append(f)
            self._filesSeen[f] = True

    # What does a partition look like? It's a list of pairs, where
    # the first element is the name of the partition, and the second is
    # the share. The share is a number. All the numbers are normalized to
    # a share of 1, and then we randomize the list of files, and
    # select slice of the randomized list.

    # If partitionIsFixed is true, the number is an actual number of
    # files, rather than a share. -1 means "everything else".

    FIXED_PARTITION_REMAINDER = -1
    
    def _partition(self, partitions, partitionIsFixed):        
        # Save the partition list in NORMALIZED form.
        if partitions is not None:
            self.partitionDict = {}
            files = self.files[:]
            random.shuffle(files)
            trueP = []
            if partitionIsFixed:
                remainder = None
                start = 0
                for pName, total in partitions:
                    if total == self.FIXED_PARTITION_REMAINDER:
                        if remainder is not None:
                            raise DocumentSetError, ("multiple remainder pairs specified: %s, %s" % (pName, remainder))
                        remainder = pName
                    elif start + total > len(files):
                        raise DocumentSetError, ("number of requested files for fixed partition '%s' exceed number of available files" % pName)
                    else:
                        trueP.append([pName, start, start + total])
                        start += total
                # Not all the files might be used.
                if remainder is not None:
                    trueP.append([pName, start, len(files)])
            else:
                total = float(sum([x[1] for x in partitions]))
                # Now, we convert the numbers in the partitions
                # into shares of the size of the number of files.
                # The last one has to grab the remainder. I don't
                # want to make this too complicated.
                i = 0.0
                for pName, share in partitions:
                    j = i + (len(files) * (share / total))
                    trueP.append([pName, int(round(i)), int(round(j))])
                    i = j
                trueP[-1][-1] = len(files)
            for pName, start, end in trueP:
                self.partitionDict[pName] = files[start:end]
        else:
            # Make sure to randomize the order.
            self.files = self.files[:]
            random.shuffle(self.files)

    def getFiles(self, partition = None):
        if partition is not None:
            if self.partitionDict is None:
                raise KeyError, partition
            else:
                return self.partitionDict[partition]
        else:
            return self.files

    def savePaths(self, outPath):
        fp = open(outPath, "w")
        for f in self.files:
            fp.write(f + "\n")
        fp.close()

    def savePartition(self, outPath):
        fp = open(outPath, "w")
        if self.partitionDict is not None:
            for name, files in self.partitionDict.items():
                for f in files:
                    fp.write("%s,%s\n" % (name, f))
        fp.close()

    def loadPartition(self, path):
        self.partitionDict = {}
        fp = open(path, "r")
        for line in fp.readlines():
            [name, f] = line.strip().split(",", 1)
            try:
                self.partitionDict[name].append(f)
            except KeyError:
                self.partitionDict[name] = [f]
            self._addFile(f)
        fp.close()

    def _deconflict(self):
        if self.deconflictions is not None:
            return
        self.deconflictions = {}
        duplicateBasenameDict = {}
        basenamesToMap = []
        for f in self.files:
            # This will be overwritten in some cases later when we figure
            # out what needs to be deconflicted.
            b = os.path.basename(f)
            self.deconflictions[f] = b
            if duplicateBasenameDict.has_key(b):
                if len(duplicateBasenameDict[b]) == 1:
                    basenamesToMap.append(b)
                duplicateBasenameDict[b].append(f)
            else:
                duplicateBasenameDict[b] = [f]
        if basenamesToMap:
            for b in basenamesToMap:
                # There will be no duplicates in the list, because
                # document sets have duplicates removed.
                dirPrefix = os.path.dirname(os.path.commonprefix(duplicateBasenameDict[b]))
                for f in duplicateBasenameDict[b]:
                    suff = f[len(dirPrefix):]
                    # The new filename is this suffix with all the dir
                    # components replaced.
                    stack = []
                    split = os.path.split(suff)
                    while split[0] != suff:
                        stack[0:0] = [split[1]]
                        suff = split[0]
                        split = os.path.split(suff)
                    newBasename = "_".join(stack)
                    # And replace it in the list of files in the document set.
                    self.deconflictions[f] = newBasename

    # Consolidate a set of documents into a directory.
    # Use deconfliction.
    
    def consolidate(self, dir, fn):
        self._deconflict()
        for f in self.files:
            fn(f, os.path.join(dir, self.deconflictions[f]))

    # In the default case, these two are no-ops. They're required for the
    # interaction with a potential parent bootstrapping or experiment engine.
    
    def setContext(self, engine):
        pass

    def prepare(self, *args, **kw):
        pass

#
# And now, something to wrap around the ModelBuilder to be used in
# bootstrapping systems. This is simplified from the original version in
# CarafeTrain.py, which does all sorts of frightening cacheing of settings, etc.
#

class TrainingRunError(Exception):
    pass

# If we're going to be able to specify a model builder
# directly in the bootstrapper, we're going to have to override some of the default
# model builder creation.

import MAT.PluginMgr

class ModelInfo(MAT.PluginMgr.ModelInfo):

    def __init__(self, task, mBClass):
        self.task = task
        self.modelClass = mBClass
        self.configName = ""
        self.modelBuildSettings = {}

class TrainingRunInstance:

    def __init__(self, engine, template, modelSubdir, trainingCorpus,
                 engineSettings = None, corpusSettings = None, builderClass = None):
        self.modelName = template.modelName
        self.modelSubdir = modelSubdir
        self.configName = template.configName
        self.builderClass = builderClass
        # I think these will be actual training corpora.
        self.trainingSet = trainingCorpus
        self.engineSettings = engineSettings
        self.corpusSettings = corpusSettings
        self.flushedStdout = template.flushedStdout
        self.template = template

        self.setContext(engine)        
        
    # In this case, there really does need to be a context set,
    # and the engine needs to have a task, etc.

    def setContext(self, engine):

        self._updateFromEngine(engine)

        if not os.path.exists(self.modelDir):
            print >> self.flushedStdout, "Creating model directory", self.modelDir, "..."
            os.makedirs(self.modelDir)

        self._configureBuilder()
        
    # The trainer requires all the files in a single directory, so we
    # take the files and put them somewhere random.
    # The format of the model output dir is a file containing
    # the file list at the toplevel, and a subdir for each increment.
    # I'm going to use the modelOutputDir also as the temp location,
    # because that's the safest thing to do - that location will have
    # to be appropriately protected for sensitive data.
    
    def train(self, interleave = False, collectCorpusStatistics = False):

        import MAT.ExecutionContext
        with MAT.ExecutionContext.Tmpdir(specifiedParent = self.modelDir) as tmpDir:
            mName = self.modelName

            print >> self.flushedStdout, "Building model ..."
            t = time.time()
            self.builder.run(os.path.join(self.modelDir, "model"),
                             self.trainingSet.getFiles(), 
                             tmpDir = tmpDir,
                             collectCorpusStatistics = collectCorpusStatistics,
                             oStream = self.flushedStdout)
            print >> self.flushedStdout, "Build completed in %.2f seconds." % (time.time() - t,)
            if interleave:
                for rTemplate in self.engine.runList:
                    if rTemplate.modelName == mName:
                        for r in rTemplate.yieldInstances(self.engine):
                            r.setContext(self.engine, self)
                            r.prepareTest()
                            rName = r.runName
                            print >> self.flushedStdout, "\n### Performing run", rName, "in directory", r.runSubdir
                            r.test()
                            print >> self.flushedStdout, "### Done."
                            r.finishTest()

    #
    # Internal methods which can be consumed.
    #
    
    def _updateFromEngine(self, engine):

        self.engine = engine
        self.modelDir = engine.getModelDir(self)

    def _configureBuilder(self):
        task = self.engine.task
        # Use a local class.
        if self.builderClass:
            mBClass = self.builderClass
            buildInfo = ModelInfo(task, mBClass)
        else:
            # Next, we add the properties.
            buildInfo = task.getModelInfo(configName = self.configName)
            mBClass = buildInfo.getModelClass()
        if mBClass is None:
            raise TrainingRunError, ("model %s has no engine for the task" % self.modelName)
        builderSettings = self.engineSettings or {}
        self.builder = buildInfo.buildModelBuilder(**builderSettings)

# The challenge here is keeping enough information about the
# corpora to be able to ensure that (a) corpus increments are guaranteed to
# be successively larger slices of the SAME ORDER, and (b) corpus balances
# can be preserved. And then there's the issue about restart - but that's
# only in CarafeTrain, and I think I have to address it there.
# So I think I'll collect them as pairs of dsetname/partition and file,
# THEN shuffle them. Then that will be what I'll use when I select from it.

class TrainingRun:

    def __init__(self, mName, trainingCorpora = None,
                 engineSettings = None, corpusSettings = None,
                 configName = None,
                 builderClass = None,
                 iterators = None,
                 flushedStdout = sys.stdout,
                 instanceClass = TrainingRunInstance):

        self.modelName = mName        
        self.iterators = iterators
        if iterators:
            for iterator in iterators[:-1]:
                if iterator.mustBeInnermost:
                    raise TrainingRunError, ("Iterator %s must be innermost, but is not last" % iterator)
        self.configName = configName
        self.builderClass = builderClass
        self.trainingCorpora = trainingCorpora
        self.engineSettings = engineSettings
        self.corpusSettings = corpusSettings
        self.flushedStdout = flushedStdout
        self.instanceClass = instanceClass
        # We collect the instances. If the run
        # asks for them and you can use the cache,
        # then use the cache.
        self._cached = False
        self.allInstances = []

    # Note that because _createTrainingCorpus is called repeatedly,
    # if there's iteration, on the output of _collectTrainingSet, there's
    # no need to guarantee an order in _collectTrainingSet.

    def _collectTrainingSet(self, engine):
        elts = []
        for dSetName, partition in self.trainingCorpora:
            elts += [((dSetName, partition), f) for f in engine.getCorpus(dSetName).getFiles(partition)]
        random.shuffle(elts)
        return elts

    def _createTrainingCorpus(self, tSetElements, size = None):
        # VERY IMPORTANT to trim BEFORE DocumentSet is created,
        # since DocumentSet does a random shuffle.
        if size is not None:
            tSetElements = tSetElements[:size]
        tFiles = [p[1] for p in tSetElements]
        return DocumentSet(None, fileList = tFiles, flushedStdout = self.flushedStdout)

    def _satisfyIterators(self, engine, iterators, subdirName, **kw):
        if not iterators:
            # We've reached the end.
            yield self._createInstance(engine, subdirName, **kw)
        else:
            for newSubdirName, newKw in iterators[0](subdirName, **kw):
                for inst in self._satisfyIterators(engine, iterators[1:], newSubdirName, **newKw):
                    yield inst

    # both tSetElements and engineSettings are keywords. The former is a list
    # of pairs ((dSetName, partition), f), and the second is guaranteed to have a dictionary value.
    
    def _createInstance(self, engine, modelSubdir, tSetElements = None, engineSettings = None,
                        corpusSettings = None, builderClass = None,
                        # Soak up the extra context that was passed in to the iterators
                        **kw):
        return self.instanceClass(engine, self, modelSubdir,
                                  self._createTrainingCorpus(tSetElements, **corpusSettings),
                                  engineSettings = engineSettings, builderClass = builderClass)
    #
    # The sole public method
    #

    # We collect the objects and record the cache as done, so if we ever
    # loop over the runs instead of the models, it'll work fine.
    
    def yieldInstances(self, engine, **kw):
        if self._cached:
            for i in self.allInstances:
                yield i
        else:
            tSetElements = self._collectTrainingSet(engine)
            for mInst in self._satisfyIterators(engine, self.iterators or [], self.modelName,
                                                tSetElements = tSetElements,
                                                engineSettings = self.engineSettings or {},
                                                corpusSettings = self.corpusSettings or {},
                                                builderClass = self.builderClass,
                                                **kw):
                self.allInstances.append(mInst)
                yield mInst
            self._cached = True

#
# Next, the TestRun object.
#

import MAT.DocumentIO, MAT.ToolChain
_jsonIO = MAT.DocumentIO.getDocumentIO('mat-json')
_rawUTF8 = MAT.DocumentIO.getDocumentIO('raw', encoding = 'utf-8')

class TestRunError(Exception):
    pass

class TestRunInstance:

    def __init__(self, engine, template, runSubdir, engineOptions = None):
        self.runName = template.runName
        self.runSubdir = runSubdir
        self.engineOptions = engineOptions
        self.enginePrepOptions = template.enginePrepOptions
        self.flushedStdout = template.flushedStdout
        self.template = template
        self.testSet = template.testSet
        
    # I was hoping that this could be called from __init__, but
    # it has to wait until the model is created, which is sometimes inside
    # the run creation loop.
    
    def setContext(self, engine, mInstance):
        self.model = mInstance
        self.engine = engine
        self.runDir = os.path.join(self.engine.getRunDir(self), self.model.modelSubdir)
    
    def prepareTest(self, **kw):
        
        print >> self.flushedStdout, "\n### Preparing run", self.runName

        runInputTestDir = os.path.join(self.runDir, "run_input")

        if os.path.isdir(runInputTestDir):
            shutil.rmtree(runInputTestDir)

        self._prepareTestCorpus()

    def test(self):

        modelDir = os.path.join(self.model.modelDir)
        modelFile = os.path.join(modelDir, "model")
        hypDir = os.path.join(self.runDir, "hyp")
        os.makedirs(hypDir)

        self._runTest(modelFile, hypDir, "Creating hypothesis...")

    def finishTest(self):
        pass

    #
    # Internal functions available for reuse.
    #
    
    def _runTest(self, modelFile, hypDir, msg):
        
        matEngineOptions = self.engineOptions
        runInputTestDir = os.path.join(self.runDir, "run_input")
        task = self.engine.task

        for key in ["tagger_local", "tagger_model", "input_file_type", "output_encoding",
                    "output_file_type", "input_encoding", "input_dir", "input_file",
                    "output_dir", "output_file", "output_fsuff", "input_file_re"]:
            if matEngineOptions.has_key(key):
                raise TestRunError, ("%s not permitted in run settings" % key)
        
        # Now, pull over the input file information from the prep options,
        # if applicable.
        
        inputEncoding = "utf-8"
        inputFileType = "raw"
        if self.enginePrepOptions is not None:
            if self.enginePrepOptions.has_key("output_file_type"):
                inputFileType = self.enginePrepOptions["output_file_type"]
            if self.enginePrepOptions.has_key("output_encoding"):
                inputEncoding = self.enginePrepOptions["output_encoding"]

        print >> self.flushedStdout, msg

        print >> self.flushedStdout, "Invoking MATEngine:", " ".join(['%s: "%s"' % pair for pair in matEngineOptions.items()])
        # The workflow had better be there. This will raise an error if it
        # isn't, most likely.
        e = MAT.ToolChain.MATEngine(taskObj = task, workflow = matEngineOptions.get("workflow"))
        e.Run(tagger_local = True, tagger_model = modelFile,
              input_file_type = inputFileType, input_encoding = inputEncoding,
              output_file_type = "mat-json", input_dir = runInputTestDir,
              output_dir = hypDir, output_fsuff = ".tag.json", **matEngineOptions)

    def _prepareTestCorpus(self):

        expEngine = self.engine
        task = expEngine.task
        testSet = self.testSet

        # Create preprocessed versions of the test files.
        # If there's no enginePrepOptions, just make them raw.
        
        print >> self.flushedStdout, "Preparing test files..."
        runInputTestDir = os.path.join(self.runDir, "run_input")
        os.makedirs(runInputTestDir)

        if self.enginePrepOptions is None:
            # Let's use UTF-8, since we know that it works.
            testSet.consolidate(runInputTestDir,
                                lambda inf, outf: _rawUTF8.writeToTarget(_jsonIO.readFromSource(inf, taskSeed = task), outf + ".prepped"))
        else:
            testSet.consolidate(runInputTestDir,
                                lambda inf, outf: shutil.copy(inf, outf + ".prepinput"))
            # Invoke the MATEngine. output_file_type is required. That's pretty much it.            
            for key in ["tagger_local", "tagger_model", "input_file_type",
                        "input_encoding", "input_dir", "input_file",
                        "output_dir", "output_file", "output_fsuff", "input_file_re"]:
                if self.enginePrepOptions.has_key(key):
                    raise TestRunError, ("%s not permitted in run prep settings" % key)
            if not self.enginePrepOptions.has_key("output_file_type"):
                raise TestRunError, "output_file_type attribute required in run prep settings"
            if self.enginePrepOptions["output_file_type"] not in ["raw", "mat-json"]:
                raise TestRunError, "output_file_type attribute in run prep settings must be either raw or mat-json"
            
            print >> self.flushedStdout, "Invoking MATEngine:", " ".join(['%s: "%s"' % pair for pair in self.enginePrepOptions.items()])
            # The workflow had better be there. This will raise an error if it
            # isn't, most likely.
            e = MAT.ToolChain.MATEngine(taskObj = task, workflow = self.enginePrepOptions.get("workflow"))
            # Use the directory temporarily.
            e.Run(input_file_type = "mat-json",
                  input_dir = runInputTestDir,
                  output_dir = runInputTestDir,
                  input_file_re = "^.*\.prepinput$",
                  output_fsuff = ".postprocessed", **self.enginePrepOptions)
            # Done. Remove all files which end with .prepinput, strip
            # .postprocessed.
            for b in testSet.deconflictions.values():
                os.remove(os.path.join(runInputTestDir, b + ".prepinput"))
                os.rename(os.path.join(runInputTestDir, b + ".prepinput.postprocessed"),
                          os.path.join(runInputTestDir, b + ".prepped"))

# Iterators can't apply to the test set. So that should be prepared
# when the test run is asked to yield instances.

class TestRun:

    def __init__(self, rName, model = None, testCorpora = None,
                 engineOptions = None,
                 iterators = None,
                 enginePrepOptions = None, flushedStdout = sys.stdout,
                 instanceClass = TestRunInstance):
        self.runName = rName
        self.modelName = model
        self.testCorpora = testCorpora
        self.engineOptions = engineOptions
        self.enginePrepOptions = enginePrepOptions
        self.testSet = None
        self.flushedStdout = flushedStdout
        self.iterators = iterators
        if iterators:
            for iterator in iterators[:-1]:
                if iterator.mustBeInnermost:
                    raise TrainingRunError, ("Iterator %s must be innermost, but is not last" % iterator)
        self.allInstances = []
        self.instanceClass = instanceClass

    def _satisfyIterators(self, engine, iterators, subdirName, **kw):
        if not iterators:
            # We've reached the end.
            yield self._createInstance(engine, subdirName, **kw)
        else:
            for newSubdirName, newKw in iterators[0](subdirName, **kw):
                for inst in self._satisfyIterators(engine, iterators[1:], newSubdirName, **newKw):
                    yield inst

    # engineOptions is a keyword, guaranteed to have a dictionary value.
    
    def _createInstance(self, engine, runSubdir, engineOptions = None,
                        # Soak up the extra context that was passed in to the iterators
                        **kw):
        return self.instanceClass(engine, self, runSubdir, 
                                  engineOptions = engineOptions)

    def _configureTestCorpus(self, engine):

        tFiles = []
        for corpusName, partition in self.testCorpora:
            corpus = engine.getCorpus(corpusName)
            tFiles += corpus.getFiles(partition = partition)
        self.testSet = DocumentSet(None, fileList = tFiles, flushedStdout = self.flushedStdout)

    #
    # The sole public method
    #
    
    def yieldInstances(self, engine, **kw):
        # We should prepare the test set here, but I'm not
        # sure where to put it yet. Let's just suppress that until the
        # instance is created. That will be a bunch of extra work
        # in the iterative cases, but no more than what's currently
        # being done. I don't think we should allow the option
        # of iterating on the test prep. For now, we just prepare the
        # test set.
        self._configureTestCorpus(engine)
        for rInst in self._satisfyIterators(engine, self.iterators or [], self.runName,
                                            engineOptions = self.engineOptions,
                                            **kw):
            self.allInstances.append(rInst)
            yield rInst

#
# Some basic iterators
#

# Each iterator has a __call__() method, which should be a
# generator.

import re

class BootstrapIterator:

    mustBeInnermost = False
    
    def _newDirName(self, curDirName, attr, val):
        return "%s_%s_%s" % (curDirName, re.sub("\W", "_", str(attr)),
                             re.sub("\W", "_", str(val)))        

class IncrementIterator(BootstrapIterator):

    def __init__(self, optionKey, attribute, startVal, endVal, increment, forceLast = False):
        self.optionKey = optionKey
        self.attribute = attribute
        self.startVal = startVal
        self.endVal = endVal
        self.increment = increment
        self.forceLast = forceLast

    def __call__(self, curSubdirName, **kw):
        v = self.startVal
        if not kw.has_key(self.optionKey):
            return
        else:
            while v <= self.endVal:
                # Copy the arguments, and the value of the option key.
                newKw = kw.copy()
                newKw[self.optionKey] = newKw[self.optionKey].copy()
                newKw[self.optionKey][self.attribute] = v
                yield self._newDirName(curSubdirName, self.attribute, v), newKw
                if self.forceLast and (v < self.endVal) and ((v + self.increment) > self.endVal):
                    v = self.endVal
                else:
                    v += self.increment

# ONLY used with the corpus.

class CorpusSizeIterator(IncrementIterator):

    def __init__(self, increment, startVal = None, endVal = None, forceLast = False):

        IncrementIterator.__init__(self, "corpusSettings", "size", startVal or increment, endVal, increment, forceLast = forceLast)

    def __call__(self, curSubdirName, tSetElements = None, **kw):
        if self.endVal is None:
            self.endVal = len(tSetElements)
        for d, newKw in IncrementIterator.__call__(self, curSubdirName, tSetElements = tSetElements, **kw):
            yield d, newKw        

class ValueIterator(BootstrapIterator):

    def __init__(self, optionKey, attribute, valueList):
        self.optionKey = optionKey
        self.attribute = attribute
        self.valueList = valueList

    def __call__(self, curSubdirName, **kw):
        if not kw.has_key(self.optionKey):
            return
        else:
            for v in self.valueList:
                # Copy the arguments, and the value of the option key.
                newKw = kw.copy()
                newKw[self.optionKey] = newKw[self.optionKey].copy()
                newKw[self.optionKey][self.attribute] = v
                yield self._newDirName(curSubdirName, self.attribute, v), newKw

#
# And finally,  the bootstrapper itself.
#

class BootstrapError(Exception):
    pass

class Bootstrapper:

    def __init__(self, dir = None, task = None,
                 corpora = None, models = None, runs = None,
                 corpusDirs = None, modelDirs = None, runDirs = None,
                 flushedStdout = sys.stdout):

        self.flushedStdout = flushedStdout
        self.dir = dir
        if dir is None:
            raise BootstrapError, "no dir specified"
        self.task = task
        if task is None:
            raise BootstrapError, "no task specified"
        # A table of the mapping from names to
        # corpora.
        self.corporaTable = {}
        # A list of corpora.
        self.corporaList = []
        # A table of the current mapping from names
        # to model set templates.
        self.modelSetTable = {}
        # A list of model set templates.
        self.modelSetList = []
        # A table of the current mapping from names
        # to training run templates.
        self.runTable = {}
        # A list of run templates.
        self.runList = []

        self.corpusDirs = corpusDirs or {}
        self.modelDirs = modelDirs or {}
        self.runDirs = runDirs or {}

        # Postpone setting the context until the run() method.
        
        if corpora is not None:
            for corpus in corpora:
                cName = corpus.corpusName
                if self.corporaTable.has_key(cName):
                    raise BootstrapError, ("duplicate corpus name '%s'" % cName)
                self.corporaTable[cName] = corpus
                self.corporaList.append(corpus)

        if models is not None:
            for model in models:
                mName = model.modelName
                if self.modelSetTable.has_key(mName):
                    raise BootstrapError, ("duplicate model set name '%s'" % mName)
                for cName, mPart in model.trainingCorpora:
                    if not self.corporaTable.has_key(cName):
                        raise BootstrapError, ("model '%s' requires unknown corpus '%s'" % (mName, cName))
                self.modelSetTable[mName] = model
                self.modelSetList.append(model)

        if runs is not None:
            for run in runs:
                rName = run.runName
                if self.runTable.has_key(rName):
                    raise BootstrapError, ("duplicate run name '%s'" % rName)
                if not self.modelSetTable.has_key(run.modelName):
                    raise BootstrapError, ("run %s requires unknown model set %s" % (rName, run.modelName))
                for rCorpus, rPart in run.testCorpora:
                    if not self.corporaTable.has_key(rCorpus):
                        raise BootstrapError, ("run %s requires unknown corpus %s" % (rName, rCorpus))
                self.runTable[rName] = run
                self.runList.append(run)

    # c is a DocumentSet.
    
    def getCorpusDir(self, c):
        cName = c.corpusName
        cSubdir = cName
        # Impose directory defaults. If dir is absent, use
        # "corpora". If dir isn't absolute, prepend the experiment engine dir.
        try:
            cDir = self.corpusDirs[cName]
        except KeyError:
            cDir = "corpora"
        if not os.path.isabs(cDir):
            cDir = os.path.join(self.dir, cDir)
        return os.path.join(cDir, cSubdir)

    # m is a TrainingRunInstance.
    
    def getModelDir(self, m):
        mName = m.modelName
        mSubdir = m.modelSubdir
        try:
            mDir = self.modelDirs[mName]
        except KeyError:
            mDir = "model_sets"
        if not os.path.isabs(mDir):
            mDir = os.path.join(self.dir, mDir)
        return os.path.join(mDir, mSubdir)

    # mTemplate is a TrainingRun.
    
    def getModelDirPrefix(self, mTemplate):
        mName = mTemplate.modelName
        try:
            mDir = self.modelDirs[mName]
        except KeyError:
            mDir = "model_sets"
        if not os.path.isabs(mDir):
            mDir = os.path.join(self.dir, mDir)
        return os.path.join(mDir, mName)

    # r is a TestRunInstance.
    
    def getRunDir(self, r):
        rName = r.runName
        rSubdir = r.runSubdir
        try:
            rDir = self.runDirs[rName]
        except KeyError:
            rDir = "runs"
        if not os.path.isabs(rDir):
            rDir = os.path.join(self.dir, rDir)
        return os.path.join(rDir, rSubdir)

    # rTemplate is a TestRun.
    
    def getRunDirPrefix(self, rTemplate):
        rName = rTemplate.runName
        try:
            rDir = self.runDirs[rName]
        except KeyError:
            rDir = "runs"
        if not os.path.isabs(rDir):
            rDir = os.path.join(self.dir, rDir)
        return os.path.join(rDir, rName)
    
    def getCorpus(self, cName):
        return self.corporaTable[cName]

    def getModel(self, mName):
        return self.modelSetTable[mName]

    # So the new workflow is this. 
    
    def run(self, interleave = True):
        
        # To run it, we need to prepare each corpus, build each model,
        # execute each run.
        
        origT = time.time()
        
        print >> self.flushedStdout, "Run began at", time.ctime(origT)

        hitError = False

        from MAT.ExecutionContext import _DEBUG

        try:
            try:

                # So the idea is that we start with the runs,
                # iterating through the corpora and then models.
                
                # Prepare each corpus.
                for c in self.corporaList:
                    c.setContext(self)
                    cDir = self.getCorpusDir(c)
                    print >> self.flushedStdout, "\n### Preparing corpus", c.corpusName
                    c.prepare()
                    print >> self.flushedStdout, "### Done."

                # We can't do interleaved scoring runs if some of the models are
                # already done. So I need to check first.

                for mTemplate in self.modelSetList:
                    for m in mTemplate.yieldInstances(self):
                        print >> self.flushedStdout, "\n### Building model set", m.modelName, "in directory", m.modelSubdir
                        # If interleave is True, we'll do the runs.
                        m.train(interleave = interleave)
                        print >> self.flushedStdout, "### Done."
                
                if not interleave:
                    # Perform each run.
                    for rTemplate in self.runList:
                        mTemplate = self.getModel(rTemplate.modelName)
                        for r in rTemplate.yieldInstances(self):
                            for m in mTemplate.yieldInstances(self):
                                r.setContext(self, m)
                                r.prepareTest()
                                print >> self.flushedStdout, "\n### Performing run", r.runName, "in directory", r.runSubdir
                                r.test()
                                print >> self.flushedStdout, "### Done."

            except Exception, e:

                if _DEBUG:
                    hitError = True
                raise
                                    
        finally:

            if not (_DEBUG and hitError):

                self.finish(origT)

    def finish(self, origT):
        pass
