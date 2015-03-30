# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# MATConfig is a dict, but it's oh, so much more.
# You can override settings with a config file, or
# with the environment. This is a read-only dictionary,
# as far as the user is concerned.

# Override order: env -> MAT_SETTINGS_FILE in environ -> MAT_settings.config
# This needs to be enforced as time goes by.

import os, sys

from UserDict import IterableUserDict
import ConfigParser

class ConfigError(Exception):
    pass

class ConfigDict(IterableUserDict):

    def __init__(self, useEnv = True, verboseConfig = False):
        IterableUserDict.__init__(self)
        self.verboseConfig = verboseConfig
        self.sourceAndVerboseStatus = {}
        thisDir = os.path.dirname(__file__)
        configFile = os.path.join(thisDir, "MAT_settings.config")
        if os.path.exists(configFile):
            self._readConfigFile(configFile)
        else:
            raise ConfigError, "config file doesn't exist"
        self.useEnv = useEnv

    def augmentSettings(self, f):
        f = f.strip()
        if not f:
            # Empty string.
            return
        if not os.path.exists(f):
            raise ConfigError, "config file doesn't exist"
        self._readConfigFile(os.path.abspath(f))

    def _readConfigFile(self, f):
        p = ConfigParser.RawConfigParser()
        p.optionxform = str
        p.read([f])
        for sect in p.sections():
            if sect == "_GLOBALS":
                prefix = ""
            else:
                prefix = sect + ":"
            for opt in p.options(sect):
                k = prefix + opt
                self.sourceAndVerboseStatus[k] = [f, False]
                self.data[k] = p.get(sect, opt)

    def __getitem__(self, key):
        useEnv = self.useEnv
        if key == "MAT_PKG_HOME":
            useEnv = False
        if useEnv and os.environ.has_key(key):
            v = os.environ[key]
            if (not self.sourceAndVerboseStatus.has_key(key)) or \
               (self.sourceAndVerboseStatus[key][0] != "<shell environment>"):
                self.sourceAndVerboseStatus[key] = ["<shell environment>", False]
        else:
            v = IterableUserDict.__getitem__(self, key)
        # If we've gotten this far, getitem hasn't thrown KeyError, which means
        # that the key HAS to have an entry in sourceAndVerboseStatus.
        # But let's check.
        if not self.sourceAndVerboseStatus.has_key(key):
            self.sourceAndVerboseStatus[key] = ["<unknown source>", False]
        if self.verboseConfig and (not self.sourceAndVerboseStatus[key][1]):
            self.sourceAndVerboseStatus[key][1] = True
            print >> sys.stderr, "[Read value of config var %s from %s]" % (key, self.sourceAndVerboseStatus[key][0])
        return v            

    def __setitem__(self, key, val):
        raise KeyError, "Read-only dictionary"

    def has_key(self, key):
        return (self.useEnv and os.environ.has_key(key)) or \
               IterableUserDict.has_key(self, key)

    def setVerboseConfig(self, boolVal):
        self.verboseConfig = boolVal

    def copy(self):
        newConf = ConfigDict(self.useEnv, self.verboseConfig)
        newConf.data = self.data.copy()
        newConf.sourceAndVerboseStatus = dict([(k, v[:]) for (k, v) in self.sourceandVerboseStatus.items()])
        return newConf

    def getMATVersion(self):
        vFile = os.path.join(self.get("MAT_PKG_HOME"), "etc", "VERSION")
        fp = open(vFile, "r")
        v = fp.read().strip()
        fp.close()
        return v

MATConfig = ConfigDict()
