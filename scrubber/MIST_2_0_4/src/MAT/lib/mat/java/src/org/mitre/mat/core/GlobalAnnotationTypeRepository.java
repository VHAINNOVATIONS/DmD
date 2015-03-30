/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.io.IOException;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.codehaus.jackson.JsonFactory;
import org.codehaus.jackson.JsonNode;
import org.codehaus.jackson.JsonParser;
import org.codehaus.jackson.map.ObjectMapper;

/**
 * The class that represents the task-level repository of annotations types available.
 * If it is not closed, additional types may be added.  This will usually be 
 * populated using the <code>fromJsonDescriptor</code> method.
 * 
 * @author sam
 * @author robyn
 */
public class GlobalAnnotationTypeRepository extends AnnotationTypeRepository {
    // the primary HashMap maps from trueLabel to atype

    private boolean isClosed;

    /**
     * Constructor for a closed repository.
     */
    public GlobalAnnotationTypeRepository() {
        this.isClosed = true;
    }

    /**
     * Constructor.
     * @param isClosed
     */
    public GlobalAnnotationTypeRepository(boolean isClosed) {
        this.isClosed = isClosed;
    }

    /**
     * 
     * @return
     */
    public boolean isClosed() {
        return isClosed;
    }

    private void close() {
        isClosed = true;
    }

    /**
     * Find the specified annotation type in this global repository and copy it
     * into the document-level repository provided.  If no such type is found,
     * and this repository is not closed, and the <code>create</code> parameter
     * is set to <code>true</true>, then the annotation type will be created
     * and added to both this and the document-level repository.
     * @param label
     * @param docTypeRepository
     * @param hasSpan
     * @param create
     * @return
     * @throws AnnotationException
     * @throws MATDocumentException
     */
    public Atype findAnnotationType(String label, DocumentAnnotationTypeRepository docTypeRepository,
            boolean hasSpan, boolean create) throws AnnotationException, MATDocumentException {
        Atype atype = null;
        atype = this.get(label);
        if (atype != null) {
            if (atype.getHasSpan() != hasSpan) {
                throw new AnnotationException("requesting an annotation type whose hasSpan value doesn't match.");
            }
            atype = atype.maybeCopy(docTypeRepository);
        } else if (!isClosed && create) {
            // it's created without attributes closed, so we need to copy it
            atype = new Atype(this, label, hasSpan);
            this.put(label, atype);
            atype = atype.maybeCopy(docTypeRepository);
        }
        return atype;
    }
    /************** We don't need to handle a list, just a single string

    public void fromJSONDescriptorList(List<String> jsonData) throws MATDocumentException {
        fromJSONDescriptorList(jsonData, false);
    }

    public void fromJSONDescriptorList(List<String> descriptorList, boolean allAnnotationsKnown) throws MATDocumentException {
        // Now, we can hoover through the descriptors, creating all
        // the annotations. We know, at this point, that it's all
        // going to be unique. We also know that the attributes
        // are all defined after the annotations (at least locally).
        // We want to close off attributesKnown AFTER we're
        // done creating the repository.
        for (String jsonString : descriptorList) {
            fromJSONDescriptor(jsonString, allAnnotationsKnown);
        }
    }
     * 
     * Populates this repository from a JSON Descriptor.  See the MAT Developer
     * documentation for details on the required JSON format.
     * 
     * @param descriptor
     * @throws MATDocumentException  
     */
    
    public void fromJSONDescriptor(String descriptor) throws MATDocumentException {
        fromJSONDescriptor(descriptor, false);
    }

    /**
     * Populates this repository from a JSON Descriptor.  See the MAT Developer
     * documentation for details on the required JSON format.
     * 
     * @param descriptor
     * @param allAnnotationsKnown (ignored -- set in the JSON node instead of here)
     * @throws MATDocumentException
     */
    public void fromJSONDescriptor(String descriptor, boolean allAnnotationsKnown) throws MATDocumentException {
        // TODO allAnnotationsKnown is not actually used for anything -- should it be?
        JsonFactory jsonFact = new JsonFactory();
        try {
            JsonParser parser = jsonFact.createJsonParser(new StringReader(descriptor));
            JsonNode jsonValues = new ObjectMapper().readTree(parser);
            this.fromJsonNode(jsonValues);
        } catch (MATDocumentException ex) {
            throw ex;
        } catch (IOException ex) {
            throw new MATDocumentException(ex.toString());
        } catch (AnnotationException ex) {
            ex.printStackTrace();
            throw new MATDocumentException(ex.toString());
        }
    }

    private void fromJsonNode(JsonNode jsonValues) throws MATDocumentException, AnnotationException {
        List labelsToClose = new ArrayList<Atype>();
        Map<AnnotationAttributeType, Set<String>> atomicLabelRestrictions =
                new HashMap<AnnotationAttributeType, Set<String>>();
        Map<AnnotationAttributeType, Set<ComplexRestriction>> complexLabelRestrictions =
                new HashMap<AnnotationAttributeType, Set<ComplexRestriction>>();

        JsonNode repository = jsonValues.path("annotationSetRepository");
        boolean allAnnotationsKnown = repository.path("allAnnotationsKnown").getBooleanValue();
        JsonNode typesNode = repository.path("types");

        if (!typesNode.isMissingNode()) {
            Iterator<String> typeIterator = typesNode.getFieldNames();
            while (typeIterator.hasNext()) {
                String trueLabel = typeIterator.next();
                JsonNode tNode = typesNode.path(trueLabel);
                if (!tNode.isMissingNode()) {
                    Atype newAtype = this.addTypeFromJsonNode(trueLabel, tNode, atomicLabelRestrictions, complexLabelRestrictions);
                    // maybe add to labelsToClose here TODO figure out about closing the labels
                    // if necessary addTypeFromJsonNode can return null if the atype should not be closed
                }
            }
        }
        for (AnnotationAttributeType annotAttr : atomicLabelRestrictions.keySet()) {
            annotAttr.setAtomicLabelRestrictions(atomicLabelRestrictions.get(annotAttr));
        }
        for (AnnotationAttributeType annotAttr : complexLabelRestrictions.keySet()) {
            annotAttr.setComplexLabelRestrictions(complexLabelRestrictions.get(annotAttr));
        }

        if (allAnnotationsKnown) {
            this.close();
        }
    }

    // need to pass in the maps of label restrictions to be added to, and then 
    // eventually implemented in fromJsonNode after all Atypes are added
    private Atype addTypeFromJsonNode(String trueLabel, JsonNode tNode,
            Map<AnnotationAttributeType, Set<String>> atomicLabelRestrictions,
            Map<AnnotationAttributeType, Set<ComplexRestriction>> complexLabelRestrictions)
            throws MATDocumentException, AnnotationException {
        JsonNode hasSpanNode = tNode.path("hasSpan");
        boolean hasSpan = true;
        if (!hasSpanNode.isMissingNode()) {
            hasSpan = hasSpanNode.getBooleanValue();
        }
        Atype atype = new Atype(this, trueLabel, hasSpan); // creates it for this global repository
        this.put(trueLabel, atype); // adds it to this global repository
        JsonNode attrsNode = tNode.path("attrs");
        if (!attrsNode.isMissingNode()) {
            Iterator<JsonNode> attrIterator = attrsNode.getElements();
            while (attrIterator.hasNext()) {
                JsonNode attrNode = attrIterator.next();
                // get name
                String attrName = attrNode.path("name").getTextValue();
                // get type
                String attrType = attrNode.path("type").getTextValue();
                if (attrType == null) { // default to "string"
                    attrType = "string";
                }
                // get aggregation
                String attrAggregation = attrNode.path("aggregation").getTextValue();
                int aggregation = AttributeType.NONE_AGGREGATION;
                if (attrAggregation != null) {
                    if (attrAggregation.equals("list")) {
                        aggregation = AttributeType.LIST_AGGREGATION;
                    } else if (attrAggregation.equals("set")) {
                        aggregation = AttributeType.SET_AGGREGATION;
                    }
                }
                // get default
                String attrDefaultVal = attrNode.path("default").getTextValue();
                // get defaultIsTextSpan
                boolean defaultIsTextSpan = attrNode.path("default_is_text_span").getBooleanValue();
                // Setup restrictions Map TODO
                Map restMap = new HashMap();
                // collect choices (which might be strings or ints
                JsonNode choices = attrNode.path("choices");
                if (!choices.isMissingNode()) {
                    Iterator<JsonNode> choiceIter = choices.getElements();
                    if (attrType.equals("string")) {
                        List<String> choiceList = new ArrayList<String>();
                        while (choiceIter.hasNext()) {
                            choiceList.add(choiceIter.next().getTextValue());
                        }
                        restMap.put("choices", choiceList);
                    } else if (attrType.equals("int")) {
                        List<Integer> choiceList = new ArrayList<Integer>();
                        while (choiceIter.hasNext()) {
                            JsonNode choiceNode = choiceIter.next();
                            Integer val;
                            if (choiceNode.isInt()) {
                                val = Integer.valueOf(choiceNode.getIntValue());
                            } else if (choiceNode.isTextual()) {
                                val = Integer.parseInt(choiceNode.getTextValue());
                            } else {
                                throw new AnnotationException("invalid non-integer choice for int attribute");
                            }
                            choiceList.add(val);
                        }
                        restMap.put("choices", choiceList);
                    }
                }
                // get minval & maxval
                Number minval = attrNode.path("minval").getNumberValue();
                if (minval != null) {
                    restMap.put("minval", minval);
                }
                Number maxval = attrNode.path("maxval").getNumberValue();
                if (maxval != null) {
                    restMap.put("maxval", maxval);
                }
                // create the attribute
                //    public int findOrAddAttribute(String attrName, String attrtype, int aggregation,
                //    Map restrictions, Object defaultValue, boolean defaultIsTextSpan)
                int attrNum = atype.findOrAddAttribute(attrName, attrType, aggregation, restMap, attrDefaultVal, defaultIsTextSpan);
                // get label restrictions (if present), if we're doing an annotation type
                if (attrType.equals("annotation")) {
                    JsonNode labelRestNode = attrNode.path("label_restrictions");
                    if (labelRestNode.isMissingNode()) {
                        throw new AnnotationException("annotation-valued attribute requires at least one label restriction");
                    } else {
                        Set<String> atomicRestrictions = new HashSet<String>();
                        Set<ComplexRestriction> complexRestrictions = new HashSet<ComplexRestriction>();
                        Iterator<JsonNode> restIter = labelRestNode.getElements();
                        while (restIter.hasNext()) {
                            JsonNode restNode = restIter.next();
                            if (restNode.isTextual()) {
                                atomicRestrictions.add(restNode.getTextValue());
                            } else {
                                Map<String, Object> attrValRests = new HashMap<String, Object>();
                                String trueLabelRest = restNode.get(0).getTextValue();
                                JsonNode restPairsList = restNode.get(1);
                                for (int i = 0; i < restPairsList.size(); i++) {
                                    String attr = restPairsList.get(i).get(0).getTextValue();
                                    JsonNode valNode = restPairsList.get(i).get(1);
                                    Object val = null;
                                    // val must be chosen from among the choices, 
                                    // so it must be a String or an int
                                    if (valNode.isTextual()) {
                                        val = valNode.getTextValue();
                                    } else if (valNode.isInt()) {
                                        val = valNode.getIntValue();
                                    } else {
                                        throw new AnnotationException("complex restriction value must be a String or an int");
                                    }
                                    attrValRests.put(attr, val);
                                }
                                complexRestrictions.add(new ComplexRestriction(trueLabelRest, attrValRests));
                            }
                        }
                        AnnotationAttributeType annotAttrType = (AnnotationAttributeType) atype.getAttributeType(attrNum);
                        // Is there a chicken and egg problem here? -- cannot validate restrictions until all the types are in the repository
                        // yes, must save these to set later
                        //annotAttrType.setAtomicLabelRestrictions(atomicRestrictions);
                        //annotAttrType.setComplexLabelRestrictions(complexRestrictions); 
                        atomicLabelRestrictions.put(annotAttrType, atomicRestrictions);
                        complexLabelRestrictions.put(annotAttrType, complexRestrictions);

                    }
                }
            }
        }
        return atype;
    }
    /*** Not needed (yet?)
    
    private HashMap<String, TrueInfo> effectiveLabelToTrueInfo = new HashMap<String, TrueInfo>();
    private HashMap<String, HashMap<TrueInfo, String>> trueLabelToEffectiveLabels = 
    new HashMap<String, HashMap<TrueInfo, String>>();
    
    public void declareEffectiveLabel(String ename, String trueLabel,
    String attr, Object val) throws AnnotationException {
    Object tval;
    if (val == null) {
    throw new AnnotationException("attempt to declare effective label "
    + ename + " with null attribute value");
    }
    if (!this.containsKey(attr)) {
    throw new AnnotationException("attempt to declare effective label "
    + ename + " which refers to a truel label " + trueLabel
    + " which hasn't been defined.");
    
    }
    Atype atype = this.get(attr);
    int k = atype.getAttributeIndex(attr);
    if (k < 0) {
    throw new AnnotationException("attempt to declare an effective label "
    + ename + " which refers to an attribute " + attr
    + " which hasn't been defined for true label " + trueLabel);
    }
    AttributeType attrObj = atype.getAttributeType(k);
    if (attrObj.getAggregationType() != AttributeType.NONE) {
    throw new AnnotationException("attempt to declare an effective label "
    + ename + " which refers to a non-singleton attribute " + attr);
    }
    if (val instanceof String) {
    tval = attrObj.digestSingleValueFromString((String) val);
    if (tval == null) {
    throw new AnnotationException("unable to digest value " + val
    + " into required type: " + attrObj.getType());
    }
    if (!attrObj.checkSingleValue(tval)) {
    throw new AnnotationException("value: " + val
    + "is not a valid value for attribute " + attr
    + " of label " + trueLabel + " for effective label "
    + ename);
    }
    }
    // make sure of this:
    attrObj.setDistinguishingAttrForEquality(true);
    
    // finally, record the settings
    TrueInfo info = new TrueInfo(trueLabel, attrObj, val);
    this.effectiveLabelToTrueInfo.put(ename, info);
    HashMap<TrueInfo, String> trueInfoToEffectiveLabelMap =
    this.trueLabelToEffectiveLabels.get(trueLabel);
    if (trueInfoToEffectiveLabelMap == null) {
    trueInfoToEffectiveLabelMap = new HashMap<TrueInfo, String>();
    this.trueLabelToEffectiveLabels.put(trueLabel, trueInfoToEffectiveLabelMap);
    }
    trueInfoToEffectiveLabelMap.put(info, ename);
    }
    
    
    public String getEffectiveAnnotationLabel(AnnotationCore annot) {
    return getEffectiveAnnotationLabel(annot, false, null);
    }
    
    public String getEffectiveAnnotationLabel(AnnotationCore annot,
    boolean useExtraDistinguishingAttrs, Set restrictToAnnotationSetNames) {
    String trueLabel = annot.getParentAtype().getLabel();
    if (!this.containsKey(trueLabel)) {
    // Sam says: If there's no entry in the tag cache, just use this label. 
    // Actually, this should probably be an error.
    return trueLabel;
    }
    String eLabel = trueLabel;
    AttributeType distAttr = null;
    HashMap<TrueInfo, String> trueInfoToEffectiveLabelMap =
    this.trueLabelToEffectiveLabels.get(trueLabel);
    for (Iterator<Map.Entry<TrueInfo,String>> it = trueInfoToEffectiveLabelMap.entrySet().iterator(); it.hasNext(); ) {
    Map.Entry<TrueInfo,String> entry = it.next();
    TrueInfo info = entry.getKey();
    String ename = entry.getValue();
    String attrName = info.getAttrType().getName();
    Object value = info.getValue();
    // TODO some stuff about restrictToAnnotationSetNames
    if (annot.getAttributeValue(attrName).equals(value)) {
    eLabel = ename;
    if (useExtraDistinguishingAttrs) {
    distAttr = info.getAttrType();
    }
    break;
    }
    }
    // TODO some stuff about distinguishing attributes
    
    return eLabel;
    }
    
    
    
    private class TrueInfo {
    
    String trueLabel;
    AttributeType attrType;
    Object value;
    
    public TrueInfo(String trueLabel, AttributeType attrType, Object value) {
    this.trueLabel = trueLabel;
    this.attrType = attrType;
    this.value = value;
    }
    
    public AttributeType getAttrType() {
    return attrType;
    }
    
    public String getTrueLabel() {
    return trueLabel;
    }
    
    public Object getValue() {
    return value;
    }
    }
     * ***/
}
