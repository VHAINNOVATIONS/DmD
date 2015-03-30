/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.mitre.mat.core.AnnotationIDCache;

/**
 * An Abstract class defining the common behavior of all Attribute Types.
 * @author robyn
 */
public abstract class AttributeType {

    /**
     * The Aggregation type for an attribute whose value is a List of values
     */
    public static final int LIST_AGGREGATION = 1;
    /**
     * The Aggregation type for an attribute whose value is a Set of values
     */
    public static final int SET_AGGREGATION = 2;
    /**
     * The Aggregation type for an attribute whose value is a single value (default)
     */
    public static final int NONE_AGGREGATION = 0;

    /**
     * A list of the names of the different aggregation types, in array order corresponding
     * to the aggregation constants above.
     */
    public static String[] aggregationString = new String[]{"none", "list", "set"};

    // any invalid values will get converted to NONE
    static int getAggregationFromString(String textValue) {
        if (textValue.equals("list")) {
            return LIST_AGGREGATION;
        } else if (textValue.equals("set")) {
            return SET_AGGREGATION;
        } else {
            return NONE_AGGREGATION;
        }
    }
    /**
     * The parent Atype to which this Attribute belongs
     */
    protected Atype atype;
    /**
     * The name of the attribute
     */
    protected String name;
    /**
     * Specifies whether or not the attribute's value is optional
     */
    protected boolean optional;
    /**
     * Specifies whether or not this Attribute is a distinguishing
     * attribute for equality.  Used for scoring.
     */
    protected boolean distinguishingAttrForEquality;
    /**
     * Specifies the aggregation type of this Attribute
     * @see #LIST_AGGREGATION
     * @see #SET_AGGREGATION
     * @see #NONE_AGGREGATION
     */
    protected int aggregationType;
    /**
     * The type of Attribute this is.  Must be set by the implementing class.
     */
    protected String type; /* must be set by the implementing class */

    /**
     * This Attribute's default value, if any.
     */
    protected Object defaultValue;
    /**
     * Specifies whether this attribute's value should default to the text
     * span of the annotation
     */
    protected boolean defaultIsTextSpan;
    private boolean hasDefault = false;
    /**
     * Specifies whether or not this attribute is considered a "choice attribute".
     * A choice attribute is a "string" or "int" type Attribute whose value is 
     * restricted to a provided list of choices.
     */
    protected boolean isChoiceAttribute = false;

    /**
     * Basic Constructor.
     * @param atype the Atype to which this AttributeType will belong
     * @param name  the name of the attribute
     * @throws AnnotationException
     */
    public AttributeType(Atype atype, String name) throws AnnotationException {
        this(atype, name, false, NONE_AGGREGATION, false, null, false);
    }

   

    /**
     * Old constructor with defaults for defaultValue and defaultIsTextSpan for
     * backward compatibility.  
     * @param atype
     * @param name
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @throws AnnotationException
     */
    public AttributeType(Atype atype, String name, boolean optional, int aggregation,
            boolean distinguishing) throws AnnotationException {
        this(atype, name, optional, aggregation, distinguishing, null, false);
    }

    /**
     * Full Constructor.
     * @param atype the Atype to which this AttributeType will belong
     * @param name  the name of the attribute
     * @param optional specifies whether or not this attribute's value is optional
     * @param aggregation specifies the aggregation type of this attribute
     * @param distinguishing specifies whether or not this attribute is a distinguishing
     *                       attribute for equality
     * @param defaultValue   provides a default value (or null if there is no default)
     * @param defaultIsTextSpan specifies whether or not this attribute's default value
     *                          should be the annotation's text span (meaningless for
     *                          spanless annotations).  If this is true, you should not
     *                          also provide a default value, and vice versa.
     * @throws AnnotationException
     */
    public AttributeType(Atype atype, String name, boolean optional, int aggregation,
            boolean distinguishing, Object defaultValue, boolean defaultIsTextSpan)
            throws AnnotationException {

        this.atype = atype;
        this.aggregationType = aggregation;
        if (aggregation != NONE_AGGREGATION && aggregation != LIST_AGGREGATION
                && aggregation != SET_AGGREGATION) {
            throw new AnnotationException("unknown attribute aggregation type"
                    + aggregation);
        }
        this.distinguishingAttrForEquality = distinguishing;
        this.name = name;
        this.optional = optional;
        this.defaultValue = defaultValue;
        this.defaultIsTextSpan = defaultIsTextSpan;
    }

    /**
     * 
     * @return a copy of this AttributeType for the same Atype
     * @throws AnnotationException
     */
    public AttributeType copy() throws AnnotationException {
        return copy(this.atype);
    }

    /**
     * Checks whether a default value has been specified, and if so if it is acceptable.
     * @throws AnnotationException
     */
    protected void manageDefaults() throws AnnotationException {
        if (defaultValue != null || defaultIsTextSpan) {
            if (defaultValue != null && defaultIsTextSpan) {
                throw new AnnotationException("can't declare both default value and defaultIsTextSpan for attribute " + name);
            }
            if (aggregationType > 0) {
                throw new AnnotationException("can't declare default for aggregated "
                        + type + " attribute: " + name);
            }
            if (defaultValue != null && !checkValue(defaultValue)) {
                throw new AnnotationException("default: " + defaultValue + " for "
                        + type + " attribute " + name + "does not meet the attribute requirements");
            } else {
                if (!atype.hasSpan()) {
                    throw new AnnotationException("can't use text span as default for spanless annotation");
                }
            }
            this.hasDefault = true;
        }

    }

    /**
     * 
     * @param annot
     * @return the default value for this attribute in the given Annotation
     * @throws AnnotationException
     */
    public Object getAttributeDefault(AnnotationCore annot) throws AnnotationException {
        if (hasDefault) {
            if (defaultIsTextSpan) {
                return extractAndCoerceTextExtent((Annotation) annot);
            } else {
                return defaultValue;
            }
        } else {
            return null;
        }
    }

    // upon request of John Aberdeen, null and non-parsing values be set to null rather than throwing an exception
    private Object extractAndCoerceTextExtent(Annotation annot) throws AnnotationException {
        Object val = this.digestSingleValueFromString(annot.getDoc().getSignal().substring(annot.getStartIndex(), annot.getEndIndex()));
        if (val != null && !this.checkValue(val)) {
            val = null;
        }
        return val;
    }

    // implementations will return appropriate subtypes
    /**
     * Copy this AttributeType.  (Implementations should return the appropriate subtypes)
     * @param atype The Atype this attribute is being copied to
     * @return a copy of this AttributeType for the given Atype
     * @throws AnnotationException
     */
    public abstract AttributeType copy(Atype atype) throws AnnotationException;
    
    /** 
     * Copy this AttributeType without necessarily doing all of the validations.
     * Defaults to calling the <code>copy(Atype)</code> method but can be overridden 
     * in subclasses to provide a quicker (and possibly safer) copy when certain 
     * validations can/must be skipped.  Most users should call <code>copy(Atype)</code> 
     * instead. This is called by <code>Atype.copy</code> when copying all of an 
     * already-validated Atype.
     * 
     * @param atype The Atype this attribute is being copied to
     * @return A copy of this instance of AttributeType for and pointing to the Atype passed in
     * @throws AnnotationException 
     * @see #copy(Atype)
     */
    public AttributeType quickCopy(Atype atype) throws AnnotationException {
        return this.copy(atype);
    }

    /**
     * Check the validity of a proposed value for this attribute.
     * Will use polymorphism to figure out if checking a list, set or single value
     * and then check the aggregationType to make sure it's appropriate.
     * @param v
     * @return
     */
    public abstract boolean checkValue(Object v);

    /**
     * Check the validity of and import a value for this attribute.  For Annotation
     * attributes, importing involves registering the reference.  For other types
     * importing doesn't do anything.
     * @param doc
     * @param value
     * @return
     */
    public abstract boolean checkAndImportSingleValue(MATDocument doc, Object value);


    
    // called when values are deleted or removed from the collection
    // used for Annotation attributes, to clear reference hash
    
    /**
     * Clear the value of this attribute.  Called when values are deleted or 
     * removed from the collection, and used for Annotation attributes, to 
     * clear the reference hash.
     * @param doc
     */
    public abstract void clearValue(MATDocument doc);

    /**
     * Attempts to coerce a String value into the type appropriate for this Annotation
     * @param val
     * @return
     * @throws AnnotationException
     */
    public abstract Object digestSingleValueFromString(String val) throws AnnotationException;

    // returns the type of the attribute 
    // possible values are "string", "int", "float", "boolean", "annotation"
    /**
     * 
     * @return the type of the annotation -- it will be one of the constants 
     *         as defined in <code>Atype</code>
     * @see Atype#ANNOTATION_ATTR_TYPE
     * @see Atype#BOOLEAN_ATTR_TYPE
     * @see Atype#FLOAT_ATTR_TYPE
     * @see Atype#INT_ATTR_TYPE
     * @see Atype#STRING_ATTR_TYPE
     */
    public String getType() {
        return type;
    }

    /**
     * 
     * @return this attributes aggregation type -- it will be one of the constants
     *         as defined in this class
     * @see NONE_AGGREGATION
     * @see LIST_AGGREGATION
     * @see SET_AGGREGATION
     */
    public int getAggregationType() {
        return aggregationType;
    }

    /**
     * 
     * @return this Attribute's parent Atype
     */
    public Atype getAtype() {
        return atype;
    }

    /**
     * 
     * @return whether this attribute is a distinguishing attribute for equality
     */
    public boolean isDistinguishingAttrForEquality() {
        return distinguishingAttrForEquality;
    }

    /**
     * 
     * @return this attribute's name
     */
    public String getName() {
        return name;
    }

    /**
     * 
     * @return whether this attribute's value is optional
     */
    public boolean isOptional() {
        return optional;
    }

    /**
     * Sets whether this attribute is a distinguishing attribute for equality.
     * @param distinguishingAttrForEquality
     */
    public void setDistinguishingAttrForEquality(boolean distinguishingAttrForEquality) {
        this.distinguishingAttrForEquality = distinguishingAttrForEquality;
    }

    /**
     * Adds restrictions on the attribute values.  
     * @param restrictions
     * @throws AnnotationException
     */
    public abstract void addRestrictions(Map restrictions) throws AnnotationException;

    /**
     * returns whether or not this attribute has a default value specified
     * @return
     */
    public boolean hasDefault() {
        return hasDefault;
    }

    /*** use getAttributedefault instead
    Object getDefaultValue() {
    return defaultValue;
    }
     * /
     
     
     /**
     * Determine whether a candidate value is acceptable for this choice 
     * attribute within the given Annotation.
     * This is general functionality for all singleton choice attributes. If 
     * you're about to change one of these values, you need to know if it CAN 
     * be changed - and it can be changed if the annotation isn't attached to 
     * anything, or if the resulting set of choice attributes satisfy SOME 
     * restriction on EACH of the places it's attached to.    
     * 
     * @param annot
     * @param candidateVal 
     * @return true if the value is acceptable, or if this isn't really a 
     *              choiceAttribute, and false otherwise
     */
    public boolean choiceAttributeOK(AnnotationCore annot, Object candidateVal) {
        if (!isChoiceAttribute) {
            // shouldn't be called in this case, but whatever.
            return true;
        }
        String id = annot.getID(false);
        if (id == null) {
            // if it doesn't have an ID, nothing can be pointing to it so any attribute value is fine
            return true;
        }

        AnnotationIDCache cache = annot.getDoc().getIDCache();
        Set<AnnotationIDCache.AnnotationReference> refs = cache.getReferringAnnots(id);
        if (refs == null || refs.isEmpty()) {
            return true;
        }

        /*
         * So now we have a set of refs, and what we need
         * to do is grab the label and choice vals
         * from the annot, ladle the candidate on top,
         * and make sure that the result satisfies at least
         * one set of restrictions for each reference.
         * We only need the label and choice vals because
         * only choice vals can be part of the label
         * restrictions.
         */
        Map<String, Object> attrDict = new HashMap<String, Object>();
        List<AttributeType> attributes = annot.getAttributes();
        List attrVals = annot.getAttributeValues();
        for (int i = 0; i < attributes.size(); i++) {
            if (attributes.get(i).isChoiceAttribute) {
                attrDict.put(attributes.get(i).getName(), attrVals.get(i));
            }
        }
        attrDict.put(this.name, candidateVal);
        for (AnnotationIDCache.AnnotationReference parentAnnotRef : refs) {
            AnnotationCore parentAnnot = parentAnnotRef.getAnnot();
            AnnotationAttributeType parentAttrType = (AnnotationAttributeType) 
                parentAnnot.getParentAtype().getAttributeType(parentAnnotRef.getAttrName());
            if (!parentAttrType.choicesSatisfyRestrictions(annot.getParentAtype().getLabel(), attrDict)) {
                return false;
            }
        }

        return true;
    }
}
