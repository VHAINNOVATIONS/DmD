/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

/**
 * The class that represents an integer-valued attribute.  This attribute may optionally
 * have either or both of a minimum and/or maximum allowable value specified.  
 * Alternately, it may optionally provide a fixed list of choices to select among.  
 * It is an error for both restrictions to be provided.
 * An optional default value may be provided, or the value may default to the contents
 * of the annotated span of text.  If the latter, the value will be set to null if
 * the text span cannot be coerced to an integer.
 * 
 * @author robyn
 */
public class IntAttributeType extends AttributeType {

    private List<Integer> choices = null;
    private Integer minval = null;
    private Integer maxval = null;

    /**
     * Constructor
     * @param atype
     * @param name
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public IntAttributeType(Atype atype, String name, boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "int";
        setIsChoiceAttribute();
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param aggregation
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public IntAttributeType(Atype atype, String name, int aggregation) throws AnnotationException {
        this(atype, name, false, aggregation, false);
    }

    // using Integer rather than int even in the constructor allows them to be null if neeced
    /**
     * Constructor
     * @param atype
     * @param name
     * @param choices
     * @param minval
     * @param maxval
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public IntAttributeType(Atype atype, String name,
            Collection<Integer> choices, Integer minval, Integer maxval,
            boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        this(atype, name, choices, minval, maxval, optional, aggregation, distinguishing, null, false);
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param choices
     * @param minval
     * @param maxval
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @param defaultValue
     * @param defaultIsTextSpan
     * @throws AnnotationException
      * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
    */
    public IntAttributeType(Atype atype, String name,
            Collection<Integer> choices, Integer minval, Integer maxval,
            boolean optional, int aggregation, boolean distinguishing, Integer defaultValue,
            boolean defaultIsTextSpan) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing, defaultValue, defaultIsTextSpan);
        if (choices != null && (minval != null || maxval != null)) {
            throw new AnnotationException("You may not specify both choices and a range for an integer attribute");
        }
        this.type = "int";
        setChoicesAtCreate(choices);
        setIsChoiceAttribute();
        this.minval = minval;
        this.maxval = maxval;
        manageDefaults();
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @throws AnnotationException
     */
    public IntAttributeType(Atype atype, String name) throws AnnotationException {
        super(atype, name);
        this.type = "int";
        setIsChoiceAttribute();
    }

    @Override
    public AttributeType copy(Atype atype) throws AnnotationException {
        return new IntAttributeType(atype, this.name, this.choices,
                this.minval, this.maxval, this.optional, this.aggregationType,
                this.distinguishingAttrForEquality, (Integer) this.defaultValue,
                this.defaultIsTextSpan);
    }

    @Override
    public boolean checkValue(Object v) {
        return checkIntValue(v);
    }

    /**
     * Validates a candidate value to see if it meets the requirements of this
     * attribute type.  The candidate value may either be an Integer or an
     * AttributeValueCollection filled with integers.
     * @param v the candidate value
     * @return
     */
    public boolean checkIntValue(Object v) {
        if (v instanceof Integer) {
            return checkIntValue((Integer) v);
        } else if (v instanceof AttributeValueCollection) {
            return checkIntValue((AttributeValueCollection) v);
        } else {
            return false;
        }
    }

    /**
     * Validates an Integer candidate value to see if it meets the requirements 
     * of this attribute type.
     * @param v the candidate value
     * @return
     */
    public boolean checkIntValue(Integer v) {
        if (choices == null) {
            return checkRange(v);
        } else {
            return (choices.contains(v));
        }
    }

    private boolean checkRange(Integer v) {
        return ((minval == null || minval.compareTo(v) <= 0)
                && (maxval == null || maxval.compareTo(v) >= 0));
    }

    // if efficiency becomes an issue, cast i.next() here catch the possible
    // cast exception and return false
    /**
     * Validates a candidate collection to see if all of the values within it
     * meet the requirements of this attribute type.
     * @param v the candidate collection of values
     */
    public boolean checkIntValue(AttributeValueCollection v) {
        // check each value in the collection
        for (Iterator i = v.iterator(); i.hasNext();) {
            if (!checkIntValue(i.next())) {
                return false;
            }
        }
        // didn't find any bad values, so...
        return true;
    }

    @Override
    public boolean checkAndImportSingleValue(MATDocument doc, Object value) {
        // there's nothing special to do for import for an int so just check it
        if (value == null) { // null is always acceptable
            return true;
        }
        return checkIntValue(value);
    }

    @Override
    // only has to do anything special for Annotation Attributes
    public void clearValue(MATDocument doc) {
        return;
    }

    @Override
    public Object digestSingleValueFromString(String val) throws AnnotationException {
        if (val == null) {
            return null;
        }
        // System.out.println("trying to digest as Integer: " + val);

        try {
            return new Integer(val);
        } catch (NumberFormatException x) {
            throw new AnnotationException(val + " is not a valid int value");
        }
    }

    @Override
    // allowable restrictions for int are  "choices", "minval", "maxval" and "default"
    public void addRestrictions(Map restrictions) throws AnnotationException {
        // keep track of whether we've already added a choices or range restriction
        // so that we can raise an exception if the other if it is also specified
        boolean hasChoices = false;
        boolean hasRange = false;
        for (Iterator i = restrictions.keySet().iterator(); i.hasNext();) {
            String key = (String) i.next();
            if ("choices".equals(key)) {
                if (hasRange) {
                    throw new AnnotationException("You may not specify both choices and a range for an integer attribute");
                }
                this.setChoices((Collection) restrictions.get("choices"));
                setIsChoiceAttribute();
                if (choices != null) {
                    hasChoices = true;
                }
            } else if ("minval".equals(key)) {
                if (hasChoices) {
                    throw new AnnotationException("You may not specify both choices and a range for an integer attribute"); 
                }
                this.setMinval((Integer) restrictions.get("minval"));
                if (minval != null) {
                    hasRange = true;
                }
            } else if ("maxval".equals(key)) {
                if (hasChoices) {
                    throw new AnnotationException("You may not specify both choices and a range for an integer attribute"); 
                }
                this.setMaxval((Integer) restrictions.get("maxval"));
                if (maxval != null) {
                    hasRange = true;
                }
            } else {
                throw new AnnotationException("invalid restriction for IntAttributeType");
            }
        }
    }

    private void setIsChoiceAttribute() {
        this.isChoiceAttribute = ((this.choices != null) && (this.aggregationType == AttributeType.NONE_AGGREGATION));
    }

    // this has to be non-overridable since it is called in the constructor
    private void setChoicesAtCreate(Collection choices) throws AnnotationException {
        this.setChoices(choices);
    }

    /**
     * Set the collection of values that are valid choices for this attribute's value
     * @param choices
     * @throws AnnotationException
     */
    public void setChoices(Collection choices) throws AnnotationException {
        // if we're passed null or an empty collection, set choices to null
        if (choices == null || choices.isEmpty()) {
            this.choices = null;
            return;
        }
        // check that each is a String, there's nothing else to validate here 
        // since we are setting the only restriction strings can have for now
        // so calling checkStringValue would be more compute-intensive and is unnecessary 
        for (Iterator i = choices.iterator(); i.hasNext();) {
            if (!(i.next() instanceof Integer)) {
                throw new AnnotationException("invalid choice for IntAttributeType");
            }
        }
        this.choices = new ArrayList(choices);
        setIsChoiceAttribute();
    }

    /**
     * Set the minimum value allowed
     * @param number
     */
    public void setMinval(Integer number) {
        this.minval = number;
    }

    /**
     * Set the minimum value allowed
     * @param i
     */
    public void setMinval(int i) {
        this.minval = new Integer(i);
    }

    /**
     * Set the maximum value allowed
     * @param number
     */
    public void setMaxval(Integer number) {
        this.maxval = number;
    }

    /**
     * Set the maximum value allowed
     * @param i
     */
    public void setMaxval(int i) {
        this.maxval = new Integer(i);
    }
}
