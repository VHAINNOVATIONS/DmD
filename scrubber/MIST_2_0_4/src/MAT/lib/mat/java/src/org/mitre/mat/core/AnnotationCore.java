/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.Iterator;
import java.util.List;

/**
 * The core Annotation class for MAT.  
 * @author sam, robyn
 */
public abstract class AnnotationCore {

    /**
     * The list of attribute values.  The order corresponds to the order of the attributes list in the parent Atype
     */
    protected List attrVals;
    /**
     * the Atype of this annotation.
     */
    protected Atype parentAtype;
    private String id;
    private MATDocument doc;

    /**
     * Constructor with valsList.
     * 
     * @param doc  The MATDocument this Annotation belongs to
     * @param parent The Atype of this Annotation
     * @param valsList 
     * @throws AnnotationException
     */
    public AnnotationCore(MATDocument doc, Atype parent, List valsList) throws AnnotationException {
        this.init(doc, parent, valsList);
    }

    // this is here because Annotation needs to have a superclass constructor 
    // that can set start and end for it before the default values are 
    // initialized -- this should only be called from the Annotation constructor
    /**
     * Constructor for a spanned annotation -- should only be called from the corresponding
     * Annotation constructor and not directly.  This is here because Annotation 
     * needs to have a superclass constructor that can set start and end for it 
     * before the default values are initialized.
     * 
     * @param doc
     * @param parent
     * @param start
     * @param end
     * @param valsList
     * @throws AnnotationException
     */
    protected AnnotationCore (MATDocument doc, Atype parent, int start, int end, List valsList) throws AnnotationException {
        if (parent.hasSpan()) {
            ((Annotation)this).setStartIndex(start);
            ((Annotation)this).setEndIndex(end);
        } else {
            throw new AnnotationException("cannot construct a spanless annotation with start and end indices");
        }
        this.init(doc, parent, valsList);
    }
    
    private void init(MATDocument doc, Atype parent, List valsList) throws AnnotationException {
        this.doc = doc;
        this.attrVals = valsList;
        // We have to check the valsList to ensure that
        // the objects are the right type.
        if ((valsList != null) && (valsList.size() > 0)) {
            parent.checkAttributeValues(valsList);
            // If the values check out, then if it's an annotation value,
            // we need to add this as a reference.
            Iterator it = valsList.iterator();
            while (it.hasNext()) {
                Object o = it.next();
                if (o instanceof AnnotationCore) {
                    doc.getIDCache().registerAnnotationReference((AnnotationCore) o);
                }
            }
        }
        this.parentAtype = parent;
        this.id = null;
        if (parent.hasDefaults()) {
            initDefaults();
        }
       
    }
    
    private void initDefaults() throws AnnotationException {
        for (int i = 0; i < parentAtype.getAttributeNames().size(); i++) {
            AttributeType attr = parentAtype.getAttributeType(i);
            if (attr.hasDefault()) {
                if (this.attrVals.size() <= i) {
                    // grow the values list if necessary
                    for (int j = this.attrVals.size(); j < i; j++) {
                        this.attrVals.add(null);
                    }
                    this.attrVals.add(attr.getAttributeDefault(this));
                }
            }
        }
    }
    
    /**
     * 
     * @return The Label (Annotation type) of this Annotation
     */
    public String getAtypeType() {
        return this.parentAtype.getAtypeType();
    }

    /**
     * 
     * @return The Atype of this Annotation
     */
    public Atype getParentAtype() {
        return this.parentAtype;
    }


    /**
     * 
     * @param attr
     * @return The value of the given attribute.  (We have to return Object
     * because the result may be any of the legal Attribute value types.)
     */
    public Object getAttributeValue(String attr) {
        int index = this.parentAtype.getAttributeIndex(attr);
        if (index >= 0) {
            try {
                return this.attrVals.get(index);
            } // Attribute value may not be specified - return null
            catch (Exception e) {
                return null;
            }
        } else {
            return null;
        }
    }

    /**
     * 
     * @return the List of attribute values (in an order corresponding to the
     *         parent Atype's list of attributes).
     */
    public List getAttributeValues() {
        return this.attrVals;
    }

    /**
     * 
     * @return the parent Atype's list of attributes
     */
    public List<AttributeType> getAttributes() {
        return this.parentAtype.getAttributes();
    }

    // the python code has a single __setitem__ method which can take an attribute index, or attribute name
    // it also does adding a new attribute differently -- we have findOrAddAttribute but the python does the
    // lookup and creation if needed within the annotation object in __setitem__
    /**
     * Sets an attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(String attr, Object value) throws MATDocumentException, AnnotationException {
        if (value instanceof AnnotationCore) {
            setAttributeValue(attr, (AnnotationCore) value);
        } else if (value instanceof AttributeValueSet) {
            setAttributeValue(attr, (AttributeValueSet) value);
        } else if (value instanceof AttributeValueList) {
            setAttributeValue(attr, (AttributeValueList) value);
        } else if (value instanceof String) {
            setTypedAttributeValue(attr, value, Atype.STRING_ATTR_TYPE);
        } else if (value instanceof Integer) {
            setTypedAttributeValue(attr, value, Atype.INT_ATTR_TYPE);
        } else if (value instanceof Float) {
            setTypedAttributeValue(attr, value, Atype.FLOAT_ATTR_TYPE);
        } else if (value instanceof Boolean) {
            setTypedAttributeValue(attr, value, Atype.BOOLEAN_ATTR_TYPE);
        } else {
            throw new AnnotationException("value is not of an allowable attribute value type");
        }
    }

    /**
     * Sets an attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(String attr, int value) throws MATDocumentException, AnnotationException {
        setTypedAttributeValue(attr, new Integer(value), Atype.INT_ATTR_TYPE);
    }

    /**
     * Sets an attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(String attr, float value) throws MATDocumentException, AnnotationException {
        setTypedAttributeValue(attr, new Float(value), Atype.FLOAT_ATTR_TYPE);
    }

    /**
     * Sets an attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(String attr, double value) throws MATDocumentException, AnnotationException {
        setTypedAttributeValue(attr, new Float(value), Atype.FLOAT_ATTR_TYPE);
    }

    /**
     * Sets an attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(String attr, AnnotationCore value) throws MATDocumentException, AnnotationException {
        this.setTypedAttributeValue(attr, value, Atype.ANNOTATION_ATTR_TYPE);
        if (value != null) {
            this.doc.getIDCache().registerAnnotationReference(value);
        } else {
            this.doc.getIDCache().clearIDReferences();
        }
    }

    /**
     * Sets a Set-valued attribute value. It is preferable to use the version that
     * also takes an attribute type parameter unless the attribute type is "string".  
     * If you don't pass in an attrtype, first we will try to find the existing 
     * AttributeType for attr; if there isn't one, we will try to infer the 
     * attrtype from the AttributeValueSet, but that will only work if the 
     * AttributeValueSet has ofAttribute already set, which is unlikely so usually 
     * we will just have to assume "string" here -- if it's something else, pass it in.
     * 
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     * @see setAttributeValue(String,String,AttributeValueSet)
     */
    public void setAttributeValue(String attr, AttributeValueSet value) throws AnnotationException, MATDocumentException {
        AttributeType attribType = this.parentAtype.getAttributeType(attr); // may be null if attr doesn't exist yet in Atype
        String attrtype = getAttributeTypeType(attribType, value);
        setAttributeValue(attr, attrtype, value);
    }

    private String getAttributeTypeType(AttributeType attribType, AttributeValueCollection value) {
        String attrtype = null;
        if (attribType != null) {
            attrtype = attribType.getType();
        } else {
            attrtype = value.getType();
        }
        if (attrtype == null) {
            attrtype = Atype.STRING_ATTR_TYPE;
        }
        return attrtype;
    }

    /**
     * Sets a Set-valued attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param attrtype the type of the attribute which must be one of the types 
     *                 defined in the Atype class
     * @param value the value to set the attribute to
     * @throws AnnotationException
     * @throws MATDocumentException
     * @see Atype#STRING_ATTR_TYPE
     * @see Atype#INT_ATTR_TYPE
     * @see Atype#FLOAT_ATTR_TYPE
     * @see Atype#BOOLEAN_ATTR_TYPE
     * @see Atype#ANNOTATION_ATTR_TYPE
     * @see Atype#ATTR_TYPES
     */
    public void setAttributeValue(String attr, String attrtype, AttributeValueSet value) throws AnnotationException, MATDocumentException {
        int index = this.parentAtype.findOrAddAttribute(attr, attrtype, AttributeType.SET_AGGREGATION);
        // we need to make sure the items within the aggregation are ok, 
        // which will happen when we set the AttributeValueSet to be hooked up 
        // to the correct AttributeType
        value.setAttribute(this.doc, this.parentAtype.getAttributeType(index));
        this.setAttributeValueAtIndex(index, value);
    }

    /**
     * Sets a List-valued attribute value. It is preferable to use the version that
     * also takes an attribute type parameter unless the attribute type is "string".  
     * If you don't pass in an attrtype, first we will try to find the existing 
     * AttributeType for attr; if there isn't one, we will try to infer the 
     * attrtype from the AttributeValueList, but that will only work if the 
     * AttributeValueSet has ofAttribute already set, which is unlikely so usually 
     * we will just have to assume "string" here -- if it's something else, pass it in.
     * 
     * @param attr  the String name of the attribute whose value is to be set
     * @param value the value to set the attribute to
     * @throws MATDocumentException
     * @throws AnnotationException
     * @see setAttributeValue(String,String,AttributeValueList)
     */
    public void setAttributeValue(String attr, AttributeValueList value) throws AnnotationException, MATDocumentException {
        AttributeType attribType = this.parentAtype.getAttributeType(attr); // may be null if attr doesn't exist yet in Atype
        String attrtype = getAttributeTypeType(attribType, value);
        setAttributeValue(attr, attrtype, value);
    }

    /**
     * Sets a List-valued attribute value.
     * @param attr  the String name of the attribute whose value is to be set
     * @param attrtype the type of the attribute which must be one of the types 
     *                 defined in the Atype class
     * @param value the value to set the attribute to
     * @throws AnnotationException
     * @throws MATDocumentException
     * @see Atype#STRING_ATTR_TYPE
     * @see Atype#INT_ATTR_TYPE
     * @see Atype#FLOAT_ATTR_TYPE
     * @see Atype#BOOLEAN_ATTR_TYPE
     * @see Atype#ANNOTATION_ATTR_TYPE
     * @see Atype#ATTR_TYPES     */
    public void setAttributeValue(String attr, String attrtype, AttributeValueList value) throws AnnotationException, MATDocumentException {
        int index = this.parentAtype.findOrAddAttribute(attr, attrtype, AttributeType.LIST_AGGREGATION);
        value.setAttribute(this.doc, this.parentAtype.getAttributeType(index));
        this.setAttributeValueAtIndex(index, value);
    }

    // These next three are intended to be used ONLY with the JSON decoder.
    // This method must convert the String value read from the JSON 
    // to the type required for the annotation at the given index
    /**
     * A variant of setAttributeValue meant to be used ONLY with the JSON decoder.
     * This method must convert the String value read from the JSON to the type 
     * required for the annotation at the given index.
     * 
     * @param index
     * @param value
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(int index, String value) throws MATDocumentException, AnnotationException {
        AttributeType attribType = this.parentAtype.getAttributeType(index);
        Object theVal = attribType.digestSingleValueFromString(value);
        if (attribType.isChoiceAttribute && !attribType.choiceAttributeOK(this, theVal))
            throw new AnnotationException("value of attribute " + attribType.getName() + " cannot be changed to " + theVal +
                    " because the result is inconsistent with the attribute restrictions of the attributes the annotation fills");
        if (attribType.checkAndImportSingleValue(doc, theVal)) {
            this.setAttributeValueAtIndex(index, theVal);
        } else {
            throw new AnnotationException("attribute value at index " + index
                    + " must be a " + attribType.getType() + " and satisfy other restrictions");
        }
    }
    
    // since I have the index, the attribute already exists 
    /**
     * A variant of setAttributeValue meant to be used ONLY with the JSON decoder.
     * @param index
     * @param value
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(int index, AttributeValueCollection value) throws MATDocumentException, AnnotationException {
        // setAttribute on the AttrValSet checks that the values are ok for the AttributeType at this index
        value.setAttribute(this.doc, this.parentAtype.getAttributeType(index));
        this.setAttributeValueAtIndex(index, value);        
    }
    
    /**
     * A variant of setAttributeValue meant to be used ONLY with the JSON decoder.
     * @param index
     * @param value
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void setAttributeValue(int index, AnnotationCore value) throws MATDocumentException, AnnotationException {
        this.setTypedAttributeValue(index, value, Atype.ANNOTATION_ATTR_TYPE);
        if (value != null) {
            this.doc.getIDCache().registerAnnotationReference(value);
        } else {
            this.doc.getIDCache().clearIDReferences();
        }
    }

    // setTypedAttibuteValue is called with an assertion as to the type of the value that was passed in
    // we check that that type is correct for the attribute, and then set it
    // if passed an attribute name, we also find the index
    // This is for single attribute values only, as the findOrAdd here doesn't consider aggregations
    private void setTypedAttributeValue(String attr, Object value, String attrtype) throws MATDocumentException, AnnotationException {
        int index = this.parentAtype.findOrAddAttribute(attr, attrtype);
        this.setTypedAttributeValue(index, value, attrtype);
    }

    private void setTypedAttributeValue(int index, Object value, String attrtype) throws MATDocumentException, AnnotationException {
        // this checks that attribute at the given index is expecting a value of type attrtype
        // this method must always be called with attrtype reflecting the actual type of value
        if (!this.parentAtype.checkAttributeTypeAtIndex(index, attrtype)) {
            throw new AnnotationException("attribute value at index " + index + " must be a " + attrtype);
        }
        AttributeType attribType = this.parentAtype.getAttributeType(index);
        if (attribType.isChoiceAttribute && !attribType.choiceAttributeOK(this, value))
            throw new AnnotationException("value of attribute " + attribType.getName() + " cannot be changed to " + value +
                    " because the result is inconsistent with the attribute restrictions of the attributes the annotation fills");
        if (attribType.checkAndImportSingleValue(doc, value)) {
            this.setAttributeValueAtIndex(index, value);
        } else {
            throw new AnnotationException("attribute value at index " + index
                    + " must be a " + attrtype + " and satisfy other restrictions");
        }
    }

    // This doesn't check types. Its callers must. 
    private void setAttributeValueAtIndex(int index, Object value) {
        if (index < this.attrVals.size()) {
            this.attrVals.set(index, value);
        } else {
            while (this.attrVals.size() < index) {
                this.attrVals.add(null);
            }
            this.attrVals.add(value);
        }
    }

    /**
     * @param generateIt indicates whether or not to generate a new id if the
     *                   annotation does not already have one
     * @return the id
     */
    public String getID(boolean generateIt) {
        if (generateIt && (this.id == null)) {
            this.id = this.doc.getIDCache().generateID(this);
        }
        return this.id;
    }

    /**
     * Retrieves or generates this Annotation's unique ID
     * @return this annotation's unique ID
     */
    public String getID() {
        return this.getID(true);
    }

    /**
     * Sets this Annotation's unique ID
     *
     * @param id the id to set
     * @throws MATDocumentException  
     */
    public void setID(String id) throws MATDocumentException {
        this.doc.getIDCache().registerID(id, this);
        this.id = id;
    }

    /**
     * 
     * @return the MATDocument to which this Annotation belongs.
     */
    public MATDocument getDoc() {
        return doc;
    }
}
