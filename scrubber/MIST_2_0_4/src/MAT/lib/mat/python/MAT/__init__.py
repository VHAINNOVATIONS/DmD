# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import sys, os

import MAT.Config

if os.environ.has_key("MAT_SETTINGS_FILE") and \
   os.environ["MAT_SETTINGS_FILE"]:
    MAT.Config.MATConfig.augmentSettings(os.environ["MAT_SETTINGS_FILE"])

import json

# There's a hideous bug in shutil.copytree() in some releases, caused by copystat.
# So we're going to redefine it so that if it's called from copytree, it
# ignores the error. 

import shutil
_cpstat = shutil.copystat
def _newcpstat(*args, **kw):
    try:
        _cpstat(*args, **kw)
    except Exception, e:
        import traceback
        for f, lno, ctx, fncall in traceback.extract_stack():
            if (os.path.basename(f) == "shutil.py") and (ctx == "copytree"):
                return
        raise
shutil.copystat = _newcpstat
    
sys.path.insert(0, MAT.Config.MATConfig["CHERRYPY_PYTHONLIB"])
sys.path.insert(0, MAT.Config.MATConfig["MUNKRES_PYTHONLIB"])
import MAT.Error
import MAT.Command
import MAT.Document
import MAT.Tagger
import MAT.JavaCarafe
import MAT.PluginMgr
import MAT.ToolChain
import MAT.PropertyCache
import MAT.Operation
import MAT.Workspace
import MAT.DocumentIO
import MAT.XMLIO
import MAT.WebClient
import MAT.ReconciliationDocument
import MAT.ComparisonDocument
import MAT.ReconciliationPhase
import MAT.Utilities
