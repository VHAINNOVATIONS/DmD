# Copyright (C) 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This file contains utilities which may be used either by
# build_tarball.py, install.py, or any of the dist.py files in
# the individual tasks.

# THIS FILE DOES NOT RELY ON THE MAT PYTHON MODULE.

import subprocess

def shellOutput(scmd):
    fp = subprocess.Popen(scmd, shell=True, stdout=subprocess.PIPE).stdout
    s = fp.read()
    fp.close()
    return s

import os

class MATManifest(dict):

    def __init__(self, bundleRoot):
        self.bundleRoot = bundleRoot
        self.manifestFile = os.path.join(self.bundleRoot, "MANIFEST")
        self.taskEntries = None

    def setTaskEntries(self, taskEntries):
        self.taskEntries = taskEntries

    def getTaskEntries(self):
        return self.taskEntries
        
    def load(self):
        fp = open(self.manifestFile, "r")
        for line in fp.readlines():
            k, v = line.split(" : ", 1)
            if k == "mat_tasks":
                self.taskEntries = v.strip().split()
            else:
                self[k] = v.strip()
        fp.close()

    def save(self):
        fp = open(self.manifestFile, "w")
        for k, v in self.items():
            fp.write(k + " : " + v + "\n")
        if self.taskEntries is not None:
            fp.write("mat_tasks : " + " ".join(self.taskEntries))
        fp.close()

def parseTaskFeatures(features):
    if not features:
        return {}
    fdict = {}
    for fspec in features.split(","):
        fspec = fspec.strip()
        toks = fspec.split("=", 1)
        if len(toks) == 1:
            fdict[fspec] = True
        else:
            fdict[toks[0].strip()] = toks[1].strip()
    return fdict

# We want to be able to save out task-specific config files.

import ConfigParser

def writeTaskSettings(taskDir, d):
    path = os.path.join(taskDir, "MAT_settings.config")
    p = ConfigParser.RawConfigParser()
    p.optionxform = str
    prefix = os.path.basename(taskDir)
    if os.path.exists(path):
        p.read([path])
    else:
        p.add_section(prefix)
    for k, v in d.items():
        p.set(prefix, k, v)
    fp = open(path, "wb")
    p.write(fp)
    fp.close()

def readTaskSettings(taskDir):
    path = os.path.join(taskDir, "MAT_settings.config")
    p = ConfigParser.RawConfigParser()
    p.optionxform = str
    prefix = os.path.basename(taskDir)
    if os.path.exists(path):
        p.read([path])
    return p

# We're going to introduce the possibility of having multiple
# versions, if we have an additional search path.

import re

class VersionExtractor:

    def __init__(self, matchRe, cmdSubstString, groupNames):
        self.matchRe = matchRe
        self.cmdSubstString = cmdSubstString
        self.groupNames = groupNames

    def extractVersion(self, seed):
        o = shellOutput(self.cmdSubstString % seed)
        m = re.search(self.matchRe, o)
        if m is None:
            return None
        else:
            version = []
            for g in self.groupNames:
                if m.group(g) is not None:
                    version.append(int(m.group(g)))
            return version
    
    def atLeastVersion(self, reqTuple, foundTuple, excludeEndpoint = False):
        i = 0
        while (i < len(reqTuple) and i < len(foundTuple)):
            if reqTuple[i] > foundTuple[i]:
                return False
            if reqTuple[i] < foundTuple[i]:
                return True
            i = i + 1
        # All the digits are equal up to the current i.
        # If the reqTuple has more digits than foundTuple,
        # (e.g. 3.79.1 vs. 3.79) we fail.
        if len(reqTuple) > len(foundTuple):
            return False
        elif excludeEndpoint:
            return False
        else:
            return True

    def atMostVersion(self, reqTuple, foundTuple, excludeEndpoint = False):
        return self.atLeastVersion(foundTuple, reqTuple, excludeEndpoint = excludeEndpoint)

#
# Better, more integrated version of the executable chooser.
#

# The candidates are considered first, then the name in the usual path,
# then the name in the extra dirs. If there's a version checker, the
# argument of any acceptability test is the checker and the version, and
# the choice function is the newest acceptable version. Otherwise, the
# argument of the acceptability test is the full pathname, and
# the choice function gets all the paths. If there's no choice function,
# the first acceptable one is chosen. If there's no acceptability
# test, the first element that exists and is a file is returned.

import sys

def chooseExecutable(category, seed = None, execName = None, execExtraDirs = None,
                     execCandidates = None, versionChecker = None,
                     filterFn = None, choiceFn = None,
                     failureString = None, execPrompt = None,
                     promptIntro = None, 
                     execFailureString = None, exitOnFailure = False):

    print "Checking for", category, "..."

    # seed, if present, can be either a name or a full path.
    if seed is not None:
        if os.path.isabs(seed):
            if execCandidates is None:
                execCandidates = [seed]
            else:
                execCandidates[0:0] = [seed]
        elif os.path.dirname(seed):
            print "Seed is neither a full path nor an executable name; ignoring."
        else:
            # It's an executable name. If execName is present, warn and discard.
            if execName is not None:
                print "Using", seed, "instead of execName"
            execName = seed

    if failureString is None:
        failureString = "failed."
    
    allCandidates = []
    versionHash = {}

    # Possible executables may appear in multiple search options.

    pathChecked = {}
    
    if versionChecker is not None:
        matchRe, cmdSubstString, groupNames, minVersion, maxVersion = versionChecker
        versionChecker = VersionExtractor(matchRe, cmdSubstString, groupNames)

        def checkVersions(cand):
            mVersion = versionHash[cand]
            if minVersion is not None and (not versionChecker.atLeastVersion(minVersion, mVersion)):
                return False
            if maxVersion is not None and (not versionChecker.atMostVersion(maxVersion, mVersion)):
                return False
            return True
        
        def chooseNewest(allPaths):
            curCandidate = allPaths[0]
            curVersion = versionHash[curCandidate]
            for candidate in allPaths[1:]:
                mVersion = versionHash[candidate]
                if versionChecker.atLeastVersion(curVersion, mVersion, excludeEndpoint = True):
                    # If it's newer, use it.
                    curCandidate = candidate
                    curVersion = mVersion
            return curCandidate
        
        choiceFn = chooseNewest
        filterFn = checkVersions

    # If there's a filterFn, don't check that it's an executable.
    
    def checkCandidate(c):
        print "Checking", c, "...",
        if versionChecker is not None:
            mVersion = versionChecker.extractVersion(c)
            if mVersion is None:
                print "not a version."
                return False
            versionHash[c] = mVersion
        elif filterFn is not None:
            if not filterFn(c):
                print failureString
                return False
        else:
            # Gotta at least make sure it's an executable.
            if (not os.path.isfile(c)) or (not os.access(c, os.X_OK)):
                print "not an executable."
                return False                

        print "ok."
        allCandidates.append(c)
        return True            
    
    if execCandidates is not None:
        for cand in execCandidates:
            if not os.path.isabs(cand):
                print "%s is not a full pathname; skipping." % cand                
            try:
                pathChecked[cand]
                continue
            except KeyError:
                pathChecked[cand] = True
            if checkCandidate(cand) and (choiceFn is None):
                print "Chose", cand
                return cand
        
    if execName is not None:
        if sys.platform == "win32":
            if not execName.endswith(".exe"):
                execName += ".exe"
            envPath = os.environ["PATH"].split(";")
        else:
            envPath = os.environ["PATH"].split(":")
        if execExtraDirs is not None:
            envPath += execExtraDirs
        for d in envPath:
            p = os.path.join(d, execName)                        
            try:
                pathChecked[p]
                continue
            except KeyError:
                pathChecked[p] = True
            if os.path.exists(p):
                if checkCandidate(p) and (choiceFn is None):
                    print "Chose", p
                    return p

    # If we're still here, we may have a bunch of things in 
    # allCandidates and choiceFn exists.

    if allCandidates:
        p = choiceFn(allCandidates)
        print "Chose", p
        return p

    else:
        if execPrompt is not None:

            if promptIntro is not None:
                print promptIntro

            def cleanValue(prompt):
                v = raw_input(prompt)
                if v is None:
                    return v
                else:
                    v = v.strip()
                    # Strip trailing slash, in either direction
                    if v and v[-1] in "/\\":
                        v = v[:-1]
                    return v

            while True:
                v = cleanValue(execPrompt)
                if v == "":
                    if execFailureString is not None:
                        print execFailureString
                    if exitOnFailure:
                        sys.exit(1)
                    else:
                        return None
                elif checkCandidate(v):
                    return v
        else:
            # This may also be a failure - don't ignore the failure cases.
            if execFailureString is not None:
                print execFailureString
            if exitOnFailure:
                sys.exit(1)
            else:
                return None
