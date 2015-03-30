// Copyright (C) 2012 The MITRE Corporation. See the toplevel
// file LICENSE for license terms.

package org.mitre.mist.replacement;

public interface JavaStandaloneReplacementEngineEventType {

    public void addTuple(String lab, int start, int end);
    public void convert(String replacerName);
    public String getReplacedSignal();
    // Not sure what type we're going to get here.
    public Object[] getReplacedTuples();
    
}
