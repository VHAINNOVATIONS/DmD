# Copyright (C) 2007 - 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This is a script which will take the zip file that you have,
# add a task to it, and create a new zip file. This is a pared-down version
# of build_tarball.py.

import sys, shutil

if not hasattr(sys, "version_info"):
    print >> sys.stderr, "Python 2.x required (2.6 or later)."
    sys.exit(1)

majV, minV = sys.version_info[:2]

if majV != 2 or (minV < 6):
    print >> sys.stderr, "Python 2.x required (2.6 or later)."
    sys.exit(1)        

if sys.platform not in ["linux2", "sunos5", "darwin"]:
    print >> sys.stderr, "Building a tarball is currently supported only on Unix-like OSs."
    sys.exit(1)
    
# OK, we know we've got the right version of Python.

import os

# The root is one directory above this one.

MAT_PKG_HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import MAT_distutils

from MAT_distutils import shellOutput, MATManifest, parseTaskFeatures, chooseExecutable

#
# Guts
#

def createTarball(tdir, zipExec, unzipExec, cvsExec, taskTuples,
                  tasksToRemove, origDistZip, bundleName, outDir):
    # First step: unpack the original zip file in the
    # test directory.
    print "Unpacking original distribution zip"
    os.system("cd '%s'; '%s' -q '%s'" % (tdir, unzipExec, os.path.abspath(origDistZip)))
    print "Renaming bundle"
    os.rename(os.path.join(tdir, os.path.splitext(os.path.basename(origDistZip))[0]),
              os.path.join(tdir, bundleName))
    print "Loading existing manifest"
    manifestDict = MATManifest(os.path.join(tdir, bundleName))
    manifestDict.load()

    # Allow the possibility of overwrite.
    taskEntries = manifestDict.getTaskEntries()
    srcDir = os.path.join(tdir, bundleName, "src")
    taskSrcDir = os.path.join(srcDir, "tasks")
    # Now, add the tasks.
    if taskTuples:
        if not os.path.exists(taskSrcDir):
            os.makedirs(taskSrcDir)

    if tasksToRemove:
        for t in tasksToRemove:
            print "Removing", t
            if t in taskEntries:
                taskEntries.remove(t)
            if os.path.exists(os.path.join(taskSrcDir, t)):
                shutil.rmtree(os.path.join(taskSrcDir, t))

    for taskDir, taskVersion, distSettings in taskTuples:
        taskName = os.path.basename(taskDir)
        if os.path.exists(os.path.join(taskSrcDir, taskName)):
            print "Overwriting existing task, using %s instead" % taskDir
            shutil.rmtree(os.path.join(taskSrcDir, taskName))
        else:
            print "Adding task from %s" % taskDir
        if taskVersion is None:
            # No version control.
            shutil.copytree(taskDir, os.path.join(taskSrcDir, taskName))
            os.system("cd '%s'; find . -name .svn -exec rm -rf {} \; -print" % os.path.join(taskSrcDir, taskName))
        else:
            os.system("cd '%s'; '%s' -d `cat '%s/CVS/Root'` export -d '%s' -r '%s' `cat '%s/CVS/Repository'`" % \
                      (taskSrcDir, cvsExec, taskDir, taskName, taskVersion, taskDir))
        if taskName not in taskEntries:
            taskEntries.append(taskName)
    
    manifestDict.setTaskEntries(taskEntries)

    # Next, run the repair scripts.    
    i = 0
    for taskDir, taskVersion, distSettings in taskTuples:
        if os.path.exists(os.path.join(taskDir, "dist.py")):
            import imp
            # Load it as a special name. We won't be using the name.
            mName = "MAT_task%d_dist" % i
            i += 1
            m = imp.load_module(mName, *imp.find_module("dist", [taskDir]))
            if hasattr(m, "distribute"):
                m.distribute(taskDir, manifestDict,
                             os.path.join(tdir, bundleName), **parseTaskFeatures(distSettings))
            
    # Finally, create manifest.
    print "Writing manifest"
    manifestDict.save()

    print "Recreating static documentation copy with current task list"
    shutil.rmtree(os.path.join(tdir, bundleName, "static_doc"))

    jcarafeDir = manifestDict["jcarafe"]
    # Using the CURRENT version of WebService, which kind of hoses me for
    # building older versions. Sigh.
    sys.path.insert(0, os.path.join(MAT_PKG_HOME, "lib", "mat", "python"))
    from MAT.WebService import createStaticDocumentTree
    if os.path.isdir(taskSrcDir):
        dirs = [os.path.join(taskSrcDir, p) for p in os.listdir(taskSrcDir)]
    else:
        dirs = []
    createStaticDocumentTree(os.path.join(srcDir, "MAT"), dirs,
                             os.path.join(srcDir, jcarafeDir),
                             os.path.join(tdir, bundleName, "static_doc"))    

    # Gotta be a zip file, if I want it to be cross-platform.
    print "Creating zip file in %s.zip" % os.path.join(outDir, bundleName)
    os.system("cd '%s'; '%s' -qr '%s.zip' '%s'" % \
              (tdir, zipExec, os.path.join(outDir, bundleName), bundleName))

    print "Done." 

#
# Toplevel
#

import getopt

def Usage():
    print "Usage: redistribute.py [ --remove_task <task_dir> ] [ --task_dir <dir>[:<cvs_version>[:<dist_settings>]] ]+ orig_dist_zip outdir bundle_name"
    sys.exit(1)

ZIP = "zip"
UNZIP = "unzip"
TASK_DIRS = []
TASKS_TO_REMOVE = []

try:    
    opts, args = getopt.getopt(sys.argv[1:], "", ["task_dir=", "remove_task="])
except getopt.GetoptError, e:
    print e
    Usage()

if len(args) != 3:
    Usage()

[ORIG_DIST_ZIP, OUTDIR, BUNDLE_NAME] = args

if not os.path.isfile(ORIG_DIST_ZIP):
    print "Can't find specified original zip file."
    Usage()

if sys.platform == "win32":
    print "Can't build a tarball in native Windows version. Exiting."
    sys.exit(1)

for k, v in opts:
    if k == "--task_dir":        
        TASK_DIRS.append(v)
    elif k == "--remove_task":
        TASKS_TO_REMOVE.append(v)
    else:
        Usage()

if (not TASK_DIRS) and (not TASKS_TO_REMOVE):
    print "No task dirs specified; just redistribute the original zip file."
    sys.exit(0)

OUTDIR = os.path.abspath(OUTDIR)

ZIP = chooseExecutable("zip in your path", execName = "zip",
                       execPrompt = "Please provide a path to zip: ",
                       execFailureString = "No version of zip specified. Exiting.",
                       exitOnFailure = True)

UNZIP = chooseExecutable("unzip in your path", execName = "unzip",
                         execPrompt = "Please provide a path to unzip: ",
                         execFailureString = "No version of unzip specified. Exiting.",
                         exitOnFailure = True)


TASK_TUPLES = []

for s in TASK_DIRS:
    toks = s.split(":", 2)
    taskDir, taskVersion, distSettings = os.path.abspath(toks[0]), None, None
    if len(toks) > 1:
        taskVersion = toks[1]
    if len(toks) > 2:
        distSettings = toks[2]
    if not taskVersion:
        if os.path.isdir(os.path.join(taskDir, ".svn")):
            print "Warning: task directory %s appears to be under SVN control. Using contents of directory rather than computing the version."
            taskVersion = None
        elif not os.path.isdir(os.path.join(taskDir, "CVS")):
            print "Warning: task directory %s does not appear to be under version control." % taskDir
            taskVersion = None
        else:
            # You'd better pick a seed file, because the archive may have random
            # stuff in it some of which is in the CVS attic. I was going to
            # use the repair script, but it might not exist.
            fnames = shellOutput("cd %s; find . \! -type d | grep -v CVS" % taskDir)
            for f in fnames.split("\n"):
                f = f.strip()
                if os.system("cd '%s'; '%s' log -h '%s' > /dev/null 2>&1" % (taskDir, CVS, f)) == 0:
                    seedFile = f
                    break
            taskVersion = computeVersion(CVS, taskDir, seedFile)
    TASK_TUPLES.append((taskDir, taskVersion, distSettings))        

if [a for a in TASK_TUPLES if a[1] is not None]:
    CVS = chooseExecutable("cvs in your path", execName = "cvs",
                           execPrompt = "Please provide a path to cvs: ",
                           execFailureString = "No version of cvs specified. Exiting.",
                           exitOnFailure = True)
else:
    CVS = None

# Ready.

import tempfile, shutil

tdir = tempfile.mkdtemp()

print "Created temp directory %s." % tdir

try:
    createTarball(tdir, ZIP, UNZIP, CVS, TASK_TUPLES,
                  TASKS_TO_REMOVE,
                  ORIG_DIST_ZIP, BUNDLE_NAME, OUTDIR)
finally:
    print "Removing temp directory."
    shutil.rmtree(tdir)

sys.exit(0)

