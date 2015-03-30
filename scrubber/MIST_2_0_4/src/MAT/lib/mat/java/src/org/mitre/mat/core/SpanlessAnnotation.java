/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */
package org.mitre.mat.core;

import java.util.List;

/**
 * An Annotation that is not directly anchored to a span of text
 * @author sam
 * @author robyn
 */
public class SpanlessAnnotation extends AnnotationCore {

    /**
     * Constructor
     * @param doc
     * @param parent
     * @param valsList
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public SpanlessAnnotation(MATDocument doc, Atype parent, List valsList) throws MATDocumentException, AnnotationException {
        super(doc, parent, valsList);
    }

    /**
     * Constructor
     * @param doc
     * @param parent
     * @throws MATDocumentException
     * @throws AnnotationException
     */
    public SpanlessAnnotation(MATDocument doc, Atype parent) throws MATDocumentException, AnnotationException {
        super(doc, parent, new java.util.ArrayList());
    }
}
