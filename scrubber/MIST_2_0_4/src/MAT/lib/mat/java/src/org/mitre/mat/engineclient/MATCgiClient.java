/*
 * Copyright (C) 2009 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.engineclient;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.apache.commons.httpclient.DefaultHttpMethodRetryHandler;
import org.apache.commons.httpclient.HttpClient;
import org.apache.commons.httpclient.HttpException;
import org.apache.commons.httpclient.HttpStatus;
import org.apache.commons.httpclient.NameValuePair;
import org.apache.commons.httpclient.methods.PostMethod;
import org.apache.commons.httpclient.params.HttpClientParams;
import org.apache.commons.httpclient.params.HttpMethodParams;
import org.codehaus.jackson.JsonFactory;
import org.codehaus.jackson.JsonNode;
import org.codehaus.jackson.node.NullNode;
import org.codehaus.jackson.JsonParser;
import org.codehaus.jackson.map.ObjectMapper;
import org.codehaus.jackson.JsonParseException;
import org.mitre.mat.core.*;

/**
 * The class which implements CGI interaction with the MAT engine.
 *
 * @author sam
 */
public class MATCgiClient implements MATEngineClientInterface {

    // Folders.
    public static final String CORE_FOLDER = "core";
    public static final String EXPORT_FOLDER = "export";
    // Not in the core yet, but I just hate having to specialize Java.
    public static final String RECONCILIATION_FOLDER = "reconciliation";

    // Segment status.
    public static final String NON_GOLD_SEGMENT_STATUS = "non-gold";
    public static final String HUMAN_GOLD_SEGMENT_STATUS = "human gold";
    public static final String RECONCILED_SEGMENT_STATUS = "reconciled";
    public static final String IGNORE_SEGMENT_STATUS = "ignore";
    public static final String IGNORE_DURING_RECONCILIATION_SEGMENT_STATUS = "ignore during reconciliation";

    // Special votes.
    public static final String IGNORE_VOTE = "ignore";
    public static final String BAD_BOUNDARIES_VOTE = "bad boundaries";

    // Phases. These aren't in the core yet either.
    public static final String CROSSVALIDATION_CHALLENGE_PHASE = "crossvalidation_challenge";
    public static final String HUMAN_VOTE_PHASE = "human_vote";
    public static final String HUMAN_DECISION_PHASE = "human_decision";

    private String url;

    public MATCgiClient(String urlHostAndPort) {
        url = urlHostAndPort + "/MAT/cgi/MATCGI.cgi";
    }

    public MATDocumentInterface doSteps(
            MATDocumentInterface doc, String task,
            String workflow, String steps, HashMap<String, String> data)
            throws MATEngineClientException {
        return doFileOperation(doc, task, workflow, "steps", "steps", steps, data);
    }

    public MATDocumentInterface doUndoThrough(
            MATDocumentInterface doc, String task,
            String workflow, String steps, HashMap<String, String> data)
            throws MATEngineClientException {
        return doFileOperation(doc, task, workflow, "undo_through", "undo_through", steps, data);
    }

    protected MATDocumentInterface doFileOperation(
            MATDocumentInterface doc, String task,
            String workflow, String op, String opKey, String opVal,
            HashMap<String, String> data)
            throws MATEngineClientException {

        ArrayList pArray = new ArrayList();

        MATJSONEncoding e = new MATJSONEncoding();
        pArray.add(new NameValuePair("task", task));
        pArray.add(new NameValuePair("workflow", workflow));
        pArray.add(new NameValuePair("operation", op));
        pArray.add(new NameValuePair(opKey, opVal));
        pArray.add(new NameValuePair("file_type", "mat-json"));
        pArray.add(new NameValuePair("input", e.toEncodedString(doc)));

        JsonNode jsonValues = this.postHTTP(pArray, data);

        // Here's the output format. It's a hash of three elements: error (None if
        // there's no error), errorStep (None if there's no error), and
        // a list of success hashes, which have a val and steps.
        // See MATCGI_tpl.py. An error always terminates the processing,
        // so on the client, you process the successes and then the error.
        // The steps should be in order of execution, and so should the
        // successes. It's not EXACTLY enforced.

        HashMap stepMap = new HashMap();

        if (!jsonValues.isObject()) {
            throw new MATEngineClientException("CGI response isn't Javascript object");
        }

        JsonNode errNode = jsonValues.path("error");
        if ((!errNode.isMissingNode()) && (!errNode.isNull())) {
            // It's an error.
            String stepName = jsonValues.path("errorStep").getTextValue();
            String stepMsg = errNode.getTextValue();
            throw new MATEngineClientException("Step " + stepName + " failed: " + stepMsg);
        }

        JsonNode successes = jsonValues.path("successes");
        if (successes.isMissingNode() || (!successes.isArray()) || (successes.size() == 0)) {
            // I doubt that this will ever happen.
            throw new MATEngineClientException("No error, but no successful document either");
        }

        // Get the last one.
        JsonNode success = successes.get(successes.size() - 1);
        JsonNode val = success.path("val");
        MATDocumentInterface newDoc;

        try {
            newDoc = doc.getClass().newInstance();
        } catch (InstantiationException ex) {
            Logger.getLogger(MATCgiClient.class.getName()).log(Level.SEVERE, null, ex);
            throw new MATEngineClientException("Couldn't create a response document");
        } catch (IllegalAccessException ex) {
            Logger.getLogger(MATCgiClient.class.getName()).log(Level.SEVERE, null, ex);
            throw new MATEngineClientException("Couldn't create a response document");
        }

        try {
            e.fromJsonNode(newDoc, val);
        } catch (MATDocumentException ex) {
            throw new MATEngineClientException("Error during JSON decode: " + ex.toString());
        } catch (AnnotationException ex) {
            throw new MATEngineClientException("Error during JSON decode: " + ex.toString());
        }
        return newDoc;
    }

    public ArrayList<String> openWorkspace(String workspaceDir, String workspaceKey, String user)
            throws MATEngineClientException {
        ArrayList<NameValuePair> pArray = new ArrayList<NameValuePair>();
        pArray.add(new NameValuePair("workspace_key", workspaceKey));
        pArray.add(new NameValuePair("workspace_dir", workspaceDir));
        pArray.add(new NameValuePair("user", user));
        pArray.add(new NameValuePair("operation", "open_workspace"));

        JsonNode jsonValues = this.postHTTP(pArray, null);

        this.checkReturnValueValidity(jsonValues);

        ArrayList<String> returnPair = new ArrayList<String>();
        JsonNode dir = jsonValues.path("workspace_dir");
        if (!dir.isMissingNode()) {
            returnPair.add(dir.getTextValue());
        } else {
            throw new MATEngineClientException("Incorrectly formatted response to open_workspace (no workspace dir)");
        }
        JsonNode t = jsonValues.path("task");
        if (!t.isMissingNode()) {
            returnPair.add(t.getTextValue());
        } else {
            throw new MATEngineClientException("Incorrectly formatted response to open_workspace (no task)");
        }
        return returnPair;
    }

    // For the moment, I'm not about to decode the whole accursed structure
    // I can't figure out how to use the recursive Jackson decoder, 
    // and there's just too much to do it by hand. So I'll just add
    // methods as needed.

    // Originally, this structure mirrored the structure of the tag table.
    // But it seems that it would be better for it to mirror the structure
    // of what I do in my UI, namely, the tagName should be the EFFECTIVE
    // tag name, and there should be a reference to the actual tag
    // name, rather than a pointer down to more ContentTagInfo structures.

    public class ContentTagInfo {

        private String tagName;
        private String effectiveTagName;
        // Display info
        private String backgroundColor;
        private String foregroundColor;
        // These are the attrs when you're in a subspecification.
        private HashMap<String, String> attrs;

        public ContentTagInfo(String tName, JsonNode n, String effectiveTName, String taskName) throws MATEngineClientException {
            this.tagName = tName;
            this.effectiveTagName = effectiveTName;
            JsonNode display = n.get("display");
            if (display != null) {
                this.decodeDisplay(display.getTextValue(), taskName);
            }
            JsonNode attrsNode = n.get("apairs");
            if ((attrsNode != null) && (attrsNode.isArray())) {
                for (int i = 0; i < attrsNode.size(); i++) {
                    if (i == 0) {
                        attrs = new HashMap<String, String>();
                    }
                    attrs.put(attrsNode.get(i).get(0).getTextValue(), attrsNode.get(i).get(1).getTextValue());
                }
            }
        }

        private void checkColor(String color, String taskName) throws MATEngineClientException {
            // So the color possibilities in CSS are:
            // a name
            // # + 3 hex chars
            // # + 6 hex chars
            // rgb(...)
            // and in css 3, rgba(, hsl(, hsla(.
            // I'm going to ignore everything but the names and # + 6 hex.
            // CSS seems to support color hexes without a leading #,
            // and I can't do anything about that.
            // Actually, because we're interpreting this, I think
            // we're going to insist that the colors have pound-sign hashes.
            // Otherwise, the client can't tell the difference between color names
            // and color elements. So if you're using a Java client, you can't
            // use color names at all.
            boolean fail = false;
            if (color.charAt(0) != '#') {
                fail = true;
            } else if (color.length() != 7) {
                fail = true;
            }
            if (fail) {
                if (this.effectiveTagName != null) {
                    throw new MATEngineClientException("color specification '" + color + "' obtained from the server for effective tag '" + this.effectiveTagName + "' in task '" + taskName + "' is not a # + 6 hex");
                } else {
                    throw new MATEngineClientException("color specification '" + color + "' obtained from the server for tag '" + this.tagName + "' in task '" + taskName + "' is not a # + 6 hex");
                }
            }
        }

        private void decodeDisplay(String cssValue, String taskName) throws MATEngineClientException {
            // First, break on ;, then strip, then break on :.
            String[] components = cssValue.split(";");
            for (int i = 0; i < components.length; i++) {
                String component = components[i].trim();
                if (component.length() > 0) {
                    String[] lr = component.split(":", 2);
                    String left = lr[0].trim();
                    if (left.equals("background-color")) {
                        this.backgroundColor = lr[1].trim();
                        this.checkColor(this.backgroundColor, taskName);
                    } else if (left.equals("color")) {
                        this.foregroundColor = lr[1].trim();
                        this.checkColor(this.foregroundColor, taskName);
                    }
                }

            }

        }

        public String getTagName() {
            return this.tagName;
        }

        public String getEffectiveTagName() {
            return this.effectiveTagName;
        }

        public String getBackgroundColor() {
            return this.backgroundColor;
        }

        public String getForegroundColor() {
            return this.foregroundColor;
        }

        public HashMap<String, String> getAttrs() {
            return this.attrs;
        }
    }

    public WorkspaceFileResult listWorkspaceFolder(
            String workspaceDir, String workspaceKey,
            String folder)
            throws MATEngineClientException {
        ArrayList<String> args = new ArrayList<String>(Arrays.asList(folder));
        return this.doToplevelWorkspaceOperation(workspaceDir, workspaceKey,
                "list", args);
    }

    public WorkspaceFileResult openWorkspaceFile(
            String workspaceDir, String workspaceKey,
            String folder, String basename)
            throws MATEngineClientException {
        return this.openWorkspaceFile(workspaceDir, workspaceKey,
                folder, basename, null);
    }

    public WorkspaceFileResult openWorkspaceFile(
            String workspaceDir, String workspaceKey,
            String folder, String basename,
            HashMap<String, String> data)
            throws MATEngineClientException {
        // Can't use the toplevel openWorkspaceFile because it doesn't
        // do the result properly.
        ArrayList<String> opArgs = new ArrayList<String>();
        opArgs.add(folder);
        opArgs.add(basename);
        return this.doToplevelWorkspaceOperation(workspaceDir, workspaceKey,
                                                 "open_file", opArgs, data);
    }

    protected void checkReturnValueValidity(JsonNode jsonValues) throws MATEngineClientException {
        if (!jsonValues.isObject()) {
            throw new MATEngineClientException("CGI response isn't Javascript object");
        }
        JsonNode successNode = jsonValues.path("success");
        if (!successNode.isBoolean()) {
            // It's an error.
            throw new MATEngineClientException("Incorrectly formatted response to workspace operation");
        }
        if (!successNode.getBooleanValue()) {
            // Find the error.
            String errString = jsonValues.path("error").getTextValue();
            throw new MATEngineClientException("Workspace operation error: " + errString);
        }
    }

    // The file result should contain affected folders,
    // target folder, and the document. In this case, you
    // have no control over what kind of document you get;
    // it's a MATDocument.
    public class WorkspaceFileResult {

        private MATDocument doc = null;
        private ArrayList<String> affectedFolders = null;
        private String targetFolder = null;
        private String basename = null;
        private ArrayList<String> files = null;

        // A lot of these variables will never be seen
        // in MAT 2.0 initial, but it's such a pain to do
        // these overrides in Java, I'm just putting them all in.
        
        // I'm not going to use this QUITE yet.
        private boolean workspaceIsOpen = false;
        private String lockId = null;
        private boolean readOnly = false;
        private String status = null;
        private String prioritizationClass = null;
        private String prioritizationMode = null;
        private String reconciliationPhase = null;
        private ArrayList<String> userNames = null;
        private ArrayList<String> segmentIDs = null;
        private ArrayList<String> availablePhases = null;
        private ArrayList<HashMap<String,String>> basenameInfo = null;

        public WorkspaceFileResult(JsonNode jsonNode) throws MATEngineClientException {
            JsonNode docNode = jsonNode.path("doc");
            if (!docNode.isMissingNode()) {
                MATJSONEncoding e = new MATJSONEncoding();
                this.doc = new MATDocument();
                try {
                    e.fromJsonNode(this.doc, docNode);
                } catch (MATDocumentException ex) {
                    throw new MATEngineClientException("Error during JSON decode: " + ex.toString());
                } catch (AnnotationException ex) {
                    throw new MATEngineClientException("Error during JSON decode: " + ex.toString());
                }
            }
            JsonNode targetNode = jsonNode.path("target");
            if (!targetNode.isMissingNode()) {
                this.targetFolder = targetNode.getTextValue();
            }
            JsonNode basenameNode = jsonNode.path("basename");
            if (!basenameNode.isMissingNode()) {
                this.basename = basenameNode.getTextValue();
            }
            JsonNode folders = jsonNode.path("affected_folders");
            if (!folders.isMissingNode()) {
                this.affectedFolders = new ArrayList<String>();
                Iterator<JsonNode> nodeIterator = folders.getElements();
                while (nodeIterator.hasNext()) {
                    this.affectedFolders.add(nodeIterator.next().getTextValue());
                }
            }
            // Gonna be using this object for double duty -
            // it will digest the  output of doToplevelWorkspaceOperation
            // as well as the file level.
            JsonNode fileArray = jsonNode.path("files");
            if (!fileArray.isMissingNode()) {
                this.files = new ArrayList<String>();
                Iterator<JsonNode> nodeIterator = fileArray.getElements();
                while (nodeIterator.hasNext()) {
                    this.files.add(nodeIterator.next().getTextValue());
                }
            }

            // If we've gotten this far, this is always true.
            this.workspaceIsOpen = true;

            JsonNode node = jsonNode;

            JsonNode readOnlyNode = node.path("read_only");
            if (!readOnlyNode.isMissingNode()) {
                this.readOnly = readOnlyNode.getBooleanValue();
            }
            JsonNode statusNode = node.path("status");
            if (!statusNode.isMissingNode()) {
                this.status = statusNode.getTextValue();
            }
            JsonNode prioritizationNode = node.path("prioritization_class");
            if (!prioritizationNode.isMissingNode()) {
                this.prioritizationClass = prioritizationNode.getTextValue();
            }
            JsonNode prioritizationModeNode = node.path("prioritization_mode");
            if (!prioritizationModeNode.isMissingNode()) {
                this.prioritizationMode = prioritizationModeNode.getTextValue();
            }
            JsonNode lockIdNode = node.path("lock_id");
            if (!lockIdNode.isMissingNode()) {
                this.lockId = lockIdNode.getTextValue();
            }
            JsonNode recNode = node.path("reconciliation_phase");
            if (!recNode.isMissingNode()) {
                this.reconciliationPhase = recNode.getTextValue();
            }
            JsonNode userArray = node.path("users");
            if (!userArray.isMissingNode()) {
                this.userNames = new ArrayList<String>();
                Iterator<JsonNode> nodeIterator = userArray.getElements();
                while (nodeIterator.hasNext()) {
                    this.userNames.add(nodeIterator.next().getTextValue());
                }
            }
            JsonNode phaseArray = node.path("available_phases");
            if (!phaseArray.isMissingNode()) {
                this.availablePhases = new ArrayList<String>();
                Iterator<JsonNode> nodeIterator = phaseArray.getElements();
                while (nodeIterator.hasNext()) {
                    this.availablePhases.add(nodeIterator.next().getTextValue());
                }
            }
            JsonNode idArray = node.path("segment_ids");
            if ((!idArray.isMissingNode()) && (!idArray.isNull())) {
                this.segmentIDs = new ArrayList<String>();
                Iterator<JsonNode> nodeIterator = idArray.getElements();
                while (nodeIterator.hasNext()) {
                    this.segmentIDs.add(nodeIterator.next().getTextValue());
                }
            }
            // This is now completely different. The result is no longer
            // an array of 2-element arrays of strings, but rather
            // an array of dictionaries. The dictionary is guaranteed to
            // contain a "basename" entry.
            JsonNode basenameInfoArray = node.path("basename_info");
            if (!basenameInfoArray.isMissingNode()) {                
                this.basenameInfo = new ArrayList<HashMap<String,String>>();
                Iterator<JsonNode> nodeIterator = basenameInfoArray.getElements();
                while (nodeIterator.hasNext()) {
                    JsonNode val = nodeIterator.next();
                    HashMap<String,String> v = new HashMap<String,String>();
                    this.basenameInfo.add(v);
                    if (val.isObject()) {
                        // Iterate through the keys, get the string values,
                        // set them.
                        Iterator<String> fields = val.getFieldNames();
                        while (fields.hasNext()) {
                            String field = fields.next();
                            v.put(field, val.get(field).getTextValue());
                        }
                    }                            
                }
            }

        }

        public MATDocument getDocument() {
            return this.doc;
        }

        // I need this because I'm reusing this slot later,
        // and I'm not adding it from the constructor.
        public void setDocument(MATDocument doc) {
            this.doc = doc;
        }

        public ArrayList<String> getAffectedFolders() {
            return this.affectedFolders;
        }

        public String getTargetFolder() {
            return this.targetFolder;
        }

        public String getBasename() {
            return this.basename;
        }

        public ArrayList<String> getFiles() {
            return this.files;
        }

        public String getLockId() {
            return lockId;
        }

        public boolean getReadOnly() {
            return readOnly;
        }

        public String getStatus() {
            return status;
        }

        public String getPrioritizationClass() {
            return prioritizationClass;
        }

        public String getPrioritizationMode() {
            return prioritizationMode;
        }

        public String getReconciliationPhase() {
            return reconciliationPhase;
        }

        public ArrayList<String> getUserNames() {
            return userNames;
        }

        public ArrayList<String> getSegmentIDs() {
            return segmentIDs;
        }

        public ArrayList<String> getAvailablePhases() {
            return availablePhases;
        }

        public ArrayList<HashMap<String,String>> getBasenameInfo() {
            return basenameInfo;
        }

        public void describe() {
            if (this.doc != null) {
                MATJSONEncoding e = new MATJSONEncoding();
                System.out.println("Doc:");
                System.out.println(e.toEncodedString(this.doc));
            }
            if (this.basename != null) {
                System.out.println("Basename: " + this.basename);
            }
            if (this.status != null) {
                System.out.println("Status: " + this.status);
            }
            if (this.targetFolder != null) {
                System.out.println("Target folder: " + this.targetFolder);
            }
            if (this.affectedFolders != null) {
                System.out.println("Affected folders:");
                for (int i = 0; i < this.affectedFolders.size(); i++) {
                    System.out.println(this.affectedFolders.get(i));
                }
            }
            if (this.files != null) {
                System.out.println("Files:");
                for (int i = 0; i < this.files.size(); i++) {
                    System.out.println(this.files.get(i));
                }
            }

            if (this.readOnly) {
                System.out.println("Read-only: true");
            }
            if (this.reconciliationPhase != null) {
                System.out.println("Reconciliation phase: " + this.reconciliationPhase);
            }
            if (this.lockId != null) {
                System.out.println("Lock ID: " + this.lockId);
            }
            if (this.prioritizationClass != null) {
                System.out.println("Prioritization class: " + this.prioritizationClass);
            }
            if (this.prioritizationMode != null) {
                System.out.println("Prioritization mode:" + this.prioritizationMode);
            }

            if (this.userNames != null) {
                System.out.println("Users:");
                for (int i = 0; i < this.userNames.size(); i++) {
                    System.out.println(this.userNames.get(i));
                }
            }
            if (this.segmentIDs != null) {
                System.out.println("Segment IDs:");
                for (int i = 0; i < this.segmentIDs.size(); i++) {
                    System.out.println(this.segmentIDs.get(i));
                }
            }
            if (this.availablePhases != null) {
                System.out.println("Available phases:");
                for (int i = 0; i < this.availablePhases.size(); i++) {
                    System.out.println(this.availablePhases.get(i));
                }
            }
            if (this.basenameInfo != null) {
                System.out.println("Basename info:");
                Iterator it = this.basenameInfo.iterator();

                while (it.hasNext()) {
                    HashMap<String,String> v = (HashMap<String,String>) it.next();
                    boolean first = true;
                    String s = "";
                    Iterator it2 = v.entrySet().iterator();
                    String k = null;
                    while (it2.hasNext()) {
                        Map.Entry subE = (Map.Entry) it2.next();
                        String subK = (String) subE.getKey();
                        String subV = (String) subE.getValue();
                        if (subV != null) {
                            if (subK.equals("basename")) {
                                k = subV;
                                continue;
                            }
                            else {
                                if (!first) {
                                    s = s.concat(", ");
                                } else {
                                    first = false;
                                }
                                s = s.concat(subK + " " + subV);
                            }
                        }
                    }
                    System.out.println(k + " (" + s + ")");
                }
            }
        }
    }

    protected WorkspaceFileResult digestResult(JsonNode jsonValues) 
            throws MATEngineClientException {
        return new WorkspaceFileResult(jsonValues);
    }

    public WorkspaceFileResult doWorkspaceOperation(
            String workspaceDir, String workspaceKey,
            String folder, String operation, String basename)
            throws MATEngineClientException {
        return this.doWorkspaceOperation(workspaceDir, workspaceKey,
                folder, operation, basename, null);
    }

    public WorkspaceFileResult doWorkspaceOperation(
            String workspaceDir, String workspaceKey,
            String folder, String operation, String basename,
            HashMap<String, String> data)
            throws MATEngineClientException {
        ArrayList<NameValuePair> pArray = new ArrayList<NameValuePair>();
        pArray.add(new NameValuePair("workspace_key", workspaceKey));
        pArray.add(new NameValuePair("workspace_dir", workspaceDir));
        pArray.add(new NameValuePair("folder", folder));
        pArray.add(new NameValuePair("ws_operation", operation));
        pArray.add(new NameValuePair("operation", "do_workspace_operation"));
        pArray.add(new NameValuePair("file", basename));

        JsonNode jsonValues = this.postHTTP(pArray, data);

        // The response has a success field. If success is true,
        // there will be some other data about folders that have been
        // affected, etc. I'm not quite interested in that at the moment,
        // since that information is used to update displays, and right
        // now I'm not focusing on that. We can update that later.

        this.checkReturnValueValidity(jsonValues);

        return this.digestResult(jsonValues);
    }

    public WorkspaceFileResult doToplevelWorkspaceOperation(
            String workspaceDir, String workspaceKey,
            String operation, ArrayList<String> args)
            throws MATEngineClientException {
        return this.doToplevelWorkspaceOperation(workspaceDir, workspaceKey,
                operation, args, null);
    }

    public WorkspaceFileResult doToplevelWorkspaceOperation(
            String workspaceDir, String workspaceKey,
            String operation, ArrayList<String> args,
            HashMap<String, String> data)
            throws MATEngineClientException {
        ArrayList<NameValuePair> pArray = new ArrayList<NameValuePair>();
        pArray.add(new NameValuePair("workspace_key", workspaceKey));
        pArray.add(new NameValuePair("workspace_dir", workspaceDir));
        pArray.add(new NameValuePair("ws_operation", operation));
        pArray.add(new NameValuePair("operation", "do_toplevel_workspace_operation"));
        if (args != null) {
            for (int i = 0; i < args.size(); i++) {
                pArray.add(new NameValuePair("arg" + (i + 1), args.get(i)));
            }
        }

        JsonNode jsonValues = this.postHTTP(pArray, data);

        // The response has a success field. If success is true,
        // there will be some other data about folders that have been
        // affected, etc. I'm not quite interested in that at the moment,
        // since that information is used to update displays, and right
        // now I'm not focusing on that. We can update that later.

        this.checkReturnValueValidity(jsonValues);

        return this.digestResult(jsonValues);
    }

    // This is a rare
    public WorkspaceFileResult importFileIntoWorkspace(
            String workspaceDir, String workspaceKey,
            String folder, MATDocumentInterface doc, String basename,
            HashMap<String, String> data) throws MATEngineClientException {
        ArrayList<NameValuePair> pArray = new ArrayList<NameValuePair>();
        MATJSONEncoding e = new MATJSONEncoding();
        pArray.add(new NameValuePair("workspace_key", workspaceKey));
        pArray.add(new NameValuePair("workspace_dir", workspaceDir));
        pArray.add(new NameValuePair("operation", "import_into_workspace"));
        pArray.add(new NameValuePair("folder", folder));
        pArray.add(new NameValuePair("file", basename));
        pArray.add(new NameValuePair("doc", e.toEncodedString(doc)));

        JsonNode jsonValues = this.postHTTP(pArray, data);

        // The response has a success field. If success is true,
        // there will be some other data about folders that have been
        // affected, etc. I'm not quite interested in that at the moment,
        // since that information is used to update displays, and right
        // now I'm not focusing on that. We can update that later.

        this.checkReturnValueValidity(jsonValues);

        return this.digestResult(jsonValues);
    }

    protected JsonNode postHTTP(ArrayList<NameValuePair> pArrayList,
            HashMap<String, String> data) throws MATEngineClientException {

        // Serialize the document, send it to HTTP, deserialize.
        if (data != null) {
            int mapsize = data.size();

            Iterator keyValuePairs1 = data.entrySet().iterator();
            for (int i = 0; i < mapsize; i++) {
                Map.Entry entry = (Map.Entry) keyValuePairs1.next();
                Object key = entry.getKey();
                Object value = entry.getValue();
                pArrayList.add(new NameValuePair((String) key, (String) value));
            }
        }

        NameValuePair[] pArray = (NameValuePair[]) pArrayList.toArray(new NameValuePair[1]);
        HttpClientParams params = new HttpClientParams();
        params.setContentCharset("utf-8");
        HttpClient client = new HttpClient(params);

        PostMethod method = new PostMethod(url);

        method.getParams().setParameter(HttpMethodParams.RETRY_HANDLER,
                new DefaultHttpMethodRetryHandler(0, false));

        method.setRequestBody(pArray);

        String resString = null;

        try {
            // Execute the method.
            int statusCode = client.executeMethod(method);

            if (statusCode != HttpStatus.SC_OK) {
                throw new MATEngineClientException("HTTP method failed: " + method.getStatusLine());
            }
            BufferedReader b = new BufferedReader(new InputStreamReader(method.getResponseBodyAsStream(), "utf-8"));
            StringBuffer buf = new StringBuffer();
            int READ_LEN = 2048;
            char[] cbuf = new char[READ_LEN];

            while (true) {
                int chars = b.read(cbuf, 0, READ_LEN);
                if (chars < 0) {
                    break;
                }
                // You may not read READ_LEN chars, but
                // that doesn't mean you're done.
                buf.append(cbuf, 0, chars);
            }
            resString = new String(buf);
        } catch (HttpException e) {
            throw new MATEngineClientException("Fatal protocol violation: " + e.getMessage());
        } catch (IOException e) {
            throw new MATEngineClientException("Fatal transport error: " + e.getMessage());
        } finally {
            // Release the connection.
            method.releaseConnection();
        }

        JsonNode responseObj = null;
        JsonFactory jsonFact = new JsonFactory();
        JsonNode jsonValues;

        JsonParser parser;
        try {
            parser = jsonFact.createJsonParser(new StringReader(resString));
            return new ObjectMapper().readTree(parser);
        } catch (org.codehaus.jackson.JsonParseException ex) {
            Logger.getLogger(MATCgiClient.class.getName()).log(Level.SEVERE, null, ex);
            throw new MATEngineClientException("Couldn't digest the following string as JSON: " + resString);
        } catch (IOException ex) {
            Logger.getLogger(MATCgiClient.class.getName()).log(Level.SEVERE, null, ex);
            throw new MATEngineClientException("Couldn't interpret response document: " + ex.getMessage());
        }
    }
}
