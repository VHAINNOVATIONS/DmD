/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.StringReader;
import java.io.UnsupportedEncodingException;
import java.io.Writer;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.codehaus.jackson.JsonFactory;
import org.codehaus.jackson.JsonParser;
import org.codehaus.jackson.JsonNode;
import org.codehaus.jackson.map.ObjectMapper;
import org.codehaus.jackson.node.ArrayNode;

/**
 * The object which handles the JSON serialization and deserialization
 * of MAT-compliant documents.
 * 
 * @author sam
 * @author robyn
 */
public class MATJSONEncoding implements MATDocumentEncoding {

    /*
     * READING
     */
    public void fromFile(MATDocumentInterface doc, String fileName)
            throws MATDocumentException {
        try {
            StringBuffer buf = null;

            BufferedReader b = null;
            b = new BufferedReader(
                    new InputStreamReader(new FileInputStream(fileName),
                    "UTF-8"));

            // Read the contents of the file.
            buf = new StringBuffer();
            int READ_LEN = 2048;

            char[] cbuf = new char[READ_LEN];

            while (true) {
                int chars = b.read(cbuf, 0, READ_LEN);
                if (chars < 0) {
                    break;
                }
                buf.append(cbuf, 0, chars);
                if (chars < READ_LEN) {
                    break;
                }
            }
            b.close();
            this.fromEncodedString(doc, new String(buf));
        } catch (IOException ex) {
            throw new MATDocumentException(ex.toString());
        }

    }

    public void fromEncodedString(MATDocumentInterface doc, String jsonData)
            throws MATDocumentException {
        JsonFactory jsonFact = new JsonFactory();
        try {
            JsonParser parser = jsonFact.createJsonParser(new StringReader(jsonData));
            JsonNode jsonValues = new ObjectMapper().readTree(parser);
            this.fromJsonNode(doc, jsonValues);
        } catch (MATDocumentException ex) {
            throw ex;
        } catch (IOException ex) {
            throw new MATDocumentException(ex.toString());
        } catch (AnnotationException ex) {
            ex.printStackTrace();
            throw new MATDocumentException(ex.toString());
        }
    }

    // Additional method to manage decoding from the JSON-RPC protocol
    // and other JSON structures.
    public void fromJsonNode(MATDocumentInterface doc, JsonNode jsonValues)
            throws MATDocumentException, AnnotationException {
        // Right now, we're just going to check the decoding.
        JsonNode verNode = jsonValues.path("version");
        //  The default version is 1, if no version is specified.
        int version = 1;
        if (verNode != null) {
            version = verNode.getIntValue();
        }
        if (version > 2) {
            // I should be throwing something, I know.
            throw new MATDocumentException("MAT JSON version is later than 2");
        }
        doc.setSignal(jsonValues.path("signal").getTextValue());
        JsonNode atypeValues = jsonValues.path("asets");
        // Bookkeeping for the annotation-valued attributes.
        // I need to keep track of a mapping from IDs to annotations,
        // from atypes to their attrIndices and attrTypes, and
        // from annotations to their attribute iterators.
        HashMap<String, AnnotationCore> annotMap = new HashMap<String, AnnotationCore>();
        HashMap<Atype, List<AttributeType>> attrTypeHash = new HashMap<Atype, List<AttributeType>>();
        HashMap<Atype, List<Integer>> attrIndexHash = new HashMap<Atype, List<Integer>>();
        HashMap<AnnotationCore, List<JsonNode>> annotAttrHash = new HashMap<AnnotationCore, List<JsonNode>>();
        if (!atypeValues.isMissingNode()) {
            Iterator<JsonNode> atypeIterator = atypeValues.getElements();
            while (atypeIterator.hasNext()) {
                JsonNode thisAtype = atypeIterator.next();
                String newType = thisAtype.path("type").getTextValue();
                // Try to find out whether it's got an ID or a span.
                boolean hasSpan = true;
                boolean hasID = false;
                JsonNode hasSpanNode = thisAtype.path("hasSpan");
                if (!hasSpanNode.isMissingNode()) {
                    hasSpan = hasSpanNode.getBooleanValue();
                }
                JsonNode hasIDNode = thisAtype.path("hasID");
                if (!hasIDNode.isMissingNode()) {
                    hasID = hasIDNode.getBooleanValue();
                }
                Atype newAtype = doc.findOrAddAtype(newType, hasSpan);
                Iterator<JsonNode> attrListIterator = thisAtype.path("attrs").getElements();
                //List<AttributeType> attrTypes = null;
                List<AttributeType> annotAttrTypes = null;
                List<Integer> attrIndices = null;
                List<Integer> annotAttrIndices = null;
                // Collect the types and the indices, so we can use them
                // to create the annotation later. We have to postpone
                // adding the annotation attributes, because some of theam
                // may be annotations.
                if (attrListIterator.hasNext()) {
                    //attrTypes = new ArrayList<AttributeType>();
                    annotAttrTypes = new ArrayList<AttributeType>();
                    attrIndices = new ArrayList<Integer>();
                    annotAttrIndices = new ArrayList<Integer>();
                }
                while (attrListIterator.hasNext()) {
                    JsonNode elt = attrListIterator.next();
                    int i;
                    if (elt.isTextual()) {
                        i = newAtype.findOrAddAttribute(elt.getTextValue());
                    } else {
                        // It's a hash. The type is string, by default.
                        JsonNode tElt = elt.path("type");
                        String aType = Atype.STRING_ATTR_TYPE;
                        if (!tElt.isMissingNode()) {
                            aType = tElt.getTextValue();
                        }
                        // aggregation is NONE by default
                        int aggregation = AttributeType.NONE_AGGREGATION;
                        JsonNode aElt = elt.path("aggregation");
                        if (!aElt.isMissingNode() && !aElt.isNull()) {
                            aggregation = AttributeType.getAggregationFromString(aElt.getTextValue());
                        }
                        i = newAtype.findOrAddAttribute(elt.path("name").getTextValue(), aType, aggregation);
                    }
                    attrIndices.add(i);
                    AttributeType attrType = newAtype.getAttributeType(i);
                    //attrTypes.add(attrType);
                    if (attrType instanceof AnnotationAttributeType) {
                        annotAttrIndices.add(i);
                        annotAttrTypes.add(attrType);
                    }
                }
                boolean hasAnnotVals = (annotAttrTypes != null) && !annotAttrTypes.isEmpty();
                // Postpone adding the attributes, just in case there
                // are annotation-valued attributes.
                // Now, postpone ONLY the annotation-valued attributes. 7/5/13
                if (hasAnnotVals) {
                    attrTypeHash.put(newAtype, annotAttrTypes);
                    attrIndexHash.put(newAtype, annotAttrIndices);
                }

                Iterator<JsonNode> annotIterator = thisAtype.path("annots").getElements();

                while (annotIterator.hasNext()) {
                    JsonNode annot = annotIterator.next();
                    ArrayList<String> attrVals = new ArrayList<String>();
                    ArrayList<String> annotVals = null;
                    if (hasAnnotVals) {
                        annotVals = new ArrayList<String>();
                    }
                    Iterator<JsonNode> annotValIterator = annot.getElements();  // items in annotations' list
                    AnnotationCore ac;
                    if (hasSpan) {
                        // If there's a span, pick off the first two indices.
                        int startIndex = annotValIterator.next().getIntValue();
                        int endIndex = annotValIterator.next().getIntValue();
                        ac = doc.createAnnotation(newAtype, startIndex, endIndex);
                    } else {
                        ac = doc.createSpanlessAnnotation(newAtype);
                    }
                    if (hasID) {
                        JsonNode idNode = annotValIterator.next();
                        if (!idNode.isNull()) {
                            String id = idNode.getTextValue();
                            ac.setID(id);
                            annotMap.put(id, ac);
                        }
                    }
                    if (attrIndices != null) {
                        Iterator<Integer> it = attrIndices.iterator();
                        List<JsonNode> annotValues = new ArrayList<JsonNode>();
                        while (annotValIterator.hasNext()) {
                            JsonNode valNode = annotValIterator.next();
                            Integer i = it.next();
                            if (annotAttrIndices.contains(i)) {
                                // save it
                                annotValues.add(valNode);
                            } else {
                                setAttributeValueFromNode(valNode, i, ac, annotMap);
                            }
                        }
                        if (!annotValues.isEmpty()) {
                            annotAttrHash.put(ac, annotValues);
                        }
                    }
                }
            }
        } else {
            throw new MATDocumentException("Missing atypeValues");
        }
        // Now that we've created all the annotations, let's add the
        // postponed attributes.
        Iterator<Entry<AnnotationCore, List<JsonNode>>> it = annotAttrHash.entrySet().iterator();
        while (it.hasNext()) {
            Entry<AnnotationCore, List<JsonNode>> e = it.next();
            AnnotationCore ac = e.getKey();
            Iterator<JsonNode> attrIt = e.getValue().iterator();
            // Iterator<AttributeType> attrTypes = attrTypeHash.get(ac.parentAtype).iterator();
            Iterator<Integer> attrIndices = attrIndexHash.get(ac.parentAtype).iterator();
            while (attrIt.hasNext()) {
                JsonNode o = attrIt.next();
                int i = attrIndices.next();
                setAttributeValueFromNode(o, i, ac, annotMap);
            }

        }
        JsonNode newMetaData = jsonValues.path("metadata");
        doc.setMetaData(this.jsonNodeToHashMap(newMetaData));
    }

    private void setAttributeValueFromNode(JsonNode valNode, int i, AnnotationCore ac,
            HashMap<String, AnnotationCore> annotMap) throws AnnotationException, MATDocumentException {
        // if it's an array node, we have a collection
        AttributeType attribType = ac.getParentAtype().getAttributeType(i);
        if (valNode instanceof ArrayNode) {
            // convert the node to an ArrayList, mapping IDs to Annots if needed
            ArrayList valList;
            if (Atype.ANNOTATION_ATTR_TYPE.equals(attribType.getType())) {
                valList = mapAnnots((ArrayList) convertJsonNode(valNode), annotMap);
            } else if (Atype.BOOLEAN_ATTR_TYPE.equals(attribType.getType())) {
                valList = digestValues(attribType, (ArrayList) convertJsonNode(valNode));
            } else {
                valList = (ArrayList) convertJsonNode(valNode);
            }

            // create the correct type of collection for the aggregation type
            AttributeValueCollection coll = null;
            int aggregation = attribType.getAggregationType();
            if (aggregation == AttributeType.LIST_AGGREGATION) {
                coll = new AttributeValueList(valList);
            } else if (aggregation == AttributeType.SET_AGGREGATION) {
                coll = new AttributeValueSet(new HashSet(valList));
            } else {
                throw new AnnotationException("invalid aggregation type for ArrayNode");
            }
            // System.out.println("try to set attribute value type: " + attribType.getType()
            //        + " aggregation: " + aggregation);
            ac.setAttributeValue(i, coll);
            // System.out.println("\t...success");
        } else {
            // for a single value, we always want to pass in a String  
            // which setAttributeValue will convert to the required type 
            // using the AttributeType's digestFromString method
            String val = null;
            try {
                val = this.convertJsonNode(valNode).toString();
            } catch (NullPointerException x) {
                // leave val = null;
            }
            //System.out.println("try to set attribute value " + attribType.getName()
            //        + " type: " + attribType.getType() + " val " + val);
            if (Atype.ANNOTATION_ATTR_TYPE.equals(attribType.getType())) {
                ac.setAttributeValue(i, annotMap.get(val));
            } else {
                ac.setAttributeValue(i, val);
            }
            //System.out.println("\t...success");
        }
    }

    private ArrayList mapAnnots(ArrayList idList, HashMap<String, AnnotationCore> annotMap) {
        ArrayList annotList = new ArrayList(idList.size());
        for (Iterator i = idList.iterator(); i.hasNext();) {
            annotList.add(annotMap.get((String) i.next()));
        }
        return annotList;
    }

    private ArrayList digestValues(AttributeType attrType, ArrayList stringVals) throws AnnotationException {
        ArrayList valsList = new ArrayList(stringVals.size());
        for (Iterator i = stringVals.iterator(); i.hasNext();) {
            valsList.add(attrType.digestSingleValueFromString((String) i.next()));
        }
        return valsList;
    }

    // Ick. 
    private HashMap<String, Object> jsonNodeToHashMap(JsonNode node) {
        HashMap<String, Object> hash = new HashMap<String, Object>();

        if (!node.isMissingNode()) {
            Iterator<String> fieldIterator = node.getFieldNames();
            while (fieldIterator.hasNext()) {
                String field = fieldIterator.next();
                JsonNode subNode = node.get(field);
                hash.put(field, this.convertJsonNode(subNode));
            }
        }
        return hash;
    }

    private Object convertJsonNode(JsonNode subNode) {
        if (subNode.isMissingNode()) {
            return null;
        } else if (subNode.isObject()) {
            return this.jsonNodeToHashMap(subNode);
        } else if (subNode.isArray()) {
            return this.jsonNodeToArrayList(subNode);
        } else if (subNode.isTextual()) {
            return subNode.getTextValue();
        } else if (subNode.isInt()) {
            return subNode.getIntValue();
        } else if (subNode.isDouble()) {
            return subNode.getDoubleValue();
        } else if (subNode.isNumber()) {
            return subNode.getNumberValue();
        } else if (subNode.isNull()) {
            return null;
        } else {
            return subNode.getValueAsText();
        }
    }

    private ArrayList<Object> jsonNodeToArrayList(JsonNode subNode) {
        ArrayList<Object> list = new ArrayList<Object>();
        Iterator<JsonNode> nodeIterator = subNode.getElements();
        while (nodeIterator.hasNext()) {
            list.add(this.convertJsonNode(nodeIterator.next()));
        }
        return list;
    }

    /*
     * WRITING
     */
    public String toEncodedString(MATDocumentInterface doc) {
        // guts moved into method below
        return this.toEncodedString(this.toJsonNode(doc));

    }

    // this is used directly by the unit test, but usually the above method
    // is the one that will be called
    // Map must be of the format returned by toJsonNode
    /**
     * A version of toEncodedString that directly takes a JSON Node. 
     * Generally you should use the version that takes a MATDocument instead.
     * @param node a JSON Node describing the document
     * @return
     * @see #toEncodedString(org.mitre.mat.core.MATDocumentInterface) 
     */
    protected String toEncodedString(Map node) {
        try {
            Writer exportWriter = null;

            ObjectMapper mapper = new ObjectMapper();
            ByteArrayOutputStream b = new ByteArrayOutputStream();
            exportWriter = new OutputStreamWriter(b, "UTF-8");

            exportWriter = new BufferedWriter(exportWriter);

            mapper.writeValue(exportWriter, node);

            exportWriter.close();
            return b.toString("UTF-8");
        } catch (IOException ex) {
            Logger.getLogger(MATJSONEncoding.class.getName()).log(Level.SEVERE, null, ex);
            return null;
        }
    }

    public void toFile(MATDocumentInterface doc, String fileName) {

        Writer exportWriter = null;
        try {
            ObjectMapper mapper = new ObjectMapper();
            exportWriter = new OutputStreamWriter(
                    new FileOutputStream(new File(fileName)),
                    "UTF-8");
            exportWriter = new BufferedWriter(exportWriter);

            mapper.writeValue(exportWriter, this.toJsonNode(doc));

            exportWriter.close();
        } catch (UnsupportedEncodingException ex) {
            Logger.getLogger(MATJSONEncoding.class.getName()).log(Level.SEVERE, null, ex);
        } catch (java.io.IOException ex) {
            Logger.getLogger(MATJSONEncoding.class.getName()).log(Level.SEVERE, null, ex);
        } finally {
            try {
                exportWriter.close();
            } catch (IOException ex) {
                Logger.getLogger(MATJSONEncoding.class.getName()).log(Level.SEVERE, null, ex);
            }
        }
    }
    // Not actually to a JSON node, but to a value that can
    // be mapped. Perhaps fix this later, when I talk to Ben.

    /**
     * Converts a MAT Document into a JSON-node-like value that can be mapped.
     * @param doc
     * @return
     */
    public Map toJsonNode(MATDocumentInterface doc) {
        Map jsonData = new LinkedHashMap();
        jsonData.put("signal", doc.getSignal());
        HashMap<String, Object> mdata = doc.getMetaData();
        if (mdata == null) {
            mdata = new HashMap<String, Object>();
        }
        jsonData.put("metadata", mdata);
        jsonData.put("asets", this.getAtypesAsMaps(doc));
        jsonData.put("version", 2);
        return jsonData;
    }

    // returns a List of the atypes in this AnnotationManager, as Maps
    private List getAtypesAsMaps(MATDocumentInterface doc) {
        HashMap<String, Atype> docAtypes = doc.getDocRepository();
        //System.err.println("AnnotMgr.getAtypesAsMaps: docAtypes=" +
        //        (docAtypes == null ? "null" : docAtypes.toString()));
        if (docAtypes == null) {
            return new ArrayList();
        } else {
            List atypes = new ArrayList();
            for (Iterator i = docAtypes.values().iterator(); i.hasNext();) {
                Atype atype = (Atype) i.next();
                Map mapForm = new LinkedHashMap();
                List<AnnotationCore> annotObjects = doc.getAnnotationsOfType(atype);
                // See if any of the annotations have IDs.
                boolean hasID = false;
                for (Iterator<AnnotationCore> ai = annotObjects.iterator(); ai.hasNext();) {
                    if (ai.next().getID(false) != null) {
                        hasID = true;
                        break;
                    }
                }
                mapForm.put("type", atype.getAtypeType());
                mapForm.put("hasSpan", atype.getHasSpan());
                mapForm.put("hasID", hasID);
                ArrayList attrListForm = new ArrayList();
                List<String> attrs = atype.getAttributeNames();
                for (int j = 0; j < attrs.size(); j++) {
                    String attrtype = atype.getAttributeTypeType(j);
                    AttributeType t = atype.getAttributeType(j);
                    Map attrForm = new LinkedHashMap();
                    attrForm.put("name", attrs.get(j));
                    attrForm.put("type", attrtype);
                    int aggregation = t.getAggregationType();
                    if (aggregation != AttributeType.NONE_AGGREGATION) {
                        attrForm.put("aggregation", AttributeType.aggregationString[aggregation]);
                    }
                    /*** I don't think I really need this -- only the python needs this to write out the task definitions
                    if (t.hasDefault()) {
                    if (t.defaultIsTextSpan) {
                    attrForm.put("default", t.getDefaultValue());
                    } else {
                    attrForm.put("default_is_text_span", true);
                    }
                    }
                     * ***/
                    attrListForm.add(attrForm);
                }
                mapForm.put("attrs", attrListForm);
                mapForm.put("annots", this.getAnnotationsAsArrays(annotObjects, atype.getHasSpan(), hasID));
                atypes.add(mapForm);
            }
            return atypes;
        }
    }

    /* actually returns them as an ArrayList of ArrayLists */
    private List getAnnotationsAsArrays(List<AnnotationCore> annotObjects, boolean hasSpan, boolean hasID) {
        List annotArrays = new ArrayList(annotObjects.size());
        for (Iterator<AnnotationCore> i = annotObjects.iterator(); i.hasNext();) {
            ArrayList listForm = new ArrayList();
            AnnotationCore ac;
            if (hasSpan) {
                Annotation annot = (Annotation) i.next();
                listForm.add(annot.getStartIndex());
                listForm.add(annot.getEndIndex());
                ac = annot;
            } else {
                ac = i.next();
            }
            if (hasID) {
                listForm.add(ac.getID(false));
            }
            Iterator it = ac.getAttributeValues().iterator();
            while (it.hasNext()) {
                Object o = it.next();
                if (o instanceof AnnotationCore) {
                    listForm.add(((AnnotationCore) o).getID(false));
                } else if (o instanceof AttributeValueCollection) {
                    AttributeValueCollection c = (AttributeValueCollection) o;
                    if (c.getType().equals(Atype.ANNOTATION_ATTR_TYPE)) {
                        listForm.add(annotsToIds(c.getCollection()));
                    } else {
                        listForm.add(((AttributeValueCollection) o).getCollection());
                    }
                } else {
                    listForm.add(o);
                }
            }
            annotArrays.add(listForm);
        }
        return annotArrays;
    }

    // takes a collection of annotations and returns a list of the ID of the annotations in the collection
    private List annotsToIds(Collection annotCollection) {
        List idList = new ArrayList(annotCollection.size());
        for (Iterator i = annotCollection.iterator(); i.hasNext();) {
            idList.add(((AnnotationCore) i.next()).getID(false));
        }
        return idList;
    }
}
