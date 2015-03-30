/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.Collection;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * A (non-abstract) subclass of AttributeValueCollection for Sets intended to be
 * used as an attribute value filler.  This class almost implements Set
 * only not quite, because the add methods throw an AnnotationException if you
 * try to add something invalid to the Set.  The class also tracks the
 * attribute and document this collection is for.

 * @author robyn
 */
public class AttributeValueSet extends AttributeValueCollection // implements Set (except not really, because I had to change the signature on some of the methods to throw the AnnotationException when the values are no good)
{

    /**
     * Constructor
     * @param ofDoc
     * @param ofAttribute
     */
    public AttributeValueSet(MATDocument ofDoc, AttributeType ofAttribute) {
        super(ofDoc, ofAttribute);
        this.theCollection = new LinkedHashSet();
    }

    /**
     * Basic Constructor
     */
    public AttributeValueSet() {
        super();
        this.theCollection = new LinkedHashSet();
    }

    /**
     * Constructor
     * @param theSet
     */
    public AttributeValueSet(Set theSet) {
        super();
        this.theCollection = theSet;
    }

    private Set theSet() {
        return (Set) theCollection;
    }

    @Override
    public AttributeValueCollection copy() {
        return new AttributeValueSet(new LinkedHashSet(theSet()));
    }

    protected void fixFloatCollection() {
        LinkedHashSet newSet = new LinkedHashSet(theCollection.size());
        for (Iterator i = theCollection.iterator(); i.hasNext();) {
            Object value = i.next();
            if (!(value instanceof Float) && (value instanceof Number)) {
                value = new Float(((Number) value).floatValue());
            }
            newSet.add(value);
        }
        theCollection = newSet;
    }
}
