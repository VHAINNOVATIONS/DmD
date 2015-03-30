# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# Here's where we manage plugins. The plugins contain tasks or demos or both.

# The plugins are in a sister directory to this module.

import os, sys, glob, shutil, re, subprocess
import MAT.ExecutionContext

class PluginError(Exception):
    pass

# NonAsciiError 

class NonAsciiError(Exception):
    pass

# Originally, I had a distinction between applications
# and document formats. In the long run, because I need
# inheritance across the boundary between them, and because
# I need to distribute different format configurations separately,
# it makes sense to combine them again.

# The inheritance, as a result, isn't actually Python
# inheritance except when there's an accompanying class to
# the XML task specification. 

#
# Utilities
#

from MAT.XMLNode import XMLNode, XMLNodeDescFromFile, XMLNodeFromFile

from xml.dom import Node

TASK_DESC = XMLNodeDescFromFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_template.xml"))

TASKS_DESC = {"nType": Node.ELEMENT_NODE,
              "label": "tasks",
              "obligMultipleChildren":
              [TASK_DESC]}

DEMO_DESC = XMLNodeDescFromFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_template.xml"))

#
# Task definition
#

def LoadPluginTask(xmlPath):
    try:
        xmlNode = XMLNodeFromFile(xmlPath, {"tasks": TASKS_DESC, "task": TASK_DESC})
    except Exception, e:
        if True or MAT.ExecutionContext._DEBUG:
            raise
        else:
            raise PluginError, ("encountered error parsing XML task file %s; error was: %s" % (xmlPath, e))
    if xmlNode is None:
        if MAT.ExecutionContext._DEBUG:
            raise
        else:
            raise PluginError, ("could not find tasks in XML task file %s; error was: %s" % xmlPath)
    if xmlNode.label == "tasks":
        tasks = xmlNode.children["task"]
    else:
        tasks = [xmlNode]
    return tasks

from MAT.PluginDocInstaller import PluginDocInstaller
from MAT.ModelBuilder import ModelBuilder
from MAT.Operation import XMLOpArgumentAggregator

class ModelInfo:

    def __init__(self, task, clsName, configName, buildSettings):
        self.task = task
        self.modelClass = FindPluginClass(clsName, task.name)
        if not issubclass(self.modelClass, ModelBuilder):
            raise PluginError, ("task %s specifies model build class %s which is not a subclass of ModelBuilder" % (task.name, clsName))
        self.configName = configName
        self.modelBuildSettings = self.modelClass.enhanceAndExtract(XMLOpArgumentAggregator(buildSettings))
        
    # Returns an absolute model path or None

    def getDefaultModel(self):
        return self.task.getDefaultModel()

    def getModelClass(self):
        return self.modelClass

    def getModelBuildSettings(self):
        return self.modelBuildSettings

    def buildModelBuilder(self, **kw):
        settings = self.modelBuildSettings.copy()
        # So I want to override the defaults with
        # the results from **kw.
        settings.update(kw)
        return self.getModelClass()(self.task, self, **settings)

import MAT.Annotation

class PluginTaskDescriptor:

    def __init__(self, name, dir):
        self.name = name
        self.taskRoot = dir
        self.webDir = None
        if dir:
            self.webDir = os.path.basename(dir)
        self.settings = {}
        self.visible = True
        if dir:
            self.resourceDir = os.path.join(dir, "resources")
        # Documentation enhancement
        self.docEnhancementClass = None
        # Workflows.
        self.inheritAllWorkflows = False
        self.inheritWorkflows = []
        self.localWorkflowDescs = {}
        self._workflowDescCache = None
        self._workflowCache = None
        # Web customization.
        self.displayConfig = None
        self.inheritJS = True
        self.inheritCSS = True
        self.alphabetizeUILabels = True
        self.textRightToLeft = False
        self.tokenlessAutotagDelimiters = None
        self.localJSFiles = []
        self.localCSSFiles = []
        self.shortWebName = None
        self.longWebName = None
        # Java engine settings.
        self.localJavaEngineSettings = {}
        self._javaEngineSettingsCache = None
        # Parentage.
        self.parentName = None
        self.parentObj = None
        self.children = []
        # Tags.
        # I need to keep track of the tag order
        # in case that's the presentation order
        # in the UI someone wants.
        self._tagHierarchyCache = None
        # New set descriptors.
        self.localAnnotationSetDescriptors = {"all_annotations_known": False,
                                              "inherit": [],
                                              "descriptors":
                                              [{"category": "admin",
                                                "name": "admin",
                                                "annotations":
                                                [{"label": "SEGMENT",
                                                  "all_attributes_known": True,
                                                  "span": True},
                                                 {"label": "VOTE",
                                                  "all_attributes_known": True,
                                                  "span": False}],
                                                "attributes":
                                                [{"name": "annotator",
                                                  "type": "string",
                                                  "of_annotations": ["SEGMENT", "VOTE"],
                                                  "distinguishing_attribute_for_equality": True},
                                                 {"name": "status",
                                                  "type": "string",
                                                  "of_annotations": ["SEGMENT"],
                                                  "choices": ["non-gold", "human gold", "reconciled", "ignore during reconciliation"],
                                                  "distinguishing_attribute_for_equality": True},
                                                 # Part of the protocol between backend and UI.
                                                 {"name": "to_review",
                                                  "type": "string",
                                                  "of_annotations": ["SEGMENT"]},
                                                 # Ditto.
                                                 {"name": "reviewed_by",
                                                  "type": "string",
                                                  "of_annotations": ["SEGMENT"]},
                                                 {"name": "content",
                                                  "type": "string",
                                                  "of_annotations": ["VOTE"],
                                                  "distinguishing_attribute_for_equality": True},
                                                 {"name": "segment",
                                                  "of_annotations": ["VOTE"],
                                                  "distinguishing_attribute_for_equality": True,
                                                  "type": "annotation",
                                                  "label_restrictions": ["SEGMENT"]},
                                                 {"name": "comment",
                                                  "type": "string",
                                                  "of_annotations": ["VOTE"],
                                                  "distinguishing_attribute_for_equality": True},
                                                 {"name": "chosen",
                                                  "type": "string",
                                                  "of_annotations": ["VOTE"],
                                                  "distinguishing_attribute_for_equality": True},
                                                 {"name": "new",
                                                  "type": "string",
                                                  "of_annotations": ["VOTE"],
                                                  # Should be changed to a boolean. Used during
                                                  # reconciliation to identify new votes from the UI.
                                                  "choices": ["no", "yes"]}
                                                 ]}]}
        self._cachedAnnotationSetDescriptors = None
        self.localAnnotationDisplays = {"labels": {}, "groups": {}, "order": ["SEGMENT", "VOTE"],
                                        "attributes": {}}
        self._cachedAnnotationDisplays = None
        self._annotationTypeRepository = None
        self._annotationCategoriesToSets = {}
        self._annotationSetsToCategories = {}
        # Model build settings
        self.localModelInfoDict = {}
        self._modelInfoCache = {}
        self.defaultModel = None
        # Workspaces
        self.inheritWorkspaceOperations = True
        self.localWorkspaceOperations = {}
        self._workspaceOperationCache = None
        # Step implementations.
        self.localStepImplementationTable = {}
        self._stepImplementationCache = None
        # Similarity profiles.
        self.similarityProfiles = None
        self.scoreProfiles = None

    def addChild(self, child):
        child.parentObj = self
        self.children.append(child)

    def _digestXMLSettings(self, xmlNode):
        if xmlNode is None:
            return {}
        d = xmlNode.wildcardAttrs.copy()
        for setting in xmlNode.children["setting"]:
            if d.has_key(setting.children["name"].text):
                raise PluginError, ("explicit <setting> for %s clashes with parent attribute" % setting.children["name"].text)
            d[setting.children["name"].text] = setting.children["value"].text
        return d

    def fromXML(self, taskDesc):

        attrs = taskDesc.attrs
        children = taskDesc.children
        
        if taskDesc.attrs["visible"] == "no":
            self.visible = False

        if taskDesc.children["doc_enhancement_class"]:
            clsName = taskDesc.children["doc_enhancement_class"].text
            cls = FindPluginClass(clsName, self.name)
            if not issubclass(cls, PluginDocInstaller):
                raise PluginError, ("task %s specifies doc enhancement class %s which is not a subclass of PluginDocInstaller" % (self.name, clsName))
            self.docEnhancementClass = cls                

        self.parentName = attrs["parent"]
                
        # Do the workflows. The elements in the workflows will
        # be dictionaries, and they'll guide the creation of the step
        # objects. 

        workflows = children["workflows"]
        if workflows.attrs["inherit_all"] == "yes":
            self.inheritAllWorkflows = True
        if workflows.attrs["inherit"] is not None:
            self.inheritWorkflows = workflows.attrs["inherit"].split(",")
        for workflow in workflows.children["workflow"]:
            stepsList = []
            for step in workflow.children["step"]:
                createSettings = self._digestXMLSettings(step.children["create_settings"])
                runSettings = self._digestXMLSettings(step.children["run_settings"])
                uiSettings = self._digestXMLSettings(step.children["ui_settings"])
                attrs = step.attrs.copy()
                attrs["hand_annotation_available"] = (attrs["hand_annotation_available"] == "yes")
                attrs["by_hand"] = (attrs["by_hand"] == "yes")
                stepsList.append((attrs, createSettings, runSettings, uiSettings))
            wfAttrs = {"uiSettings": self._digestXMLSettings(workflow.children["ui_settings"])}
            wfAttrs["hand_annotation_available_at_end"] = (workflow.attrs["hand_annotation_available_at_end"] == "yes")
            wfAttrs["hand_annotation_available_at_beginning"] = (workflow.attrs["hand_annotation_available_at_beginning"] == "yes")
            self.localWorkflowDescs[workflow.attrs["name"]] = (wfAttrs, stepsList)

        # Do the web customizations.
        if children["web_customization"] is not None:
            cust = children["web_customization"]
            self.displayConfig = cust.attrs["display_config"]
            self.localJSFiles = [a.text for a in cust.children["js"]]
            self.localCSSFiles = [a.text for a in cust.children["css"]]
            if cust.attrs["inherit_js"] == "no":
                self.inheritJS = False
            if cust.attrs["inherit_css"] == "no":
                self.inheritCSS = False
            if cust.attrs["alphabetize_labels"] == "no":
                self.alphabetizeUILabels = False                
            self.textRightToLeft = (cust.attrs["text_right_to_left"] == "yes")
            self.tokenlessAutotagDelimiters = cust.attrs["tokenless_autotag_delimiters"]
            if cust.children["short_name"]:
                self.shortWebName = cust.children["short_name"].text
            if cust.children["long_name"]:
                self.longWebName = cust.children["long_name"].text
            if ((self.shortWebName is not None) or (self.longWebName is not None)) and \
               not ((self.shortWebName is not None) and (self.longWebName is not None)):
                raise PluginError, ("for task %s, short_name and long_name must be both defined, or neither" % self.name)

        # Java engine settings.
        if children["java_subprocess_parameters"] is not None:
            attrs = children["java_subprocess_parameters"].attrs
            self.localJavaEngineSettings["stack_size"] = attrs["stack_size"]
            self.localJavaEngineSettings["heap_size"] = attrs["heap_size"]
        
        # Do the settings.

        self.settings = self._digestXMLSettings(children["settings"])

        # Do the annotation sets. 

        # Let's just get us back to where we are. Don't even bother trying to take them
        # apart yet.

        asds = children["annotation_set_descriptors"]
        eLabelDict = {}
        if asds:
            convertedASDs = self.localAnnotationSetDescriptors
            # First, convert it to JSON for local storage.
            convertedASDs["all_annotations_known"] = (asds.attrs["all_annotations_known"] == "yes")
            convertedASDs["inherit"] = (asds.attrs["inherit"] and [s.strip() for s in asds.attrs["inherit"].split(",")]) or []
            newDescriptors = [{"category": asd.attrs["category"],
                               "name": asd.attrs["name"],
                               "annotations":
                               [{"label": annot.attrs["label"],
                                 "all_attributes_known": annot.attrs["all_attributes_known"] == "yes",
                                 "span": annot.attrs["span"] != "no"}
                                for annot in asd.children["annotation"]],
                               "attributes":
                               [{"name": attr.attrs["name"],
                                 "distinguishing_attribute_for_equality":
                                 attr.attrs["distinguishing_attribute_for_equality"] == "yes",
                                 "of_annotations": (attr.attrs["of_annotation"] and [s.strip() for s in attr.attrs["of_annotation"].split(",")]) or [],
                                 "type": attr.attrs["type"] or "string",
                                 "aggregation": attr.attrs["aggregation"],
                                 "optional": attr.attrs["optional"] == "yes",
                                 "default": attr.attrs["default"],
                                 "default_is_text_span": attr.attrs["default_is_text_span"] == "yes",
                                 "choices": [c.text for c in attr.children["choice"]] or [],
                                 "effective_labels": dict([(c.text, c.attrs["effective_label"])
                                                           for c in attr.children["choice"]
                                                           if c.attrs["effective_label"] is not None]) or None,
                                 "minval": (attr.children["range"] and attr.children["range"].attrs["from"]) or None,
                                 "maxval": (attr.children["range"] and attr.children["range"].attrs["to"]) or None,
                                 "label_restrictions": [(t.attrs["label"], ((t.children["attributes"] and t.children["attributes"].wildcardAttrs.copy()) or None)) for t in attr.children["label_restriction"]]}
                                for attr in asd.children["attribute"]]}
                              for asd in asds.children["annotation_set_descriptor"]]
            # Convert the values.
            unpermittedAttrSpecs = {
                "string": ["minval", "maxval", "label_restrictions"],
                "int": ["label_restrictions"],
                "float": ["choices", "effective_labels", "label_restrictions"],
                "boolean": ["choices", "effective_labels",
                            "minval", "maxval", "label_restrictions", "default_is_text_span"],
                "annotation": ["choices", "effective_labels",
                               "minval", "maxval", "default", "default_is_text_span"]}
            def _coerceValue(attr, kName, v, tList, desc):
                if v is None:
                    return None
                for t in tList:
                    try:
                        return t(v)
                    except ValueError:
                        continue
                raise PluginError, ("for task %s, %s '%s' of attribute %s is %s" %
                                    (self.name, kName, v, attr["name"], desc))

            def _boolCoerce(s):
                if s == "yes":
                    return True
                elif s == "no":
                    return False
                else:
                    raise ValueError
            
            for d in newDescriptors:
                # TEMPORARY RESTRICTION.
                if d["category"] and (d["category"] not in ("zone", "token", "content")):
                    raise PluginError, ("for task %s, category %s is not one of zone, token, content" %
                                        (self.name, d["category"]))

                for e in d["annotations"]:
                    if e["label"] in ("untaggable", "SEGMENT", "VOTE"):
                        raise PluginError, ("reserved annotation name '%s' mentioned in task %s" % (e["name"], self.name))
                localLabels = set([e["label"] for e in d["annotations"]])

                for attr in d["attributes"]:
                    # TEMPORARY RESTRICTION
                    for label in attr["of_annotations"]:
                        if label not in localLabels:
                            raise PluginError, ("for task %s, label %s for attribute %s not locally declared (this restriction will ultimately be removed)" % (self.name, label, attr["name"]))
                
                    t = attr["type"]
                    if not unpermittedAttrSpecs.has_key(t):
                        raise PluginError, ("for task %s, attribute %s for labels %s has unknown type %s" %
                                            (self.name, attr["name"], attr["of_annotations"], t))
                    for e in unpermittedAttrSpecs[t]:
                        if attr[e]:
                            raise PluginError, ("for task %s, %s attribute %s for labels %s is not permitted a value for %s" %
                                                (self.name, t, attr["name"], attr["of_annotations"], e))
                        # It's null, but we don't want the key there at all.
                        del attr[e]
                    if t == "int":
                        attr["minval"] = _coerceValue(attr, "minval", attr["minval"], (int, long), "neither int nor long")
                        attr["maxval"] = _coerceValue(attr, "maxval", attr["maxval"], (int, long), "neither int nor long")
                        attr["default"] = _coerceValue(attr, "default", attr["default"], (int, long), "neither int nor long")
                        attr["choices"] = [_coerceValue(attr, "choices", c, (int, long), "neither int nor long")
                                           for c in attr["choices"]]
                        if attr["effective_labels"]:
                            attr["effective_labels"] = dict([(_coerceValue(attr, "effective_labels", k, (int, long),
                                                                           "neither int nor long"), v)
                                                             for (k, v) in attr["effective_labels"]])
                    elif t  == "float":
                        attr["minval"] = _coerceValue(attr, "minval", attr["minval"], (int, long, float),
                                                      "neither int nor long nor gloat")
                        attr["maxval"] = _coerceValue(attr, "maxval", attr["maxval"], (int, long, float),
                                                      "neither int nor long nor float")
                        attr["default"] = _coerceValue(attr, "default", attr["default"], (int, long, float),
                                                       "neither int nor long nor float")
                    elif t == "boolean":
                        attr["default"] = _coerceValue(attr, "default", attr["default"], (_boolCoerce,),
                                                       "neither 'yes' or 'no'")
                        
            # Check uniqueness.
            allDescriptorNames = set()
            allLabelNames = set()
            allAttributes = set()
            self._checkASDUniqueness(newDescriptors, allDescriptorNames, allLabelNames, allAttributes)
            convertedASDs["descriptors"] += newDescriptors

        adisplay = children["annotation_display"]
        if adisplay is not None:
            convertedADisplays = self.localAnnotationDisplays
            # First, convert it to something storeable.
            convertedADisplays["labels"].update(dict([(lbl.attrs["name"], 
                                                       {"name": lbl.attrs["name"],
                                                        "css": lbl.attrs["css"],
                                                        "presented_name": lbl.attrs["presented_name"],
                                                        "edit_immediately": lbl.attrs["edit_immediately"] == "yes",
                                                        "accelerator": lbl.attrs["accelerator"]})
                                                      for lbl in adisplay.children["label"]]))
            convertedADisplays["groups"].update(dict([(grp.attrs["name"],
                                                       {"name": grp.attrs["name"],
                                                        "children": (grp.attrs["children"] and [s.strip() for s in grp.attrs["children"].split(",")]),
                                                        "css": grp.attrs["css"]})
                                                      for grp in adisplay.children["label_group"]]))
            # The group names can also be label names. So remove those things
            # which are groups and also labels. But it's only the label and label_group
            # elements which form this; not the attribute info.
            convertedADisplays["order"] += [e.attrs["name"] for e in (adisplay.children["label"] + adisplay.children["label_group"])
                                            if not ((e in adisplay.children["label_group"] and \
                                                     convertedADisplays["labels"].has_key(e.attrs["name"])))]
            
            for e in adisplay.children["attribute"]:
                for aLabel in e.attrs["of_annotation"].split(","):
                    convertedADisplays["attributes"][(e.attrs["name"], aLabel)] = {
                        "editor_style": e.attrs["editor_style"],
                        "read_only": e.attrs["read_only"] == "yes",                        
                        "custom_editor": e.attrs["custom_editor"],
                        "custom_editor_button_label": e.attrs["custom_editor_button_label"],
                        "url_link": e.attrs["url_link"],
                        "custom_editor_is_multiattribute": e.attrs["custom_editor_is_multiattribute"] == "yes"}
            if not asds:
                allLabelNames = set()

            # We ought to be able to override inherited behavior. So don't
            # check here whether the label is locally defined.

            allGroupNamesOrig = set(convertedADisplays["groups"].keys())
            if len(allGroupNamesOrig) < len(convertedADisplays["groups"].keys()):
                raise PluginError, ("label hierarchy in task %s contains a duplicate label group name" % self.name)
            
            for g in convertedADisplays["groups"].values():
                if not g["children"]:
                    raise PluginError, ("tag group %s has no children in task %s" % (g["name"], self.name))

        # Similarity profiles
        simProfiles = children["similarity_profile"]
        if simProfiles:
            self.similarityProfiles = []
            for simProfile in simProfiles:
                p = {"name": simProfile.attrs["name"],
                     "tag_profiles": [{"true_labels": [l.strip() for l in tp.attrs["true_labels"].split(",")],
                                       "attr_equivalences": dict([(aq.attrs["name"], [s.strip() for s in aq.attrs["attrs"].split(",")]) for aq in tp.children["attr_equivalences"]]),
                                       "dimensions": [{"name": dim.attrs["name"],
                                                       "weight": float(dim.attrs["weight"]),
                                                       "method": dim.attrs["method"],
                                                       "aggregator_method": dim.attrs["aggregator_method"],
                                                       "param_digester_method": dim.attrs["param_digester_method"],
                                                       "params": dim.wildcardAttrs}
                                                      for dim in tp.children["dimension"]]}
                                      for tp in simProfile.children["tag_profile"]]}
                # Strata should not even be set if there aren't any in the input.
                if simProfile.children["stratum"]:
                    p["strata"] = [[l.strip() for l in s.attrs["true_labels"].split(",")] for s in simProfile.children["stratum"]]
                self.similarityProfiles.append(p)

        # Score profiles.
        scoreProfiles = children["score_profile"]
        if scoreProfiles:
            self.scoreProfiles = []
            for scoreProfile in scoreProfiles:
                p = {"name": scoreProfile.attrs["name"],
                     "label_limitation": (scoreProfile.children["label_limitation"] and [l.strip() for l in scoreProfile.children["label_limitation"].attrs["true_labels"].split(",")]) or None,
                     "aggregations": [{"name": aggr.attrs["name"],
                                       "true_labels": [l.strip() for l in aggr.attrs["true_labels"].split(",")]}
                                      for aggr in scoreProfile.children["aggregation"]],
                     "attr_decompositions": [{"attrs": [l.strip() for l in attr.attrs["attrs"].split(",")],
                                              "true_labels": [l.strip() for l in attr.attrs["true_labels"].split(",")]}
                                             for attr in scoreProfile.children["attr_decomposition"]],
                     "partition_decompositions": [{"method": pt.attrs["method"],
                                                   "true_labels": [l.strip() for l in pt.attrs["true_labels"].split(",")]}
                                                  for pt in scoreProfile.children["partition_decomposition"]]}
                self.scoreProfiles.append(p)
            
        # Do the workspaces.

        workspace = children["workspace"]
        if workspace is not None:
            if workspace.attrs["inherit_operations"] == "no":
                self.inheritWorkspaceOperations = False
            for action in workspace.children["operation"]:
                aName = action.attrs["name"]
                actionSettings = self._digestXMLSettings(action.children["settings"])
                self.localWorkspaceOperations[aName] = actionSettings

        # Capture the model build settings.

        if children["model_config"]:
            settingsList = children["model_config"]
            for settings in settingsList:
                configName = settings.attrs["config_name"]
                # configName may be None. If there's already a default,
                # or if there's already a model by that configName, complain.
                if (configName is None) and self.localModelInfoDict.has_key(None):
                    raise PluginError, ("for task %s, two local default model build settings defined" % self.name)
                elif self.localModelInfoDict.has_key(configName):
                    raise PluginError, ("for task %s, two local model build settings named %s" % (self.name, configName))
                self.localModelInfoDict[configName] = (settings.attrs["class"], configName,
                                                       self._digestXMLSettings(settings.children["build_settings"]))

        if children["default_model"]:
            self.defaultModel = children["default_model"].text

        # Do the step implementations. These are the local
        # implementations. For each step name, there might be
        # a default implementation, and then an implementation for
        # specific elements. When you get the workflows, you first
        # compute the local implementation table, and then instantiate
        # the table based on the computations.

        stepImpls = children["step_implementations"]
        if stepImpls is not None:
            for step in stepImpls.children["step"]:
                sName = step.attrs["name"]
                workflows = step.attrs["workflows"]
                sClassName = step.attrs["class"]
                createSettings = self._digestXMLSettings(step.children["create_settings"])
                sClass = FindPluginClass(sClassName, self.name)
                if not issubclass(sClass, PluginStep):
                    raise PluginError, ("task %s specifies step implementation class %s which is not a subclass of PluginStep" % (self.name, sClassName))
                try:
                    localTableEntry = self.localStepImplementationTable[sName]
                except KeyError:
                    localTableEntry = [None, {}]
                    self.localStepImplementationTable[sName] = localTableEntry                    
                if workflows is not None:
                    for wfName in workflows.split(","):
                        localTableEntry[1][wfName] = (sClass, createSettings)
                else:
                    localTableEntry[0] = (sClass, createSettings)

    #
    # Managing resource files
    #

    def getResourceFile(self, pathSuff):
        return os.path.join(self.resourceDir, pathSuff)

    def readResourceFileLines(self, pathSuff):
        rFile = self.getResourceFile(pathSuff)
        fp = open(rFile, "r")
        lines = fp.readlines()
        fp.close()
        return lines

    #
    # Settings. Config can override.
    #

    #
    # Retrieving local workflows, tag tables, and step implementations.
    #

    # This just checks uniqueness. Later, I need to ensure that the true label
    # for effective labels and the of_annotations for attributes actually exist.
    # We do that when we create the annotation type repository, in order to
    # ensure that inherited labels can be used.
    
    def _checkASDUniqueness(self, descriptors, allDescriptorNames, allLabelNames, allAttributes):

        for d in descriptors:
            if d["name"] in allDescriptorNames:
                raise PluginError, ("for task %s, duplicate annotation set descriptor name %s" % (self.name, d["name"]))
            allDescriptorNames.add(d["name"])
            for a in d["annotations"]:
                if a["label"] in allLabelNames:
                    raise PluginError, ("for task %s, duplicate annotation or effective label name %s" % (self.name, a["label"]))
                allLabelNames.add(a["label"])
            localLabelNames = [a["label"] for a in d["annotations"]]
            localAttributes = set()
            for attr in d["attributes"]:
                for tName in attr["of_annotations"]:
                    if (attr["name"], tName) in allAttributes:
                        raise PluginError, ("for task %s, duplicate attribute %s of annotation %s" %
                                            (self.name, attr["name"], tName))
                    allAttributes.add((attr["name"], tName))
                    localAttributes.add((attr["name"], tName))
                if attr.has_key("effective_labels") and attr["effective_labels"]:
                    for v in attr["effective_labels"].values():
                        if v in allLabelNames:
                            raise PluginError, ("for task %s, duplicate annotation or effective label name %s" % (self.name, v))
                        allLabelNames.add(v)

    def _cacheASDs(self):
        if self._cachedAnnotationSetDescriptors is None:
            asdCache = []
            if self.localAnnotationSetDescriptors:
                asds = self.localAnnotationSetDescriptors
                if asds["inherit"] and self.parentObj:
                    asdCache = self.parentObj._inheritASDs(asds["inherit"])
                allDescriptorNames = set([d["name"] for d in asdCache])
                allLabelNames = set()
                allAttributes = set()
                # Don't need to check uniqueness for what's in the parent.
                for d in asdCache:
                    allLabelNames |= set([a["label"] for a in d["annotations"]])
                    for attr in d["attributes"]:
                        if attr.has_key("effective_labels") and attr["effective_labels"]:
                            allLabelNames |= set(attr["effective_labels"].values())
                    for attr in d["attributes"]:
                        allAttributes |= set([(attr["name"], tName) for tName in attr["of_annotations"]])
                # But we DO for what's in the child.
                self._checkASDUniqueness(asds["descriptors"], allDescriptorNames, allLabelNames, allAttributes)
                # Now, we need to enforce that of_annotations all exist, as well
                # as the truenames and attributes in the effective_labels. 
                for d in asdCache:
                    for attr in d["attributes"]:
                        for tName in attr["of_annotations"]:
                            if tName not in allLabelNames:
                                raise PluginError, ("for task %s and annotation set descriptor %s, attribute %s refers to undefined label %s" %
                                                    (self.task, d["name"], attr["name"], tName))
                # If it passes, append them.
                asdCache += asds["descriptors"]
            self._cachedAnnotationSetDescriptors = asdCache

    def _inheritASDs(self, inheritList):
        nameList = []
        categoryList = []
        for i in inheritList:
            if i == "category:admin":
                raise PluginError, ("can't inherit admin category")
            if i.startswith("category:"):
                categoryList.append(i[9:])
            else:
                nameList.append(i)
        self._cacheASDs()
        return [d for d in self._cachedAnnotationSetDescriptors
                if (d["name"] in nameList) or (d["category"] and (d["category"] in categoryList))]        

    def getAnnotationTypeRepository(self):
        if self._annotationTypeRepository is None:
            atp = MAT.Annotation.GlobalAnnotationTypeRepository()
            # Here's how we do it. First, we inherit all the relevant types
            # from the parent. Then, we add the local types. You CANNOT
            # redefine something that's already defined; that's an error.
            # I want to be able to inherit specific sets, so we really want
            # to cache the accumulated annotation set descriptors. Any
            # accumulated parent set will already have the appropriate uniqueness
            # conditions enforced already (no duplicate annots, no duplicate
            # attrs in the annots). We only need to augment the parent
            # with the local additions. And once we've accumulated all the
            # elements, we create the types. I think this is cleaner than
            # asking the types to copy themselves, etc.
            self._cacheASDs()
            allKnown = self.localAnnotationSetDescriptors and self.localAnnotationSetDescriptors.get("all_annotations_known", False)
            atp.fromJSONDescriptorList(self._cachedAnnotationSetDescriptors,
                                       allAnnotationsKnown = allKnown)
            self._annotationCategoriesToSets = {}
            self._annotationSetsToCategories = {}
            for d in self._cachedAnnotationSetDescriptors:
                cat = d.get("category")
                if cat is not None:
                    self._annotationSetsToCategories[d["name"]] = cat
                    try:
                        self._annotationCategoriesToSets[cat].add(d["name"])
                    except KeyError:
                        self._annotationCategoriesToSets[cat] = set([d["name"]])
            self._annotationTypeRepository = atp
        return self._annotationTypeRepository

    # Here's a convenience function.
    def newDocument(self, signal = None, docClass = MAT.Document.AnnotatedDoc):
        return docClass(signal = signal, globalTypeRepository = self.getAnnotationTypeRepository())

    def getAnnotationDisplayInfo(self):
        if self._cachedAnnotationDisplays is None:
            # Use the inheritance info from the local annotation set descriptors,
            # and then override and filter. The only label display info should
            # refer to an effective label or true label in the annotation type repository.
            atp = self.getAnnotationTypeRepository()
            # If there's any inheritance information at all, then get the display
            # info from the parent. The information has to be ordered, because
            # I need to compute the local tag info. Overriding locally overrides
            # the order.
            if self.parentObj and self.localAnnotationSetDescriptors and \
               self.localAnnotationSetDescriptors["inherit"]:
                parentInfo = self.parentObj.getAnnotationDisplayInfo()
                tagOrder = parentInfo["order"][:]
                labelDict = parentInfo["labels"].copy()
                groupDict = parentInfo["groups"].copy()
                attrDict = parentInfo["attributes"].copy()
                if self.localAnnotationDisplays:
                    localInfo = self.localAnnotationDisplays
                    labelDict.update(localInfo["labels"])
                    groupDict.update(localInfo["groups"])
                    attrDict.update(localInfo["attributes"])
                    tagOrder = [o for o in tagOrder if o not in localInfo["order"]] + localInfo["order"]
            elif self.localAnnotationDisplays:
                localInfo = self.localAnnotationDisplays
                labelDict = localInfo["labels"].copy()
                groupDict = localInfo["groups"].copy()
                attrDict = localInfo["attributes"].copy()
                tagOrder = localInfo["order"][:]
            else:
                labelDict = {}
                groupDict = {}
                attrDict = {}
                tagOrder = []
            # We'll build the order backward. Anything that's in a group's children
            # which isn't a mentioned group or a known label will be dropped;
            # any labels which aren't known labels will be dropped.
            labelDict = dict([(k, v) for (k, v) in labelDict.items() if atp.labelKnown(k)])
            # For the groups, first remove all the unknown labels. THEN
            # iteratively remove all the groups which have no children, and repeat
            # as long as you find something to remove. This won't catch cycles.
            # I'll deal with that when I actually build the tree.
            groupNames = groupDict.keys()
            for g in groupDict.values():
                g["children"] = [e for e in g["children"] if (e in groupNames) or atp.labelKnown(k)]
            while True:
                toRemove = set()
                for g in groupDict.values():
                    if len(g["children"]) == 0:
                        toRemove.add(g["name"])
                if not toRemove:
                    break
                for t in toRemove:
                    del groupDict[t]
                for g in groupDict.values():
                    g["children"] = [e for e in g["children"] if e not in toRemove]
            groupNames = groupDict.keys()
            tagOrder = [t for t in tagOrder if atp.labelKnown(t) or (t in groupNames)]
            info = {"labels": labelDict, "groups": groupDict, "order": tagOrder, "attributes": attrDict}
            self._cachedAnnotationDisplays = info
        return self._cachedAnnotationDisplays

    # We're now going to try to construct this directly off the display info,
    # which has already been inherited.
    
    def getTagHierarchy(self):
        if self._tagHierarchyCache is None:
            atp = self.getAnnotationTypeRepository()
            displayInfo = self.getAnnotationDisplayInfo()

            if not displayInfo["groups"]:
                # If there's no groups, just leave the tag hierarchy none.
                return

            # Now, the displayInfo has all the elements I need.

            # So the idea of tag groups is that they can be inherited, but only the
            # entire family of groupings. No interleaving, one from column A, one from
            # column B nonsense. All groups without parents are toplevel groups;
            # no cycles are permitted; ui children are permitted to be defined
            # ONLY if the group doesn't already exist in the localTags list;
            # no accelerators are permitted for the ui children; 
            # every element which is referenced has to be a content tag.
            # Children are obligatory. The structure must be a tree - nothing can
            # be mentioned more than once, and all tag group names must be mentioned.

            # So first, collect the visible names and their categories.
            # This includes the effective labels.

            allNames = dict([(k, self.getCategoryForLabel(k)) for k in displayInfo["labels"]])                             

            # Next, check to see which groups are already defined, and
            # find the roots.

            allGroupNamesOrig = set(displayInfo["groups"].keys())
            allGroupNames = allGroupNamesOrig.copy()
            allTagNames = set(allNames.keys())

            for g in displayInfo["groups"].values():
                tName = g["name"]
                children = g["children"]
                uiCSS = g["css"]

                for child in children:
                    if (child not in allGroupNamesOrig) and \
                       (not allNames.has_key(child)):
                        raise PluginError, ("tag group %s references unknown child %s in task %s" %
                                            (tName, child, self.name))
                    if (child not in allGroupNames) and \
                       (child not in allTagNames):
                        raise PluginError, ("child tag %s is named more than once in tag hierarchy in task %s" % \
                                            (child, self.name))
                    if child in allGroupNames:
                        allGroupNames.remove(child)
                    else:
                        allTagNames.remove(child)
                if allNames.has_key(tName):
                    if allNames[tName] != "content":
                        raise PluginError, ("tag group %s references non-content tag in task %s" % \
                                            tName, self.name)
                    if uiCSS is not None:
                        raise PluginError, ("tag group %s references content tag but also tries to define its own UI attributes in task %s" % \
                                            (tName, self.name))

            if len(allGroupNames) == 0:
                raise PluginError, ("tag groups in task %s are cyclic" % self.name)

            def _checkCycles(tbl, root, prefix):
                if root in prefix:
                    raise PluginError, ("tag group %s is cyclic in task %s" % (root, self.name))
                if tbl.has_key(root):
                    for child in tbl[root]["children"]:
                        _checkCycles(tbl, child, [root] + prefix)

            # These are the roots.
            for r in allGroupNames:
                _checkCycles(displayInfo["groups"], r, [])

            # All the checking is done. The tag groups constitute a tree, and no
            # name is present more than once. The elements remaining in allGroupNames are
            # the root tag groups, and the elements remaining in allTagNames, if content tags, are
            # the remaining tags (which must also be "roots"), AS LONG AS THEY'RE NOT IN THE
            # GROUPS AS WELL.

            self._tagHierarchyCache = {}
            for name in allTagNames:
                if (allNames[name] == "content") and (not displayInfo["groups"].has_key(name)):
                    self._tagHierarchyCache[name] = {}
            def _populateTagHierarchy(names, d):
                for name in names:
                    try:
                        g = displayInfo["groups"][name]
                        children = g["children"]
                        uiCSS = g["css"]
                        childD = {}
                        d[name] = {"css": uiCSS,
                                   "children": childD}
                        _populateTagHierarchy(children, childD)
                    except KeyError:
                        d[name] = {}
            _populateTagHierarchy(allGroupNames, self._tagHierarchyCache)

        return self._tagHierarchyCache

    # Let's redefine this, for the time being, from the annotation type
    # repository, etc. 

    def getJSONAnnotationRepositoryForDisplay(self):
        toplevelATR = self.getAnnotationTypeRepository().toJSON()
        jsonATR = toplevelATR["types"]
        # And I want to salt this repository with presentation information.
        # And category information, for that matter.
        displayInfo = self.getAnnotationDisplayInfo()
        for k, v in jsonATR.items():
            if displayInfo["labels"].has_key(k):
                # There's display info for this label.
                v["display"] = displayInfo["labels"][k]
            v["category"] = self._annotationSetsToCategories.get(v.get("set_name"))
            for attr in v["attrs"]:
                attr["category"] = self._annotationSetsToCategories.get(attr.get("set_name"))
            if v.has_key("effective_labels"):
                for eName, eData in v["effective_labels"].items():
                    if displayInfo["labels"].has_key(eName):
                        eData["display"] = displayInfo["labels"][eName]
                    eData["category"] = self._annotationSetsToCategories.get(eData.get("set_name"))
        for (attrName, labelName), attrD in displayInfo["attributes"].items():
            for attr in jsonATR[labelName]["attrs"]:
                if attr["name"] == attrName:
                    attr["display"] = attrD
                    break
        return toplevelATR

    # In MATAnnotationInfoToJSON, I want to further modify the
    # output of getJSONAnnotationRepositoryForDisplay. But I can't
    # do it in the same call, because of how the code is constructed.

    @staticmethod
    def simplifyJSONDisplayAnnotationRepository(toplevelATR, removeNoncontentAnnotations = False, removeRedundantInfo = False):
        if not (removeNoncontentAnnotations or removeRedundantInfo):
            return toplevelATR
        
        import copy
        typeData = copy.deepcopy(toplevelATR["types"])
        toplevelATR["types"] = typeData
        if removeNoncontentAnnotations:
            for label, typeInfo in typeData.items():
                if typeInfo.get("category") in ("zone", "token", "admin"):
                    del typeData[label]
        if removeRedundantInfo:
            for label, typeInfo in typeData.items():
                if typeInfo.get("category") == "content":
                    del typeInfo["category"]
                if typeInfo.get("set_name") == "content":
                    del typeInfo["set_name"]
                if typeInfo.get("hasSpan"):
                    del typeInfo["hasSpan"]
                if typeInfo.has_key("allAttributesKnown"):
                    if not typeInfo["allAttributesKnown"]:
                        del typeInfo["allAttributesKnown"]
                if typeInfo.get("type"):
                    del typeInfo["type"]
                if typeInfo.get("attrs") == []:
                    del typeInfo["attrs"]
                elif typeInfo.get("attrs"):
                    for attr in typeInfo["attrs"]:
                        if attr.has_key("aggregation") and \
                           (attr["aggregation"] in ("none", None)):
                            del attr["aggregation"]
                        if attr.get("category") == "content":
                            del attr["category"]
                        if attr.get("set_name") == "content":
                            del attr["set_name"]
                        if attr.get("type") == "string":
                            del attr["type"]
                        if attr.has_key("display"):
                            if attr["display"].get("editor_style") == "short_string":
                                del attr["display"]["editor_style"]
                            for k in ("custom_editor", "custom_editor_is_multiattribute", "url_link",
                                      "editor_style", "read_only", "custom_editor_button_label"):
                                if attr["display"].has_key(k):
                                    if not attr["display"][k]:
                                        del attr["display"][k]
                            if not attr["display"]:
                                del attr["display"]
                if typeInfo.has_key("display"):
                    if typeInfo["display"].get("name"):
                        del typeInfo["display"]["name"]
                    for k in ["edit_immediately", "presented_name", "accelerator"]:
                        if typeInfo["display"].has_key(k):
                            if not typeInfo["display"][k]:
                                del typeInfo["display"][k]
                    if not typeInfo["display"]:
                        # dict is now empty.
                        del typeInfo["display"]
                if typeInfo.has_key("effective_labels"):
                    if not typeInfo.get("effective_labels"):
                        del typeInfo["effective_labels"]
                    else:
                        for eLab, eLabData in typeInfo["effective_labels"].items():
                            if eLabData.get("category") == "content":
                                del eLabData["category"]
                            if eLabData.get("set_name") == "content":
                                del eLabData["set_name"]
                            if eLabData.has_key("display"):
                                if eLabData["display"].get("name"):
                                    del eLabData["display"]["name"]
                                for k in ["edit_immediately", "presented_name", "accelerator"]:
                                    if eLabData["display"].has_key(k):
                                        if not eLabData["display"][k]:
                                            del eLabData["display"][k]
                                if not eLabData["display"]:
                                    del eLabData["display"]
        return toplevelATR
    
    # These are now defined in the annotation type repository.
    # The main source of distinguishing attributes is the record of
    # attribute sets, but this may not be sufficient for our
    # purposes (e.g., the scorer ought to want all of them, even
    # if the attribute sets aren't named).
    
    def getEffectiveAnnotationLabel(self, annot, restrictToCategory = None, **kw):
        if self._annotationTypeRepository is None:
            self.getAnnotationTypeRepository()
        restrictToSets = None
        if restrictToCategory is not None:
            restrictToSets = self._annotationCategoriesToSets.get(restrictToCategory)
            if restrictToSets is None:
                return annot.atype.lab
        return self._annotationTypeRepository.getEffectiveAnnotationLabel(annot, restrictToAnnotationSetNames = restrictToSets, **kw)

    # Probably want to phase this out. The name is stupid, anyway.
    def getAnnotationTypesByCategory(self, cat):
        if self._annotationTypeRepository is None:
            self.getAnnotationTypeRepository()
        sets = self._annotationCategoriesToSets.get(cat)
        if sets is None:
            return []
        # Believe it or not, you can pass an actual set() object using *. The order
        # is arbitrary, but that's correct for this function.
        # This returns only the true labels.
        return self._annotationTypeRepository.getLabelsForAnnotationSetNames(*sets)[0]

    def getCategoryForLabel(self, lab):
        if self._annotationTypeRepository is None:
            self.getAnnotationTypeRepository()
        sName = self._annotationTypeRepository.getAnnotationSetNameForLabel(lab)
        if sName is None:
            return None
        return self._annotationSetsToCategories.get(sName)

    def getLabelsForCategory(self, cat):
        if self._annotationTypeRepository is None:
            self.getAnnotationTypeRepository()
        sets = self._annotationCategoriesToSets.get(cat)
        if sets is None:
            return ([], [])
        # Believe it or not, you can pass an actual set() object using *. The order
        # is arbitrary, but that's correct for this function.
        return self._annotationTypeRepository.getLabelsForAnnotationSetNames(*sets)

    def getLabelsAndAttributesForCategory(self, cat):
        if self._annotationTypeRepository is None:
            self.getAnnotationTypeRepository()
        sets = self._annotationCategoriesToSets.get(cat)
        if sets is None:
            return [], {}, {}
        # Believe it or not, you can pass an actual set() object using *. The order
        # is arbitrary, but that's correct for this function.
        return self._annotationTypeRepository.getLabelsAndAttributesForAnnotationSetNames(*sets)

    def _getStepImplementationTable(self):

        if self._stepImplementationCache is None:
            seedCache = {}
            if self.parentObj:
                # Gotta do a recursive copy here.
                for key, [defaultObjTriple, wfDict] in self.parentObj._getStepImplementationTable().items():
                    seedCache[key] = [defaultObjTriple, wfDict.copy()]
            for key, [defaultObjTriple, wfDict] in self.localStepImplementationTable.items():
                if not seedCache.has_key(key):
                    seedCache[key] = [defaultObjTriple, wfDict]
                else:
                    cacheEntry = seedCache[key]
                    if defaultObjTriple:
                        # There's a local default. Override everything in the parent.
                        cacheEntry[0] = defaultObjTriple
                        cacheEntry[1] = {}
                    for wfName, sClassTriple in wfDict.items():
                        cacheEntry[1][wfName] = sClassTriple
            # Every entry had better have a default object, so that
            # the undo can use the default step if nothing else
            # is around.
            for key, [defaultObjTriple, wfDict] in seedCache.items():
                if not defaultObjTriple:
                    raise PluginError, ("Task %s is missing a default implementation for step %s" % (self.name, key))
            self._stepImplementationCache = seedCache
            
        return self._stepImplementationCache

    def _getWorkflowDescTable(self):
        if self._workflowDescCache is not None:
            return self._workflowDescCache
        else:
            if self.parentObj and self.inheritAllWorkflows:
                t = self.parentObj._getWorkflowDescTable().copy()
            elif self.parentObj and self.inheritWorkflows:
                t = {}
                pWorkflows = self.parentObj._getWorkflowDescTable()
                for w in self.inheritWorkflows:
                    try:
                        t[w] = pWorkflows[w]
                    except KeyError:
                        pass
            else:
                t = {}
            for key, val in self.localWorkflowDescs.items():
                t[key] = val
            self._workflowDescCache = t
            return t

    def getWorkflows(self):
        if self._workflowCache is not None:
            return self._workflowCache
        else:
            # Compute the two local tables, and create objects
            # for each step.
            
            def _findImpl(impls, stepName, wfName):
                try:
                    stepEntry = impls[stepName]
                except KeyError:
                    raise PluginError, ("no step implementation for step %s" % stepName)
                try:
                    sClass, creationSettings = stepEntry[1][wfName]
                except KeyError:
                    sClass, creationSettings = stepEntry[0]
                if not sClass:
                    raise PluginError, ("no step implementation for step %s" % stepName)
                return sClass, creationSettings
            
            t = self._getWorkflowDescTable()
            impls = self._getStepImplementationTable()
            wfTable = {}
            for wfName, (params, stepList) in t.items():
                finalSteps = []
                for declaredAttrs, createSettings, runSettings, uiSettings in stepList:
                    stepName = declaredAttrs["name"]
                    if declaredAttrs["proxy_for_steps"] is not None:
                        sClass = MultiStep
                        stepCreationSettings = {}
                        proxyNames = declaredAttrs["proxy_for_steps"].split(",")
                        proxies = []
                        for proxyName in proxyNames:
                            pClass, pCreationSettings = _findImpl(impls, proxyName, wfName)
                            proxies.append(pClass(proxyName, self, wfName, **pCreationSettings))
                        declaredAttrs["proxies"] = proxies
                    else:
                        sClass, stepCreationSettings = _findImpl(impls, stepName, wfName)
                    creationDict = stepCreationSettings.copy()
                    creationDict.update(declaredAttrs)
                    creationDict.update(createSettings)
                    sImpl = sClass(stepName, self, wfName, runSettings = runSettings, uiSettings = uiSettings,
                                   **creationDict)
                    finalSteps.append(sImpl)
                wfTable[wfName] = PluginWorkflow(wfName, self, finalSteps, **params)
            self._workflowCache = wfTable
            return wfTable

    def getStep(self, workflow, stepName):
        try:
            wf = self.getWorkflows()[workflow]
        except KeyError:
            raise PluginError, ("no workflow named %s" % workflow)
        for step in wf.stepList:
            if step.stepName == stepName:
                return step
        raise PluginError, ("no step named %s in workflow %s" % (stepName, workflow))

    # There will always be one, because the step implementation table insists.
    
    def getDefaultStep(self, stepName):
        t = self._getStepImplementationTable()
        sClass, creationFlags = t[stepName][0]
        return sClass(stepName, self, None, **creationFlags)

    # Java subprocess setting defaults.

    def _computeJavaSubprocessParametersCache(self):
        if self.parentObj:
            t = self.parentObj.getJavaSubprocessParameters().copy()
        else:
            t = {}
        t.update(self.localJavaEngineSettings)
        self._javaEngineSettingsCache = t
        
    def getJavaSubprocessParameters(self):
        if self._javaEngineSettingsCache is None:
            self._computeJavaSubprocessParametersCache()
        return self._javaEngineSettingsCache

    # None indicates a default model. There may not be one. If there's
    # no local default model, climb until you find one. Ditto for named
    # configs. But if we climb, we need to copy it and create the proper
    # backpointer to THIS task.

    def _getModelInfoDesc(self, configName):
        if self.localModelInfoDict.has_key(configName):
            return self.localModelInfoDict[configName]
        elif self.parentObj:
            return self.parentObj._getModelInfoDesc(configName = configName)
        else:
            return None
    
    def getModelInfo(self, configName = None):
        try:
            return self._modelInfoCache[configName]
        except KeyError:
            info = self._getModelInfoDesc(configName)
            if info is not None:
                clsName, configName, buildSettings = info
                i = ModelInfo(self, clsName, configName, buildSettings)
                self._modelInfoCache[configName] = i
                return i
            else:
                return None        

    # The idea is that the name of the default model is inheritable,
    # but if it's a relative pathname, it'll be interpreted relative
    # to the child which was asked for the default model.

    def _getRawDefaultModel(self):
        if self.defaultModel:
            return self.defaultModel
        elif self.parentObj:
            return self.parentObj._getRawDefaultModel()
        else:
            return None

    def getDefaultModel(self):
        m = self._getRawDefaultModel()
        if m:
            if os.path.isabs(m):
                return m
            else:
                return os.path.join(self.taskRoot, m)
        else:
            return None

    # Ditto workspaces.

    def getWorkspaceOperations(self):
        if self._workspaceOperationCache is not None:
            return self._workspaceOperationCache
        else:
            if self.parentObj and self.inheritWorkspaceOperations:
                t = self.parentObj.getWorkspaceOperations().copy()
            else:
                t = {}
            for key, val in self.localWorkspaceOperations.items():
                t[key] = val
            self._workspaceOperationCache = t
            return t

    # This can be specialized. The backend doesn't
    # care at all what's in this; it's just for passing to
    # the frontend Javascript, as a JSON object.

    def getCGIWorkflowMetadata(self, wfObj):
        p = wfObj.params.copy()
        p["uiSettings"] = wfObj.uiSettings or {}
        return p

    # Catch-all for tasks, if they need to add something.
    def enhanceCGIMetadata(self, mData):
        pass

    # This can be specialized. It should be a list of
    # lines to be printed out in the usage mssage.

    def getCmdlineTaskMetadata(self):
        return []

    def _getStepClassTable(self):
        visited = {}
        for wf in self.getWorkflows().values():
            for step in wf.stepList:
                cls = step.__class__
                try:
                    try:
                        visited[cls][step.stepName].append(wf.name)
                    except KeyError:
                        visited[cls][step.stepName] = [wf.name]
                except KeyError:
                    visited[cls] = {step.stepName: [wf.name]}
        return visited

    def addOptions(self, aggregator):
        # For the various workflows, for the various steps,
        # collect all the classes, and ask each of them
        # for their options.
        visited = self._getStepClassTable();
        for cls, stepDict in visited.items():
            stepStr = ", ".join(["step '%s' (workflows %s)" % (stepName, ", ".join(wfList))
                                 for stepName, wfList in stepDict.items()])
            cls.addOptions(aggregator, heading = "Options for " + stepStr)

    # This probably won't be specialized. Enforces
    # inheritance for display config.

    def _inheritValue(self, attr, default = None):
        localV = getattr(self, attr)
        if localV == "":
            return default
        elif localV is not None:
            return localV
        elif self.parentObj:
            return self.parentObj._inheritValue(attr, default)
        else:
            return default

    def getDisplayConfig(self):
        return self._inheritValue("displayConfig")

    def getShortWebName(self):
        return self._inheritValue("shortWebName")

    def getLongWebName(self):
        return self._inheritValue("longWebName")
        
    # This collects all the workflows and produces a table
    # of all the steps after each step. This is used for undoing.
    # The workflows must form a DAG without cycles.

    def getStepSuccessors(self):
        t = self._getWorkflowDescTable()
        # Build up a table of previous and next.
        stepTable = {}
        for wfName, (params, stepList) in t.items():
            prevStep = None
            for declaredAttrs, createSettings, runSettings, uiSettings in stepList:
                step = declaredAttrs["name"]
                if not stepTable.has_key(step):
                    stepTable[step] = [set([]), set([]), {}]
                if prevStep:
                    stepTable[step][0].add(prevStep)
                    stepTable[step][2][prevStep] = True
                    if stepTable.has_key(prevStep):
                        stepTable[prevStep][1].add(step)
                    else:
                        stepTable[prevStep] = [set([]), set([step]), {}]
                prevStep = step
                
        # Now, compute reachability. Walk through the graph, 
        # added reachability from each predecessor and collecting
        # a total order. THEN, for each node, we can take subsets of the
        # total order which are reachable from that node.

        finalList = []
        while True:
            if not stepTable:
                break
            noIncoming = []
            for key, val in stepTable.items():
                if not val[0]:
                    noIncoming.append((key, val[1], val[2]))
            if not noIncoming:
                raise PluginError, ("Cycles in step graph for task %s" % self.name)
            for step, successorSteps, reachable in noIncoming:
                # For each successor, update the reachability
                # from this node, remove the predecessor.
                for nextStep in successorSteps:
                    e = stepTable[nextStep]
                    e[0].remove(step)
                    e[2].update(reachable)
                del stepTable[step]
            finalList += noIncoming

        finalTable = {}
        for i in range(len(finalList)):
            step, ignore, reachable = finalList[i]
            finalTable[step] = [e[0] for e in finalList[i+1:] if e[2].has_key(step)]
        # Add everybody.
        finalTable["<start>"] = [e[0] for e in finalList]

        return finalTable        
        
    # Looks for an appropriate leaf.

    # If eligibleLeafTaskImplementation throws a plugin error,
    # then we should catch the error and cache it as a possible
    # failure reason.

    def getTaskImplementation(self, wfName, steps, **params):
        failureReasons = []
        res = self._getTaskImplementation(wfName, steps, failureReasons, **params)
        if res is None:
            if failureReasons:
                raise PluginError, ("task implementation not found; possible reasons: %s" % ("; ".join(failureReasons)))
        elif self.visible and (res is not self):
            # Pretty unfriendly, since whoever's asking for it probably
            # intended to ask for this task, and you'll never get this task.
            raise PluginError, ("task %s is visible, but it's not accessible for operations because it's not a leaf in the task tree" % self.name)
        return res            

    def _getTaskImplementation(self, wfName, steps, failureReasons, **params):
        if not self.children:
            # I don't think this throws the relevant error anymore.
            # I think it all happens in eligibleLeafTaskImplementation.
            try:
                return self.eligibleLeafTaskImplementation(wfName, steps, failureReasons, **params)
            except PluginError, e:
                if str(e) not in failureReasons:
                    failureReasons.append(str(e))
                return None
        else:
            for child in self.children:
                a = child._getTaskImplementation(wfName, steps, failureReasons, **params)
                if a is not None:
                    return a
            return None

    # If there are no steps, return yourself.
    
    def eligibleLeafTaskImplementation(self, wfName, steps, failureReasons, **params):
        try:
            if not steps:
                return self
            else:
                wfObj = self.getWorkflows()[wfName]
                # Give each step that's being invoked an opportunity
                # to reject the params.
                for step in wfObj.stepList:
                    if step.stepName in steps:
                        if not step.paramsSatisfactory(wfName, failureReasons, **params):
                            return None
                return self
        except KeyError:
            return None

    # Returns a triple (taskName, serverName, serverCmd).
    # Only leaves have servers.

    def findServers(self, serverTable = None):
        if serverTable is None:
            serverTable = {}
        if not self.children:
            # Look through the workflows.
            for wfObj in self.getWorkflows().values():
                for step in wfObj.stepList:
                    if isinstance(step, TagStep):
                        step.findServers(serverTable)
            return serverTable
        else:
            for c in self.children:
                c.findServers(serverTable)
            return serverTable
    
    # Subclass this one. Used in the tokenization and tagging methods.
    # The zone types that are returned here must be the same zone types
    # assigned in the zone step (i.e., by the addZones() method of
    # the PrepStep).

    # SAM 5/26/11: Actually, the problem is that I'm trying to
    # overload the zones, because I don't have enough categories of
    # annotations. In 2.0, I'll fix this right. But for now, I'm
    # going to have the task do a more thorough job. Instead of
    # just returning the zone attribute and region type, I'm
    # going to return the true zone info.

    def getTrueZoneInfo(self):
        return "zone", "region_type", ["body"]
        
    # For the experiment engine, so we can specialize how the tables
    # are computed.

    def augmentTagSummaryScoreTable(self, t):
        return t

    def augmentTokenSummaryScoreTable(self, t):
        return t

    def augmentDetailScoreTable(self, t):
        return t

    # For the workspace engine, so we can specialize the operations
    # and folders.

    def workspaceCustomize(self, workspace, create = False):
        pass

    # Special hook for customizing the workspace upgrade from
    # MAT 1.x to MAT 2.0.
    
    def workspaceUpdate1To2(self, workspace, oldWorkspaceDir, allOldBasenames, initialUser):
        pass

    # Similarity profiles.

    def getSimilarityProfile(self, name = None):
        if self.similarityProfiles is None:
            return None
        elif len(self.similarityProfiles) == 1:
            return self.similarityProfiles[0]
        else:
            for p in self.similarityProfiles:
                if (name is None) and (p.get("name") is None):
                    return p
                elif p.get("name") == name:
                    return p
            if name is None:
                raise PluginError, "No default similarity profile"
            else:
                raise PluginError, ("No similarity profile named '%s'" % name)

    def getScoreProfile(self, name = None):
        if self.scoreProfiles is None:
            return None
        elif len(self.scoreProfiles) == 1:
            return self.scoreProfiles[0]
        else:
            for p in self.scoreProfiles:
                if (name is None) and (p.get("name") is None):
                    return p
                elif p.get("name") == name:
                    return p
            if name is None:
                raise PluginError, "No default score profile"
            else:
                raise PluginError, ("No score profile named '%s'" % name)

# It appears that it may be useful to have this as an object.

class PluginWorkflow:

    def __init__(self, name, descriptor, steps, uiSettings = None, **params):
        self.descriptor = descriptor
        self.name = name
        self.stepList = steps
        self.uiSettings = uiSettings
        # These are the DEFINED settings.
        self.params = params

# The task steps are objects. I'm going to subclass a
# bunch of them here.

import MAT.Error

from MAT.Operation import Operation, OpArgument

class PluginStep(Operation):
    
    # All of printable ASCII (not quite all of string.printable).
    # I escape the - and \ and ] with another \, and each \ must be
    # two typed characters. A number of the children who need to
    # think about ASCII exclusively need this.
    
    ASCII_CHECK = re.compile("[^0-9a-zA-Z!\"#$%&'()*+,\\-./:;<=>?@[\\\\\\]^_`{|}~ \t\n\r]")

    def __init__(self, stepName, descriptor, workflow, runSettings = None,
                 uiSettings = None, by_hand = False, **initSettings):
        if by_hand:
            raise PluginError, "by_hand attribute applies only to tagging steps"
        Operation.__init__(self)
        self.descriptor = descriptor
        self.workflow = workflow
        self.stepName = stepName
        self.initSettings = initSettings
        self.runSettings = runSettings or {}
        self.uiSettings = uiSettings or {}

    #
    # These are the main functions, the ones which really
    # need to be reimplemented for every child type. Actually,
    # it's only do() that really needs it, but if you have
    # special batch behavior, you can override doBatch.    
    #
    
    def do(self, annotSet, **kw):
        raise PluginError, "not implemented"

    def undo(self, annotSet, **kw):
        raise PluginError, "not implemented"

    def doBatch(self, iDataPairs, **kw):
        # By default, loop through the iDataPairs and
        # call the do() step.
        pairsDone = []
        for fname, iData in iDataPairs:
            # I'd like to get the file into the error in
            # batch, too, but I'm not sure how to do that consistently.
            try:
                iData = self.do(iData, **kw)
            except Exception, e:
                if MAT.ExecutionContext._DEBUG:
                    raise
                else:
                    raise MAT.Error.MATError(self.stepName, str(e),
                                             show_tb = True, file = fname)
            pairsDone.append((fname, iData))
        return pairsDone

    # Utilities.

    def getTrueZoneInfo(self):
        return self.descriptor.getTrueZoneInfo()

    def getAnnotationTypesByCategory(self, cat):
        return self.descriptor.getAnnotationTypesByCategory(cat)

    def getCGIMetadata(self):
        # This should contain the name, the pretty name, and
        # whatever settings are present. Basically, we should
        # return the entire params dictionary, plus pretty_name.
        return {"initSettings": self.initSettings,
                "runSettings": self.runSettings,
                "uiSettings": self.uiSettings}

    def paramsSatisfactory(self, wfName, failureReasons, **params):
        return True

    def removeAnnotationsByCategory(self, annotSet, *cats):
        for cat in cats:
            annotSet.removeAnnotations(self.getAnnotationTypesByCategory(cat))

    # In most cases, if an operation is done, it can't be redone.
    # However, in certain exceptional cases (redoable taggers) this
    # is not true. See ToolChain.py.
    
    def stepCanBeDone(self, annotSet):
        return self.stepName not in annotSet.getStepsDone()

    # Return True if you can determine that the step has been done,
    # independently of whether the phase is recorded.
    def isDone(self, annotSet):
        return False

# Here's a step which combines a bunch of steps. The idea is that there's
# a list of steps whose implementations combine to make this step. A
# good example is prep = zone + tokenize.

import MAT.Document

class MultiStep(PluginStep):

    def __init__(self, stepName, descriptor, workflow, proxies = None,
                 hand_annotation_available = False, **kw):

        if hand_annotation_available:
            raise PluginError, "hand_annotation_available not available for MultiStep"
        if proxies is None:
            raise PluginError, "no proxies for MultiStep"
        self.proxies = proxies
        PluginStep.__init__(self, stepName, descriptor, workflow, **kw)

    def enhanceAndExtract(self, aggregator):
        # You need to look at each proxy. Duh.
        d = {}
        for p in self.proxies:
            d.update(p.enhanceAndExtract(aggregator))
        return d

    # Do, undo,  and doBatch do exactly what you'd expect for a multi-step.
    
    def do(self, annotSet, **kw):
        for p in self.proxies:
            if p.stepName not in annotSet.getStepsDone():
                annotSet = p.do(annotSet, **kw)
                annotSet.recordStep(p.stepName)
        return annotSet

    def undo(self, annotSet, **kw):
        # UNDO BACKWARD.
        proxies = self.proxies[:]
        proxies.reverse()
        for p in proxies:
            if p.stepName in annotSet.getStepsDone():
                p.undo(annotSet, **kw)
                annotSet.stepUndone(p.stepName)

    def doBatch(self, iDataPairs, **kw):
        # Unfortunately, this needs to do, in miniature, what ToolChain
        # does.
        for p in self.proxies:
            # Filter the ones which need to be done. 
            fOrder = [fname for fname, iData in iDataPairs]
            d = dict(iDataPairs)
            pairsToDo = [(fname, iData) for fname, iData in iDataPairs
                         if p.stepName not in iData.getStepsDone()]
            pairsDone = p.doBatch(pairsToDo, **kw)
            for fname, iData in pairsDone:
                oldData = d[fname]
                if (iData is oldData) and \
                   isinstance(iData, MAT.Document.AnnotatedDoc):
                    iData.recordStep(p.stepName)
                d[fname] = iData
            iDataPairs = [(fname, d[fname]) for fname in fOrder]
        return iDataPairs

    def isDone(self, annotSet):
        for p in self.proxies:
            if not p.isDone(annotSet):
                return False
        return True

# The clean step is to make the document processable. The clean
# step isn't necessarily undoable - it can modify the signal.

class CleanStep(PluginStep):

    def undo(self, annotSet, **kw):
        raise PluginError, "can't undo clean step"

    def truncateToUnixAscii(self, annotSet):
        # The guts of the important cleaning step. We remove
        # everything that isn't ASCII, and we also remove
        # some other things we recognize, such as vertical tab
        # and form feed (note that they've been left out of
        # the ASCII_CHECK in the prep step).

        # Convert \r\n to \n.
        annotSet.signal = annotSet.signal.replace("\r\n", "\n")
        # And finally, remove all the non-breaking spaces -
        # they're latin1, but not ascii, and at the moment,
        # the tokenizer barfs on them. Actually, it's everything
        # in latin1 that has to go. 
        annotSet.signal = annotSet.signal.replace(u"\xa0", " ")
        annotSet.signal = annotSet.signal.replace(u"\x92", "'")
        # Replace formfeed with newline.
        annotSet.signal = annotSet.signal.replace("\x0c", "\n")
        # Replace vertical tab with newline.
        annotSet.signal = annotSet.signal.replace("\x0b", "\n")
        # Now, replace everything else with ?. But make it
        # Unicode again.
        annotSet.signal = annotSet.signal.encode('ascii', 'replace').decode('ascii')
        return annotSet

class AlignStep(PluginStep):

    def do(self, annotSet, **kw):
        annotSet.adjustTagsToTokens(self.descriptor)
        return annotSet

    def undo(self, annotSet, **kw):
        raise PluginError, "can't undo align step"

# The tokenization step. Soon, this will be a general
# command line step.

class CmdlinePluginStepMixin(object):

    pass

class CmdlinePluginStep(PluginStep, CmdlinePluginStepMixin):
    pass

class TokenizationStep(PluginStep):

    def undo(self, annotSet, **kw):
        # Might as well remove all the tags.
        self.removeAnnotationsByCategory(annotSet, "token")

    def isDone(self, annotSet):
        return annotSet.hasAnnotations(self.descriptor.getAnnotationTypesByCategory("token"))

class CmdlineTokenizationStep(TokenizationStep, CmdlinePluginStepMixin):

    pass

# General zoning.

class ZoneStep(PluginStep):

    argList = [OpArgument("mark_gold", help = "If present, mark the document segments as gold-standard data")]

    def addZones(self, annotSet, tuples, mark_gold = False, **kw):
        # I don't do anything with the kw - just so we can pass it down without
        # having to predict what flags are needed.

        # This will be called when there are zones, but not segments. That's going
        # to be the case when the document didn't come from us. If that's the case,
        # then we're being called with triples we created, and those will either be
        # annotations you already have which are being recreated with SEGMENTS, or
        # new segments. So one way or another, we're just going to remove
        # whatever zone annotations there are.
        annotSet.removeAnnotations(self.descriptor.getAnnotationTypesByCategory("zone"))
        # Determine the annotator and status for the segments you'll create.
        if mark_gold:
            annotator = "GOLD_STANDARD"
            status = "reconciled"
        else:
            annotator = None
            status = "non-gold"
        # Again, grab the first one.
        # There should only be one, and there better be one.
        zType, rAttr, regionTypes = self.getTrueZoneInfo()
        # NOTE: The MAT UI relies on this type being present,  even if it
        # has no annotations, because we need to distinguish between zoning
        # having happened and finding nothing, and zoning having not happened.
        zObj = annotSet.findAnnotationType(zType)
        if rAttr:
            zObj.ensureAttribute(rAttr)
        # Everything that isn't in a zone is untaggable. But we no
        # longer record that, except in the UI.
        # tuples are (start, end, rtype). Sort them
        # by start index.
        d = {}
        for t in tuples:
            if d.has_key(t[0]):
                raise PluginError, "multiple regions with the same start index"
            d[t[0]] = t
        keys = d.keys()
        keys.sort()
        i = 0
        signalLen = len(annotSet.signal)
        for k in keys:
            start, end, rtype = d[k]
            if end < start:
                raise PluginError, "region end is before region start"
            # We've overshot. Not sure how, but just drop the regions.
            if start > signalLen:
                break
            # We've overshot the end. Just truncate.
            if end > signalLen:
                end = signalLen
            if start < i:
                raise PluginError, "region starting at %d is before previous end" % i
            elif start > i:
                # Here, we would have created an untaggable annotation, but no longer.
                # Also at the end.
                pass
            if rAttr and rtype and (rtype in regionTypes):
                annotSet.createAnnotation(start, end, zObj, [rtype])
            else:
                annotSet.createAnnotation(start, end, zObj)
            annotSet.createAnnotation(start, end, "SEGMENT",
                                      {"annotator": annotator,
                                       "status": status})
            i = end

    def undo(self, annotSet, **kw):
        self.removeAnnotationsByCategory(annotSet, "zone")
        annotSet.removeAnnotations(["VOTE", "SEGMENT"])

    # If it happens to have zone annotations, it better have SEGMENTs too.
    def isDone(self, annotSet):
        return annotSet.hasAnnotations(self.descriptor.getAnnotationTypesByCategory("zone")) and \
               annotSet.hasAnnotations(["SEGMENT"])

class WholeZoneStep(ZoneStep):

    def do(self, annotSet, **kw):

        # Mark everything. Use the region info if available.
        zType, rAttr, regionTypes = self.descriptor.getTrueZoneInfo()
        rType = None
        if regionTypes:
            rType = regionTypes[0]
        
        self.addZones(annotSet, [(0, len(annotSet.signal), rType)],
                      **kw)
        
        return annotSet

class TagStep(PluginStep):

    def __init__(self, *args, **kw):
        by_hand = kw.get("by_hand")
        try:
            del kw["by_hand"]
        except:
            pass
        PluginStep.__init__(self, *args, **kw)
        # We want this for the UI, among other things.
        self.initSettings["tag_step"] = True
        if by_hand:
            self.initSettings["hand_annotation_available"] = True
            self.initSettings["by_hand"] = True

    # These are no-ops when by_hand is defined.
    
    def do(self, annotSet, **kw):
        if self.initSettings.has_key("by_hand") and self.initSettings["by_hand"]:
            return annotSet
        else:
            raise PluginError, "undefined tag step"

    def doBatch(self, iDataPairs, **kw):
        if self.initSettings.has_key("by_hand") and self.initSettings["by_hand"]:
            return iDataPairs
        else:
            return PluginStep.doBatch(self, iDataPairs, **kw)

    def findServers(self, serverTable):
        pass

    def undo(self, annotSet, **kw):
        # Remove all the content tags.
        annotSet.removeAnnotations(self.descriptor.getAnnotationTypesByCategory("content"))
        # Now, get all the segment annotations, and mark them non-gold.
        for annot in annotSet.getAnnotations(["SEGMENT"]):
            annot["status"] = "non-gold"
            annot["annotator"] = None

    def isDone(self, annotSet):
        return annotSet.hasAnnotations(self.descriptor.getAnnotationTypesByCategory("content"))

from MAT.Error import TaggerConfigurationError

class CmdlineTagStep(TagStep):

    argList = [OpArgument("tagger_local", help = "don't try to contact a remote tagger server; rather, start up a local command."),
               OpArgument("tagger_model", help = "provide a tagger model file. Obligatory if no model is specified in the task step.", hasArg = True)]

    # Support for finding servers.
    
    def findServers(self, serverTable):
        self.findTaggerServers(serverTable, **self.runSettings)

    def findTaggerServers(self, serverTable, tagger_local = False, **kw):
        tableKey = (self.descriptor.name, self.stepName)
        if (not tagger_local) and (not serverTable.has_key(tableKey)):
            try:
                # s must be a FileSystemCmdlineAsynchronous. See Carafe.py
                # for a (complicated) example.
                s = self.createTaggerService(**kw)
                serverTable[tableKey] = s
            except TaggerConfigurationError:
                pass

#
# Demos
#

class PluginDemo:

    def __init__(self, demoDir):
        self.demoDir = demoDir
        self.webDir = os.path.basename(demoDir)

    @staticmethod
    def _combineDicts(d1, d2):
        d = dict(**d1)
        d.update(d2)
        return d

    def fromXML(self, xmlNode):
        self.name = xmlNode.attrs['name']
        self.description = xmlNode.children["description"].text
        # All ready to pass to JSON. Note that we need to collect
        # the documents and check to see what's happening with
        # file_type. If it's raw, encoding must be default
        # to ascii and editable to yes; if it's not raw,
        # encoding is utf-8 and editable is no.
        self.activities = []
        for task in xmlNode.children["activity"]:
            activity = {"name": task.attrs["name"],
                        "enable_blank_document": task.attrs["enable_blank_document"] == "yes",
                        "description": task.children["description"].text,
                        "engine_settings": self._combineDicts(task.children["engine_settings"].wildcardAttrs,
                                                              task.children["engine_settings"].attrs),
                        "documents": []}
            for doc in task.children["sample_document"]:
                adoc = {"description": doc.attrs["description"],
                        "location": doc.attrs["relative_location"]}
                fileType = doc.attrs["file_type"]
                adoc["file_type"] = fileType
                if fileType == "raw":
                    adoc["encoding"] = doc.attrs["encoding"] or "ascii"
                    if doc.attrs["editable"] is None:
                        adoc["editable"] = True
                    else:
                        adoc["editable"] = (doc.attrs["editable"] == "yes")
                else:
                    adoc["editable"] = False
                    adoc["encoding"] = "utf-8"
                activity["documents"].append(adoc)
            self.activities.append(activity)

    def findRequiredTasks(self):
        tasks = []
        for dir in self.activities:
            taskName = dir["engine_settings"]["task"]
            if taskName not in tasks:
                tasks.append(taskName)
        return tasks

# First, we need to load all the classes, and then we can
# load the task files. 

# The Plugins directory will now
# contain subdirectories, each representing a task. The
# structure of each subdirectory is as described in sample_app/README.
# the otherDirs should be similar directories.

# The plugin dictionary will be a mapping from the named
# tasks to their objects (remember, the named tasks are the
# ones which are visible to the UIs). It also implements
# toplevel collection of information, especially in those
# cases where the information is only needed at the toplevel.

class PluginDict(dict):

    def __init__(self):
        self._cssCache = None
        self._jsCache = None
        self._cgiMetadataCache = None
        self._cmdlineMetadataCache = None
        self.rootTask = PluginTaskDescriptor("<root>", None)
        self.rootTask.visible = False        
        # The task is the root task. It already has SEGMENT and VOTE in it.
        # First, the annotation set.
        self.rootTask.localAnnotationSetDescriptors["descriptors"] += [{"category": "token",
                                                                        "name": "token",
                                                                        "annotations":
                                                                        [{"label": "lex",
                                                                          "all_attributes_known": True,
                                                                          "span": True}],
                                                                        "attributes": []},
                                                                       {"category": "zone",
                                                                        "name": "zone",
                                                                        "annotations":
                                                                        [{"label": "zone",
                                                                          "all_attributes_known": True,
                                                                          "span": True}],
                                                                        "attributes":
                                                                        [{"name": "region_type",
                                                                          "type": "string",
                                                                          "of_annotations": ["zone"],
                                                                          "distinguishing_attribute_for_equality": True}]}]
        self.rootTask.localAnnotationDisplays["labels"].update({"lex": {"name": "lex", "css": "border: 1px solid #CCCCCC"}})
        # I need this because the frontend filters on what's in the
        # tag order list.
        self.rootTask.localAnnotationDisplays["order"] += ["lex", "zone"]
        self.byDir = {}
        
    def recordDemoDir(self, demo):
        if self.byDir.has_key(demo.webDir):
            fullDir, curDemo, curTasks = self.byDir[demo.webDir]
            if curDemo is not None:
                raise PluginError, ("Multiple demos with the same directory basename '%s'" % demo.webDir)
            if demo.demoDir != fullDir:
                    raise PluginError, ("Demo '%s' matches basename of task, but has different directory" % demo.webDir)
            self.byDir[demo.webDir][1] = demo
        else:
            self.byDir[demo.webDir] = [demo.demoDir, demo, []]

    # Only the visible tasks will be recorded. The task root will
    # never be recorded, then. It's the only task which is permitted
    # not to have a value for webDir.
    def recordTaskDir(self, task):
        if self.byDir.has_key(task.webDir):
            fullDir, curDemo, curTasks = self.byDir[task.webDir]
            if task.taskRoot != fullDir:
                raise PluginError, ("Task basename '%s' matches basename in different directory" % task.webDir)
            self.byDir[task.webDir][2].append(task)
        else:
            self.byDir[task.webDir] = [task.taskRoot, None, [task]]

    def getRecorded(self, webDir):
        try:
            return self.byDir[webDir]
        except KeyError:
            return None

    def getRootTask(self):
        return self.rootTask

    def getTask(self, tName):
        try:
            return self[tName]
        except KeyError:
            return None

    def getAllTasks(self):
        return self.values()

    def pruneTask(self, task):
        # Don't prune the root task.
        if task is self.rootTask:
            raise PluginError, "Can't prune the root task"
        if task.visible:
            try:
                del self[task.name]
            except KeyError:
                pass
        if task.parentObj and task in task.parentObj.children:
            task.parentObj.children.remove(task)

        # Prune it from the byDir list, too.
        if task in self.byDir[task.webDir][2]:
            self.byDir[task.webDir][2].remove(task)

    #
    # Web customizations
    #

    def getCSSFiles(self):
        if self._cssCache is None:
            # recurse on the plugins.
            self._cssCache = []
            self._jsCache = []
            self._collectWebFiles(self.rootTask)            
        return self._cssCache

    def getJSFiles(self):
        if self._jsCache is None:
            # recurse on the plugins.
            self._cssCache = []
            self._jsCache = []
            self._collectWebFiles(self.rootTask)
        return self._jsCache

    def _collectWebFiles(self, c):
        for a in c.localCSSFiles:
            p = os.path.join(c.taskRoot, a)
            if p not in self._cssCache:
                self._cssCache.append(p)
        for a in c.localJSFiles:
            p = os.path.join(c.taskRoot, a)
            if p not in self._jsCache:
                self._jsCache.append(p)
        for child in c.children:
            self._collectWebFiles(child)

    # CGI metadata is a hash from workflow names to
    # an element consisting of the display config, steps,
    # and other metadata. Within the scope of a named
    # element, you can't reuse a workflow; the mapping
    # must be unique. It's a little kludgy, because
    # getWorkflows() climbs back up the tree, but I
    # can live with that, because I don't know when
    # I'll be calling the CGI fetcher.

    def getCGIMetadata(self):
        if self._cgiMetadataCache is None:
            self._cgiMetadataCache = {}
            self._compileCGIMetadata(self.rootTask, None, None, None)
        return self._cgiMetadataCache

    def _compileCGIMetadata(self, c, visibleScope, accumulatedMetadata, displayConfig):

        # Reset accumulatedMetadata within each visible element.
        # Check to see, when you add a workflow, whether it's already
        # in accumulatedWorkflows. But the restriction only
        # holds for the leaves, which is the only place I'm going
        # to collect results.

        # We ALSO want to collect workspace operations, because
        # we may need the settings in the UI. Arrgh. Also, I must
        # forbid an invisible leaf child from resetting the display config.
        
        if visibleScope is None and c.visible:
            visibleScope = c.name
            accumulatedMetadata = {}
            displayConfig = c.getDisplayConfig()

        if c.visible:
            self._cgiMetadataCache[c.name] = {"workflows": accumulatedMetadata,
                                              "shortName": c.getShortWebName(),
                                              "longName": c.getLongWebName(),
                                              "displayConfig": displayConfig,
                                              "annotationSetRepository": c.getJSONAnnotationRepositoryForDisplay(),
                                              "tagOrder": c.getAnnotationDisplayInfo()["order"],
                                              "alphabetizeLabels": c._inheritValue("alphabetizeUILabels",
                                                                                   default = False),
                                              "tokenlessAutotagDelimiters": c._inheritValue("tokenlessAutotagDelimiters"),
                                              "textRightToLeft": c._inheritValue("textRightToLeft", default = False),
                                              "tagHierarchy": c.getTagHierarchy(),
                                              "stepSuccessors": c.getStepSuccessors()}
            c.enhanceCGIMetadata(self._cgiMetadataCache[c.name])
        
        if not c.children:
            # It's a leaf. But it may not be visible, because expected
            # children weren't loaded.
            if c.visible and (c.getDisplayConfig() != displayConfig):
                raise PluginError, ("display config reset within the scope of task '%s'" % visibleScope)
            for wf, wfObj in c.getWorkflows().items():
                if accumulatedMetadata is not None:
                   if accumulatedMetadata.has_key(wf):
                       raise PluginError, ("workflow '%s' found more than once in the scope of task '%s'" % (wf, visibleScope))
                   accumulatedMetadata[wf] = {"displayConfig": displayConfig,
                                              "steps": [step.getCGIMetadata() for step in wfObj.stepList],
                                              "workflowData": c.getCGIWorkflowMetadata(wfObj)}
        else:
            # It's not a leaf.
            for child in c.children:
                self._compileCGIMetadata(child, visibleScope, accumulatedMetadata, displayConfig)

    # Cmdline metadata. Ignore the root - it will never
    # have anything.

    def formatCmdlineMetadata(self, task):
        return "\n".join(self._compileCmdlineMetadata(task)[0])

    def _compileCmdlineMetadata(self, c, inName = False, configCounter = 1):
        # We don't start collecting stuff until c is
        # names.
        l = []
        localName = False
        if not inName and c.visible:
            inName = True
            l += [c.name + " :"]
            # Reset the config counter.
            configCounter = 1
            localName = True
        if c.children:
            # Not a leaf.
            for child in c.children:
                lIncr, configCounter = self._compileCmdlineMetadata(child, inName, configCounter)
                l += lIncr
        else:
            # Leaf. If the name was local, don't print out the
            # configuration line or increment the counter.
            if localName:
                indent = ""
            else:
                l.append("  configuration %d (%s):" % (configCounter, c.name))
                configCounter += 1
                indent = "  "
            l.append(indent + "  available workflows:")
            for  k, v in c.getWorkflows().items():
                l.append(indent + "    " + k + " : steps " +
                         ", ".join([x.stepName for x in v.stepList]))
            for incr in c.getCmdlineTaskMetadata():
                l.append(indent + incr)
            s1 = []
        return l, configCounter
    
_PluginNamespace = {}

def FindPluginClass(cName, tName):
    global _PluginNamespace
    try:
        v = eval(cName, globals(), _PluginNamespace)
        import inspect
        if not inspect.isclass(v):
            # It's not a class
            raise PluginError, ("found element in plugin named %s, but it's not a class" % cName)
        return v
    except (NameError, AttributeError):
        raise PluginError, ("can't find plugin class named %s for %s" % (cName, tName))

def FindPluginObject(cName, tName):
    global _PluginNamespace
    try:
        return eval(cName, globals(), _PluginNamespace)
    except (NameError, AttributeError):
        raise PluginError, ("can't find plugin object named %s for %s" % (cName, tName))
    

#
# Plugin directory manager.
#

class PluginDirMgr:

    def __init__(self):

        self.matDir = os.path.dirname(os.path.abspath(__file__))
        self.matLoc = os.path.dirname(self.matDir)
        self.pluginDir = os.path.join(self.matDir, "Plugins")        
        self.pluginRecord = os.path.join(self.pluginDir, "plugins.txt")
        self.dirPairs = []

    #
    # core utilities
    #

    def exists(self):
        return os.path.exists(self.pluginRecord)

    def createDir(self, verbose = False):
        if not os.path.isdir(self.pluginDir):
            if verbose:
                print "### Creating", self.pluginDir, "..."
            os.makedirs(self.pluginDir)

    def read(self, verbose = False):
        # Create an ordered list, and a hash.
        self.dirPairs = []
        if self.exists():
            if verbose:
                print "### Reading plugins.txt..."
            fp = open(self.pluginRecord, "r")
            for line in [line.strip() for line in fp.readlines()]:
                if not line:
                    continue
                elif line[0] == "#":
                    # Remove all the characters at the beginning which
                    # are comments, and then strip again.
                    while line[0] == "#":
                        line = line[1:].strip()
                    self.dirPairs.append(["#", line])
                else:
                    self.dirPairs.append(["", line])
            fp.close()

    def write(self, verbose = False):
        if not self.exists():
            self.createDir(verbose = verbose)
        if verbose:
            print "### Writing plugins.txt..."
        fp = open(self.pluginRecord, "w")
        for prefix, line in self.dirPairs:
            fp.write(prefix + line + "\n")
        fp.close()

    def add(self, appDir, verbose = False):
        fullPath = os.path.realpath(os.path.abspath(appDir))

        try:
            i = self.dirPairs.index(["", fullPath])            
            if verbose:
                print "Task %s already registered. Skipping." % fullPath
            return False
        except ValueError:
            try:
                i = self.dirPairs.index(["#", fullPath])
                # there, just commented out.
                self.dirPairs[i][0] = ""
            except ValueError:
                self.dirPairs.append(["", fullPath])
            return True

    def remove(self, appDir, commentOut = False, verbose = False):
        fullPath = os.path.realpath(os.path.abspath(appDir))

        try:
            i = self.dirPairs.index(["", fullPath])
            if commentOut:
                self.dirPairs[i][0] = "#"
            else:
                # Delete it.
                self.dirPairs[i:i+1] = []
        except ValueError:
            if verbose:
                print "Task %s not registered. Skipping." % fullPath

    #
    # toplevel operations
    #

    def installPluginDir(self, appDir, verbose = False):

        taskFile = os.path.join(appDir, "task.xml")
        demoFile = os.path.join(appDir, "demo.xml")

        if (not os.path.exists(taskFile)) and (not os.path.exists(demoFile)):
            raise PluginError, "%s is not a proper task directory" % appDir

        self.read(verbose = verbose)

        if not self.add(appDir, verbose = verbose):
            # It was already registered.
            return

        self.write(verbose = verbose)

        if os.path.exists(taskFile):
                        
            pluginPy = glob.glob(os.path.join(appDir, "python", "*.py"))

            if verbose:
                print "### Compiling Python files ..."

            # Since code might be spread out over multiple directories,
            # we need to have all the plugin directories in sys.path.

            # I want to ensure that each module is imported, so the
            # code is compiled at configuration time, JUST IN CASE
            # the installation directory can't be written by the
            # person running the code - otherwise, Python will hang for
            # a bit trying to save the compiled file.

            import imp
            
            origSysModules = sys.modules
            origSysPath = sys.path

            try:
                for p in pluginPy:
                    print "Compiling", p, "..."
                    # I need to copy sys.modules and sys.path for the moment.
                    sys.modules = origSysModules.copy()
                    sys.path = [self.matLoc] + [os.path.join(pth, "python") for prefix, pth in self.dirPairs if prefix == ""] + origSysPath
                    modName = os.path.splitext(os.path.basename(p))[0]
                    try:
                        fp, pathname, desc = imp.find_module(modName)
                        imp.load_module(modName, fp, pathname, desc)
                    except ImportError, e:
                        raise PluginError, ("Couldn't load plugin from %s: %s" % (p, str(e)))
                    if fp:
                        fp.close()
            finally:
                sys.modules = origSysModules
                sys.path = origSysPath

    def uninstallPluginDir(self, appDir, commentOut = False, verbose = False):

        if self.exists():

            self.read(verbose = verbose)
            self.remove(appDir, commentOut = commentOut, verbose = verbose)
            self.write(verbose = verbose)

    def getPluginDirs(self):
        # Preserve the order of the file.
        return [x[1] for x in self.dirPairs if x[0] == ""]

#
# And now, the ugly job of actually loading the plugins.
#

def LoadPlugins(*otherDirs):

    dirMgr = PluginDirMgr()
    dirMgr.read()

    # Make sure the dirs are canonicalized and only
    # added if not present.
    
    allDirs = dirMgr.getPluginDirs()
    for dir in otherDirs:
        dir = os.path.realpath(os.path.abspath(dir))
        if dir not in allDirs:
            allDirs.append(dir)

    return LoadPluginsFromDirs(allDirs)

from MAT.Config import MATConfig

def LoadPluginsFromDirs(allDirs):

    global _PluginNamespace

    # Originally, I just did execfile, but let's try loading the
    # modules, instead, and rooting around in them. We'll have to
    # use imp. But if I do that, I'd better make sure that the
    # apps have been compiled. It's not enough to tell it to load
    # a source module, because it'll try to compile it and
    # there's no way to block it.

    import imp

    pDir = {}

    xmlDescs = []

    demos = []

    #
    # Second step: load all the Python modules, and all the
    # XML descriptions. All the directories have to be available
    # in the Python path, because otherwise, if dependencies among
    # tasks are scattered across task directories, you'll
    # be hosed. 
    #

    allPyDirs = map(lambda x: os.path.join(x, "python"), allDirs)

    for pdirName in allDirs:

        xmlPath = os.path.join(pdirName, "task.xml")
        demoXmlPath = os.path.join(pdirName, "demo.xml")
        settingsPath = os.path.join(pdirName, "MAT_settings.config")
        if os.path.exists(settingsPath):
            MATConfig.augmentSettings(settingsPath)
        
        if (not os.path.exists(xmlPath)) and (not os.path.exists(demoXmlPath)):
            raise PluginError, ("%s contains neither task.xml nor demo.xml file" % pdirName)

        if os.path.exists(demoXmlPath):
            demo = PluginDemo(os.path.dirname(demoXmlPath))
            demo.fromXML(XMLNodeFromFile(demoXmlPath, {"demo": DEMO_DESC}))
            demos.append(demo)

        if os.path.exists(xmlPath):
            xmlDescs.append((pdirName, LoadPluginTask(xmlPath)))

            # It's not enough to pass a path to imp.find_module;
            # you have to set sys.path for load_module to work
            # if the loaded module has any other local dependencies.

            pyDir = os.path.join(pdirName, "python")

            # There may not be any extensions

            if not os.path.isdir(pyDir):
                continue

            # Use all the paths, but put the current one first.

            oldSysPath = sys.path[:]        

            sys.path[0:0] = [pyDir] + [p for p in allPyDirs if p != pyDir]

            for file in os.listdir(pyDir):

                p = os.path.join(pyDir, file)
                if os.path.isfile(p) and os.path.splitext(file)[1] == ".py":
                    # It's a Python file. Load it AS A MODULE.
                    modName = os.path.splitext(file)[0]
                    if sys.modules.has_key(modName):
                        _PluginNamespace[modName] = sys.modules[modName]
                    else:
                        fp = None
                        try:
                            fp, pathname, desc = imp.find_module(modName)
                            m = imp.load_module(modName, fp, pathname, desc)
                            _PluginNamespace[modName] = m
                        except ImportError, e:                        
                            raise PluginError, ("Couldn't load plugin from %s: %s" % (p, str(e)))
                        if fp:
                            fp.close()

            sys.path = oldSysPath

    #
    # Third step: collect the classes for each description
    #

    pluginClasses = {}

    for pDirName, taskDescs in xmlDescs:
        for taskDesc in taskDescs:
            pAttrs = taskDesc.attrs
            if pAttrs["class"] is not None:
                try:
                    c = FindPluginClass(pAttrs["class"], pAttrs["name"])
                    if not issubclass(c, PluginTaskDescriptor):
                        raise PluginError, ("task %s specifies descriptor class which is not a subclass of PluginTaskDescriptor" % pAttrs["name"])
                    pluginClasses[pAttrs["name"]] = c
                except NameError:
                    raise PluginError, ("task %s specifies unknown descriptor class %s" % (pAttrs["name"], pAttrs["class"]))
            else:
                pluginClasses[pAttrs["name"]] = PluginTaskDescriptor

    #
    # Fourth step: ensure that the parent relationships among
    # the XML descriptions parallel the relationships among
    # the referenced classes.
    #

    for pDirName, taskDescs in xmlDescs:
        for taskDesc in taskDescs:
            pAttrs = taskDesc.attrs
            if pAttrs["parent"] is not None:
                if not pluginClasses.has_key(pAttrs["parent"]):
                    raise PluginError, ("the parent specified by task %s, %s, doesn't exist" % (pAttrs["name"], pAttrs["parent"]))
                # I was checking to make sure that the parent/child relationship
                # was mirrored in a superclass/subclass relationship, but now
                # that I've introduced proxies, that doesn't work, and I'm not
                # sure it's necessary anyway.
            elif not issubclass(pluginClasses[pAttrs["name"]], PluginTaskDescriptor):
                raise PluginError, ("the class specified by task %s is not a subclass of PluginTaskDescriptor" % pAttrs["name"])

    #
    # Fifth step: actually build each element, and
    # then assign the parent relationships.
    #

    outputPDir = PluginDict()

    for taskRoot, taskDescs in xmlDescs:
        # The only thing that will be here is a list of
        # task children in the pChildren dictionary.
        for taskDesc in taskDescs:
            pAttrs = taskDesc.attrs
            pClass = pluginClasses[pAttrs["name"]]
            task = pClass(pAttrs["name"], taskRoot)
            task.fromXML(taskDesc)
            pDir[pAttrs["name"]] = task
            if task.visible:
                outputPDir[pAttrs["name"]] = task

    # Define a root task.

    rootTask = outputPDir.getRootTask()

    for task in pDir.values():
        if task.parentName:
            pDir[task.parentName].addChild(task)
        else:
            rootTask.addChild(task)
        outputPDir.recordTaskDir(task)

    # We need to do a final check here. If the task has some bad dependencies, it
    # won't get checked until you actually ask about the repository.

    for task in outputPDir.values():
        try:
            t = task.getAnnotationTypeRepository()
            # Check the UI label constraints.
            t.checkUILabelConstraints(task.name)
        except Exception, e:
            raise PluginError, ("For task %s: checking the annotation repository generated the following error: %s" % (task.name, str(e)))

    for demo in demos:
        outputPDir.recordDemoDir(demo)

    # And we're done. Return ONLY the visible ones - we
    # can't refer to the invisible ones anyway.
    
    return outputPDir
