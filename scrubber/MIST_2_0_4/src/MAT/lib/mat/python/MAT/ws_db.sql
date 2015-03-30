/* SQL schema for workspace db. */

CREATE TABLE document_info (
  doc_name TEXT PRIMARY KEY NOT NULL, /* name of the file */
  basename TEXT NOT NULL, /* visible basename */
  assigned_user TEXT, /* user assigned to document (may be null) */
  locked_by TEXT, /* user who's locked the document (may be null) */  
  status TEXT NOT NULL, /* one of "reconciled", "gold", "partially gold",
                           "partially corrected", "uncorrected", "unannotated" */
  lock_id TEXT /* if locked, a lock ID for close/save */
);

/* Note that locking in reconciliation locks basenames,
   while locking in core locks documents. So they can't be managed
   together. */

CREATE TABLE reconciliation_phase_info (
  basename TEXT PRIMARY KEY NOT NULL, /* the visible basename - primary key here */
  reconciliation_phase TEXT NOT NULL, /* what phase is the basename in? */
  locked_by TEXT, /* user who's currently reviewing the basename (may be null) */
  lock_id TEXT /* if locked, a lock ID for close/save */
);

CREATE TABLE reconciliation_assignment_info (
  basename TEXT NOT NULL, /* visible basename, not a primary key here */
  reconciliation_phase TEXT NOT NULL, /* the phase */
  reviewer TEXT NOT NULL, /* the user who needs to review this document in the phase */
  done INTEGER DEFAULT 0 /* whether the user has reviewed it or not */
);

/* I want to leave open the possibility of having users with no roles. */

CREATE TABLE users (
  user TEXT PRIMARY KEY NOT NULL
);

CREATE TABLE user_roles (
  user TEXT NOT NULL /* user name, not a primary key */,
  role TEXT NOT NULL /* a role for the user: core annotation, or a reconciliation phase */  
);

/* There will be exactly one row in this table. */

CREATE TABLE workspace_state (
  task TEXT NOT NULL /* the name of the task */,
  reconciliation_phases TEXT NULL /* */,
  logging_enabled INTEGER DEFAULT 0 /* 1 if enabled, 0 otherwise */,
  prioritization_class TEXT NULL /* the name of a prioritization class */,
  max_old_models INTEGER DEFAULT 0 /* the number of old models to keep */
);

/* Basename sets. This is many-to-many. */

CREATE TABLE basename_sets (
  basename TEXT NOT NULL /* a basename */,
  basename_set TEXT NOT NULL /* a basename set */
);
