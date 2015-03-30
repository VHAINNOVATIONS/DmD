/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.Map;

/**
 * The class that defines complex restrictions on annotation-valued attributes.
 * A complex restriction specifies an annotation type (label) along with a set
 * of attribute/value pairs that must be satisfied for an annotation of that type
 * to be an acceptable filler of the attribute to which this complex restriction
 * is attached.  The attributes named must all be "choice attributes" -- that is
 * string or int attributes for which the value is restricted to a pre-specified
 * list of choices.
 * 
 * @author robyn
 */
public class ComplexRestriction {

    private String label;
    private Map<String,Object> attrValRestrictions;

    /**
     * Constructor
     * @param label the required annotation type (label)
     * @param attrVal a Map from attribute names to their required values.
     */
    public ComplexRestriction(String label, Map<String,Object> attrVal) {
        this.attrValRestrictions = attrVal;
        this.label = label;
    }

    /**
     * Retrieve the Map of attribute/value restrictions
     * @return the Map of attribute/value restrictions
     */
    public Map<String,Object> getAttrValRestrictions() {
        return attrValRestrictions;
    }

    /**
     * Retrieve the annotation type (label)
     * @return the annotation type (label)
     */
    public String getLabel() {
        return label;
    }
}
