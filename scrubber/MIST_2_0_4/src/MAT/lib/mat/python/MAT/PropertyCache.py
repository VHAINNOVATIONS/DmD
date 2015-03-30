# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This is a file-based property cache which I was originally using in
# the experiment engine, but now also in the workspaces.

#
# A property cache
#

# attrTriples is a sequence of triples <attr>, <readFunction>, <writeFunction>
# The read and write functions take the object and the value, and return
# a string (for writing) or an object (for reading). If they're null,
# the literal value is used.

# 11/4/2009: updated the backing store to the ConfigParser module. This
# allows me to have a GLOBALS section, and then subsections for, e.g.,
# MAT engine argument settings.

# So the syntax now permits the value to be a dictionary OF STRINGS,
# in which case
# the attribute is a section name. This can't happen recursively.
# Otherwise, the section name is "GLOBALS". And, the keys will be
# case-insensitive. So in the dictionary children, we have to
# store a couple things, like the actual field name and whether it's
# boolean or not.

from ConfigParser import RawConfigParser, MissingSectionHeaderError

class PropertyCache:

    def __init__(self, obj, file, *attrTriples):
        self.obj = obj
        self.file = file
        self.attrTriples = []
        self.attrDict = {}
        if attrTriples:
            self.addAttrTriples(attrTriples)

    def addAttrTriples(self, attrTriples):
        self.attrTriples += attrTriples
        self.attrDict.update(dict([(a[0].lower(), (a[0], a[1], a[2])) for a in attrTriples]))

    def save(self):
        obj = self.obj
        p = RawConfigParser()
        p.add_section("_GLOBALS")
        for attr, readF, writeF in self.attrTriples:            
            writeObj = None
            if hasattr(obj, attr):
                v = getattr(obj, attr)  
                if v is not None:                    
                    if writeF is not None:
                        writeObj = writeF(obj, v)
                    elif type(v) is dict:
                        writeObj = v
                    else:
                        writeObj = str(v)
            elif writeF is not None:
                writeObj = writeF(obj, None)
            if writeObj is not None:                
                if type(writeObj) is dict:
                    addedSection = False
                    for k, v in writeObj.items():
                        if v is None:
                            continue
                        if not addedSection:
                            p.add_section(attr)
                            p.add_section("_METADATA " + attr)
                            addedSection = True
                        # Let's record the type. Let's allow
                        # strings, booleans, ints, floats.
                        # For backward compatibility, "no"
                        # means string, "yes" means boolean
                        # when we read.
                        if type(v) in (bool, str, int, float):
                            tString = type(v).__name__
                            v = str(v)
                        else:
                            raise TypeError, "dictionary value must be ASCII string, float, boolean or integer"
                        p.set(attr, k, v)
                        p.set("_METADATA " + attr, k, tString + " " + k)
                else:
                    p.set("_GLOBALS", attr, writeObj)        
        fp = open(self.file, "w")
        p.write(fp)
        fp.close()

    def load(self):
        obj = self.obj
        p = RawConfigParser()
        try:
            p.read([self.file])
        except MissingSectionHeaderError:
            # Oops, probably the old file format.
            self._loadv1()
            return
        lvPairs = []
        metadata = {}
        dictDigesters = {"str": lambda x: x,
                         "no": lambda x: x,
                         "int": int,
                         "float": float,
                         "yes": lambda x: x == "True",
                         "bool": lambda x: x == "True"}
        for sect in p.sections():
            opts = p.options(sect)
            if sect == "_GLOBALS":
                for lab in opts:
                    val = p.get(sect, lab)
                    lvPairs.append((lab, val))
            elif sect.startswith("_METADATA "):
                attrName = sect[10:]
                localMdata = {}
                for lab in opts:
                    val = p.get(sect, lab)
                    # Let's record the type. Let's allow
                    # strings, booleans, ints, floats.
                    # For backward compatibility, "no"
                    # means string, "yes" means boolean
                    # when we read.
                    toks = val.split(None, 1)                    
                    if len(toks) == 2:
                        localMdata[lab] = (dictDigesters[toks[0]], toks[1])
                metadata[attrName] = localMdata
            else:
                # Construct a dictionary.
                d = {}
                for lab in opts:
                    d[lab] = p.get(sect, lab)
                lvPairs.append((sect, d))
        for lab, val in lvPairs:
            if metadata.has_key(lab):
                for k, (digester, trueK) in metadata[lab].items():
                    v = val[k]
                    del val[k]
                    val[trueK] = digester(v)
            if self.attrDict.has_key(lab):
                attrName, readF, writeF = self.attrDict[lab]
                if readF is not None:
                    readObj = readF(obj, val)
                else:
                    readObj = val
                if readObj is not None:
                    setattr(obj, attrName, readObj)

    # For the 1.0 property cache file format.
    # First, we have to turn the dictionary into something
    # useful. The 1.0 version didn't have to worry about
    # the case insensitivity issue.
    
    def _loadv1(self):
        obj = self.obj
        attrDict = dict([(attrName, (readF, writeF)) for attrName, readF, writeF
                         in self.attrDict.values()])
        fp = open(self.file, "r")
        for line in fp.readlines():
            toks = line.strip().split(" : ", 1)
            if len(toks) == 2:
                [lab, val] = toks
                if attrDict.has_key(lab):
                    readF, writeF = attrDict[lab]
                    if readF is not None:
                        readObj = readF(obj, val)
                    else:
                        readObj = val
                    if readObj is not None:
                        setattr(obj, lab, readObj)
        fp.close()

