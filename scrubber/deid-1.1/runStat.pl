 #!/usr/bin/perl
#**************************************************************************************************************
# File: runStat.pl	 
# Author: L. Lehman 
# (lilehman AT alum DOT mit DOT edu) Nov, 2007
#
# Requires: stat.pm library file
#______________________________________________________________________________
#
# runStat.pl: Calculates performance statistics by comparing PHI 
# locations in 2 files using the first file as the reference for comparison. 
#
# Performance statistics are printed on the screen
# Sensitivity = TP/(TP+FN)    
# PPV = TP/(TP+FP)
# note: sensitivity = recall, PPV = specificity
#
# Command to run the software: 
#
# perl runStat.pl <filename1> <filename2>
#
# where <filename1> is the name of file containing the reference / gold standard  
# PHI locations, and <filename2> is the name of the file containing PHI 
# locations output from the deid software or some other PHI locations you
# wish to generate performance statistics for. 
#
# Example Usage: perl runStat.pl id.deid id.phi
#
# The file format should be the same as those used in the gold standard 
# PHI location file, id.deid. Please see the user manual 
# (./docs/DeidUserManual.pdf) for PHI location file format specifications.
#
#Copyright (C) 2007 L. Lehman
#
#This code is free software; you can redistribute it and/or modify it under
#the terms of the GNU Library General Public License as published by the Free
#Software Foundation; either version 2 of the License, or (at your option) any
#later version.
#
#This library is distributed in the hope that it will be useful, but WITHOUT ANY
#WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#PARTICULAR PURPOSE.  See the GNU Library General Public License for more
#details.
#
#You should have received a copy of the GNU Library General Public License along
#with this code; if not, write to the Free Software Foundation, Inc., 59
#Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
#You may contact the author by e-mail or postal mail
#(MIT Room E25-505, Cambridge, MA 02139 USA).  For updates to this software,
#please visit PhysioNet (http://www.physionet.org/).
#_______________________________________________________________________________

#**************************************************************************************************************
# Arguments: string $gs (file name for reference / gold standard PHI locations), 
#   string $test (file name for PHI locations you wish to generate 
#   performance statistics for)
# Description: Calculates performance statistics by comparing PHI 
#   locations in $test file against a reference (gold standard) PHI location file
#   $gs, and output performance statistics on screen.

if ($#ARGV == 1) { 
    $gs = $ARGV[0];
    $test = $ARGV[1];
    require "stat.pm";    
    &stat($gs,$test); 

} else {
    print "\nError: Wrong number of arguments entered";
    print "\nThe algorithm takes 2 arguments:";
    print "\n  1. filename1 (reference / gold standard PHI locations)";
    print "\n  2. filename2 (PHI locations you wish to evaluate)";
    print "\nExample: perl runStat.pl id.deid id.phi\n";

}

