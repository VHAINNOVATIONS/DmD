@echo off

for %%F in ("%~dp0..\") do set rootD=%%~dpF

set DISTLIBS=%rootD%/java-mat-core/dist/java-mat-core.jar;%rootD%/java-mat-engine-client/dist/java-mat-engine-client.jar
set CORELIBDIR=%rootD%/lib

java -cp "%CORELIBDIR%/commons-codec-1.2.jar;%CORELIBDIR%/commons-logging-1.1.jar;%CORELIBDIR%/commons-httpclient-3.1.jar;%CORELIBDIR%/jackson-core-lgpl-1.4.3.jar;%CORELIBDIR%/jackson-mapper-lgpl-1.4.3.jar;%DISTLIBS%" org.mitre.mat.engineclient.MATCgiClientDemo %*
