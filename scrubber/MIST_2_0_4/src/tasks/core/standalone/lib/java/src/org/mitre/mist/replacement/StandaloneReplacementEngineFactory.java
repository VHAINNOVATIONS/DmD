// Copyright (C) 2012 The MITRE Corporation. See the toplevel
// file LICENSE for license terms.

package org.mitre.mist.replacement;
import org.python.core.PyObject;
import org.python.core.PyString;
import org.python.util.PythonInterpreter;

public class StandaloneReplacementEngineFactory {

    private PyObject proxyType;
    private String module;
    private String cls;
    
    public StandaloneReplacementEngineFactory(String libJythonPyDir, String corePyDir, String module, String cls, String[] taskPyDirs) {
        PythonInterpreter interpreter = new PythonInterpreter();
        interpreter.exec("import sys");
        interpreter.exec("sys.path.insert(0, '" + corePyDir + "')");
        // Now, add the taskPyDirs in reverse order, so that the first one is
        // first on the list.
        if ((taskPyDirs != null) && (taskPyDirs.length > 0)) {
            for (int i = taskPyDirs.length - 1; i >= 0; i--) {
                interpreter.exec("sys.path.insert(0, '" + taskPyDirs[i] + "')");
            }
        }
        interpreter.exec("sys.path.insert(0, '" + libJythonPyDir + "')");
        this.module = module;
        this.cls = cls;
        interpreter.exec("from JavaStandaloneReplacementEngine import StandaloneReplacementEngineProxy");
        this.proxyType = interpreter.get("StandaloneReplacementEngineProxy");
    }

    public StandaloneReplacementEngineProxyType create() {
        PyObject proxyObj = this.proxyType.__call__(new PyString(this.module), new PyString(this.cls));
        return (StandaloneReplacementEngineProxyType) proxyObj.__tojava__(StandaloneReplacementEngineProxyType.class);
    }
}