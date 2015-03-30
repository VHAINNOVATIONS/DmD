# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import sys
import MAT

# This file will ultimately contain the tagger abstractions. Right now
# it's just a dummy class to dominate Carafe.

class Tagger(object):

    def __init__(self, *args, **kw):
        pass

# Global setting for the threaded tagger broker. If this is present,
# the tool will attempt to make a request to the broker directly,
# rather than using XMLRPC.

TAGGER_BROKER = None

# Here's a thread to start up a tagger server accumulator. This
# used to be MATServer, but I'm folding it into a thread here.
# Its children are managed by socket connections, using some ungodly
# complicated connection management code I wrote a long, long
# time ago. Perhaps replace it, someday.

from MAT.Command import XMLRPCCommandServer

class TaggerBroker(XMLRPCCommandServer):

    def __init__(self, **kw):
        
        pDir = MAT.PluginMgr.LoadPlugins()

        processes = []

        # The elements in allServers are a 3-tuple <taskName> <servName> <serverInstance>
        # What comes back from findServers() is a dictionary of (taskname, servName) -> inst.

        for app in pDir.values():
            for (taskName, servName), servInst in app.findServers().items():
                processes.append([taskName, servName, servInst])

        XMLRPCCommandServer.__init__(self, *processes, **kw)
