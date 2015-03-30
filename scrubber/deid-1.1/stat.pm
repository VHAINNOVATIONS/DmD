 #!/usr/bin/perl

#**************************************************************************************************************
# File: stat.pm	 
# Authors: M. Douglass, I. Neamatullah, L. Lehman 
# Last revised by Li Lehman 	
# (lilehman AT alum DOT mit DOT edu) in December, 2007
#______________________________________________________________________________
#
# stat.pm: contains library subroutines to calculate code performance 
# statistics by comparing PHI locations in a file with a reference
# or gold standard PHI location file.
#
# Performance statistics are printed on the screen
# Sensitivity = TP/(TP+FN)    
# PPV = TP/(TP+FP)
# note: sensitivity = recall, PPV = specificity
##
#Copyright (C) 2004-2007 Margaret Douglas and  Ishna Neamatullah
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

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: stat()
# Arguments: string $gs (file name for gold standard PHI locations), 
#   string $test (file name for PHI locations you wish to generate 
#   performance statistics for)
# Returns: None
# Description: Calculates performance statistics by comparing PHI 
#   locations in $test file against a reference (gold standard) PHI location file
#   $gs, and output performance statistics on screen.
#   Performance statistics generated:
# Sensitivity = TP/(TP+FN)    
# PPV = TP/(TP+FP)
#
# note: sensitivity = recall, PPV = specificity

sub stat() {

    my ($gs, $test);
    ($gs,$test) = @_;

    open GS, $gs or die "Cannot open $gs. Make sure that a gold standard exists";   # GS = Gold Standard file
    open TEST, $test or die "Cannot open $test";   # TEST = Deid'ed file
    
    # Runs through deid'ed file line by line
    # Enters PHI locations in a HASH %phi with KEY = (patient_number appended with note_number) and VALUE = (ARRAY of PHI locations in that note)
    my $counter=0;
    my $c = 0;
    my %phi;
    while ($line1 = <TEST>) {
	chomp $line1;
	#if ($line1 =~ /(patient *(\d+)\tnote *(\d+))/ig) {
	if ($line1 =~ /(patient\s+(\d+)\s+note\s+(\d+))/ig) {
	    $c = 0;
	    $counter = $2."||||".$3;
	}
	#elsif ($line1 =~ /(\d+)\t(\d+)\t(\d+)/ig) {
	elsif ($line1 =~ /(\d+)\s+(\d+)\s+(\d+)/ig) {
	    $st = $2;
	    $end = $3;    
	    $phi{$counter}[$c] = "$st-$end";
	    $c++;
	}
    }

           
    # Runs through Gold Standard file line by line
    # Enters PHI locations in a HASH %phi2 with KEY = (patient_number appended with note_number) and VALUE = (ARRAY of PHI locations in that note)
    my $counter2=0;
    my $c2 = 0;
    my %phi2;
    my $totalp = 0;
    while ($line2 = <GS>) {
	chomp $line2;
	#if ($line2 =~ /(patient *(\d+)\tnote * (\d+))/ig) {
	if ($line2 =~ /(patient\s+(\d+)\s+note\s+(\d+))/ig) {
	    $c2 = 0;
	    $counter2 = $2."||||".$3;
	}
	#elsif ($line2 =~ /(\d+)\t(\d+)\t(\d+)/ig) {
	elsif ($line2 =~ /(\d+)\s+(\d+)\s+(\d+)/ig) {
	    $st = $2;
	    $end = $3;
	    $phi2{$counter2}[$c2] = "$st-$end";
	    $c2++;
	    $totalp++;
	}
    }    
    
    my $key;
    my $key2;
    my $key22;

    # Runs through each patient_note combination in Gold Standard hash
    # Then in each note, runs through each PHI location 
    # For each PHI location, checks if the same location exists in the same patient_note in the deid'ed hash
    # If there is a match, true positives is incremented
    # If there is no match, false negatives is incremented   
    my $tp = 0;   # true positives
    my $fn = 0;   # false negatives
    my $gsstart;
    my $gsend;
    my $prevgsstart;
    my $prevgsend;
    my $nextgsstart;
    my $nextgsend;
    my $teststart;
    my $testend;
    my $prevteststart;
    my $prevtestend;
    my $found1 = 0;
   
    foreach $key (sort keys %phi2) {
	my @x = @{$phi2{$key}};
	my $len = $#x + 1;
	#foreach $key2 (1 .. length($phi2{$key})) {
	foreach $key2 (1 .. $len) {
	    $found1 = 0;
	    $gsphi = $phi2{$key}[$key2-1];
	    if ((length $gsphi) != 0) {
		($gsstart, $gsend) = split "-", $gsphi;
		$nextgsphi = $phi2{$key}[$key2];
		if ((length $nextgsphi) != 0) {
		    ($nextgsstart, $nextgsend) = split "-", $nextgsphi;
		}

		my $overlap_len = 0; # init to zero for each new gs PHI
		#go through the test phi to find match with gs phi
	
		@x2 = @{$phi{$key}};
		my $len2 = $#x2 + 1;

		#foreach $key22 (1 .. length($phi{$key})) {
		foreach $key22 (1 ..$len2) {
		
		    $i = $phi{$key}[$key22-1];
		    if ((length $i) != 0) {
			($teststart, $testend) = split "-", $i;

			
			#if gs phi and test phi overlap
			if ( (($gsstart  <= $testend)  && ($gsstart >= $teststart))||
			     (($gsend <= $testend) && ($gsend >= $teststart)) ||
			     (($teststart  <= $gsend)  && ($teststart >= $gsstart))||
			     (($testend <= $gsend) && ($testend >= $gsstart))) 
			{
			    
			    $found1 = 1;
			    $tp = $tp++;
			    last;
			}   

		    }  #end if length $i is not zero
		} # end for each $key22

		if ($found1 == 0) {
		    #print "fn # $fn: $key, $gsphi\n";
		    $fn++;
		}	    
	    }

	}
    }
        
    # Runs through each patient_note combination in deid'ed hash
    # Then in each note, runs through each PHI location
    # For each PHI location, checks if the same location exists in the same patient_note in the Gold Standard hash
    # If there is a match, true positives is incremented
    # If there is no match, false positives is incremented
    my $fp = 0;   # false positives

    my $tp_test = 0;

    my $nextteststart;
    my $nexttestend;
    my $found2 = 0;
    my $totaltestphi = 0;  #total number of test phi
    
    #phi2 is GS, phi is Test
    foreach $key (sort keys %phi) {	
	my @x = @{$phi{$key}};
	my $len = $#x +1;
	#foreach $key2 (1 .. length($phi{$key})) {
	foreach $key2 (1 .. $len ) {
	    $found2 = 0;
	    $testphi = $phi{$key}[$key2-1];

	    if ((length $testphi) != 0) {
		$totaltestphi++; 
		($teststart, $testend) = split "-", $testphi;
		#print "$teststart $teststart $testend\n";
		$nexttestphi = $phi{$key}[$key2];
		if ((length $nexttestphi) != 0) {
		    ($nextteststart, $nexttestend) = split "-", $nexttestphi;
		}
		@x2 = @{$phi2{$key}};
		my $len2 = $#x2 + 1;
		#foreach $key22 (1 .. length($phi2{$key})) {	
		foreach $key22 (1 .. $len2) {	
		    $i = $phi2{$key}[$key22-1];
		    if ((length $i) != 0) {
			($gsstart, $gsend) = split "-", $i;

			
			#if testphi does not overlap with some gsphi, it's a false positive 
			if ( (($teststart  <= $gsend)  && ($teststart >= $gsstart)) ||
			     (($testend <= $gsend) && ($testend >= $gsstart)) ||
			     (($gsstart  <= $testsend)  && ($gsstart >= $teststart)) ||
			     (($gsend <= $testend) && ($gsend >= $teststart))) 
			{	    
			    $found2 = 1;
			    $tp_test++;
			    last;
			}   

		    }
		}
		if ($found2 == 0) {
		    $fp++;
		    #print "$teststart $teststart $testend\n";
		}
	    }

	}
    }   

    $tp = $totalp - $fn;  #totalp is number of phi in gold std

    # Calculates sensitivity and positive predictive value (PPV)
    $sens = round(($tp/($tp+$fn))*1000)/1000.0;
    #if($totaltestphi ne 0){
      
      $ppv = round(( ($totaltestphi-$fp)/$totaltestphi)*1000)/1000.0;
    #}
    #else{
    #  $ppv = 'zero';
    #}
    
  
    # Prints code performance statistics on the screen
    print "\n\n==========================\n";
    print "\nNum of true positives = $tp\n";
    print "\nNum of false positives = $fp\n";
    print "\nNum of false negatives = $fn\n";
    print "\nSensitivity/Recall = $sens\n";
    print "\nPPV/Specificity = $ppv\n";
    print "\n==========================\n\n";    
}

# End of stat()


################################################
#subroutine to perform rounding for positive numbers
sub round {
    my($number) = shift;
    return int($number + .5);
}
#end round()


1;
