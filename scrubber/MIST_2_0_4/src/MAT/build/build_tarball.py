# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This script builds an appropriate tarball for MAT and its
# associated applications.

# It should  take tarballs of:
# mrxvt-0.5.3-patched (now optional)
# jcarafe
# cherrypy 3.1.2

# It should take a MAT version, or use the current version, and export a 
# clean version of MAT from CVS. Or, it least, it should have an option 
# for doing that. Then it should do a "make install" into 
# an installation location, which will be the content of the core 
# MAT tarball. As for the associated applications, it should probably
# do the same for those. In each case, it should probably be pointed to a 
# checked-out directory, so it can use the CVS root there.

# Changed my mind. Because I want to build in the settings, rather than
# have to edit them by hand, I'll distribute the source tree.

# Once it's built a place for the tarballs, it should run the application
# scripts which add other stuff (like models, etc.) that happen not to
# be in the application tarball itself. 

# Should I check the versions? I should, but I'm going with tarballs, so 
# I'd have to settle for checking the actual numbers on the tarball. I can
# double check the versions when I build it.

# This sort of thing is typically done in sh, but sh is pretty limiting, 
# and it's probably faster to do it in Python anyway, and the whole
# system requires Python, so why not.

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

#
# Utilities
# 

from MAT_distutils import shellOutput, MATManifest, parseTaskFeatures, chooseExecutable

def computeVersion(cvsExec, pkgDir, seedFile):
    try:
        print "No version for %s provided, computing from CVS." % os.path.basename(pkgDir)
        s = re.search("symbolic names:\s*(.*?):",
                      shellOutput("cd %s; %s log -h %s 2>/dev/null" % (pkgDir, cvsExec, seedFile))).group(1).strip()
        print "Found most recent version %s." % s
        return s
    except:
        print "Could not compute appropriate version for %s. Exiting." % os.path.basename(pkgDir)
        sys.exit(1)

#
# Core work
#

# This tmp directory
# should be structured as follows:

# app_name/src: MAT, the MAT applications, and the source for the tarballs.
# app_name/build: the installation location for all the tarballs. This will be
# created when we build on the target machine.
# app_name/web: the default location for the Web server. This will be
# created when we run on the target machine.

# The application scripts might add other stuff.

# I've decided to include a manifest, because there will
# be potentially many application directories.

def createTarball(tdir, gnuTar, zipExec, unzipExec, cvsExec, taskTuples, matVersion,
                  mrxvtTgz, jcarafeTgz, munkresTgz, psutilTgz,
                  yuiJs, cherrypyTgz, bundleName, macTerminator,
                  winConsoleBundle, omitNetbeansInternals,
                  licenseFile, diffExec, diffAgainst, readmeHTML, outDir):
    srcDir = os.path.join(tdir, bundleName, "src")
    os.makedirs(srcDir)
    ignoreDirs = []
    manifestDict = MATManifest(os.path.join(tdir, bundleName))

    tgzTriples = [("CherryPy", "cherrypy", cherrypyTgz),
                  # jcarafe doesn't really belong in srcdir, but...
                  ("jcarafe", "jcarafe", jcarafeTgz),
                  ("munkres", "munkres", munkresTgz)]

    if psutilTgz is not None:
        tgzTriples.append(("psutil", "psutil", psutilTgz))

    if mrxvtTgz is not None:
        tgzTriples.append(("mrxvt", "mrxvt", mrxvtTgz))

    storedDirs = {}

    for nm, slug, tgz in tgzTriples:
        print "Unpacking", nm
        os.system("cd %s; %s zxf %s" %
                  (srcDir, gnuTar, os.path.abspath(tgz)))
        dirList = os.listdir(srcDir)
        for d in ignoreDirs:
            dirList.remove(d)
        thisDir = dirList[0]
        manifestDict[slug] = thisDir
        ignoreDirs.append(thisDir)

    # We need this later.
    jcarafeDir = manifestDict["jcarafe"]

    if macTerminator is not None:
        externalDir = os.path.join(tdir, bundleName, "external")
        if not os.path.exists(externalDir):
            os.makedirs(externalDir)
        print "Copying Mac terminator DMG"
        shutil.copy(macTerminator, externalDir)
        manifestDict['terminator'] = os.path.split(macTerminator)[1]
    if winConsoleBundle is not None:
        print "Unpacking Console.exe bundle"
        externalDir = os.path.join(tdir, bundleName, "external")
        if not os.path.exists(externalDir):
            os.makedirs(externalDir)
        os.system("cd %s; %s -q %s" % (externalDir, unzipExec,
                                       os.path.abspath(winConsoleBundle)))
        manifestDict['console'] = os.path.split(os.path.splitext(winConsoleBundle)[0])[1]

    print "Copying yui"
    shutil.copytree(os.path.abspath(yuiJs), os.path.join(srcDir, os.path.split(yuiJs)[1]))
    manifestDict["yui_dir"] = os.path.split(yuiJs)[1]
    print "Adding build scripts and README"
    for p in ["install.py", "install.sh", "README"]:
        shutil.copy(os.path.join(MAT_PKG_HOME, "build", p),
                    os.path.join(tdir, bundleName))
    # Install Windows README.    
    # Convert README to DOS line endings, so that it works
    # in Windows, and use .txt extension so it'll open
    # with double-click. 
    shutil.copy(os.path.join(tdir, bundleName, "README"),
                os.path.join(tdir, bundleName, "README_clrf.txt"))
    os.system("unix2dos %s 2> /dev/null" % os.path.join(tdir, bundleName, "README_clrf.txt"))
    taskEntries = []
    taskSrcDir = os.path.join(srcDir, "tasks")
    if taskTuples:
        os.makedirs(taskSrcDir)
    for taskDir, taskVersion, distSettings in taskTuples:
        print "Adding task from %s" % taskDir
        if taskVersion is None:
            # No CVS version control.
            shutil.copytree(taskDir, os.path.join(taskSrcDir, os.path.basename(taskDir)))
            os.system("cd %s; find . -name .svn -exec rm -rf {} \; -print" % os.path.join(taskSrcDir, os.path.basename(taskDir)))
        else:
            os.system("cd %s; %s -d `cat %s/CVS/Root` export -d %s -r %s `cat %s/CVS/Repository`" % \
                      (taskSrcDir, cvsExec, taskDir, os.path.basename(taskDir), taskVersion, taskDir))
        taskEntries.append(os.path.basename(taskDir))

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

    print "Checking out MAT version %s" % matVersion
    os.system("cd %s; %s -d `cat %s/CVS/Root` export -r %s MAT" % \
              (srcDir, cvsExec, MAT_PKG_HOME, matVersion))

    # Remove BUILD_LOG, if present.
    try:
        os.remove(os.path.join(srcDir, "MAT", "build", "BUILD_LOG"))
    except:
        pass

    if omitNetbeansInternals:
        for lib in ["CopyLibs", "junit", "junit_4"]:
            try:
                shutil.rmtree(os.path.join(srcDir, "MAT", "lib", "mat", "java", "lib", lib))
            except:
                pass

    print "Updating MAT version in JAR manifest file"
    os.system("cd %s/MAT/lib/mat/java/java-mat-core/dist; %s -q java-mat-core.jar META-INF/MANIFEST.MF" % (srcDir, unzipExec))
    import codecs, re
    fp = codecs.open(os.path.join(srcDir, "MAT/lib/mat/java/java-mat-core/dist/META-INF/MANIFEST.MF"), "r", "utf8")
    s = fp.read()
    fp.close()
    fp = open(os.path.join(srcDir, "MAT/etc/VERSION"), "r")
    vNum = fp.read()
    fp.close()
    # Replace Implementation-Version with the proper one.
    s = re.sub("^Implementation-Version: .*$", "Implementation-Version: " + vNum, s, flags = re.MULTILINE)
    fp = codecs.open(os.path.join(srcDir, "MAT/lib/mat/java/java-mat-core/dist/META-INF/MANIFEST.MF"), "w", "utf8")
    fp.write(s)
    fp.close()
    # Delete the old file from the manifest, add the new one.
    os.system("cd %s/MAT/lib/mat/java/java-mat-core/dist; %s -qd java-mat-core.jar META-INF/MANIFEST.MF; %s -q java-mat-core.jar META-INF/MANIFEST.MF; rm -rf META-INF" % (srcDir, zipExec, zipExec))    

    print "Copying license file"
    if licenseFile is None:
        licenseFile = os.path.join(MAT_PKG_HOME, "build", "MATLicensePlusDisclosures.txt")
    # Copy it into two places.
    shutil.copy(licenseFile, os.path.join(tdir, bundleName, "LICENSE"))
    shutil.copy(licenseFile, os.path.join(srcDir, "MAT", "BUNDLE_LICENSE"))

    print "Creating static documentation copy"
    if readmeHTML is None:
        readmeHTML = os.path.join(MAT_PKG_HOME, "build", "readme.html")
    shutil.copy(readmeHTML, os.path.join(tdir, bundleName, "readme.html"))
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
    
    # Now. Try to generate a diff. The previous dir may already contain a diff
    # -- duh -- so we have to remove it if it's there before we diff.
    if diffAgainst is not None:
        diffAgainst = os.path.abspath(diffAgainst)
        if not os.path.isfile(diffAgainst):
            print "Can't prepare diff against nonexistent comparison distro %s. Skipping." % diffAgainst
        # It better be a diff file.
        if os.system("cd %s; %s -q %s" % (tdir, unzipExec, diffAgainst)) != 0:
            print "Failed to unzip comparison distro %s. Skipping." % diffAgainst
        else:
            # Try removing the previous diff.
            previousDir = os.path.splitext(os.path.basename(diffAgainst))[0]
            try:
                os.remove(os.path.join(tdir, previousBasename, "previous_diff"))
            except:
                pass
            print "Generating diff against comparison distro %s" % diffAgainst
            fp = open(os.path.join(tdir, "previous_diff"), 'w')
            fp.write("Diff with previous version %s\n====================\n\n" % previousDir)
            fp.close()
            # Check the return value is pointless - it's nonzero if it finds anything.
            os.system("cd %s; %s -r %s %s >> previous_diff 2>&1" % (tdir, diffExec, bundleName, previousDir))
            os.rename(os.path.join(tdir, "previous_diff"), os.path.join(tdir, bundleName, "previous_diff"))

    # Gotta be a zip file, if I want it to be cross-platform.
    print "Creating zip file in %s.zip" % os.path.join(outDir, bundleName)
    os.system("cd %s; %s -qr %s.zip %s" % \
              (tdir, zipExec, os.path.join(outDir, bundleName), bundleName))

    # Add to the build log.
    print "Adding to the build log"
    purpose = raw_input("Purpose of build: ").strip()
    if not purpose:
        print "No purpose specified, skipping."
    else:
        # First, update it in CVS, then add to it, then commit.
        os.system("cd %s; %s update BUILD_LOG" % (os.path.dirname(__file__), cvsExec))
        fp = open(os.path.join(os.path.dirname(__file__), "BUILD_LOG"), "a")
        fp.write("\n")
        import time
        fp.write("Date: " + time.ctime() + "\n")
        fp.write("Purpose: " + purpose + "\n")
        fp.write("Dir: " + os.getcwd() + "\n")
        fp.write("Arguments: " + str(sys.argv[1:]) + "\n")
        fp.close()
        os.system("cd %s; %s commit -m 'Updated BUILD_LOG' BUILD_LOG" % (os.path.dirname(__file__), cvsExec))

    print "Done." 

#
# Toplevel.
#

import getopt, os, re

def Usage():
    print "Usage: build_tarball.py --yui_js <dir> --cherrypy_tgz <file> --munkres_tgz <file> [ --mat_version <cvs_version> ] [ --gnu_tar <path> ] [ --task_dir <dir>[:<version>[:<dist_settings>]] ]* [ --out_dir <dir> ] [ --mac_terminator_bundle <dmg> ] [ --mrxvt_tgz <file> ] [ --win_console_bundle <zip> ] [ --jcarafe_tgz <tgz> ] [ --psutil_tgz <file> ] [ --omit_netbeans_internals ] [ --diff_against <diff_zip> ] [ --readme_html <file> ] <bundle_name>"
    sys.exit(1)

GNU_TAR = "tar"
ZIP = "zip"
UNZIP = "unzip"
TASK_DIRS = []
MAT_VERSION = None
MRXVT_TGZ = None
YUI_JS = None
CHERRYPY_TGZ = None
MUNKRES_TGZ = None
OUTDIR = None
MAC_TERMINATOR_BUNDLE = None
WIN_CONSOLE_BUNDLE = None
LICENSE_FILE = None
JCARAFE_TGZ = None
PSUTIL_TGZ = None
OMIT_NETBEANS_INTERNALS = False
DIFF_AGAINST = None
DIFF = None
README_HTML = None

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["mrxvt_tgz=",
                                                  "yui_js=", "cherrypy_tgz=", "jcarafe_tgz=", "munkres_tgz=",
                                                  "psutil_tgz=",
                                                  "mat_version=",
                                                  "gnu_tar=", "task_dir=", "out_dir=",
                                                  "mac_terminator_bundle=",
                                                  "win_console_bundle=",
                                                  "omit_netbeans_internals",
                                                  "diff_against=",
                                                  "license_file=", "readme_html="])
except getopt.GetoptError, e:
    print e
    Usage()

if len(args) != 1:
    Usage()

[BUNDLE_NAME] = args

if sys.platform == "win32":
    print "Can't build a tarball in native Windows version. Exiting."
    sys.exit(1)

for k, v in opts:
    if k == "--mrxvt_tgz":
        MRXVT_TGZ = v
    elif k == "--yui_js":
        YUI_JS = v
    elif k == "--cherrypy_tgz":
        CHERRYPY_TGZ = v
    elif k == "--jcarafe_tgz":
        JCARAFE_TGZ = v
    elif k == "--munkres_tgz":
        MUNKRES_TGZ = v
    elif k == "--psutil_tgz":
        PSUTIL_TGZ = v
    elif k == "--mat_version":
        MAT_VERSION = v
    elif k == "--gnu_tar":
        GNU_TAR = v
    elif k == "--task_dir":        
        TASK_DIRS.append(v)
    elif k == "--out_dir":
        OUTDIR = v
    elif k == "--mac_terminator_bundle":
        MAC_TERMINATOR_BUNDLE = v
    elif k == "--win_console_bundle":
        WIN_CONSOLE_BUNDLE = v
    elif k == "--license_file":
        LICENSE_FILE = v
    elif k == "--omit_netbeans_internals":
        OMIT_NETBEANS_INTERNALS = True
    elif k == "--diff_against":
        DIFF_AGAINST = v
    elif k == "--readme_html":
        README_HTML = v
    else:
        Usage()

if OUTDIR is None:
    OUTDIR = os.getcwd()

OUTDIR = os.path.abspath(OUTDIR)

if (YUI_JS is None) or (CHERRYPY_TGZ is None) or (JCARAFE_TGZ is None) or (MUNKRES_TGZ is None):
    print "All of --yui_js, --cherrypy_tgz, --jcarafe_tgz, --munkres_tgz are required."
    Usage()

# We thought we'd need mrxvt on Leopard, but Terminator works.

# First, we check to make sure we have a decent version of tar.

GNU_TAR = chooseExecutable("GNU tar", seed = GNU_TAR,
                           filterFn = lambda v: re.search("GNU tar", shellOutput(v + " --version 2>/dev/null")) is not None,
                           failureString = "not a version of GNU tar.",
                           execPrompt = "Please provide a path to a version of GNU tar: ",
                           execFailureString = "No version of GNU tar specified. Exiting.",
                           exitOnFailure = True)

ZIP = chooseExecutable("zip in your path", execName = "zip",
                       execPrompt = "Please provide a path to zip: ",
                       execFailureString = "No version of zip specified. Exiting.",
                       exitOnFailure = True)

UNZIP = chooseExecutable("unzip in your path", execName = "unzip",
                         execPrompt = "Please provide a path to unzip: ",
                         execFailureString = "No version of unzip specified. Exiting.",
                         exitOnFailure = True)

CVS = chooseExecutable("cvs in your path", execName = "cvs",
                       execPrompt = "Please provide a path to cvs: ",
                       execFailureString = "No version of cvs specified. Exiting.",
                       exitOnFailure = True)

if DIFF_AGAINST is not None:
    DIFF = chooseExecutable("GNU diff in your path", execName = "diff",
                            filterFn = lambda v: re.search("GNU diffutils", shellOutput(v + " --version 2>/dev/null")) is not None,
                            failureString = "not a version of GNU diff.",
                            execPrompt = "Please provide a path to a version of GNU diff: ",
                            execFailureString = "No version of GNU diff specified. Skipping diff against previous release.")
    if DIFF is None:
        DIFF_AGAINST = None

import os

# Next, if there's no MAT_VERSION, find the most recent CVS tag.

if MAT_VERSION is None:
    MAT_VERSION = computeVersion(CVS, MAT_PKG_HOME, "etc/VERSION")    

TASK_TUPLES = []

for s in TASK_DIRS:
    toks = s.split(":", 2)
    taskDir, taskVersion, distSettings = os.path.abspath(toks[0]), None, None
    if not os.path.isdir(taskDir):
        print "Warning: task directory %s does not exist. Exiting." % taskDir
        sys.exit(1)
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
                if os.system("cd %s; %s log -h %s > /dev/null 2>&1" % (taskDir, CVS, f)) == 0:
                    seedFile = f
                    break
            taskVersion = computeVersion(CVS, taskDir, seedFile)
    TASK_TUPLES.append((taskDir, taskVersion, distSettings))        

# OK, at this point, we have the MAT version, the right version of tar,
# and all the tarballs. Now, we create a tmp directory. 

import tempfile, shutil

tdir = tempfile.mkdtemp()

print "Created temp directory %s." % tdir

try:
    createTarball(tdir, GNU_TAR, ZIP, UNZIP, CVS, TASK_TUPLES, MAT_VERSION,
                  MRXVT_TGZ, JCARAFE_TGZ, MUNKRES_TGZ, PSUTIL_TGZ,
                  YUI_JS, CHERRYPY_TGZ, BUNDLE_NAME,
                  MAC_TERMINATOR_BUNDLE,
                  WIN_CONSOLE_BUNDLE, OMIT_NETBEANS_INTERNALS,
                  LICENSE_FILE, DIFF, DIFF_AGAINST, README_HTML, OUTDIR)
finally:
    print "Removing temp directory."
    shutil.rmtree(tdir)

sys.exit(0)

