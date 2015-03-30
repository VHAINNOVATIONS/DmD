/*
 * Copyright (C) 2009 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * An API for a MAT document, for use with the serializer and deserializer.
 *
 * At the moment,
 * it has some significant shortcomings when used with the serializer,
 * because it requires other types to work, so implementing the API is a
 * little tricky. The MATDocument object implements it correctly.
 *
 * @author sam
 * @author robyn
 */
public interface MATDocumentInterface {

    /**
     * Sets the metadata for this document
     * @param map a Map representing a JSON node with the metadata
     */
    public void setMetaData(HashMap<String, Object> map);

    /**
     * 
     * @return the signal String for this document
     */
    String getSignal();

    /**
     * Sets the signal String for this document.
     * @param signal
     */
    void setSignal(String signal);

    /**
     * Find or add an annotation type (<code>Atype</code>).
     * @param atypeType the String Label of the desired annotation type
     * @return the Atype
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Atype findOrAddAtype(String atypeType) throws MATDocumentException, AnnotationException;

    /**
     * Find or add an annotation type (<code>Atype</code>).
     * @param atypeType the String Label of the desired annotation type
     * @param hasSpan   specifies whether or not the Atype should be for span annotations
     * @return the Atype
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Atype findOrAddAtype(String atypeType, boolean hasSpan) throws MATDocumentException, AnnotationException;

    /**
     * 
     * @return this Annotations's metadata, as a JsonNode (in Map format)
     */
    HashMap<String, Object> getMetaData();

    /**
     * 
     * @return the Set of annotation types that this Document supports, as Strings
     */
    Set<String> getAnnotationTypes();

    /**
     * 
     * @param atypeType
     * @return list of attributeType objects for the given Atype type (label)
     */
    List<AttributeType> getAttributesOfType(String atypeType);

    /**
     * 
     * @param atypeType
     * @return list of annotation objects for the given Atype type (label)
     */
    List<AnnotationCore> getAnnotationsOfType(String atypeType);

    /**
     * 
     * @param atype
     * @return list of annotation objects for the given Atype
     */
    List<AnnotationCore> getAnnotationsOfType(Atype atype);
    
    /**
     * 
     * @return a List of all spanned annotations in the document
     */
    List<Annotation> getSpannedAnnotations();
    
    /**
     * 
     * @return a list of all spanned annotations in the document, in 
     *         document order
     */
    List<Annotation> getOrderedAnnotations();
    
    /**
     * 
     * @return a List of all spanless annotations in the document
     */
    List<SpanlessAnnotation> getSpanlessAnnotations();
    
    /**
     * 
     * @return a List of all annotations in the document (spanned and spanless)
     */
    List<AnnotationCore> getAllAnnotations();

    // HashMap<String, Atype> getAtypes(); -- deprecated
    
    /**
     * 
     * @return the local annotation type repository
     */
    DocumentAnnotationTypeRepository getDocRepository();

    /**
     * Create a new spanned annotation
     * @param atype
     * @param start
     * @param end
     * @return the annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Annotation createAnnotation(Atype atype, int start, int end) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanned annotation with attribute values set
     * @param atype
     * @param start
     * @param end
     * @param valsList the list of attribute values, in the order that the
     *                 attributes are listed in the Atype
     * @return the Annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Annotation createAnnotation(Atype atype, int start, int end, List valsList) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanned annotation with attribute values set
     * @param atype
     * @param start
     * @param end
     * @param valsMap a map of attribute names to their values
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Annotation createAnnotation(Atype atype, int start, int end, Map valsMap) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanned annotation
     * @param atypeType
     * @param start
     * @param end
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Annotation createAnnotation(String atypeType, int start, int end) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanned annotation with attribute values set
     * @param atypeType
     * @param start
     * @param end
     * @param valsList the list of attribute values, in the order that the
     *                 attributes are listed in the Atype
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Annotation createAnnotation(String atypeType, int start, int end, List valsList) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanned annotation with attribute values set
     * @param atypeType
     * @param start
     * @param end
     * @param valsMap a map of attribute names to their values
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    Annotation createAnnotation(String atypeType, int start, int end, Map valsMap) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanless annotation
     * @param atype
     * @return the Annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    SpanlessAnnotation createSpanlessAnnotation(Atype atype) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanless annotation with attribute values set
     * @param atype
     * @param valsList the list of attribute values, in the order that the
     *                 attributes are listed in the Atype
     * @return the annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    SpanlessAnnotation createSpanlessAnnotation(Atype atype, List valsList) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanless annotation with attribute values set
     * @param atype
     * @param valsMap a map of attribute names to their values
     * @return the annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    SpanlessAnnotation createSpanlessAnnotation(Atype atype, Map valsMap) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanless annotation
     * @param atypeType
     * @return the annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    SpanlessAnnotation createSpanlessAnnotation(String atypeType) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanless annotation with attribute values set
     * @param atypeType
     * @param valsList the list of attribute values, in the order that the
     *                 attributes are listed in the Atype
     * @return the annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    SpanlessAnnotation createSpanlessAnnotation(String atypeType, List valsList) throws MATDocumentException, AnnotationException;

    /**
     * Create a new spanless annotation with attribute values set
     * @param atypeType
     * @param valsMap a map of attribute names to their values
     * @return the annotation
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    SpanlessAnnotation createSpanlessAnnotation(String atypeType, Map valsMap) throws MATDocumentException, AnnotationException;

    /**
     * Delete an annotation from this document
     * @param a the annotation to be deleted
     * @throws MATDocumentException
     */
    void deleteAnnotation(AnnotationCore a) throws MATDocumentException;

    /**
     * Delete a list of annotations
     * @param annots the annotations to be deleted
     * @throws MATDocumentException
     */
    void deleteAnnotations(List<AnnotationCore> annots) throws MATDocumentException;

    /**
     * Delete ALL annotations from this document
     * @throws MATDocumentException
     */
    void deleteAllAnnotations() throws MATDocumentException;

    /**
     * Get this Document's ID Cache
     * @return the ID Cache
     */
    AnnotationIDCache getIDCache();
}
