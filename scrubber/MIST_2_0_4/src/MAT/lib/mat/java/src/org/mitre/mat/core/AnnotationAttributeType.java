/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Set;

/**
 * An attribute whose value is an Annotation (or set or list of Annotations)
 * 
 * @author robyn
 */
public class AnnotationAttributeType extends AttributeType {

    private Set<String> atomicLabelRestrictions;
    private Set<ComplexRestriction> complexLabelRestrictions;

    /**
     * Constructor
     * @param atype the parent Atype for this attribute
     * @param name  the name of the attribute
     * @param optional specifies whether or not this attribute's value is optional
     * @param aggregation specifies the aggregation type of this attribute
     *                    using the constants defined in AttributeType
     * @param distinguishing specifies whether or not this attribute is a
     *                       distinguishing attribute for equality
     * @throws AnnotationException
     * @see AttributeType#LIST_AGGREGATION
     * @see AttributeType#SET_AGGREGATION
     * @see AttributeType#NONE_AGGREGATION
     */
    public AnnotationAttributeType(Atype atype, String name, boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "annotation";
    }

    /**
     * Constructor.
     * @param atype the parent Atype for this attribute
     * @param name  the name of the attribute
     * @param aggregation specifies the aggregation type of this attribute
     *                    using the constants defined in AttributeType
     * @throws AnnotationException
     * @see AttributeType#LIST_AGGREGATION
     * @see AttributeType#SET_AGGREGATION
     * @see AttributeType#NONE_AGGREGATION     */
    public AnnotationAttributeType(Atype atype, String name, int aggregation) throws AnnotationException {
        this(atype, name, false, aggregation, false);
    }

    /**
     * Simple Constructor.
     * @param atype the parent Atype for this attribute
     * @param name  the name of the attribute
     * @throws AnnotationException
     */
    public AnnotationAttributeType(Atype atype, String name) throws AnnotationException {
        super(atype, name);
        this.type = "annotation";
    }

    @Override
    public AttributeType copy(Atype atype) throws AnnotationException {
        AnnotationAttributeType cp =
                new AnnotationAttributeType(atype, this.name, this.optional,
                this.aggregationType, this.distinguishingAttrForEquality);
        cp.setAtomicLabelRestrictions(new HashSet(atomicLabelRestrictions));
        cp.setComplexLabelRestrictions(new HashSet(complexLabelRestrictions));
        return cp;
    }
    
    @Override
    public AttributeType quickCopy(Atype atype) throws AnnotationException {
        AnnotationAttributeType cp =
                new AnnotationAttributeType(atype, this.name, this.optional,
                this.aggregationType, this.distinguishingAttrForEquality);
        cp.atomicLabelRestrictions = atomicLabelRestrictions;
        cp.complexLabelRestrictions = complexLabelRestrictions;
        return cp;
    }

    @Override
    public boolean checkValue(Object v) {
        return checkAnnotationValue(v);
    }

    @Override
    public boolean checkAndImportSingleValue(MATDocument doc, Object value) {
        if (value == null) { // null is always acceptable
            doc.getIDCache().clearIDReferences(); // may be overwriting an existing value
            return true;
        }
        if (!(value instanceof AnnotationCore)) {
            return false;
        }
        AnnotationCore annot = (AnnotationCore) value;

        if (checkAnnotationValue(annot)) {
            doc.getIDCache().registerAnnotationReference(annot);
            return true;
        } else {
            return false;
        }
    }

    @Override
    public void clearValue(MATDocument doc) {
        // clear the id references
        doc.getIDCache().clearIDReferences();
    }

    @Override
    public Object digestSingleValueFromString(String val) {
        // not possible
        return null;
    }

    private boolean checkAnnotationValue(AnnotationCore v) {
        return checkRestrictions(v);
    }

    private boolean checkAnnotationValue(AttributeValueCollection v) {
        // check each value in the collection
        for (Iterator i = v.iterator(); i.hasNext();) {
            if (!checkAnnotationValue(i.next())) {
                return false;
            }
        }
        // didn't find any bad values, so...
        return true;
    }

    private boolean checkAnnotationValue(Object v) {
        if (v instanceof AnnotationCore) {
            return checkAnnotationValue((AnnotationCore) v);
        } else if (v instanceof AttributeValueCollection) {
            return checkAnnotationValue((AttributeValueCollection) v);
        } else {
            return false;
        }
    }

    private boolean checkRestrictions(AnnotationCore v) {
        return (!hasRestrictions() || checkSimpleRestrictions(v) || checkComplexRestrictions(v));
    }

    /**
     * Sets the atomic label restrictions on the types of annotations that can
     * fill this attribute value.  Each atomic restriction is the name of an 
     * annotation label.  An annotation with the specified label may fill this 
     * attribute value.  An attribute can have a set of such restrictions, and 
     * an annotation that has any of the specified labels is an acceptable filler
     * for this attribute value.
     * @param atomicLabelRestrictions a List of annotation labels
     * @throws AnnotationException
     */
    public void setAtomicLabelRestrictions(Set<String> atomicLabelRestrictions) throws AnnotationException {
        for (String rest: atomicLabelRestrictions) {
            if (!validateAtomicRestriction(rest)) {
                throw new AnnotationException("invalid annotation restriction found");
            }
        }
        this.atomicLabelRestrictions = atomicLabelRestrictions;
    }

    /**
     * Sets the complex restrictions on the types of annotations that can
     * fill this attribute value.  Each <code>ComplexRestriction</code> specifies
     * an annotation label and a Map of attribute/value pairs.  An annotation with
     * the specified label may fill this attribute value if all of the attributes
     * included in the restrictions map are set to the specified values.  An  
     * attribute can have a set of such restrictions; an annotation can fill this
     * attribute value if it satisfies at least one of the ComplexRestrictions
     * (but it need not satisfy them all -- that is, the restrictions are 
     * effectively OR'd together).
     * @param complexLabelRestrictions a set of ComplexRestrictions that restrict
     *                                 the annotations that can fill this attribute value
     * @throws AnnotationException
     * @see ComplexRestriction
     */
    public void setComplexLabelRestrictions(Set<ComplexRestriction> complexLabelRestrictions) throws AnnotationException {
        for (ComplexRestriction rest: complexLabelRestrictions) {
            if (!validateComplexRestriction(rest)) {
                throw new AnnotationException("invalid annotation restriction found");
            }
        }
        this.complexLabelRestrictions = complexLabelRestrictions;
    }

    private void addAtomicLabelRestriction(String label) {
        this.atomicLabelRestrictions.add(label);
    }

    private void addComplexLabelRestriction(ComplexRestriction rest) {
        this.complexLabelRestrictions.add(rest);
    }

    /**
     * Sets both atomic and complex label restrictions specifying which 
     * annotations can fill this attribute value.  An annotation must satisfy
     * at least one (but not necessarily all) of the label restrictions to be
     * a valid filler of this attribute value.
     * @param labelRestrictions a Set containing Strings and/or ComplexRestrictions
     *                          representing atomic or complex label restrictions, 
     *                          respectively.
     * @throws AnnotationException
     * @see AnnotationAttributeType#setAtomicLabelRestrictions(java.util.Set) 
     * @see AnnotationAttributeType#setComplexLabelRestrictions(java.util.Set) 
     */
    public void setLabelRestrictions(Set labelRestrictions) throws AnnotationException {
        this.atomicLabelRestrictions = new HashSet();
        this.complexLabelRestrictions = new HashSet();
        for (Iterator i = labelRestrictions.iterator(); i.hasNext();) {
            Object rest = i.next();
            if ((rest instanceof String) && validateAtomicRestriction((String) rest)) {
                    addAtomicLabelRestriction((String) rest);
            } else if ((rest instanceof ComplexRestriction) && validateComplexRestriction((ComplexRestriction) rest)) {
                    addComplexLabelRestriction((ComplexRestriction) rest);
            } else {
                throw new AnnotationException("invalid annotation restriction found");
            }
        }
    }

    // if it matches any simple restriction, return true; otherwise return false
    // if there are no simple restrictions return false
    private boolean checkSimpleRestrictions(AnnotationCore v) {
        if (atomicLabelRestrictions == null) {
            return false;
        }
        for (Iterator<String> i = this.atomicLabelRestrictions.iterator(); i.hasNext();) {
            if (v.getParentAtype().getLabel().equals(i.next())) {
                return true;
            }
        }
        return false;
    }

    // if it matches any complex restriction, return true; otherwise return false
    // if there are not complex restrictions return false
    private boolean checkComplexRestrictions(AnnotationCore v) {
        if (complexLabelRestrictions == null) {
            return false;
        }
        for (Iterator<ComplexRestriction> i = this.complexLabelRestrictions.iterator(); i.hasNext();) {
            if (checkComplexRestriction(v, i.next())) {
                return true;
            }
        }
        return false;
    }

    // I don't think we need this in the Java
    /**
     * Unsupported.  (I don't think this is needed in the Java API)
     * @param gloablATR
     */
    public void digestLabelRestrictions(GlobalAnnotationTypeRepository gloablATR) {
        throw new UnsupportedOperationException("Not supported.");

    }

    // the validate restriction methods are instead of digestLabelRestrictions, 
    // since I need to do less than is done in the digest method in python
    
    /**
     * Validates an atomic label restriction.  This method ensures that the
     * proposed label restriction refers to a label that exists already in 
     * the parent AnnotationTypeRepository.
     * @param label The label proposed as an atomic label restriction
     * @return
     */
    public boolean validateAtomicRestriction(String label) {
        AnnotationTypeRepository atr = this.atype.getRepository();
        return (atr.get(label) != null);
    }

    
    /**
     * Validates a complex label restriction.  This requires us to ensure that:
     * 1) the label exists in the parent AnnotationTypeRepository
     * 2) for each attribute value pair, the attribute exists on the annotation
     *    type indicated by the label, and that attribute is a choice attribute,
     *    and the value provided is one of the choices.
     * @param rest
     * @return
     * @see ComplexRestriction
     */
    public boolean validateComplexRestriction(ComplexRestriction rest) {
        AnnotationTypeRepository atr = this.atype.getRepository();
        Atype labelAtype = atr.get(rest.getLabel());
        if (labelAtype == null) {
            return false;
        }
        Map<String,Object> avRest = rest.getAttrValRestrictions();
        for (String attrName:avRest.keySet()) {
            Object val = avRest.get(attrName);
            AttributeType attrtype = labelAtype.getAttributeType(attrName);
            if (attrtype == null || !attrtype.isChoiceAttribute) {
                return false;
            }
            // for a choice attribute, checkValue just checks if it is one of 
            // the choices, which is exactly what we need to know
            if (!attrtype.checkValue(val)) {
                return false;
            }
        }
        // since there is nothing wrong with it, return true
        return true;
    }

    // TODO do I need to implement toJSON?  here and in AttributeType? 
    
    @Override
    // only restriction key for AnnotationAttributeType is label_restrictions
    public void addRestrictions(Map restrictions) throws AnnotationException {
        for (Iterator i = restrictions.keySet().iterator(); i.hasNext();) {
            if ("label_restrictions".equals(i.next())) {
                this.setLabelRestrictions((Set) restrictions.get("label_restrictions"));
            } else {
                throw new AnnotationException("invalid restriction for AnnotationAttributeType");
            }
        }
    }

    private boolean checkComplexRestriction(AnnotationCore v, ComplexRestriction rest) {
        if (v.getParentAtype().getLabel().equals(rest.getLabel())) {
            Map attrValRestrictions = rest.getAttrValRestrictions();
            for (Iterator i = attrValRestrictions.keySet().iterator(); i.hasNext();) {
                String attr = (String) i.next();
                Object attrval = v.getAttributeValue(attr);
                if (attrval == null) {
                    return false; // the required attribute isn't set so it automatically fails to meet the restrictions
                }
                if (!attrval.equals(attrValRestrictions.get(attr))) {
                    return false;
                }
            }
            return true;
        } else {
            return false;
        }
    }

    private boolean hasRestrictions() {
        return ((atomicLabelRestrictions != null) || (complexLabelRestrictions != null));
    }

    /* This is used when possibly setting the value of a choice
     * attribute of an annotation that has already been assigned
     * as a subordinate, to make sure the resulting array of features works.
     * Very similar to checkRestrictions
     */
    /**
     * Confirm that a set of attribute/value choices on a particular annotation type
     * will satisfy the requirements of this attribute.  This is called when attempting
     * to set or change an attribute value in an annotation that has already been 
     * used to fill this AnnotationAttribute slot, to ensure that the resulting array
     * of features works. 
     * @param candidateLabel The label of the annotation
     * @param candidateFeatures A map from attribute name to value, representing 
     *                          a candidate set of features we wish to validate
     *                          for a filler of this attribute value
     * @return
     * @see AnnotationAttributeType#checkRestrictions(org.mitre.mat.core.AnnotationCore) 
     */
    public boolean choicesSatisfyRestrictions(String candidateLabel, Map<String, Object> candidateFeatures) {
        if (!hasRestrictions()) {
            return true;
        }
        if (atomicLabelRestrictions != null && atomicLabelRestrictions.contains(candidateLabel)) {
            return true;
        }
        if (complexLabelRestrictions != null) {
            for (ComplexRestriction cRest : complexLabelRestrictions) {
                String lab = cRest.getLabel();
                if (!candidateLabel.equals(lab)) {
                    continue;
                }
                Map<String, Object> restPairs = cRest.getAttrValRestrictions();
                boolean failed = false;
                for (String key : restPairs.keySet()) {
                    if (!candidateFeatures.get(key).equals(restPairs.get(key))) {
                        failed = true;
                        break;
                    }
                }
                if (!failed) {
                    return true;
                }
            }
        }
        return false;
    }
}
