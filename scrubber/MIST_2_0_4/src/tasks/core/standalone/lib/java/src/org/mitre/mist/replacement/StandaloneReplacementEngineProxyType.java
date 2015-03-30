// Copyright (C) 2012 The MITRE Corporation. See the toplevel
// file LICENSE for license terms.

package org.mitre.mist.replacement;
import org.python.core.PyObject;

public abstract class StandaloneReplacementEngineProxyType {

    public abstract void addResourceDir(String dir);
    
    public abstract PyObject newEvent(String signal, String prologue);
    
    public JavaStandaloneReplacementEngineEventType newEventInJava(String signal) {
        return this.newEventInJava(signal, null);
    }

    public JavaStandaloneReplacementEngineEventType newEventInJava(String signal, String prologue) {
        PyObject o = this.newEvent(signal, prologue);
        return (JavaStandaloneReplacementEngineEventType) o.__tojava__(JavaStandaloneReplacementEngineEventType.class);
    }
}