/*
 * Copyright (C) 2009 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * This is the document-level repository of annotation types.  It has a pointer
 * to all the Atypes allowed in the document.  It also optionally points to a 
 * global (task-level) repository.  If there is a global repository, types not
 * found in the local repository will be copied in from the global repository as
 * needed.
 * 
 * @author sam
 * @author robyn
 */
public class DocumentAnnotationTypeRepository extends AnnotationTypeRepository {

    private MATDocument doc = null;

    private GlobalAnnotationTypeRepository globalTypeRepository = null;

    /**
     * Constructor
     * @param doc
     */
    public DocumentAnnotationTypeRepository(MATDocument doc) {
        this(doc, null);
    }

    /**
     * Constructor
     * @param doc
     * @param globalRep a global (task-level) repository to back up this repository
     */
    public DocumentAnnotationTypeRepository(MATDocument doc, GlobalAnnotationTypeRepository globalRep) {

        this.doc = doc;
        this.globalTypeRepository = globalRep;
    }

    /** 
     * A version of findAnnotationType that accepts and an atype
     * instead of a label; it just checks the hasSpan agreement.  
     * Create doesn't make sense in this case.
     * 
     * @param atype 
     * @param hasSpan 
     * @return
     * @throws MATDocumentException  
     * @see #findAnnotationType(java.lang.String, boolean, boolean) 
     */
    public Atype findAnnotationType(Atype atype, boolean hasSpan)
            throws MATDocumentException {
        if (atype.getHasSpan() != hasSpan) {
            throw new MATDocumentException("attribute value is not of the appropriate type");
        } else {
            return atype;
        }
    }

    /**
     * Find the specified Atype for a spanned annotation within the repository,
     * or create it if it is not found.
     * @param label
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     * @see #findAnnotationType(java.lang.String, boolean, boolean) 
     */
    public Atype findAnnotationType(String label) throws MATDocumentException, AnnotationException {
        return findAnnotationType(label, true, true);
    }

    /**
     * Find the specified Atype within the repository.  If you pass in create = true,
     * the Atype will be created if not found.  
     * If create = false, it's a retrieval plus a check on the hasSpan
     * agreement.
     * 
     * @param label
     * @param hasSpan
     * @param create
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Atype findAnnotationType(String label, boolean hasSpan,
            boolean create) throws MATDocumentException, AnnotationException {
        Atype atype = this.get(label);
        if (atype != null) {
            return (findAnnotationType(atype, hasSpan));
        }
        // if we get here, atype == null so there was not atype of the
        // named type already in the repository.  If there's a global
        // repository, get it from there.  Otherwise if create is
        // true, maybe create it locally.

        if (globalTypeRepository != null) {
            // You can NEVER create an annotation type in the global
            // repository by virtue of a local create flag. But if
            // there's no global entry, and the global repository
            // isn't locked (which means you're allowed to create it
            // locally) and create is true, make a local one.
            atype = globalTypeRepository.findAnnotationType(label, this,
                    hasSpan, false);
            if (atype == null && create && !globalTypeRepository.isClosed()) {
                try {
                    // we can create a local only Atype for this type of annotation
                    // we don't know anything about attributes yet, so it gets 
                    // created with none
                    atype = new Atype(this, label, hasSpan);
                } catch (MATDocumentException ex) {
                    Logger.getLogger(DocumentAnnotationTypeRepository.class.getName()).log(Level.SEVERE, null, ex);
                }
            }
            if (atype != null) {
                // we found one in the global repository or created one
                // now add it to our local map
                this.put(label, atype);
            }
        } else if (create) {
            try {
                // there is no global repository, but we can just create it locally
                atype = new Atype(this, label, hasSpan);
                this.put(label, atype);
            } catch (MATDocumentException ex) {
                Logger.getLogger(DocumentAnnotationTypeRepository.class.getName()).log(Level.SEVERE, null, ex);
            }
        }
        return atype;
    }

    // the python version returns values() -- do I need that?
    /**
     * Copies all the annotation types from the given document to this repository
     * @param doc the MATDocument whose annotation types we want to copy
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public void importAnnotationTypes(MATDocument doc) throws MATDocumentException, AnnotationException {
        importAnnotationTypes(doc, null);
    }

    /**
     * Copies all the annotation types, except those in the removeAnnotationTypes
     * Collection, from the given document to this repository
     * @param doc the MATDocument whose annotation types we want to copy
     * @param removeAnnotationTypes
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Collection<Atype> importAnnotationTypes(MATDocument doc, Collection<Atype> removeAnnotationTypes) throws MATDocumentException, AnnotationException {
        for (Iterator<Atype> i = doc.getDocumentTypeRepository().values().iterator();
                i.hasNext();) {
            Atype atype = i.next();
            if (removeAnnotationTypes != null && removeAnnotationTypes.contains(atype)) {
                continue;
            }
            importAnnotationType(atype);
        }

        // Pull in the repository if appropriate. This will guide the
        // annotation types which haven't been fetched yet.
        if (this.globalTypeRepository == null
                && doc.getDocumentTypeRepository().getGlobalTypeRepository() != null) {
            this.globalTypeRepository =
                    doc.getDocumentTypeRepository().getGlobalTypeRepository();
        }

        return this.values();

    }

    /**
     * Copies the given Atype to this repository
     * @param atype
     * @return
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public Atype importAnnotationType(Atype atype) throws MATDocumentException, AnnotationException {
        // maybeCopy copies if needed, never returns null
        Atype copy = atype.maybeCopy(this);
        this.put(copy.getLabel(), copy);
        return copy;
    }

    /**
     * Retrieve the global repository backing this one
     * @return the global repository backing this one
     */
    public GlobalAnnotationTypeRepository getGlobalTypeRepository() {
        return globalTypeRepository;
    }

    void registerAnnotationReference(Object value) {
        throw new UnsupportedOperationException("Not yet implemented");
    }


}
