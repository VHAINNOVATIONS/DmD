# Copyright (C) 2007 - 2009 The MITRE Corporation. See the toplevel
# file LICENSE for license terms.

# SAM 8/11/08: modified the scorer to provide a much more detailed
# breakdown of matches: correct, wrong tag, wrong span, wrong span and
# tag (all judged identical by overlap), missing (in ref, not hyp),
# spurious (in hyp, not ref). For the purposes of precision/recall/fmeasure,
# each of the pairs in the three "wrong" buckets counts as
# one missing, one spurious.

import os, sys, weakref

# SAM 3/2/09: Adding an option for writing out spreadsheet formulas
# to CSV files. Borrowing code I wrote a long time ago for another
# purpose. Turning the data into spreadsheet cells.

# SAM 6/12/12: moved the pairer into its own file.

# Guts translated from Ben's scoretags.pl, and then munged beyond recognition.

# A scorer for lists of target/ref pairs. Each pair is a tuple
# (fname, aset).

# What information do we want to collect? We want to know the summary
# (prec/rec/fmeasure) for each tag, and also possibly the details.

# So the data structure we want to collect is for each tag.

import MAT.DocumentIO, MAT.Document

_jsonIO = MAT.DocumentIO.getDocumentIO('mat-json')

class ScoreResultTableError(Exception):
    pass

# The idea is that we have a sequence of columns and
# ways of calculating the columns. There are the literal
# values; the "fake" values, which are keyword arguments
# that are passed but then ignored; and then the computed
# values, which are based on preceding "fake" values and
# all the other values accumulated so far. We can insert
# new columns after existing ones, one at a time.

class ScoreColumn:

    def __init__(self, colName, formatFn = str, colKey = None):

        self.colName = colName
        self.colKey = colKey or self.colName
        self.formatFn = formatFn

    def addCell(self, row, computedKW, kw):
        raise ScoreResultTableError, "unimplemented"

class LiteralScoreColumn(ScoreColumn):

    def addCell(self, row, computedKW, kw):
        try:
            v = kw[self.colKey]
        except KeyError:
            raise ScoreResultTableError, ("missing value for row key %s" % self.colKey)
        cell = ScoreTableCell(row, v)
        computedKW[self.colKey] = cell
        
class FakeScoreColumn(ScoreColumn):

    def addCell(self, row, computedKW, kw):
        try:
            v = kw[self.colKey]
        except KeyError:
            raise ScoreResultTableError, ("missing value for row key %s" % self.colKey)
        cell = ScoreTableCell(None, v)
        computedKW[self.colKey] = cell

class AggregatorScoreColumn(ScoreColumn):

    def __init__(self, colName, rowDispatch = None, **kw):
        ScoreColumn.__init__(self, colName, **kw)
        self.rowDispatch = rowDispatch

    def copy(self):
        return AggregatorScoreColumn(self.colName, colKey = self.colKey,
                                     rowDispatch = self.rowDispatch,
                                     formatFn = self.formatFn)

    def addCell(self, row, computedKW, kw):
        # The idea is that we should get the accumulator.
        accum = computedKW["accum"].data
        # At this point I should know whether I'm producing formulas or not. But it
        # doesn't matter.
        v = accum.getForCell(self.colKey)
        cell = AggregatorScoreTableCell(accum, self.colKey, row, v)
        computedKW[self.colKey] = cell

class ComputedScoreColumn(ScoreColumn):

    def __init__(self, colName, computeFn = None, inputs = None, **kw):
        ScoreColumn.__init__(self, colName, **kw)
        self.computeFn = computeFn
        self.inputs = inputs
        self.dependsOnFake = None
        if computeFn is None:
            raise ScoreResultTableError, "no compute function for computed column"
        if inputs is None:
            raise ScoreResultTableError, "inputs not specified for compute function"

    def addCell(self, row, computedKW, kw):
        # This should return a formula, if it wants to.
        v = self.computeFn(row.scoreTable, *[computedKW[input] for input in self.inputs])
        cell = ScoreTableCell(row, v)
        computedKW[self.colKey] = cell

# This class is used exclusively for importing rows. It's the column
# type when we have a column in the imported set which shadows what's in the
# importing set.

class _CopyCacheScoreColumn(ScoreColumn):

    def __init__(self, shadowColumn):
        # Let's get rid of the shadow column and see if that fixes
        # one of the memory problems I'm having. Nope.
        self.shadowColumnColKey = shadowColumn.colKey
        self.shadowColumnIsFake = isinstance(shadowColumn, FakeScoreColumn)
        # self.shadowColumn = shadowColumn
        ScoreColumn.__init__(self, shadowColumn.colName,
                             formatFn = shadowColumn.formatFn,
                             colKey = shadowColumn.colKey)

    def addCell(self, row, computedKW, kw):
        if self.shadowColumnIsFake:
            # It was shadowed, but nothing was passed in.
            computedKW[self.colKey] = ScoreTableCell(None)
        else:
            computedKW[self.colKey] = kw[self.shadowColumnColKey].copy(row)

class ScoreTableRow:
    def __init__(self, scoreTable):
        self.cells = []
        self.scoreTable = weakref.proxy(scoreTable)

class Formula:
    def __init__(self, *cellRefs):
        self.cellRefs = cellRefs
    # Change on inheritance.
    def render(self, scoreTable, separator = None):
        return ""
    def compute(self):
        return 0
    def convertToLiteralForRowFiltering(self):
        return self

class Sum(Formula):
    def render(self, scoreTable, separator = None):
        sum_sep = separator
        cells = [scoreTable.accumCellDict[c] for c in self.cellRefs]
        cell_refs = [c.reference() for c in cells]
        # Now that I've called reference() on these cells, they all
        # have a loc, and I can sort them by row and column, and then
        # see if there are any groups. If they're not all one row, or
        # not all one column, I'm just going to not worry about grouping.
        if len(set([c.loc[0] for c in cells])) == 1:
            cell_refs = self._collapseConsecutiveRefs(cells, 1)
        elif len(set([c.loc[1] for c in cells])) == 1:
            # All columns.
            cell_refs = self._collapseConsecutiveRefs(cells, 0)
        # You're gonna love this. It turns out that SUM
        # has an argument limit! It's 30. Just to be safe,
        # I'll bunch them by 20s.
        cell_ref_batches = []
        if len(cell_refs) <= 20:
            cell_ref_batches = cell_refs
        else:
            while cell_refs:
                cell_ref_batches.append("SUM(" + sum_sep.join(cell_refs[:20])
                                        + ")")
                cell_refs = cell_refs[20:]
        if cell_ref_batches:
            return "=SUM(" + sum_sep.join(cell_ref_batches) + ")"
        else:
            return "0"
    
    def _collapseConsecutiveRefs(self, cells, i):
        # All rows. Try to sort by the other dimension
        # and see if there are consecutives.
        cellCopy = cells[:]
        cellCopy.sort(key = lambda c: c.loc[i])
        cell_refs = []
        curStart = None
        curEnd = None
        for c in cellCopy:
            if curStart is None:
                curStart = curEnd = c
            elif c.loc[i] == curEnd.loc[i] + 1:
                curEnd = c
            else:
                # End.
                if curEnd is curStart:
                    # Hasn't budged.                    
                    cell_refs.append(curStart.reference())
                else:
                    cell_refs.append(curStart.reference()+":"+curEnd.reference())
                curStart = curEnd = c
        if curStart:
            if curEnd is curStart:
                # Hasn't budged.                    
                cell_refs.append(curStart.reference())
            else:
                cell_refs.append(curStart.reference()+":"+curEnd.reference())
        return cell_refs

    # This will be a staticmethod.
    def compute(self):
        return sum([v for v in [accum.get(slot) for accum, slot in self.cellRefs] if v is not None])

# This is for the situation where we want the sum literally computed
# rather than getting a formula.

class ComputedSum(Sum):

    def render(self, scoreTable, separator = None):
        return self.compute()

class ColumnSum(Sum):

    def __init__(self, colPair):
        accum, col = colPair
        Sum.__init__(self, *[(acc, col) for acc in accum.childRows])

    def convertToLiteralForRowFiltering(self):
        return self.compute()

# What if there's no first child?

class FirstChild(Formula):

    def __init__(self, colPair):
        self.colPair = colPair

    def compute(self):
        accum, col = self.colPair
        if accum.childRows:
            return accum.childRows[0].get(col)
        else:
            return None

    def render(self, scoreTable, separator = None):
        accum, col = self.colPair
        if accum.childRows:
            v = accum.childRows[0].getForCell(col)
            if isinstance(v, Formula):
                return v.render(scoreTable, separator = separator)
            else:
                return v
        else:
            return None

    def convertToLiteralForRowFiltering(self):
        return self.compute()

class Precision(Formula):

    def __init__(self, hCount, match):
        self.hCount = hCount
        self.match = match
        Formula.__init__(self, hCount, match)

    def render(self, scoreTable, separator = None):        
        sep = separator
        return "=IF(%(hCount)s = 0%(sep)s1.00%(sep)sIF(%(match)s = 0%(sep)s0.0%(sep)s%(match)s / %(hCount)s))" % {"hCount": scoreTable.accumCellDict[self.hCount].reference(), "match": scoreTable.accumCellDict[self.match].reference(), "sep": sep}

    def compute(self):
        hAccum, hSlot = self.hCount
        mAccum, mSlot = self.match
        hCount = hAccum.get(hSlot)
        match = mAccum.get(mSlot)
        if not hCount:
            return 1.0
        elif not match:
            return 0.0
        else:
            return float(match)/float(hCount)

class Recall(Formula):

    def __init__(self, rCount, match):
        self.rCount = rCount
        self.match = match
        Formula.__init__(self, rCount, match)

    def render(self, scoreTable, separator = None):
        sep = separator
        return "=IF(%(rCount)s = 0%(sep)s1.0%(sep)sIF(%(match)s = 0%(sep)s0.0%(sep)s%(match)s / %(rCount)s))" % {"rCount": scoreTable.accumCellDict[self.rCount].reference(), "match": scoreTable.accumCellDict[self.match].reference(), "sep": sep}
    
    def compute(self):
        rAccum, rSlot = self.rCount
        mAccum, mSlot = self.match
        rCount = rAccum.get(rSlot)
        match = mAccum.get(mSlot)
        if not rCount:
            return 1.0
        elif not match:
            return 0.0
        else:
            return float(match)/float(rCount)

class Fmeasure(Formula):

    def __init__(self, p, r):
        self.p = p
        self.r = r
        Formula.__init__(self, p, r)

    def render(self, scoreTable, separator = None):        
        sep = separator
        return "=IF((%(p)s + %(r)s) = 0%(sep)s0.0%(sep)s2.0 * ((%(p)s * %(r)s) / (%(p)s + %(r)s)))" % {"p": scoreTable.accumCellDict[self.p].reference(), "r": scoreTable.accumCellDict[self.r].reference(), "sep": sep}

    def compute(self):
        pAccum, pSlot = self.p
        rAccum, rSlot = self.r
        p = pAccum.get(pSlot)
        r = rAccum.get(rSlot)
        
        if (p + r == 0):
            return 0.0
        else:
            return 2.0 * (p * r) / (p + r)
    
class Accuracy(Formula):

    def __init__(self, testToks, *errorCells):
        self.testToks = testToks
        self.errorCells = errorCells
        Formula.__init__(self, testToks, *errorCells)

    def render(self, scoreTable, separator = None):
        return "=(%(testToks)s - %(errors)s)/%(testToks)s" % \
               {"testToks": scoreTable.accumCellDict[self.testToks].reference(),
                "errors": " - ".join([scoreTable.accumCellDict[cell].reference() for cell in self.errorCells])}

    def compute(self):
        ttAccum, ttSlot = self.testToks
        testToks = ttAccum.get(ttSlot)
        errorVals = [accum.get(slot) for accum, slot in self.errorCells]
        numerator = testToks
        # In some rare cases, when there are no annotations at all
        # in the region, testToks will be zero. This is a bug that
        # should be fixed. The score is right, but that's not all
        # I want.
        if testToks == 0:
            return 1.00
        for v in errorVals:
            numerator -= v
        return float(numerator)/float(testToks)

class ErrorRate(Formula):

    def __init__(self, accuracy):
        self.accuracy = accuracy
        Formula.__init__(self, accuracy)

    def render(self, scoreTable, separator = None):
        return "=(1 - %s)" % scoreTable.accumCellDict[self.accuracy].reference()

    def compute(self):
        aAccum, aSlot = self.accuracy
        return 1 - aAccum.get(aSlot)

class Mean(Formula):

    def __init__(self, slot):
        self.mean = slot

    def render(self, scoreTable, separator = None):
        return self.compute()

    def compute(self):
        meanAccum, meanSlot = self.mean
        return meanAccum.corpusAggregate.computeMeanAndVariance(meanAccum._cache, meanSlot, "mean")

    def convertToLiteralForRowFiltering(self):
        return self.compute()

class Variance(Formula):

    def __init__(self, slot):
        self.variance = slot

    def render(self, scoreTable, separator = None):
        return self.compute()

    def compute(self):
        varAccum, varSlot = self.variance
        return varAccum.corpusAggregate.computeMeanAndVariance(varAccum._cache, varSlot, "variance")

    def convertToLiteralForRowFiltering(self):
        return self.compute()

class StdDeviation(Formula):

    def __init__(self, slot):
        self.variance = slot

    def render(self, scoreTable, separator = None):
        return self.compute()

    def compute(self):
        varAccum, varSlot = self.variance
        return varAccum.corpusAggregate.computeMeanAndVariance(varAccum._cache, varSlot, "stddev")

    def convertToLiteralForRowFiltering(self):
        return self.compute()

class ScoreTableCell:
    def __init__(self, row, data = ""):
        self.data = data
        self.setScoreTableRow(row)
        self.loc = None
        
    def setScoreTableRow(self, row):
        self.row = (row and weakref.proxy(row)) or None
        if self.row:
            self.row.cells.append(self)

    def render(self, separator = None):
        return self.data

    def compute(self):
        return self.data
        
    def reference(self):
        if self.loc is None:
            # Compute row and column. Very slow.
            column = self.row.cells.index(self)
            row = self.row.scoreTable.getRowIndex(self.row)
            self.loc = row, column
        else:
            row, column = self.loc
        return self._colnum_to_colname(column)+("%d" % (row + 1,))

    def _colnum_to_colname(self, num):
        # It's basically base 26. But not really.
        # Essentially, you can use all the digits in
        # each position, while in normal base notation
        # the low digit can't be used in the high
        # position. This means that you have to do
        # a round of capture, then divide and DECREMENT,
        # So by the time you've filled n decimal places,
        # you have more than n^base cases.
        A_index = ord("A")
        chars = []
        while 1:
            chars[0:0] = [chr((num % 26) + A_index)]
            if num < 26:
                break
            num = (num / 26) - 1
        return "".join(chars)
    
    def copy(self, row):
        # Only pass a row if we already had one.
        if self.row is None:
            row = None
        return self.__class__(row, self.data)

class AggregatorScoreTableCell(ScoreTableCell):

    def __init__(self, accum, colKey, row, data):
        ScoreTableCell.__init__(self, row, data)
        self.accum = accum
        self.colKey = colKey
        # No harm in recording it, even if the value isn't a formula.
        row.scoreTable.accumCellDict[(self.accum, self.colKey)] = self
            
    def render(self, separator = None):
        if isinstance(self.data, Formula):
            return self.data.render(self.row.scoreTable, separator = separator)
        else:
            return ScoreTableCell.render(self, separator = separator)
        
    def compute(self):
        if isinstance(self.data, Formula):
            return self.data.compute()
        else:
            return ScoreTableCell.compute(self)

    # Copy yourself. Put yourself in the cache if appropriate.
    # Originally, the idea was that copying a formula was enough
    # to copy the cell. But in the new refactor, formulas don't
    # know anything about the spreadsheet; only formula.render()
    # knows about the spreadsheet. So formula.copy() needs to be
    # the other thing that knows about the spreadsheet. But that's
    # also wrong, because the formulas are the only thing that
    # care about the cache. So we're no longer copying the
    # formulas, because we don't have to.

    def copy(self, row):
        # Only pass a row if we already had one.
        if self.row is None:
            row = None
        return self.__class__(self.accum, self.colKey, row, self.data)
    
OO_SEPARATOR = ";"
EXCEL_SEPARATOR = ","

class ScoreFormat:

    def __init__(self, csvFormulaOutput = None):
        if csvFormulaOutput is None:
            self.formulaOutputs = ['excel']
        else:
            if type(csvFormulaOutput) in (str, unicode):
                csvFormulaOutput = [x.strip() for x in csvFormulaOutput.split(",")]
            if type(csvFormulaOutput) not in (tuple, list, set):
                raise ScoreResultTableError, "wrong type for CSV formula output"
            self.formulaOutputs = []
            for e in csvFormulaOutput:
                if e not in ('excel', 'literal', 'oo'):
                    raise ScoreResultTableError, ("unknown CSV formula output type '%s'" % e)
                self.formulaOutputs.append(e)

    def getSeparator(self, format):
        if format == "excel":
            return EXCEL_SEPARATOR
        elif format == "oo":
            return OO_SEPARATOR
        else:
            return None

class WriteableTable:

    def writeCSV(self, path, colNames, rows):

        import csv
        # CSV rows.

        # The contents of the documents being scored are all Unicode strings,
        # so if those strings happen to be in there (and they might be),
        # we need to be able to deal with that. Note the documentation
        # on the CSV module; it doesn't actually do Unicode. So what you need
        # to do is encode them as UTF-8.

        def utf8writer(w, row):
            w.writerow([((type(a) is unicode) and a.encode('utf-8')) or a for a in row])
        fp = open(path, "wb")
        w = csv.writer(fp)
        utf8writer(w, colNames)
        for row in rows:
            utf8writer(w, row)
        fp.close()

    def format(self, colNames, fmtRows):

        # Be careful; if fmtRows is empty, then max(n, *[]) will fail.
        if len(fmtRows) == 0:
            fmtString = " ".join("%" + str(len(colNames[i])) + "s" for i in range(len(colNames)))
        else:
            fmtString = " ".join(["%" + str(max(len(colNames[i]), *[len(row[i]) for row in fmtRows])) + "s" for i in range(len(colNames))])

        sList = [fmtString % tuple(colNames),
                 fmtString % (tuple(["-----"]) * len(colNames))]

        for row in fmtRows:
            sList.append(fmtString % tuple(row))
        
        return "\n".join(sList)

class ScoreResultTable(WriteableTable):

    def __init__(self, columns = None, firstDataRow = 1, format = None):
        if format is None:
            format = ScoreFormat()
        if columns:
            self.columns = columns[:]
        else:
            self.columns = []
        self._computeVisibleColumns()
        self.rows = []
        # What to add to the index into self.rows. This should
        # account for whatever rows you'll be writing before
        # you write the actual data, e.g., the headers.
        self.firstDataRow = firstDataRow
        # The formula separator is , for Excel, but ; for OO.        
        self.csvFormat = format
        self.initializationKW = {"columns": self.columns,
                                 "firstDataRow": self.firstDataRow,
                                 "format": self.csvFormat}
        # This is a placeholder for a corpus aggregate, in case
        # we need to hold it until we're done with the score table.
        self.corpusAggregate = None
    
    def copy(self):
        newCopy = self._newInstance()
        newCopy.importRows(self)
        return newCopy

    def _newInstance(self):
        return self.__class__(**self.initializationKW)

    def _computeVisibleColumns(self):        
        self.visibleColumns = [c for c in self.columns if not isinstance(c, FakeScoreColumn)]

    def addColumn(self, colObj, after = None):

        if after is None:
            self.columns[0:0] = [colObj]
        else:
            foundColumn = False
            for i in range(len(self.columns)):
                if self.columns[i].colName == after:
                    self.columns[i+1:i+1] = [colObj]
                    foundColumn = True
                    break
            if not foundColumn:
                raise ScoreResultTableError, ("couldn't find column named '%s' to insert after" % after)
        self._computeVisibleColumns()

    def addRow(self, **kw):

        self._addRow(self.columns, **kw)

    def _addRow(self, columns, **kw):

        # The way we add a row is as follows. We loop through the
        # columns. If the column is a literal or fake, it has to be
        # in kw. If it's literal, collect the value, and record
        # it both in a row list and in the dictionary to pass
        # to the computed values. If it's fake, record it only
        # in the dictionary. If it's computed, compute it based
        # on the dictionary (so it should have a kw value for
        # each literal and computed value in the preceding headers).
        row = ScoreTableRow(self)
        computedKW = {}
        for col in columns:
            col.addCell(row, computedKW, kw)
        # Add this LAST, so anything that's looking at the existing
        # rows won't hit it yet.
        self.rows.append(row)

    def _fixLocations(self):
        i = self.firstDataRow
        for r in self.rows:
            j = 0
            for c in r.cells:
                c.loc = i, j
                j = j + 1
            i = i + 1

    def getRowIndex(self, row):
        return self.firstDataRow + self.rows.index(row)

    def getColumnIndex(self, colKey):
        i = 0
        for c in self.visibleColumns:
            if c.colKey == colKey:
                return i
            i += 1
        return None
        
    def importRows(self, otherScorer, **kw):

        # So I've gone through a number of iterations here.
        # I've settled on this: each cell knows how to copy itself.
        # It doesn't matter what the columns say, or what the previous
        # computations are. A literal cell will copy itself; a
        # cell with a formula will copy the formula, using the
        # cells which have already been created.

        otherColDict = {}
        for c in otherScorer.columns:
            otherColDict[c.colKey] = c
        tempCols = []
        for c in self.columns:
            if otherColDict.has_key(c.colKey):
                otherC = otherColDict[c.colKey]
                # Create a cache column.
                tempCols.append(_CopyCacheScoreColumn(otherC))
            else:
                tempCols.append(c)        

        # Now this is going to be a bit more complicated, because
        # we want to do the same computation as before. Just collect the cells,
        # because any column we're going to use from the old score sheet
        # will have a cache column.

        # We have to do something clever about the fake columns, because
        # we're not going to need them, but we don't want to try to compute
        # them.
        
        for row in otherScorer.rows:
            d = kw.copy()
            d.update(zip([c.colKey for c in otherScorer.visibleColumns], row.cells))
            self._addRow(tempCols, **d)

    def writeCSVByFormat(self, dir, basename):
        
        for e in self.csvFormat.formulaOutputs:
            self.writeCSV(os.path.join(dir, basename + "_" + e + ".csv"), format = e)


    def writeCSV(self, path, format = None):

        separator = None
        if format is not None:
            separator = self.csvFormat.getSeparator(format)

        self._fixLocations()        
        
        import csv
        WriteableTable.writeCSV(self, path, [c.colName for c in self.visibleColumns],
                                ((separator is None) and [[cell.compute() for cell in row.cells] for row in self.rows]) or \
                                [[cell.render(separator = separator) for cell in row.cells] for row in self.rows])

    def format(self):

        return WriteableTable.format(self, [c.colName for c in self.visibleColumns],
                                     [[p[0].formatFn(p[1]) for p in zip(self.visibleColumns, [cell.compute() for cell in row.cells])]
                                      for row in self.rows])

# The confusability table will be on either the token or pseudo-token
# level. Null will be one of the options. If any token ends up
# mapping to more than one thing, the confusability table will be aborted
# (see below).

class ConfusabilityTable(WriteableTable):

    def __init__(self):
        self.matrix = {}
        self.columns = None
        self.rows = None

    def addPair(self, refLab, hypLab, incr = 1):
        try:
            self.matrix[hypLab][refLab] += incr
        except KeyError:
            try:
                self.matrix[hypLab][refLab] = incr
            except KeyError:
                self.matrix[hypLab] = {refLab: incr}            

    def declareAllTags(self, allTags):
        allTags = list(allTags)
        allTags.sort()
        self.allTags = allTags + [None]

    def _makeTable(self):
        orderedTags = self.allTags
        if (self.columns is None) or (self.rows is None):
            self.columns = [""] + [((t is None) and "null (ref)") or (t + " (ref)") for t in orderedTags]
            self.rows = []
            for t in orderedTags:
                self.rows.append([((t is None) and "null (hyp)") or (t + " (hyp)")] + [(self.matrix.has_key(t) and self.matrix[t].get(otherT, 0)) or 0 for otherT in orderedTags])
    
    def writeCSV(self, path):
        self._makeTable()
        WriteableTable.writeCSV(self, path, self.columns, self.rows)

    def format(self):
        self._makeTable()
        return WriteableTable.format(self, self.columns, [[str(x) for x in row] for row in self.rows])

#
# Here are the core row elements, which we'll put together and ask for
# individual values.
#

class BaseScoreRow:

    def __init__(self, rowCache, computationColumns = None):
        self.file = rowCache.get("file")
        self.tag = rowCache.get("tag")
        self._cache = rowCache
        self.formulaDict = {}
        if computationColumns is not None:
            self._addComputationColumns(computationColumns)

    def _addComputationColumns(self, computationColumns):
        for c in computationColumns:
            if c.rowDispatch is not None:
                for entry in c.rowDispatch:
                    if isinstance(self, entry[0]):
                        formulaCls = entry[1]
                        vals = entry[2:]
                        self.formulaDict[c.colKey] = formulaCls, vals
                        break

    def get(self, slot):
        try:
            return self._cache[slot]
        except KeyError:
            # See if you can compute it. Let it raise a
            # KeyError if it fails.
            f = self._getFormula(slot)
            if f is None:
                v = None
            else:
                v = f.compute()
            self._cache[slot] = v
            return v

    def _getFormula(self, slot):
        formulaCls, vals = self.formulaDict[slot]
        if formulaCls is None:
            return None
        else:
            return formulaCls(*[(self, v) for v in vals])       

    def getForCell(self, slot):
        try:
            return self._getFormula(slot) or ""
        except KeyError:
            return self.get(slot)

class ScoreRow(BaseScoreRow):

    def __init__(self, rowCache, tokenCount,
                 rDoc, tDoc, computationColumns = None, scoreTable = None, initSlot = None, incrVal = 1,
                 extraAccumulators = None):
        if scoreTable is not None:
            computationColumns = scoreTable.aggregates
        BaseScoreRow.__init__(self, rowCache, computationColumns)
        self.accumulators = dict([(label, 0) for label in \
                                  ["spurious", "missing", "match", "refclash", "hypclash"]])
        if extraAccumulators:
            self.accumulators.update(dict([(label, 0) for label in extraAccumulators]))
        self._cache["test_toks"] = tokenCount
        # self._cache["refdoc"] = rDoc
        # self._cache["hypdoc"] = tDoc
        self.refDoc = rDoc
        self.hypDoc = tDoc
        if initSlot is not None:
            self.accumulators[initSlot] = incrVal

    def incr(self, slot, incrVal = 1):
        # You can only increment the accumulatable slots.
        self.accumulators[slot] += incrVal

    def get(self, slot):
        try:
            return self.accumulators[slot]
        except KeyError:
            return BaseScoreRow.get(self, slot)

class AggregateScoreRow(BaseScoreRow):

    def __init__(self, childRows, *args, **kw):
        BaseScoreRow.__init__(self, *args, **kw)
        self.childRows = childRows

class FileAggregateScoreRow(AggregateScoreRow):
    
    def __init__(self, hypDoc, refDoc, childRows, file, aggregation, rowCacheSeed, **kw):
        rowCache = rowCacheSeed.copy()
        rowCache["file"] = file
        rowCache["tag"] = aggregation # usually "<all>"
        AggregateScoreRow.__init__(self, childRows, rowCache, **kw)
        self.hypDoc = hypDoc
        self.refDoc = refDoc

class TagAggregateScoreRow(AggregateScoreRow):

    def __init__(self, corpusAggregate, totalTokFormula, childRows, tag, rowCacheSeed, **kw):
        rowCache = rowCacheSeed.copy()
        rowCache["file"] = "<all>"
        rowCache["tag"] = tag
        AggregateScoreRow.__init__(self, childRows, rowCache, **kw)
        self.totalTokFormula = totalTokFormula
        self.corpusAggregate = weakref.proxy(corpusAggregate)

    def _getFormula(self, slot):
        if slot == "test_toks":
            return self.totalTokFormula
        else:
            return AggregateScoreRow._getFormula(self, slot)

class Bootstrapper:

    def __init__(self, corpusAggregate, numSamples):
        
        self.seedAggregate = weakref.proxy(corpusAggregate)
        self.mvDict = {}
        self.samples = self._generateSamples(numSamples)
        
    # We're going to sample with replacement, so we can get a better
    # feel for what the mean and variance are. We compute the metrics
    # on the new buckets the same way we'd compute the normal ones
    # (except I'm trying to be really, really efficient here and I
    # don't need to worry about rendering or cells).
    
    def _generateSamples(self, numSamples):
        print "Producing samples for confidence intervals ...",
        i = 0
        rowPairs = self.seedAggregate.fileRowPairs
        comps = self.seedAggregate.computationColumns
        rowCacheSeed = self.seedAggregate.rowCacheSeed
        fileRange = range(len(rowPairs))
        resDicts = []
        while i < numSamples:
            i += 1
            if i % 100 == 0:
                print i, "...",
                sys.stdout.flush()
            newFileRowPairs = [random.choice(rowPairs) for k in fileRange]
            # Now, from this, build a new corpus aggregate.
            newAggregate = CorpusAggregate(rowCacheSeed,
                                           newFileRowPairs, comps)
            resDicts.append(newAggregate)
        print
        return resDicts

    # The dataCache contains the static information for each row:
    # tag, file, similarity profile, decomposition, aggregation, etc.
    
    def getValue(self, dataCache, metric, meanOrVariance):
        tag = dataCache["tag"]
        decomp = dataCache["tag subset"]
        import math
        try:
            sMean, sVar = self.mvDict[(metric, tag, decomp)]
        except KeyError:
            # So now, for each requested tag and header, we collect the score
            # vectors and cache the results. Some of the results may be None,
            # if there happen to be no elements of that type in that
            # sample.
            allVals = []
            for a in self.samples:
                try:
                    allVals.append(a.corpusDict[tag][decomp].get(metric))
                except KeyError:
                    pass
            # Is it possible for there to be nothing in allVals for the tag
            # and subset? I think so. Ben says skip the sample, rather than setting
            # it to 0. But what about if it's missing from ALL the samples?
            # I THINK I should make it None, None. I don't think that
            # hurts anything downstream.
            # It turns out that it's incredibly hard to tickle this bug.
            # If the decomp, for instance, happens to have no values, it
            # won't be listed. That may also be true for the labels themselves.
            # I'm just not going to worry about this bug any further.
            if allVals:
                sMean = float(sum(allVals)) / len(allVals)
                sDiffsSquared = [math.pow(v - sMean, 2) for v in allVals]
                sVar = float(sum(sDiffsSquared)) / len(sDiffsSquared)
            else:
                sMean = None
                sVar = None
            self.mvDict[(metric, tag, decomp)] = (sMean, sVar)
        if meanOrVariance == "mean":
            return sMean
        elif meanOrVariance == "variance":
            return sVar
        elif meanOrVariance == "stddev":
            if sVar is not None:
                return math.sqrt(sVar)
            else:
                return None

# Each of the fileRows is a FileAggregateScoreRow, which has childRows
# which are the rows for each file for each tag/tag aggregate and decomposition.
# Here below, we prepare (a) a sum of
# the tokens, which is composed on the file aggregates, and (b) a row
# for each tag/aggregate and decomposition for <all> files.

# The particular problem I'm trying to fix at the moment is if there
# are no annotations in the reference. In that case, the FileAggregate will
# have no children, which means, since it uses FirstChild as its
# way of getting the tokens, it will have no token count. So what I need is
# to make sure that the FileAggregate gets a token count for the file
# in the case where there are no individual rows. But that can't get
# fixed here. This has to happen in _newAggregate.

class CorpusAggregate:

    def __init__(self, rowCacheSeed, fileRowPairs, computationColumns):
        # fileRowPairs is a list of pairs of file names and constructed rows
        # for that file. See _newAggregate. Note that this CANNOT be a
        # dictionary, because when we do the bootstrapping, there will be
        # duplicates in it.
        self.rowCacheSeed = rowCacheSeed
        self.fileRowPairs = fileRowPairs
        self.computationColumns = computationColumns
        # So what we need to do is collect a dictionary of (tag, decomp) -> list of
        # underlying ScoreRows. We also need to collect the file rows which correspond
        # to ("<all>", "<none>") and pass them to create the totalToks.
        # NOTE: This is ALSO called in the bootstrapping, which means that
        # we can't sort by file ANYWHERE in this init function, because there
        # may be duplicate files. It doesn't look like I do that anywhere, but
        # keep it in mind.

        # We want to ensure that the <all> entries are computed,
        # whether or not there are any contributing elements. This means 
        # we can't rely on the tag/decomp pairs in the countDict, exclusively.
        # I need to deal with this at the <all> level.

        totalTokFileRows = []
        tagDecompDict = {}
        for bName, fileRows in self.fileRowPairs:
            for r in fileRows:
                key = (r.tag, r.get("tag subset"))
                try:
                    tagDecompDict[key].append(r)
                except KeyError:
                    tagDecompDict[key] = [r]
                if key == ("<all>", "<none>"):
                    totalTokFileRows.append(r)
                for child in r.childRows:
                    key = (child.tag, child.get("tag subset"))
                    try:
                        tagDecompDict[key].append(child)
                    except KeyError:
                        tagDecompDict[key] = [child]
        # and then collect the 
        # totalToks MUST be a ColumnSum, or otherwise no one will
        # know to convert it to a literal when you extract a global summary.
        # I use a dummy AggregateScoreRow to seed it. The rows it requires are
        # file, tag = "<all>", decomp = "<none>"
        totalToks = ColumnSum((AggregateScoreRow(totalTokFileRows, {}), "test_toks"))
        # This should have the same structure as the dicts in updateAccumDict, so I can
        # do the same things with them when I get to _updateFromAccumulations.
        
        self.corpusDict = {}
        for (tag, decomp), rList in tagDecompDict.items():
            rowCacheSeed["tag subset"] = decomp
            r = TagAggregateScoreRow(self, totalToks, rList, tag,
                                     rowCacheSeed,
                                     computationColumns = computationColumns)
            try:
                self.corpusDict[tag][decomp] = r
            except KeyError:
                self.corpusDict[tag] = {decomp: r}
        # Make sure <all> <all> is here.
        if not self.corpusDict.has_key("<all>"):
            rowCacheSeed["tag subset"] = "<none>"
            self.corpusDict["<all>"] = {"<none>": TagAggregateScoreRow(self, totalToks, [], "<all>", rowCacheSeed,
                                                                       computationColumns = computationColumns)}
        self._mvData = None

    # The dataCache is the cache created for each score row. It contains
    # all the information required to compute the appropriate value.
    
    def computeMeanAndVariance(self, dataCache, metric, meanOrVariance):
        # So the idea here is that we need to collect all the columns that we want to
        # participate in this rigamarole, and do n random choices of k% of the set,
        # and then compute the scores. This has to be cached, so that we only
        # do the computation the first time we encounter it. We're going to do
        # computations for a number of metrics: precision, recall, fmeasure,
        # and all the tokenSummary headers (if they're present). 
        if self._mvData is None:
            self._mvData = Bootstrapper(self, 1000)
        return self._mvData.getValue(dataCache, metric, meanOrVariance)

    # Here's where we take all these lovely rows we created and
    # turn them into an actual spreadsheet. We really should group the rows,
    # as follows:
    # For each file, group the labels by stratum. For each label, always
    # do the <none> decomposition FIRST. Then do the other decomps, bundled.
    # Then, for each file, do the label aggregations, and again, do the
    # <none> decomposition first; and do <all> last.
    # Then repeat the process for <all>.
    
    def _updateFromAccumulations(self, countDict, resultSheet, numDocs, orderedStrata, labsToDecomps):
        
        fileRowDict = {}

        for bName, fileRows in self.fileRowPairs:
            # Make sure that there's always an entry in fileRowDict
            # for bName, even if there are no rows.
            try:
                labDict = fileRowDict[bName]
            except KeyError:
                labDict = {}
                fileRowDict[bName] = labDict            
            for r in fileRows:
                try:
                    decompDict = labDict[r.tag]
                except KeyError:
                    decompDict = {}
                    labDict[r.tag] = decompDict
                decompDict[r.get("tag subset")] = r
        
        corpusDict = self.corpusDict
        # I need to add the corpus aggregate to the result sheet,
        # so that I can make all the backpointers in the aggregate into
        # weakrefs. This is because the corpus aggregate is referenced
        # in the result sheet.
        resultSheet.corpusAggregate = self

        keys = countDict.keys()
        keys.sort()

        cacheKeys = ["similarity profile", "test_toks", "score profile",
                     "score dimension", "tag subset"]
        
        def addRowsToResultSheet(docCount, lab, decomps):
            thisLabDecomp = None
            if decomps:
                thisLabDecomp = labsToDecomps.get(lab)
                r = decomps["<none>"]
                # here we do bName, lab, "<none>"
                resultSheet.addRow(file = r.file, tag = r.tag, test_docs = docCount, accum = r,
                                   **dict([(k, r.get(k)) for k in cacheKeys]))
                if thisLabDecomp:
                    # Attrs first, then partitions.
                    for decompSet in [thisLabDecomp["attrs"], thisLabDecomp["partitions"]]:
                        for attrDecomp in decompSet:
                            for decomp in attrDecomp:
                                r = decomps.get(decomp)
                                if r:                                    
                                    # here we do bname, lab, decomp
                                    resultSheet.addRow(file = r.file, tag = r.tag, test_docs = docCount, accum = r,
                                                       **dict([(k, r.get(k)) for k in cacheKeys]))
        
        for bName in keys:
            # d is a mapping from labels to decomps to row.
            d = countDict[bName]
            for spanned, spanless in orderedStrata:
                for lab in spanned:
                    decomps = d.get(lab)
                    addRowsToResultSheet(1, lab, decomps)
                for lab in spanless:
                    decomps = d.get(lab)
                    addRowsToResultSheet(1, lab, decomps)
            # At this point, we've done all the elements entered for bName in
            # updateAccumDict. Now, let's do the aggregates for the file.
            # Do <all> LAST.
            labDict = fileRowDict[bName]
            for aggr, decompDict in labDict.items():
                if aggr != "<all>":
                    addRowsToResultSheet(1, aggr, decompDict)
            if labDict.has_key("<all>"):
                # This should almost always happen; the only case where
                # it shouldn't is if there are no annotations at all in the doc.
                addRowsToResultSheet(1, "<all>", labDict["<all>"])

        # Now, the file rows don't contain the "<all>" file entries; those are
        # in the corpusDict. Note, too, that ALL the keys are in the corpusDict;
        # they're not divided by aggregation. So I have to order the <all>
        # entries with the strata (see above).

        labsDone = set()
        for spanned, spanless in orderedStrata:
            labsDone.update(spanned)
            labsDone.update(spanless)
            for lab in spanned:
                decomps = corpusDict.get(lab)
                if decomps:
                    addRowsToResultSheet(numDocs, lab, decomps)
            for lab in spanless:
                decomps = corpusDict.get(lab)
                if decomps:
                    addRowsToResultSheet(numDocs, lab, decomps)

        for aggr, decompDict in corpusDict.items():
            if (aggr != "<all>") and (aggr not in labsDone):
                addRowsToResultSheet(numDocs, aggr, decompDict)
        if corpusDict.has_key("<all>"):
            # This should almost always happen; the only case where
            # it shouldn't is if there are no annotations at all in the doc.
            addRowsToResultSheet(numDocs, "<all>", corpusDict["<all>"])

        return self


# We'll use these headers instead of the normal ones when we're summing up,
# so that we generate the appropriate sums without having to refer to
# fake columns.

# So there are a couple ways to do this. In particular, the error analysis
# differs if you're going to have common basic units (e.g., token, pseudo-token, char)
# vs. not (tag). In the latter case, you have the option of all sorts of span-related
# errors, which I've enumerated. For the tag case, you have the option of
# including the enumerated errors, or just getting an aggregate.

SUMMARY_HEADERS = [
    LiteralScoreColumn('similarity profile'),
    LiteralScoreColumn('score profile'),
    # We'll add this eventually, probably. The code supports
    # passing it around, but otherwise, not caring.
    # LiteralScoreColumn('score dimension'),
    LiteralScoreColumn('file'),
    # Number of eligible docs. For individual files, it's 1.
    # For <all> aggregation, it's the number of total files.
    LiteralScoreColumn('test docs', colKey = 'test_docs'),
    LiteralScoreColumn('tag'),
    # If there's a decomposition, it'll be called "tag subset"
    # and it'll be here.
    FakeScoreColumn('accum'),
    # Hm. What do you do when there's no first child? The problem is that
    # occasionally you get a reference document which has no annotations in it,
    # so there will be no child rows. I've fixed this in _newAggregate.
    AggregatorScoreColumn("test toks", colKey = 'test_toks',
                          rowDispatch = [(FileAggregateScoreRow, FirstChild, "test_toks")]),
    AggregatorScoreColumn("match",
                          rowDispatch = [(AggregateScoreRow, ColumnSum, "match")]),
    AggregatorScoreColumn("refclash",                          
                          rowDispatch = [(AggregateScoreRow, ColumnSum, "refclash")]),
    AggregatorScoreColumn("missing",
                          rowDispatch = [(AggregateScoreRow, ColumnSum, "missing")]),
    AggregatorScoreColumn("refonly",
                          rowDispatch = [(BaseScoreRow, Sum, "refclash", "missing")]),
    AggregatorScoreColumn("reftotal",
                          rowDispatch = [(BaseScoreRow, Sum, "refonly", "match")]),
    AggregatorScoreColumn("hypclash",
                          rowDispatch = [(AggregateScoreRow, ColumnSum, "hypclash")]),
    AggregatorScoreColumn("spurious",
                          rowDispatch = [(AggregateScoreRow, ColumnSum, "spurious")]),
    AggregatorScoreColumn('hyponly',
                          rowDispatch = [(BaseScoreRow, Sum, "hypclash", "spurious")]),
    AggregatorScoreColumn('hyptotal',
                          rowDispatch = [(BaseScoreRow, Sum, "hyponly", "match")]),
    AggregatorScoreColumn("precision",
                          rowDispatch = [(BaseScoreRow, Precision, "hyptotal", "match")],
                          formatFn = lambda x: "%.3f" % x),
    AggregatorScoreColumn("recall",
                          rowDispatch = [(BaseScoreRow, Recall, "reftotal", "match")],
                          formatFn = lambda x: "%.3f" % x),
    AggregatorScoreColumn("fmeasure",
                          rowDispatch = [(BaseScoreRow, Fmeasure, "precision", "recall")],
                          formatFn = lambda x: "%.3f" % x)
    ]    
    
TOKEN_SUMMARY_HEADERS = [
    AggregatorScoreColumn("tag_sensitive_accuracy",
                          rowDispatch  = [(BaseScoreRow, Accuracy, "test_toks", "missing", "spurious", "refclash")],
                          formatFn = lambda x: "%.3f" % x),
    AggregatorScoreColumn("tag_sensitive_error_rate",
                          rowDispatch = [(BaseScoreRow, ErrorRate, "tag_sensitive_accuracy")],
                          formatFn = lambda x: "%.3f" % x),
    AggregatorScoreColumn("tag_blind_accuracy",
                          rowDispatch = [(BaseScoreRow, Accuracy, "test_toks", "missing", "spurious")],
                          formatFn = lambda x: "%.3f" % x),
    AggregatorScoreColumn("tag_blind_error_rate",
                          rowDispatch = [(BaseScoreRow, ErrorRate, "tag_blind_accuracy")],
                          formatFn = lambda x: "%.3f" % x)
    ]

def spanValue(cell, start = True):
    if cell.data and cell.data[1].atype.hasSpan:
        if start:
            return cell.data[1].start
        else:
            return cell.data[1].end
    else:
        return ""

def spanContent(cell, doc):
    if cell.data and cell.data[1].atype.hasSpan:
        return doc.data.signal[cell.data[1].start:cell.data[1].end]
    else:
        return ""

DETAIL_HEADERS = [LiteralScoreColumn("file"),
                  LiteralScoreColumn("type"),
                  FakeScoreColumn("ref"),
                  FakeScoreColumn("hyp"),
                  ComputedScoreColumn("refid", 
                                      inputs = ["ref"],
                                      computeFn = lambda scorer, ref: (ref.data and ref.data[1].id) or ""),
                  ComputedScoreColumn("hypid", 
                                      inputs = ["hyp"],
                                      computeFn = lambda scorer, hyp: (hyp.data and hyp.data[1].id) or ""),
                  ComputedScoreColumn("refdescription",
                                      inputs = ["ref"],
                                      computeFn = lambda scorer, ref: (ref.data and ref.data[1].describe()) or ""),
                  ComputedScoreColumn("hypdescription",
                                      inputs = ["hyp"],
                                      computeFn = lambda scorer, hyp: (hyp.data and hyp.data[1].describe()) or ""),
                  ComputedScoreColumn("reflabel", 
                                      inputs = ["ref"],
                                      computeFn = lambda scorer, ref: (ref.data and ref.data[0]) or ""),
                  ComputedScoreColumn("hyplabel", 
                                      inputs = ["hyp"],
                                      computeFn = lambda scorer, hyp: (hyp.data and hyp.data[0]) or ""),
                  ComputedScoreColumn("refstart", 
                                      inputs = ["ref"],
                                      computeFn = lambda scorer, ref: spanValue(ref)),
                  ComputedScoreColumn("refend", 
                                      inputs = ["ref"],
                                      computeFn = lambda scorer, ref: spanValue(ref, start = False)),
                  ComputedScoreColumn("hypstart", 
                                      inputs = ["hyp"],
                                      computeFn = lambda scorer, hyp: spanValue(hyp)),
                  ComputedScoreColumn("hypend", 
                                      inputs = ["hyp"],
                                      computeFn = lambda scorer, hyp: spanValue(hyp, start = False)),
                  FakeScoreColumn("doc"),
                  ComputedScoreColumn("refcontent", 
                                      inputs = ["ref", "doc"],
                                      computeFn = lambda scorer, ref, doc: spanContent(ref, doc),
                                      formatFn = lambda x: '"' + x + '"'),
                  ComputedScoreColumn("hypcontent", 
                                      inputs = ["hyp", "doc"],
                                      computeFn = lambda scorer, hyp, doc: spanContent(hyp, doc),
                                      formatFn = lambda x: '"' + x + '"')]

import random

class SummaryScoreResultTable(ScoreResultTable):

    def __init__(self, forTokens = False, computeConfidenceData = False, tokenColumn = None, showTagOutputMismatchDetails = False, **kw):
        headers = SUMMARY_HEADERS[:]
        if tokenColumn is not None:
            i = 0
            for h in headers:
                if h.colKey == "test_toks":
                    break
                i += 1
            hCopy = headers[i].copy()
            hCopy.colName = tokenColumn
            headers[i] = hCopy                    
        if forTokens:
            headers += TOKEN_SUMMARY_HEADERS
        ScoreResultTable.__init__(self, headers, **kw)
        self.aggregates = [c for c in self.columns if isinstance(c, AggregatorScoreColumn)]                
        if computeConfidenceData:
            for h in ["recall", "precision", "fmeasure"]:
                self._addMVData(h)
            if forTokens:
                for h in ["tag_sensitive_accuracy", 
                          "tag_sensitive_error_rate", 
                          "tag_blind_accuracy", 
                          "tag_blind_error_rate"]:
                    self._addMVData(h)
        # This is how it'll be reconstructed.
        del self.initializationKW["columns"]
        self.initializationKW["forTokens"] = forTokens
        self.initializationKW["computeConfidenceData"] = computeConfidenceData
        self.initializationKW["tokenColumn"] = tokenColumn
        self.initializationKW["showTagOutputMismatchDetails"] = showTagOutputMismatchDetails
        self.forTokens = forTokens
        self.showTagOutputMismatchDetails = showTagOutputMismatchDetails
        # For use with AggregatorScoreColumns
        self.accumCellDict = {}
        self.columnsToAddForCopy = []

    # This one should be used internally, when you manage the copying
    # of the columns in _newInstance yourself.
    def _addColumn(self, c, after = None):
        ScoreResultTable.addColumn(self, c, after = after)
        if isinstance(c, AggregatorScoreColumn):
            self.aggregates.append(c)

    def addColumn(self, c, after = None):
        self._addColumn(c, after = after)
        # Augment this.        
        self.columnsToAddForCopy.append((c, after))

    def _newInstance(self):
        newCopy = ScoreResultTable._newInstance(self)
        for c, after in self.columnsToAddForCopy:
            newCopy.addColumn(c, after = after)
        return newCopy

    def _addMVData(self, header):
        c = AggregatorScoreColumn(header+"_mean",
                                  rowDispatch = [(TagAggregateScoreRow, Mean, header),
                                                 (BaseScoreRow, None)])
        self._addColumn(c, after = header)
        c = AggregatorScoreColumn(header+'_variance',
                                  rowDispatch = [(TagAggregateScoreRow, Variance, header),
                                                 (BaseScoreRow, None)])
        self._addColumn(c, after = header+"_mean")
        c = AggregatorScoreColumn(header+'_stddev',
                                  rowDispatch = [(TagAggregateScoreRow, StdDeviation, header),
                                                 (BaseScoreRow, None)])
        self._addColumn(c, after = header+"_variance")

    # The summary will no longer have the other columns, so anything that's
    # a ColumnSum or a FirstChild needs to be converted to a literal.
    # Ditto with mean and variance, I think.
    
    def extractGlobalSummary(self):
        # This removes the file column, and filters all rows which
        # don't have <all> in the file column. First, of course.
        newCopy = self.copy()
        i = newCopy.getColumnIndex("file")
        newCopy.rows = [r for r in newCopy.rows if r.cells[i].compute() == "<all>"]
        col = newCopy.visibleColumns[i]
        newCopy.visibleColumns.remove(col)
        try:
            newCopy.columns.remove(col)
        except ValueError:
            pass
        for r in newCopy.rows:
            r.cells[i:i+1] = []
            for cell in r.cells:
                if isinstance(cell.data, Formula):
                    cell.data = cell.data.convertToLiteralForRowFiltering()
        return newCopy

    # Generating the aggregate.

    # I want to order these rows eventually, but the fact is, these things that
    # claim to be score rows aren't score rows: they're just accumulation and
    # aggregation containers. The true row adding and ordering happens in _updateFromAccumulations.

    # So here, we're first creating the per-file aggregates. What we want to do is
    # find the aggregations in the score profile, if it exists, and then
    # collect up all the keys in value per file - these keys will be pairs of
    # label and decomposition. Group these by decomposition, and then create a
    # file aggregate for each.

    def _newAggregate(self, countDict, translatedAggrs, rowCacheSeed, basenameInfoDict):

        # I used to pass in just a list of the file rows, but that won't work
        # because what I have is lots of aggregates and decompositions for a given file.
        # So it's gotta be a list of pairs of file names and corresponding rows.
        # It CANNOT be a dictionary, because when we do the bootstrapping, there
        # will be duplicates.

        fileRowPairs = []
        # d is a mapping from labels to decompositions to ScoreRows.        
        for bName, d in countDict.items():
            fileRows = []
            # For each aggregation, we need one FileAggregateScoreRow per
            # all available decompositions.
            decompPairs = [("<all>", d.values())] + \
                          [(k, [d.get(lab, {}) for lab in v]) for (k, v) in translatedAggrs.items()]

            for aggrName, decompDicts in decompPairs:
                # A mapping from decomp names to all relevant rows.
                decompMap = {}
                for decompDict in decompDicts:
                    for k, v in decompDict.items():
                        try:
                            decompMap[k].add(v)
                        except KeyError:
                            decompMap[k] = set([v])
                for decomp, rowSet in decompMap.items():
                    # The seed is copied immediately, so this is just a way of passing
                    # in the subset.
                    rowCacheSeed["tag subset"] = decomp
                    newAggr = FileAggregateScoreRow(basenameInfoDict[bName]["hypdoc"],
                                                    basenameInfoDict[bName]["refdoc"],
                                                    list(rowSet), bName, aggrName, rowCacheSeed,
                                                    computationColumns = self.aggregates)
                    fileRows.append(newAggr)

                    # In the case where there are no rows for a given file, you need to get the token
                    # counts anyway.

                    if len(d.values()) == 0:
                        newAggr._cache["test_toks"] = basenameInfoDict[bName]["tok_count"]

            fileRowPairs.append((bName, fileRows))

        # I'm going to create a corpus aggregate which stores and computes the
        # remainder of the values. This aggregate will also be able to compute means
        # and variances. Because of the bootstrapper, it needs to be able to essentially
        # create the tag aggregates from the file row contents.

        return CorpusAggregate(rowCacheSeed, fileRowPairs, self.aggregates)

class DetailScoreResultTable(ScoreResultTable):

    def __init__(self, **kw):
        ScoreResultTable.__init__(self, DETAIL_HEADERS, **kw)

    def updateFromTagProfiles(self, profileList):
        attrsAdded = set(["_label", "_span"])
        def cbFactory(dimName):
            return lambda scorer, cell: (cell.data and cell.data[1].getByName(dimName)) or ""
        for tp in profileList:
            for dim in tp["dimensions"]:
                dimName = dim["name"]
                if dimName not in attrsAdded:
                    attrsAdded.add(dimName)
                    # Add a reference version and a hypothesis version. I'm
                    # not going to add different ones for different annotation types
                    # if the names are the same.
                    col = ComputedScoreColumn("ref " + dimName,
                                              inputs = ["ref"],
                                              computeFn = cbFactory(dimName))
                    self.addColumn(col, after = "hypend")
                    col = ComputedScoreColumn("hyp " + dimName,
                                              inputs = ["hyp"],
                                              computeFn = cbFactory(dimName))
                    self.addColumn(col, after = "ref " + dimName)
            

import MAT.Pair

from MAT.Pair import checkContentTag, checkLexTag

class Score:

    def __init__(self, tagSeedList = None, tagResultTable = None,
                 tokenResultTable = None, detailResultTable = None,
                 # These aren't enabled by default.
                 pseudoTokenResultTable = False, characterResultTable = False,
                 computeConfidenceData = False, computeConfusability = False,
                 showTagOutputMismatchDetails = False, similarityProfile = None,
                 scoreProfile = None,
                 format = None, task = None, contentAnnotations = None,
                 tokenAnnotations = None, equivalenceClasses = None,
                 labelsToIgnore = None, restrictRefToGoldSegments = False,
                 restrictHypToGoldSegments = False):
        if format is None:
            # Default.
            format = ScoreFormat()
        self.tagCounts = self.tokenCounts = self.pseudoTokenCounts = self.characterCounts = self.tagDetails = None
        if tagResultTable is not False:
            # Only the tag table needs the details.
            self.tagCounts = tagResultTable or SummaryScoreResultTable(format = format, computeConfidenceData = computeConfidenceData,
                                                                       showTagOutputMismatchDetails = showTagOutputMismatchDetails)
        if tokenResultTable is not False:
            self.tokenCounts = tokenResultTable or SummaryScoreResultTable(forTokens = True, format = format,
                                                                           computeConfidenceData = computeConfidenceData)
        if pseudoTokenResultTable is not False:
            self.pseudoTokenCounts = pseudoTokenResultTable or SummaryScoreResultTable(forTokens = True, format = format,
                                                                                       computeConfidenceData = computeConfidenceData,
                                                                                       tokenColumn = "test pseudo-toks")
        if characterResultTable is not False:
            self.characterCounts = characterResultTable or SummaryScoreResultTable(forTokens = True, format = format,
                                                                                   computeConfidenceData = computeConfidenceData,
                                                                                   tokenColumn = "test chars")
        self.foundSomeTokens = False
        # This table contains a mapping from tags to triples
        # of [occurs in both, occurs in hypothesis, occurs in reference]
        # Each entry in these sublists is a triple of
        # (hyp filename, hyp doc, annotation).
        if detailResultTable is not False:
            self.tagDetails = detailResultTable or DetailScoreResultTable(format = format)
        # If there are tags we absolutely, definitely want to
        # be handled, but they may not be in the test set, pass
        # them in here. If you're passing in a task, the seed list had better
        # be in terms of the effective elements of the task.
        self.tagSeedList = tagSeedList
        self.task = task
        self.pairer = MAT.Pair.PairState(task, contentAnnotations, tokenAnnotations,
                                         equivalenceClasses, labelsToIgnore,
                                         similarityProfile = similarityProfile)
        if self.tagDetails and self.pairer.simEngine.profile and self.pairer.simEngine.profile.get("tag_profiles"):
            self.tagDetails.updateFromTagProfiles(self.pairer.simEngine.profile["tag_profiles"])
        self.confusabilityTable = None
        if computeConfusability:
            self.confusabilityTable = ConfusabilityTable()
        def useableSeg(seg):
            return seg.get("status") in ("human gold", "reconciled")
        self.refSegRestriction = self.hypSegRestriction = None
        if restrictRefToGoldSegments:
            self.refSegRestriction = useableSeg
        if restrictHypToGoldSegments:
            self.hypSegRestriction = useableSeg
        # The score profile.
        self.scoreProfile = None
        if self.task:
            sp = self.task.getScoreProfile(name = scoreProfile)
            if sp:
                self._compileScoreProfile(sp)

    def _compileScoreProfile(self, scoreProfile):
        # Here, we compile the score profile. This is like compiling the
        # similarity profile in the similarity engine. We have to ensure
        # that all labels are known, and that all attrs are known for
        # the attr decompositions, and the filter methods are known, and
        # that there's no more than one decomposition per label.
        globalATR = self.task.getAnnotationTypeRepository()
        aggrNames = set()
        for aggr in scoreProfile["aggregations"]:
            if aggr["name"] in aggrNames:
                raise ScoreResultTableError, ("duplicate aggregation name '%s' in score profile in task '%s'" (aggr["name"], self.task.name))
            aggrNames.add(aggr["name"])
            for label in aggr["true_labels"]:
                if not globalATR.has_key(label):
                    raise ScoreResultTableError, ("unknown label '%s' in aggregation for score profile in task '%s'" % (label, self.task.name))
        labelLimitation = None
        spLabelLimitation = scoreProfile.get("label_limitation")
        if spLabelLimitation:
            labelLimitation = set(spLabelLimitation)
        self.scoreProfile = {"aggregations": scoreProfile["aggregations"],
                             "name": scoreProfile.get("name"),
                             "label_limitation": labelLimitation}
        decompMap = {}
        # If there are ANY decompositions at all, add the tag subset column
        # to all the spreadsheets.
        foundDecomp = False
        for decomp in scoreProfile["attr_decompositions"]:
            foundDecomp = True
            for label in decomp["true_labels"]:
                atype = globalATR.get(label)
                if not atype:
                    raise ScoreResultTableError, ("unknown label '%s' in attr decomposition for score profile in task '%s'" % (label, self.task.name))
                for attr in decomp["attrs"]:
                    if not atype.attr_table.has_key(attr):
                        raise ScoreResultTableError, ("label '%s' is decomposed by unknown attr '%s' in attr decomposition for score profile in task '%s'" % (label, attr, self.task.name))
                try:
                    decompMap[label]["attrs"].append(decomp)
                except KeyError:
                    decompMap[label] = {"attrs": [decomp], "partitions": []}
        for pt in scoreProfile["partition_decompositions"]:
            foundDecomp = True
            for label in pt["true_labels"]:
                if not globalATR.has_key(label):
                    raise ScoreResultTableError, ("unknown label '%s' in partition decomposition for score profile in task '%s'" % (label, self.task.name))
                try:
                    meth = eval(pt["method"])
                except (NameError, AttributeError):
                    # OK, try it in the plugin.
                    import MAT.PluginMgr
                    try:
                        meth = MAT.PluginMgr.FindPluginObject(pt["method"], self.task.name)
                    except MAT.PluginMgr.PluginError:
                        raise ScoreResultTableError, ("unknown partition method '%s' for partition decomposition in score profile in task '%s'" % (pt["method"], self.task.name))
                newPartition = {"method": meth, "true_labels": pt["true_labels"]}
                try:
                    decompMap[label]["partitions"].append(newPartition)
                except KeyError:
                    decompMap[label] = {"attrs": [], "partitions": [newPartition]}
        self.scoreProfile["decompositions"] = decompMap
        if foundDecomp:
            if self.tagCounts:
                self.tagCounts.addColumn(LiteralScoreColumn('tag subset'), after = "tag")
            if self.tokenCounts:
                self.tokenCounts.addColumn(LiteralScoreColumn('tag subset'), after = "tag")
            if self.pseudoTokenCounts:
                self.pseudoTokenCounts.addColumn(LiteralScoreColumn('tag subset'), after = "tag")
            if self.characterCounts:
                self.characterCounts.addColumn(LiteralScoreColumn('tag subset'), after = "tag")
    
    def addFilenamePairs(self, pairList, refIO = None, hypIO = None):
        pairs = []
        if refIO is None:
            refIO = _jsonIO
        if hypIO is None:
            hypIO = _jsonIO
        for target, ref in pairList:
            # Load both docs.
            try:
                tDoc = hypIO.readFromSource(target, taskSeed = self.task)
            except IOError:
                print "Couldn't open target %s; skipping pair." % target
                continue
            except MAT.DocumentIO.LoadError, e:
                print "Couldn't load reference %s (%s); skipping pair." % (ref, str(e))
                continue                
            except:
                print "Couldn't decode target %s; skipping pair." % target
                continue
            try:
                rDoc = refIO.readFromSource(ref, taskSeed = self.task)
            except IOError:
                print "Couldn't open reference %s; skipping pair." % ref
                continue
            except MAT.DocumentIO.LoadError, e:
                print "Couldn't load reference %s (%s); skipping pair." % (ref, str(e))
                continue
            except:
                print "Couldn't decode reference %s; skipping pair." % ref
                continue
            pairs.append(((target, tDoc), (ref, rDoc)))

        self.addDocumentPairlist(pairs)

    def addDocumentPairlist(self, pairList):

        # The hypothesis appears first in each of these pairs, but
        # the pairer treats the first element as the "pivot", so that
        # should be the reference.
        
        self.pairer.addDocumentTuples([(p[1], p[0]) for p in pairList],
                                      (self.refSegRestriction, self.hypSegRestriction))

        similarityProfile = self.pairer.simEngine.profileName or "<default>"
        scoreProfile = (self.scoreProfile and self.scoreProfile["name"]) or "<default>"
        # This should be optional.
        scoreDimension = "<default>"
        tokenTotal = 0
        numDocs = 0
        tagDict = {}
        tokenDict = {}
        pseudoTokenDict = {}
        charDict = {}
        contentTags = {}
        tagAggregates = None
        
        # I'd been collecting the token counts in the aggregate lines
        # by examining their first child, but sometimes there's no
        # first child. So I need to actually store them.

        # Actually, it looks like I need even more info here. So let's
        # gather some info per basename.
        
        basenameInfoDict = {}

        # Note that there may be extra accumulators
        # which are found as part of the tag scoring. We have to pass these in
        # when the row is created, and we have to ensure that the column
        # is created in the appropriate place.

        extraTagAccumulators = []

        def _ensureColumn(resultTable, tDict, colName, ref = False):
            if colName not in extraTagAccumulators:
                extraTagAccumulators.append(colName)
                # Create a new column. This column needs to be inserted
                # at the appropriate point in the columns for the table,
                # and it needs to be added to the computation columns
                # for each row, and the accumulator needs to be added
                # to each row.
                newCol = AggregatorScoreColumn(colName, 
                                               rowDispatch = [(AggregateScoreRow, ColumnSum, colName)])
                for d in tDict.values():
                    for decompD in d.values():
                        for row in decompD.values():
                            row.accumulators[colName] = 0
                            row._addComputationColumns([newCol])
                # And where do we put the new column in the resultTable?
                # It's going to be after refclash if ref is True, after
                # hypclash if ref is False. Don't bother trying to
                # put it at the end of the block; who cares.
                resultTable.addColumn(newCol, after = (ref and "refclash") or "hypclash")                

        # define the accumulator function. Note that this has to pay attention to
        # the decompositions in the score profile. Because there are so many
        # calls to updateAccumDict, I'm going to cache the decompositions for each
        # annotation.

        # a map from annotations (in either the ref or hyp) to extra
        # decompositions.
        decompositionCache = {}
        # And I need this for the aggregations.
        trueLabsToEffectiveLabs = {}
        allTags = set()
        # I need this for grouping the 
        # decompositions in the spreadsheet output. This is a mapping from
        # effective labels to dictionaries which have the same form
        # as the score profile (if there is one). In each position in
        # the lists for attrs and partitions, we have a set of discovered values.
        labsToDecomps = {}

        # I want to use the label_limitations to drop various labels
        # on the floor.
        
        def updateAccumDict(tDict, bName, lab, ann, mtype, numToks, resultTable, inc = 1, extraAccumulators = None):
            if self.scoreProfile and \
               self.scoreProfile["label_limitation"] and \
               ann.atype.lab not in self.scoreProfile["label_limitation"]:
                return
            allTags.add(lab)
            try:
                trueLabsToEffectiveLabs[ann.atype.lab].add(lab)
            except KeyError:
                trueLabsToEffectiveLabs[ann.atype.lab] = set([lab])
            try:
                decomps = decompositionCache[ann]
            except KeyError:
                decomps = []
                if self.scoreProfile:
                    # {"attrs": [], "partitions": [newPartition]}
                    decompEntries = self.scoreProfile["decompositions"].get(ann.atype.lab)                    
                    if decompEntries:
                        try:
                            recordedValues = labsToDecomps[lab]
                        except KeyError:
                            recordedValues = {"attrs": [set() for d in decompEntries["attrs"]],
                                              "partitions": [set() for d in decompEntries["partitions"]]}
                            labsToDecomps[lab] = recordedValues
                        i = 0
                        # Note that none of these new values can appear in any OTHER
                        # entry in the recorded values.
                        for attrDecomp in decompEntries["attrs"]:
                            vPairs = ",".join(["%s=%s" % (attr, ann.getByName(attr, "<null>")) for attr in attrDecomp["attrs"]])
                            decomps.append(vPairs)
                            curSet = recordedValues["attrs"][i]
                            if vPairs not in curSet:
                                for otherSet in recordedValues["attrs"] + recordedValues["partitions"]:
                                    if vPairs in otherSet:
                                        raise ScoreResultTableError, ("value '%s' for attribute decomposition for label '%s' in task '%s' also appears as a recorded value for another partition for that label" % (vPairs, lab, self.task.name))
                                curSet.add(vPairs)
                            i += 1
                        i = 0
                        for ptDecomp in decompEntries["partitions"]:
                            v = ptDecomp["method"](ann)
                            if v is not None:
                                v = ptDecomp["method"].__name__+"="+str(v)
                                decomps.append(v)
                                curSet = recordedValues["partitions"][i]
                                if v not in curSet:
                                    for otherSet in recordedValues["attrs"] + recordedValues["partitions"]:
                                        if v in otherSet:
                                            raise ScoreResultTableError, ("value '%s' for partition decomposition for label '%s' in task '%s' also appears as a recorded value for another partition for that label" % (v, lab, self.task.name))
                                    curSet.add(v)
                decompositionCache[ann] = decomps
            for decomp in ["<none>"] + decomps:
                try:
                    tDict[bName][lab][decomp].incr(mtype, incrVal = inc)                    
                except KeyError:
                    try:
                        dDir = tDict[bName][lab]
                    except KeyError:
                        dDir = {}
                        tDict[bName][lab] = dDir
                    dDir[decomp] = ScoreRow({"file": bName, "tag": lab,
                                             "similarity profile": similarityProfile,
                                             "score profile": scoreProfile,
                                             "score dimension": scoreDimension,
                                             "tag subset": decomp},
                                            numToks, rDoc, tDoc,
                                            scoreTable = resultTable, initSlot = mtype, incrVal = inc,
                                            extraAccumulators = extraAccumulators)

        def updateTagDetail(self, fName, ref, hyp, doc, cat):
            if self.tagDetails:
                # cat is the status of the pair. It may be a string, or it may be
                # a set of error tokens.
                if cat and (type(cat) not in (str, unicode)):
                    cat = ",".join(cat)
                self.tagDetails.addRow(file = fName, type = cat, ref = ref, hyp = hyp, doc = doc)

        for d in self.pairer.resultEntries:
            filterRegions = d["filterRegions"]
            t = d["tuple"]
            pairs = d["pairs"]
            pairsTokLevel = d["tokenPairs"]
            # Remember, the reference and hypothesis were swapped when we invoked
            # the pairer.
            (ref, rDoc), (target, tDoc) = t
            
            bName = os.path.basename(target)
            numDocs += 1
            # OK, everything's loaded and we know they're the same document.
            # Now, we track the occurrences. Split up the content tags, and
            # accumulate the token totals.
            toks = []
            hContent = []
            rContent = []
            tagDict[bName] = {}
            tokenDict[bName] = {}
            pseudoTokenDict[bName] = {}
            charDict[bName] = {}

            # I can't believe there would every be a spanless token tag, but
            # just in case someone is that crazy...
            for atype, annots in tDoc.atypeDict.items():
                if not atype.hasSpan:
                    continue
                if checkLexTag(self.pairer.contentTags, atype, self.task,
                               self.pairer.contentAnnotations, self.pairer.tokenAnnotations):
                    toks = toks + annots

            # Return is spanned lists, spanless lists.
            (toks,), ignore = self.pairer.filterByRegions(filterRegions, spannedLists = [toks])
            
            numToks = len(toks)
            numChars = len(rDoc.signal)
            
            # Counting pseudo tokens is a little tricky. Whitespace is a boundary,
            # but so is every annotation boundary which isn't at or in whitespace.
            # So the right way to count this is to collect all the indices, as we
            # do above, and count the tokens in each span. Just splitting the
            # signal at whitespace isn't good enough.

            # The problem isn't what happens in the span mismatches, but rather
            # what happens when they MATCH. The count of the basic tokens has to
            # equal the number of basic elements found. E.g., let's take a
            # document of the form "abcdefgh". It has one pseudotoken, if we
            # just split. But if there are 2 annotations, and both the hyp and
            # ref match (say, 0-4 and 4-8), then there are two pseudotokens which are
            # correct, but only one pseudotoken in the document.

            # I'm going to need the record of pseudo-tokens seen later anyway.

            # And to do the pseudo-tokens, we have to make sure the annotations
            # are spanned.

            pseudoTokenCountMap = {}
            rAnnots = [p[1] for p in pairs if p[1] is not None]
            hAnnots = [p[4] for p in pairs if p[4] is not None]
            indices = set([h.start for h in hAnnots if h.atype.hasSpan] + [h.end for h in hAnnots if h.atype.hasSpan] +
                          [r.start for r in rAnnots if r.atype.hasSpan] + [r.end for r in rAnnots if r.atype.hasSpan] +
                          [len(rDoc.signal)])
            indices = list(indices)
            indices.sort()
            prev = 0
            numPseudoTokens = 0
            for i in indices:
                numPseudoTokens += len(rDoc.signal[prev:i].split())
                pseudoTokenCountMap[i] = numPseudoTokens
                prev = i

            # For the purposes of the decompositions, we have to "untranslate" the
            # tags from effective labels to true labels.
            
            if self.tagSeedList:
                globalATR = None
                if self.task:
                    globalATR = self.task.getAnnotationTypeRepository()
                for tag in self.tagSeedList:
                    if globalATR:
                        # This may map to itself.
                        trueLab = globalATR.getTrueLabelForEffectiveLabel(tag)
                        try:
                            trueLabsToEffectiveLabs[trueLab].add(tag)
                        except KeyError:
                            trueLabsToEffectiveLabs[trueLab] = set([tag])
                    else:
                        trueLabsToEffectiveLabs[tag] = set([tag])
                    for d, tbl in [(tagDict, self.tagCounts), (tokenDict, self.tokenCounts),
                                   (pseudoTokenDict, self.pseudoTokenCounts),
                                   (charDict, self.characterCounts)]:
                        try:
                            dDict = d[bName][tag]
                        except KeyError:
                            dDict = {}
                            d[bName][tag] = dDict
                        dDict["<none>"] = ScoreRow({"file": bName, "tag": tag,
                                                    "tag subset": "<none>",
                                                    "similarity profile": similarityProfile,
                                                    "score profile": scoreProfile,
                                                    "score dimension": scoreDimension},
                                                   numToks, rDoc, tDoc, scoreTable = tbl)

            # What about overlaps and multiple spans on each side? The original
            # algorithm didn't take that into account. In fact, the way it's sorted
            # in multiple places clearly shows that all sorts of things would
            # break.

            # Tokens are going to be the same in both docs, so
            # I only need to analyze one of them. But I only need to
            # do this if the tokens are being collected. And if either
            # the reference or the hypothesis doesn't have tokens, we
            # shouldn't try, because it'll break and we don't
            # have tokens.

            basenameInfoDict[bName] = {"tok_count": len(toks), "refdoc": rDoc, "hypdoc": tDoc}
            tokenTotal += len(toks)

            # GAAAA. I have to make sure that whatever pairing I
            # apply for the tags applies to the tokens as well. So
            # the token algorithm has to change, completely. Ditto
            # for the pseudo-tokens and characters. EVERYTHING
            # starts with the annotation pairings. 

            # We'll collect triples of (ref, hyp, status),
            # where status is one of "match", 
            # "missing", "spurious", or a set of errors. We'll loop through the ref, since
            # we have no reason to pick one or the other. In some cases, we have to
            # do this from the point of view of one side or the other.
            # updateTagDetail() does it from the point of view of the hypothesis.

            # In order to do this by tag, I have to subdivide the
            # results by tag.

            # We're going to collect both character counts and pseudo-tokens (see below).

            # OK. Easy case first. Do the update for the toplevel pairs.
                        
            for [label, ann, refMatchStatus, hLabel, hAnn, hypMatchStatus] in pairs:
                hEntry = (hLabel, hAnn)
                if refMatchStatus == "missing":
                    updateTagDetail(self, bName, (label, ann), None, rDoc, "missing")
                    updateAccumDict(tagDict, bName, label, ann, "missing", numToks, self.tagCounts,
                                    extraAccumulators = extraTagAccumulators)
                elif hypMatchStatus == "spurious":
                    updateTagDetail(self, bName, None, hEntry, rDoc, "spurious")
                    updateAccumDict(tagDict, bName, hLabel, hAnn, "spurious", numToks, self.tagCounts,
                                    extraAccumulators = extraTagAccumulators)
                elif refMatchStatus == "match":
                    updateTagDetail(self, bName, (label, ann), hEntry, rDoc, "match")
                    updateAccumDict(tagDict, bName, label, ann, "match", numToks, self.tagCounts,
                                    extraAccumulators = extraTagAccumulators)                    
                else:
                    # Update the clashes.
                    updateTagDetail(self, bName, (label, ann), hEntry, rDoc, refMatchStatus)
                    updateAccumDict(tagDict, bName, hLabel, hAnn, "hypclash", numToks, self.tagCounts,
                                    extraAccumulators = extraTagAccumulators)
                    updateAccumDict(tagDict, bName, label, ann, "refclash", numToks, self.tagCounts,
                                    extraAccumulators = extraTagAccumulators)
                    # The counts for the individual details are only handled here.
                    # we need to collect the various error details and turn them
                    # into columns. They have to be added as accumulators to each existing score row, and
                    # also as columns to the table. This only happens with tag scoring. So look at
                    # self.tagCounts.showTagOutputMismatchDetails.
                    if self.tagCounts.showTagOutputMismatchDetails:
                        if type(hypMatchStatus) == set:
                            for status in hypMatchStatus:
                                colName = "hyp" + status + " (detail)"
                                _ensureColumn(self.tagCounts, tagDict, colName)
                                updateAccumDict(tagDict, bName, hLabel, hAnn, colName, numToks, self.tagCounts,
                                                extraAccumulators = extraTagAccumulators)
                        if type(refMatchStatus) == set:
                            for status in refMatchStatus:
                                colName = "ref" + status + " (detail)"
                                _ensureColumn(self.tagCounts, tagDict, colName, ref = True)
                                updateAccumDict(tagDict, bName, label, ann, colName, numToks, self.tagCounts)
            
            # And now the token updates.
            
            toksSeenMap = None
            confusabilityToksInDoc = numPseudoTokens
            
            if len(toks) and self.tokenCounts:

                toksSeenMap = {}
                
                toks.sort(cmp, lambda x: x.start)

                i = 0
                for t in toks:
                    toksSeenMap[t.start] = i
                    toksSeenMap[t.end] = i + 1
                    i += 1

                confusabilityToksInDoc = len(toks)

            confusabilityIndexesClaimed = set()
            
            for [rLab, rAnn, rMatchStatus, hLab, hAnn, hMatchStatus, start, end] in pairsTokLevel:

                ptokStart = pseudoTokenCountMap[start]
                ptokEnd = pseudoTokenCountMap[end]
                confusabilityStart = confusabilityEnd = None

                # There's some slop built into here - if the annotation accidently
                # covers some whitespace, but the far end of the whitespace is on
                # a token boundary, the token counts will still work correctly.
                if toksSeenMap is not None:
                    try:
                        tokStart = toksSeenMap[start]
                        tokEnd = toksSeenMap[end]
                        # Set up the confusability table.
                        confusabilityStart = tokStart
                        confusabilityEnd = tokEnd
                    except KeyError:
                        print "Found annotation boundary which doesn't fall on a token boundary; skipping token scoring."
                        if (self.confusabilityTable is not None) and (numDocs > 1):
                            # We've started this with tokens, but we can't finish it. Abort.
                            print "Aborting confusability as well, since we began it with token scoring."
                            self.confusabilityTable = None
                        toksSeenMap = None
                        self.tokenCounts = None
                else:
                    confusabilityStart = ptokStart
                    confusabilityEnd = ptokEnd

                # In either case, it's the number seen by that point. So
                # if the start is 0 and the end is 4, we saw 0 tokens or pseudo-tokens
                # at the start of the interval and 4 at the end, which means there are
                # 4 in the region. We want to record 0, 1, 2, 3 as the elements
                # paired (zero-based into the relevant list of tokens). All we need
                # is for it to be consistent, since we're just checking whether they've
                # been seen before.
                if self.confusabilityTable is not None:
                    i = confusabilityStart
                    while i < confusabilityEnd:
                        if i in confusabilityIndexesClaimed:
                            print "A token or pseudo-token participates in more than one pair; skipping confusability table."
                            self.confusabilityTable = None
                            break
                        confusabilityIndexesClaimed.add(i)                        
                        i += 1
                    if self.confusabilityTable is not None:
                        self.confusabilityTable.addPair(rLab, hLab, confusabilityEnd - confusabilityStart)
                        confusabilityToksInDoc -= (confusabilityEnd - confusabilityStart)

                # matchStatus will be missing, spurious, match, tagclash.

                if rMatchStatus == "missing":
                    updateAccumDict(pseudoTokenDict, bName, rLab, rAnn, "missing", numPseudoTokens,
                                    self.pseudoTokenCounts, inc = ptokEnd - ptokStart)
                    updateAccumDict(charDict, bName, rLab, rAnn, "missing", numChars,
                                    self.characterCounts, inc = end - start)
                    if toksSeenMap is not None:
                        updateAccumDict(tokenDict, bName, rLab, rAnn, "missing", numToks, self.tokenCounts, inc = tokEnd - tokStart)
                elif hMatchStatus == "spurious":
                    updateAccumDict(pseudoTokenDict, bName, hLab, hAnn, "spurious", numPseudoTokens,
                                    self.pseudoTokenCounts, inc = ptokEnd - ptokStart)
                    updateAccumDict(charDict, bName, hLab, hAnn, "spurious", numChars,
                                    self.characterCounts, inc = end - start)
                    if toksSeenMap is not None:
                        updateAccumDict(tokenDict, bName, hLab, hAnn, "spurious", numToks, self.tokenCounts, inc = tokEnd - tokStart)
                elif rMatchStatus == "match":
                    updateAccumDict(pseudoTokenDict, bName, rLab, rAnn, "match", numPseudoTokens,
                                    self.pseudoTokenCounts, inc = ptokEnd - ptokStart)
                    updateAccumDict(charDict, bName, rLab, rAnn, "match", numChars,
                                    self.characterCounts, inc = end - start)
                    if toksSeenMap is not None:            
                        updateAccumDict(tokenDict, bName, rLab, rAnn, "match", numToks, self.tokenCounts, inc = tokEnd - tokStart)
                else:
                    updateAccumDict(pseudoTokenDict, bName, rLab, rAnn, "refclash", numPseudoTokens,
                                    self.pseudoTokenCounts, inc = ptokEnd - ptokStart)
                    updateAccumDict(pseudoTokenDict, bName, hLab, hAnn, "hypclash", numPseudoTokens,
                                    self.pseudoTokenCounts, inc = ptokEnd - ptokStart)

                    updateAccumDict(charDict, bName, rLab, rAnn, "refclash", numChars,
                                    self.characterCounts, inc = end - start)
                    updateAccumDict(charDict, bName, hLab, hAnn, "hypclash", numChars,
                                    self.characterCounts, inc = end - start)
                    
                    if toksSeenMap is not None:
                        updateAccumDict(tokenDict, bName, rLab, rAnn, "refclash", numToks, self.tokenCounts, inc = tokEnd - tokStart)
                        updateAccumDict(tokenDict, bName, hLab, hAnn, "hypclash", numToks, self.tokenCounts, inc = tokEnd - tokStart)

            # At the end, one final goose to the confusability matrix, for those tokens that were not matched.
            if self.confusabilityTable is not None:
                self.confusabilityTable.addPair(None, None, confusabilityToksInDoc)
        
        # Now, I have a dictionary by file and tag. From this, I need to create the
        # spreadsheet.

        rowCacheSeed = {"similarity profile": similarityProfile,
                        "score profile": scoreProfile,
                        "score dimension": scoreDimension}

        # So what's the order of the decompositions for the aggregations?
        # We know what it is for the individual labels. It seems to me
        # that leaving aside the fact that labsToDecomps is by effective label,
        # you may get an aggregation value more than once. So I think the
        # only rational thing to do is have a single attr decomposition
        # and a single partition decomposition for each aggregation.
        
        # While we're translating the aggrs, we should also create entries in labsToDecomps
        # for all the aggregations, including <all>. We can ONLY do this after we
        # do all the calls to updateAccumDict, because the aggregate entries will
        # not be order-paired with anything, unlike the label version.
        # And remember, labsToDecomps is by EFFECTIVE LABEL. So I need to create
        # the union of all the sets in the parallel positions, to get the
        # decomps for the true labels, and then concatenate THOSE into the all entry.

        labsToDecompsAllEntry = {"attrs": [set()], "partitions": [set()]}
        if self.scoreProfile:
            for trueLab, effectiveLabs in trueLabsToEffectiveLabs.items():
                # {"attrs": [], "partitions": []}
                for lab in effectiveLabs:
                    decompEntry = labsToDecomps.get(lab)
                    if decompEntry:
                        for attrSet in decompEntry["attrs"]:
                            labsToDecompsAllEntry["attrs"][0] |= attrSet
                        for partitionSet in decompEntry["partitions"]:
                            labsToDecompsAllEntry["partitions"][0] |= partitionSet
            if labsToDecompsAllEntry["attrs"][0] & labsToDecompsAllEntry["partitions"][0]:
                raise ScoreResultTableError, ("for aggregation <all>, attribute decompositions and partition decompositions overlap for task '%s'" % self.task.name)
            labsToDecomps["<all>"] = labsToDecompsAllEntry
        
        translatedAggrs = {}
        if self.scoreProfile:
            for aggr in self.scoreProfile["aggregations"]:
                effectiveLabels = set()
                for trueLab in aggr["true_labels"]:
                    effectiveLabels.update(trueLabsToEffectiveLabs.get(trueLab, []))
                translatedAggrs[aggr["name"]] = effectiveLabels
                labsToDecompsEntry = {"attrs": [set()], "partitions": [set()]}
                for lab in effectiveLabels:
                    decompEntry = labsToDecomps.get(lab)
                    if decompEntry:
                        for attrSet in decompEntry["attrs"]:
                            labsToDecompsEntry["attrs"][0] |= attrSet
                        for partitionSet in decompEntry["partitions"]:
                            labsToDecompsEntry["partitions"][0] |= partitionSet
                if labsToDecompsAllEntry["attrs"][0] & labsToDecompsAllEntry["partitions"][0]:
                    raise ScoreResultTableError, ("for aggregation '%s', attribute decompositions and partition decompositions overlap for task '%s'" % (aggr["name"], self.task.name))
                labsToDecomps[aggr["name"]] = labsToDecompsEntry

        # Use this order for the strata when we create the spreadsheet.
        # We're converting the mapping to effective labels. But if there's
        # no task, we just use the tags that have been collected.

        # BUT if there's a task seed, I have to make sure that
        # those tags are included.
        
        orderedStrata = []

        foundSpanned = set()
        foundSpanless = set()
        
        if self.task and self.pairer.simEngine.strata:
            for trueSpanned, trueSpanless in self.pairer.simEngine.strata:
                spanned = []
                for p in trueSpanned:
                    spanned += trueLabsToEffectiveLabs.get(p, [])
                spanned.sort()
                foundSpanned.update(spanned)
                spanless = []
                for p in trueSpanless:
                    spanless += trueLabsToEffectiveLabs.get(p, [])
                spanless.sort()
                foundSpanless.update(spanless)
                orderedStrata.append((spanned, spanless))
        else:
            foundSpanned.update(allTags)
            orderedStrata = [(list(allTags), [])]
        
        if self.tagSeedList:            
            finalStratum = ([], [])
            globalATR = None
            if self.task:
                globalATR = self.task.getAnnotationTypeRepository()
            for tag in set(self.tagSeedList):
                if (tag not in foundSpanned) and (tag not in foundSpanless):
                    if self.task:
                        trueLab = globalATR.getTrueLabelForEffectiveLabel(tag)
                        if globalATR[trueLab].hasSpan:
                            finalStratum[0].append(tag)
                        else:
                            finalStratum[1].append(tag)
                    else:
                        finalStratum[0].append(tag)
            if finalStratum[0] or finalStratum[1]:
                orderedStrata.append(finalStratum)

        # We need to postprocess labsToDecomps so the elements in
        # the lists are sorted lists, rather than sets.
        for decomps in labsToDecomps.values():
            decomps["attrs"] = [list(s) for s in decomps["attrs"]]
            for l in decomps["attrs"]:
                l.sort()
            decomps["partitions"] = [list(s) for s in decomps["partitions"]]
            for l in decomps["partitions"]:
                l.sort()

        if self.tagCounts:
            self.tagCorpusAggregate = self.tagCounts._newAggregate(tagDict, translatedAggrs, rowCacheSeed,
                                                                   basenameInfoDict)
            self.tagCorpusAggregate._updateFromAccumulations(tagDict, self.tagCounts, numDocs,
                                                             orderedStrata, labsToDecomps)
        if self.pseudoTokenCounts:
            self.pseudoTokenCorpusAggregate = self.pseudoTokenCounts._newAggregate(pseudoTokenDict,
                                                                                   translatedAggrs, 
                                                                                   rowCacheSeed,
                                                                                   basenameInfoDict)
            self.pseudoTokenCorpusAggregate._updateFromAccumulations(pseudoTokenDict, self.pseudoTokenCounts, numDocs,
                                                                     orderedStrata, labsToDecomps)
        if self.characterCounts:
            self.characterCorpusAggregate = self.characterCounts._newAggregate(charDict,
                                                                               translatedAggrs, 
                                                                               rowCacheSeed,
                                                                               basenameInfoDict)
            self.characterCorpusAggregate._updateFromAccumulations(charDict, self.characterCounts, numDocs,
                                                                   orderedStrata, labsToDecomps)
        if tokenTotal and self.tokenCounts:
            self.foundSomeTokens = True
            self.tokenCorpusAggregate = self.tokenCounts._newAggregate(tokenDict, translatedAggrs, 
                                                                       rowCacheSeed,
                                                                       basenameInfoDict)
            self.tokenCorpusAggregate._updateFromAccumulations(tokenDict, self.tokenCounts, numDocs,
                                                               orderedStrata, labsToDecomps)
        if self.confusabilityTable is not None:
            self.confusabilityTable.declareAllTags(allTags)
    
    def formatResults(self, byTag = True, byToken = True, byPseudoToken = True, byCharacter = True, detail = True, confusability = True):

        s = ""
        if self.tagCounts and byTag:
            s += "By tag:\n\n" + self.tagCounts.extractGlobalSummary().format()

        if self.tokenCounts and byToken and self.foundSomeTokens:
            s += "\n\nBy token:\n\n" + self.tokenCounts.extractGlobalSummary().format()

        if self.pseudoTokenCounts and byPseudoToken:
            s += "\n\nBy pseudo-token:\n\n" + self.pseudoTokenCounts.extractGlobalSummary().format()

        if self.characterCounts and byCharacter:
            s += "\n\nBy character:\n\n" + self.characterCounts.extractGlobalSummary().format()

        # Step 3: Show the details, if appropriate.

        if self.tagDetails and detail:
            s += "\n\nDetails:\n\n" + self.tagDetails.format()

        if self.confusabilityTable and confusability:
            if self.tokenCounts and self.foundSomeTokens:
                s += "\n\nToken confusability matrix:\n\n" + self.confusabilityTable.format()
            else:
                s += "\n\nPseudo-token confusability matrix:\n\n" + self.confusabilityTable.format()

        return s

    def writeCSV(self, outputDir, byTag = True, byToken = True, byPseudoToken = True, byCharacter = True, detail = True, confusability = True):

        if self.tagCounts and byTag:
            self.tagCounts.writeCSVByFormat(outputDir, "bytag")
        if self.tokenCounts and byToken and self.foundSomeTokens:
            self.tokenCounts.writeCSVByFormat(outputDir, "bytoken")
        if self.pseudoTokenCounts and byPseudoToken:
            self.pseudoTokenCounts.writeCSVByFormat(outputDir, "bypseudotoken")
        if self.characterCounts and byCharacter:
            self.characterCounts.writeCSVByFormat(outputDir, "bychar")
        if self.tagDetails and detail:
            self.tagDetails.writeCSV(os.path.join(outputDir, "details.csv"))
        if self.confusabilityTable and detail:
            self.confusabilityTable.writeCSV(os.path.join(outputDir, "confusability.csv"))
