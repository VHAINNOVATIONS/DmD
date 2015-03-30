# Copyright (C) 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This tool is MOSTLY for testing purposes - we currently have no need
# for a Python Web client tool.

# This is going to be a pretty direct translation of the Java tool.

from MAT.DocumentIO import getDocumentIO
from MAT.Document import AnnotatedDoc

_jsonIO = getDocumentIO("mat-json")

import urllib
from MAT import json

class WebClientError(Exception):
    pass

class WebClient:

    # E.g., "http://localhost:7801"

    # Leaving proxies unset uses the env proxies. Otherwise,
    # we use the proxies specified. An empty dictionary
    # turns off all proxies.
    
    def __init__(self, httpPrefix, proxies = None):
        self.url = httpPrefix + "/MAT/cgi/MATCGI.cgi"
        self.proxies = proxies

    def doSteps(self, doc, task, workflow, steps, **kw):
        data = kw.copy()
        data["task"] = task
        data["workflow"] = workflow
        # This is a comma-separated string.
        if (type(steps) is tuple) or (type(steps) is list):
            steps = ",".join(steps)
        data["steps"] = steps
        data["operation"] = "steps"
        data["file_type"] = "mat-json"
        data["input"] = _jsonIO.writeToByteSequence(doc)
        fp = urllib.urlopen(self.url, urllib.urlencode(data), self.proxies)
        s = fp.read()
        fp.close()
        # The string will be a JSON string, or it should be.
        try:
            d = json.loads(s)
        except ValueError:
            raise WebClientError, "CGI response isn't a JSON object"
        err = d.get("error")
        if err:
            raise WebClientError, ("Step %s failed: %s" % (d.get("errorStep"), err))
        successes = d.get("successes")
        if not successes:
            raise WebClientError, "No error, but no successful document either"
        # Get the last one.
        finalSuccess = successes[-1]
        seedDocument = AnnotatedDoc()
        _jsonIO._deserializeFromJSON(finalSuccess["val"], seedDocument)
        return seedDocument
        
