# Copyright (C) 2007 - 2011 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This script builds an appropriate tarball for the MAT standalone
# document viewer.

# It should take a MAT version, or use the current version, and export a 
# clean version of MAT from CVS. Or, it least, it should have an option 
# for doing that. 

import sys, shutil

if sys.platform not in ["linux2", "sunos5", "darwin"]:
    print >> sys.stderr, "Building a tarball is currently supported only on Unix-like OSs."
    sys.exit(1)

# OK, we know we've got the right version of Python.

import os

# The root is two directories above this one.

MAT_PKG_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

def createTarball(tdir, zipExec, cvsExec, matVersion, bundleName, outDir):
    srcDir = os.path.join(tdir, bundleName)
    os.makedirs(srcDir)

    print "Checking out MAT version %s" % matVersion

    whatWeWant = ["MAT/web/htdocs/js/mat_utils.js",
                  "MAT/web/htdocs/js/mat_core.js",
                  "MAT/web/htdocs/js/core_ui.js",
                  "MAT/web/htdocs/js/mat_doc_display.js",
                  "MAT/web/htdocs/js/mat_standalone_doc_viewer.js",
                  "MAT/web/htdocs/css/mat_core.css",
                  "MAT/web/htdocs/doc/html/mat_json_format.html",
                  "MAT/web/htdocs/doc/html/standalone_viewer.html",
                  "MAT/web/htdocs/doc/css/doc.css",
                  "MAT/web/examples/standalone_viewer_example.html",
                  "MAT/etc/VERSION",
                  # And then the stuff we're going to move around.
                  "MAT/build/standalone_viewer/readers_and_writers.html",
                  "MAT/build/standalone_viewer/MATWeb.html",
                  "MAT/build/standalone_viewer/README",
                  "MAT/build/standalone_viewer/LICENSE"
                  ]
    os.system("cd %s; %s -d `cat %s/CVS/Root` export -r %s %s" % \
              (srcDir, cvsExec, MAT_PKG_HOME, matVersion, " ".join(whatWeWant)))

    print "Moving things around"

    shutil.move(os.path.join(srcDir, "MAT", "web"), os.path.join(srcDir, "web"))
    shutil.move(os.path.join(srcDir, "MAT", "etc"), os.path.join(srcDir, "etc"))
    shutil.move(os.path.join(srcDir, "MAT", "build"), os.path.join(srcDir, "build"))
    shutil.rmtree(os.path.join(srcDir, "MAT"))
    shutil.move(os.path.join(srcDir, "build", "standalone_viewer", "README"), os.path.join(srcDir, "README"))
    shutil.move(os.path.join(srcDir, "build", "standalone_viewer", "LICENSE"), os.path.join(srcDir, "LICENSE"))
    shutil.move(os.path.join(srcDir, "build", "standalone_viewer", "readers_and_writers.html"),
                os.path.join(srcDir, "web", "htdocs", "doc", "html"))
    shutil.move(os.path.join(srcDir, "build", "standalone_viewer", "MATWeb.html"),
                os.path.join(srcDir, "web", "htdocs", "doc", "html"))
    shutil.rmtree(os.path.join(srcDir, "build"))

    # Install Windows README.    
    # Convert README to DOS line endings, so that it works
    # in Windows, and use .txt extension so it'll open
    # with double-click. 
    shutil.copy(os.path.join(tdir, bundleName, "README"),
                os.path.join(tdir, bundleName, "README_clrf.txt"))
    os.system("unix2dos %s 2> /dev/null" % os.path.join(tdir, bundleName, "README_clrf.txt"))

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
        os.system("cd %s; %s update BUILD_LOG" % (os.path.dirname(os.path.dirname(__file__)), cvsExec))
        fp = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "BUILD_LOG"), "a")
        fp.write("\n")
        import time
        fp.write("Date: " + time.ctime() + "\n")
        fp.write("Purpose: " + purpose + "\n")
        fp.write("Dir: " + os.getcwd() + "\n")
        fp.write("Arguments: " + str(sys.argv[1:]) + "\n")
        fp.close()
        os.system("cd %s; %s commit -m 'Updated BUILD_LOG' BUILD_LOG" % (os.path.dirname(os.path.dirname(__file__)), cvsExec))

    print "Done." 

#
# Toplevel.
#

import getopt, os, re

def Usage():
    print "Usage: build_standalone_viewer.py [ --mat_version <cvs_version> ] [ --out_dir <dir> ] <bundle_name>"
    sys.exit(1)

ZIP = "zip"
MAT_VERSION = None
OUTDIR = None

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["mat_version=", "out_dir="])
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
    if k == "--mat_version":
        MAT_VERSION = v
    elif k == "--out_dir":
        OUTDIR = v
    else:
        Usage()

if OUTDIR is None:
    OUTDIR = os.getcwd()

OUTDIR = os.path.abspath(OUTDIR)

ZIP = chooseExecutable("zip in your path", execName = "zip",
                       execPrompt = "Please provide a path to zip: ",
                       execFailureString = "No version of zip specified. Exiting.",
                       exitOnFailure = True)

CVS = chooseExecutable("cvs in your path", execName = "cvs",
                       execPrompt = "Please provide a path to cvs: ",
                       execFailureString = "No version of cvs specified. Exiting.",
                       exitOnFailure = True)

import os

# Next, if there's no MAT_VERSION, find the most recent CVS tag.

if MAT_VERSION is None:
    MAT_VERSION = computeVersion(CVS, MAT_PKG_HOME, "etc/VERSION")    

# OK, at this point, we have the MAT version, the right version of tar,
# and all the tarballs. Now, we create a tmp directory. 

import tempfile, shutil

tdir = tempfile.mkdtemp()

print "Created temp directory %s." % tdir

try:
    createTarball(tdir, ZIP, CVS, MAT_VERSION, BUNDLE_NAME, OUTDIR)
finally:
    print "Removing temp directory."
    shutil.rmtree(tdir)

sys.exit(0)

