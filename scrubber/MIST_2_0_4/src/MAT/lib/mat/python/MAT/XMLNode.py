# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

import os, sys

# Descriptor, like a DTD.
from xml.dom import Node

# Convert the DOM into something that's actually useful, and
# do WFC checking while I'm at it. Sort of like DTDs, only useful.
# Convert everything to ASCII, while I'm at it.

# Pass in a structure that looks like this:

# {"nType": Node.ELEMENT_NODE,
#  "label": "task",
#  "obligAttrs": ["name"],
#  "optAttrs": ["instantiable", "parent", "class"],
#  "optSingleChildren": [ ... ]
#  "optMultipleChildren": [ ... ]
#  "collectTextChildren": False,
#  "wildcardAttrs": False
# }

# recursively. The resulting object has three important
# fields: text (None unless collectTextChildren is true, in
# which case it's a string), attrs (a hash of attributes,
# with all known but non-occurring attributes set to tNone),
# and children (a hash of children, either another XMLNode
# if single, a list of such if multiple, with all known
# but non-occurring attributes set to None if single,
# an empty list if multiple).

# New feature: importable definitions.

class XMLError(Exception):
    pass

# When importTmpl is not None, and import_from is present, go get the
# contents of the file using the search path and continue processing.

class XMLNode:

    def __init__(self, leaveValsAsUnicode = False, label = None, node = None, initialAttrs = None,
                 initialChildren = None, initialText = None,
                 **kw):
        self.leaveValsAsUnicode = leaveValsAsUnicode
        self.precedingComments = []
        self.followingComments = []
        # initialize everything.
        
        self.label = label
        self.attrs = {}
        self.children = {}
        self.orderedChildren = []
        self.text = initialText
        self.wildcardAttrs = None

        if initialAttrs is not None:
            self.attrs.update(initialAttrs)
        if initialChildren is not None:
            # Pairs of node, isList
            self.orderedChildren = [p[0] for p in initialChildren]
            for n, isList in initialChildren:
                if isList:
                    try:
                        self.children[n.label].append(n)
                    except KeyError:
                        self.children[n.label] = [n]
                else:
                    self.children[n.label] = n           
        if node:
            self._updateFromNode(label = label, node = node, **kw)

    def _updateFromNode(self, node = None, searchPath = None, nType = None, label = None, obligAttrs = None,
                        optAttrs = None, forceUnicodeAttrs = None,
                        obligSingleChildren = None, obligMultipleChildren = None,
                        optSingleChildren = None, optMultipleChildren = None,
                        collectTextChildren = False, wildcardAttrs = False, importTmpl = None):

        # Initial error check
        if nType is not None and \
           node.nodeType is not nType:
            raise XMLError, ("node %s is not of type %d" % (node.nodeName, nType))
        if label is not None and \
           node.nodeName != label:
            raise XMLError, ("node %s is not named %s" % (node.nodeName, label))

        if wildcardAttrs:
            self.wildcardAttrs = {}
        for attrList in [obligAttrs, optAttrs]:
            if attrList is not None:
                for attr in attrList:
                    self.attrs[attr] = None

        importedNode = self._processAttributes(node, importTmpl, wildcardAttrs, obligAttrs, optAttrs,
                                               forceUnicodeAttrs, searchPath)

        # Now, if we have an imported node, we want to use it from here on down.
        if importTmpl:
            if importedNode:
                node = importedNode
            obligSingleChildren = importTmpl["obligSingleChildren"]
            obligMultipleChildren = importTmpl["obligMultipleChildren"]
            optSingleChildren = importTmpl["optSingleChildren"]
            optMultipleChildren = importTmpl["optMultipleChildren"]
            collectTextChildren = importTmpl["collectTextChildren"]

        for childList in [obligSingleChildren, optSingleChildren,
                          obligMultipleChildren, optMultipleChildren]:
            if childList is not None:
                for child in childList:
                    self.children[child["label"]] = []
            
        textChildren = []
        childNodes = {}
        
        for childNode in node.childNodes:
            if childNode.nodeType is Node.COMMENT_NODE:
                continue
            if childNode.nodeType in [Node.TEXT_NODE, Node.CDATA_SECTION_NODE]:
                if collectTextChildren:
                    v = childNode.nodeValue
                    if not self.leaveValsAsUnicode:
                        v = v.encode('ascii')
                    textChildren.append(v)
                continue
            
            if childNodes.has_key(childNode.nodeName):
                childNodes[childNode.nodeName.encode('ascii')].append(childNode)
            else:
                childNodes[childNode.nodeName.encode('ascii')] = [childNode]        
        if collectTextChildren:
            self.text = "".join(textChildren)
        childNodeMapping = {}
        self._doChildren(node, searchPath, obligSingleChildren, childNodes, True, True, childNodeMapping)
        self._doChildren(node, searchPath, obligMultipleChildren, childNodes, True, False, childNodeMapping)
        self._doChildren(node, searchPath, optSingleChildren, childNodes, False, True, childNodeMapping)
        self._doChildren(node, searchPath, optMultipleChildren, childNodes, False, False, childNodeMapping)
        if childNodes:
            raise XMLError, ("node %s has extra child nodes: %s" % (node.nodeName, str(childNodes)))
        # Updated the ordered children. Insert comments
        # before the node.
        comments = []
        lastOrderedChild = None
        for childNode in node.childNodes:
            # I collect the comment nodes in case I have to regenerate this.
            if childNode.nodeType is Node.COMMENT_NODE:
                comments.append(childNode.data)
            else:
                try:
                    lastOrderedChild = childNodeMapping[childNode]
                    lastOrderedChild.precedingComments = comments
                    comments = []
                    self.orderedChildren.append(lastOrderedChild)
                except KeyError:
                    pass
        if comments and lastOrderedChild:
            lastOrderedChild.followingComments = comments

    def _processAttrSpecs(self, node, attrKeys, obligAttrs, optAttrs):
        if obligAttrs is not None:
            for attr in obligAttrs:
                if attr not in attrKeys:
                    raise XMLError, ("node %s does not have attribute %s" % (node.nodeName, attr))
                # Remove the attr from the attrKeys.
                attrKeys.remove(attr)
        if optAttrs is not None:
            for attr in optAttrs:
                if attr in attrKeys:
                    attrKeys.remove(attr)

    def _prepareAttributes(self, node, forceUnicodeAttrs, importTmpl, searchPath):
        
        attributes = node.attributes                     
        foundAttrDict = self.attrs
        importedNode = None
        
        if attributes is not None:
            for i in range(attributes.length):
                attr = attributes.item(i)
                attrName = attr.name.encode('ascii')
                attrVal = attr.value
                if (not self.leaveValsAsUnicode) and ((forceUnicodeAttrs is None) or (attrName not in forceUnicodeAttrs)):
                    attrVal = attrVal.encode('ascii')
                # Interlude: if there's an importTmpl and import_from is present,
                if (importTmpl is not None) and (attrName == "import_from"):
                    importedNode = self._importNode(searchPath, attrVal, importTmpl)
                    if node.childNodes:
                        # It can't have any child nodes.
                        raise XMLError, ("node %s with import_from has child nodes" % node.nodeName)
                else:
                    foundAttrDict[attrName] = attrVal
                    
        return [key for key, val in foundAttrDict.items() if val is not None], importedNode

    def _importNode(self, searchPath, fName, importTmpl):
        if searchPath:
            for p in searchPath:
                fullP = os.path.join(p, fName)
                if os.path.isfile(fullP):
                    # Not going to pass down leaveValsAsUnicode, because
                    # these files are entirely created by me, and we don't
                    # need that yet.
                    return XMLNodeFromFile(fullP, importTmpl, searchPath)
        raise XMLError, ("can't find subordinate XML file %s in search path" % fName)        

    def _processAttributes(self, node, importTmpl, wildcardAttrs, obligAttrs, optAttrs, forceUnicodeAttrs, searchPath):

        attrKeys, importedNode = self._prepareAttributes(node, forceUnicodeAttrs, importTmpl, searchPath)

        self._processAttrSpecs(node, attrKeys, obligAttrs, optAttrs)

        # In the case where there's an importTmpl but no importedNode, we want to
        # ALSO process the importTmpl against this node. Then we check the attribute
        # keys here. Then, if there's both an importTmpl and an importedNode, we want
        # to also check the child node attributes. THEN, we use the child selections for
        # either this template (if there's no importTmpl) or the child.

        if importTmpl and (not importedNode):
            self._processAttrSpecs(node, attrKeys, importTmpl["obligAttrs"], importTmpl["optAttrs"])

        # Check the remainder.
        if attrKeys:
            if wildcardAttrs:
                for key in attrKeys:
                    self.wildcardAttrs[key] = self.attrs[key]
            else:
                raise XMLError, ("node %s has extra attributes %s" % (node.nodeName, ",".join(attrKeys)))

        # Now, we may want to ALSO check the child, and then merge the results.
        if importTmpl and importedNode:
            savedAttrs = self.attrs
            self.attrs = {}
            self._processAttributes(importedNode, None, importTmpl["wildcardAttrs"],
                                    importTmpl["obligAttrs"], importTmpl["optAttrs"],
                                    importTmpl["forceUnicodeAttrs"], searchPath)
            # I want the parent to take precedence.
            self.attrs.update(savedAttrs)
        return importedNode

    def _doChildren(self, node, searchPath, childDictList, childNodes, isOblig, isUnique, childNodeMapping):
        processedNodes = self.children
        if childDictList is not None:
            for d in childDictList:
                childName = d['label']
                if not childNodes.has_key(childName):
                    if isOblig:
                        raise XMLError, ("node %s is missing the %s child" % (node.nodeName, childName))
                    elif isUnique:
                        # Optional unique children, not present.
                        processedNodes[childName] = None
                else:
                    nodes = childNodes[childName]
                    if isUnique:
                        if len(nodes) > 1:
                            raise XMLError, ("node %s has too many %s children" % (node.nodeName, childName))
                        child = XMLNode(leaveValsAsUnicode = self.leaveValsAsUnicode,
                                        node = nodes[0], searchPath = searchPath, **d)
                        processedNodes[childName] = child
                        childNodeMapping[nodes[0]] = child
                    else:
                        childList = []
                        for n in nodes:
                            child = XMLNode(leaveValsAsUnicode = self.leaveValsAsUnicode,
                                            node = n, searchPath = searchPath, **d)
                            childList.append(child)
                            childNodeMapping[n] = child
                        processedNodes[childName] = childList
                    del childNodes[childName]

    def _print(self, indent = 0, fp = sys.stdout, colwidth = 80):
        import xml.sax.saxutils
        prefix = " " * indent
        self._printComments(self.precedingComments or [], prefix, fp)
        # Let's make this pretty.        
        openPrefix = prefix
        # First, format the header line.
        openTag = prefix + "<" + self.label
        openEntity = openTag
        for key, val in self.attrs.items():
            if val is None: continue
            # Encode the XML value.
            entry = " %s='%s'" % (key, xml.sax.saxutils.escape(val))
            if (len(openEntity) + len(entry) > colwidth) and (openEntity != openTag):
                # Wrap, but only if it's not the first element.
                print >> fp, openEntity
                openPrefix = " " * len(openTag)
                openEntity = openPrefix + entry
            else:
                openEntity += entry
        if self.text is not None:
            print >> fp, "%s>%s</%s>" % (openEntity, xml.sax.saxutils.escape(self.text), self.label)
        elif self.orderedChildren:
            print >> fp, openEntity + ">"
            for c in self.orderedChildren:
                c._print(indent = indent + 2, fp = fp, colwidth = colwidth)
            print >> fp, "%s</%s>" % (prefix, self.label)
        else:
            print >> fp, openEntity + "/>"
        self._printComments(self.followingComments or [], prefix, fp)

    def _printComments(self, comments, prefix, fp):
        for comment in comments:
            # Split into newlines, strip, pad.
            lines = [line.strip() for line in comment.split("\n")]
            lines[0] = prefix + "<!-- " + lines[0]
            lines = [lines[0]] + [prefix + "     " + l for l in lines[1:]]
            lines[-1] += " -->"
            for line in lines:
                print >> fp, line

import xml
import xml.dom.minidom
from xml.dom import Node

def _recursivelyConstructTemplate(tmplDir, domNode, parent = None):
    d = {"nType": Node.ELEMENT_NODE,
         "label": domNode.nodeName.encode("ascii"),
         "obligAttrs": [],
         "optAttrs": [],
         "forceUnicodeAttrs": [],
         "optSingleChildren": [],
         "optMultipleChildren": [],
         "obligSingleChildren": [],
         "obligMultipleChildren": [],
         "collectTextChildren": False,
         "wildcardAttrs": False,
         "importTmpl": None}
    attributes = domNode.attributes
    if attributes is not None:
        foundCount = False
        for i in range(attributes.length):
            attr = attributes.item(i)
            name = attr.name.encode("ascii")
            value = attr.value.encode("ascii")
            if name == "_xmlnode_count":
                if parent:
                    if value == "?":
                        parent["optSingleChildren"].append(d)
                    elif value == "*":
                        parent["optMultipleChildren"].append(d)
                    elif value == "+":
                        parent["obligMultipleChildren"].append(d)
                    else:
                        raise XMLError, ("don't recognize attr/value %s=%s" % (name, value))
                foundCount = True
            elif name == "_xmlnode_collecttextchildren":
                if value == "yes":
                    d["collectTextChildren"] = True
                else:
                    raise XMLError, ("don't recognize attr/value %s=%s" % (name, value))
            elif name == "_xmlnode_import":
                # Import the grammar from the specified file. The options are either to
                # have an import attribute which refers to the content, or have it in-line.
                # If import is present, nothing else can be; if import is absent, well,
                # you get the idea.
                if tmplDir is None:
                    raise XMLError, "can't import from subordinate template because no template directory was found"
                importD = XMLNodeDescFromFile(os.path.join(tmplDir, value))
                if importD["label"] != d["label"]:
                    raise XMLError, ("import template doesn't have the same label as its host: %s vs. %s" % (importD["label"], d["label"]))
                d["importTmpl"] = importD
            elif name == "_xmlnode_wildcardattrs":
                if value == "yes":
                    d["wildcardAttrs"] = True
                else:
                    raise XMLError, ("don't recognize attr/value %s=%s" % (name, value))
            # New functionality: complex tokens here.
            else:
                toks = set([s.strip() for s in value.split(",")])
                # Must have one of these.
                if "obligatory" in toks:
                    d["obligAttrs"].append(name)
                elif "optional" in toks:
                    d["optAttrs"].append(name)
                else:
                    raise XMLError, ("don't recognize attr/value %s=%s" % (name, value))
                if "force_unicode" in toks:
                    d["forceUnicodeAttrs"].append(name)
        if parent and (not foundCount):
            parent["obligSingleChildren"].append(d)
    for child in domNode.childNodes:
        if child.nodeType == Node.ELEMENT_NODE:
            _recursivelyConstructTemplate(tmplDir, child, d)
    if d["importTmpl"] is not None:
        if (("import_from" in d["obligAttrs"]) or ("import_from" in d["optAttrs"])):
            raise XMLError, "import_from is a reserved attribute for elements with _xmlnode_import"
        if d["optSingleChildren"] or d["optMultipleChildren"] or d["obligSingleChildren"] or d["obligMultipleChildren"]:
            raise XMLError, "elements with _xmlnode_import are not permitted to have local children"
        if d["collectTextChildren"]:
            raise XMLError, "can't collect text children for elements with _xmlnode_import"
        if d["wildcardAttrs"]:
            raise XMLError, "can't have wildcard attrs for elements with _xmlnode_import"
    return d

# fName can be a file or a file name.

def XMLNodeDescFromFile(fName):
    if type(fName) in (str, unicode):
        tmplDir = os.path.dirname(os.path.abspath(fName))
    elif hasattr(fName, "name"):
        tmplDir = os.path.dirname(os.path.abspath(fName.name))
    else:
        tmplDir = None
    dom = xml.dom.minidom.parse(fName)
    d = None
    # Grab the first element child.
    for n in dom.childNodes:
        if n.nodeType == Node.ELEMENT_NODE:
            d = _recursivelyConstructTemplate(tmplDir, n)
            break
    dom.unlink()
    if d["importTmpl"] is not None:
        raise XMLError, "_xmlnode_import is not permitted on the toplevel node in a template file"
    return d

# Reverse engineering for testing.

def _reformatDesc(d, indent = 0, childCount = None):
    sList = ["<" + d["label"]]
    importTmpl = d["importTmpl"]
    for k in set(d["obligAttrs"] + ((importTmpl and importTmpl["obligAttrs"]) or [])):
        if k in d["forceUnicodeAttrs"]:
            sList.append(" %s='obligatory,force_unicode'" % k)
        else:
            sList.append(" %s='obligatory'" % k)
    for k in set(d["optAttrs"] + ((importTmpl and importTmpl["optAttrs"]) or [])):
        if k in d["forceUnicodeAttrs"]:
            sList.append(" %s='optional,force_unicode'" % k)
        else:
            sList.append(" %s='optional'" % k)
    if childCount is not None:
        sList.append(" _xmlnode_count='%s'" % childCount)
    if d["collectTextChildren"] or (importTmpl and importTmpl["collectTextChildren"]):
        sList.append(" _xmlnode_collecttextchildren='yes'")
    if d["wildcardAttrs"] or (importTmpl and importTmpl["wildcardAttrs"]):
        sList.append(" _xmlnode_wildcardattrs='yes'")
    children = []
    for k, ct in [("obligSingleChildren", None), ("optSingleChildren", "?"),
                  ("obligMultipleChildren", "+"), ("optMultipleChildren", "*")]:
        for subD in d[k] + ((importTmpl and importTmpl[k]) or []):
            children.append(_reformatDesc(subD, indent + 2, ct))
    if not children:
        sList.append("/>")
        return (" " * indent) + "".join(sList)
    else:
        sList.append(">")
        return "\n".join([(" " * indent) + "".join(sList)] + children + [(" " * indent) + "</" + d["label"] + ">"])

# fName can be a file or a file name. Sometimes the file is a
# UTF-8 file, and I want the values as Unicode.

def XMLNodeFromString(s, descTable, searchPath = None, leaveValsAsUnicode = False):
    if type(s) is unicode:
        # s really has to be a byte sequence in UTF-8.
        s = s.encode("utf8")        
    return _XMLNodeFromDom(xml.dom.minidom.parseString(s), descTable, searchPath, leaveValsAsUnicode)

def XMLNodeFromFile(fName, descTable, searchPath = None, leaveValsAsUnicode = False):
    if type(fName) in (str, unicode):
        pList = [os.path.dirname(os.path.abspath(fName))]
    elif hasattr(fName, "name"):
        pList = [os.path.dirname(os.path.abspath(fName.name))]
    else:
        pList = None
    if searchPath is not None:
        if pList is None:
            pList = searchPath
        else:
            pList += searchPath
    return _XMLNodeFromDom(xml.dom.minidom.parse(fName), descTable, pList, leaveValsAsUnicode)

def _XMLNodeFromDom(dom, descTable, pList, leaveValsAsUnicode):
    # dom is a document node. There should be
    # exactly one child which is an element.
    # There may be comments, for instance.
    node = None
    precedingComments = []
    for n in dom.childNodes:
        # Take the first element child.
        if n.nodeType == Node.COMMENT_NODE:
            if node is None:
                precedingComments.append(n.data)
            else:
                node.followingComments.append(n.data)
        if n.nodeType == Node.ELEMENT_NODE:
            if descTable.has_key(n.nodeName):
                node = XMLNode(leaveValsAsUnicode = leaveValsAsUnicode,
                               node = n, searchPath = pList, **descTable[n.nodeName])
                node.precedingComments = precedingComments
                node.followingComments = []
            break
    dom.unlink()
    return node
