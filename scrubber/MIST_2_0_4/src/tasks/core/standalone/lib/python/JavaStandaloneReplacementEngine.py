# Copyright (C) 2012 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Tried to have dual inheritance for the engine event, apparently failed. So it looks like
# this event will have to be a proxy.

from org.mitre.mist.replacement import StandaloneReplacementEngineProxyType, JavaStandaloneReplacementEngineEventType

from ReplacementEngine import StandaloneReplacementEngine, StandaloneReplacementEngineError

class JavaStandaloneReplacementEngineEvent(JavaStandaloneReplacementEngineEventType):

    def __init__(self, e):
        self.trueEvent = e

    def addTuple(self, lab, start, end):
        return self.trueEvent.addTuple(lab, start, end)

    def convert(self, rName):
        self.trueEvent.convert(rName)

    def getReplacedSignal(self):
        return self.trueEvent.getReplacedSignal()

    def getReplacedTuples(self):
        return self.trueEvent.getReplacedTuples()

# I'm doing it this way because I want to make sure that there's
# a single Java type interface.

class StandaloneReplacementEngineProxy(StandaloneReplacementEngineProxyType):

    def __init__(self, module, cls):
        try:
            exec "import %s" % module
        except ImportError, e:
            raise StandaloneReplacementEngineError, str(e)
        try:
            rClass = eval("%s.%s" % (module, cls))
        except ValueError:
            raise StandaloneReplacementEngineError, str(e)
        if not issubclass(rClass, StandaloneReplacementEngine):
            raise StandaloneReplacementEngineError, "The requested class is not a subclass of ReplacementEngine.StandaloneReplacementEngine"
        self.trueClass = rClass()
        # self.trueClass.evtClass = JavaStandaloneReplacementEngineEvent

    def getReplaceableLabels(self):
        return self.trueClass.getReplaceableLabels()

    def addResourceDir(self, dir):
        self.trueClass.addResourceDir(dir)

    def newEvent(self, signal, prologue):
        e = self.trueClass.newEvent(signal, prologue)
        return JavaStandaloneReplacementEngineEvent(e)
