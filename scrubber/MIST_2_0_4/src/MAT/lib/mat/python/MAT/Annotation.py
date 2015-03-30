# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# These are the local annotation and annotation type objects.
# They are stubs for the situation where we aren't using AMS,
# which has its own annotation and annotation type objects.
# The wrapper code is identical to AMS.

#
# Annotation types
#

# These are loaded on demand. I keep a list of the
# types (for mapping from indices to types) and a
# table of the types (for mapping from names to types).
# I do the same for the attributes for each annotation type.

class AnnotationError(Exception):
    pass

from types import StringType, ListType, IntType, DictionaryType, UnicodeType

# The legal types will be: string, int, float (double), boolean, annotation.
# The legal aggregations will be: none, list, set

# There's one oddity: because I need to know about annotations which are
# attribute values, I can't set an attribute value to a normal list of annotations
# using __setitem__, because then any adds or appends won't do the right thing.
# So I really, actually, need separate classes - either that or not actually
# setting the value that's passed, which also seems wrong. Ditto sets.

# Actually, this isn't good enough. Unlike Java, I don't have the ability to
# enforce a value type with ordinary values. So perhaps I need to do this for
# ALL aggregations? After all, .append() and .add() have to do the right thing
# for lists of ints, etc.

class AttributeValueSequence:

    def __init__(self):
        self.ofDocAndAttribute = None
        
    # Reusing for a different attribute. ofDocAndAttribute should be None.
    def copy(self):
        return self.__class__(self)

    # Now, we have to make sure that we check
    # the values, and do the right thing 
    def _setAttribute(self, doc, attr):
        self.ofDocAndAttribute = (doc, attr)
        for val in self:
            if not attr._checkAndImportSingleValue(doc, val):
                raise AnnotationError, ("candidate value %s value of element of attribute '%s' must be a %s and meet the other requirements" % (str(val), attr.name, attr._typename_))

    def _checkAttribute(self, doc, attr):
        for val in self:
            if not attr._checkSingleValue(doc, val):
                raise AnnotationError, ("candidate value %s of element of attribute '%s' must be a %s and meet the other requirements" % (str(val), attr.name, attr._typename_))

    def _checkVal(self, v, clear = False):
        if self.ofDocAndAttribute:
            doc, attr = self.ofDocAndAttribute
            if clear and attr._clearValue:
                attr._clearValue(doc)
            if not attr._checkAndImportSingleValue(doc, v):
                raise AnnotationError, ("candidate value %s of element of attribute '%s' must be a %s and meet the other requirements" % (str(v), attr.name, attr._typename_))
            
    def _checkSeq(self, vl, clear = False):
        if self.ofDocAndAttribute:
            doc, attr = self.ofDocAndAttribute
            if clear and attr._clearValue:
                attr._clearValue(doc)
            for v in vl:
                if not attr._checkAndImportSingleValue(doc, v):
                    raise AnnotationError, ("candidate value %s of element of attribute '%s' must be a %s and meet the other requirements" % (str(v), attr.name, attr._typename_))

    def _clearAttr(self):
        if self.ofDocAndAttribute:
            doc, attr = self.ofDocAndAttribute
            if attr._clearValue:
                attr._clearValue(doc)

class AttributeValueList(AttributeValueSequence, list):

    def __init__(self, *args, **kw):
        list.__init__(self, *args, **kw)
        AttributeValueSequence.__init__(self)

    # __setitem__, __setslice__, __delitem__, __delslice__
    # append, extend, insert, pop, remove, __iadd__

    def __setitem__(self, key, value):
        self._checkVal(value, clear = True)
        return list.__setitem__(self, key, value)

    def __setslice__(self, i, j, sequence):
        self._checkSeq(sequence, clear = True)
        return list.__setslice__(self, i, j, sequence)

    def __delitem__(self, key):
        self._clearAttr()
        return list.__delitem__(self, key)

    def __delslice__(self, i, j):
        self._clearAttr()
        return list.__delslice__(self, i, j)

    def append(self, other):
        self._checkVal(other, clear = True)
        return list.append(self, other)

    def extend(self, other):
        self._checkSeq(other, clear = True)
        return list.extend(self, other)

    __iadd__ = extend
    
    def insert(self, i, val):
        self._checkVal(val, clear = True)
        return list.insert(self, i, val)

    def pop(self, *args):
        self._clearAttr()
        return list.pop(*args)

    def remove(self, elt):
        self._clearAttr()
        return list.remove(self, elt)        

class AttributeValueSet(AttributeValueSequence, set):

    def __init__(self, *args, **kw):
        set.__init__(self, *args, **kw)
        AttributeValueSequence.__init__(self)

    # update, __ior__, intersection_update, __iand__, difference_update, __isub__,
    # symmetric_difference_update, __ixor__
    # add, remove, discard, pop, clear
    # I think that's all the ones that modify a set.

    def __ior__(self, other):
        self._checkSeq(other, clear = True)
        return set.__ior__(self, other)

    def __iand__(self, other):
        self._clearAttr()
        return set.__iand__(self, other)

    def __isub__(self, other):
        self._clearAttr()
        return set.__isub__(self, other)

    def __ixor__(self, other):
        self._checkSeq(other, clear = True)
        return set.__ixor__(self, other)

    def update(self, *others):
        self._clearAttr()
        for o in others:
            self._checkSeq(o)
        return set.update(self, *others)

    def intersection_update(self, *others):
        self._clearAttr()
        return set.intersection_update(self, *others)

    def difference_update(self, *others):
        self._clearAttr()
        return set.difference_update(self, *others)
        
    symmetric_difference_update = __ixor__

    def add(self, elem):
        self._checkVal(elem, clear = True)
        return set.add(self, elem)

    def remove(self, elem):
        self._clearAttr()
        return set.remove(self, elem)

    def discard(self, elem):
        self._clearAttr()
        return set.discard(self, elem)

    def pop(self):
        self._clearAttr()
        return set.pop(self)

    def clear(self):
        self._clearAttr()
        return set.clear(self)

# How to store the behavior for the attributes? We want to:
# - see if the value is a legal value
# - process the value for setting
# - convert from and to strings for MATReport, XML attribute vals, etc.
# But the problem is that fancy stuff happens for aggregations of annotations,
# as for annotations themselves. Do I need to worry about that? Yes, because
# if I'm setting a value, or importing, I need to know I have a list, because
# I don't want to flush the annotation hashes multiple times.
# But actually, they DO want to be instances, because they have
# different things like options, etc.

class AttributeType(object):

    def __init__(self, atype, name, optional = False, aggregation = None,
                 distinguishing_attribute_for_equality = False, default = None,
                 default_is_text_span = False):
        self.atype = atype
        self.name = name
        self.optional = optional
        self.aggregation = aggregation
        # Usually false. If there's an effective label for the type,
        # that attribute will also be distinguishing.
        self.distinguishingAttributeForEquality = distinguishing_attribute_for_equality
        self.effectiveLabelAttribute = False
        if aggregation is not None:
            if aggregation not in ("list", "set", "none"):
                raise AnnotationError, "unknown attribute aggregation type '%s'" % aggregation
            if aggregation == "none":
                self.aggregation = None
        self._clearValue = None
        self.hasDefault = False
        self.default = default
        self.defaultIsTextSpan = default_is_text_span
        # See _choiceAttributeOK below.
        self._choiceAttribute = False

    # Has to be called after _checkSingleValue is set.
    def _computeMethods(self):
        if self.aggregation is None:
            self._checkValue = self._checkSingleValue
            self._importValue = self._importSingleValue
            self._checkAndImportValue = self._checkAndImportSingleValue
            if hasattr(self, "_toStringSingleValue"):
                self.toStringNonNull = self._toStringSingleValue
            else:
                # Don't want to introduce two layers of function calls
                # if I can get away with it.
                self.toStringNonNull = unicode
        elif self.aggregation == "list":
            self._checkValue = self._checkListValue
            self._checkAndImportValue = self._checkAndImportListValue
            self._importValue = self._importSequenceValue
            self.toStringNonNull = self._toStringSequenceValue
        elif self.aggregation == "set":
            self._checkValue = self._checkSetValue
            self._checkAndImportValue = self._checkAndImportSetValue
            self._importValue = self._importSequenceValue
            self.toStringNonNull = self._toStringSequenceValue

    def _manageDefaults(self):
        default = self.default
        default_is_text_span = self.defaultIsTextSpan
        if (default is not None) or default_is_text_span:
            if (default is not None) and default_is_text_span:
                raise AnnotationError, ("can't declare both default and default_is_text_span for attribute '%s'" % self.name)
            if self.aggregation:
                raise AnnotationError, ("can't declare default for aggregated %s attribute '%s'" % (self._typename_, self.name))
            if default is not None:
                # We won't need the doc in checkSingleValue here, which is good,
                # because we don't have it.
                if not self._checkSingleValue(None, default):
                    raise AnnotationError, ("default for %s attribute '%s' does not meet the attribute requirements" % (self._typename_, self.name))
                self._getAttributeDefault = lambda a: self.default
            else:
                if not self.atype.hasSpan:
                    raise AnnotationError, ("can't use text span as default for attribute '%s' of spanless annotation type '%s'" % (self.name, self.atype.lab))
                # Gotta coerce.
                self._getAttributeDefault = self._extractAndCoerceTextExtent
            self.hasDefault = True

    # This used to insist that the value be not None (i.e., that it can be parsed). But
    # John Aberdeen has pointed out to me that this is too restrictive. And if it digests
    # a value that matches the type, but that value doesn't match the finer-grained restrictions,
    # that should be None, too.
    def _extractAndCoerceTextExtent(self, annot):
        s = self._digestSingleValueFromString(annot.doc.signal[annot.start:annot.end])
        if (s is not None) and (not self._checkSingleValue(annot.doc, s)):
            s = None
        return s
    
    def toString(self, v):
        if v is None:
            return "(null)"
        else:
            return self.toStringNonNull(v)
    
    # Not going to worry about escaping the commas - this isn't
    # supposed to be robust.
    
    def _toStringSequenceValue(self, v):
        return ",".join([((hasattr(self, "_toStringSingleValue") and self._toStringSingleValue) or str)(x) for x in v])        
            
    def copy(self, atype = None):
        raise AnnotationError, "undefined"

    # Depending on the properties of the attribute types, we're
    # going to set this method to one of the specialized methods
    # that are defined for the given attribute type.

    def _checkSingleValue(self, doc, v):
        raise AnnotationError, "undefined"

    # Guaranteed not to be None.
    def _checkValue(self, doc, v):
        raise AnnotationError, "undefined"
    
    def _checkListValue(self, doc, v):
        if not isinstance(v, AttributeValueList):
            raise AnnotationError, ("value of attribute '%s' must be an AttributeValueList of %s" % (self.name, self._typename_))
        if (v.ofDocAndAttribute is not None) and (v.ofDocAndAttribute != (doc, self)):
            raise AnnotationError, "can't reuse list value attributes"
        v._checkAttribute(doc, self)
        return True

    def _checkSetValue(self, doc, v):
        if not isinstance(v, AttributeValueSet):
            raise AnnotationError, ("value of attribute '%s' must be an AttributeValueSet of %s" % (self.name, self._typename_))
        if (v.ofDocAndAttribute is not None) and (v.ofDocAndAttribute != (doc, self)):
            raise AnnotationError, "can't reuse set value attributes"
        v._checkAttribute(doc, self)
        return True

    def _checkAndImportListValue(self, doc, v):
        if not isinstance(v, AttributeValueList):
            raise AnnotationError, ("value of attribute '%s' must be an AttributeValueList of %s" % (self.name, self._typename_))
        if (v.ofDocAndAttribute is not None) and (v.ofDocAndAttribute != (doc, self)):
            raise AnnotationError, "can't reuse list value attributes"
        v._setAttribute(doc, self)
        return True

    def _checkAndImportSetValue(self, doc, v):
        if not isinstance(v, AttributeValueSet):
            raise AnnotationError, ("value of attribute '%s' must be an AttributeValueSet of %s" % (self.name, self._typename_))
        if (v.ofDocAndAttribute is not None) and (v.ofDocAndAttribute != (doc, self)):
            raise AnnotationError, "can't reuse set value attributes"
        v._setAttribute(doc, self)
        return True

    # These are only called when we've already computed the type, and don't
    # need to check it.
    
    def _importValue(self, doc, v):
        pass

    def _importSequenceValue(self, doc, v):
        for val in v:
            self._importSingleValue(doc, val)

    def _importSingleValue(self, doc, v):
        pass

    def _digestSingleValueFromString(self, v):
        return v

    def toJSON(self):
        d = {"name": self.name, "type": self._typename_, "aggregation": self.aggregation}
        if self.default is not None:
            d["default"] = self.default
        if self.defaultIsTextSpan:
            d["default_is_text_span"] = True
        return d

    # This is general functionality for all
    # singleton choice attributes. If you're about to
    # change one of these values, you need to know if it
    # CAN be changed - and it can be changed if the annotation
    # isn't attached to anything, or if the resulting
    # set of choice attributes satisfy SOME restriction
    # on EACH of the places it's attached to.    

    def _choiceAttributeOK(self, annot, candidateVal):
        if not self._choiceAttribute:
            # Shouldn't be called in this case, but whatever.
            return True
        else:
            atr = annot.doc.atypeRepository
            atr._buildInverseIdDict()
            refs = atr._inverseIdDict.get(annot.id)
            if not refs:
                return True
            else:
                # So now we have a set of refs, and what I need
                # to do is grab the label and choice vals
                # from the annot, ladle the candidate on top,
                # and make sure that the result satisfies at least
                # one set of restrictions for each reference.
                # I only need the label and choice vals because
                # only choice vals can be part of the label
                # restrictions.
                d = dict([(attrObj.name, attr) for (attrObj, attr)
                          in zip(annot.atype.attr_list, annot.attrs)
                          if attrObj._choiceAttribute])
                d[self.name] = candidateVal
                for parentAnnot, parentAName, ignore in refs:
                    parentAtype = parentAnnot.atype.attr_list[parentAnnot.atype.attr_table[parentAName]]
                    if not parentAtype._choicesSatisfyRestrictions(annot.atype.lab, d):
                        return False
                return True

    # Moved this here from the global repository. Only called by string and int attributes.
    # It's a little nuts that the actionable portion of this info is stored
    # in the repository, not on the attribute or the atype, but for the moment,
    # there it is.
    
    def declareEffectiveLabels(self, effective_labels):
        for otherAttr in self.atype.attr_list:
            if (otherAttr is not self) and otherAttr.effectiveLabelAttribute:
                raise AnnotationError, ("annotation type '%s' already has effective label attribute '%s'" % \
                                        (self.atype.lab, otherAttr.name))
        if self.aggregation is not None:
            raise AnnotationError, ("effective labels defined on a non-singleton attribute %s" % self.name)
        if self._typename_ not in ("string", "int"):
            raise AnnotationError, ("effective labels defined on a non-string, non-int attribute %s" % self.name)
        if self.choices is None:
            raise AnnotationError, ("effective labels defined on an attribute %s without choices" % self.name)
        if set(effective_labels.keys()) - self.choices:
            raise AnnotationError, ("effective labels defined on unknown attribute values on attribute %s" % self.name)
        if self.choices != set(effective_labels.keys()):
            raise AnnotationError, ("some, but not all, choices for attribute '%s' have effective labels" % self.name)
        trueLabel = self.atype.lab
        attr = self.name
        for val, eName in effective_labels.items():
            if val is None:
                raise AnnotationError, ("found an effective label %s whose attribute value is null" % eName)
            else:
                if type(val) in (str, unicode):
                    tval = self._digestSingleValueFromString(val)
                    if tval is None:
                        raise AnnotationError, ("value '%s' can't be digested into the proper type (%s) for attribute %s of label %s for effective label %s" %
                                                (val, self._typename_, attr, trueLabel, eName))
                    val = tval
                # Now, check the value.
                if not self._checkSingleValue(None, val):
                    raise AnnotationError, ("value %s is not a legal value for attribute %s of label %s for effective label %s" %
                                            (val, attr, trueLabel, eName))
                # We already have this implemented on the repository, and while
                # I wanted to move around the code in the XML to make the definition
                # cleaner, I don't really have time to move around the underlying implementation.
                self.atype.repository.recordEffectiveLabel(val, attr, trueLabel, eName)
        # Make sure of this.
        self.distinguishingAttributeForEquality = True
        self.effectiveLabelAttribute = True

class StringAttributeType(AttributeType):

    _typename_ = "string"

    # Grrr. I can't use regexes, because they're compiled differently depending
    # on the programming language. Let's disable them for now.

    def __init__(self, attr, name, choices = None, effective_labels = None,
                 regexes = None, **kw):
        AttributeType.__init__(self, attr, name, **kw)        
        self.choices = None
        if choices:
            # Don't use all() - it evaluates the entire list comprehension argument.
            for c in choices:
                if type(c) not in (str, unicode):
                    raise AnnotationError, ("not all choices for attribute '%s' are strings" % self.name)
            self.choices = set(choices)
            self._choicesForJSON = choices            
        if self.choices and (self.aggregation is None):
            self._choiceAttribute = True
        self.regexes = None
        if regexes:
            raise AnnotationError, "regexes temporarily disabled due to programming language incompatibilities"
            import re
            # If it's already a regex, compile returns it.
            self.regexes = [re.compile(r) for r in regexes]
        whichMethod = {
            (True, True): self._checkTypeAlone,
            (False, True): self._checkChoices,
            (True, False): self._checkRegexesAndType,
            (False, False): self._checkChoicesOrRegexes
            }
        
        self._checkSingleValue = whichMethod[(self.choices is None, self.regexes is None)]
        self._checkAndImportSingleValue = self._checkSingleValue
        self._computeMethods()
        # This has to be handled after the methods are computed.
        self.effective_labels = effective_labels
        if effective_labels is not None:
            self.declareEffectiveLabels(effective_labels)
        self._manageDefaults()

    def _checkTypeAlone(self, doc, v):
        return type(v) in (str, unicode)

    # We've already checked the types of the choices, so we don't
    # need to check the type of the element.
    def _checkChoices(self, doc, v):
        return v in self.choices

    def _checkRegexesAndType(self, doc, v):
        if type(v) not in (str, unicode):
            return False
        for r in self.regexes:
            if r.search(v):
                return True
        return False

    # I'm not just calling _checkChoices or _checkRegexesAndType, because
    # I'm assuming that this needs to be as fast as possible, so no
    # additional function calls.
    
    def _checkChoicesOrRegexes(self, doc, v):
        if v in self.choices:
            return True
        if type(v) not in (str, unicode):
            return False
        for r in self.regexes:
            if r.search(v):
                return True
        return False

    def copy(self, atype = None):
        return StringAttributeType(atype or self.atype, self.name, optional = self.optional,
                                   aggregation = self.aggregation,
                                   default = self.default, choices = self.choices,
                                   effective_labels = self.effective_labels,
                                   default_is_text_span = self.defaultIsTextSpan,
                                   regexes = self.regexes)

    def toJSON(self):
        d = AttributeType.toJSON(self)
        if self.choices:
            d["choices"] = self._choicesForJSON
        return d

class IntAttributeType(AttributeType):

    _typename_ = "int"

    def __init__(self, atype, name, choices = None, effective_labels = None,
                 minval = None, maxval = None, **kw):
        AttributeType.__init__(self, atype, name, **kw)
        self.choices = None
        if choices:
            for c in choices:
                if type(c) not in (int, long):
                    raise AnnotationError, ("not all choices for attribute '%s' are integers" % self.name)
            self.choices = set(choices)
            self._choicesForJSON = choices
        if self.choices and (self.aggregation is None):
            self._choiceAttribute = True
        self.minval = self.maxval = None
        if minval is not None:
            if choices:
                raise AnnotationError, ("can't define both range and choices for int attribute '%s'" % self.name)
            if type(minval) not in (int, long, float):
                raise AnnotationError, ("minval for attribute '%s' is not a numeric" % self.name)
            self.minval = minval
        if maxval is not None:
            if choices:
                raise AnnotationError, ("can't define both range and choices for int attribute '%s'" % self.name)
            if type(maxval) not in (int, long, float):
                raise AnnotationError, ("maxval for attribute '%s' is not a numeric" % self.name)            
            self.maxval = maxval
        whichMethod = {
            (True, True, True): self._checkType,
            (True, False, True): self._checkTypeAndMinval,
            (True, True, False): self._checkTypeAndMaxval,
            (True, False, False): self._checkTypeAndRange,
            (False, True, True): self._checkChoices,
            (False, True, False): self._checkChoices,
            (False, False, True): self._checkChoices,
            (False, False, False): self._checkChoices,
            }
        self._checkSingleValue = whichMethod[(self.choices is None, self.minval is None, self.maxval is None)]
        self._checkAndImportSingleValue = self._checkSingleValue
        self._computeMethods()
        # This has to be handled after the methods are computed.
        self.effective_labels = effective_labels
        if effective_labels is not None:
            self.declareEffectiveLabels(effective_labels)
        self._manageDefaults()

    def _checkType(self, doc, v):
        return type(v) in (int, long)

    def _checkTypeAndMaxval(self, doc, v):
        return (type(v) in (int, long)) and (v <= self.maxval)

    def _checkTypeAndMinval(self, doc, v):
        return (type(v) in (int, long)) and (v >= self.minval)

    def _checkTypeAndRange(self, doc, v):
        return (type(v) in (int, long)) and (v >= self.minval) and (v <= self.maxval)

    def _checkChoices(self, doc, v):
        return v in self.choices

    def copy(self, atype = None):
        return IntAttributeType(atype or self.atype, self.name, optional = self.optional,
                                aggregation = self.aggregation,
                                default = self.default, choices = self.choices,
                                effective_labels = self.effective_labels,
                                default_is_text_span = self.defaultIsTextSpan,
                                minval = self.minval, maxval = self.maxval)

    def toJSON(self):
        d = AttributeType.toJSON(self)
        if self.choices:
            d["choices"] = self._choicesForJSON
        if self.minval is not None:
            d["minval"] = self.minval
        if self.maxval is not None:
            d["maxval"] = self.maxval
        return d

    def _digestSingleValueFromString(self, v):
        try:
            return int(v)
        except ValueError:
            try:
                return long(v)
            except ValueError:
                return None

class FloatAttributeType(AttributeType):

    _typename_ = "float"

    def __init__(self, atype, name, minval = None, maxval = None, **kw):
        AttributeType.__init__(self, atype, name, **kw)
        self.minval = self.maxval = None
        if minval is not None:
            if type(minval) not in (int, long, float):
                raise AnnotationError, ("minval for attribute '%s' is not a numeric" % self.name)
            self.minval = minval
        if maxval is not None:
            if type(maxval) not in (int, long, float):
                raise AnnotationError, ("maxval for attribute '%s' is not a numeric" % self.name)
            self.maxval = maxval

        whichMethod = {
            (True, True): self._checkType,
            (False, True): self._checkTypeAndMinval,
            (True, False): self._checkTypeAndMaxval,
            (False, False): self._checkTypeAndRange
            }
        self._checkSingleValue = whichMethod[(self.minval is None, self.maxval is None)]
        self._checkAndImportSingleValue = self._checkSingleValue
        self._computeMethods()
        self._manageDefaults()

    def _checkType(self, doc, v):
        return type(v) is float

    def _checkTypeAndMaxval(self, doc, v):
        return (type(v) is float) and (v <= self.maxval)

    def _checkTypeAndMinval(self, doc, v):
        return (type(v) is float) and (v >= self.minval)

    def _checkTypeAndRange(self, doc, v):
        return (type(v) is float) and (v >= self.minval) and (v <= self.maxval)

    def copy(self, atype = None):
        return FloatAttributeType(atype or self.atype, self.name, optional = self.optional,
                                  aggregation = self.aggregation,
                                  minval = self.minval, maxval = self.maxval)
    
    def toJSON(self):
        d = AttributeType.toJSON(self)
        if self.minval is not None:
            d["minval"] = self.minval
        if self.maxval is not None:
            d["maxval"] = self.maxval
        return d

    def _digestSingleValueFromString(self, v):
        try:
            return float(v)
        except ValueError:
            return None

class BooleanAttributeType(AttributeType):

    _typename_ = "boolean"

    def __init__(self, *args, **kw):
        AttributeType.__init__(self, *args, **kw)
        if self.defaultIsTextSpan:
            raise AnnotationError, ("default_is_text_span not permitted for boolean attribute '%s'" % self.name)
        self._checkAndImportSingleValue = self._checkSingleValue
        self._computeMethods()
        self._manageDefaults()

    def _checkSingleValue(self, doc, v):
        return v in (True, False)

    def copy(self, atype = None):
        return BooleanAttributeType(atype or self.atype, self.name, optional = self.optional,
                                    aggregation = self.aggregation)

    def _toStringSingleValue(self, v):
        return (v and "yes") or "no"

    def _digestSingleValueFromString(self, v):
        if v == "yes":
            return True
        elif v == "no":
            return False
        else:
            return None

# The label restrictions should be either string atoms, or tuples
# whose first element is a string and second element is a dictionary or a list, set or tuple of attribute-value
# pairs. The restrictions won't be compiled and checked until the entire type
# repository is defined.

class AnnotationAttributeType(AttributeType):

    _typename_ = "annotation"

    def __init__(self, atype, name, label_restrictions = None, **kw):
        AttributeType.__init__(self, atype, name, **kw)
        if (self.default is not None) or self.defaultIsTextSpan:
            raise AnnotationError, ("defaults not permitted for annotation attribute '%s' of annotation type '%s'" % (self.name, self.atype.lab))
        # Let's just start with labels only.
        self.atomicLabelRestrictions = None
        self.complexLabelRestrictions = None
        if label_restrictions:
            if type(label_restrictions) not in (list, tuple, set):
                raise AnnotationError, ("label restrictions for attribute '%s' are not a list, tuple or set" % self.name)
            for e in label_restrictions:
                if type(e) in (str, unicode):
                    # It's just an atom.
                    if not self.atomicLabelRestrictions:
                        self.atomicLabelRestrictions = set([e])
                    else:
                        self.atomicLabelRestrictions.add(e)                    
                elif type(e) in (list, tuple):
                    if (len(e) < 1) or (type(e[0]) not in (str, unicode)):
                        raise AnnotationError, ("complex label restriction for attribute '%s' must begin with a string" % self.name)
                    if (len(e) == 1) or ((len(e) == 2) and (not e[1])):
                        # It's just an atom.
                        if not self.atomicLabelRestrictions:
                            self.atomicLabelRestrictions = set([e[0]])
                        else:
                            self.atomicLabelRestrictions.add(e[0])
                    elif len(e) == 2:
                        l = e[0]
                        if type(e[1]) is dict:
                            pairs = e[1].items()
                        elif type(e[1]) in (tuple, list, set):
                            pairs = list(e[1])
                        else:
                            raise AnnotationError, ("complex label restriction for attribute '%s' must be a 2-element sequence of a string and either a dictionary, list, tuple or set of attribute-value pairs" % self.name)
                        for p in pairs:
                            if not ((len(p) == 2) and (type(p[0]) in (str, unicode))):
                                raise AnnotationError, ("complex label restriction for attribute '%s' must be a sequence of a string and either a dictionary, list, tuple or set of attribute-value pairs" % self.name)
                        # Not gonna try to check if the attribute values are the right type.
                        if not self.complexLabelRestrictions:
                            self.complexLabelRestrictions = [(l, pairs)]
                        else:
                            self.complexLabelRestrictions.append((l, pairs))
                    else:
                        raise AnnotationError, ("label restrictions for attribute '%s' must each be a string or a sequence of a string and either a dictionary, list, tuple or set of attribute-value pairs" % self.name)
                else:
                    raise AnnotationError, ("label restrictions for attribute '%s' must each be a string or a sequence of a string and either a dictionary, list, tuple or set of attribute-value pairs" % self.name)

        self._computeLocalMethods()
        self._clearValue = self._clearAnnotationValue
        
    def _computeLocalMethods(self):
        whichMethod = {
            (True, True): self._checkType,
            (False, True): self._checkTypeAndSimpleRestrictions,
            (True, False): self._checkTypeAndComplexRestrictions,
            (False, False): self._checkTypeAndRestrictions
            }
        # This has to be redone after we call digestLabelRestrictions.
        self._checkSingleValue = whichMethod[(self.atomicLabelRestrictions is None, self.complexLabelRestrictions is None)]
        self._computeMethods()

    def _checkAndImportSingleValue(self, doc, v):
        if self._checkSingleValue(doc, v):
            doc.atypeRepository._registerAnnotationReference(v)
            return True
        else:
            return False

    def _importSingleValue(self, doc, v):
        doc.atypeRepository._registerAnnotationReference(v)
    
    # Each of these should register the annotation reference.
    
    def _checkType(self, doc, v):
        return isinstance(v, AnnotationCore)

    # The labels in the restrictions can be EFFECTIVE labels,
    # but we unpack those restrictions when we create the global
    # annotation set.

    def _checkTypeAndSimpleRestrictions(self, doc, v):
        return isinstance(v, AnnotationCore) and (v.atype.lab in self.atomicLabelRestrictions)

    def _checkTypeAndComplexRestrictions(self, doc, v):
        if not isinstance(v, AnnotationCore):
            return False
        for (lab, pairs) in self.complexLabelRestrictions:
            if v.atype.lab != lab:
                continue
            failed = False
            for a, val in pairs:
                if v.get(a) != val:
                    failed = True
                    break
            if not failed:
                return True
        return False

    def _checkTypeAndRestrictions(self, doc, v):
        if not isinstance(v, AnnotationCore):
            return False
        if (v.atype.lab in self.atomicLabelRestrictions):
            return True
        for (lab, pairs) in self.complexLabelRestrictions:
            if v.atype.lab != lab:
                continue
            failed = False
            for a, val in pairs:
                if v.get(a) != val:
                    failed = True
                    break
            if not failed:
                return True
        return False

    # This is used when possibly setting the value of a choice
    # attribute, to make sure the resulting array of features works.
    # Very similar to _checkTypeAndRestrictions.
    
    def _choicesSatisfyRestrictions(self, candidateLab, candidateFeatures):
        if (self.atomicLabelRestrictions is not None) and \
           (candidateLab in self.atomicLabelRestrictions):
            return True
        if self.complexLabelRestrictions is not None:
            for (lab, pairs) in self.complexLabelRestrictions:
                if candidateLab != lab:
                    continue
                failed = False
                for a, val in pairs:
                    if candidateFeatures.get(a) != val:
                        failed = True
                        break
                if not failed:
                    return True
            return False
        # Note that while it's not possible for an annotation-valued attribute
        # to lack all restrictions when the attribute is defined in a task
        # specification, the attribute ITSELF imposes no such restriction, in
        # case you're simply inducing the type from an annotation. So we have
        # to worry about this case, just in case.
        if (self.atomicLabelRestrictions is None) and (self.complexLabelRestrictions is None):
            return True
        else:
            return False

    def copy(self, atype = None):
        labelRestrictions = ((self.atomicLabelRestrictions and list(self.atomicLabelRestrictions)) or []) + \
                            (self.complexLabelRestrictions or [])
        if not labelRestrictions:
            labelRestrictions = None
        return AnnotationAttributeType(atype or self.atype, self.name, optional = self.optional,
                                       aggregation = self.aggregation,
                                       label_restrictions = labelRestrictions)

    def _toStringSingleValue(self, v):
        return v.describe()

    def _digestSingleValueFromString(self, v):
        # Not possible
        return None

    def _clearAnnotationValue(self, doc):
        # If there's already a current value.
        doc.atypeRepository._clearIDReferences()

    # We check the labels, and convert the values, and unpack
    # the effective labels. We know the effective labels point
    # to real info. This is called when the global type repository
    # is being compiled together.

    # We want to enforce a restriction where the attribute restrictions
    # can only correspond to attributes with choices.
    
    def digestLabelRestrictions(self, globalATR):
        toRemove = set()
        toAdd = []
        if self.atomicLabelRestrictions is not None:
            for a in self.atomicLabelRestrictions:
                if globalATR.effectiveLabelToTrueInfo.has_key(a):
                    toRemove.add(a)
                    (trueLabel, attr, val) = globalATR.effectiveLabelToTrueInfo[a]
                    toAdd.append((trueLabel, [(attr, val)]))
                elif not globalATR.has_key(a):
                    raise AnnotationError, ("label restriction refers to unknown label %s" % a)
        if toRemove:
            self.atomicLabelRestrictions -= toRemove
            if len(self.atomicLabelRestrictions) == 0:
                self.atomicLabelRestrictions = None
        if self.complexLabelRestrictions is not None:
            for i in range(len(self.complexLabelRestrictions)):
                [label, pairs] = self.complexLabelRestrictions[i]
                valChanged = False
                finalPairs = []
                if globalATR.effectiveLabelToTrueInfo.has_key(label):
                    (trueLabel, attr, val) = effectiveLabelToTrueInfo[label]
                    label = trueLabel                    
                    finalPairs = [(attr, val)]
                    valChanged = True
                elif not globalATR.has_key(label):
                    raise AnnotationError, ("label restriction refers to unknown label %s" % label)
                lObj = globalATR[label]
                for (attr, val) in pairs:
                    # Check and digest.
                    if val is None:
                        raise AnnotationError, ("label restriction refers to null attribute value")
                    try:
                        k = lObj.attr_table[attr]
                    except KeyError:
                        raise AnnotationError, ("found a label restriction which refers to an attribute %s which hasn't been defined for label %s" % (attr, label))
                    attrObj = lObj.attr_list[k]
                    if attrObj.aggregation is not None:
                        raise AnnotationError, ("found a label restriction which refers to a non-singleton attribute %s for label %s" %
                                                (attr, label))
                    if attrObj._typename_ not in ("string", "int"):
                        raise AnnotationError, ("found a label restriction which refers to a non-string, non-int attribute %s for label %s" % (attr, label))
                    if attrObj.choices is None:
                        raise AnnotationError, ("found a label restriction which refers to an attribute %s for label %s which has no choices" % (attr, label))
                    if type(val) in (str, unicode):
                        tval = attrObj._digestSingleValueFromString(val)
                        if tval is None:
                            raise AnnotationError, ("value '%s' can't be digested into the proper type (%s) for attribute %s of label %s in label restriction" %
                                                    (val, attrObj._typename_, attr, label))
                        if val != tval:
                            val = tval
                            valChanged = True
                    # Now, check the value.
                    if not attrObj._checkSingleValue(None, val):
                        raise AnnotationError, ("value %s is not a legal value for attribute %s of label %s in label restriction" %
                                                (val, attr, label))
                    finalPairs.append((attr, val))
                if valChanged:
                    self.complexLabelRestrictions[i] = [label, finalPairs]
            if toRemove:
                self.complexLabelRestrictions += toAdd
        elif toRemove:
            self.complexLabelRestrictions = toAdd
        if toRemove:
            # This computation may have changed.
            self._computeLocalMethods()

    def toJSON(self):
        d = AttributeType.toJSON(self)
        # Munging these back together, since the frontend ALSO has to
        # process them.
        if self.atomicLabelRestrictions and self.complexLabelRestrictions:
            d["label_restrictions"] = list(self.atomicLabelRestrictions) + self.complexLabelRestrictions            
        elif self.complexLabelRestrictions:
            d["label_restrictions"] = self.complexLabelRestrictions
        elif self.atomicLabelRestrictions:
            d["label_restrictions"] = list(self.atomicLabelRestrictions)
        return d

_ATTR_TYPES = dict([(p._typename_, p) for p in [StringAttributeType, IntAttributeType, FloatAttributeType,
                                                BooleanAttributeType, AnnotationAttributeType]])

# These types are used both within documents and within a task.
# They can only point back to the repository, which will differ
# between documents and tasks. You should NEVER expect the _Atype
# to be able to reach back into a document.

class _Atype:
    def __init__(self, repository, lab, hasSpan = True):
        self.repository = repository
        self.lab = lab
        self.hasSpan = hasSpan
        self.hasAnnotationValuedAttributes = False
        self.hasDefaults = False
        self.attr_list = []
        # Let's not check the length of the attr list over and over.
        self.attr_len = 0
        self.attr_table = {}
        self.closed = False

    def _close(self):
        self.closed = True
        
    def _ensureAttributeNumber(self, n):
        # Make sure we've retrieved the names of        
        # all the attributes up to this number.
        # First, check what we have.
        if n <= self.attr_len:
            return
        if n == 0:
            return
        
        # Aren't this many.
        raise AnnotationError, ("annotation type %s has fewer than %d attributes" % (self.lab, n))

    def _createAttributeType(self, attrType, s, aggregation = None, **kw):
        if self.closed:
            raise AnnotationError, ("annotation type %s no longer permits attributes to be added" % self.lab)
        # Give this a chance to raise an error before we go and increment stuff.
        newAttr = attrType(self, s, aggregation = aggregation, **kw)
        i = self.attr_len
        self.attr_table[s] = i            
        self.attr_list.append(newAttr)
        self.attr_len += 1
        if attrType is AnnotationAttributeType:
            self.hasAnnotationValuedAttributes = True
        if newAttr.hasDefault:
            self.hasDefaults = True
        return i

    # ensureAttribute should only barf on mismatching atypes if the aType is not None.
    def ensureAttribute(self, s, aType = None, aggregation = None, **kw):
        if type(s) not in (str, unicode):
            raise AnnotationError, "attribute name must be string"
        if not self.attr_table.has_key(s):
            try:
                attrType = _ATTR_TYPES[aType or "string"]
            except KeyError:
                raise AnnotationError, ("unknown attribute type '%s' for label '%s'" % (aType, self.lab))
            i = self._createAttributeType(attrType, s, aggregation = aggregation, **kw)
        else:
            i = self.attr_table[s]
            if aType is not None:
                if aggregation == "none":
                    aggregation = None
                if (self.attr_list[i]._typename_ != aType) or (self.attr_list[i].aggregation != aggregation):
                    
                    raise AnnotationError, ("type of attribute '%s' (%s) of label '%s' doesn't match type in task description (%s)" % \
                                            (s, ((aggregation and (aggregation + " of " )) or "") + aType, self.lab,
                                             ((self.attr_list[i].aggregation and (self.attr_list[i].aggregation + " of " )) or "") + self.attr_list[i]._typename_))
        return i

    # We only need to copy it from document to document, or from global
    # to local repository, if it's not closed. If the target repository
    # is the same as the source, and it's closed, leave it. Otherwise, copy.
    
    def maybeCopy(self, targetRepository):
        if self.closed and (isinstance(self.repository, GlobalAnnotationTypeRepository) or (self.repository is targetRepository)):
            return self
        else:
            return self.copy(repository = targetRepository)

    # closed is always False for the copy.    
    def copy(self, repository = None):
        newA = _Atype(repository or self.repository, self.lab, hasSpan = self.hasSpan)
        newA.attr_list = [a.copy(atype = newA) for a in self.attr_list]
        newA.attr_len = self.attr_len
        newA.attr_table = self.attr_table.copy()
        newA.hasAnnotationValuedAttributes = self.hasAnnotationValuedAttributes
        newA.hasDefaults = self.hasDefaults
        return newA

    # Rather than use ensureAttribute, now that things are getting complicated.
    def importAttribute(self, attrObj):
        if not self.attr_table.has_key(attrObj.name):
            i = self.attr_len
            self.attr_table[attrObj.name] = i
            self.attr_list.append(attrObj.copy(atype = self))
            self.attr_len += 1
            if isinstance(attrObj, AnnotationAttributeType):
                self.hasAnnotationValuedAttributes = True
        else:
            i = self.attr_table[attrObj.name]
            # Don't set, just check.
            if (self.attr_list[i]._typename_ != attrObj._typename_) or (self.attr_list[i].aggregation != attrObj.aggregation):
                raise AnnotationError, "attribute types don't match"
        return i

    def getDistinguishingAttributesForEquality(self):
        return [a.name for a in self.attr_list if a.distinguishingAttributeForEquality]

    # For shipping over the wire, at various points.
    def toJSON(self):
        return {"type": self.lab,
                "hasSpan": self.hasSpan,
                "allAttributesKnown": self.closed,
                "attrs": [a.toJSON() for a in self.attr_list]}
        

# I think, at least here, it'll be the repository which
# tracks the IDs. This repository is a DOCUMENT annotation type
# repository. The task repository is different.

class DocumentAnnotationTypeRepository(dict):

    def __init__(self, doc, globalTypeRepository = None):
        self.doc = doc
        self._idCount = 0
        self._idDict = {}
        self._inverseIdDict = None
        self.globalTypeRepository = globalTypeRepository
        self.forceUnlocked = False

    def forceUnlock(self):
        self.forceUnlocked = True

    # We used to support findAnnotationType as an integer,
    # but we no longer do.

    # So this is the getOrCreate method. If create = False,
    # it's a retrieval plus a check.
    
    def findAnnotationType(self, lab, hasSpan = True, create = True):
        atype = None
        if isinstance(lab, _Atype):
            atype = lab
        elif type(lab) in (StringType, UnicodeType):
            try:
                atype = self[lab]
            except KeyError:
                pass
        else:
            raise AnnotationError, "annotation label must be string"
        if atype is not None:
            if atype.hasSpan != hasSpan:
                raise AnnotationError, "requesting an annotation type whose hasSpan value doesn't match"
        elif self.globalTypeRepository:
            # You can NEVER create an annotation type in the global repository
            # by virtue of a local create flag. But if there's no global entry,
            # but the global repository isn't locked and you're supposed to create, make a local one.
            # If forceUnlocked is True, then we have to make sure to copy anything
            # we get back that doesn't point to this repository.
            atype = self.globalTypeRepository.findAnnotationType(lab, self, hasSpan = hasSpan, create = False)
            if self.forceUnlocked and atype and (atype.repository is not self):
                # Force the copy.
                atype = atype.copy(repository = self)
            elif create and (not atype) and (self.forceUnlocked or (not self.globalTypeRepository.isClosed())):
                atype = _Atype(self, lab, hasSpan = hasSpan)
            if atype is not None:
                self[lab] = atype
        elif create:
            atype = _Atype(self, lab, hasSpan = hasSpan)
            self[lab] = atype
        return atype        

    # Import from another document. The assumption is
    # that the current document is empty.

    def importAnnotationTypes(self, doc, removeAnnotationTypes = None):
        for aType in doc.atypeRepository.values():
            if (removeAnnotationTypes is not None) and (aType.lab in removeAnnotationTypes):
                continue
            self.importAnnotationType(aType)
        # Pull in the repository if appropriate. This will guide the annotation types
        # which haven't been fetched yet.
        if (self.globalTypeRepository is None) and doc.atypeRepository.globalTypeRepository:
            self.globalTypeRepository = doc.atypeRepository.globalTypeRepository
        return self.values()

    def importAnnotationType(self, aType):
        c = aType.maybeCopy(self)
        self[c.lab] = c
        return c

    # ID management. You can register an ID if it's
    # not already taken. If it's an integer string,
    # increase the count.
    
    def _registerID(self, aID, annot):
        if self._idDict.has_key(aID):
            raise AnnotationError, ("duplicate annotation ID '%s'" % aID)
        try:
            maxInt = int(aID)
            if maxInt < 0:
                raise AnnotationError, "annotation ID is < 0"
            self._idCount = max(self._idCount, maxInt + 1)
        except ValueError:
            # Isn't an integer.
            pass
        self._idDict[aID] = annot

    def _registerAnnotationReference(self, annot):
        annot.getID()
        # Don't record the inverse ID in inverseIDdict.
        # Just make sure that we know it's stale.
        self._inverseIdDict = None

    def _clearIDReferences(self):
        # Needs to be done when an annotation-valued attribute is None.
        self._inverseIdDict = None

    def _generateID(self, annot):
        i = self._idCount
        self._idCount += 1
        aID = str(i)
        self._idDict[aID] = annot
        return aID

    def getAnnotationByID(self, aID):
        return self._idDict.get(aID, None)

    # The elements in the aGroup can't be pointed to by
    # anyone outside the group. And in addition to removing
    # the annotation ID itself, we have to undo anything
    # it points to.

    def _buildInverseIdDict(self):
        if self._inverseIdDict is None:
            d = {}
            self._inverseIdDict = d
            for atype, annots in self.doc.atypeDict.items():
                if atype.hasAnnotationValuedAttributes:                    
                    for annot in annots:
                        for attrObj, attr in zip(annot.atype.attr_list, annot.attrs):
                            if isinstance(attr, AnnotationCore):
                                try:
                                    d[attr.id].add((annot, attrObj.name, None))
                                except KeyError:
                                    d[attr.id] = set([(annot, attrObj.name, None)])
                            elif isinstance(attr, AttributeValueSequence) and attr.ofDocAndAttribute and \
                                 isinstance(attr.ofDocAndAttribute[1], AnnotationAttributeType):
                                for subval in attr:
                                    try:
                                        d[subval.id].add((annot, attrObj.name, attrObj.aggregation))
                                    except KeyError:
                                        d[subval.id] = set([(annot, attrObj.name, attrObj.aggregation)])
    
    def removeAnnotationIDs(self, aGroup, forceDetach = False):
        self._buildInverseIdDict()
        externalPointers = set()
        for a in aGroup:
            if a.id is not None:
                try:
                    # We only care about the annotations, not about the attribute name.
                    externalPointers.update([(a, t) for t in self._inverseIdDict[a.id]])
                except KeyError:
                    pass
        annotsThatPoint = set([t[1][0] for t in externalPointers])
        if externalPointers and (not set(aGroup).issuperset(annotsThatPoint)):
            if forceDetach:
                # Forcibly detach these references.
                for (annotPointedTo, (annotThatPoints, attr, aggr)) in externalPointers:
                    if not aggr:
                        annotThatPoints[attr] = None
                    else:
                        v = annotThatPoints[attr]
                        v.remove(annotPointedTo)
            else:
                raise AnnotationError, "a group of annotations to be removed can't be pointed at by annotations outside the group"
        for a in aGroup:            
            if a.id is not None:
                aID = a.id
                try:
                    del self._idDict[aID]
                except:
                    pass
                try:
                    del self._inverseIdDict[aID]
                except:
                    pass
            for attrObj, attr in zip(a.atype.attr_list, a.attrs):
                if isinstance(attr, AnnotationCore):
                    # This update is worth doing "live", rather than just
                    # removing the dict and forcing a rebuild.
                    # A sequence of removes() will be more efficient then.
                    try:
                        self._inverseIdDict[attr.id].remove((a, attrObj.name, None))
                    except KeyError:
                        # Perhaps it's pointed to by the same annotation
                        # twice. In that case, it may already have been removed.
                        pass
                elif isinstance(attr, AttributeValueSequence) and attr.ofDocAndAttribute and \
                     isinstance(attr.ofDocAndAttribute[1], AnnotationAttributeType):
                    for subval in attr:
                        try:
                            self._inverseIdDict[subval.id].remove((a, attrObj.name, attrObj.aggregation))
                        except KeyError:
                            pass
                        
    def clear(self):
        self._idDict = {}
        self._inverseIdDict = None
        self._idCount = 0
        
    def recordEffectiveLabel(self, val, attr, trueLabel, eName):
        # What do I want to do here? I'm pretty sure that for the
        # document type repositories, this is a no-op - I don't want to
        # relay this to the parent global repository (if it exists).
        pass
    
#
# Annotations.
#

# We create the annotation when we read it,
# and we might also create new annotations by hand.
# We might use the annotation label id to create
# the annotation, or the name. We keep a record
# of both. Ditto with the attributes.

class AnnotationCore:
    def __init__(self, doc, lab, attrs = None):
        self.doc = doc
        self.id = None
        # I used to call a simplified version of findAnnotationType here, but now that
        # we have the complex local/global annotation repository stuff, I can't do that.
        a = self._findAnnotationType(lab)
        self.atype = a
        # Well, now. We have the type first; that's
        # the first part. Now, we need to figure out
        # what's happening with the attributes.
        # They might be a list of strings, in which case
        # we want to ensure we have that number of attributes.
        # Or they might be a dictionary whose keys are
        # strings, in which case we want to find all the
        # indices and order the keys.
        # Later, the Annotation object presents a dictionary
        # interface, which does the "right thing".
        # Initialize this so that things like _setAttrList can refer to it.
        self.attrs = []
        if attrs:
            if type(attrs) is ListType:
                a._ensureAttributeNumber(len(attrs))
                self._setAttrList(attrs)
            elif type(attrs) is DictionaryType:
                self.attrs = []
                for k, v in attrs.items():
                    # Well, duh. Use the dictionary interface.
                    self.__setitem__(k, v)
            else:
                raise AnnotationError, "attrs must be list or dictionary"
        if self.atype.hasDefaults:
            for i in range(len(self.atype.attr_list)):
                attr = self.atype.attr_list[i]
                if attr.hasDefault:
                    if len(self.attrs) <= i:
                        # Grow the attrs list if necessary.
                        self.attrs = self.attrs + ([None] * (i + 1 - len(self.attrs)))
                        self.attrs[i] = attr._getAttributeDefault(self)
                    elif self.attrs[i] is None:
                        self.attrs[i] = attr._getAttributeDefault(self)
    
    def _setAttrList(self, attrs):
        i = 0
        if self.attrs:
            self.doc.atypeRepository._clearIDReferences()
        while i < len(attrs):
            v = attrs[i]
            if v is not None:
                if not self.atype.attr_list[i]._checkAndImportValue(self.doc, v):
                    raise AnnotationError, ("value of attribute '%s' must be a %s" % (self.atype.attr_list[i].name, self.atype.attr_list[i]._typename_))
            i += 1
        self.attrs = attrs

    def _computeAttributeType(self, v):
        if isinstance(v, AttributeValueSequence):
            aggrType = ((isinstance(v, AttributeValueList) and "list") or "set")
            if len(v) == 0:
                # What else can we do?
                return StringAttributeType, aggrType
            else:
                first = True
                finalT = None
                for subV in v:
                    subT, subA = self._computeAttributeType(subV)
                    if subA is not None:
                        raise AnnotationError, "list or sequence attribute value may not have list or sequence members"
                    if first:
                        finalT = subT
                        first = False
                    elif subT is not finalT:
                        raise AnnotationError, "not all members of list or sequence attribute value are the same type"
                return finalT, aggrType
        elif type(v) in (str, unicode):
            return StringAttributeType, None
        elif type(v) in (int, long):
            return IntAttributeType, None
        elif type(v) is float:
            return FloatAttributeType, None
        elif isinstance(v, AnnotationCore):
            return AnnotationAttributeType, None
        elif v in (True, False):
            return BooleanAttributeType, None
        else:
            raise AnnotationError,( "attribute value %s must be AttributeValueList, AttributeValueSet, str, unicode, int, long, float, AnnotationCore, or boolean" % v)
            
    def __setitem__(self, k, v):
        # Here, we want to ensure that we have a given attribute,
        # if we can.
        attrIsNew = False
        if type(k) is IntType:
            # This may raise an AnnotationError.
            self.atype._ensureAttributeNumber(k + 1)
        elif type(k) in (StringType, UnicodeType):
            if self.atype.attr_table.has_key(k):
                k = self.atype.attr_table[k]
            else:
                # compute the type.
                s = k
                if v is None:
                    t = StringAttributeType
                    aggr = None
                else:
                    t, aggr = self._computeAttributeType(v)
                k = self.atype._createAttributeType(t, k, aggregation = aggr)
                attrIsNew = True
        else:
            raise AnnotationError, "key must be string or integer"
        if len(self.attrs) <= k:
            # Grow the attrs list if necessary.
            self.attrs = self.attrs + ([None] * (k + 1 - len(self.attrs)))
        if not attrIsNew:
            # If the attribute is new, the type has already been checked,
            # and the current value is known to be None.
            atp = self.atype.attr_list[k]
            if atp._choiceAttribute:
                if not atp._choiceAttributeOK(self, v):
                    raise AnnotationError, ("value of attribute '%s' can't be changed to '%s' because the result is inconsistent with the attribute restrictions of the attributes the annotation fills" % (atp.name, str(v)))
            if v is not None:
                if not atp._checkAndImportValue(self.doc, v):
                    raise AnnotationError, ("candidate value %s of attribute '%s' must be a %s and meet the other requirements" % (str(v), atp.name, atp._typename_))
            elif (len(self.attrs) > k) and (self.attrs[k] is not None) and atp._clearValue:
                atp._clearValue(self.doc)
        elif v is not None:
            # attrIsNew, and the types are checked. But I need to do _importValue in this case.
            atp = self.atype.attr_list[k]
            atp._importValue(self.doc, v)
        self.attrs[k] = v
    
    def __getitem__(self, k):
        if type(k) is IntType:
            try:
                return self.attrs[k]
            except IndexError, e:
                raise KeyError, k
        elif type(k) in (StringType, UnicodeType):
            # This may raise a key error.
            i = self.atype.attr_table[k]
            try:
                return self.attrs[i]
            except IndexError, e:
                raise KeyError, k
        else:
            raise KeyError, k

    def get(self, k, default = None):
        try:
            return self[k]
        except KeyError:
            return default

    def getByName(self, k, default = None):
        try:
            v = self[k]
        except KeyError:
            return default
        if v is None:
            return default
        else:
            if type(k) is not IntType:
                k = self.atype.attr_table[k]
            return self.atype.attr_list[k].toStringNonNull(v)

    # You can set the ID of an annotation,
    # but only if it's not already taken. If it's
    # an integer string, the counter will be automatically
    # increased.

    def setID(self, aID):
        # This may raise an error.
        self.doc.atypeRepository._registerID(aID, self)
        self.id = aID

    def getID(self):
        if self.id is None:
            self.id = self.doc.atypeRepository._generateID(self)
        return self.id

    def copy(self, doc = None, atype = None, attributes = None, **kw):
        raise AnnotationError, "not implemented"

    def _findAnnotationType(self, lab):
        raise AnnotationError, "not implemented"

    def describe(self):
        raise AnnotationError, "not implemented"

    def _describeAttributes(self):
        d = {}
        for attr, val in zip(self.atype.attr_list, self.attrs):
            if val is not None:
                v = attr.toStringNonNull(val)
                if attr._typename_ == "annotation":
                    v = "["+v+"]"
                d[attr.name] = v
        keys = d.keys()
        keys.sort()
        return [("%s=%s" % (k, d[k])) for k in keys]

    def getEffectiveLabel(self):
        if self.doc.atypeRepository.globalTypeRepository:
            return self.doc.atypeRepository.globalTypeRepository.getEffectiveAnnotationLabel(self)
        else:
            return self.atype.lab        

# If you're copying your own attrs, you'll need to make sure
# you copy any attribute value sequences, since they can't be reused.
# And be warned; if there are annotation attribute values, they
# will not be copied - you'll get them directly.

class SpanlessAnnotation(AnnotationCore):

    def copy(self, doc = None, atype = None, attrs = None, copyID = True, **kw):
        if (doc is not None) and (atype is None):
            raise AnnotationError, "Can't specify new doc for annotation without new atype"
        doc = doc or self.doc
        atype = atype or self.atype
        if attrs is None:
            attrs = [((isinstance(av, AttributeValueSequence) and av.copy()) or av)
                     for av in self.attrs]
        a = SpanlessAnnotation(doc, atype, attrs)
        # I may turn out never to use this. I'm not sure where I
        # do use it, but I know where I can't use it: in _importAnnotations.
        if self.id and copyID:
            a.setID(self.id)
        return a
    
    def _findAnnotationType(self, lab):
        return self.doc.atypeRepository.findAnnotationType(lab, hasSpan = False)

    def describe(self):
        vals = [self.atype.lab]
        if self.id:
            vals.append("(id %s)" % self.id)
        return " ".join(vals + self._describeAttributes())

class Annotation(AnnotationCore):

    def __init__(self, doc, start, end, lab, attrs = None):
        self.start = start
        self.end = end
        AnnotationCore.__init__(self, doc, lab, attrs)

    def copy(self, doc = None, atype = None, attrs = None, offset  = 0, copyID = True, **kw):
        if (doc is not None) and (atype is None):
            raise AnnotationError, "Can't specify new doc for annotation without new atype"
        doc = doc or self.doc
        atype = atype or self.atype
        if attrs is None:
            attrs = [((isinstance(av, AttributeValueSequence) and av.copy()) or av)
                     for av in self.attrs]
        start = self.start + offset
        end = self.end + offset
        a = Annotation(doc, start, end, atype, attrs)
        if self.id and copyID:
            a.setID(self.id)
        return a

    def _findAnnotationType(self, lab):
        return self.doc.atypeRepository.findAnnotationType(lab)

    def describe(self):
        vals = [self.atype.lab, "(%d-%d)" % (self.start, self.end)]
        if self.id:
            vals.append("(id %s)" % self.id)
        return " ".join(vals + self._describeAttributes())

#
# The task type repository. This repository has a number of the
# same methods, but it works a little differently.
#

class GlobalAnnotationTypeRepository(dict):

    def __init__(self):
        self.closed = False
        self.trueLabelToEffectiveLabels = {}
        self.labelToASD = {}
        self.attributeToASD = {}
        self.ASDToLabels = {}
        self.ASDToAttributes = {}
        self.effectiveLabelToTrueInfo = {}

    def _close(self):
        self.closed =  True

    def isClosed(self):
        return self.closed

    def recordEffectiveLabel(self, val, attr, trueLabel, eName):
        # Now, record the settings.
        self.effectiveLabelToTrueInfo[eName] = (trueLabel, attr, val)
        try:
            self.trueLabelToEffectiveLabels[trueLabel][(attr, val)] = eName
        except KeyError:
            self.trueLabelToEffectiveLabels[trueLabel] = {(attr, val): eName}

    # In some cases, we want to restrict the distinguishing
    # attributes to those that are in a particular category.
    # in PluginMgr.py, restrictToAnnotationSetNames is a set()
    # for efficiency.
    
    def getEffectiveAnnotationLabel(self, annot, useExtraDistinguishingAttributes = False,
                                    restrictToAnnotationSetNames = None):
        label = annot.atype.lab
        try:
            tEntry = self[label]
        except KeyError:
            # If there's no entry in the tag cache, just use this label. Actually,
            # this should probably be an error.
            return label

        lab = label

        distAttr = None
        
        for (attr, val), eName in self.trueLabelToEffectiveLabels.get(label, {}).items():
            if restrictToAnnotationSetNames and (self.attributeToASD.get((label, attr)) not in restrictToAnnotationSetNames):
                continue
            if annot.get(attr) == val:
                lab = eName
                if useExtraDistinguishingAttributes:
                    distAttr = attr
                break
        
        if useExtraDistinguishingAttributes:
            # We may have collected some. Remove those from
            # the global list of other attributes, sort
            # the remainder, and augment the label.
            curDistAttrs = set([a.name for a in self[label].attr_list
                                if a.distinguishingAttributeForEquality and \
                                   ((restrictToAnnotationSetNames is None) or
                                    (self.attributeToASD.get((label, a.name)) in restrictToAnnotationSetNames))])
            if distAttr:
                curDistAttrs.discard(distAttr)
            if curDistAttrs:
                curDistAttrs = list(curDistAttrs)
                curDistAttrs.sort()
                labList = [lab]
                for d in curDistAttrs:
                    labList.append(d+"="+ annot.get(d, "<null>"))
                lab = "_".join(labList)
        return lab

    def registerAnnotationSetNameForLabels(self, aname, trueLabels, effectiveLabels):
        for lab in trueLabels + effectiveLabels:
            self.labelToASD[lab] = aname
        for lab in trueLabels:
            try:
                self.ASDToLabels[aname][0].append(lab)
            except KeyError:
                self.ASDToLabels[aname] = ([lab], [])
        for lab in effectiveLabels:
            try:
                self.ASDToLabels[aname][1].append(lab)
            except KeyError:
                self.ASDToLabels[aname] = ([], [lab])

    def registerAnnotationSetNameForAttribute(self, aname, label, attribute):
        self.attributeToASD[(label, attribute)] = aname
        try:
            self.ASDToAttributes[aname][label].append(attribute)
        except KeyError:
            try:
                self.ASDToAttributes[aname][label] = [attribute]
            except KeyError:
                self.ASDToAttributes[aname]= {label: [attribute]}

    # Note that this function looks up both true and effective labels.
    
    def getAnnotationSetNameForLabel(self, lab):
        return self.labelToASD.get(lab)

    # Note that this function retrieves both true and effective labels,
    # separated.

    def getLabelsForAnnotationSetNames(self, *setNames):
        if len(setNames) == 0:
            return ([], [])
        elif len(setNames) == 1:
            r = self.ASDToLabels.get(setNames[0])
            if r is None:
                return ([], [])
            else:
                return r
        else:
            tLabs = []
            eLabs = []
            for s in setNames:
                r = self.ASDToLabels.get(s)
                if r is not None:
                    tLabs += r[0]
                    eLabs += r[1]
            return tLabs, eLabs
    
    # I need to know which labels are effective labels and which are true
    # labels, among other things.

    def getLabelsAndAttributesForAnnotationSetNames(self, *setNames):
        trueL, effL = self.getLabelsForAnnotationSetNames(*setNames)
        if len(setNames) == 1:
            attrD = self.ASDToAttributes.get(setNames[0]) or {}
        else:
            attrD = {}
            for s in setNames:
                d = self.ASDToAttributes.get(s)
                if d is not None:
                    attrD.update(d)
        effInfo = dict([(e, self.effectiveLabelToTrueInfo[e]) for e in effL])
        return trueL, attrD, effInfo

    def getEffectiveLabelsForTrueLabel(self, label):
        return self.trueLabelToEffectiveLabels.get(label)

    def getTrueLabelForEffectiveLabel(self, lab):
        try:
            return self.effectiveLabelToTrueInfo[lab][0]
        except KeyError:
            return lab

    def labelKnown(self, lab):
        return self.has_key(lab) or self.effectiveLabelToTrueInfo.has_key(lab)

    # This is a resource access call by DOCUMENTs. So lab is always
    # a string, unlike the document repository, and we copy the
    # annotation type if it's not closed.
    
    def findAnnotationType(self, lab, documentRepository, hasSpan = True, create = True):
        atype = None
        if type(lab) in (StringType, UnicodeType):
            try:
                atype = self[lab]
            except KeyError:
                pass
        else:
            raise AnnotationError, "annotation label must be string"
        if atype is not None:
            if atype.hasSpan != hasSpan:
                raise AnnotationError, "requesting an annotation type whose hasSpan value doesn't match"
            atype = atype.maybeCopy(documentRepository)
        elif (not self.closed) and create:
            # It's created without attributes closed, so we need to
            # copy it.
            atype = _Atype(self, lab, hasSpan = hasSpan)
            self[lab] = atype
            atype = atype.maybeCopy(documentRepository)
        return atype        

    def fromJSONDescriptorList(self, descriptorList, allAnnotationsKnown = False):
        
        # Now, we can hoover through the descriptors, creating all
        # the annotations. We know, at this point, that it's all
        # going to be unique. We also know that the attributes
        # are all defined after the annotations (at least locally).
        # We want to close off attributesKnown AFTER we're
        # done creating the repository.

        labelsToClose = []
        # We want mappings from labels to categories and from
        # categories to labels.
        for d in descriptorList:
            for annot in d.get("annotations", []):
                hasSpan = True
                if (annot.get("span") is not None) and (annot["span"] is False):
                    hasSpan = False
                self[annot["label"]] = _Atype(self, annot["label"], hasSpan = hasSpan)
                if annot.get("all_attributes_known", False):
                    labelsToClose.append(annot["label"])
            allEffectiveLabels = set()
            for attr in d.get("attributes", []):
                specs = attr.copy()
                aName = specs["name"]
                del specs["name"]
                tNames = specs["of_annotations"]
                del specs["of_annotations"]
                aTName = specs["type"]
                del specs["type"]
                for tName in tNames:
                    atype = self[tName]
                    # Special case. I want to force annotation-valued attributes
                    # to have label restrictions, but only when defined from
                    # a spec. Otherwise, it shouldn't be an issue.
                    if aTName == "annotation" and not specs.get("label_restrictions"):
                        raise AnnotationError, ("label_restrictions required for annotation attribute '%s' of annotation types %s" % (aName, ", ".join(tNames)))
                    atype.ensureAttribute(aName, aType = aTName, **specs)
                    self.registerAnnotationSetNameForAttribute(d["name"], tName, aName)
                # If it's successful, collect the effective labels.
                if specs.get("effective_labels"):
                    allEffectiveLabels.update(specs["effective_labels"].values())
            self.registerAnnotationSetNameForLabels(d["name"], [annot["label"] for annot in d.get("annotations", [])],
                                                    list(allEffectiveLabels))
        self.digestAnnotationAttributeLabelRestrictions()
        for l in labelsToClose:
            self[l]._close()
        if allAnnotationsKnown:
            self._close()

    def digestAnnotationAttributeLabelRestrictions(self):
        # If an annotation attribute has a restriction which is an effective
        # label, we should unpack it.
        for atype in self.values():
            for attr in atype.attr_list:
                if isinstance(attr, AnnotationAttributeType):
                    attr.digestLabelRestrictions(self)

    def toJSON(self):
        basicJSON = dict([(lab, atype.toJSON()) for (lab, atype) in self.items()])
        # Now, I want to salt this basic dict with a bunch of stuff. First, each
        # annotation should get its effective labels, complete with set name.
        for k, v in self.trueLabelToEffectiveLabels.items():
            basicJSON[k]["effective_labels"] = dict([(eName, {"attr": attr, "val": val,
                                                              "set_name": self.labelToASD.get(eName)})
                                                     for ((attr, val), eName) in v.items()])
        # I also want to add to each annotation and attribute 
        # its annotation set name.
        for k, v in self.items():
            e = basicJSON[k]
            e["set_name"] = self.labelToASD.get(k)
            for i in range(len(v.attr_list)):
                e["attrs"][i]["set_name"] = self.attributeToASD.get((k, v.attr_list[i].name))
        return {"allAnnotationsKnown": self.closed, "types": basicJSON}

    # It turns out that because of how we implement the CSS for
    # the labels, because CSS is case-insensitive, if two labels
    # vary only by case, you won't be able to do the right things with
    # the task in the UI. So we warn when we load the plugin dir.
    # See LoadPluginsFromDirs in PluginMgr.py.

    def checkUILabelConstraints(self, taskName):
        caseInsensitiveDict = {}
        for k in self.keys():
            lowK = k.lower()
            try:
                kEntry = caseInsensitiveDict[lowK]
                import sys
                print >> sys.stderr, "Warning: for task %s, the labels %s vary only by case, and can't be distinguished by CSS in the UI" % (taskName, ", ".join([k] + kEntry))
                kEntry.append(k)
            except KeyError:
                caseInsensitiveDict[lowK] = [k]
