# Copyright (C) 2010 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# We're going to require Python 2.6, because we need sqlite3.

# Note that this contains all the DB manipulations, including those for
# the reconciliation folder, even though we haven't migrated reconciliation
# from TooCAAn into here yet. I think that's OK.

import sqlite3, os, re

DB_SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ws_db.sql")

class WorkspaceDBError(Exception):
    pass

# There's an upper limit on the number of sqlite variables
# you can have. On all platforms other than the Mac, which has its
# own build, the limit is 999. If you have a workspace with more
# than 999 basenames in it, bad things will happen in a number
# of the queries below, if we don't guard against it. So I've
# written some special-case handling for the variable-length
# query arguments. And I'm going to set the limit lower here.

SQLITE_VARIABLE_LIMIT = 500

class WorkspaceDB:

    def __init__(self, ws):
        self.workspace = ws
        self.wsDBFile = os.path.join(ws.dir, "ws_db.db")
        self.conn = None
        self.savepoint = "sp1"
        self.autocommit = True
        if not os.path.exists(self.wsDBFile):
            self.run_script(DB_SCHEMA)
        # I don't really want to do isolation_level = None, since this is
        # autocommit mode, but the problem is that unfortunately,
        # sqlite3 starts a transaction before modifying statements,
        # and commits them before non-modifying statements.
        # If I go into autocommit mode, then I can control
        # commits explicitly with BEGIN TRANSACTION, etc.
        # But that doesn't seem to be working either.
        self.conn = sqlite3.connect(self.wsDBFile, isolation_level = None)

    def run_script(self, script):
        conn = sqlite3.connect(self.wsDBFile)
        c = conn.cursor()
        fp = open(script, "r")
        s = fp.read()
        fp.close()
        c.executescript(s)
        c.close()
        # Make damn sure that the DB is saved.
        conn.commit()            
        conn.close()        

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    # In case someone forgets to close it explicitly...
    def __del__(self):
        self.close()

    # query wrapper utility. If many is True, params
    # should be a list of lists.
    
    def _execute(self, stmt, params = None, many = False, retrieval = True):
        if self.conn is None:
            raise WorkspaceDBError, "operation on closed connection"
        c = self.conn.cursor()
        if params is not None:
            if many:
                c.executemany(stmt, params)
            else:
                c.execute(stmt, params)
        else:
            c.execute(stmt)
        if retrieval:
            res = c.fetchall()
        else:
            if self.autocommit:
                self.conn.commit()
            res = None
            if self.workspace.logger:
                self.workspace.logger.logDBUpdate(stmt, params, many)
        c.close()
        return res

    # Even more of an abstraction. In this case, we have a dict
    # of params, and $(key) in the statement. If any of the params are
    # lists, we have to deal with the possibility that the length
    # of the list may exceed the variable limit. In that case, we need
    # to recursively loop down to calls to _execute and then assemble
    # the results. many = False for all of these.

    # Step 1: convert the keys to %s. I've used my own $(key) pattern
    # because it may be more reliable than the ?.

    # Note that the number of variables permitted at each position
    # will vary, because we need to keep the TOTAL number
    # of variables in each call under the limit. 

    PARAM_DICT_PAT = re.compile("\$\(([^)]+?)\)")
    
    def _executeWithParamDict(self, stmt, paramDict, retrieval = True):
        keyOrder = [m.group(1) for m in self.PARAM_DICT_PAT.finditer(stmt)]
        if not (set(keyOrder) <= set(paramDict.keys())):
            raise WorkspaceDBError, "param dict doesn't contain all the statement keys"
        # There may be duplicates here. That's OK.
        paramsInOrder = [paramDict[key] for key in keyOrder]

        if not paramsInOrder:
            # We may not actually end up using any params.
            return self._execute(stmt, retrieval = retrieval)
        
        # Escape any percents, then add %s.
        stmt = self.PARAM_DICT_PAT.sub("%s", stmt.replace("%", "%%"))

        # I need to recursively assemble this list of things to
        # execute. But I need to make sure that we impose
        # the appropriate limits. We can't have more than a
        # TOTAL of SQLITE_VARIABLE_LIMIT.

        singletons = 0
        totalInLists = 0
        numLists = 0

        for p in paramsInOrder:
            if type(p) in (list, tuple):
                totalInLists += len(p)
                numLists += 1
            else:
                singletons += 1

        if (totalInLists + singletons) > SQLITE_VARIABLE_LIMIT:
            # This is integer division, so it'll round down.
            listLimit = (SQLITE_VARIABLE_LIMIT - singletons) / numLists
        else:
            # This will never actually get used, the way things
            # play out below.
            listLimit = SQLITE_VARIABLE_LIMIT

        paramLists = []

        def recurseParams(seeds, substs, remainingParams):
            if not remainingParams:
                paramLists.append((seeds, substs))
            else:
                seed = remainingParams[0]
                if type(seed) in (list, tuple):
                    if len(seed) > listLimit:
                        i = 0
                        while i < len(seed):
                            newSeed = seed[i:i+listLimit]
                            recurseParams(seeds + list(newSeed),
                                          substs + [", ".join(["?"] * len(newSeed))],
                                          remainingParams[1:])
                            i += listLimit
                    else:
                        recurseParams(seeds + list(seed),
                                      substs + [", ".join(["?"] * len(seed))],
                                      remainingParams[1:])
                else:
                    recurseParams(seeds + [seed], substs + ["?"], remainingParams[1:])

        recurseParams([], [], paramsInOrder)

        results = []
        for (seeds, substs) in paramLists:
            res = self._execute((stmt % tuple(substs)),
                                params = seeds,
                                retrieval = retrieval)
            if retrieval:
                results += res
        if retrieval:
            return results
        else:
            return None                

    def dumpDatabase(self, tables = None):
        allTables = self.getTables()
        if tables is None:
            tables = allTables
        else:
            tables = [t for t in tables if t in allTables]
        return [{"table": t, "columns": [r[1] for r in self._execute("PRAGMA table_info(%s)" % t)],
                 "data": self._execute("SELECT * from %s" % t)} for t in tables]

    def getTables(self):
        return [r[0] for r in self._execute("SELECT name FROM sqlite_master WHERE type='table'")]
            

    #
    # Second section: document info
    #

    def insertDocument(self, docName, basename, status, assignedUser = None):
        self._execute("INSERT INTO document_info VALUES (?, ?, ?, NULL, ?, NULL)",
                      params = [docName, basename, assignedUser, status],
                      retrieval = False)

    def updateDocumentStatus(self, docName, status):
        self._execute("UPDATE document_info SET status = ? WHERE doc_name = ?",
                      params = [status, docName],
                      retrieval = False)

    def basenameInfo(self, basenames):
        return self._executeWithParamDict("SELECT doc_name, basename, status, assigned_user, locked_by FROM document_info WHERE basename IN ($(basenames)) ORDER BY basename", {"basenames": basenames})

    def basenameAssignedToUser(self, basename, user):
        return len(self._execute("SELECT basename, assigned_user FROM document_info WHERE basename = ? and assigned_user = ?",
                                 params = [user, basename])) > 0

    def allBasenames(self, basenames = None):
        q = "SELECT DISTINCT basename FROM document_info"
        if basenames is not None:
            q += " WHERE basename IN ($(basenames))"
        return [r[0] for r in self._executeWithParamDict(q, {"basenames": basenames})]

    def documentsForBasenames(self, basenames = None):
        d = {}
        curBasename = None
        q = "SELECT basename, doc_name FROM document_info"
        if basenames is not None:
            q += " WHERE basename IN ($(basenames))"
        for row in self._executeWithParamDict(q + " ORDER BY basename",
                                              {"basenames": basenames}):
            basename, docName = row
            if curBasename != basename:
                curBasename = basename
                d[curBasename] = [docName]
            else:
                d[curBasename].append(docName)
        return d

    # This can return None if there is no appropriate document.
    # If the user is None, don't match any of the assigned files.
    # If the user is not None, try for an assigned file.
    
    def documentForBasenameAndUser(self, basename, user):
        r = []
        if user is not None:
            r = self._execute("SELECT doc_name FROM document_info WHERE basename = ? and assigned_user = ?",
                              params = [basename, user])
        if not r:
            r = self._execute("SELECT doc_name FROM document_info WHERE basename = ? and assigned_user IS NULL",
                              params = [basename])
        if not r:
            return None
        else:
            return r[0][0]

    def basenameForDocname(self, docName):
        r = self._execute("SELECT basename FROM document_info WHERE doc_name = ?",
                          params = [docName])
        if not r:
            return None
        else:
            return r[0][0]

    def usersForBasenames(self, basenames):
        r = self._executeWithParamDict("SELECT assigned_user, basename FROM document_info WHERE basename IN ($(basenames)) ORDER BY basename", {"basenames": basenames})
        d = {}
        curBasename = None
        for [user, basename] in r:
            # Note: user may be None.
            if curBasename != basename:
                curBasename = basename
                d[curBasename] = [user]
            else:
                d[curBasename].append(user)
        return d

    def coreDocumentStatus(self, docName):
        r = self._execute("SELECT status FROM document_info WHERE doc_name = ?",
                          params = [docName])
        if not r:
            return None
        else:
            return r[0][0]

    def removeUnassignedBasenameEntry(self, basename):
        self._execute("DELETE FROM document_info WHERE basename = ? AND assigned_user IS NULL",
                      params = [basename], retrieval = False)
        
    #
    # Third section: user management
    #

    def registerUsers(self, users, roles):
        self._execute("INSERT INTO users VALUES (?)",
                      params = [[u] for u in users],
                      many = True, retrieval = False)
        self._execute("INSERT INTO user_roles VALUES (?, ?)",
                      params = [[u, r] for u in users for r in roles],
                      retrieval = False, many = True)

    # Can't use parameter substitution.
    def unregisterUsers(self, *users):
        self._executeWithParamDict("DELETE FROM users WHERE user in ($(users))",
                                   {"users": users}, retrieval = False)
        self._executeWithParamDict("DELETE FROM user_roles WHERE user in ($(users))",
                                   {"users": users}, retrieval = False)

    def userIsRegistered(self, user):
        return self._execute("SELECT COUNT(*) FROM users WHERE user = ?",
                             params = [user])[0][0] > 0

    def listUsers(self):
        return [x[0] for x in self._execute("SELECT user FROM users")]


    def listUsersForRole(self, role):
        return [x[0] for x in self._execute("SELECT DISTINCT user FROM user_roles WHERE role = ?",
                                            params = [role])]

    def listUsersAndRoles(self):
        d = {}
        for user, role in self._execute("SELECT A.user, B.role FROM users A LEFT JOIN user_roles B ON A.user = B.user"):
            try:
                entry = d[user]
            except KeyError:
                entry = []
                d[user] = entry
            if role is not None:
                entry.append(role)
        return d

    def removeUserRoles(self, users, roles):
        self._execute("DELETE FROM user_roles WHERE user = ? AND role = ?",
                      params = [[u, r] for u in users for r in roles],
                      many = True, retrieval = False)

    def addUserRoles(self, users, roles):
        # First, delete them, because we don't want any duplicates.
        self.removeUserRoles(users, roles)
        self._execute("INSERT INTO user_roles VALUES (?, ?)",
                      params = [[u, r] for u in users for r in roles],
                      many = True, retrieval = False)
        
    def userHasRole(self, user, role):
        return len(self._execute("SELECT user, role FROM user_roles WHERE user = ? AND role = ?",
                                 params = [user, role])) > 0
    
    # Unregistering users is a bit trickier. You should fail
    # to unregister any user who's got something locked, or is
    # involved in reconciliation.

    def usersInUse(self):
        return [x[0] for x in self._execute("SELECT DISTINCT assigned_user FROM document_info")], \
               [x[0] for x in self._execute("SELECT DISTINCT locked_by FROM document_info")], \
               [x[0] for x in self._execute("SELECT DISTINCT locked_by FROM reconciliation_phase_info")], \
               [tuple(t) for t in self._execute("SELECT DISTINCT reviewer, reconciliation_phase FROM reconciliation_assignment_info")]

    #
    # Fourth section: locking
    #

    # The strategies for locking core and reconciliation are different.

    def lockCoreDocument(self, lockId, docName, lockedBy):
        self._execute("UPDATE document_info SET locked_by = ?, lock_id = ? WHERE doc_name = ?",
                      params = [lockedBy, lockId, docName],
                      retrieval = False)

    def lockReconciliationBasename(self, lockId, basename, lockedBy):
        self._execute("UPDATE reconciliation_phase_info SET locked_by = ?, lock_id = ? WHERE basename = ?",
                      params = [lockedBy, lockId, basename],
                      retrieval = False)

    # I actually need the name of the locking user, so I can force an unlock
    # if the user who requests this document is the same as the user that
    # locked it.
    
    def coreDocumentLocked(self, docName):
        lockedByResult = self._execute("SELECT locked_by FROM document_info WHERE locked_by IS NOT NULL AND doc_name = ? LIMIT 1",
                                       params = [docName])
        if not lockedByResult:
            return None
        else:
            return lockedByResult[0][0]

    def reconciliationBasenameLocked(self, basename):
        lockedByResult = self._execute("SELECT locked_by FROM reconciliation_phase_info WHERE locked_by IS NOT NULL AND basename = ? LIMIT 1",
                                       params = [basename])
        if not lockedByResult:
            return None
        else:
            return lockedByResult[0][0]

    def taggableDocumentsLocked(self):
        return self._execute("SELECT COUNT(*) FROM document_info WHERE locked_by IS NOT NULL AND locked_by != 'RECONCILIATION'")[0][0] > 0


    def coreGetLockIDInfo(self, lockId):
        v = self._execute("SELECT doc_name, basename, locked_by FROM document_info WHERE lock_id = ?",
                          params = [lockId])
        if len(v) == 0:
            return None, None, None
        else:
            return v[0]

    def unlockCoreLock(self, lockId):
        self._execute("UPDATE document_info SET locked_by = NULL, lock_id = NULL WHERE lock_id = ?",
                      params = [lockId],
                      retrieval = False)

    def unlockReconciliationLock(self, lockId):
        self._execute("UPDATE reconciliation_phase_info SET locked_by = NULL, lock_id = NULL WHERE lock_id = ?",
                      params = [lockId],
                      retrieval = False)

    # Another situation where we can't use substitution because I need "IN".
    def forceUnlockCoreBasenames(self, user, basenames):
        docLocksToDelete = [r[0] for r in self._executeWithParamDict("SELECT doc_name FROM document_info WHERE locked_by = $(user) AND basename IN ($(basenames))", {"user": user, "basenames": basenames})]
        if docLocksToDelete:
            self._executeWithParamDict("UPDATE document_info SET locked_by = NULL, lock_id = NULL WHERE doc_name IN ($(docLocksToDelete))", {"docLocksToDelete": docLocksToDelete}, retrieval = False)
        return docLocksToDelete

    def forceUnlockReconciliationBasenames(self, user, basenames):
        basenameLocksToDelete = [r[0] for r in self._executeWithParamDict("SELECT basename FROM reconciliation_phase_info WHERE locked_by = $(user) AND basename IN ($(basenames))", {"user": user, "basenames": basenames})]
        if basenameLocksToDelete:
            self._executeWithParamDict("UPDATE reconciliation_phase_info SET locked_by = NULL, lock_id = NULL WHERE basename IN ($(basenameLocksToDelete))", {"basenameLocksToDelete": basenameLocksToDelete}, retrieval = False)
        return basenameLocksToDelete

    #
    # Fifth section: reconciliation management
    #

    def submitToReconciliation(self, basename, firstPhase, assignments):
        self._execute("INSERT INTO reconciliation_phase_info VALUES (?, ?, NULL, NULL)",
                      params = [basename, firstPhase],
                      retrieval = False)
        self._execute("INSERT INTO reconciliation_assignment_info VALUES (?, ?, ?, 0)",
                      params = [(basename, phase, reviewer) for (phase, reviewer) in assignments],
                      many = True, retrieval = False)

    def beingReconciled(self, basename):
        return self._execute("SELECT COUNT(*) FROM reconciliation_phase_info WHERE basename = ?",
                             params = [basename])[0][0] > 0

    def removeFromReconciliation(self, basename):
        self._execute("DELETE FROM reconciliation_phase_info WHERE basename = ?",
                      params = [basename],
                      retrieval = False)
        self._execute("DELETE from reconciliation_assignment_info WHERE basename = ?",
                      params = [basename],
                      retrieval = False)

    def getNextReconciliationDocument(self, user):
        docs = self._execute("SELECT a.basename FROM reconciliation_phase_info a, reconciliation_assignment_info b WHERE a.basename = b.basename and a.reconciliation_phase = b.reconciliation_phase and b.done = 0 and b.reviewer = ? and a.locked_by IS NULL LIMIT 1",
                             params = [user])
        if len(docs) == 1:
            return docs[0][0]
        else:
            return None

    def getReconciliationQueue(self, user):
        return self._execute("SELECT a.basename, a.reconciliation_phase FROM reconciliation_phase_info a, reconciliation_assignment_info b WHERE a.basename = b.basename and a.reconciliation_phase = b.reconciliation_phase and b.done = 0 and b.reviewer = ? and a.locked_by IS NULL",
                             params = [user])

    def reconciliationLockIDMatches(self, lockId, basename):
        return self._execute("SELECT COUNT(*) FROM reconciliation_phase_info WHERE basename = ? AND lock_id = ?",
                             params = [basename, lockId])[0][0] > 0

    def reconciliationPhaseForBasename(self, basename):
        return self._execute("SELECT reconciliation_phase FROM reconciliation_phase_info WHERE basename = ?",
                             params = [basename])[0][0]
    
    def reconciliationGetLockInfo(self, lockId):
        v = self._execute("SELECT basename, locked_by, reconciliation_phase FROM reconciliation_phase_info WHERE lock_id = ?",
                          params = [lockId])
        if len(v) == 0:
            return None, None, None
        else:
            return v[0][0], v[0][1], v[0][2]

    def reconciliationUserDoneInPhase(self, user, basename, phase):
        self._execute("UPDATE reconciliation_assignment_info SET done = 1 WHERE reviewer = ? AND basename = ? AND reconciliation_phase = ?",
                      params = [user, basename, phase],
                      retrieval = False)

    def reconciliationDocumentDoneInPhase(self, basename, phase):
        # If there are no rows for this basename and phase which aren't done,
        # the document is done.
        return self._execute("SELECT count(*) FROM reconciliation_assignment_info WHERE basename = ? and reconciliation_phase = ? and done = 0", params = [basename, phase])[0][0] == 0

    def advanceReconciliationDocument(self, basename, phase):
        self._execute("UPDATE reconciliation_phase_info SET reconciliation_phase = ? where basename = ?",
                      params = [phase, basename],
                      retrieval = False)

    def reconciliationInfo(self, basenames):
        # For listing folders. For reconciliation, we want to know
        bPrev = None
        bEntries = []
        for basename, phase, lockedBy, reviewer in self._executeWithParamDict("SELECT A.basename, A.reconciliation_phase, A.locked_by, B.reviewer FROM reconciliation_phase_info A, reconciliation_assignment_info B WHERE A.basename = B.basename and A.reconciliation_phase = B.reconciliation_phase and B.done = 0 and A.basename IN ($(basenames)) ORDER BY A.basename", {"basenames": basenames}):
            if basename != bPrev:
                bEntries.append([basename, phase, lockedBy, [reviewer]])
                bPrev = basename
            else:
                bEntries[-1][-1].append(reviewer)
        return bEntries

    def usersAvailableForPhase(self, basename, phase):
        return [entry[0] for entry in \
                self._execute("SELECT reviewer from reconciliation_assignment_info where basename = ? and reconciliation_phase = ?",
                              params = [basename, phase])]

    # For the current phase, for the redoers listed, done must be reset to 0.
    def forceReconciliationRedo(self, basename, redoers):
        self._executeWithParamDict("UPDATE reconciliation_assignment_info SET done = 0 WHERE reviewer IN ($(redoers)) AND basename = $(basename) AND reconciliation_phase IN (SELECT reconciliation_phase FROM reconciliation_phase_info where basename = $(basename))", {"redoers": redoers, "basename": basename}, retrieval = False)

    #
    # Sixth section: general basename maintenance
    #

    def discardBasenames(self, basenames):
        if basenames:
            self._executeWithParamDict("DELETE FROM document_info WHERE basename IN ($(basenames))", {"basenames": basenames}, retrieval = False)
            self._executeWithParamDict("DELETE FROM reconciliation_phase_info WHERE basename IN ($(basenames))", {"basenames": basenames}, retrieval = False)
            self._executeWithParamDict("DELETE FROM reconciliation_assignment_info WHERE basename IN ($(basenames))", {"basenames": basenames}, retrieval = False)
            self._executeWithParamDict("DELETE FROM basename_sets WHERE basename IN ($(basenames))", {"basenames": basenames}, retrieval = False)
                                                                                        

    #
    # Seventh section: transactions
    #

    def beginTransaction(self):
        # We're using savepoints instead. See
        # http://bugs.python.org/issue8145.
        # AND BYPASS MY _EXECUTE CODE - it uses commit.
        # self.conn.execute("SAVEPOINT %s" % self.savepoint)
        self.autocommit = False
        # print "Savepoint", self.savepoint
        self.conn.execute("BEGIN TRANSACTION")

    def commitTransaction(self):
        # self.conn.execute("RELEASE SAVEPOINT %s" % self.savepoint)
        # print "Releasing savepoint", self.savepoint
        self.autocommit = True
        self.conn.commit()
    
    def rollbackTransaction(self):
        # print "Rolling back to savepoint", self.savepoint
        # self.conn.execute("ROLLBACK TO SAVEPOINT %s" % self.savepoint)
        self.autocommit = True
        self.conn.rollback()

    #
    # Eighth section: workspace state
    #

    def initializeWorkspaceState(self, task, reconciliationPhases, loggingEnabled, prioritizationClass, maxOldModels):
        prioritizationClass = (prioritizationClass and ("%s.%s" % (prioritizationClass.__module__, prioritizationClass.__name__))) or None
        loggingEnabled = (loggingEnabled and 1) or 0
        reconciliationPhases = (reconciliationPhases and ",".join(reconciliationPhases)) or None
        self._execute("DELETE FROM workspace_state", retrieval = False)
        self._execute("INSERT INTO workspace_state VALUES (?, ?, ?, ?, ?)",
                      params = [task, reconciliationPhases, loggingEnabled, prioritizationClass, maxOldModels],
                      retrieval = False)

    def enableLogging(self):
        self._execute("UPDATE workspace_state SET logging_enabled = 1", retrieval = False)
        
    def disableLogging(self):
        self._execute("UPDATE workspace_state SET logging_enabled = 0", retrieval = False)

    def loggingEnabled(self):
        return self._execute("SELECT logging_enabled FROM workspace_state LIMIT 1")[0][0] == 1

    def setMaxOldModels(self, modelCount):
        self._execute("UPDATE workspace_state SET max_old_models = ?", params = [modelCount], retrieval = False)

    def getMaxOldModels(self):
        return self._execute("SELECT max_old_models FROM workspace_state LIMIT 1")[0][0]

    def getTaskName(self):
        return self._execute("SELECT task FROM workspace_state LIMIT 1")[0][0]

    def setPrioritizationClass(self, prioritizationClass):
        prioritizationClass = (prioritizationClass and ("%s.%s" % (prioritizationClass.__module__, prioritizationClass.__name__))) or None
        self._execute("UPDATE workspace_state SET prioritization_class = ?", params = [prioritizationClass], retrieval = False)

    def getPrioritizationClass(self):
        return self._execute("SELECT prioritization_class FROM workspace_state LIMIT 1")[0][0]

    def setReconciliationPhases(self, reconciliationPhases):
        reconciliationPhases = (reconciliationPhases and ",".join(reconciliationPhases)) or None
        self._execute("UPDATE workspace_state SET reconciliation_phases = ?", params = [reconciliationPhases], retrieval = False)

    def getReconciliationPhases(self):
        p = self._execute("SELECT reconciliation_phases FROM workspace_state LIMIT 1")[0][0]
        return (p and p.split(",")) or []

    # Ninth section: basename sets.

    def getBasenameSetNames(self):
        return self._execute("SELECT DISTINCT basename_set FROM basename_sets")

    def getBasenameSetMap(self):
        bMap = {}
        bPrev = None
        for basename, setName in self._execute("SELECT basename, basename_set FROM basename_sets ORDER BY basename_set"):
            if setName != bPrev:
                bMap[setName] = set([basename])
                bPrev = setName
            else:                
                bMap[setName].add(basename)
        return bMap
            
    def addBasenameToBasenameSet(self, basename, setName):
        if self._execute("SELECT COUNT(*) FROM basename_sets where basename = ? and basename_set = ?",
                         params = [basename, setName])[0][0] == 0:
            self._execute("INSERT INTO basename_sets VALUES (?, ?)",
                          params = [basename, setName], retrieval = False)

    def removeBasenameFromBasenameSet(self, basename, setName):
        self._execute("DELETE FROM basename_sets WHERE basename = ? and basename_set = ?",
                      params = [basename, setName],
                      retrieval = False)
