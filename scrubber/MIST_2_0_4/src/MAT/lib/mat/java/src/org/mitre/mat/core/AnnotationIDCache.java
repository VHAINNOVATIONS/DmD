/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;

/**
 * Keeps track of the unique ID for each annotation, and tracks information
 * about where annotations are referenced by other annotations.
 * @author sam
 * @author robyn
 */
public class AnnotationIDCache {

    // We need to keep track of the IDs.
    private int idCount = 0;
    // This is the hash from the IDs to the annotations.
    private HashMap<String, AnnotationCore> idHash = null;
    
    /*** replaced by AnnotationReference version below *****
    // This is the hash from the IDs to the annotations that
    // refer to them in their attr list. Usually, it's null,
    // but if it's computed for a delete, it remains around
    // until an add of an annotation attr value is made.
    private HashMap<String, Set<AnnotationCore>> idReferences = null;
     *********************************************************/
    
    // This is the hash from the IDs to the annotations that
    // refer to them in their attr list. This maps to an
    // AnnotationReference object (see below) with additional 
    // information about the name and aggregation of the attribute
    // in the parent annotation pointing to the referenced child 
    // annotation.  Usually, it's null, but if it's computed, it 
    // remains around until an add of an annotation attr value is made.
    private HashMap<String, Set<AnnotationReference>> idReferences = null;
    // This points back to the MAT document. NOT the interface -
    // I'm not sure I need this in the interface, really.
    private MATDocument doc = null;

    /**
     * Constructor
     * @param doc The MAT document
     */
    public AnnotationIDCache(MATDocument doc) {
        this.doc = doc;
    }

    /**
     * Clears all the information
     */
    public void clear() {
        this.idHash = null;
        this.idReferences = null;
        this.idCount = 0;
    }

    /**
     * Generate a new ID for the given annotation
     * @param a the annotation
     * @return
     */
    public String generateID(AnnotationCore a) {
        if (this.idHash == null) {
            this.idHash = new HashMap<String, AnnotationCore>();
        }
        String id = Integer.toString(this.idCount);
        this.idCount++;
        this.idHash.put(id, a);
        return id;
    }

    /**
     * Register a given annotation ID for a given annotation.  The ID may be any
     * string.  If the string is numeric, all new generated IDs will be greater
     * than that number.
     * @param aID the id
     * @param a the annotation
     * @throws MATDocumentException if the ID is already in use, or if passed a
     *                              numeric annotation ID that is less than zero
     */
    public void registerID(String aID, AnnotationCore a) throws MATDocumentException {
        if (this.idHash == null) {
            this.idHash = new HashMap<String, AnnotationCore>();
        } else if (this.idHash.containsKey(aID)) {
            throw new MATDocumentException("duplicate annotation ID");
        }
        try {
            int i = Integer.parseInt(aID);
            if (i < 0) {
                throw new MATDocumentException("annotation ID is < 0");
            }
            // Since we know the ID hasn't been used, idCount will
            // definitely be less than it.
            this.idCount = Math.max(this.idCount, i + 1);
        } catch (NumberFormatException e) {
            // Don't do anything if it isn't a number.
        }
        this.idHash.put(aID, a);

    }

    /**
     * Retrieve an annotation by ID
     * @param aID the ID
     * @return
     */
    public AnnotationCore getAnnotationByID(String aID) {
        if (this.idHash == null) {
            return null;
        }
        return this.idHash.get(aID);
    }

    /**
     * Registers the fact that the given annotation is referenced by another.
     * Does not actually register the reference at this time, but rather
     * nulls out the idReferences map to indicate that it needs to be 
     * recomputed the next time it is needed.
     * @param a
     */
    public void registerAnnotationReference(AnnotationCore a) {
        // Not an actual reference. Just make sure it's got
        // an ID, and that the cache of reference maps is nulled out.
        a.getID();
        this.idReferences = null;
    }

    /**
     * Clears the idReferences map.  This can be used to force the map
     * to be recomputed the next time it is needed.
     */
    public void clearIDReferences() {
        this.idReferences = null;
    }

    /**
     * Finds all Annotations that refer to the annotation with the given ID
     * @param id the ID of the referenced annotation
     * @return
     */
    public Set<AnnotationReference> getReferringAnnots(String id) {
        buildIDReferenceHash(); // only happens if it's null
        return this.idReferences.get(id);
    }

    private void buildIDReferenceHash() {
        if (this.idReferences == null) {
            HashMap<String, Set<AnnotationReference>> refs = new HashMap<String, Set<AnnotationReference>>();
            this.idReferences = refs;
            Iterator<Atype> it = this.doc.getDocRepository().values().iterator();
            while (it.hasNext()) {
                Atype a = it.next();
                if (a.hasAnnotationAttribute()) {
                    Iterator<AnnotationCore> aIt = doc.getAnnotationsOfType(a).iterator();
                    while (aIt.hasNext()) {
                        AnnotationCore ac = aIt.next();
                        List<AttributeType> attributes = ac.getAttributes();
                        List attrVals = ac.getAttributeValues();
                        //Iterator attrIt = ac.getAttributeValues().iterator();
                        //while (attrIt.hasNext()) {
                        for (int i = 0; i < attrVals.size(); i++) {
                            //Object o = attrIt.next();
                            Object o = attrVals.get(i);
                            AttributeType attrObj = attributes.get(i);
                            if (o instanceof AnnotationCore) {
                                AnnotationCore attrAc = (AnnotationCore) o;
                                Set<AnnotationReference> s = refs.get(attrAc.getID());
                                if (s == null) {
                                    s = new HashSet<AnnotationReference>();
                                    refs.put(attrAc.getID(), s);
                                }
                                s.add(new AnnotationReference(ac, attrObj.getName(), AttributeType.NONE_AGGREGATION));
                            } else if (o instanceof AttributeValueCollection) {
                                Iterator avcIter = ((AttributeValueCollection) o).iterator();
                                while (avcIter.hasNext()) {
                                    Object val = avcIter.next();
                                    if (val instanceof AnnotationCore) {
                                        AnnotationCore attrAc = (AnnotationCore) val;
                                        Set<AnnotationReference> s = refs.get(attrAc.getID());
                                        if (s == null) {
                                            s = new HashSet<AnnotationReference>();
                                            refs.put(attrAc.getID(), s);
                                        }
                                        s.add(new AnnotationReference(ac, attrObj.getName(), attrObj.getAggregationType()));
                                    } else {
                                        break; // if the first one wasn't an Annotation, the rest won't be either
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    /**
     * Removes the IDs of a given list of annotations from the cache
     * @param aList the list of annotations to be removed from the cache
     * @throws MATDocumentException if you attempt to remove annotations that are
     *                              pointed to by other annotations not on the List
     */
    public void removeAnnotationIDs(List<AnnotationCore> aList) throws MATDocumentException {
        this.buildIDReferenceHash();
        Set<AnnotationCore> externalPointers = new HashSet<AnnotationCore>();
        Iterator<AnnotationCore> it = aList.iterator();
        while (it.hasNext()) {
            AnnotationCore ac = it.next();
            String id = ac.getID(false);
            if (id != null) {
                Set<AnnotationReference> s = this.idReferences.get(id);
                if (s != null) {
                    externalPointers.addAll(annotSet(s));
                }
            }
        }
        if ((externalPointers.size() > 0)
                && (!aList.containsAll(externalPointers))) {
            throw new MATDocumentException("a group annotations to be removed can't be pointed to by annotations outside the group");
        }
        it = aList.iterator();
        while (it.hasNext()) {
            AnnotationCore ac = it.next();
            String id = ac.getID(false);
            if (id != null) {
                if (this.idHash != null) {
                    this.idHash.remove(id);
                }
                this.idReferences.remove(id);
            }
            // Update the id references instead of deleting it,
            // so we don't need to regenerate it EVERY time.
            Iterator attrIt = ac.getAttributeValues().iterator();
            while (attrIt.hasNext()) {
                Object o = attrIt.next();
                if (o instanceof AnnotationCore) {
                    AnnotationCore attrAc = (AnnotationCore) o;
                    // RK added false to getID because we wouldn't want to look up 
                    // references to a just-generated ID
                    Set<AnnotationReference> s = this.idReferences.get(attrAc.getID(false));
                    if (s != null) {
                        removeAnnotRefs(s, ac); // find the right item and remove it
                    }
                } else if (o instanceof AttributeValueCollection) {
                    Iterator avcIter = ((AttributeValueCollection) o).iterator();
                    while (avcIter.hasNext()) {
                        Object val = avcIter.next();
                        if (val instanceof AnnotationCore) {
                            AnnotationCore attrAc = (AnnotationCore) val;
                            Set<AnnotationReference> s = this.idReferences.get(attrAc.getID(false));
                            if (s != null) {
                                removeAnnotRefs(s, ac); // find the right item and remove it
                            }
                        } else {
                            break; // if the first one wasn't an Annotation, the rest won't be either
                        }
                    }
                }
            }
        }
    }

    /**
     * Given a Set of AnnotationReferences, removes all that indicate a reference
     * to the given Annotation
     * @param s a set of AnnotationReferences
     * @param ac an annotation
     * 
     */
    private void removeAnnotRefs(Set<AnnotationReference> s, AnnotationCore ac) {
        Set<AnnotationReference> removes = new HashSet<AnnotationReference>();
        for (AnnotationReference ref : s) {
            if (ref.getAnnot().equals(ac)) {
                // can't remove while iterating -- save and remove all at end
                removes.add(ref);
            }
        }
        s.removeAll(removes);
    }
    
    private Set<AnnotationCore> annotSet(Set<AnnotationReference> refSet) {
        Set<AnnotationCore> annots = new HashSet<AnnotationCore>();
        for (AnnotationReference ref : refSet) {
            annots.add(ref.getAnnot());
        }
        return annots;
    }

    /**
     * For any annotation that is referenced by another annotation, this
     * class stores the referring annotation, the name of the annotation-valued 
     * attribute, and the aggregation type of the attribute.
     */
    public class AnnotationReference {

        private AnnotationCore annot;
        private String attrName;
        private int aggregation;

        /**
         * Constructor.
         * @param annot the referenced annotation
         * @param attrName the name of the annotation-valued attribute where the
         *                 annotation is referenced
         * @param aggregation the aggregation type of the annotation-valued attribute
         *                    where the annotation is referenced
         */
        public AnnotationReference(AnnotationCore annot, String attrName, int aggregation) {
            this.annot = annot;
            this.attrName = attrName;
            this.aggregation = aggregation;
        }

        /**
         * Retrieve the aggregation type of the annotation-valued attribute
         * @return the aggregation type
         */
        public int getAggregation() {
            return aggregation;
        }

        /**
         * Retrieve the referenced Annotation
         * @return the referenced annotation
         */
        public AnnotationCore getAnnot() {
            return annot;
        }

        /**
         * Retrieve the name of the annotation-valued attribute
         * @return the name of the annotation-valued attribute
         */
        public String getAttrName() {
            return attrName;
        }
    }
}
