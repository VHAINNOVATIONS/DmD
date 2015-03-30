#!/bin/sh

if [ -n "`uname | grep -i cygwin`" ] ; then
  echo "Script will not work under Cygwin."
  exit 1
fi

# Figure out where we are.

fullPath=$0
if [ -z "`echo $fullPath | grep '^/'`" ] ; then
  fullPath=$PWD/$fullPath
fi

if [ -f "/bin/pwd" ] ; then
  pwdExe=/bin/pwd
elif [ -f "/usr/bin/pwd" ] ; then
  pwdExe=/usr/bin/pwd
else
  echo "Can\'t find pwd executable. Exiting."
  exit 1
fi

if [ -f "/bin/dirname" ] ; then
  dirnameExe=/bin/dirname
elif [ -f "/usr/bin/dirname" ] ; then
  dirnameExe=/usr/bin/dirname
else
  echo "Can\'t find dirname executable. Exiting."
  exit 1
fi

d=`$dirnameExe "$fullPath"`
trueD=`cd "$d"; $pwdExe`
rootD=`cd "$trueD"/..; $pwdExe`

DISTLIBS=$rootD/java-mat-core/dist/java-mat-core.jar:$rootD/java-mat-engine-client/dist/java-mat-engine-client.jar
CORELIBDIR=$rootD/lib

MAT_PKG_HOME=`cd "$rootD"/../../..; $pwdExe`

JAVA_BIN=`grep JAVA_BIN: "${MAT_PKG_HOME}/etc/MAT_settings.config" | sed -e 's|JAVA_BIN: *||'`

"$JAVA_BIN" -cp "$CORELIBDIR/commons-codec-1.2.jar:$CORELIBDIR/commons-logging-1.1.jar:$CORELIBDIR/commons-httpclient-3.1.jar:$CORELIBDIR/jackson-core-lgpl-1.4.3.jar:$CORELIBDIR/jackson-mapper-lgpl-1.4.3.jar:$DISTLIBS" org.mitre.mat.engineclient.MATCgiClientDemo "$@"
