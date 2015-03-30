/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;
import java.util.ListIterator;

/**
 * A (non-abstract) subclass of AttributeValueCollection for Lists intended to be
 * used as an attribute value filler.  This class almost implements List
 * only not quite, because the add/set methods throw an AnnotationException if you
 * try to add something invalid to the List.  The class also tracks the
 * attribute and document this collection is for.

 * @author robyn
 */
public class AttributeValueList extends AttributeValueCollection
        // implements List (except not really, because I had to change the signature on some of the methods to throw the AnnotationException when the values are no good)
{

    /**
     * Constructor
     * @param ofDoc the MAT Document
     * @param ofAttribute the attribute of which this collection is a value
     */
    public AttributeValueList(MATDocument ofDoc, AttributeType ofAttribute) {
        super(ofDoc, ofAttribute);
        this.theCollection = new ArrayList();
    }

    /**
     * Basic Constructor
     */
    public AttributeValueList() {
        super();
        this.theCollection = new ArrayList();
    }
    
    /**
     * Constructor
     * @param theList the list of values
     */
    public AttributeValueList(List theList) {
        super();
        this.theCollection = theList;
    }

    private List theList() {
        return (List)theCollection;
    }
            
    @Override
    public AttributeValueCollection copy() {
        return new AttributeValueList(new ArrayList(theList()));
    }

    //implements List, sort of, and adds bookkeeping and checking needed *
   
    /** 
     * @param o
     * @return  
     * @see List#indexOf(java.lang.Object) 
     */
    
    public int indexOf(Object o) {
        return ((ArrayList)theCollection).indexOf(o);
    }

    /**
     * 
     * @param o
     * @return
     * @see List#lastIndexOf(java.lang.Object) 
     */
    public int lastIndexOf(Object o) {
        return ((ArrayList)theCollection).lastIndexOf(o);
    }

    /**
     * 
     * @return
     * @see List#listIterator() 
     */
    public ListIterator listIterator() {
        return ((ArrayList)theCollection).listIterator();
    }

    /**
     * 
     * @param index
     * @return
     * @see List#listIterator(int) 
     */
    public ListIterator listIterator(int index) {
        return ((ArrayList)theCollection).listIterator(index);
    }

    /**
     * 
     * @param fromIndex
     * @param toIndex
     * @return
     * @see List#subList(int, int) 
     */
    public List subList(int fromIndex, int toIndex) {
        return ((ArrayList)theCollection).subList(fromIndex, toIndex);
    }

    /**
     * 
     * @param index
     * @param c
     * @return
     * @throws AnnotationException if any of the values is unacceptable
     * @see List#addAll(int, java.util.Collection) 
     */
    public boolean addAll(int index, Collection c) throws AnnotationException {
        checkCollection(c);
        return ((ArrayList)theCollection).addAll(index, c);
    }

    /**
     * 
     * @param index
     * @return
     * @see List#get(int) 
     */
    public Object get(int index) {
        return ((ArrayList)theCollection).get(index);
    }

    /**
     * 
     * @param index
     * @param element
     * @return
     * @throws AnnotationException if the element is unacceptable as a value for this attribute
     * @see List#set(int, java.lang.Object) 
     */
    public Object set(int index, Object element) throws AnnotationException {
        checkValue(element, true);
        return ((ArrayList)theCollection).set(index, element);
    }

    /**
     * 
     * @param index
     * @param element
     * @throws AnnotationException if the element is unacceptable as a value for this attribute
     * @see List#add(int, java.lang.Object) 
     */
    public void add(int index, Object element) throws AnnotationException {
        checkValue(element);
        ((ArrayList)theCollection).add(index, element);
    }

    /**
     * 
     * @param index
     * @return
     * @see List#remove(java.lang.Object) 
     */
    public Object remove(int index) {
        clearAttribute();
        return ((ArrayList)theCollection).remove(index);
    }
    
    protected void fixFloatCollection() {
        ArrayList newList = new ArrayList(theCollection.size());
         for (Iterator i = theCollection.iterator(); i.hasNext();) {
            Object value = i.next();
            if (!(value instanceof Float) && (value instanceof Number)) {
                value = new Float(((Number)value).floatValue());
            }
            newList.add(value);
        }
        theCollection = newList;
    }
    
}
