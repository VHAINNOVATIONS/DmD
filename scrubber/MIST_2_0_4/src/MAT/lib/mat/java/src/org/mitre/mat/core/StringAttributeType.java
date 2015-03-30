/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The class that represents a string-valued attribute.  This attribute may
 * optionally provide a fixed list of choices to select among.  
 * An optional default value may be provided, or the value may default to the contents
 * of the annotated span of text.  If the latter, the value will be set to null if
 * the text span is an unsuitable value.
 *
 * @author robyn
 */
public class StringAttributeType extends AttributeType {

    // if someone tries to set choices to an empty collection, it will be set
    // to null instead, which indicates no restriction
    // it is not possible to set choices to an empty set of choices, as that would be stupid
    private List<String> choices = null;

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
    public StringAttributeType(Atype atype, String name, boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "string";
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
    public StringAttributeType(Atype atype, String name, int aggregation) throws AnnotationException {
        this(atype, name, false, aggregation, false);
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public StringAttributeType(Atype atype, String name) throws AnnotationException {
        super(atype, name);
        this.type = "string";
        setIsChoiceAttribute();
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param choices
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public StringAttributeType(Atype atype, String name, Collection choices,
            boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "string";
        setChoicesAtCreate(choices);
        setIsChoiceAttribute();
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param choices
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @param defaultValue
     * @param defaultIsTextSpan
     * @throws AnnotationException
      * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
    */
    public StringAttributeType(Atype atype, String name, Collection choices,
            boolean optional, int aggregation, boolean distinguishing, String defaultValue, boolean defaultIsTextSpan) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing, defaultValue, defaultIsTextSpan);
        this.type = "string";
        setChoicesAtCreate(choices);
        setIsChoiceAttribute();
        manageDefaults();
    }

    @Override
    public AttributeType copy(Atype atype) throws AnnotationException {
        return new StringAttributeType(atype, this.name, this.choices, this.optional,
                this.aggregationType, this.distinguishingAttrForEquality,
                (String) this.defaultValue, this.defaultIsTextSpan);

    }

    @Override
    // will call the Collection or single value version of checkStringValue
    // according to the type of v
    public boolean checkValue(Object v) {
        return checkStringValue(v);
    }

    @Override
    public boolean checkAndImportSingleValue(MATDocument doc, Object value) {
        // there's nothing special to do for a string import, so just check it
        if (value == null) { // null is always acceptable
            return true;
        }

        return checkStringValue(value);
    }

    @Override
    // only has to do anything special for Annotation Attributes
    public void clearValue(MATDocument doc) {
        return;
    }

    @Override
    public Object digestSingleValueFromString(String val) {
        return val;
    }

    private void setIsChoiceAttribute() {
        this.isChoiceAttribute = ((this.choices != null) && (this.aggregationType == AttributeType.NONE_AGGREGATION));
    }
    
    private boolean checkStringValue(String v) {
        if (hasChoices()) {
            return choices.contains(v);
        } else {
            return true;
        }
    }

    private boolean checkStringValue(AttributeValueCollection v) {
        // check each value in the collection
        for (Iterator i = v.iterator(); i.hasNext();) {
            if (!checkStringValue(i.next())) {
                return false;
            }
        }
        // didn't find any bad values, so...
        return true;
    }

    // casts any uncast values to call the correct overloaded version of
    // checkStringValue, and returns false if v is not a String or
    // AttributeValueCollection
    private boolean checkStringValue(Object v) {
        if (v == null) {
            return true; // null is always an acceptable value
        }
        if (v instanceof String) {
            return checkStringValue((String) v);
        } else if (v instanceof AttributeValueCollection) {
            return checkStringValue((AttributeValueCollection) v);
        } else {
            return false;
        }
    }

    // this needs to be non-overridable because it is used in the constructor
    private void setChoicesAtCreate(Collection choices) throws AnnotationException {
        this.setChoices(choices);
    }
    
    /**
     * Set the list of choices of allowable values for this attribute.
     * @param choices
     * @throws AnnotationException if any of the items in choices are not Strings
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
            if (!(i.next() instanceof String)) {
                throw new AnnotationException("invalid choice for StringAttributeType");
            }
        }
        this.choices = new ArrayList(choices);
        setIsChoiceAttribute();
    }

    /**
     * retrieve the List of choices of allowable values for this attribute.
     * @return the List of choices of allowable values for this attribute.
     */
    public List getChoices() {
        return choices;
    }

    /**
     * 
     * @return true if this attributes values are restricted to a specific list 
     * of choices, false otherwise
     */
    public boolean hasChoices() {
        return (choices != null);
    }

    @Override
    // allowable restrictions for string are only "choices"
    public void addRestrictions(Map restrictions) throws AnnotationException {
        for (Iterator i = restrictions.keySet().iterator(); i.hasNext();) {
            if ("choices".equals(i.next())) {
                this.setChoices((Collection) restrictions.get("choices"));
            } else {
                throw new AnnotationException("invalid restriction for StringAttributeType");
            }
        }
    }
}
