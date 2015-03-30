# Copyright (C) 2007 - 2011 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# We need to be able to deal globally with execution context:
# debug vs. nondebug, subprocess monitoring, tempfile location.
# There's a default context, which can be updated by various executables.

_TMPDIR = None
_SUBPROCESS_DEBUG = 0
_SUBPROCESS_STATISTICS = False
_PRESERVE_TEMPFILES = False
_DEBUG = False
_VERBOSE_CONFIG = False

import tempfile, os, shutil

# The logic is simple: if you specify a directory,
# then it doesn't get removed. Otherwise, it gets removed unless
# the global context says don't remove it.

# usage:
# with Tmpdir() as dir:
#   ...

class Tmpdir:

    def __init__(self, specifiedDir = None, specifiedParent = None, preserveTempfiles = None):
        global _PRESERVE_TEMPFILES
        self.specifiedDir = specifiedDir
        self.specifiedParent = None
        if preserveTempfiles is None:
            self.preserveTempfiles = _PRESERVE_TEMPFILES
        else:
            self.preserveTempfiles = preserveTempfiles
        if self.preserveTempfiles:
            # Leave a little gift. Where are we? Extract 2
            # stack frames (because __exit__ is one of them)
            # and grab the first (top) frame. The first two
            # elements are the file and line.
            import traceback
            self.location = traceback.extract_stack(limit = 2)[0][:2]

    def __enter__(self):
        global _TMPDIR
        if self.specifiedDir:
            self.dir = self.specifiedDir
        elif self.specifiedParent:
            self.dir = tempfile.mkdtemp(dir = self.specifiedParent)
        elif _TMPDIR:
            self.dir = tempfile.mkdtemp(dir = _TMPDIR)
        else:
            self.dir = tempfile.mkdtemp()
        return self.dir

    def __exit__(self, type, value, traceback):
        if (self.specifiedDir is None) and (not self.preserveTempfiles):
            shutil.rmtree(self.dir)
        elif self.preserveTempfiles:            
            fp = open(os.path.join(self.dir, ".source"), "w")
            fp.write("%s, line %d" % self.location)
            fp.close()

def setDebug(boolVal):
    global _DEBUG
    _DEBUG = boolVal

from MAT.Config import MATConfig

def setVerboseConfig(boolVal):
    global _VERBOSE_CONFIG, MATConfig
    _VERBOSE_CONFIG = boolVal
    MATConfig.setVerboseConfig(boolVal)

#
# You can use "with" to catch errors! This is exactly what I want for my
# debug handling. But you can't really scope the debugs - you can
# pass it a value, but you can't climb the stack and find out which
# debug you're in the context of. 
#

# But I don't want to be that clever right now. I've reviewed all the cases
# where debug is handled, and at the moment I don't see the value in
# generalizing.

def setTempfilePreservation(boolVal):
    global _PRESERVE_TEMPFILES
    _PRESERVE_TEMPFILES = boolVal

def setTmpdirRoot(path):
    global _TMPDIR
    import os
    tRoot = os.path.abspath(path)
    if not os.path.exists(tRoot):
        os.makedirs(tRoot)
    elif not os.path.isdir(tRoot):
        raise OSError, "requested tempdir exists, but is not a directory"
    _TMPDIR = tRoot

def setSubprocessDebug(val):
    global _SUBPROCESS_DEBUG
    try:
        _SUBPROCESS_DEBUG = int(val)
    except ValueError:
        pass

def setSubprocessStatistics(boolVal):
    global _SUBPROCESS_STATISTICS
    if not boolVal:
        _SUBPROCESS_STATISTICS = False
    elif not _SUBPROCESS_STATISTICS:
        # TRY to set it up.
        _psutil = MATConfig.get("PSUTIL_PYTHONLIB")
        if _psutil:
            import sys
            if _psutil not in sys.path:
                sys.path.insert(0, _psutil)
                try:
                    import psutil
                    _SUBPROCESS_STATISTICS = True
                except ImportError:
                    pass

# Set a default from the configuration.

if MATConfig.get("SUBPROCESS_DEBUG") == "yes":
    setSubprocessDebug(10)

if MATConfig.get("SUBPROCESS_STATISTICS") == "yes":
    setSubprocessStatistics(True)

# So. On to the command line processing.

def _printVersionAndExit(option, opt, value, parser):    
    print "MAT version is %s." % MATConfig.getMATVersion()
    import sys
    sys.exit(1)

def addOptions(optionBearer):
    optionBearer.add_option("--version",
                            help = "Print version number and exit",
                            action = "callback",
                            callback = _printVersionAndExit)
    optionBearer.add_option("--debug", dest = "debug",
                            action = "store_true",
                            help = "Enable debug output.")
    optionBearer.add_option("--subprocess_debug", dest = "subprocess_debug",
                            type = "int",
                            metavar = "int",
                            help = "Set the subprocess debug level to the value provided, overriding the global setting. 0 disables, 1 shows some subprocess activity, 2 shows all subprocess activity.")
    optionBearer.add_option("--subprocess_statistics", dest = "subprocess_statistics",
                            action = "store_true",
                            help = "Enable subprocess statistics (memory/time), if the capability is available and it isn't globally enabled.")
    optionBearer.add_option("--tmpdir_root", dest = "tmpdir_root",
                            metavar = "dir",
                            help = "Override the default system location for temporary files. If the directory doesn't exist, it will be created. Use this feature to control where temporary files are created, for added security, or in conjunction with --preserve_tempfiles, as a debugging aid.")
    optionBearer.add_option("--preserve_tempfiles", dest = "preserve_tempfiles",
                            action = "store_true",
                            help = "Preserve the temporary files created, as a debugging aid.")
    optionBearer.add_option("--verbose_config", dest = "verbose_config",
                            action = "store_true",
                            help = "If specified, print to stderr the source of each MAT configuration variable the first time it's accessed.")

def extractOptions(options):
    if options.preserve_tempfiles is not None:
        setTempfilePreservation(True)
    if options.tmpdir_root is not None:
        setTmpdirRoot(options.tmpdir_root)
    if options.subprocess_debug is not None:
        setSubprocessDebug(options.subprocess_debug)
    if options.subprocess_statistics is not None:
        setSubprocessStatistics(True)
    if options.debug is not None:
        setDebug(True)
    if options.verbose_config is not None:
        setVerboseConfig(True)
