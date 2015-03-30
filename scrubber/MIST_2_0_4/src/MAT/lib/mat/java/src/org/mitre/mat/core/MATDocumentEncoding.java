/*
 * Copyright (C) 2009-2102 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */

package org.mitre.mat.core;

/**
 * The interface for each encoding object.
 *
 * @author sam
 */
public interface MATDocumentEncoding {
    
    /**
     * 
     * @param doc
     * @param s
     * @throws MATDocumentException
     */
    void fromEncodedString(MATDocumentInterface doc, String s)
            throws MATDocumentException;
    
    /**
     * 
     * @param doc
     * @param fileName
     * @throws MATDocumentException
     */
    void fromFile(MATDocumentInterface doc, String fileName)
            throws MATDocumentException;
    
    /**
     * 
     * @param doc
     * @return
     */
    String toEncodedString(MATDocumentInterface doc);
    
    /**
     * 
     * @param doc
     * @param fileName
     */
    void toFile(MATDocumentInterface doc, String fileName);

}
