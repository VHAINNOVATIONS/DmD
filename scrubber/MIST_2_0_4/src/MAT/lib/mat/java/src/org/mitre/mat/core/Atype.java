/*
 * Copyright (C) 2009, 2010 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.HashMap;
import java.util.Iterator;
import java.util.ListIterator;
import java.util.Map;

/**
 * A type of annotations, containing a label and a set of attributes
 * for each annotation.
 *
 * These types are used both within documents and within a task.  They
 * can only point back to the repository, which will differ between
 * documents and tasks. You should NEVER expect the atype to be able
 * to reach back into a document.  The same atype can be used in multiple
 * documents if it implements a type defined in the GlobalAnnotationTypeRepository.
 *
 * @author sam
 * @author robyn
 */
public class Atype {

    private String label = "";
    // tells us which repository this Atype is a part of
    // since the Atype is modifiable unless closed, we must
    // have a separate copy for each repository.
    // this could be a global or local repository
    // if the Atype is closed, this will point back to the 
    // global repository but will also be referenced by 
    // local repositories as needed
    private AnnotationTypeRepository repository;
    // list of all the attributes
    private List<AttributeType> attributes = null;
    // hash from attribute name to its index
    private HashMap<String, Integer> attrHash = null;
    private int curAttrHashIndex = 0; // saves us from having to check the length of the list every time
    private boolean hasSpan = true;
    private boolean hasAnnotationAttribute = false;
    private boolean isClosed = false;
    private boolean hasDefaults = false;
    public static final String STRING_ATTR_TYPE = "string";
    public static final String INT_ATTR_TYPE = "int";
    public static final String FLOAT_ATTR_TYPE = "float";
    public static final String BOOLEAN_ATTR_TYPE = "boolean";
    public static final String ANNOTATION_ATTR_TYPE = "annotation";
    // might not need this if I don't want to try to get fancy with reflection ;-)
    private static final Map<String, Class> ATTR_TYPES;

    static {
        Map<String, Class> aMap = new HashMap<String, Class>();
        aMap.put(STRING_ATTR_TYPE, StringAttributeType.class);
        aMap.put(INT_ATTR_TYPE, IntAttributeType.class);
        aMap.put(FLOAT_ATTR_TYPE, FloatAttributeType.class);
        aMap.put(BOOLEAN_ATTR_TYPE, BooleanAttributeType.class);
        aMap.put(ANNOTATION_ATTR_TYPE, AnnotationAttributeType.class);
        ATTR_TYPES = Collections.unmodifiableMap(aMap);
    }

    /**
     *  Creates an Atype 
     *  
     * @param repository the AnnotationTypeRepository (may be global or local)
     *                   to which thie new Atype will be added
     * @param atypeLabel
     * @param hasSpan 
     * @param attrList 
     * @throws MATDocumentException 
     * @throws AnnotationException  
     */
    public Atype(AnnotationTypeRepository repository,
            String atypeLabel, List<String> attrList, boolean hasSpan)
            throws MATDocumentException, AnnotationException {

        this.repository = repository;
        this.label = atypeLabel;
        this.hasSpan = hasSpan;
        if (attrList != null) {
            this.addAttributes(attrList);
        } else {
            // The spec requires attributes to be a list, never null.
            this.initAttributes();
        }
//        this.annotObjects = new java.util.ArrayList();
    }

    /**
     *  Creates an Atype 
     * 
     * @param repository
     * @param atypeLabel
     * @param attrList
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Atype(AnnotationTypeRepository repository, String atypeLabel, List<String> attrList) throws MATDocumentException, AnnotationException {
        this(repository, atypeLabel, attrList, true);
    }

    /**
     *  Creates an Atype 
     * 
     * @param repository
     * @param atypeLabel
     * @param hasSpan
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Atype(AnnotationTypeRepository repository, String atypeLabel, boolean hasSpan) throws MATDocumentException, AnnotationException {
        this(repository, atypeLabel, null, hasSpan);
    }

    /**
     *  Creates an Atype 
     * 
     * @param repository
     * @param atypeLabel
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Atype(AnnotationTypeRepository repository, String atypeLabel) throws MATDocumentException, AnnotationException {
        this(repository, atypeLabel, null, true);
    }

    /**
     * Check whether or not there are at least n attributes, and if not
     * throw an exception
     * @param n
     * @throws AnnotationException if there are not enough attributes
     */
    public void ensureAttributeNumber(int n) throws AnnotationException {
        if (n == 0 || n <= curAttrHashIndex) {
            return;
        }

        // there aren't enough attributes
        throw new AnnotationException("Annotation type " + label
                + " has fewer than " + n + " attributes.");
    }

    private void initAttributes() {
        this.attributes = new ArrayList<AttributeType>();
        this.attrHash = new HashMap<String, Integer>();
    }

    // Use this method to add basic String attributes which don't have any
    // special types.
    private void addAttributes(List<String> attrList) throws MATDocumentException, AnnotationException {
        Iterator<String> it = attrList.iterator();
        while (it.hasNext()) {
            String attr = it.next();
            this.findOrAddAttribute(attr, STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, false);
        }
    }

    /**
     * Finds the index of the specified attribute in this Atype, or adds it.
     * @param attr the name of the attribute
     * @return the index of the specified attribute
     * @throws AnnotationException
     * @throws MATDocumentException
     */
    public int findOrAddAttribute(String attr) throws AnnotationException, MATDocumentException {
        return this.findOrAddAttribute(attr, STRING_ATTR_TYPE, AttributeType.NONE_AGGREGATION, null, null, false);
    }

    /**
     * Finds the index of the specified attribute in this Atype, or adds it.
     * @param attr the name of the attribute
     * @param attrtype
     * @return the index of the specified attribute
     * @throws AnnotationException
     * @throws MATDocumentException
     */
    public int findOrAddAttribute(String attr, String attrtype) throws AnnotationException, MATDocumentException {
        return this.findOrAddAttribute(attr, attrtype, AttributeType.NONE_AGGREGATION, null, null, false);
    }

    /**
     * Finds the index of the specified attribute in this Atype, or adds it.
     * @param attrName
     * @param attrtype
     * @param aggregation
     * @return the index of the specified attribute
     * @throws AnnotationException
     * @throws MATDocumentException
     */
    public int findOrAddAttribute(String attrName, String attrtype, int aggregation) throws AnnotationException, MATDocumentException {
        return this.findOrAddAttribute(attrName, attrtype, aggregation, null, null, false);
    }

    /**
     * Finds the index of the specified attribute in this Atype, or adds it.
     * @param attrName
     * @param attrtype
     * @param aggregation
     * @param restrictions
     * @return the index of the specified attribute
     * @throws AnnotationException
     * @throws MATDocumentException
     */
    public int findOrAddAttribute(String attrName, String attrtype, int aggregation, Map restrictions)
            throws AnnotationException, MATDocumentException {
        return this.findOrAddAttribute(attrName, attrtype, aggregation, restrictions, null, false);
    }

    // this actually does the find or add
    /**
     * Finds the index of the specified attribute in this Atype, or adds it.
     * @param attrName
     * @param attrtype
     * @param aggregation
     * @param restrictions
     * @param defaultValue
     * @param defaultIsTextSpan
     * @return the index of the specified attribute
     * @throws AnnotationException
     * @throws MATDocumentException
     */
    public int findOrAddAttribute(String attrName, String attrtype, int aggregation,
            Map restrictions, Object defaultValue, boolean defaultIsTextSpan)
            throws AnnotationException, MATDocumentException {
        if (isClosed) {
            throw new AnnotationException("Annotation type " + this.label + " no longer permits attributes to be added.");
        }

        if (this.attributes == null) {
            this.initAttributes();
        }

        int i;
        // Don't add keys more than once.
        if (this.attrHash.containsKey(attrName)) {
            i = this.attrHash.get(attrName);
            if (!this.attributes.get(i).getType().equals(attrtype)) {
                throw new MATDocumentException("attribute already defined, but types don't match");
            }
            if (this.attributes.get(i).getAggregationType() != aggregation) {
                throw new MATDocumentException("attribute already defined, but aggregation types don't match");
            }
        } else {
            AttributeType attrType;
            // I could try to get fancy and use reflection here, but I won't
            if (attrtype.equals(STRING_ATTR_TYPE)) {
                attrType = new StringAttributeType(this, attrName, null, false,
                        aggregation, false, (String) defaultValue, defaultIsTextSpan);
            } else if (attrtype.equals(INT_ATTR_TYPE)) {
                attrType = new IntAttributeType(this, attrName, null, null, null,
                        false, aggregation, false, (Integer) defaultValue, defaultIsTextSpan);
            } else if (attrtype.equals(FLOAT_ATTR_TYPE)) {
                attrType = new FloatAttributeType(this, attrName, null, null, false,
                        aggregation, false, (Float) defaultValue, defaultIsTextSpan);
            } else if (attrtype.equals(BOOLEAN_ATTR_TYPE)) {
                if (defaultIsTextSpan) {
                    throw new AnnotationException("Boolean attribute cannot use text span as default");
                }
                attrType = new BooleanAttributeType(this, attrName, false,
                        aggregation, false, (Boolean) defaultValue);
            } else if (attrtype.equals(ANNOTATION_ATTR_TYPE)) {
                if (defaultIsTextSpan || defaultValue != null) {
                    throw new AnnotationException("Annotation attribute cannot specify default");
                }
                attrType = new AnnotationAttributeType(this, attrName, aggregation);
                this.hasAnnotationAttribute = true;
            } else {
                throw new MATDocumentException("attribute type is not one of the recognized types");
            }
            if (restrictions != null) {
                attrType.addRestrictions(restrictions);
            }
            this.attributes.add(attrType);
            if (attrType.hasDefault()) {
                this.hasDefaults = true;
            }
            this.attrHash.put(attrName, curAttrHashIndex);
            i = curAttrHashIndex;
            curAttrHashIndex += 1;

        }
        return i;
    }

    // allows one to use any of the fancy attribute constructors if needed
    /**
     * Adds an attribute
     * @param attrType
     * @return the index of the new attribute
     */
    public int addAttribute(AttributeType attrType) {
        this.attributes.add(attrType);
        if (attrType.hasDefault()) {
            this.hasDefaults = true;
        }
        this.attrHash.put(attrType.getName(), curAttrHashIndex);
        int i = curAttrHashIndex;
        curAttrHashIndex += 1;
        return i;
    }

    /**
     * 
     * @return the List of attributes for this Atype
     */
    public List<AttributeType> getAttributes() {
        return new ArrayList<AttributeType>(this.attributes);
    }

    /**
     * 
     * @param i
     * @return the name of the ith attribute
     */
    public String getAttributeName(int i) {
        try {
            ensureAttributeNumber(i);
        } catch (AnnotationException x) {
            return null;
        }
        return this.attributes.get(i).getName();
    }

    /**
     * 
     * @param i
     * @return the ith attribute
     */
    public AttributeType getAttributeType(int i) {
        try {
            ensureAttributeNumber(i);
        } catch (AnnotationException x) {
            return null;
        }
        return this.attributes.get(i);
    }

    /**
     * 
     * @param i
     * @return the type of the ith attribute
     */
    public String getAttributeTypeType(int i) {
        try {
            ensureAttributeNumber(i);
        } catch (AnnotationException x) {
            return null;
        }
        return this.attributes.get(i).getType();
    }

    List<String> getAttributeNames() {
        List theList = new ArrayList(this.attributes.size());
        for (ListIterator<AttributeType> it = this.attributes.listIterator(); it.hasNext();) {
            theList.add(it.next().getName());
        }
        return theList;
    }

    /**
     * Find the index of an attribute specified by name
     * @param attr
     * @return the index of the specified attribute, if it exists, or -1 if it does not
     */
    public int getAttributeIndex(String attr) {
        if (this.attrHash == null) {
            return -1;
        } else if (this.attrHash.containsKey(attr)) {
            return this.attrHash.get(attr);
        } else {
            return -1;
        }
    }

    /**
     * Find the attribute with the specified name
     * @param attrName
     * @return the attribute with the specified name
     */
    public AttributeType getAttributeType(String attrName) {
        return this.getAttributeType(this.getAttributeIndex(attrName));
    }

    /**
     * Get the AnnotationTypeRepository to which this Atype belongs.  This may
     * be either a GlobalAnnotationTypeRepository or a 
     * DocumentAnnotationTypeRepository (local).
     * @return the AnnotationTypeRepository to which this Atype belongs
     */
    public AnnotationTypeRepository getRepository() {
        return repository;
    }
    
    

    /**
     * Checks that the list of aVals has attribute values of the correct
     * types and also that they're valid values for their corresponding AttributeTypes
     * @param aVals
     * @throws AnnotationException
     */
    public void checkAttributeValues(List aVals) throws AnnotationException {
        // Using an iterator because we need to iterate across the types.
        int aValLen = aVals.size();
        if (aValLen > this.attributes.size()) {
            throw new AnnotationException("more attribute values than attributes");
        }
        for (int i = 0; i < aValLen; i++) {
            AttributeType attrType = this.attributes.get(i);
            Object value = aVals.get(i);
            if (attrType instanceof StringAttributeType) {
                if (!(value instanceof String)) {
                    throw new AnnotationException("attribute value must be a string");
                }
            } else if (attrType instanceof AnnotationAttributeType) {
                if (!(value instanceof AnnotationCore)) {
                    throw new AnnotationException("attribute value must be an annotation");
                }

            } else if (attrType instanceof IntAttributeType) {
                if (!(value instanceof Integer)) {
                    throw new AnnotationException("attribute value must be an integer");
                }

            } else if (attrType instanceof FloatAttributeType) {
                if (!(value instanceof Float)) {
                    throw new AnnotationException("attribute value must be a float");
                }

            } else if (attrType instanceof BooleanAttributeType) {
                if (!(value instanceof AnnotationCore)) {
                    throw new AnnotationException("attribute value must be a boolean");
                }
            }
            if (!attrType.checkValue(value)) {
                throw new AnnotationException("attribute value must be a " + attrType.getType()
                        + " and meet other requirements.");
            }
        }
    }

    /**
     * alternate name for getLabel() for backward compatibility
     * @return
     */
    public String getAtypeType() {
        return getLabel();
    }

    /**
     * 
     * @return this Atype's label 
     */
    public String getLabel() {
        return this.label;
    }

    /*** Atype does not store annotations anymore
    public List<AnnotationCore> getAnnotations() {
    return this.annotObjects;
    } */
    /**
     * @return whether this type of annotation has a span or not
     */
    public boolean getHasSpan() {
        return hasSpan;
    }

    /**
     * duplicate of getHasSpan that makes the code read better
     * @return
     */
    public boolean hasSpan() {
        return getHasSpan();
    }

    /**
     * Closes the annotation so that no more attributes can be added.
     */
    public void close() {
        isClosed = true;
    }

    boolean hasAnnotationAttribute() {
        return this.hasAnnotationAttribute;
    }

    /**
     * 
     * @return true if this Atype has any attributes with defaults, false otherwise.
     */
    public boolean hasDefaults() {
        return hasDefaults;
    }

    boolean checkAttributeTypeAtIndex(int index, String attrType) {
        if (this.attributes == null) {
            return false;
        }
        if (this.attributes.size() <= index) {
            return false;
        }
        return this.attributes.get(index).getType().equals(attrType);
    }

    /**
     * Copy this Atype to another repository if necessary.
     * We only need to copy it from document to document, or from global
     * to local repository, if it's not closed. If the target repository
     * is the same as the source, and it's closed, leave it. Otherwise, copy.
     * 
     * @param targetRepository
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Atype maybeCopy(DocumentAnnotationTypeRepository targetRepository) throws MATDocumentException, AnnotationException {
        if (isClosed && ((repository instanceof GlobalAnnotationTypeRepository) || repository.equals(targetRepository))) {
            return this;
        } else {
            return this.copy(targetRepository);
        }
    }
    
    // closed is always False for the copy (that is the default so we don't have to explicitly set it)
    private Atype copy(DocumentAnnotationTypeRepository targetRepository) throws MATDocumentException, AnnotationException {
        Atype newA = new Atype(targetRepository, this.label, this.hasSpan);
        // create a copy of each attribute for the new Atype and put it in newA's list of attributes
        // for Annotation attributes, quickCopy does not validate the label restrictions;
        // we assume we're copying in a way that maintains validity, but it is possible to 
        // break things if copying only some Atypes from a given repository, resulting in
        // restrictions that refer to types we may not know about.  So don't do that.
        for(AttributeType attr:this.attributes) {
            newA.attributes.add(attr.quickCopy(newA));
        }
        newA.attrHash = new HashMap<String,Integer>(this.attrHash);
        newA.curAttrHashIndex = this.curAttrHashIndex;
        newA.hasAnnotationAttribute = this.hasAnnotationAttribute;
        newA.hasDefaults = this.hasDefaults;
        return newA;
    }
    
    
    /** I don't need this method, I just need to expand findOrAddAttribute to take an aggregation
    private void createAttributeType(String attrtype, String attrName, int aggregation) throws AnnotationException {
    if (isClosed) {
    throw new AnnotationException("Annotation type " + this.label + " no longer permits attributes to be added.");
    }
    // give this a chance to throw an exception before we go and increment stuff
    AttributeType newAttr = attr.
    
    
    }
     ***/
    /*** this seems to be just another findOrCreate
    // ensureAttribute should only barf on mismatching atypes if the aType is not null.
    public int ensureAttribute(String attrName, String attrtype, int aggregation) {
    
    
    }
     * ***/
}
