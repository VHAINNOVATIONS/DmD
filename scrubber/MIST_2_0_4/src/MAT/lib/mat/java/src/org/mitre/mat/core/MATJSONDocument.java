/*
 * Copyright (C) 2009-2012 The MITRE Corporation. See the toplevel
 * file LICENSE for license terms.
 */

package org.mitre.mat.core;

import java.io.StringReader;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;

/**
 * A simple specialization of MATDocument which includes methods for
 * serialization. Probably not useful.
 *
 * @author sam
 */

public class MATJSONDocument extends MATDocument {

    public MATJSONDocument() {
    }
    
    public void fromEncodedString(String s) throws MATDocumentException {
        new MATJSONEncoding().fromEncodedString(this, s);
    }

    public String toEncodedString() {
        return new MATJSONEncoding().toEncodedString(this);
    }

}

