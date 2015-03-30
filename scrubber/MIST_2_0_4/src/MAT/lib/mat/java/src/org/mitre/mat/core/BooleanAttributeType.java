/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.mitre.mat.core;

import java.util.Collection;
import java.util.Iterator;
import java.util.Map;

/**
 *
 * @author robyn
 */
class BooleanAttributeType extends AttributeType {

    public BooleanAttributeType(Atype atype, String name) throws AnnotationException {
        super(atype, name);
        this.type = "boolean";
    }
    
    public BooleanAttributeType(Atype atype, String name, int aggregation) throws AnnotationException {
        this(atype, name, false, aggregation, false);
    }

     public BooleanAttributeType(Atype atype, String name, boolean optional, int aggregation, boolean distinguishing) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing);
        this.type = "boolean";
    }

     public BooleanAttributeType(Atype atype, String name, boolean optional, 
             int aggregation, boolean distinguishing, Boolean defaultVal) throws AnnotationException {
        super(atype, name, optional, aggregation, distinguishing, defaultVal, false);
        this.type = "boolean";
        manageDefaults();
    }

    @Override
    public AttributeType copy(Atype atype) throws AnnotationException {
        return new BooleanAttributeType(this.atype, this.name, this.optional, 
                this.aggregationType, this.distinguishingAttrForEquality, (Boolean)this.defaultValue);
    }

    @Override
    public boolean checkValue(Object v) {
        return checkBooleanValue(v);
    }
    
    public boolean checkBooleanValue(Object v) {
        if (v instanceof Boolean) {
            return true;
        } else if (v instanceof AttributeValueCollection) {
            return checkBooleanValue((AttributeValueCollection) v);
        } else {
            return false;
        }
    }
    
    public boolean checkBooleanValue(AttributeValueCollection v) {
        // check each value in the collection
        for (Iterator i = v.iterator(); i.hasNext();) {
            if (!checkBooleanValue(i.next())) {
                return false;
            }
        }
        // didn't find any bad values, so...
        return true;

    }

    @Override
    public boolean checkAndImportSingleValue(MATDocument doc, Object value) {
        // nothing special for import for booleans, so just check
        if (value == null) { // null is always acceptable
            return true;
        }
        return checkBooleanValue(value);
    }

    @Override
    // only has to do anything special for Annotation Attributes
    public void clearValue(MATDocument doc) {
        return;
    }

    @Override
    public Object digestSingleValueFromString(String val) {
        if (val == null) {
            return null;
        }
        if (val.equalsIgnoreCase("yes")) {
            return Boolean.TRUE;
        }
        return Boolean.valueOf(val);
    }

        @Override
    // allowable restrictions for string are only "choices"
    public void addRestrictions(Map restrictions) throws AnnotationException {
        for (Iterator i = restrictions.keySet().iterator(); i.hasNext(); ) {
            if ("choices".equals(i.next())) {
                this.setChoiceSet((Collection)restrictions.get("choices"));
            } else {
                throw new AnnotationException("invalid restriction for StringAttributeType");
            }
        }
    }

    private void setChoiceSet(Collection collection) {
        throw new UnsupportedOperationException("Not yet implemented");
    }

}
