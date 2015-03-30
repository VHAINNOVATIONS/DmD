/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.Collection;
import java.util.Iterator;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * An abstract class for Collections of values (Sets or Lists) intended to be
 * used as an attribute value filler.  This class almost implements Collection
 * only not quite, because the add methods throw an AnnotationException if you
 * try to add something invalid to the Collection.  The class also tracks the
 * attribute and document this collection is for.
 * 
 * @author robyn
 */
public abstract class AttributeValueCollection //implements Collection (except not really, because I had to change the signature on some of the methods to throw the AnnotationException when the values are no good)
{
    protected MATDocument ofDoc;
    protected AttributeType ofAttribute;
    protected Collection theCollection;

    /**
     * Constructor.  Implementers must initialize the appropriate aggregation.
     */
    public AttributeValueCollection() {
        this.ofDoc = null;
        this.ofAttribute = null;
    }

    /**
     * Constructor.  Implementers must initialize the appropriate aggregation.
     * @param ofDoc the MAT Document
     * @param ofAttribute the attribute for which this collection is the value
     */
    public AttributeValueCollection(MATDocument ofDoc, AttributeType ofAttribute) {
        this.ofDoc = ofDoc;
        this.ofAttribute = ofAttribute;
    }

    /**
     * Copy this AttributeValueCollection
     * @return the copy
     */
    public abstract AttributeValueCollection copy();

    // does a check and import on each value in the collection
    /**
     * Validates and imports each value in the collection.  Must be called before
     * this collection can be set as the attribute value in the annotation
     * @param doc the MAT Document
     * @param attr the attribute
     * @throws AnnotationException if any of the values in the collection is an
     *                             invalid value for the attribute
     */
    public void setAttribute(MATDocument doc, AttributeType attr) throws AnnotationException {
        if (attr instanceof FloatAttributeType) {
            fixFloatCollection();
        }
        this.ofDoc = doc;
        this.ofAttribute = attr;
        for (Iterator i = theCollection.iterator(); i.hasNext();) {
            Object value = i.next();
            if (!attr.checkAndImportSingleValue(doc, value)) {
                throw new AnnotationException("value of element of attribute \'"
                        + attr.getName() + "\' must be a " + attr.getType()
                        + " and meet the other requirements.  Bad value: " 
                        + value.toString() + " Class: " + value.getClass());
            }
        }
    }

    // checks that every value in theCollection has a valid value based on the rules of the AttributeType
    /**
     * Validates each value in the collection without actually importing the
     * values.  May be used to determine whether the values are hypothetically
     * acceptable without committing to actually setting the attribute value.
     * @param attr the attribute
     * @throws AnnotationException if any of the values in the collection is an
     *                             invalid value for the attribute
     */
    public void checkAttribute(AttributeType attr) throws AnnotationException {
        for (Iterator i = theCollection.iterator(); i.hasNext();) {
            Object value = i.next();
            if (!attr.checkValue(value)) {
                throw new AnnotationException("value of element of attribute \'"
                        + attr.getName() + "\' must be a " + attr.getType()
                        + " and meet the other requirements.");
            }
        }
    }

    /**
     * Checks a single value to see if it is appropriate to go into the
     * collection, and calls clearValue on the attribute (which indicates that
     * the reference hashes will need to be recomputed)
     * @param value the value to check
     * @throws AnnotationException if the value is unacceptable
     */
    public void checkValue(Object value) throws AnnotationException {
        checkValue(value, true);
    }

    // checks a single value to see if it's appropriate to go into theCollection
    // optionally calls clearValue first, if the clear parameter is set to true
    // clearValue just sets the flag indicating that indices may be fubar'd?
    // so we need to clear if we are actually setting the value, but not if we're just checking "for fun"
    /**
     * A version of checkValue that permits not calling clearValue.  You would want
     * to not call clearValue if you were just checking the value "for fun" but
     * not setting it.
     * @param value the value to check
     * @param clear indicates whether or not to call clearValue on the attribute
     * @throws AnnotationException if the value is unacceptable
     * @see AttributeValueCollection#checkValue(java.lang.Object) 
     */
    public void checkValue(Object value, boolean clear) throws AnnotationException {
        if (ofDoc != null && ofAttribute != null) {
            if (clear) {
                ofAttribute.clearValue(ofDoc);
            }
            if (!ofAttribute.checkAndImportSingleValue(ofDoc, value)) {
                throw new AnnotationException("value of element of attribute \'"
                        + ofAttribute.getName() + "\' must be a " + ofAttribute.getType()
                        + " and meet the other requirements.");

            }
        }
    }

    /**
     * Checks a Collection to see if each value therein is appropriate to go into the
     * collection, and calls clearValue on the attribute (which indicates that
     * the reference hashes will need to be recomputed)
     * @param vals the values to check
     * @throws AnnotationException if any of the values is unacceptable
     */
    public void checkCollection(Collection vals) throws AnnotationException {
        checkCollection(vals, true);
    }

    // checks a collection of values to see if they're all appropriate to go into theCollection
    // optionally calls clearValue first, if the clear parameter is set to true
    // clearValue just sets the flag indicating that indices may be fubar'd?
    // so we need to clear if we are actually setting the value, but not if we're just checking "for fun"
    /**
     * A version of checkValue that permits not calling clearValue.  You would want
     * to not call clearValue if you were just checking the value "for fun" but
     * not setting it.
     * @param vals the values to check
     * @param clear indicates whether or not to call clearValue on the attribute
     * @throws AnnotationException if any of the values is unacceptable
     */
    public void checkCollection(Collection vals, boolean clear) throws AnnotationException {
        if (ofDoc != null && ofAttribute != null) {
            if (clear) {
                ofAttribute.clearValue(ofDoc);
            }
            for (Iterator i = vals.iterator(); i.hasNext();) {
                Object value = i.next();
                if (!ofAttribute.checkAndImportSingleValue(ofDoc, value)) {
                    throw new AnnotationException("value of element of attribute \'"
                            + ofAttribute.getName() + "\' must be a " + ofAttribute.getType()
                            + " and meet the other requirements.");

                }
            }
        }
    }

    /**
     * calls clearValue on this collection's attribute (which indicates that
     * the reference hashes will need to be recomputed)     
     */
    protected void clearAttribute() {
        if (ofDoc != null && ofAttribute != null) {
            ofAttribute.clearValue(ofDoc);
        }
    }

    /**
     * Retrieve this collections's attribute
     * @return the attribute
     */
    public AttributeType ofAttribute() {
        return ofAttribute;
    }

    /**
     * Retrieve this collection's parent document
     * @return the document
     */
    public MATDocument ofDoc() {
        return ofDoc;
    }

    /**
     * Retrieve the type this collection's attribute (which is the type all
     * of the values in the collection must be)
     * @return the type
     */
    public String getType() {
        if (ofAttribute == null) {
            return null;
        }
        return ofAttribute.getType();
    }

    /**
     * Compares the contents of this attributeValueCollection to that of another.
     * The document and attribute can be different -- only the underlying collections
     * need to be equal.
     * @param v the collection to compare to this one
     * @return true if the collection underlying v is equal to the collection 
     *         underlying this AttributeValueCollection
     */
    public boolean collectionEquals(AttributeValueCollection v) {
        return theCollection.equals(v.getCollection());
    }
    
    // Implements Collection, sort of, and adds bookkeeping and checking needed
    // we don't officially implement Collection, because I had to change the 
    // signature on some of the methods to throw the AnnotationException when 
    // the values are no good)
    /**
     * 
     * @return the size of the underlying collection
     * @see Collection#size()
     */
    public int size() {
        return theCollection.size();
    }

    /**
     * 
     * @return true if the underlying collection is empty
     * @see Collection#isEmpty() 
     */
    public boolean isEmpty() {
        return theCollection.isEmpty();
    }

    /**
     * 
     * @param o
     * @return true if the underlying collection contains o
     * @see Collection#contains(java.lang.Object) 
     */
    public boolean contains(Object o) {
        return theCollection.contains(o);
    }

    /**
     * 
     * @return an iterator over the underlying collection
     * @see Collection#iterator() 
     */
    public Iterator iterator() {
        return theCollection.iterator();
    }

    /**
     * 
     * @return the underlying collection as an array
     * @see Collection#toArray() 
     */
    public Object[] toArray() {
        return theCollection.toArray();
    }

    /**
     * 
     * @param a 
     * @return the underlying collection in the given array
     * @see Collection#toArray(T[]) 
     */
    public Object[] toArray(Object[] a) {
        return theCollection.toArray(a);
    }

    /**
     * 
     * @param e
     * @return
     * @throws AnnotationException if the object is invalid for addition to the collection
     * @see Collection#add(java.lang.Object) 
     */
    public boolean add(Object e) throws AnnotationException {
        checkValue(e);
        return theCollection.add(e);
    }

    /**
     * 
     * @param o
     * @return
     * @see Collection#remove(java.lang.Object) 
     */
    public boolean remove(Object o) {
        clearAttribute();
        return theCollection.remove(o);
    }

    /**
     * 
     * @param c
     * @return
     * @see Collection#containsAll(java.util.Collection) 
     */
    public boolean containsAll(Collection c) {
        return theCollection.containsAll(c);
    }

    /**
     * 
     * @param c
     * @return
     * @throws AnnotationException if any of the values is invalid to add to the collection
     * @see Collection#addAll(java.util.Collection) 
     */
    public boolean addAll(Collection c) throws AnnotationException {
        checkCollection(c);
        return theCollection.addAll(c);
    }

    /**
     * 
     * @param c
     * @return
     * @see Collection#removeAll(java.util.Collection) 
     */
    public boolean removeAll(Collection c) {
        clearAttribute();
        return theCollection.removeAll(c);
    }

    /**
     * 
     * @param c
     * @return
     * @see Collection#retainAll(java.util.Collection) 
     */
    public boolean retainAll(Collection c) {
        clearAttribute();
        return theCollection.retainAll(c);
    }

    /**
     * @see Collection#clear() 
     */
    public void clear() {
        clearAttribute();
        theCollection.clear();
    }

    // intended to be called only when serializing 
    /**
     * Do not call.  Intended to be called only when serializing.
     * @return
     */
    public Collection getCollection() {
        return theCollection;
    }

    /**
     * Replace the underlying Collection with a version with any non-Float 
     * numbers converted to Floats
     */
    protected abstract void fixFloatCollection();  
       
    }
