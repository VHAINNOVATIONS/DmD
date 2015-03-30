# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# The error class

class MATError(StandardError):
    def __init__(self, phase, errstr, show_tb = False, file = None):
        self.phase = phase
        self.errstr = errstr
        self.tb_str = ""
        self.file = file
        self.prefix = "for phase " + self.phase
        if self.file:
            self.prefix += ", file " + self.file
        if show_tb:
            import traceback, sys
            self.tb_str = "".join(traceback.format_tb(sys.exc_info()[2]))
    def __str__(self):
        return self.prefix + ": " + self.errstr + "\n" + self.tb_str

class TaggerConfigurationError(StandardError):
    pass

class TaggingError(StandardError):
    pass
