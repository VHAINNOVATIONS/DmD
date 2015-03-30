/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.Collection;
import java.util.Iterator;
import java.util.Map;

/**
 * The class that represents a float-valued attribute.  This attribute may optionally
 * have either or both of a minimum and/or maximum allowable value specified.
 * @author robyn
 */
public class FloatAttributeType extends AttributeType {

    private Float minval = null;
    private Float maxval = null;

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
    public FloatAttributeType(Atype atype, String name, boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "float";
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param minval
     * @param maxval
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public FloatAttributeType(Atype atype, String name, Float minval, Float maxval,
            boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "float";
        this.minval = minval;
        this.maxval = maxval;
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param minval
     * @param maxval
     * @param optional
     * @param aggregation
     * @param distinguishing
     * @param defaultValue
     * @param defaultIsTextValue
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public FloatAttributeType(Atype atype, String name, Float minval, Float maxval,
            boolean optional, int aggregation, boolean distinguishing, Float defaultValue, 
            boolean defaultIsTextValue) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing, defaultValue, defaultIsTextValue);
        this.type = "float";
        this.minval = minval;
        this.maxval = maxval;
        manageDefaults();
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @param aggregation
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public FloatAttributeType(Atype atype, String name, int aggregation) throws AnnotationException {
        this(atype, name, false, aggregation, false);
    }

    /**
     * Constructor
     * @param atype
     * @param name
     * @throws AnnotationException
     * @see AttributeType#AttributeType(org.mitre.mat.core.Atype, java.lang.String, boolean, int, boolean, java.lang.Object, boolean) 
     */
    public FloatAttributeType(Atype atype, String name) throws AnnotationException {
        super(atype, name);
        this.type = "float";
    }

    @Override
    public AttributeType copy(Atype atype) throws AnnotationException {
        return new FloatAttributeType(atype, this.name, this.minval, this.maxval,
                this.optional, this.aggregationType, this.distinguishingAttrForEquality,
                (Float)this.defaultValue, this.defaultIsTextSpan);
    }

    @Override
    public boolean checkValue(Object v) {
        return checkFloatValue(v);
    }

    private boolean checkFloatValue(Object v) {
        if (v instanceof Float) {
            return checkFloatValue((Float) v);
          /*** let's not allow Integers even though maybe that's ok?
        } else if (v instanceof Integer) {
            // we can live with Integers as well, as long as the value is ok
            return checkFloatValue(((Integer)v).floatValue());
           * ***/
        } else if (v instanceof AttributeValueCollection) {
            return checkFloatValue((AttributeValueCollection) v);
        } else {
            return false;
        }
    }

    private boolean checkFloatValue(Float v) {
        if (minval != null && minval.compareTo(v) > 0) {
            return false;
        }
        if (maxval != null && maxval.compareTo(v) < 0) {
            return false;
        }
        return true;
    }

    private boolean checkFloatValue(AttributeValueCollection v) {
        // check each value in the collection
        for (Iterator i = v.iterator(); i.hasNext();) {
            if (!checkFloatValue(i.next())) {
                return false;
            }
        }
        // didn't find any bad values, so...
        return true;
    }

    @Override
    public boolean checkAndImportSingleValue(MATDocument doc, Object value) {
        // nothing special needed for import; just check
        if (value == null) { // null is always acceptable
            return true;
        }
        return checkFloatValue(value);
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
        // System.out.println("trying to digest as Float: " + val);
        try {
            return Float.valueOf(val);
        } catch (NumberFormatException x) {
            throw new AnnotationException(val + " is not a valid float value");
        }

    }

    @Override
    // allowable restrictions for float are only minval and maxval
    public void addRestrictions(Map restrictions) throws AnnotationException {
        for (Iterator i = restrictions.keySet().iterator(); i.hasNext();) {
            Object value = i.next();
            if ("minval".equals(value)) {
                this.setMinval((Float) restrictions.get("minval"));
            } else if ("maxval".equals(value)) {
                this.setMaxval((Float) restrictions.get("maxval"));
            } else {
                throw new AnnotationException("invalid restriction for FloatAttributeType");
            }
        }
    }

    private void setMinval(Float aFloat) {
        this.minval = aFloat;
    }

    private void setMaxval(Float aFloat) {
        this.maxval = aFloat;
    }
}
