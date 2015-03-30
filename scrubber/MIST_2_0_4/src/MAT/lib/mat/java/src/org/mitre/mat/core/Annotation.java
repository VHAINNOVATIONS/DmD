/*
 * Copyright (C) 2009 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.Comparator;
import java.util.List;

/**
 * The core object that corresponds to a span annotation.
 * The attribute values are a sequence of Objects, which pair
 * up with the attributes in the attribute List.
 */
public class Annotation extends AnnotationCore {

    private String text = null;
    private int startIndex;
    private int endIndex;

    /**
     * Constructor that takes a list of attribute values to assign.
     * @param doc the MAT document
     * @param parent the parent Atype
     * @param start  the start offset
     * @param end the end offset
     * @param valsList the list of attribute values, in the order that the
     *                 attributes are listed in the Atype
     * @throws AnnotationException
     */
    public Annotation(MATDocument doc, Atype parent,
            int start, int end, List valsList) throws AnnotationException {
        // ok, here's the thing:  the superclass initializes all of the default values
        // but it fails to initialize the span-valued defaults because start and end
        // haven't been set yet
        // and I can't set start and end until after I call the super constructor
        // because that can only be called first
        // so, sadly, AnnotationCore is going to have to have a constructor that
        // takes the start and end and sets them before doing and default stuff
        super(doc, parent, start, end, valsList);
        /** this now happens in the constructor and not here
        this.startIndex = start;
        this.endIndex = end;
         */
    }

    /**
     * Basic constructor
     * @param doc the MAT document
     * @param parent the parent Atype
     * @param start  the start offset
     * @param end the end offset
    * @throws AnnotationException
     */
    public Annotation(MATDocument doc, Atype parent, int start, int end) throws AnnotationException {
        this(doc, parent, start, end, new java.util.ArrayList());
    }

    /**
     * Retrieve the text annotated by this annotation
     * @return a String representing the signal text between the start index
     *         (inclusive) and the end index (exclusive).
     */
    public String getAnnotationText() {
        if (this.text == null) {
            String signal = (this.getDoc()).getSignal();
            this.text = signal.substring(this.startIndex, this.endIndex);
        }
        return this.text;
    }

    /**
     * Retrieve the start index of this annotation
     * @return the start index
     */
    public int getStartIndex() {
        return this.startIndex;
    }

    /**
     * Retrieve the end index of this annotation
     * @return the end index
     */
    public int getEndIndex() {
        return this.endIndex;
    }

    /**
     * Set the start index of this annotation
     * @param i the desired start index
     */
    public void setStartIndex(int i) {
        this.startIndex = i;
    }

    /**
     * Set the end index of this annotation
     * @param i the desired end index
     */
    public void setEndIndex(int i) {
        this.endIndex = i;
    }

    /**
     * compares annotations according to their locations in the document
     * if start indices differ, the annotation with the larger start index is greater
     *   if start indices are the same, the annotation with the larger end index is greater
     *   if annotations are co-located but not equal, they are sorted according to hashcode
     *      in order to maintain am ordering consistent with equals
     */
    static class AnnotationComparator implements  Comparator<Annotation> {

        public int compare(Annotation a1, Annotation a2) {
            if (a1.equals(a2)) {
                return 0;
            }
            int a1start = a1.getStartIndex();
            int a2start = a2.getStartIndex();
            if (a1start < a2start) {
                return -1;
            } else if (a1start > a2start) {
                return 1;
            } else {
                // the two annots have the same start index
                int a1end = a1.getEndIndex();
                int a2end = a2.getEndIndex();
                if (a1end < a2end) {
                    return -1;
                } else if (a2end < a1end) {
                    return 1;
                } else {
                    // start and end are the same, but the annots are not equal
                    // if a1's hashcode is smaller, will return a negative number
                    // to indicate that a1 < a2 and vice versa
                    return (a1.hashCode() - a2.hashCode());
                }
            }
        }
        
        
    }
    

}
