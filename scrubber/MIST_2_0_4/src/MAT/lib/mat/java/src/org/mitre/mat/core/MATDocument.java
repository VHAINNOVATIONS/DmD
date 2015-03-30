/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * The object which embodies a MAT document.
 *
 * Each document contains a signal, a set of annotation types (Atype instances),
 * and a dictionary mapping Atypes to the Lists of actual annotations of that
 * type in the document, as well as a repository for arbitrary data (the metaData). 
 * Each annotation type has a label and a sequence of attributes, 
 * and each annotation contains a sequence of values which correspond
 * in order to the attributes in the appropriate Atype.
 *
 * For examples of use, see the package.
 *
 * @see org.mitre.mat.core
 *
 * @author sam
 * @author robyn
 */
public class MATDocument implements MATDocumentInterface {

    // instead of docAtypes use the docRepository
//    protected HashMap<String, Atype> docAtypes = null;
    
    /**
     * The signal String for this document
     */
    protected String signal;
    /**
     * the metaData for this document
     */
    protected HashMap<String, Object> metaData = null;
    
    /**
     * the actual annotations in the document
     * in a Map from Atype to the List of annotations of that type
     */
    protected HashMap<Atype, List<AnnotationCore>> atypeDict = null;
    
    //the ID Cache handles all the ID management stuff that is currently in DocumentAnnotationTypeRepository in Python
    // atype does not point to the idCache anymore
    /**
     * The ID Cache
     */
    protected AnnotationIDCache idCache = null;
    /**
     * The local repository of annotation types
     */
    protected DocumentAnnotationTypeRepository docRepository = null;
    // so we don't need to create one each time it's needed
    /**
     * A Comparator that compares (spanned) annotations based on document order.
     * @see Annotation.AnnotationComparator
     * @see Comparator
     */
    protected static Annotation.AnnotationComparator annotComparator = new Annotation.AnnotationComparator();

    /**
     * Constructor without no GlobalAnotationTypeRepository
     */
    public MATDocument() {
        init(null);
    }
    
    /**
     * Constructor for a MATDocument pointing to a GlobalAnnotationTypeRepository
     * @param gatr
     */
    public MATDocument(GlobalAnnotationTypeRepository gatr) {
        init(gatr);
    }

    private void init(GlobalAnnotationTypeRepository gatr) {
        // instead of doing lazy instantiation in addAtype do it up front
        // so that I can create a new Atype pointing to this document's
        // document repository and then call addAtype on it, and the docRepository
        // will exist when creating the atype
        this.docRepository = new DocumentAnnotationTypeRepository(this, gatr);
        this.idCache = new AnnotationIDCache(this);
        this.atypeDict = new HashMap<Atype, List<AnnotationCore>>();
    }

    /**
     * Add an Atype to the types permitted in this document
     * @param atype
     * @return the Atype (as passed in)
     */
    public Atype addAtype(Atype atype) {
        // atype.setIDCache(this.idCache);
        String type = atype.getAtypeType();
        this.docRepository.put(type, atype);
        this.atypeDict.put(atype, new ArrayList<AnnotationCore>());
        return atype;
    }

    public Atype findOrAddAtype(String atypeType, boolean hasSpan) throws MATDocumentException, AnnotationException {
        Atype atype = this.findAtypeOfType(atypeType);
        if (atype != null) {
            if (atype.getHasSpan() != hasSpan) {
                throw new MATDocumentException("found atype type, but span requirements don't match");
            }
            return atype;
        } else {
            // TODO is adding to the local docRepository the right thing here?
            return this.addAtype(new Atype(docRepository, atypeType, hasSpan));
        }
    }

    public Atype findOrAddAtype(String atypeType) throws MATDocumentException, AnnotationException {
        return this.findOrAddAtype(atypeType, true);
    }

    /* deprecated, use getDocRepository instead
    public HashMap<String, Atype> getAtypes() {
    return this.docRepository;
    }
     * */
    // TODO add this to interface?
    /**
     * 
     * @return the atypeDict (containing all annotations in this document,\
     *         mapped by Atype)
     */
    public HashMap<Atype, List<AnnotationCore>> getAtypeDict() {
        return this.atypeDict;
    }

    public Set<String> getAnnotationTypes() {
        // System.out.println("Getting annotation types");
        if (this.docRepository == null) {
            return null;
        } else {
            return this.docRepository.keySet();
        }
    }

    public List<AnnotationCore> getAnnotationsOfType(String atypeType) {
        Atype atype = findAtypeOfType(atypeType);
        return getAnnotationsOfType(atype);
    }

    public List<AnnotationCore> getAnnotationsOfType(Atype atype) {
        if (atype == null) {
            return null;
        } else {
            // We really want to copy this list, in case someone
            // decides to start removing annotations.
            List<AnnotationCore> theList = atypeDict.get(atype);
            if (theList == null) {
                return new ArrayList<AnnotationCore>();
            } else {
                return new ArrayList<AnnotationCore>(theList);
            }
        }
    }

    public List<AttributeType> getAttributesOfType(String atypeType) {
        Atype atype = findAtypeOfType(atypeType);
        if (atype == null) {
            return null;
        } else {
            return atype.getAttributes();
        }
    }

    public String getSignal() {
        return this.signal;
    }

    public void setSignal(String signal) {
        this.signal = signal;
    }

    public DocumentAnnotationTypeRepository getDocRepository() {
        return docRepository;
    }

    /**
     * Alternate method name for getDocRepository provided for backward compatibility
     * @return the local annotation type repository
     * @see MATDocumentInterface#getDocRepository() 
     */
    public DocumentAnnotationTypeRepository getDocumentTypeRepository() {
        return getDocRepository();
    }

    /**
     * 
     * @return the global annotation type repository for the task
     */
    public GlobalAnnotationTypeRepository getGlobalRepository() {
        return docRepository.getGlobalTypeRepository();
    }

    /**
     * Find the Atype whose label is given.  If the Atype does not exist
     * in the local annotation type repository, and there is a global
     * annotation type repository available, the Atype will be copied 
     * from the global to the local repository if it is found in the 
     * global repository.
     * @param type the Atype type (label) of the desired Atype.
     * @return the Atype (or null if not found)
     */
    protected Atype findAtypeOfType(String type) {
        if (this.docRepository != null) {
            Atype atype = this.docRepository.get(type);
            if (atype == null && this.docRepository.getGlobalTypeRepository() != null) {
                atype = this.docRepository.getGlobalTypeRepository().get(type);
                if (atype == null) {
                    return null;
                }
                // then what? copy it to the local doc repository AND add it to this document I think
                // ugh, I don't want to throw exceptions here because the callers have signatures that don't throw exceptions....
                // I think these exceptions should never happen, so I'm going to live dangerously here.
                try {
                    Atype copy = atype.maybeCopy(docRepository);
                    this.addAtype(copy);
                    return copy;
                } catch (MATDocumentException ex) {
                    System.err.println ("should not happen MATDocException copying atype from global to local repository");
                    return null;
                    // should never happen
                } catch (AnnotationException ex) {
                    // should never happen
                    System.err.println ("should not happen AnnotationException copying atype from global to local repository");
                    return null;
                }
            }
            return atype;
        } else {
            return null;
        }
    }

    public HashMap<String, Object> getMetaData() {
        if (this.metaData == null) {
            this.metaData = new HashMap<String, Object>();
        }
        return this.metaData;
    }

    public void setMetaData(HashMap<String, Object> map) {
        if (this.metaData == null) {
            this.metaData = new HashMap<String, Object>();
        }
        this.metaData.putAll(map);
    }

    public Annotation createAnnotation(Atype atype, int start, int end, List valsList) throws MATDocumentException, AnnotationException {
        if (!atype.hasSpan()) {
            throw new MATDocumentException("can't specify start and end for spanless annotation type");
        }
        Annotation annot = new Annotation(this, atype, start, end, valsList);
        addAnnotation(atype, annot);
        return annot;
    }

    // normally you should not call this directly (made un-private for unit testing)
    void addAnnotation(Atype atype, AnnotationCore annot) throws MATDocumentException {
        List<AnnotationCore> annots = atypeDict.get(atype);
        if (annots == null) {
            throw new MATDocumentException("invalid atype specified: " + atype.getLabel());
        }
        annots.add(annot);
    }

    public Annotation createAnnotation(String atypeType, int start, int end, List valsList)
            throws MATDocumentException, AnnotationException {
        Atype atype = this.findOrAddAtype(atypeType);
        return this.createAnnotation(atype, start, end, valsList);
    }

    public Annotation createAnnotation(String atypeType, int start, int end, Map valsMap)
            throws MATDocumentException, AnnotationException {
        Atype atype = this.findOrAddAtype(atypeType);
        return createAnnotation(atype, start, end, valsMap);
    }

    public Annotation createAnnotation(Atype atype, int start, int end, Map valsMap) throws MATDocumentException, AnnotationException {
        Annotation theAnnot = this.createAnnotation(atype, start, end);
        setMapVals(theAnnot, valsMap);
        return theAnnot;
    }

    private void setMapVals(AnnotationCore theAnnot, Map valsMap) throws MATDocumentException, AnnotationException {
        for (Iterator i = valsMap.keySet().iterator(); i.hasNext();) {
            String key = (String) i.next();
            Object value = valsMap.get(key);
            theAnnot.setAttributeValue(key, value);
        }
    }

    public Annotation createAnnotation(String atypeType, int start, int end) throws MATDocumentException, AnnotationException {
        Atype atype = this.findOrAddAtype(atypeType);
        return this.createAnnotation(atype, start, end);
    }

    public Annotation createAnnotation(Atype atype, int start, int end) throws MATDocumentException, AnnotationException {
        if (!atype.hasSpan()) {
            throw new MATDocumentException("can't specify start and end for spanless annotation type");
        }
        Annotation annot = new Annotation(this, atype, start, end);
        addAnnotation(atype, annot);
        return annot;
    }

    public SpanlessAnnotation createSpanlessAnnotation(Atype atype) throws MATDocumentException, AnnotationException {
        if (atype.hasSpan()) {
            throw new MATDocumentException("can't create spanless annotation of spanned annotation type");
        }
        SpanlessAnnotation annot = new SpanlessAnnotation(this, atype);
        addAnnotation(atype, annot);
        return annot;
    }

    public SpanlessAnnotation createSpanlessAnnotation(Atype atype, List valsList) throws MATDocumentException, AnnotationException {
        if (atype.hasSpan()) {
            throw new MATDocumentException("can't create spanless annotation of spanned annotation type");
        }
        SpanlessAnnotation annot = new SpanlessAnnotation(this, atype, valsList);
        addAnnotation(atype, annot);
        return annot;
    }

    public SpanlessAnnotation createSpanlessAnnotation(String atypeType) throws MATDocumentException, AnnotationException {
        Atype atype = this.findOrAddAtype(atypeType, false);
        return this.createSpanlessAnnotation(atype);
    }

    public SpanlessAnnotation createSpanlessAnnotation(String atypeType, List valsList) throws MATDocumentException, AnnotationException {
        Atype atype = this.findOrAddAtype(atypeType, false);
        return this.createSpanlessAnnotation(atype, valsList);
    }

    public SpanlessAnnotation createSpanlessAnnotation(Atype atype, Map valsMap) throws MATDocumentException, AnnotationException {
        SpanlessAnnotation theAnnot = this.createSpanlessAnnotation(atype);
        setMapVals(theAnnot, valsMap);
        return theAnnot;
    }

    public SpanlessAnnotation createSpanlessAnnotation(String atypeType, Map valsMap) throws MATDocumentException, AnnotationException {
        Atype atype = this.findOrAddAtype(atypeType, false);
        return this.createSpanlessAnnotation(atype, valsMap);
    }

    /**
     * 
     * @param id
     * @return the Annotation with the given id
     */
    public AnnotationCore getAnnotationByID(String id) {
        return this.idCache.getAnnotationByID(id);
    }

    public void deleteAnnotation(AnnotationCore a) throws MATDocumentException {
        Atype parentAtype = a.getParentAtype();
        /*** atype is not connected to a single doc anymore
        if (parentAtype.getDocument() != this) {
        throw new MATDocumentException("can't delete an annotation from a document it isn't in");
        } ***/
        this.idCache.removeAnnotationIDs(Arrays.asList(a));
        removeAnnotationFromAtypeDict(parentAtype, a);
    }

    // must only be called after removeIDs has happened
    private void removeAnnotationFromAtypeDict(Atype atype, AnnotationCore a) throws MATDocumentException {
        List<AnnotationCore> annots = atypeDict.get(atype);
        if (annots == null) {
            throw new MATDocumentException("invalid atype specified: " + atype.getLabel());
        }
        annots.remove(a);
    }

    public void deleteAnnotations(List<AnnotationCore> annots) throws MATDocumentException {
        Iterator<AnnotationCore> it = annots.iterator();
        /*** atype is not connected to a single doc anymore 
        while (it.hasNext()) {
        if (it.next().getParentAtype().getDocument() != this) {
        throw new MATDocumentException("can't delete an annotation from a document it isn't in");
        }
        }
         ****/
        this.idCache.removeAnnotationIDs(annots);
        it = annots.iterator();
        while (it.hasNext()) {
            AnnotationCore a = it.next();
            removeAnnotationFromAtypeDict(a.getParentAtype(), a);
        }
    }

    public void deleteAllAnnotations() throws MATDocumentException {
        if (this.idCache != null) {
            this.idCache.clear();
        }
        if (this.docRepository != null) {
            Iterator<Atype> it = this.docRepository.values().iterator();
            while (it.hasNext()) {
                atypeDict.put(it.next(), new ArrayList<AnnotationCore>());
            }
        }
    }

    public AnnotationIDCache getIDCache() {
        return idCache;
    }

    public List<Annotation> getSpannedAnnotations() {
        List<Annotation> spannedAnnots = new ArrayList<Annotation>();
        for (Atype atype:atypeDict.keySet()) {
            if (atype.hasSpan()) {
                //spannedAnnots.addAll(atypeDict.get(atype));
                // gross, I have to cast every annotation from AnnotationCore to 
                // Annotation now that I know it is spanned
                for (AnnotationCore annot:atypeDict.get(atype)) {
                    spannedAnnots.add((Annotation)annot);
                }
            }
        }
        return spannedAnnots;
    }

    public List<Annotation> getOrderedAnnotations() {
        // get all the spanned annots
        List<Annotation> orderedAnnots = getSpannedAnnotations();
        // sort them
        Collections.sort(orderedAnnots, this.annotComparator);
        // return them
        return orderedAnnots;
    }

    public List<SpanlessAnnotation> getSpanlessAnnotations() {
        List<SpanlessAnnotation> spanlessAnnots = new ArrayList<SpanlessAnnotation>();
        for (Atype atype:atypeDict.keySet()) {
            if (!atype.hasSpan()) {
                for (AnnotationCore annot:atypeDict.get(atype)) {
                    spanlessAnnots.add((SpanlessAnnotation)annot);
                }
            }
        }
        return spanlessAnnots;
    }

    public List<AnnotationCore> getAllAnnotations() {
        List<AnnotationCore> allAnnots = new ArrayList<AnnotationCore>();
        for (List<AnnotationCore> annots:atypeDict.values()) {
            allAnnots.addAll(annots);
        }
        return allAnnots;
    }
    
    private class OrderSpannedAnnots implements Comparator {

        public int compare(Object o1, Object o2) {
            throw new UnsupportedOperationException("Not supported yet.");
        }
    
    }   
           
}
