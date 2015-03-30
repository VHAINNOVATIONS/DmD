# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This object is used by the plugins to modify web/htdocs/doc/html/index.html and
# to insert documentation in the appropriate place. A subclass of this class
# should be defined in the Python for the class, and referenced in
# the <doc_enhancement_class> element in task.xml.

# Specialize the process() method.

import os, re, xml.dom.minidom, urllib, cgi

class PluginDocInstaller:

    # Set up the environment, find the body, turn it into XML.
    
    def __init__(self, taskBasename, indexContents):
        self.taskBasename = taskBasename
        m = re.search("<body>.*</body>", indexContents, re.S)
        body = indexContents[m.start():m.end()]
        self.bodyDoc = xml.dom.minidom.parseString(body)
        self.prefix = indexContents[:m.start()]
        self.suffix = indexContents[m.end():]

    # The default does nothing.
    
    def process(self):
        pass

    def finish(self):
        return self.prefix + self.toXML(self.bodyDoc) + self.suffix

    # Utilities. These should be class methods, but screw it.

    #
    # Documentation-format-specific utilities
    #

    # The HREF is with respect to the plugin dir, which means,
    # the way we've set things up, that tasks/<basename>/<href>
    # will get there.    
    
    def addAppOverviewEntry(self, href, txt, liID = None, showOverview = True):
        overview = self.getElementById('appoverview')
        # Make it visible, because we're adding something.
        self.removeClass(overview, "invisible")
        entryS = cgi.escape(txt)
        if href:
            urlTarget = "tasks/%s/%s" % (self.taskBasename, href)
            entryS = '<a href = "%s" target="iframetarget">%s</a>' % (urllib.quote(urlTarget), entryS)
        idS = ""
        if liID:
            idS = ' id="%s"' % liID
        s = '<ul class="secthead"><li%s>%s</li></ul>' % (idS, entryS)
        overview.appendChild(self.xmlNodeFromString(s))
        # If this is the first one, we should change the main pane to show
        # it. If it's NOT the first one, we should change the main pane to
        # show the main overview. And brand the title.
        if href and showOverview:
            self.showOverview(href, txt)

    def addListElement(self, listElt, txt, href = None, first = False):
        txt = cgi.escape(txt)
        if href:
            txt = "<a href='tasks/%s/%s' target='iframetarget'>%s</a>" % \
                  (urllib.quote(self.taskBasename), urllib.quote(href), txt)
        li = self.xmlNodeFromString("<li>"+txt+"</li>")
        if first:
            self.insertFirst(listElt, li)
        else:
            listElt.appendChild(li)
        return li

    def addTree(self, listElt, entries):
        for entry in entries:
            if len(entry) == 2:
                url, txt = entry
                self.addListElement(listElt, txt, href = url)
            elif len(entry) == 3:
                url, txt, subEntries = entry
                li = self.addListElement(listElt, txt, href = url)
                if subEntries:
                    ul = self.xmlNodeFromString("<ul/>")
                    li.appendChild(ul)
                    self.addTree(ul, subEntries)                

    def showOverview(self, href, txt):
        urlTarget = "tasks/%s/%s" % (self.taskBasename, href)
        iframe = self.getElementById('maindocpane')
        iframe.setAttribute("src", urlTarget)
        self.setTitle(txt)        

    def setTitle(self, title):
        self.prefix = re.sub("<title>[^<]*</title>", "<title>"+cgi.escape(title)+"</title>", self.prefix, 1)
        
    def addAppCustomizationList(self, xmlString):
        custLoc = self.getElementById('appcustomizations')
        self.removeClass(custLoc, "invisible")
        node = self.xmlNodeFromString(xmlString)
        self.addClass(node, "tasksection")
        custLoc.appendChild(node)
        
    def makeListEntry(self, href, txt):
        return "<li><a href='tasks/%s/%s' target='iframetarget'>%s</a></li>" % \
               (urllib.quote(self.taskBasename), urllib.quote(href), cgi.escape(txt))

    #
    # General utilities
    #

    def removeClass(self, node, className):
        attrClass = node.getAttribute("class")
        toks = attrClass.split()
        if className in toks:
            # Remove it.
            toks.remove(className)
            if toks:
                node.setAttribute("class", " ".join(toks))
            else:
                node.removeAttribute("class")

    def addClass(self, node, className):
        attrClass = node.getAttribute("class")
        if not attrClass:
            node.setAttribute("class", className)
        else:
            toks = attrClass.split()
            if className not in toks:
                node.setAttribute("class", attrClass + " " + className)        
    
    def getElementById(self, id, node = None):
        if node is None:
            node = self.bodyDoc
        if node.nodeType is xml.dom.minidom.Node.ELEMENT_NODE and \
           node.getAttribute("id") == id:
            return node
        for child in node.childNodes:
            r = self.getElementById(id, child)
            if r is not None:
                return r
        return None

    def xmlNodeFromString(self, str):
        doc = xml.dom.minidom.parseString(str)
        child = doc.firstChild
        doc.removeChild(child)
        return child

    def insertBefore(self, node, newNode):
        node.parentNode.insertBefore(newNode, node)

    def insertAfter(self, node, newNode):
        if node.nextSibling:
            node.parentNode.insertBefore(newNode, node.nextSibling)
        else:
            node.parentNode.appendChild(newNode)

    def insertFirst(self, node, newNode):
        if node.firstChild:
            node.insertBefore(node.firstChild, newNode)
        else:
            node.appendChild(newNode)

    NO_CLOSE = ["br"]

    def toXML(self, node, sList = None):
        atTop = False
        if sList is None:
            atTop = True
            sList = []
        if node.nodeType is xml.dom.minidom.Node.ELEMENT_NODE:
            sList.append("<"+node.tagName)
            for i in range(node.attributes.length):
                attr = node.attributes.item(i)
                sList.append(" %s='%s'" % (attr.nodeName, attr.nodeValue))
            sList.append(">")
            for child in node.childNodes:
                self.toXML(child, sList)
            if node.tagName not in self.NO_CLOSE:
                sList.append("</%s>" % node.tagName)
        elif node.nodeType is xml.dom.minidom.Node.TEXT_NODE:
            sList.append(cgi.escape(node.data))
        else:
            for child in node.childNodes:
                self.toXML(child, sList)
        if atTop:
            return "".join(sList)
