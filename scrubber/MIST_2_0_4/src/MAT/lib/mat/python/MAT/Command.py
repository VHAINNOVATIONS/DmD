# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# This file was borrowed heavily from a combination of the
# dexec package written under the auspices of Reading Comp, and
# some tools for persistent clients and servers, also written
# under the auspices of Reading Comp.

# This should be a simple library which does some simple
# expect-like things - I can't really use pexpect, because I
# want to be able to use the expect-like things across
# the network. Although I should probably be using pexpect and
# extending it.

# We need three classes: local asynchronous process, local
# synchronous process, remote synchronous process. I suppose we
# should also have a remote asynchronous process for completeness,
# but we have no need for it here.

# We're going to do some expect-like things. The expectation seq
# is a sequence of [TO_CHILD <string>], [WAIT_CHILD <outmatch> <errmatch>],
# [FROM_CHILD_ERR <outmatch>], [FROM_CHILD_OUT <errmatch>]
# where <outmatch>, <errmatch> are either strings or regular
# expressions. WAIT_CHILD discards until it finds everything it's
# looking for; the others are all immediate.

TO_CHILD = 0
WAIT_CHILD = 1
FROM_CHILD_ERR = 2
FROM_CHILD_OUT = 3

# Do NOT import the _SUBPROCESS_* variables - if the command
# line changes them, you'll miss the changes.

import MAT.ExecutionContext

# Once the engine is satisfied, it passes everything it's
# given. It may buffer if it's in a WAIT_CHILD and one has
# matched and the other hasn't.

class ExpectError(Exception):
    pass

class ErrorDuringExpect(Exception):
    pass

import subprocess, sys, select, time, os

# We use the _kill patch in CherryPyService, too.
# os.kill has existed in Unix forever, and in Windows in 2.7 and later.

if sys.platform == "win32" and not hasattr(os, "kill"):
    def _kill_process(pid):
        import ctypes
        PROCESS_TERMINATE = 1
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)
else:
    def _kill_process(pid):
        import signal
        os.kill(pid, signal.SIGKILL)

# Fix subprocess.

if not hasattr(subprocess.Popen, "kill"):
    subprocess.Popen.kill = lambda self: _kill_process(self.pid)

if not hasattr(subprocess.Popen, "terminate"):
    if sys.platform == "win32":
        subprocess.Popen.terminate = subprocess.Popen.kill
    else:
        def _terminate(self):
            import signal
            os.kill(self.pid, signal.SIGTERM)
        subprocess.Popen.terminate = _terminate

import sys

# The waiter has two levels of buffer: the step buffer and the
# wait buffer. When a wait is done, the step buffer is flushed
# into the wait buffer.

class Waiter:
    
    def __init__(self, waitIndex, verbose = None, stdout = sys.stdout):
        if verbose is None:
            verbose = MAT.ExecutionContext._SUBPROCESS_DEBUG
        self.stepBuf = []
        self.waitBuf = []
        self.waitIndex = waitIndex
        self.waitStep = -1
        self.waitMatch = None
        self.matchDone = False
        self.SetStdout(stdout)
        self.SetVerbose(verbose)

    def SetVerbose(self, verbose):        
        self.verbose = verbose

    def SetStdout(self, stdout):
        self.stdout = stdout

    def write(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()
        
    def Initialize(self, waitStep, waitEntry):
        waitMatch = waitEntry[self.waitIndex]
        if self.waitStep < waitStep:
            # Don't flush the buffer, just in case you get two waiters
            # in a row.
            self.stepBuf = []
            self.waitStep = waitStep
            self.waitMatch = waitMatch
            if self.waitMatch is None:
                self.matchDone = True
            else:
                self.matchDone = False
    
    def IsMatchDone(self):
        return self.matchDone

    def WaitDone(self):
        self.waitBuf = self.waitBuf + self.stepBuf
        self.stepBuf = []

    # Process the line. Update the internal
    # state as appropriate
    
    def WaitSucceeded(self, line):
        if self.matchDone:
            self.stepBuf.append(line)
            if self.verbose:
                print >> self, "[Buffering %s]" % repr(line)
            return True
        elif type(self.waitMatch) is type(""):
            if self.waitMatch == line:
                # We satisfy this portion of the step.
                # Discard the line and update the
                # state. If it's now done, the OTHER
                # one needs to return its outbuf. Only
                # one of the dimensions will have something
                # in its buffer.
                self.matchDone = True
                return True
        elif self.waitMatch.search(line) is not None:
            self.matchDone = True
            return True
        return False

    def FlushBuffer(self):
        b = self.waitBuf
        self.waitBuf = []
        return b

class ExpectEngine:
    def __init__(self, process, expectation_seq = None, failure_pats = None, verbose = None,
                 stdout = sys.stdout):
        if verbose is None:
            verbose = MAT.ExecutionContext._SUBPROCESS_DEBUG
        self.stdout = stdout
        self.failurePairs = []
        if failure_pats is not None:
            for p in failure_pats:
                if type(p) in [type(()), type([])]:
                    self.failurePairs.append(p)
                else:
                    self.failurePairs.append((p, None))
        self.expectationSeq = expectation_seq
        if self.expectationSeq is None:
            self.expectationSeq = []
        self.process = process
        if not self.process:
            if self.verbose:
                print >> self, "[Expect error: no process]"
            raise ExpectError, "no process"
        self.verbose = verbose
        self.Reset()

    def SetVerbose(self, verbose):        
        self.verbose = verbose
        if self.outWaiter:
            self.outWaiter.SetVerbose(verbose)
        if self.errWaiter:
            self.errWaiter.SetVerbose(verbose)

    def SetStdout(self, stdout):
        self.stdout = stdout
        if self.outWaiter:
            self.outWaiter.SetStdout(stdout)
        if self.errWaiter:
            self.errWaiter.SetStdout(stdout)

    def write(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()
        
    def Initialize(self, process):
        self.Reset()
        self._MaybeWrite()

    def Reset(self):
        self.seqPos = 0
        self.seqPassed = False
        self.outWaiter = Waiter(1, self.verbose, self.stdout)
        self.errWaiter = Waiter(2, self.verbose, self.stdout)
        
    def _MaybeDone(self):
        if self.seqPos == len(self.expectationSeq):
            if self.verbose:
                print >> self, "[Expectations satisfied]"
            self.seqPassed = True
            self.process.expectationsSatisfied()

    def _MaybeWrite(self):
        # If the current expectation
        while (not self.seqPassed) and \
              (self.expectationSeq[self.seqPos][0] is TO_CHILD):            
            self.process._InputLines(self.expectationSeq[self.seqPos][1])
            self._Advance()

    def _Advance(self):
        self.seqPos = self.seqPos + 1
        self._MaybeDone()

    # These functions return the lines which pass through.
    
    def ErrorLines(self, lines):
        return self._DoLines(lines, FROM_CHILD_ERR,
                             self.errWaiter, self.outWaiter)
    
    def OutputLines(self, lines):
        return self._DoLines(lines, FROM_CHILD_OUT,
                             self.outWaiter, self.errWaiter)

    def _DoLines(self, lines, expectedStep, thisWaiter, otherWaiter):
        if lines:            
            outLines = []
            for line in lines:
                for p, errMsg in self.failurePairs:
                    m = p.match(line)
                    if m is not None:
                        raise ErrorDuringExpect, (errMsg or m.group(1),)
                self._MaybeWrite()
                if self.seqPassed:
                    outLines.append(line)
                else:
                    curStep = self.expectationSeq[self.seqPos]
                    if curStep[0] == WAIT_CHILD:
                        thisWaiter.Initialize(self.seqPos, curStep)
                        otherWaiter.Initialize(self.seqPos, curStep)
                        if thisWaiter.WaitSucceeded(line):
                            if otherWaiter.IsMatchDone():
                                # Both matches are done.
                                thisWaiter.WaitDone()
                                otherWaiter.WaitDone()
                                self._Advance()                            
                    elif curStep[0] != expectedStep:
                        if self.verbose:
                            print >> self, "[Expect error: wrong step type %d]" % curStep
                        raise ExpectError, ("wrong step type", curStep)
                    else:
                        passIt = False
                        if type(curStep[1]) is type(""):
                            if (curStep[1] == line):
                                passIt = True
                        elif curStep[1].search(line) is not None:
                            passIt = True
                        if passIt:
                            self._Advance()
                        else:
                            if self.verbose:
                                print >> self, "[Expect error: line doesn't match: %s, %s]" % (repr(curStep), repr(line))
                            raise ExpectError, ("line doesn't match", curStep, line)
            self._MaybeWrite()
            # This is synchronous, so there's no chance that a wait step
            # could buffer and flush in the same line group.
            return thisWaiter.FlushBuffer() + outLines
        else:
            return thisWaiter.FlushBuffer()

_MAYBE_ALIVE = 0
_DEFINITELY_ALIVE = 1
_DEFINITELY_DEAD = 2

_SUB_RUNNING = 0
_SUB_SUCCESS = 1
_SUB_FAILURE = 2
_SUB_DIED = 3
_SUB_KILLED = 4
_SUB_INTERRUPTED = 5
_SUB_UNKNOWN = 6
_SUB_PRESTART = 7

# If you have pre_expectations, you'd better make sure that discard_output
# isn't True.

#
# PUBLIC API
#

# RunSynchronous(args): start the process up, run it, shut it down.

# RunAsynchronous(args): start up, leave it running. Use callbacks or Poll().

# Stop(): shut down the process forcibly

# Fail(reason): force a failure and shutdown.

# Succeed(): force a success and shutdown.

# Status() -> (code, failure_reason)

# InputLines(*lines): write lines to the process.

# ReadHandler(handle): called to read data from the handle.

#
# LOCAL CHILDREN MUST IMPLEMENT
#

# Run(args): must call root _Initialize method.

#
# PUBLIC CHILDREN SHOULD SPECIALIZE
#

# OutputLines(*lines): callback when eligible lines are found
# on stdout

# ErrorLines(*lines): callback when eligible lines are found
# on stderr

class ProcessError(Exception):
    pass

# These used to be more general, but in the process of updating for Windows,
# I eliminated everything I wasn't using.


class _PipeHandleCore:

    def __init__(self, handle, nonBlocking = False):
        self.handle = handle
        if nonBlocking:
            self._SetNonblocking()

    def ReadBytes(self, num_bytes):
        # If num_bytes is -1, read whatever you can.
        try:
            if num_bytes == -1:
                data = self._readBytes()
                if data:
                    status = _DEFINITELY_ALIVE
                else:
                    status = _MAYBE_ALIVE
            else:
                data = self._readBytes(num_bytes)
                if len(data) < num_bytes:
                    status = _MAYBE_ALIVE
                else:
                    status = _DEFINITELY_ALIVE
            return status, data
        except IOError:
            eval_res = sys.exc_info()[1]
            if hasattr(eval_res, "errno") and \
               eval_res.errno == errno.EAGAIN:
                return _DEFINITELY_ALIVE, ""
            else:
                return _DEFINITELY_DEAD, ""

    # We're not trying to implement nonblocking writes.
    
    def WriteBytes(self, bytes):
        self.handle.write(bytes)
        self.handle.flush()

    def ID(self):
        return self.handle.fileno()

    #
    # Local methods
    #

    def _SetNonblocking(self):
        raise ProcessError, "undefined"

    def _readBytes(self, num_bytes = None):
        raise ProcessError, "undefined"

if sys.platform == "win32":

    # Windows version of pipe handles.
    # Thanks to http://code.google.com/p/subprocdev, which
    # is the reference code for Python PEP 3145, "Asynchronous I/O For subprocess.Popen",
    # for showing me how to do this using ctypes. On the one hand, I wish I could just
    # use that code in its entirety, but on the other hand, I don't have a warm fuzzy
    # about its compatibility with subprocess.py in later releases. So.

    import msvcrt
    from ctypes import c_char_p, byref, windll, c_long, \
        create_string_buffer, sizeof

    # from win32file import ReadFile
    def ReadFile(handle, readsize, lpOverlapped = None):
        """
        Windows kernel32.dll ReadFile API
        
        Reads data from the file or input/output device with the given handle.
        A tuple is returned with the first element being the number of bytes
        read and the second the data that was read.
        
        Please note that Windows API may convert \\n newlines to \\r\\n.
        """
        readdata = create_string_buffer(readsize)
        bytesread = c_long(0)
        # In the original code, the final argument was c_long(0), which ought
        # to be the same as None, but on Windows 7, I get a memory error
        # with c_long(0).
        returncode = windll.kernel32.ReadFile(c_long(handle), byref(readdata),
            c_long(readsize), byref(bytesread), None)
        read = readdata.value
        if returncode == True and read is None:
            read = ''
        return (bytesread.value, read)
    
    # from win32pipe import PeekNamedPipe
    def PeekNamedPipe(handle, buffersize):
        """
        Windows kernel32.dll ReadFile API
        
        Reads data and status information from the file or input/output device
        with the given handle. A tuple containing the data read, amount of
        bytes read and the remaining bytes left in the message is returned.
        """
        readdata = create_string_buffer(buffersize)
        readbytes = c_long(0)
        available = c_long(0)
        leftthismessage = c_long(0)
        returncode = windll.kernel32.PeekNamedPipe(c_long(handle),
            byref(readdata), buffersize, byref(readbytes), byref(available),
            byref(leftthismessage))
        read = readdata.value
        if returncode == 1 and read is None:
            read = ''
        return (read, available.value, leftthismessage.value)

    # If the handle isn't nonblocking, we just do the normal read.

    class PipeHandle(_PipeHandleCore):

        def __init__(self, handle, nonBlocking = False):
            self.nonBlocking = nonBlocking
            _PipeHandleCore.__init__(self, handle, nonBlocking = nonBlocking)

        def _SetNonblocking(self):
            self.nonBlocking = True
            if self.nonBlocking:
                self._readBytes = self._readBytesNonBlocking

        # Just the normal read.
        def _readBytes(self, num_bytes = None):
            if num_bytes is None:
                return self.handle.read()
            else:
                return self.handle.read(num_bytes)

        # The caller expects IOError, and EAGAIN if the
        # problem is that there's nothing there.

        def _readBytesNonBlocking(self, num_bytes = None):        
            try:
                x = msvcrt.get_osfhandle(self.handle.fileno())
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
                if nAvail == 0:
                    # This MIGHT want to raise IOError(EAGAIN)
                    # but I'm not sure.
                    return ''
                else:
                    (errCode, read) = ReadFile(x, nAvail, None)
                    # The reference code apparently believes that errCode
                    # will never be interesting. OK.
                    return read
            except ValueError:
                raise IOError(errno.EBADF, "bad file number")
            except Exception, e:
                if hasattr(e, "errno") and (e.errno in (109, errno.ESHUTDOWN)):
                    raise IOError(errno.ESHUTDOWN, "cannot send after transport endpoint shutdown")
                raise

    class WinPoller:

        def __init__(self):
            self.handles = {}

        # The only anticipated error below is a select.error,
        # and that's for some freakish Cygwin stuff.

        def poll(self, ms):
            # If nobody has anything to read, then sleep the
            # available ms.
            avail = []
            for h in self.handles.keys():
                x = msvcrt.get_osfhandle(h.fileno())
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
                if nAvail > 0:
                    avail.append((h.fileno(), POLLIN))
            if avail:
                return avail
            else:
                # Try to sleep for a bit.
                time.sleep(float(ms) / 1000)
                return []

        def register(self, handle, flags):
            # Just ignore the flags.
            self.handles[handle] = True

        def unregister(self, handle):
            try:
                del self.handles[handle]
            except:
                pass

    def _getpoller():
        return WinPoller()

    POLLIN = POLLIN_WITH_PRI = 0
    
else:
    
    # Unix version of pipe handles.
    import fcntl, os
    try:
        F_SETFL = fcntl.F_SETFL
        F_GETFL = fcntl.F_GETFL
    except AttributeError:
        import FCNTL
        F_SETFL = FCNTL.F_SETFL
        F_GETFL = FCNTL.F_GETFL

    try:
        O_NONBLOCK = os.O_NONBLOCK
    except AttributeError:
        import FCNTL
        O_NONBLOCK = FCNTL.O_NONBLOCK

    class PipeHandle(_PipeHandleCore):
        
        #
        # Local methods
        #

        def _readBytes(self, num_bytes = None):
            if num_bytes is None:
                return self.handle.read()
            else:
                return self.handle.read(num_bytes)

        def _SetNonblocking(self):
            fcntl.fcntl(self.handle.fileno(), F_SETFL,
                        O_NONBLOCK | fcntl.fcntl(self.handle.fileno(),
                                                 F_GETFL))

    # The poller expects poll(), register(), unregister().
    # In Unix, it's just poll().

    if hasattr(select, "poll"):

        def _getpoller():
            return select.poll()

        POLLIN = select.POLLIN
        POLLIN_WITH_PRI = select.POLLIN | select.POLLPRI

    else:

        class SelectPoller:

            def __init__(self):
                self.handles = {}

            # The only anticipated error below is a select.error,
            # and that's for some freakish Cygwin stuff.

            def poll(self, ms):
                return [(fd.fileno(), POLLIN) for fd in select.select(self.handles.keys(), [], [], float(ms) / 1000)[0]]

            def register(self, handle, flags):
                # Just ignore the flags.
                self.handles[handle] = True

            def unregister(self, handle):
                try:
                    del self.handles[handle]
                except:
                    pass

        def _getpoller():
            return SelectPoller()

        POLLIN = POLLIN_WITH_PRI = 0
    
# handle is a subprocess.Popen object.

class PidHandle:

    def __init__(self, handle):
        self.handle = handle

    def Status(self):
        p = self.handle.poll()
        if p is None:
            return _SUB_RUNNING
        else:
            return self._InterpretReturnCode(p)

    def ID(self):
        return self.handle.pid
    
    def _InterpretReturnCode(self, exitstatus):

        # Won't be called if the process is still running.
        # So it's exited. We'll never return _SUB_UNKNOWN from here.
        if exitstatus == 0:
            # Success!
            status = _SUB_SUCCESS
        elif exitstatus == -2:
            # Cntl-C is 2.
            status = _SUB_INTERRUPTED
        elif exitstatus < 0:
            status = _SUB_DIED
        else:                   
            status = _SUB_FAILURE
        return status

# Only useful if MAT.ExecutionContext._SUBPROCESS_STATISTICS is True.
# Let's see if I can check subprocesses. This is going
# to be ugly, because you need to check all the
# processes above this PID in the PID list, since
# processes know about their parents, not their
# children.

class ProcessMonitor:

    def __init__(self, p):
        self.rootProcess = p
        # Save this. It may be -1 by the tme we read it from the
        # psutil.Process object.
        self.rootPid = p.id
        import psutil
        proc = ProcessMonitorProcess(psutil.Process(self.rootPid))
        self.rootCreateTime = proc.subP.create_time
        self.pDict = {(self.rootPid, self.rootCreateTime): proc}

    def check(self):
        import psutil
        # OK, we need to build a PID tree, and the
        # only way to do that is to check all the PIDs,
        # EVERY TIME, and find the parent pid of the ones
        # that are greater than the current PID.
        curPid = self.rootPid
        # Must child pids be greater than their parent? No. Can't
        # use that as a shortcut, in general. If I want to monitor
        # all children, including remote ones, I need to build the
        # tree and THEN filter. I can eliminate p in 0, 1.
        pTree = {}
        for p in psutil.process_iter():
            try:
                ppid = p.ppid
                pid = p.pid
            except psutil.error.NoSuchProcess:
                continue
            except IOError:
                # No such process.
                continue
            if ppid < 2:
                continue
            else:
                try:
                    e = pTree[pid]
                    e[0] = p
                except KeyError:
                    e = [p, []]
                    pTree[pid] = e
                try:
                    pTree[ppid][1].append(e)
                except KeyError:
                    pTree[ppid] = [None, [e]]
        myTree = pTree[curPid]

        curKeys = self.pDict.keys()
        procsFound = set()
        # By the time I get around to checking this,
        # the process may have vanished. If it has,
        # don't record any info about it.
        def _recurse(e, s):
            thisProc = e[0]
            try:
                k = (thisProc.pid, thisProc.create_time)
                try:
                    thisPmProc = self.pDict[k]
                except KeyError:
                    thisPmProc = ProcessMonitorProcess(thisProc)
                thisPmProc.check()
                self.pDict[k] = thisPmProc
                procsFound.add(k)
            except psutil.error.NoSuchProcess:
                pass
            except IOError:
                # No such process.
                pass
            for a in e[1]:
                _recurse(a, s)
        _recurse(myTree, procsFound)
        
        # Anything we haven't found is ended.
        for k in set(curKeys) - procsFound:
            self.pDict[k].endTime = time.time()
        

    def report(self):
        self.pDict[(self.rootPid, self.rootCreateTime)].endTime = time.time()
        for p in self.pDict.values():
            p.report(self.rootProcess)                      

class ProcessMonitorProcess:

    def __init__(self, subP):
        import psutil
        self.maxResM, self.maxVM = 0, 0
        self.startTime = time.time()
        self.subP = subP
        self.cmdline = self.subP.cmdline
        self.uTime, self.sysTime = 0.0, 0.0
        self.endTime = self.startTime

    def check(self):
        resM, vM = self.subP.get_memory_info()
        self.maxResM = max(self.maxResM, resM)
        self.maxVM = max(self.maxVM, vM)
        self.uTime, self.sysTime = self.subP.get_cpu_times()

    def _suffixAndFloat(self, n):
        for suff in ["bytes", "KB", "MB", "GB"]:
            if n < 1024:
                return n, suff
            n = n / 1024.0
        return n, suff

    def report(self, stream):
        print >> stream , """TIME AND MEMORY for %s:
  %.2f seconds real clock time elapsed
  %.2f seconds user time
  %.2f seconds system time
  %.2f %s max resident memory
  %.2f %s max virtual memory""" % ((self.cmdline, self.endTime - self.startTime, self.uTime, self.sysTime) + self._suffixAndFloat(self.maxResM) + self._suffixAndFloat(self.maxVM))

# Put in **kw, so you can pass extra keys to it without its barfing.

class ExpectLikeProcess:
    
    def __init__(self, pre_expectations = None,
                 discard_output = False, verbose = None,
                 failure_pats = None, stdout = sys.stdout, **kw):
        if verbose is None:
            verbose = MAT.ExecutionContext._SUBPROCESS_DEBUG
        self.discard_output = discard_output
        self.stdout = stdout
        self.postExpectationInputQueue = []
        if pre_expectations:
            self.preExpectations = ExpectEngine(self, pre_expectations, failure_pats, verbose, stdout)
        else:
            self.preExpectations = None
        self.SetVerbose(verbose)
        self.SetSimulate(False)
        self._Reset()

    #
    # Local methods
    #

    def _ClearHandles(self):        
        self.outHandle = None
        self.inHandle = None
        self.errHandle = None
        self.statusHandle = None
        self.id = -1

    def expectationsSatisfied(self):
        self.preExpectationsSatisfied = True
        if self.postExpectationInputQueue:
            lines = self.postExpectationInputQueue
            self.postExpectationInputQueue = []
            self._InputLines(*lines)
        
    def _Reset(self):
        self.errBuf = ""
        self.outBuf = ""
        self._ClearHandles()
        self.exitStatus = _SUB_PRESTART
        self.duringExit = False
        self.failReason = None
        if self.preExpectations:
            self.preExpectationsSatisfied = False
        else:
            self.expectationsSatisfied()
        
    def _DoBuffer(self, buf, s, bufname, bufarrow):
        if self.verbose > 1:
            print >> self, ("[%d read]%s" % (self.id, bufarrow)), repr(s)
        lines = None
        if s:
            s = buf + s
            buf = ""
            # This will preserve the trailing lines, which is
            # what I want.
            lines = s.splitlines(True)
            if lines[-1][-1] != '\n':
                # It didn't end with a newline; push it back
                # on the buf.
                buf = lines[-1]
                lines[-1:] = []
        if buf and (self.verbose > 1):
            print >> self, ("[%d %s buffer]" % (self.id, bufname)), repr(buf)
        return buf, lines

    def _ErrorText(self, s):
        self.errBuf, lines = self._DoBuffer(self.errBuf, s, "err", "<<")
        self._ErrorLines(lines)

    # These two operations do the buffering. We never report
    # a partial line. The utility itself sees all the lines;
    # the application only sees the lines which aren't part
    # of the expectation exchange.

    def _OutputText(self, s):
        self.outBuf, lines = self._DoBuffer(self.outBuf, s, "out", "<")
        self._OutputLines(lines)

    def _OutputLines(self, lines):
        # We always should go through the expecter,  because
        # it may have a buffer to flush.
        if self.verbose:
            for line in lines:
                print >> self, ("[%d]<" % self.id), line,        
        if self.preExpectations:
            try:
                lines = self.preExpectations.OutputLines(lines)
            except ExpectError:
                self.Fail("initialization pattern not matched")
                return []
            except ErrorDuringExpect, e:
                self.Fail(e.message)
                return []
        if lines:
            self.OutputLines(*lines)

    def _ErrorLines(self, lines):
        # We always should go through the expecter,  because
        # it may have a buffer to flush.
        if self.verbose:
            for line in lines:
                print >> self, ("[%d]<<" % self.id), line,
        if self.preExpectations:
            try:
                lines = self.preExpectations.ErrorLines(lines)
            except ExpectError:
                self.Fail("initialization pattern not matched")
                return []
            except ErrorDuringExpect, e:
                self.Fail(e.message)
                return []
        if lines:
            self.ErrorLines(*lines)

    # handle is an PipeHandle

    def _ReadAndUpdate(self, handle, meth):
        if handle:
            # print >> sys.stderr, "*** About to read"
            status, data = handle.ReadBytes(-1)
            # print >> sys.stderr, "*** Done reading", data
            if status is not _DEFINITELY_DEAD:
                if data: meth(data)
            return status, len(data) > 0

    # handle is an PipeHandle
    
    def ReadHandler(self, handle):
        if handle:
            meth = None
            if handle is self.outHandle:
                meth = self._OutputText
            elif handle is self.errHandle:
                meth = self._ErrorText
            if meth:
                childStatus, readData = self._ReadAndUpdate(handle, meth)

                exitStatus = self._TimeToExit(childStatus)

                if exitStatus not in [ _SUB_RUNNING, _SUB_PRESTART ]:
                    # Dead.
                    self._Exit(exitStatus)
    
    def _TimeToExit(self, childStatus):
        if childStatus == _DEFINITELY_ALIVE:
            return _SUB_RUNNING
        elif not self.statusHandle:
            return _SUB_UNKNOWN
        else:
            return self.statusHandle.Status()


    #
    # Internal methods to be called by local children
    #

    def _Initialize(self, childIn, childOut, childErr, statusHandle, initString):
        self._Reset()
        if self.preExpectations:
            self.preExpectations.Initialize(self)
        self.inHandle = childIn
        self.outHandle = childOut        
        self.errHandle = childErr
        self.statusHandle = statusHandle
        if statusHandle:
            self.id = statusHandle.ID()
        if self.verbose:
            print >> self, "[%d: %s]" % (self.id, initString)
        self.exitStatus = _SUB_RUNNING

    # Exiting is always tricky, because you have to be careful not
    # to recursively exit.
    
    def _Exit(self, exitStatus, from_exit_parent = False):
        if (not from_exit_parent) and self.duringExit:
            return
        self.duringExit = True
        
        # Do a final read from both children. But somehow I have to ensure
        # that the read callbacks can't call Fail() or Stop(), since those
        # are already being called - or, more to the point, Fail() or Stop()
        # can't stop something that's already happening.
        if self.outHandle:
            self._ReadAndUpdate(self.outHandle, self._OutputText)
        if self.errHandle:
            self._ReadAndUpdate(self.errHandle, self._ErrorText)
        # Finally, close all the streams and remove the child.
        # This should flush what you have in the buffers.
        self._OutputLines([])
        self._ErrorLines([])
        # Now, call the exit handler.
        self._ExitHandler(exitStatus)        
        self.exitStatus = exitStatus
        self._ClearHandles()
    
    def _Start(self, **args):
        # Args can have verbose, simulate.
        if args.has_key("verbose"):
            self.SetVerbose(args["verbose"])
        if args.has_key("simulate"):
            self.SetSimulate(args["simulate"])
        if args.has_key("stdout"):
            self.SetStdout(args["stdout"])

    #
    # Private methods, perhaps implemented by children
    #
    
    def _ExitHandler(self, exitStatus):
        # Children will define this.
        pass

    #
    # Public methods, perhaps implemented by children
    #

    def SetVerbose(self, verbose):
        self.verbose = verbose
        if self.preExpectations:
            self.preExpectations.SetVerbose(verbose)

    def SetSimulate(self, simulate):
        self.simulate = simulate

    def SetStdout(self, stdout):
        self.stdout = stdout
        if self.preExpectations:
            self.preExpectations.SetStdout(stdout)

    def write(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()

    def SatisfyExpectations(self):
        # This happens when it's started up but its
        # expectations haven't been satisfied. If you want to
        # force the expectations to be satisfied before you
        # do something else, call this.
        if not self.preExpectations:
            return
        # The application could easily fail during this
        # period. Be careful. The expectations may have eaten
        # an error there. You'd better stop looping if
        # something bad has happened.
        while (not self.preExpectations.seqPassed) and \
              (self.exitStatus == _SUB_RUNNING):
            self.Poll()
    
    # The RunSynchronous method takes keys and values, as strings, and
    # returns a tuple of results. The keys are substituted
    # into a Python string: perhaps a command line, or perhaps
    # a string to send across to the server in the remote
    # case.    
    
    # This is oddly slow on Solaris. As far as I can tell, the problem is
    # entirely a matter of the subprocess startup time. Why?
    # For the first second or so, polling returns nothing. Works
    # fine on Linux, MacOS X.

    def RunSynchronous(self, **args):
        self._Start(**args)
        if self.simulate:
            return self.Status()
        if MAT.ExecutionContext._SUBPROCESS_STATISTICS:
            monitor = ProcessMonitor(self)
        pollDict = {}
        if self.statusHandle.Status() in [ _SUB_UNKNOWN, _SUB_INTERRUPTED,
                                           _SUB_KILLED, _SUB_DIED ]:
            # Don't check for _SUB_RUNNING, because it may already be done.
            print >> self, "Process failed to start."
            return
        pollObj = None
        if self.outHandle:
            if not pollObj:
                pollObj = _getpoller()
            pollObj.register(self.outHandle.handle, POLLIN_WITH_PRI)
            pollDict[self.outHandle.ID()] = self.outHandle
        if self.errHandle:
            if not pollObj:
                pollObj = _getpoller()
            pollObj.register(self.errHandle.handle, POLLIN_WITH_PRI)
            pollDict[self.errHandle.ID()] = self.errHandle
        
        # Now we loop.
        while True:
            avail = None
            if pollObj:
                # print >> self, "*** Polling"
                if MAT.ExecutionContext._SUBPROCESS_STATISTICS:
                    monitor.check()
                avail = pollObj.poll(.01)
                # print >> self, "*** Polled", avail
                for fd, event in avail:
                    try:
                        self.ReadHandler(pollDict[fd])
                    except KeyError:
                        pass
                    if self.exitStatus != _SUB_RUNNING:
                        break
            if self.exitStatus != _SUB_RUNNING:
                break
            if not avail:
                
                exitStatus = self.statusHandle.Status()

                if exitStatus not in [ _SUB_RUNNING, _SUB_PRESTART ]:
                    # Dead.
                    self._Exit(exitStatus)
                    break
                else:
                    time.sleep(0.1)

        if MAT.ExecutionContext._SUBPROCESS_STATISTICS:
            monitor.report()
                    
        return self.Status()
        
    def RunAsynchronous(self, **args):
        self._Start(**args)
        if self.simulate:
            return self.Status()
        self.exitStatus = self.statusHandle.Status()
        return self.exitStatus

    def Stop(self, exitStatus):
        raise ProcessError, "stop method not implemented"

    def Status(self):
        if self.exitStatus in [ _SUB_PRESTART, _SUB_RUNNING ]:
            return self.exitStatus, None
        # We check a bunch of stuff.
        if self.preExpectations and not self.preExpectations.seqPassed:
            # Oops, we never got done.
            if self.exitStatus == _SUB_SUCCESS:
                return _SUB_FAILURE, "initialization incomplete"
        if self.exitStatus != _SUB_SUCCESS:
            if self.failReason is not None:
                return self.exitStatus, self.failReason
            else:
                return self.exitStatus, "[reason unknown]"
        else:
            return _SUB_SUCCESS, None

    def Fail(self, reason):
        if self.duringExit and (self.failReason is not None):
            # Cleanup found more error output. Append it.
            # The formatting might not be perfect, but at least
            # we'll have the whole error.
            self.failReason += "\n"+reason
        else:
            self.failReason = reason
        self.Stop(_SUB_FAILURE)

    def Succeed(self):
        self.Stop(_SUB_SUCCESS)

    def InputLines(self, *lines):
        if self.preExpectationsSatisfied:
            self._InputLines(*lines)
        else:
            self.postExpectationInputQueue += list(lines)

    def _InputLines(self, *lines):
        if self.inHandle:
            self.inHandle.WriteBytes("".join(lines))
            if self.verbose:
                for line in lines:
                    print >> self, ("[%d]>" % self.id), line,

    # Specialize these to do something with the stdout, stdin,
    # or stderr of the child. In some cases, nothing will ever
    # happen with ErrorText.
    
    def OutputLines(self, *lines):
        pass
    
    def ErrorLines(self, *lines):
        pass

    def Poll(self):
        self.ReadHandler(self.outHandle)
        self.ReadHandler(self.errHandle)

# This code was stolen from my dexec package, trimmed down,
# and somewhat enhanced.

# popen2 is deprecated in 2.6.

import sys, os, errno

# Argh. Because of Cygwin and Java, I need a cmdline
# container which I can use to yield command lines. Poo.
# And it's a bit worse than I thought, because the way
# Windows processes its command line doesn't seem to do
# the right thing if shell is True, and I can't do
# a command line string with shell = False on Unix. So
# my best bet is just to use shell = False and pass
# in lists of tokens, rather than a cmdline string.

class CmdlineContainer:

    def __init__(self, cmdToks, pathDict = None, substDict = None, cmdIsWindowsNative = False):
        self.cmdToks = cmdToks
        self.cmdIsWindowsNative = cmdIsWindowsNative
        self.substDict = substDict = {}
        if pathDict is not None:
            self.substDict.update(pathDict)
            self.pathKeys = pathDict.keys()
        else:
            self.pathKeys = []

    def extend(self, cmdToks, pathDict = None, substDict = None):
        self.cmdToks += cmdToks
        if pathDict is not None:
            self.substDict.update(pathDict)
            self.pathKeys += pathDict.keys()
        if substDict is not None:
            self.substDict.update(substDict)

    def createCmdline(self, **args):
        # The idea is that anything that
        # was in the original path dict is
        # actually a path, which must be updated in Cygwin.
        keys = set(self.pathKeys)
        self.substDict.update(args)
        
        if self.cmdIsWindowsNative and (sys.platform == "cygwin"):
            for k in keys:
                self.substDict[k] = self._shellOutput("cygpath -w '%s'" % self.substDict[k]).strip()

        return [tok % self.substDict for tok in self.cmdToks]

    def _shellOutput(self, scmd):
        fp = subprocess.Popen(scmd, shell=True, stdout=subprocess.PIPE).stdout
        s = fp.read()
        fp.close()
        return s

class LocalProcess(ExpectLikeProcess):

    def __init__(self, cmdline, **args):
        if args.has_key("interleave_error"):
            self.interleave_error = args["interleave_error"]
            del args["interleave_error"]
        else:
            self.interleave_error = False
        ExpectLikeProcess.__init__(self, **args)
        if isinstance(cmdline, CmdlineContainer):
            self.cmdline = cmdline
        else:
            self.cmdline = CmdlineContainer(cmdline)
        self.child = None
    
    #
    # Internal methods to be called by local children
    #
    
    def _Start(self, **args):
        ExpectLikeProcess._Start(self, **args)
        if self.simulate:
            self.Succeed()
            return
        cmdline = self.cmdline.createCmdline(**args)
        # On Windows, discard_output can't be used, because
        # you'd have to kill the whole process group, and there's
        # no exec in CMD.EXE, which means you'd have to do something
        # complicated with process groups that isn't supported
        # straightforwardly in the subprocess module. So.
        # Actually, because of the incompatibilities in
        # shell commands, space escapes, etc., I'm just going
        # to not use shell at all anymore.
        if self.discard_output:
            raise ProcessError, "discard_output not supported"
        stdout = stderr = stdin = subprocess.PIPE
        shell = False
        if self.interleave_error:
            stderr = subprocess.STDOUT
        try:
            self.child = subprocess.Popen(cmdline, stdout = stdout, shell = shell,
                                          stderr = stderr, stdin = stdin)
        except Exception:
            if self.verbose:
                print >> self, "Cmdline is %s" % cmdline
            raise
        # self.child = popen2.Popen3(cmdline, not self.interleave_error)
        inHandle = outHandle = errHandle = None
        if self.child.stdout:
            if self.discard_output:
                self.child.stdout.close()
                self.child.stdout = None
            else:
                outHandle = PipeHandle(self.child.stdout, nonBlocking = True)
        if self.child.stderr:
            if self.discard_output:
                self.child.stderr.close()
                self.child.stderr = None
            else:
                errHandle = PipeHandle(self.child.stderr, nonBlocking = True)
        if self.child.stdin:
            inHandle = PipeHandle(self.child.stdin)
        self._Initialize(inHandle, outHandle, errHandle,
                         PidHandle(self.child), cmdline)

    def _Exit(self, exitStatus, from_exit_parent = False):
        if (not from_exit_parent) and self.duringExit:
            return
        self.duringExit = True
        ExpectLikeProcess._Exit(self, exitStatus, True)
        if self.child:
            for handle in [self.child.stdout, self.child.stderr, self.child.stdin]:
                if handle:
                    try:
                        handle.close()
                    except:
                        pass
            self.child = None

    #
    # Implementations of specialized public methods
    #

    def ErrorLines(self, *lines):
        self.Fail("".join(lines).strip())

    def Stop(self, exitStatus):
        if self.child:
            try:
                self.child.kill()
            except: pass
            self._Exit(exitStatus)

    def _ExitHandler(self, exitStatus):
        self.ExitHandler(self.child.stdout, self.child.stderr)

    # Children should subclass this if they want
    # something special to happen.
    
    def ExitHandler(self, childOut, childErr):
        pass

#
# A simple local process. If the process
# isn't being monitored, you don't need to
# do anything besides return a subprocess object.
#

class _SimpleLocalProcess:

    def __init__(self, cmdline, **kw):
        if isinstance(cmdline, CmdlineContainer):
            self.cmdline = cmdline
        else:
            self.cmdline = CmdlineContainer(cmdline)

    def RunSynchronous(self, stdout = sys.stdout, **kw):
        # If stdout doesn't have fileno, we need to capture
        # the data with a pipe and then write it out.
        if not hasattr(stdout, "fileno"):
            p = subprocess.Popen(self.cmdline.createCmdline(), stdout = subprocess.PIPE)
            o = p.communicate()[0]
            stdout.write(o)
            exitStatus = p.returncode
        else:
            exitStatus = subprocess.call(self.cmdline.createCmdline(), stdout = stdout)
        if exitStatus == 0:
            return _SUB_SUCCESS, None
        else:
            return _SUB_FAILURE, ("exit status was %d" % exitStatus)

def SimpleLocalProcess(*args, **kw):
    if MAT.ExecutionContext._SUBPROCESS_STATISTICS:
        return LocalProcess(*args, **kw)
    else:
        return _SimpleLocalProcess(*args, **kw)

#
# And here we have a "broker", which might choose to dismantle
# the document into a sequence of separate documents, and merge
# the results. It may also choose to extract the appropriate
# annotations without splitting up the document.
#

def brokerAnnotations(incomingDocs, docProcessor,
                      intervalExtractor = None, removeOnInput = None,
                      mergeOnOutput = None, truncateAndMergeOnOutput = None):
    # If you're going to do signal intervals or filtering, you have to do the
    # merging.
    if ((intervalExtractor is not None) or (removeOnInput is not None)) and \
       (mergeOnOutput is None) and (truncateAndMergeOnOutput is None):
        raise ProcessError, "signal intervals specified without output harvesting lists"
    # Now, let's prepare the inputs.
    docMap = None
    if intervalExtractor or removeOnInput or mergeOnOutput or truncateAndMergeOnOutput:
        origDocs = incomingDocs
        if intervalExtractor:
            incomingDocs = []
            docMap = {}
            for d in origDocs:
                signalIntervals = intervalExtractor(d)
                subDocs = [d.copy(removeAnnotationTypes = removeOnInput, signalInterval = s) for s in signalIntervals]
                incomingDocs += subDocs
                docMap[d] = (signalIntervals, subDocs)
        else:
            # The doc that gets processed should be a copy.
            incomingDocs = [d.copy(removeAnnotationTypes = removeOnInput) for d in incomingDocs]
            docMap = dict(zip(origDocs, incomingDocs))
    docProcessor(incomingDocs)
    # OK, they're done.
    if docMap is not None:
        # Time to undo the instructions. Reassemble the annotations.
        # We know that if there were signal intervals, we will have
        # merge things.
        if mergeOnOutput:
            allMerge = mergeOnOutput[:]
        else:
            allMerge = []
        if truncateAndMergeOnOutput:
            for m in truncateAndMergeOnOutput:
                # Truncate first.
                for d in docMap.keys():
                    try:
                        d.atypeDict[d.anameDict[m]] = []
                    except KeyError:
                        pass
                allMerge.append(m)
        # OK. Now things are truncated. So for each desired
        # annotation type, we create a new annotation in the original doc.
        for origD, sourceData in docMap.items():
            if intervalExtractor is not None:
                signalIntervals, sourceDList = sourceData
                for signalInterval, sourceD in zip(signalIntervals, sourceDList):
                    newStart = signalInterval[0]
                    origD.importAnnotations(sourceD, atypes = allMerge, offset = newStart)
            else:
                origD.importAnnotations(sourceData, atypes = allMerge)

#
# And even more finally, a wrapper which
# handles an annotation-set-specific document sequence.
#

# This command mixin creates a temporary directory and dumps
# the annotation sets, etc.

# We want to disassemble the main loop so that it's
# a matter of setup and shutdown and running, so that we
# can deal with callback contexts.

class FileSystemCmdlineIOMixin:

    def __init__(self, inVar = None, outVar = None,
                 fileDumper = None, fileLoader = None,
                 argsAreDirectories = False, **kw):
        self.inVar = inVar
        self.outVar = outVar
        self.argsAreDirectories = argsAreDirectories
        if self.inVar is None:
            raise ProcessError, "no input variable specified"
        if self.outVar is None:
            raise ProcessError, "no output variable specified"
        self.fileDumper = fileDumper
        self.fileLoader = fileLoader
        if self.fileDumper is None:
            raise ProcessError, "no file dumper specified"
        if self.fileLoader is None:
            raise ProcessError, "no file loader specified"

    def _cmdRun(self, vars):

        exitStatus, errMsg = self.RunSynchronous(simulate = False,
                                                 verbose = MAT.ExecutionContext._SUBPROCESS_DEBUG,
                                                 **vars)
        if exitStatus != _SUB_SUCCESS:
            # Oops.
            raise ProcessError, errMsg
        
    # cmd is an ExpectLikeProcesses.
    # iVar, oVar: input and output variables.
    # iWriter: the writer object to use to save the
    # input annotSet into the iVar.
    # oReader: the reader object to use to update the
    # output into the annotSet passed in.
    # tmpDir is the temp directory to use; if not specified,
    # one will be created and destroyed.

    def prepareInputs(self, annotSets, tmpDir):

        iVar = self.inVar
        oVar = self.outVar
        iWriter = self.fileDumper
        
        import random, string
        prefix = "".join([random.choice(string.letters) for x in range(5)])

        annotSetPairs = []
        inDir = os.path.join(tmpDir, prefix + "_" + iVar)
        outDir = os.path.join(tmpDir, prefix + "_" + oVar)
        varDir = {iVar: inDir, oVar: outDir}

        os.makedirs(inDir)
        os.makedirs(outDir)

        i = 0
        for annotSet in annotSets:
            annotSetPairs.append((annotSet, i))
            outP = os.path.join(inDir, str(i))
            # Write everything.
            iWriter.writeToTarget(annotSet, outP)
            i += 1

        return annotSetPairs, varDir

    def digestOutputs(self, annotSetPairs, varDir):
        
        outDir = varDir[self.outVar]
        oReader = self.fileLoader

        # Pull them all out.
        for annotSet, i in annotSetPairs:
            resultP = os.path.join(outDir, str(i))
            oReader.readFromSource(resultP, seedDocument = annotSet, update = True)

    def processAnnotSets(self, annotSets, **kw):
        brokerAnnotations(annotSets, self._processAnnotSets, **kw)

    def _processAnnotSets(self, annotSets):

        import MAT.ExecutionContext
        with MAT.ExecutionContext.Tmpdir() as tagDir:

            # If argsAreDirectories is True, iVar and oVar are directory
            # substitutions. If batch is False, they're file substitutions.

            annotSetPairs, varDir = self.prepareInputs(annotSets, tagDir)

            if self.argsAreDirectories is True:
                # Just do it once.
                self._cmdRun(varDir)
            else:
                # Do it once for each var.
                inDir = varDir[self.inVar]
                outDir = varDir[self.outVar]
                for set, i in annotSetPairs:
                    inP = os.path.join(inDir, str(i))
                    resultP = os.path.join(outDir, str(i))
                    d = varDir.copy()
                    for k, v in d.items():
                        if v == inDir:
                            d[k] = inP
                        elif v == outDir:
                            d[k] = resultP
                    self._cmdRun(d)

            self.digestOutputs(annotSetPairs, varDir)

# The local version.

class FileSystemCmdlineLocalProcess(LocalProcess, FileSystemCmdlineIOMixin):

    def __init__(self, cmdLine, **kw):
        LocalProcess.__init__(self, cmdLine, **kw)
        FileSystemCmdlineIOMixin.__init__(self, **kw)

# This is specifically for use with the command server below.
# Because we call the update for side effect, we use a wrapper.
# The serializations are byte sequences; all the encoding and
# decoding happens on the client.

class SerializationWrapper:

    def __init__(self, serialization):
        self.serialization = serialization

class RawIO:

    def writeToTarget(self, sWrapper, outFile):
        fp = open(outFile, "w")
        fp.write(sWrapper.serialization)
        fp.close()

    def readFromSource(self, inFile, seedDocument = None, update = True):
        fp = open(inFile, "r")
        seedDocument.serialization = fp.read()
        fp.close()

class FileSystemCmdlineAsynchronousProcess(LocalProcess, FileSystemCmdlineIOMixin):

    def __init__(self, cmdline, address, ioLine, preStart = False,
                 inVar = None, outVar = None,
                 argsAreDirectories = False, **kw):
        self.preStart = preStart
        LocalProcess.__init__(self, cmdline, **kw)
        exchanger = RawIO()
        FileSystemCmdlineIOMixin.__init__(self, fileDumper = exchanger,
                                          fileLoader = exchanger,
                                          inVar = inVar, outVar = outVar,
                                          argsAreDirectories = argsAreDirectories, **kw)
        self.commandServer = None
        self.requester = None
        self.address = address
        self.ioLine = ioLine
        self.curRequestData = None
        self.tmpDir = None
        
    def SetCommandServer(self, server):
        self.commandServer = server

    def RunAsynchronous(self, **args):
        if self.tmpDir is None:
            import tempfile
            self.tmpDir = tempfile.mkdtemp()
        s = LocalProcess.RunAsynchronous(self, **args)
        if self.child:
            if self.child.stdout:
                self.commandServer.RegisterHandler(
                    self.child.stdout,
                    self._ReadHandler)
            if self.child.stderr:
                self.commandServer.RegisterHandler(
                    self.child.stderr,
                    self._ReadHandler)

    def _ReadHandler(self, handleHandle):
        if handleHandle is self.child.stdout:
            self.ReadHandler(self.outHandle)
        elif handleHandle is self.child.stderr:
            self.ReadHandler(self.errHandle)

    def Stop(self, exitStatus):
        try:
            LocalProcess.Stop(self, exitStatus)
        finally:
            if self.tmpDir:
                import shutil
                shutil.rmtree(self.tmpDir)
                self.tmpDir = None

    def ExitHandler(self, childOut, childErr):
        if childOut:
            self.commandServer.UnregisterHandler(childOut)
        if childErr:
            self.commandServer.UnregisterHandler(childErr)
        if self.requester and not self.failReason:
            # Eh. This is bad. Somebody requested it, and
            # now it's hosed itself in the middle. But we don't want to
            # short-circuit the actual exit handling, so I see if
            # a failReason is set.
            self.Fail("server-side process exited for an unknown reason")
    
    def Fail(self, reason):
        LocalProcess.Fail(self, reason)
        # But we have to relay it to the caller.
        self.clientFail(reason)

    def Reserve(self, requester):
        self.requester = requester

    def Unreserve(self):
        self.requester = None

    def ReservedBy(self):
        return self.requester

    def clientSubmit(self, docSerialization):
        annotSetPairs, varDir = self.prepareInputs([SerializationWrapper(docSerialization)], self.tmpDir)
        self.curRequestData = annotSetPairs, varDir
        inDir = varDir[self.inVar]
        outDir = varDir[self.outVar]
        annotSet, i = annotSetPairs[0]
        inP = os.path.join(inDir, str(i))
        resultP = os.path.join(outDir, str(i))
        d = varDir.copy()
        for k, v in d.items():
            if v == inDir:
                d[k] = inP
            elif v == outDir:
                d[k] = resultP
        self.InputLines(self.ioLine % d)

    # These are the two functions which can be called by, e.g., OutputLines or
    # ErrorLines.
    
    def clientSucceed(self):
        if self.curRequestData is not None:
            annotSetPairs, varDir = self.curRequestData
            self.curRequestData = None
            self.digestOutputs(annotSetPairs, varDir)
            import shutil
            shutil.rmtree(varDir[self.inVar])
            shutil.rmtree(varDir[self.outVar])
            if self.requester:
                # Pull out the result serialization
                self.commandServer.clientSucceed(self.requester, annotSetPairs[0][0].serialization)

    def clientFail(self, msg):
        if self.curRequestData is not None:
            self.curRequestData = None
            if self.requester:
                self.commandServer.clientFail(self.requester, msg)

    # Create and return a remote proxy.

    def remoteProxy(self, host, port, dumper, loader):
        # return RemoteBase64Process(self.address, host, port)
        return RemoteXMLRPCProcess(self.address, host, port, dumper, loader)

    def localProxy(self, broker, dumper, loader):
        return FileSystemLocalProxy(self.address, broker, dumper, loader)

# And now, for XML-RPC. Pret-ty simple.

import xmlrpclib

class RemoteXMLRPCProcess:

    def __init__(self, pTuple, host, port, dumper, loader):
        self.pTuple = pTuple
        self.host = host
        self.port = port
        self.dumper = dumper
        self.loader = loader

    def processAnnotSet(self, annotSet):
        
        if annotSet is None:
            raise ProcessError, "no document"
        # Order of arguments: address, document.
        import socket
        try:
            d = xmlrpclib.ServerProxy("http://%s:%d/MAT/xmlrpc" % (self.host, self.port), allow_none = True).tag(
                self.pTuple, xmlrpclib.Binary(self.dumper.writeToByteSequence(annotSet)))
        except socket.error, e:
            raise ProcessError, ("Remote tagger service error (%s); consider specifying tagger_local to avoid contacting the server" % e)
        # Decode the document. I have to do what
        # the file-based version does: modify the input
        # document for side effect.
        self.loader.readFromByteSequence(d, seedDocument = annotSet, update = True)

    # The update of the results happens in OutputLines.

    def processAnnotSets(self, annotSets, **kw):
        brokerAnnotations(annotSets, self._processAnnotSets, **kw)

    def _processAnnotSets(self, annotSets):
        for annotSet in annotSets:
            try:
                self.processAnnotSet(annotSet)
            except xmlrpclib.Fault, e:
                # Oops.
                raise ProcessError, e.faultString

class FileSystemLocalProxy:

    def __init__(self, pTuple, broker, dumper, loader):
        self.pTuple = pTuple
        self.broker = broker
        self.dumper = dumper
        self.loader = loader

    def processAnnotSets(self, annotSets, **kw):
        brokerAnnotations(annotSets, self._processAnnotSets, **kw)

    def _processAnnotSets(self, annotSets):
        for annotSet in annotSets:
            d = self.broker.request(self.pTuple, self.dumper.writeToByteSequence(annotSet))
            self.loader.readFromByteSequence(d, seedDocument = annotSet, update = True)

# Here's the object that manages the thread on the other end.
# We have a Queue, which is synchronized; a lock for each
# child process; and a condition for each request. Complicated.

import threading, Queue

class ThreadedTaggerRequest:

    def __init__(self, address, document):
        self.address = " ".join(address)
        # This is a hash structure, not an AnnotatedDoc.
        self.document = document
        self.condition = threading.Condition()
        self.process = None
        # For the result.
        self.success = False
        self.error = None

class XMLRPCCommandServer:
    
    def __init__(self, *async_processes, **kw):

        self.procDict = {}
        if kw.has_key('stdout'):
            self.stdout = kw["stdout"]
        else:
            self.stdout = sys.stdout
        for taskName, servName, async_process in async_processes:
            if not isinstance(async_process, FileSystemCmdlineAsynchronousProcess):
                raise ProcessError, "process must be child of FileSystemCmdlineAsynchronousProcess"
            else:
                self.procDict[taskName + " " + servName] = (async_process, threading.Lock())
                async_process.SetCommandServer(self)
        
        self.poller = _getpoller()
        # Mapping from file numbers to callbacks.
        self.poll_dict = {}
        self.exited = False
        self.taggerThread = None
        self.queue = Queue.Queue()

    def write(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()

    # End execution manager API.
    
    def RunChild(self, async_process):

        status, reason = async_process.Status()

        if status == _SUB_PRESTART:
            async_process.RunAsynchronous(stdout = self.stdout)
            # async_process.SatisfyExpectations()
        elif status != _SUB_RUNNING:
            # Force a shutdown. Just in case. This should unregister
            # the handlers.
            async_process.Stop(_SUB_KILLED)
            print >> self, "[Restarting.]"
            async_process.RunAsynchronous(stdout = self.stdout)
            # async_process.SatisfyExpectations()
            
    def Run(self):

        self.exited = False

        # print "Thread started", threading.currentThread()

        # queue is a locked, synchronized queue.
        
        for async_process, pLock in self.procDict.values():
            if async_process.preStart:
                self.RunChild(async_process)

        # Every 10 ms, time out.
        
        try:
            while True:
                try:
                    newItem = self.queue.get_nowait()
                    # print "Got an item", threading.currentThread()
                    self.insertRequest(newItem)
                except Queue.Empty:
                    pass
                try:
                    fd_list = self.poller.poll(10)
                except select.error, e:
                    # Cygwin has this as a possibility. On Mac,
                    # you can't interrupt the system call in a thread.
                    pass
                if self.exited:
                    # print "Got a break", threading.currentThread()
                    break
                for fd, event in fd_list:
                    # print "Doing", fd, event, threading.currentThread()
                    self.poll_dict[fd]()
        except Exception:
            self.exited = True
            import traceback
            print >> self, traceback.format_exc()
        self._cleanup()
            
    def _cleanup(self):
        # print "Cleaning up", threading.currentThread()
        for async_process, pLock in self.procDict.values():
            async_process.Stop(_SUB_KILLED)
            req = async_process.ReservedBy()
            if req is not None:
                self.reportFailure(req, "server terminated")
        # Fail the pending requests.
        while True:
            try:
                newItem = self.queue.get_nowait()
                self.reportFailure(newItem, "server terminated")
            except Queue.Empty:
                break
        
    def RegisterHandler(self, handle, callback):
        self.poller.register(handle, POLLIN)
        self.poll_dict[handle.fileno()] = lambda h = handle, c = callback: c(h)

    def UnregisterHandler(self, handle):        
        self.poller.unregister(handle)
        del self.poll_dict[handle.fileno()]

    def clientSucceed(self, req, resultObj):
        self.reportSuccess(req, resultObj)

    def clientFail(self, req, msg):
        self.reportFailure(req, msg)

    def reportSuccess(self, req, resultObj):
        req.document = resultObj
        req.success = True
        self.releaseRequest(req)

    def reportFailure(self, req, msg):
        req.error = msg
        req.success = False
        self.releaseRequest(req)

    def releaseRequest(self, req):
        # print "Releasing from a job", threading.currentThread()
        if req.process:
            req.process.Unreserve()
            ignore, pLock = self.procDict[req.address]
            pLock.release()
        req.condition.notify()
        req.condition.release()

    def insertRequest(self, req):

        # Always, always acquire the condition before you do anything.
        # print "Acquiring for a job", threading.currentThread()
        req.condition.acquire()

        if self.exited:
            # Fail.
            self.reportFailure(req, "thread has exited")
            return

        # If the object is available (i.e., not reserved by another
        # socket), reserve it and send the input.
        try:
            p, pLock = self.procDict[req.address]
        except KeyError:
            print >> self, "[Reporting error: %s not found]" % req.address
            self.reportFailure(req, "The tagger service with the address '%s' was not found" % req.address)
            return

        if not pLock.acquire(False):
            # Can't acquire the lock.
            print >> self, "[Reporting error: %s busy]" % req.address
            self.reportFailure(req, "The tagger service with the address '%s' is busy" % req.address)
            return

        # OK, we have the lock.
        req.process = p
        p.Reserve(req)
        self.RunChild(p)
        p.clientSubmit(req.document)

    # Requesting thread.
    
    def request(self, curAddress, docSerialization):

        if not self.taggerThread:
            raise ProcessError, "no tagger thread"

        # This variable isn't locked, but
        # I check  it everywhere.
        if self.exited:
            raise ProcessError, "thread has exited"

        req = ThreadedTaggerRequest(curAddress, docSerialization)
        # print "Requesting a job", threading.currentThread()
        req.condition.acquire()
        # Put it on the queue. The thread, when it reads from the
        # queue, should acquire the condition before it does anything.
        self.queue.put(req)
        # print "Waiting on a job", threading.currentThread()
        req.condition.wait()
        # Don't need the lock anymore. Release it.
        req.condition.release()
        # print "Done waiting on a job", threading.currentThread()
        if req.success is False:
            raise ProcessError, req.error
        # Will have been surgically altered.
        return req.document

    # External control. Compatible with CherryPy.

    def start(self):
        if self.taggerThread is None:
            self.taggerThread = threading.Thread(target = self.Run)
            self.taggerThread.setName("Tagger thread " + self.taggerThread.getName())
            self.taggerThread.start()

    def stop(self):
        # print "Before requesting a break", threading.currentThread()
        if self.taggerThread and (not self.exited):
            # print "Requesting a break", threading.currentThread()
            self.exited = True

#
# Important utility
#

# We have to worry about how to invoke Java in the case
# of Cygwin, because Cygwin doesn't have its own Java.
# All paths must be converted. This all has to happen in
# the evaluation of CmdlineContainer, because other paths are factored in down there.

def _jarInvocation(jPath, jar, heap_size = None, stack_size = None, cls = None,
                   task = None, classPath = None, javaParams = None, **kw):
    # The task, if present, contains defaults for heap and stack size.
    # These defaults can be cancelled by having the heap_size or stack_size
    # be the empty string.
    if task is not None:
        defaults = task.getJavaSubprocessParameters()
        if heap_size is None:
            heap_size = defaults.get("heap_size")
        if stack_size is None:
            stack_size = defaults.get("stack_size")
    if heap_size and (heap_size is not None):
        heapSize = ["-Xmx"+heap_size]
    else:
        heapSize = []
    if stack_size and (stack_size is not None):
        stackSize = ["-Xss"+stack_size]
    else:
        stackSize = []
    if classPath is None:
        classPath = []
    s = [jPath] + heapSize + stackSize
    if jar is not None:
        pathDict = {"jar": jar}
    else:
        pathDict = {}
    if classPath is None:
        classPath = []
    classStrings = []
    i = 0
    for elt in classPath:
        classStr = "cpentry" + str(i)
        pathDict[classStr] = elt
        classStrings.append("%(" + classStr + ")s")
        i += 1
    if (jar is not None) and (cls is not None):
        classStrings[0:0] = ["%(jar)s"]
    if classStrings:
        if sys.platform == "win32":
            sep = ";"
        else:
            sep = ":"        
        s += ["-cp", sep.join(classStrings)]
    if javaParams is not None:
        s += javaParams
    if cls is not None:
        s += [cls]
    elif jar is not None:
        s += ["-jar", "%(jar)s"]
    # Java is Windows native if we're under Cygwin. But jPath
    # must be not converted, since if we're under Cygwin, it needs
    # to be a Unix-y path.    
    return CmdlineContainer(s, pathDict = pathDict,
                            cmdIsWindowsNative = True)
