# Copyright (C) 2011 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# I just have no place for this.

import socket
import MAT

def findPort(startingAt):
    while True:
        v = socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('127.0.0.1', startingAt))
        if v == 0:
            startingAt += 1
        else:
            return startingAt

def portTaken(portNum):
    return socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('127.0.0.1', portNum)) == 0
    
def configurationPortTaken(configName):
    return portTaken(int(MAT.Config.MATConfig[configName]))

def configurationFindPort(configName):
    return findPort(int(MAT.Config.MATConfig[configName]))
