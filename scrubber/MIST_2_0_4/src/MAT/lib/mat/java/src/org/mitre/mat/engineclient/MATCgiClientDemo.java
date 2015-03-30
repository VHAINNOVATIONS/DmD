/*
 * Copyright (C) 2009 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.engineclient;

import java.io.*;
import java.util.ArrayList;
import java.util.HashMap;
import org.mitre.mat.core.*;

/**
 *
 * @author sam
 */
public class MATCgiClientDemo {

    /**
     * @param args the command line arguments
     */
    private static void Usage() {
        System.err.println("Usage: MATCgiClientDemo url 'file' [ --attr val ]* json_input json_output task workflow");
        System.err.println("       MATCgiClientDemo url 'workspace_file' [ --attr val ]* workspace workspace_key operation folder basename");
        System.err.println("       MATCgiClientDemo url 'workspace' [ --attr val ]* workspace workspace_key operation arg...");
        System.err.println("          If operation is 'import_file', arg 2 should be a full path to import into the workspace,");
        System.err.println("          and arg 1 should be the folder to import it into.");
        System.exit(1);
    }

    public static void main(String[] args) {

        if (args.length < 2) {
            Usage();
        }

        // Several different use cases, differentiated by the arguments.
        // First two arguments are the url and use type.

        String url = args[0];
        String useType = args[1];

        int i = 2;
        HashMap<String, String> attrMap = null;
        while (i < (args.length - 1) && args[i].startsWith("--")) {
            if (attrMap == null) {
                attrMap = new HashMap<String, String>();
            }
            attrMap.put(args[i].substring(2), args[i + 1]);
            i += 2;
        }

        if (i == args.length) {
            Usage();
        }

        if (useType.equals("file")) {
            fileMain(url, args, i, attrMap);
        } else if (useType.equals("workspace_file")) {
            workspaceFileMain(url, args, i, attrMap);
        } else if (useType.equals("workspace")) {
            workspaceToplevelMain(url, args, i, attrMap);
        } else {
            System.err.println("Unknown use type " + useType + ".");
            Usage();
        }
    }

    private static void fileMain(String url, String[] args, int i, HashMap<String, String> attrMap) {
        // We need 4 args beyond what we have.
        if (args.length - i != 4) {
            System.err.println("Wrong number of args for file use type.");
            Usage();
        }
        String infile = args[i];
        String outfile = args[i + 1];
        String task = args[i + 2];
        String workflow = args[i + 3];

        // Look for steps or undo_through. Can only do one or the other
        // from the client.
        boolean hasSteps = attrMap.containsKey("steps");
        boolean hasUndoThrough = attrMap.containsKey("undo_through");

        if (hasSteps && hasUndoThrough) {
            System.err.println("Can't perform both steps and undo_through simultaneously.");
            Usage();
        } else if (!(hasSteps || hasUndoThrough)) {
            System.err.println("Must provide either steps or undo_through as attr key-value pair");
            Usage();
        }

        MATDocument doc = new MATDocument();
        MATJSONEncoding e = new MATJSONEncoding();
        try {
            e.fromFile(doc, infile);
        } catch (MATDocumentException ex) {
            System.err.println("Couldn't read file " + infile + " :" + ex.toString());
            System.exit(1);
        }

        MATCgiClient client = new MATCgiClient(url);
        try {
            MATDocument resultDoc = null;
            if (hasSteps) {
                String steps = attrMap.get("steps");
                attrMap.remove("steps");
                resultDoc = (MATDocument) client.doSteps(doc, task, workflow, steps, attrMap);
            } else {
                String undoThrough = attrMap.get("undo_through");
                attrMap.remove("undo_through");
                resultDoc = (MATDocument) client.doUndoThrough(doc, task, workflow, undoThrough, attrMap);
            }
            e.toFile(resultDoc, outfile);
        } catch (MATEngineClientException ex) {
            System.err.println("Processing failed: " + ex.getMessage());
            System.exit(1);
        }
    }

    private static void workspaceToplevelMain(String url, String[] args, int i, HashMap<String, String> attrMap) {
        // We need at least 3 args beyond what we have.
        if (args.length - i < 3) {
            System.err.println("Wrong number of args for file use type.");
            Usage();
        }
        String workspace = args[i];
        String workspaceKey = args[i + 1];
        String operation = args[i + 2];
        i += 3;
        ArrayList <String> opArgs = new ArrayList<String>();
        while (i < args.length) {
            opArgs.add(args[i]);
            i += 1;
        }

        MATCgiClient client = new MATCgiClient(url);
        MATCgiClient.WorkspaceFileResult res = null;

        try {
            if (operation.equals("import_file")) {
                MATDocument doc = new MATDocument();
                MATJSONEncoding e = new MATJSONEncoding();
                if (opArgs.size() != 2) {
                    System.err.println("Wrong number of arguments for import_file.");
                    Usage();
                }
                String folder = opArgs.get(0);
                String basename = opArgs.get(1);
                try {
                    e.fromFile(doc, basename);
                } catch (MATDocumentException ex) {
                    System.err.println("Couldn't read file " + basename + " :" + ex.toString());
                    System.exit(1);
                }
                res = client.importFileIntoWorkspace(workspace,
                        workspaceKey, folder, doc,
                        new File(basename).getName(), attrMap);
            } else {
                res = client.doToplevelWorkspaceOperation(workspace,
                        workspaceKey, operation, opArgs, attrMap);
            }
            System.out.println("Operation '" + operation + "' succeeded.");
            res.describe();
            System.exit(0);
        } catch (MATEngineClientException ex) {
            System.err.println("Processing failed: " + ex.getMessage());
            System.exit(1);
        }
    }

    private static void workspaceFileMain(String url, String[] args, int i, HashMap<String, String> attrMap) {
        // We need 5 args beyond what we have.
        if (args.length - i != 5) {
            System.err.println("Wrong number of args for file use type.");
            Usage();
        }
        String workspace = args[i];
        String workspaceKey = args[i + 1];
        String operation = args[i + 2];
        String folder = args[i + 3];
        String basename = args[i + 4];

        MATCgiClient client = new MATCgiClient(url);
        MATCgiClient.WorkspaceFileResult res = null;

        try {
            res = client.doWorkspaceOperation(workspace,
                    workspaceKey, folder, operation, basename, attrMap);

            System.out.println("Operation '" + operation + "' succeeded for '" + basename + "' into folder '" + res.getTargetFolder() + "'.");
            res.describe();
            System.exit(0);
        } catch (MATEngineClientException ex) {
            System.err.println("Processing failed: " + ex.getMessage());
            System.exit(1);
        }
    }
}
