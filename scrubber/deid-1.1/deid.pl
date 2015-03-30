 #!/usr/bin/perl

#**************************************************************************************************************
#file: deid.pl	 Original author: M. Douglass 2004	
#Last revised:    Apr 2009	DeID 1.1
#                 
#
#_______________________________________________________________________________
#
#deid.pl: De-identification algorithm -- scrubs PHI from free-text medical records 
#(e.g. Discharge Summaries and Nursing Notes)
#
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
#
# De-identification Algorithm: Scrubs PHI from free-text medical records 
#(e.g. Discharge Summaries and Nursing Notes)
# Original version written by: 
#   Margaret Douglass (douglass AT alum DOT mit DOT edu)
#   William Long (wjl AT mit DOT edu)
# Modified by:
#   Ishna Neamatullah (ishna AT alum DOT mit DOT edu) in Sept 5, 2006
# Last modified by:
#   Li-wei Lehman (lilehman AT alum DOT mit DOT edu) in April, 2009
#
# Command to run the software: 
# perl deid.pl <filename> <config_filename>
#
# Input arguments: 
# filename (without extension, where extension must be .text): file to be de-identified
# config_filename: configuration file
#
# Required library file: stat.pm
#
# Output files:
# filename.res: de-identified file
# filename.phi: file containing all PHI locations, used in calculating performance statistics
# filename.info: file containing information useful for debugging
# code performance statistics printed on screen if Gold Standard available for nursing notes (details in README)
#**************************************************************************************************************

#use Stat;

# Declaring some variables for algorithm run configuration

# Variables to switch on/off filter functions
$allfilters = "";
$ssnfilter = "";
$urlfilter = "";
$emailfilter = "";
$telfilter = "";
$unitfilter = "";
$agefilter = "";
$locfilter = "";
$datefilter = "";
$namefilter = "";
$us_state_filter = "";
$ds_specific_filter = ""; #filter for discharge summmary specific patterns
$gs_specific_filter = ""; #filter for gold std specific patterns

my $offset; # positive date shift in number of days
my $comparison = ""; # 1=comparison with gold standard, 0=no comparison with gold standard

# Variables to switch on/off dictionaries/lists
$alllists = "";
$pid_patientname_list = "";
$pid_dateshift_list = "";
$country_list = "";
$company_list = "";
$ethnicity_list = "";
$hospital_list = "";
$doctor_list = "";
$location_list = "";
$local_list = "";
$state_list = "";

use Time::Local;
my ($mday,$mon,$year) = (localtime(time))[3,4,5];
my $shortyear = substr($year,1,4);
my $longyear = '20'.$shortyear; 

# Nursing note date as retrieved from the header
my $nn_year;

# Sets whether a de-identified version should be output: 0 = no new version of text output, 1 = fully de-identified version of text output
# Note: Generally keep output_deid_text = 1 
$output_deid_text = 1;

#Default date used to de-identify the Gold Std if no default date is specified in the
#config file.  You can change the default date by setting the "Default date" variable to
#some other dates (in MM/DD/YYYY format).
$DEFAULT_DATE = "01/01/2000";

#The "Two Digit Year Threshold" is used to determine whether
#to interpret the year as a year in the 1900's or 2000's.
#Must be a 1- or 2-digit number.
#Two digit years > Threshold are  interepreted as in the 1900's
#Two digit years <=  Threshold are interpreted as in the 2000's
$TWO_DIGIT_YEAR_THRESHOLD = 30;#change this default by setting "Two Digit Year Threshold" in config file.

# "Valid Year Low" and "Valid Year High" (must be 4-digit numbers) are 
# used in certain date pattern checking routines to determine if a 
# four digit number that appear in a potential 
# date pattern is a year or not -- it is a valid year if it is
# in the range of [Valid Year Low, Valid Year High].  
$VALID_YEAR_LOW = 1900; 
$VALID_YEAR_HIGH = 2030;



my @known_phi;
my @known_first_name;
my @known_last_name;

# Hash that stores PHI information from de-identification
# KEY = (patient number), VALUE = array with each element = (%HASH with KEY = start-end, VALUE = array of types of PHI for the note number/index of the array)
%all_phi;
my %ID;

# Declares some global variables
%lhash = ();
@typename = ();
$ntype = 1;
@extend = ('phrases');


##########################################################################################
# Sets paths to lists and dictionaries in working directory that will be used in this algorithm
$date_shift_file = "shift.txt"; # contains mapping of PID to date offset
$countries_file = "lists/countries_unambig.txt";
$ethnicities_unambig_file = "lists/ethnicities_unambig.txt";
$companies_file = "lists/company_names_unambig.txt";
$companies_ambig_file = "lists/company_names_ambig.txt";
$common_words_file = "dict/common_words.txt";
$medical_words_file = "dict/sno_edited.txt"; 
$very_common_words_file = "dict/commonest_words.txt"; 
$female_unambig_file = "lists/female_names_unambig.txt";
$female_ambig_file = "lists/female_names_ambig.txt";
$female_popular_file = "lists/female_names_popular.txt";
$male_unambig_file = "lists/male_names_unambig.txt";
$male_ambig_file = "lists/male_names_ambig.txt";
$male_popular_file = "lists/male_names_popular.txt";
$last_unambig_file = "lists/last_names_unambig.txt";
$last_ambig_file = "lists/last_names_ambig.txt";
$last_popular_file = "lists/last_names_popular.txt";
#$last_name_prefixes_file = "lists/last_name_prefixes.txt";
$doctor_first_unambig_file = "lists/doctor_first_names.txt";
$doctor_last_unambig_file = "lists/doctor_last_names.txt";
$prefixes_unambig_file = "lists/prefixes_unambig.txt";
$locations_unambig_file = "lists/locations_unambig.txt"; 
$locations_ambig_file = "lists/locations_ambig.txt";
$local_places_ambig_file = "lists/local_places_ambig.txt";
$local_places_unambig_file = "lists/local_places_unambig.txt";
$hospital_file = "lists/stripped_hospitals.txt";
$last_name_prefix_file = "lists/last_name_prefixes.txt";
$patient_file = "lists/pid_patientname.txt"; # contains mapping of PID to patient name
$us_states_file = "lists/us_states.txt";
$us_states_abbre_file = "lists/us_states_abbre.txt";
$more_us_states_abbre_file = "lists/more_us_state_abbreviations.txt";
$us_area_code_file = "lists/us_area_code.txt";
$medical_phrases_file = "dict/medical_phrases.txt"; 
$unambig_common_words_file = "dict/notes_common.txt";

############################################################################################################
# Declares some arrays of context words that can be used to identify PHI
# Days of the month
@days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday");

# Titles that precede last names (ignore .'s)
@titles = ("MISTER", "DOCTOR", "DOCTORS", "MISS", "PROF", "PROFESSOR", "REV", "RABBI", "NURSE", "MD", "PRINCESS", "PRINCE", "DEACON", "DEACONESS", "CAREGIVER", "PRACTITIONER", "MR", "MS");

@strict_titles = ("Dr", "DRS", "Mrs");  #treat words after these strict_titles as PHI 

%titles = ();
foreach $title (@titles){
    $titles{$title} = 1;
}

# Name indicators that precede or follow names
@name_indicators = ("problem","problem:", "proxy", "daughter","daughters", "dtr", "son", "brother","sister", "mother", "mom", "father", "dad", "wife", "husband", "neice", "nephew", "spouse", "partner", "cousin", "aunt", "uncle", "granddaughter", "grandson", "grandmother", "grandmom", "grandfather", "granddad", "relative", "friend", "neighbor", "visitor", "family member", "lawyer", "priest", "rabbi", "coworker", "co-worker", "boyfriend", "girlfriend", "name is", "named", "rrt", "significant other", "jr", "caregiver", "proxys", "friends", "sons", "brothers", "sisters", "sister-in-law", "brother-in-law", "mother-in-law", "father-in-law", "son-in-law", "daughter-in-law", "dtr-in-law", "surname will be", "name will be", "name at discharge will be", "name at discharge is");


# Phrases that precede locations
@location_indicators = ("lives in", "resident of", "lived in", "lives at", "comes from", "called from", "visited from", "arrived from", "returned to");

@employment_indicators_pre = ("employee of", "employed by", "employed at", "CEO of", "manager at", "manager for", "manager of", "works at", "business");


# Hospital indicators that follow hospital names
@hospital_indicators = ("Hospital", "General Hospital", "Gen Hospital", "gen hosp", "hosp", "Medical Center", "Med Center", "Med Ctr", "Rehab", "Clinic", "Rehabilitation", "Campus", "health center", "cancer center", "development center", "community health center", "health and rehabilitation", "Medical", "transferred to", "transferred from", "transfered to", "transfered from");

# Location indicators that follow locations
@loc_indicators_suff = ("city", "town", "beach", "valley","county", "harbor", "ville", "creek", "springs", "mountain", "island", "lake", "lakes", "shore", "garden", "haven", "village", "grove", "hills", "hill", "shire", "cove", "coast", "alley", "street", "terrace", "boulevard", "parkway", "highway", "university", "college", "tower");

# Location indicators that are most likely preceded by locations
@loc_ind_suff_c = ("town", "ville", "harbor", "tower");

# Location indicators that precede locations
#@loc_indicators_pre = ("cape", "fort", "lake", "mount", "santa", "los", "great","east","west","north","south");
@loc_indicators_pre = ("cape", "fort", "lake", "mount", "santa", "los", "east","west","north","south");


@apt_indicators = ("apt", "suite"); #only check these after the street address is found
@street_add_suff = ("park", "drive", "street", "road", "lane", "boulevard", "blvd", "avenue", "highway", "circle","ave", "place", "rd", "st");

#Strict street address suffix: case-sensitive match on the following, 
#and will be marked as PHI regardless of ambiguity (common words)
@strict_street_add_suff = ("Park", "Drive", "Street", "Road", "Lane", "Boulevard", "Blvd", "Avenue", "Highway","Ave",,"Rd", "PARK", "DRIVE", "STREET", "ROAD", "LANE", "BOULEVARD", "BLVD", "AVENUE", "HIGHWAY","AVE", "RD");

# Age indicators that follow ages
@age_indicators_suff = ("year old", "y\. o\.", "y\.o\.", "yo", "y", "years old", "year-old", "-year-old", "years-old", "-years-old", "years of age", "yrs of age");

# Age indicators that precede ages
@age_indicators_pre = ("age", "he is", "she is", "patient is");

# Digits, used in identifying ages
@digits = ("one","two","three","four","five","six","seven","eight","nine", "");

# Different variations of the 12 months
@months = ("January", "Jan", "February", "Feb", "March", "Mar", "April", "Apr", "May", "June", "Jun", "July", "Jul", "August", "Aug", "September", "Sept", "Sep", "October", "Oct", "November", "Nov", "December", "Dec");

######################################################################################
# If the correct number of input argument is provided, sets the input and output filenames.
if ($#ARGV == 1) { 
    $data_file = "$ARGV[0].text";      # data_file: input file
    $output_file = "$ARGV[0].phi";     # output_file: file containing PHI locations
    $debug_file = "$ARGV[0].info";     # debug_file: file used for debugging, contains PHI and non-PHI locations
    $deid_text_file = "$ARGV[0].res";  # deid_text_file: de-identified text file 
    $gs_file = "$ARGV[0].deid";        # gs_file: Gold Standard of the input file


    print "\n*******************************************************************************************************************\n";
    print "De-Identification Algorithm: Identifies Protected Health Information (PHI) in Discharge Summaries and Nursing Notes";
    print "\n*******************************************************************************************************************\n";


   
    $config_file = $ARGV[1];
    open CF, $config_file or die "Cannot open $config_file";
    while ($cfline = <CF>) {
	chomp $cfline;
	if ($cfline =~ /\A[\#]+/){
	   next;
	}
	if ($cfline =~ /\bGold\s+standard\s+comparison\s*\=\s*([0-9])/ig) {
	    $comparison = ($1);
	}
	#Date default expects MM/DD/YYYY
	if ($cfline =~ /\bDate\s+default\s*\=\s*(\d\d)\/(\d\d)\/(\d\d\d\d)/ig) {
	    
	    my $mm = $1; $dd = $2; $yyyy = $3;
	    $DEFAULT_DATE = "$mm/$dd/$yyyy";
	    #print "Default date is $DEFAULT_DATE\n";
	}
 
	#The "Two Digit Year Threshold" is used to determine whether
        #to interpret the year as a year in the 1900's or 2000's
	if ($cfline =~ /\bTwo\s+Digit\s+Year\s+Threshold\s*=\s*(\d{1,2})/ig) {
	    $TWO_DIGIT_YEAR_THRESHOLD = "$1";
	    #print "Two Digit Year Threshold is $TWO_DIGIT_YEAR_THRESHOLD\n";
	}
 
	if ($cfline =~ /\bDate\s+offset\s*\=\s*([0-9]+)/ig) {
	    $offset = ($1);
	    #print "Date offset is $1\n";
	}
	if ($cfline =~ /\bSSN\s+filter\s*\=\s*([a-z])/ig) {
	    $ssnfilter = ($1);	   
	}
	if ($cfline =~ /\bURL\s+filter\s*\=\s*([a-z])/ig) {
	    $urlfilter = ($1);
	}
	if ($cfline =~ /\bEmail\s+filter\s*\=\s*([a-z])/ig) {
	    $emailfilter = ($1);
	}
	if ($cfline =~ /\bTelephone\s+filter\s*\=\s*([a-z])/ig) {
	    $telfilter = ($1);
	}
	if ($cfline =~ /\bUnit\s+number\s+filter\s*\=\s*([a-z])/ig) {
	    $unitfilter = ($1);
	}
	if ($cfline =~ /\bAge\s+filter\s*\=\s*([a-z])/ig) {
	    $agefilter = ($1);
	}
	if ($cfline =~ /\bLocation\s+filter\s*\=\s*([a-z])/ig) {
	    $locfilter = ($1);
	}
	if ($cfline =~ /\bDate\s+filter\s*\=\s*([a-z])/ig) {
	    $datefilter = ($1);
	}
	if ($cfline =~ /\bName\s+filter\s*\=\s*([a-z])/ig) {
	    $namefilter = ($1);
	}

	if ($cfline =~ /\bState\s+filter\s*\=\s*([a-z])/ig) {
	    $us_state_filter = ($1);

	}

	if ($cfline =~ /\bDS\s+filter\s*\=\s*([a-z])/ig) {
	    $ds_specific_filter = ($1);

	}

	if ($cfline =~ /\bGS\s+filter\s*\=\s*([a-z])/ig) {
	    $gs_specific_filter = ($1);

	}

	######################################################
	#get the config info for dictionaries loading
	if ($cfline =~ /\bPID\s+to\s+patient\s+name\s+mapping\s*\=\s*([a-z])/ig) {
	    $pid_patientname_list = ($1);

	}	
	if ($cfline =~ /\bPID\s+to\s+date\s+offset\s+mapping\s*\=\s*([a-z])/ig) {
	    $pid_dateshift_list = ($1);
	}
	if ($cfline =~ /\bCountry\s+names\s*\=\s*([a-z])/ig) {
	    $country_list = ($1);
	}
	if ($cfline =~ /\bCompany\s+names\s*\=\s*([a-z])/ig) {
	    $company_list = ($1);
	}
	if ($cfline =~ /\bEthnicities\s*\=\s*([a-z])/ig) {
	    $ethnicity_list = ($1);
	}
	if ($cfline =~ /\bHospital\s+names\s*\=\s*([a-z])/ig) {
	    $hospital_list = ($1);
	}
	if ($cfline =~ /\bLocation\s+names\s*\=\s*([a-z])/ig) {
	    $location_list = ($1);

	}	
	if ($cfline =~ /\bDoctor\s+names\s*\=\s*([a-z])/ig) {
	    $doctor_list = ($1);

	}

	if ($cfline =~ /\bLocalPlaces\s+names\s*\=\s*([a-z])/ig) {
	    $local_list = ($1);
	}

	if ($cfline =~ /\bState\s+names\s*\=\s*([a-z])/ig) {
	    $state_list = ($1);
	}

    }

}

# Prints an error message on the screen if number of arguments is incorrect
else {
    print "\n===========================================================================================";
    print "\nError: Wrong number of arguments entered";
    print "\nThe algorithm takes 2 arguments:";
    print "\n  1. filename (the filename of medical notes, without extension, where extension must be .text)";
    print "\n  2. config_filename (the configuration filename)";
    print "\nExample (for Gold Standard Comparison): perl deid.pl id deid.config";
    print "\nExample (for output mode using Gold Standard): perl deid.pl id deid-output.config";
    print "\nFor further documentation, please consult the README.txt file";
    print "\n===========================================================================================\n";
    exit;

}

# After setting file names and configuring the run, indicates that de-identification has commenced
print "\n\nStarting de-identification (version 1.1) ...\n\n";


#check if we can open the .phi file
open F, ">$output_file" or die "Cannot open $output_file";
close F;

# Calls setup to create some lookup lists in memory
setup();


if ($comparison==1) {
    print "Running deid in performance comparison mode.\n";    
    print "Using PHI locations in $gs_file as comparison. Output files will be:\n";
    print "$output_file: the PHI locations found by the code.\n"; 
    print "$debug_file: debug info about the PHI locations.\n";
    #check if the gold std file exists
    open GS, $gs_file or die "Cannot open $gs_file. Make sure that the gold standard file exists!\n";   # GS = Gold Standard file
    close GS;
} 
else {
    #check if we can open the .res file
    open F, ">$deid_text_file" or die "Cannot open $deid_text_file";
    close F;
    print "Running deid in output mode. Output files will be: \n";
    print "$output_file: the PHI locations found by the code.\n"; 
    print "$deid_text_file: the scrubbed text.\n"; 
    print "$debug_file: debug info about the PHI locations.\n";
      
}

deid();

# Calls function stat() to calculate code performance statistics, if comparison mode = 1
if ($comparison==1) {
    require "stat.pm";
    &stat($gs_file, $output_file);

}

# End of top level of code
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
sub numerically { 
		      #print "a is $a  b is $b\n";
		      $a <=> $b;
 }
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Reads in a file and pushes each line onto an array. Returns the array.

sub preload {
    my ($file) = @_;
    my @res = ();
    open FILE, $file or die "Cannot open file $file";
    while ($line = <FILE>) {
	chomp $line;
	push(@res, uc($line));
    }
    close FILE;
    return @res;
}
# End of preload()
#***********************************************************************************************************
#***********************************************************************************************************
#*********************************************************************************************************** 
# Reads in a file and pushes each line onto an array. Returns the array.

sub preload_uc {
    my ($file) = @_;
    my @res = ();
    open FILE, $file or die "Cannot open file $file";
    while ($line = <FILE>) {
	chomp $line;
	push(@res, uc($line));
    }
    close FILE;
    return @res;
}
# End of preload_uc()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Reads in a file and creates a dictionary that records each line in that file under the given association, by mapping the line to a '1' in the dictionary of the association

sub preload_assoc {
    my ($file,$assoc) = @_;
    open FILE, $file or die "Cannot open file $file";

    while ($line = <FILE>) {
	chomp $line;
	$$assoc{uc($line)}=1;
    }
    close FILE;
}
# End of preload_assoc()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Reads in a file and calls setup_hash on each line

sub setup_hash {
    my ($file, $tname) = @_;
    my @entry;
    $typename[$ntype]= $tname;
    open FILE, $file or die "Cannot open file $file";
    while ($line = <FILE>) {
	chomp $line;
	&setup_item($ntype,$line);
    }
    $ntype++;
    close FILE;
}
# End of setup_hash()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Reads in a file and calls setup_hash on each line
sub setup_lst_hash {
    my ($tname, @hlst) = @_;
    $typename[$ntype]= $tname;
    foreach $line (@hlst) {
	&setup_item($ntype,$line);
    }
    $ntype++;
}
# End of setup_lst_hash()
#***********************************************************************************************************
#***********************************************************************************************************
#*********************************************************************************************************** 
sub setup_item {
    my ($type,$line) = @_;
    my ($head, @lst) = split (/([^a-zA-Z0-9_\']+)/,uc($line));
    my $ix = $type;
  
    if(@lst){

	push @extend, [@lst];
	$ix = "$type,$#extend";
    }
    my $entry = $lhash{$head};
    if ($entry){
	$lhash{$head} .= "|" . $ix;
    }
    else{$lhash{$head}=$ix;
     }
}

# End of setup_item()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
sub typename {
    my ($num) = @_;
    return($typename[$num]);
}
# End of typename()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Takes in an array of words and compares them with hashes of known PHI. Recognizes and adds PHI using addType().

sub lookhash {
    my @txtlst = @_;
    my $pos = 0;
    my $npos = 0;
    my $tl,$ty;
    my $txt = 1; # item is text not separator
    my $item;

    while (@txtlst) {
	$item = shift(@txtlst);

	$npos = $pos + length($item);
	if ($item =~ /([a-zA-Z\']+)/ig) {
	    if($item){
		$item = uc($item);
		$tl = $lhash{$item};

		#if the term ends with 's, remove it and see if
                #there is a match in PHI hash
		#if (!($tl) && $item =~/([a-zA-Z\'\-]+)\'s$/ig) {
		if (!($tl) && $item =~/([a-zA-Z\']+)\'s$/ig) { 
		    $tl = $lhash {$1};
		}

		if($tl){

		    # Compares with known PHI by calling bestmatch()
		    ($xpos, $done, @types)=&bestmatch($tl,@txtlst);
		    splice(@txtlst,0,$#txtlst-$done);
		    $npos += $xpos;

		    foreach $typ (@types){
			#print "item $item, adding type $type for position $pos-$npos\n";
			#print "type is $typ , key is $pos - $npos  \n";
			addType("$pos-$npos",$typ);		
			#print "positions are $pos-$npos, typ is $typ\n";
		    }
		}
	    }  #end if $item
	    $txt = 0;
	}  #end if $txt
	else {
	    $txt = 1;
	}
	$pos = $npos;
    }
}
# End of lookhash()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
sub bestmatch {
    my ($tl,@txtlst) = @_;
    my $pos = 0;
    my $bestpos = 0;
    my $bestrest = $#txtlst;
    my @besttyp = ();
    my ($type, $rest, $xpos, @nlst);

    foreach $ck (split '\|',$tl) {
	($type, $rest) = split ',',$ck;

	if($rest) {
	    ($xpos , @nlst) = &matchrest($rest,@txtlst);
	    if ($xpos) {
		if($xpos > $bestpos) {

		    $bestrest = $#nlst; $bestpos = $xpos; 
		    @besttyp = ($typename[$type]);
		}
		elsif($xpos == $bestpos) {
		    push @besttyp,$typename[$type];
		}
	    }
	}
	elsif ($bestpos == 0) {
	    push @besttyp,$typename[$type];
	}
    }
    return ($bestpos, $bestrest, @besttyp);
}
# End of bestmatch()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
sub matchrest {
    my ($rest, @txtlst) = @_;
    my @mlst = @{$extend[$rest]};
    my $item;
    my $pos = 0;
    my $pm = 0;

    my $tmppos = 0;

    if ($mlst[0] eq '|') {
	$pm = 1; shift(@mlst);
    }
    foreach $i (@mlst) {
	if ($i !~ /([a-zA-Z\'\-]+)$/ig){
	    next;
	}

	$item = shift(@txtlst);
	$pos += length($item);


	while ( $#txtlst >= 0 && ($item !~ /([a-zA-Z\'\-]+)/ig)){
	    $item = shift(@txtlst);
	    $pos += length ($item);
	    #print "item is $item, len is $#txtlst";
	}

	if ($pm ? (uc($item) !~ /$i/) : ($i ne uc($item))) {
	    #print "pm is $pm, returning zero\n";
	    return 0;
	}
    }
    return ($pos, @txtlst);
}
# End of matchrest()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: setup()
# Arguments: None
# Returns: None
# Called by: Topmost level of code
# Description: Creates some lookup lists to have in memory
sub setup {
    
    # This part is not necessary
    open LP, $last_name_prefix_file or die "Cannot open $last_name_prefix_file";
    while ($line = <LP>) {
	chomp $line;
	$prefixes{uc($line)} = 1;
    }
    close LP;

    #Added to reduce false positives
    &setup_hash($medical_phrases_file,"MedicalPhrase");
   
    # Sets up hashes of some PHI lists for direct identification
    if ($namefilter =~ /y/) {
	&setup_hash($female_unambig_file,"Female First Name (un)");
	&setup_hash($female_ambig_file,"Female First Name (ambig)");
	&setup_hash($male_unambig_file,"Male First Name (un)");
	&setup_hash($male_ambig_file,"Male First Name (ambig)");
	&setup_hash($last_unambig_file,"Last Name (un)");
	&setup_hash($last_popular_file,"Last Name (popular/ambig)"); 
	&setup_hash($last_ambig_file,"Last Name (ambig)");
	&setup_hash($female_popular_file, "Female First Name (popular/ambig)");
	&setup_hash($male_popular_file, "Male First Name (popular/ambig)");
	
	if ($doctor_list =~ /y/) {
	    &setup_hash($doctor_first_unambig_file, "Doctor First Name");
	    &setup_hash($doctor_last_unambig_file, "Doctor Last Name");
	}
	
    }

    if ($locfilter =~ /y/) {
	if ($location_list =~ /y/) {
	    &setup_hash($locations_ambig_file,"Location (ambig)");
	    &setup_hash($locations_unambig_file,"Location (un)"); 
	  
	} else {
	    @loc_unambig = ();
	    @more_loc_unambig = ();
	    @loc_ambig = ();
	}


	if ($hospital_list =~ /y/) {
	    &setup_hash($hospital_file,"Hospital");
	}
	if ($ethnicity_list =~ /y/) {		
	    &setup_hash($ethnicities_unambig_file, "Ethnicity");
	}
	if ($company_list =~ /y/) {	
	    &setup_hash($companies_file, "Company");
	    &setup_hash($companies_ambig_file, "Company (ambig)");
	
	}
	if ($country_list =~ /y/) {
	    &setup_hash($countries_file, "Country");
	}

	if ($local_list =~ /y/){
	    &setup_hash($local_places_unambig_file, "Location (un)"); 
	    &setup_hash($local_places_ambig_file, "Location (ambig)"); 
	
	}
    }

    # Preloads PHI in some lists into corresponding arrays    
    @female_popular = &preload($female_popular_file);
    @male_popular = &preload($male_popular_file);
    #@last_name_prefixes = &preload_uc($last_name_prefixes_file);
    @prefixes_unambig = &preload_uc($prefixes_unambig_file);
    

    if ($hospital_list =~ /y/) {
	@hospital = &preload($hospital_file);
    } else {@hospital = ();}

    if ($state_list =~ /y/){
	@us_states = &preload($us_states_file);
	@us_states_abbre =  &preload($us_states_abbre_file);
	@more_us_states_abbre =  &preload($more_us_states_abbre_file);
    }
  

    # Generates associations between PHI in some lists and PHI categories
    &preload_assoc($common_words_file,"common_words");
    &preload_assoc($medical_words_file,"common_words");

    &preload_assoc($very_common_words_file,"very_common_words");
    &preload_assoc($unambig_common_words_file, "unambig_common_words");
    &preload_assoc($male_unambig_file, "male_unambig");
    &preload_assoc($female_unambig_file, "female_unambig");
    &preload_assoc($female_ambig_file, "female_ambig");
    &preload_assoc($male_ambig_file, "male_ambig");
    &preload_assoc($last_ambig_file, "last_ambig");
    &preload_assoc($male_popular_file, "male_popular");
    &preload_assoc($female_popular_file, "female_popular");
    &preload_assoc($us_area_code_file,"us_area_code");

     # Opens debug file for debugging
    open D, ">".$debug_file;
    close D;
}
# End of setup()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: deid()
# Arguments: None
# Returns: None
# Called by: Topmost level of code
# Description: One of the 2 major branches of the code
# This function takes over de-identification if no performance statistic is required
# Function first loads the patient name list file.
# Then reads the medical text line by line.
#  If the line indicates START_OF_RECORD, read the Patient ID (PID), Note ID (NID), (and Note Date if any) info
# Scan for PHI a paragraph at a time
# output PHI locations into .phi file
my $currentID;
my @known_phi;
my @known_first_name;
my @known_last_name;
my %pidPtNames; # key = pid, value = [0] first name [1] last name

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************

sub deid {
    
    $allText = ""; 
    $allallText = "";
    open DF, $data_file or die "Cannot open $data_file";

    my $paraCount = 0;

    my $stpos = 0;


    my %deids; #key = start index, value = array of (end index, ID)
    my %phiTerms; #key = lc(word), value = # of occurrences
    my %phiT; 
    my %phiTT;
    my $noteDate;
    my $line;
 
    $currentID = 0; #initialize current ID to a non-existent PID 0 

    # Code runs through text by paragraph so things that extend over lines aren't missed
    $para = "";

    #load the patient name file
    if ($pid_patientname_list =~ /y/) {
	open PF, $patient_file or die "Cannot open $patient_file";
	
	while ($pfline = <PF>) {
	    chomp $pfline;

	    if ($pfline =~ /((.)+)\|\|\|\|((.)+)\|\|\|\|((.)+)/ig) {		
		my $pid = $1;

		$known_first_names = $3;
		$known_last_names = $5;			
		$pidPtNames{$pid}[0] = $known_first_names;
		$pidPtNames{$pid}[1] = $known_last_names;		
		
	    }# end if pfline = ~ /((.)+)\|\|\|\|((.)+)\|\|\|\|((.)+)/ig) 
	} # end while $pfline = <PF> 
    } #end if pid_patient_name_list ~= y
    ###End loading the patient names

    while ($line = <DF>) {
	
	#If this is a new record, set PID, Note ID
	#we assume all notes for the same patient go together
	if ( $line =~ /\ASTART_OF_RECORD=(([0-9]+)(\|)+([0-9]+)(\|)+(\d\d\/\d\d\/\d{4})?)/) {
	    
	   # $currentNote = $2;
	   # $thePT = $4;
	   # $noteDate =$6; #noteDate is empty in gold std

	    #print "pt $thePT, currentNote $currentNote\n";

	    #if it's gold standard, the header contains PID then NID
	   
	    $currentNote = $4;
	    $thePT = $2;
	    $noteDate =$6; #noteDate is empty in gold std

	    my $label = "Patient $thePT\tNote $currentNote";
	    open DEST, ">>".$debug_file or die "Cannot open $debug_file";
	    print DEST "$label\n";
	    close DEST;
	    
            #Gold Standard corpus does not specify note date, so assign a default
            #If you would like deid to date shift the notes on a per note basis, make sure you
            #specify the record date in the header!
	    if (length($noteDate) ==0){
	    	#$noteDate="01/01/2020";
		$noteDate = $DEFAULT_DATE;
	    }

	    #if this is a new patient, set the PID, and lookup patient name
	    if ($thePT != $currentID) {  #This is a new patient!	
		$currentID = $thePT;
		%phiTerms = ();  #clear the phiTerms on new pt


		# Find the patient name for the current PID
		#lookup first and last name of this patient
		if ($pid_patientname_list =~ /y/ && exists $pidPtNames{$currentID} ) {
		    
		    $known_first_names = $pidPtNames{$currentID}[0];
		    $known_last_names = $pidPtNames{$currentID}[1];
		    
		    #print "Found patient names, first = $known_first_names   last = $known_last_names\n";

		    if ($known_first_names =~ /([a-z][a-z]+)[\s\-]([a-z][a-z]+)/ig) {
			    @known_first_name = ($1, $2);}
		    else {
			if ($known_first_names =~ /\b([a-z])(\.?)\s([a-z]+)/ig) {
			    @known_first_name = ($3);
			}
			    
			elsif ($known_first_names =~ /\b([a-z][a-z]+)\s([a-z])(\.?)/ig) {
			    @known_first_name = ($1);
			}
			else {
			    @known_first_name = ($known_first_names);
			}
		    }
			
		    if ($known_last_names =~ /([a-z][a-z]+)[\s\-]([a-z][a-z]+)/ig) {
			@known_last_name = ($1, $2);}
		    else {
			if ($known_last_names =~ /\b([a-z])(\.?)\s([a-z]+)/ig) {
			    @known_last_name = ($3);
			}
			elsif ($known_last_names =~ /\b([a-z][a-z]+)\s([a-z])(\.?)/ig) {
			    @known_last_name = ($1);
			}
			
			else {
			    @known_last_name = ($known_last_names);	
			}
		    }


		} else {  #if no pid/patient name file, just set the first name and last name to null
		    @known_first_name = ();
		    @known_last_name = ();
		}
	    } # end if this is a new patient

	    #output the header to output file	    
            $allText = "";       #reset, 
	    $allallText = "";    #reset
	    $stpos = 0;
	    $para = "";

	    #if output mode, output the header line (with patient and note ID) to .res file
            if ($comparison == 0) {
	      open TF, ">>$deid_text_file" or die "Cannot open $deid_text_file";   #now open in append mode
	      print TF "\n$line";
	      close TF;
            }   
	    next; #skip to next line
	  }  #end if this is start of a record
	else {  #else this is not the start of a record, just append the line to the end of the current text
	    chomp $line;   
	    $allText .= $line."\n";
	    $allallText .= $line."\n";	  
            
            #$myline = $line;
            #chomp $myline;
	    #$allText .= $myline."\n";
	    #$allallText .= $myline."\n";	  
	}

	#Look for paragraph separator: if this is a line is entirely non-alphanumeric or
        #if it starts with spaces, or if it is an empty line, or if this line marks the end of record, 
        #then call findPHI() for the current paragraph we have so far.
        #If end of record is encoutnered, output the de-id text; else if 
        #it's not end of record yet, append the line to the paragraph. 
#	if ( (!($line =~ /[a-zA-Z\d]+/)) || $line =~ /^ +/ || $line eq "" || ($line =~ /\|\|\|\|END_OF_RECORD/) ) {  
	if (   (!($line =~ /[a-zA-Z\d]+/)) || ($line eq "") || ($line =~ /\|\|\|\|END_OF_RECORD/) ) {  
	    if ($para =~ /\w/ ){  #if para contains alphanumeric
				
                # Calls findPHI() with current paragraph; resulting PHI locations are stored in %phiT
		#%phiT = findPHI("Para $paraCount", $date, $stpos, $para);
		%phiT = findPHI("Para $paraCount", $noteDate, $stpos, $para);
		$paraCount++;
		# %phiT is copied over to %phiTT
		foreach $x (sort numerically keys %phiT) {
		    @{$phiTT{$x}} = @{$phiT{$x}};
		}
		
		#Sorts keys in %phiT; outputs text accordingly
		foreach $k (keys %phiT) {		  
		    my ($start, $end) = split '-', $k;
		    # $deids_end = ${@{$deids{$start}}}[0]; #does not work with perl v5.10
		    my @deidsval =  ${@{$deids{$start}}};
		    $deids_end = $deidsval[0];
       		   
		    $found = $phiT{$k};
		    foreach $t (@{$phiT{$k}}) {
		    }
		    my $word = lc(substr $allallText, $start, ($end - $start));

		    #print "Key in PhiT = $k, word = $word\n"; #DEBUG

		   # if ($end > ${@{$deids{$start}}}[0]) {  
		    if ($end > $deidsval[0]) {
			$deids{$start}[0] = $end;
			$deids{$start}[1] = $currentID;
			$deids{$start}[2] = $noteDate;						
		    }


		    #############################################################################
		    #Now remember the PHI terms that are important names for checking for repeated occurrences of PHIs
		    #PHI Name Tags
                    #(NI)       Name indicators
                    #(LF)       Lastname Firstnames
                    #(PTitle)   plural titles 
                    #(MD)       followed by  "MD" or "M.D"
                    #(PRE)      checks up to 3 words following "PCP Name" ("PCP", "physician", "provider", "created by", "name");
                    #(NameIs)   followed by pattern "name is"
                    #(Prefixes) for @prefixes_unambig) 
                    #(STitle)   @specific_titles = ("MR", "MISTER", "MS");
                    #(Titles)       @titles
                    #(NamePattern)  all other name patterns in sub name3
		    #remember all the PHI of type name (strict_titles) and name (indicators)
		    #print "checking for repeated occurences of PHIs: word is $word, phitype is (@{$phiT{$k}})\n";

		    if ( ($word !~ /\d/) && ((length $word) > 3) && !(isCommon($word)) && 
			 ( isPHIType( "(NI)", @{$phiT{$k}}) ||
			   isPHIType( "(PTitle)", (@{$phiT{$k}})) || isPHIType( "(LF)", (@{$phiT{$k}})) ||  
			   isPHIType( "(NamePattern)", (@{$phiT{$k}})) ||
			   isPHIType( "(MD)", (@{$phiT{$k}})) || 						  
			   isPHIType( "(NameIs)", (@{$phiT{$k}})) || isPHIType("(STitle)",  (@{$phiT{$k}})) || 
			   isPHIType("(Titles)", (@{$phiT{$k}}) ))
			) {		
			    #$phiTerms{$word}++;
			    if (!(exists $phiTerms{$word})) {
				
				$phiTerms{$word} = 1;}
			    else { 
				
				$phiTerms{$word} = $phiTerms{$word}+ 1; 
			    }


		    } #end if
		}  # end foreach $k (keys %phiT)
            } #end if ($para =~ /\W/)

	    if ($line =~ /\|\|\|\|END_OF_RECORD/ ) {  
	    
		open DEST, ">>".$debug_file or die "Cannot open $debug_file";
		####################################################
		#check for repeated occurences of PHIs for this note
		while ($allallText =~ /\b([A-Za-z]+)\b/g) {
		    my $token = $1;
		    my $start = (length ($`));  #$` is the string preceding what was matched by the last successful match
		    my $end = $start + length($token);

		   if (!(exists    $deids{$start})   ) {
		    #if (!(exists ${@{$deids{$start}}}[0])) {
		      L:
			foreach $word (keys %phiTerms) {
		
			    if ( (uc($token) eq uc($word))  ) {
				
				$deids{$start}[0] = $end;
				$deids{$start}[1] = $currentID;
				$deids{$start}[2] = $noteDate;
				
				$term = substr $text, $start, ($end - $start +1);
				$outstr = "$start \t $end \t $term \t Name (Repeated Occurrence) \n";
				print DEST $outstr;
				
				next L;
			    } #end if
			} # end foreach
		    } # end if
		} # end while
		#end checking for repeated occurences of PHIs
		close DEST;
		#####################################################

		##output PHI locations to the .phi file 
		open OUTF, ">>$output_file" or die "Cannot open $output_file";
		print OUTF "\nPatient $currentID\tNote $currentNote";
		foreach $k (sort numerically keys %deids) { 
		    my @deidvals = @{$deids{$k}};
		    $thisend = $deidvals[0];
		    if ($thisend ){
			print OUTF "\n$k\t$k\t$thisend";
		    }
		}
		close OUTF;

		###output de-ided text to .res file
		if ($comparison==0) {
		    outputText(\%deids, \%phiTT);	
		}

		#now that we have output text for this record, we reset the 
                #variables to get ready for the next record
		$para = "";
		$paraCount = 0;
		$stpos = 0;
		
		%deids=(); #clear the deid hash
		%phiTT=(); #clear the phiTT hash
		%phiT=();


		$allText = "";       #reset, 
		$allallText = "";    #reset

	    } else {  # this is not end of record yet ...
		my $tmp = length($para);
		$stpos += length ($para);
		$para = $line.' ';
	    }

	    	    
	}  #end if line starts with empty spaces || empty line || end of record
	else { # else this line is still a part of the current paragraph 
	    #$para .= ' '.$line;  #just append to end of current paragraph
	    #$para .= $line.' '; #just append to end of current paragraph
	     if ($line eq "") {
		$para .= "\n";
	    } else {
		$para .= $line.' '; #just append to end of current paragraph
	    }
	}
    } #end while ($line=<DF>)
    
    close DF;

}
# End of deid()





#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: findPHI()
# Arguments: string $label ("Para $paraCount"), string $date (e.g. "yyyy-mm-dd"), int $startIndex (normally 0), string $text (paragraph of text)
# Returns: hash %approved (key=start-end of each PHI, value=PHI types)
# Called by: deid()
# Description: Dispatched from deid() to perform de-identification
# Reads in a paragraph of text and runs the de-identification algorithm on it


sub findPHI {
    my ($label, $curr_date, $startIndex, $text) = @_;


    # Initializes the hash %phi which stores PHI locations and their PHI types
    %phi = (); #key = start-end, value = (type1, type2, ...)
    local %end = (); # key = start, value = end (dynamic scope so addType can do it)
    if ($text !~ /\w/) {	
	return %phi;
    } #[wjl] skip blank lines
    
    # Splits the text into separate items at spaces
    #my @txtlst = split (/([^a-zA-Z0-9_\'\-]+)/,$text); # used by lookhash and appx match
    my @txtlst = split (/([^a-zA-Z0-9_\']+)/,$text); 
    
    # Performs exact matching with the hashes of PHI lists
    &lookhash(@txtlst);

    # Initializes hash %phik which stores only start and end indices of each PHI in %phi
    %phik = ();

    foreach $k (keys %phi) {
	($st,$end) = split ('-',$k);
	$phik{$st} = $end;
    }   


    # Calls each filter module

    if ($datefilter =~ /y/) {
	&commonHoliday($text, 0);
	&date ($text, $curr_date);
	&dateWithContextCheck($text, $curr_date);
	&yearWithContextCheck($text, $curr_date);
	&seasonYear ($text, 0);
    }

    if ($telfilter =~ /y/) {
	&telephone($text, 0);
	&pager ($text, 0);
    }

    if ($locfilter =~ /y/) {
	&wardname($text, 0);
	&location1 ($text, 0);
	&location2 ($text, 0);
    }

    if ($emailfilter =~ /y/) {
	&email ($text, 0);
    }

    if ($urlfilter =~ /y/) {
	&url ($text, 0);
    }

    if ($ssnfilter =~ /y/) {	
	&ssn ($text, 0);
    }

    if ($agefilter =~ /y/) {
	&age ($text, 0);
    }

    if ($namefilter =~ /y/) {

	&name1 ($text, 0);
	&name2 ($text, 0);
	&name3 ($text, 0);
	&knownPatientName($text, 0);
	&problem ($text, 0);
	&signatureField ($text, 0);
    }

    if ($unitfilter =~ /y/) {
	&mrn ($text, 0);
	&unit ($text, 0);
	&providerNumber ($text, 0);	
    }


    
    if ($ds_specific_filter =~ /y/){
	#discharge summary specific filters
	#filter not enabled for this version
	#&dischargeSummarySpecific ($text, 0);
    }


    # Call new function here >>>>>>>>>>
    # Follow format shown here if necessary
    # &functionName ($text, 0);

    open DEST, ">>".$debug_file or die "Cannot open $debug_file";
    #print DEST "$label\n";

    # Sub-function: finalPHICheck()
    # After findPHI() has performed most PHI checks, goes through the identified PHI before adding them to the final PHI files
    
    my %approved;
    my ($startp, $endp) = (0, 0);
    my $notAmbig = 0;
    my $stg1 = "";
    my $stg2 = "";
    my $prevAmbig = 0;
    my $oldk = "";
    my $prevKey = "";
    my ($oldstartp, $oldendp,) = (0, 0);
    my $oldtext = "";
    
    # Prunes keys and checks whether each PHI is ambiguous or is an indicator (e.g. hospital indicator)
    foreach $k (&pruneKeys("phi",$text)) {
	($startp, $endp) = split "-", $k;

	my $the_word = (substr $text, $startp, ($endp - $startp));


	$notAmbig = 0;  #so by default, the term is ambiguous
	foreach $tt (@{$phi{$k}}){
	    #if(($tt !~ /ambig/) && ($tt !~ /Indicator/)    ) {
	    if (($tt !~ /ambig/) && ($tt !~ /Indicator/)  && ($tt !~ /MedicalPhrase/)) {
		#so IF the term matches ANY type that's non-ambiguous, THEN set it as non-ambiguous
		$notAmbig = 1; last;}
	}  #end for each

       
	my $notIndicator = 1; #default to be not an indicator
	
	foreach $tt (@{$phi{$k}}){
	    if ($tt =~ /Indicator/) {
		$notIndicator = 0; last;
	    }
	}
	
	$prevText = (substr $text, $oldstartp, ($oldendp - $oldstartp));
	$newText = (substr $text, $startp, ($endp - $startp));
		

	$a = (isType($prevKey, "Male First Name", 1) && ($prevAmbig==1) && (!isCommon($prevText)));
	$b = (isType($k, "Last Name", 1) && ($notAmbig==0) && (!isCommon($newText)));
	

	#if (this is ambig) and (previous is ambig) and ...
	if ((($notAmbig==0) && ($prevAmbig==1) && (isType($prevKey, "Male First Name", 1) || (isType($prevKey, "Female First Name", 1))) && (!isCommon($prevText)) && (!isCommon($newText)) && ($prevText !~ /\./) && isType($k, "Last Name", 1) && (($startp-$oldendp)<3)) ||
	#if (this is not-ambig) and (previous is ambig) and ...
	    (($notAmbig==1) && ($prevAmbig==1) && (isType($prevKey, "Male First Name", 1) || (isType($prevKey, "Female First Name", 1))) && (!isCommon($prevText)) && (!isCommon($newText))  && ($prevText !~ /\./) && isType($k, "Last Name", 1) && (($startp-$oldendp)<3)) ||
	#if (this is not-ambig) and (previous is ambig) and ...
	    (($notAmbig==1) && ($prevAmbig==1) && isType($prevKey, "Last Name", 1) && (!isCommon($prevText)) && (!isCommon($newText))  && ($prevText !~ /\./) && isType($k, "First Name", 1) && (($startp-$oldendp)<3)) ||
	    #commented out on 1/31/07
	    (($notAmbig==0) && ($prevAmbig==0) && (isType($prevKey, "Male First Name", 1) || (isType($prevKey, "Female First Name", 1))) && (!isCommon($prevText)) && (!isCommon($newText))  && ($prevText !~ /\./) && isType($k, "Last Name", 1) && (($startp-$oldendp)<3)) ||

	#if (this is ambig) and (previous is not ambig) and ...
	    (($notAmbig==0) && ($prevAmbig==0) && isType($prevKey, "Last Name", 1) && (!isCommon($prevText)) && (!isCommon($newText))  && ($prevText !~ /\./) && isType($k, "First Name", 1) && (($startp-$oldendp)<3))) {

	    print DEST ($startIndex + $oldstartp)."\t".($startIndex+$oldendp)."\t".(substr $text, $oldstartp, ($oldendp - $oldstartp +1));


	    ###################

	    my $oldtext = $text;
	    my $newKey = ($startIndex + $oldstartp)."-".($startIndex + $oldendp);
	    ###my $text = (substr $text, $oldstartp, ($oldendp - $oldstartp));
	    foreach $tt (@{$phi{$prevKey}}) {
		print DEST "\t$tt";
		push @{$approved{$newKey}}, $tt;}
	    print DEST "\n";
	    print DEST ($startIndex + $startp)."\t".($startIndex+$endp)."\t".(substr $oldtext, $startp, ($endp - $startp +1));
	    
	    my $newKey = ($startIndex + $startp)."-".($startIndex + $endp);
	    ###my $text = (substr $oldtext, $startp, ($endp - $startp));
	    foreach $tt (@{$phi{$k}}) {
		print DEST "\t$tt";
		push @{$approved{$newKey}}, $tt;
	    }
	    print DEST "\n";


	}
	
	# If the PHI is not ambiguous and not an indicator, recognizes it as PHI; add it to PHI file
	elsif ($notAmbig && $notIndicator) {

	    ###################

	    
	    print DEST ($startIndex + $startp)."\t".($startIndex+$endp)."\t".(substr $text, $startp, ($endp - $startp +1));
	    my $newKey = ($startIndex + $startp)."-".($startIndex + $endp);
	    ###my $text = (substr $text, $startp, ($endp - $startp));
	    foreach $tt (@{$phi{$k}}){		
		print DEST "\t$tt";
		if (($tt !~ /ambig/) && ($tt !~ /Indicator/)) {
		    push @{$approved{$newKey}}, $tt;
		}
	    }
	    print DEST "\n";

	} # Else ck keys discarded
	
	else {
	    ###################
	    
	    # Otherwise keeps the remaining PHI as non-PHI
	    print DEST ($startIndex + $startp)."\t".($startIndex+$endp)."\t# ".(substr $text, $startp, ($endp - $startp +1));
	    foreach $tt (@{$phi{$k}}) {
		print DEST "\t$tt";
	    }
	    print DEST "\n";}

	# Sets ambiguous variables for current PHI to be recognized as previous PHI for the next round
	if ($notAmbig==0) {
	    $prevAmbig = 1;
	    $prevKey = $k;
	    ($oldstartp, $oldendp) = split "-", $prevKey;
	    $oldtext = $text;

	}
	else {
	    $prevAmbig = 0;
	}
    }    
    close DEST;

    # End of sub-function finalPHICheck()
    #***********************************************************************************************************


    return %approved;
}
# End of findPHI()



#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: date ()
# Searches for date ranges following formats that appear most frequently in text
sub date {
    #$text = $_[0];    
    my ($text, $date) = @_;
    my $year = substr $date, 0, 4;  
    # Checks if dates should be filtered
    if ($datefilter =~ /y/) {
	
	# Searches for the pattern mm/dd-mm/dd where the items are valid dates
	while ($text =~ /\b((\d\d?)\/(\d\d?)\-(\d\d?)\/(\d\d?))\b/ig) {
	    if (isValidDate($2,$3,-1) && isValidDate($4,$5,-1)) {
		$date_range = $1;
		$start = length($`);
		$end = $start + length($date_range);
		$key = "$start-$end";
		addType($key, "Date range (1)");
	    }
	}		

	# Searches for mm/dd/yy-mm/dd/yy or mm/dd/yyyy-mm/dd/yyyy where the items are valid dates
	while ($text =~ /\b((\d\d?)\/(\d\d?)\/(\d\d|\d\d\d\d)\-(\d\d?)\/(\d\d?)\/(\d\d|\d\d\d\d))\b/ig) {
	    if (isValidDate($2,$3,$4) && isValidDate($5,$6,$7)) {
		$date_range = $1;
		$start = length($`);
		$end = $start + length($date_range);
		$key = "$start-$end";
		addType($key, "Date range (2)");
	    }
	}       
	
	# Searches for mm/dd-mm/dd/yy or mm/dd-mm/dd/yyyy where the items are valid dates
	while ($text =~ /\b((\d\d?)\/(\d\d?)\-(\d\d?)\/(\d\d?)\/(\d\d|\d\d\d\d))\b/ig) {
	    if (isValidDate($6,$2,$3) && isValidDate($6,$4,$5)) {
		$date_range = $1;
		$start = length($`);
		$end = $start + length($date_range);
		$key = "$start-$end";
		addType($key, "Date range (3)");
	    }
	}	
    } #end if date filter is on
    # End of sub-function date1()

    if ($datefilter =~ /y/) {	
	# Checks for month/day/year
	while ($text =~ /\b(\d\d?)[\-\/](\d\d?)[\-\/](\d\d|\d{4})\b/g) {
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $key = $startI."-".$endI;
	    my $first_num = $1;
	    my $second_num = $2;
	    my $third_num = $3;
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;


	    if (($beginr !~ /(\|\|)/) && ($endr !~ /(\|\|)/)) {
		if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%\/]/) && ($endr !~ /\S\d/)) {

		    #print "checking M/D/Y, $first_num, $second_num, $third_num\n";

		    if (isValidDate ($first_num, $second_num, $third_num)) {
			addType ($key, "Month/Day/Year");
		    }
		}
	    }
	} #end while
	
	# Checks for month/day/year
	while ($text =~ /\b(\d\d?)\.(\d\d?)\.(\d\d|\d{4})\b/g) {
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $key = $startI."-".$endI;
	    my $first_num = $1;
	    my $second_num = $2;
	    my $third_num = $3;
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    
	    #print "2. checking M/D/Y, $first_num, $second_num, $third_num\n";

	    if (($beginr !~ /(\|\|)/) && ($endr !~ /(\|\|)/)) {
		if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%\/]/) && ($endr !~ /\S\d/)) {
		    if (isValidDate ($first_num, $second_num, $third_num)) {
			addType ($key, "Month/Day/Year");
		    }
		}
	    }
	}		      

	# Checks for day/month/year
	while ($text =~ /\b(\d\d?)[\-\/](\d\d?)[\-\/](\d\d|\d{4})\b/g){
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $key = $startI."-".$endI;
	    my $first_num = $1;
	    my $second_num = $2;
	    my $third_num = $3;
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    
	    if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%\/]/) && ($endr !~ /\S\d/)) {
		if (isValidDate ($second_num, $first_num, $third_num)) {
		}
	    }
	}
	
	# Checks for year/month/day
	while ($text =~ /\b(\d\d|\d{4})[\-\/](\d\d?)[\-\/](\d\d?)\b/g){
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $key = $startI."-".$endI;
	    my $yr = $1;
	    $nn_year = $yr;
	    my $mo = $2;
	    my $da = $3;
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    
	    
	    if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%\/]/) && ($endr !~ /\S\d/)) {
		if (isValidDate ($mo, $da, $yr) && (($yr>50) || ($yr<6))) {
		    $prevChars = (substr $text, ($startI-4), 4);
		    $nextChars = (substr $text, $endI, 11);
		    if (($prevChars =~ /(\d)(\s)?(\|)(\s)?/) && ($nextChars =~ /\s\d{2}\:\d{2}\:\d{2}(\s)?(\|)/)) {
			addType ($key, "Header Date");
			$longyear = $yr;
		    }
		    else {
			addType ($key, "Year/Month/Day");
		    }
		}
	    }
	} #end while
	
	
	
	# Checks for year/month/day
	while ($text =~ /\b(\d\d|\d{4})\.(\d\d?)\.(\d\d?)\b/g){
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $key = $startI."-".$endI;
	    my $yr = $1;
	    $nn_year = $yr;
	    my $mo = $2;
	    my $da = $3;
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    
	    
	    if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%\/]/) && ($endr !~ /\S\d/)) {
		#if (isValidDate ($mo, $da, $yr) && (($yr>50) || ($yr<6))) {
		if (isValidDate ($mo, $da, $yr)) {
		    $prevChars = (substr $text, ($startI-4), 4);
		    $nextChars = (substr $text, $endI, 11);
		    if (($prevChars =~ /(\d)(\s)?(\|)(\s)?/) && ($nextChars =~ /\s\d{2}\:\d{2}\:\d{2}(\s)?(\|)/)) {
			addType ($key, "Header Date");
			$longyear = $yr;
		    }
		    else {
			addType ($key, "Year/Month/Day");
		    }
		}
	    }
	}
	
	
	
	# Checks for year/day/month
	while ($text =~ /\b(\d\d|\d{4})[\-\/](\d\d?)[\-\/](\d\d?)\b/g){
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $key = $startI."-".$endI;
	    my $yr = $1;
	    $nn_year = $yr;
	    my $mo = $3;
	    my $da = $2;
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    
	    if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%\/]/) && ($endr !~ /\S\d/)) {
		#if (isValidDate ($mo, $da, $yr) && (($yr>50) || ($yr<6))) {
		if (isValidDate ($mo, $da, $yr)) {
		    $prevChars = (substr $text, ($startI-4), 4);
		    $nextChars = (substr $text, $endI, 11);
		    
		    if (($prevChars =~ /(\d)(\s)?(\|)(\s)?/) && ($nextChars =~ /\s\d{2}\:\d{2}\:\d{2}(\s)?(\|)/)) {
			addType ($key, "Header Date");
			$longyear = $yr;
		    }
		    else {
		    }
		}
	    }
	} #end while

	# Checks for month/4-digit year
	while ($text =~ /\b((\d\d?)[\-\/](\d{4}))/g) {
	    my $startI = (length($`));
	    my $endI = $startI + length($&);
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    my $first_num = $2;
	    my $second_num = $3;
	    my $st = length($`);
	    my $endb = $st + length ($2) + length($3) + 1;
	    my $key = "$st-$endb";
	    if (($beginr !~ /\|\|/) && ($endr !~ /\|\|/)) {
		if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /[\/\.\%]/)) {
		    #if (($first_num <= 12) && ($first_num > 0) && ($second_num>=1900)) { 
		    if (($first_num <= 12) && ($first_num > 0) && 
			( $second_num >= $VALID_YEAR_LOW &&  $second_num <= $VALID_YEAR_HIGH  )  ) { 
			addType ($key, "Month/Year 1"); }}} 
	} #end while
	
        # Checks for 4-digit year/month
	while ($text =~ /\b((\d{4})[\-\/](\d\d?))\b/g) {
	    my $first_num = $2;
	    my $second_num = $3;
	    my $st = length($`);
	    my $endb = $st + length ($2) + length($3) + 1;
	    my $key = "$st-$endb";
	    if (($begin !~ /\d[\/\.\-]/) && ($end !~ /[\/\.\%]/)) {
		#if (($second_num <= 12) && ($second_num > 0) && ($first_num>=1900) && ($first_num<2010)) { 
		
		if (($second_num <= 12) && ($second_num > 0) && ($first_num>=$VALID_YEAR_LOW) && ($first_num <= $VALID_YEAR_HIGH)) { 
		    addType ($key, "Year/Month"); }}
	} #end while

    
	# Checks for spelled-out months
	# Accounts for ambiguity around the dates, e.g. acronyms for measurements, spelled out months and such
	foreach $m (@months) {
	    
	    while ($text =~ /\b((\d{1,2})[ \-]?$m[ \-\,]? ?\'?\d{2,4})\b/ig) { # 2-May-04
		my $day = $2;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day < 32) && ($day > 0)) {
		    addType ($key, "Day Month Year");
		}
	    }

	    while ($text =~ /\b((\d{1,2}) ?(\-|to|through)+ ?(\d{1,2})[ \-]?$m[ \-\,]? ?\'?\d{2,4})\b/ig) { # 2-May-04
		my $day1 = $2;
		my $day2 = $4;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) && ($day2 >0)) {
		    addType ($key, "Date range (4)");
		}
	    }
	    
	    while ($text =~ /\b((\d{1,2}) ?\-\> ?(\d{1,2})[ \-]?$m[ \-\,]? ?\'?\d{2,4})\b/ig) { # 2-May-04
		my $day1 = $2;
		my $day2 = $3;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) && ($day2 > 0)) {
		    addType ($key, "Date range (5)");
		}
	    }
	    
	    
	    while ($text =~ /\b($m\b\.? (\d{1,2})[\,\s]+ *\'?\d{2,4})\b/ig) { # Apr. 2 05
	
		my $day = $2;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day < 32) && ($day > 0)) {
		    addType ($key, "Month Day Year");
		}
	    }

	    while ($text =~ /\b($m\b\.? (\d{1,2}) ?(\-|to|through)+ ?(\d{1,2})[\,\s]+ *\'?\d{2,4})\b/ig) { # Apr. 2 05
		my $day1 = $2;
		my $day2 = $4;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) & ($day2 > 0)) {
		    addType ($key, "Date range (6)");
		}
	    }

	    while ($text =~ /\b($m\b\.? (\d{1,2}) ?\-\> ?(\d{1,2})[\,\s]+ *\'?\d{2,4})\b/ig) { # Apr. 2 05
	
		my $day1 = $2;
		my $day2 = $3;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) & ($day2 > 0)) {
		    addType ($key, "Date range (7)");
		}
	    }
	    	    
	    #while ($text =~ /\b($m\b\.?,? ?(\d{1,2})(|st|nd|rd|th|)? ?[\,\s]+ *\'?\d{2,4})\b/ig) { # Apr. 12 2000
	   while ($text =~ /\b($m\b\.?,? ?(\d{1,2})(|st|nd|rd|th|) ?[\,\s]+ *\'?\d{2,4})\b/ig) { # Apr. 12th 2000
		my $day = $2;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day < 32) && ($day > 0)) {
		    addType ($key, "Month Day Year (2)"); 
		    #addType ($key, "Month Day Year");
		}
	    }
	    
	   # while ($text =~ /\b($m\b\.?,? ?(\d{1,2})(|st|nd|rd|th|)?)\b/ig) { # Apr. 12
	    while ($text =~ /\b($m\b\.?,?\s*(\d{1,2})(|st|nd|rd|th|)?)\b/ig) { # Apr. 12
		my $day = $2;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));

		if (($day < 32) && ($day > 0)) {
		    addType ($key, "Month Day");
		}
	    }
	    
	    while ($text =~ /\b($m\b\.?,? ?(\d{1,2})(|st|nd|rd|th|)? ?(\-|to|through)+ ?(\d{1,2})(|st|nd|rd|th|)?)\b/ig) { # Apr. 12
		my $day1 = $2;
		my $day2 = $4;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) && ($day2 > 0)) {
		    addType ($key, "Date range (8)");
		}
	    }
	    
	    while ($text =~ /\b($m\b\.?,? ?(\d{1,2})(|st|nd|rd|th|)? ?\-\> ?(\d{1,2})(|st|nd|rd|th|)?)\b/ig) { # Apr. 12th
		my $day1 = $2;
		my $day2 = $4;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) && ($day2 > 0)) {
		    addType ($key, "Date range (9)");
		}
	    }
	    
	    while ($text =~ /\b((\d{1,2})(|st|nd|rd|th|)?( of)?[ \-]\b$m)\b/ig) { # 12-Apr, or Second of April
		my $day = $2;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day < 32) && ($day > 0)) {
		    addType ($key, "Day Month");
		}
	    }

	    ###
	  #  while ($text =~ /\b((\d{1,2})(|st|nd|rd|th|)?\s+(of)?\s+[\-]\b$m\.?,?)\s*(\d{2,4})\b/ig) { # 12-Apr, or Second of April
while ($text =~ /\b(((\d{1,2})(|st|nd|rd|th|)?\s+(of\s)?[\-]?\b($m)\.?,?)\s+(\d{2,4}))\b/ig) { # 12-Apr, or Second of April
		my $day = $3;
		my $month = $6; 
		my $year = $7;

		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day < 32) && ($day > 0)) {
		    addType ($key, "Day Month Year 2");
		}
	    }
           ###
	    
	    while ($text =~ /\b((\d{1,2})(|st|nd|rd|th|)? ?(\-|to|through)+ ?(\d{1,2})(|st|nd|rd|th|)?( of)?[ \-]\b$m)\b/ig) { # 12-Apr
		my $day1 = $2;
		my $day2 = $5;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) && ($day2 > 0)) {
		    addType ($key, "Date range (10)");
		}
	    }
	    
	    while ($text =~ /\b((\d{1,2})(|st|nd|rd|th|)? ?\-\> ?(\d{1,2})(|st|nd|rd|th|)?( of)?[ \-]\b$m)\b/ig) { # 12-Apr
		my $day1 = $2;
		my $day2 = $5;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		if (($day1 < 32) && ($day1 > 0) && ($day2 < 32) && ($day2 > 0)) {
		    addType ($key, "Date range (11)");
		}
	    }
	    
	    
	    while ($text =~ /\b($m\.?,? ?(of )?\d{2}\d{2}?)\b/ig) { # Apr. 2002
		my $year = $2;
		my $completeDate = $1;
		my $st = length($`);
		my $key = "$st-".($st + length($1));
		addType ($key, "Month Year"); 
	    }
	}
    }   
}
# End of function date()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: age()
# Checks for ages that are >=90 (assuming that no one is over 125 years old, just as a sanity check)
# When ages are spelled-out, assumes that the number will not be over hundred, i.e. highest spelled-out age="hundred"

sub age {
    $text = $_[0];   
    if ($agefilter =~ /y/) {
	
	foreach $i (@age_indicators_suff) {
	    if (($text =~ /\b(ninety)[\s\-]+ *$i\b/ig) || ($text =~ /\b(hundred)[\s\-]+ *$i\b/ig)) {
		my $age = $1;
		my $st = length($`);
		my $key = "$st-".((length $age) + $st);
		addType ($key, "Age over 90");
	    }
	    while ($text =~ /\b(([A-Za-z]+)([\s \-])([A-Za-z]+)) ? *$i\b/ig) {   		  
		foreach $j (@digits) {
		    $first = $2;
		    $second = $4;
		    my $age1 = $1;
		    my $st1 = length($`);
		    my $end1 = (length $age1) + $st1;
		    my $key1 = "$st1-$end1";
		    $st2 = $st1+length($2)+length($3);
		    $end2 = $st2+(length($second));
		    my $key2 = "$st2-$end2";
		    if ((($first=~/\bninety\b/ig) || ($first=~/\bhundred\b/ig)) && (($second=~/\b$digits\b/ig))) {
			addType ($key1, "Age over 90");	    
		    }
		    else {
			if (!(($first=~/\bninety\b/ig) || ($first=~/\bhundred\b/ig))) {
			    if (($second=~/\bninety\b/ig) || ($second=~/\bhundred\b/ig)) {
				addType ($key2, "Age over 90");
			    }
			}
		    }
		}
	    }
	    	    
	    while ($text =~ /\b(\d+) *$i/ig) {    
		my $age = $1;
		my $st = length($`);
		my $key = "$st-".((length $age) + $st);
		if (($age >= 90) && ($age <= 125)) {
		    addType ($key, "Age over 90");
		}
	    }
	}
	
	foreach $i (@age_indicators_pre) {
	    while ($text =~ /\b($i + *)(([A-Za-z]+)([\s \-])([A-Za-z]+))\b/ig) {   		  
		foreach $j (@digits) {
		    $first = $3;
		    $second = $5;
		    my $age1 = $2;
		    my $st1 = length($`)+length($1);
		    my $end1 = (length $age1) + $st1;
		    my $key1 = "$st1-$end1";
		    $st2 = $st1;
		    $end2 = $st2+length($first);
		    my $key2 = "$st2-$end2";
		    if ((($first=~/\bninety\b/ig) || ($first=~/\bhundred\b/ig)) && (($second=~/\b$digits\b/ig) || (length($second)))) {
			addType ($key1, "Age over 90");	    
		    }
		    else {
			if (!(($first=~/\bninety\b/ig) || ($first=~/\bhundred\b/ig))) {
			    if (($second=~/\bninety\b/ig) || ($second=~/\bhundred\b/ig)) {
				addType ($key2, "Age over 90");
			    }
			}
		    }
		}
	    }
	    
	    
	    while ($text =~ /\b($i + *)(\d+)\b/ig) {    
		my $age = $2;
		my $st = length($`)+length($1);
		my $key = "$st-".((length $age) + $st);
		if (($age >= 90) && ($age <= 125)) {
		    addType ($key, "Age over 90");
		}
	    }
	}
    }
}
# End of function age()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: pager()
# Checks for pager numbers 

sub pager {
    $text = $_[0];
    if ($telfilter =~ /y/) {
	foreach $i ("Pager", "Pg", "Pgr", "Page", "Beeper", "Beeper number", "Pager number") {  #removed "P" 

	    while ($text =~ /\b$i[\s\#\:\-\=]*([a-zA-Z]\s+)*[a-zA-Z]*\s*(\d\d\d+)\b/gi) {
		my $num = $2;
		my $end = length($`)+length($&);
		my $key = ($end - (length $num))."-$end";
		addType ($key, "Pager number");
	    }
	    while ($text =~ /\b$i[\s\#\:\-\=]*/gi){
		my $startp = length($`);
                my $endp =  length($`)+length($&);
		#get the next 30 characters
		my $the_chunck = (substr $text, $endp, 30);
                #now look for a 5-digit number
		while ($the_chunck =~ /(\D)(\d{5})(\D)/gi){
		    my $pager_startp = $endp + length($`) + length($1);
		    my $pager_endp = $pager_startp + length($2);	
		    my $key = "$pager_startp-$pager_endp";
		    addType ($key, "Pager number");
		    
		} #end while
	    } #end while
	}
    }
}
# End of function pager()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: email()
# Looks for e-mail addresses

sub email {
    $text = $_[0];   
    if ($emailfilter =~ /y/) {
	while ($text =~ /\b([\w\.]+\w ?@ ?\w+[\.\w+]\.\w{2,3})\b/g) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "E-mail address");
	}
    }
}
# End of function email()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: url()
# Checks for URLs of different types

sub url {
    $text = $_[0];   
    if ($urlfilter =~ /y/) {
	
	while ($text =~ /\bhttps?\:\/\/[\w\.]+\w{2,4}\/\S+\b/gi) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
	while ($text =~ /\bftp\:\/\/[\w\.]+\w{2,4}\/\S+\b/gi) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
	while ($text =~ /\bwww\.[\w\.]+\w{2,4}\/\S+\b/gi) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
	while ($text =~ /\bwww\.[\w\.]+\w{2,4}\b/gi) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
	while ($text =~ /\bweb\.[\w\.]+\w{2,4}\/\S+\b/gi) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
	while ($text =~ /\bweb\.[\w\.]+\w{2,4}\b/gi) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}

	while ($text =~ /\bhttps?\:\/\/[\w\.]+\w{2,4}\b/g) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
	while ($text =~ /\bftp\:\/\/[\w\.]+\w{2,4}\b/g) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "URL");
	}
    }
}
# End of function url()
#***********************************************************************************************************
#***********************************************************************************************************
#*********************************************************************************************************** 
# Function: ssn()
# Checks for social security numbers (SSNs)

sub ssn {
    $text = $_[0];   
     
    if ($ssnfilter =~ /y/) {
	while ($text =~ /\b\d\d\d([- \/]?)\d\d\1\d\d\d\d\b/g) {
	    my $st = length($`);
	    my $key = "$st-".($st+length($&));
	    addType ($key, "Social Security Number");
	}
    }
}
# End of function ssn()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: name1()
# Uses name prefixes to make last names

sub name1 {
    $text = $_[0];   
    if ($namefilter =~ /y/) {

	my @keylst = sort numerically keys %phi;
	my $key;
	for($i=0;$i<$#keylst;$i++){
	    $key = $keylst[$i];
	    if (isType($key, "Last Prefix", 0)){
		($f1,$t1) = split ('-',$key);
		($f2,$t2) = split ('-',$keylst[$i+1]);
		if ($f2 < $t1+3){
		    if (isType($keylst[$i+1], "Last Name", 1)){
			print "Found Last Prefix match, Adding $keylst[$i+1] type for last name!!";
			addType("$f1-$t2","Last Name");
		    }
		}
	    }
	}
	#####################################################	
	# Uses common-sense heuristics to try to find more names
	foreach $i (@name_indicators){
	 
	    #while ($text =~ /\b($i)(s)?( *)(\-|\,|\.|\()?( *)([A-Za-z]+\b)(\s+)(and )?( *)([A-Za-z]+)\b/ig) { 
	    while ($text =~ /\b($i)(s)?( *)(\-|\,|\.|\()?( *)([A-Za-z]+\b)\b/ig) { 

		$potential_name = $6;
    
		$start = length($`)+length($1) + length ($2) + length($3) + length($4) + length($5);
		$end = $start + length($potential_name);
		$key = "$start-$end";
		my $tmpstr = substr $text, $start, $end-$start;
		
		my $tmp = isType($key, "Name",1);
	     

		if (isProbablyName($key, $potential_name)){		
		    addType ($key, "Name (NI)");
		} # end if the first word after the name indicator is a name

		 my $new_start = $end + length($6) + length($7);
		 my $new_end = $new_start + length($8);


	     #########now check the next word
	     my $rest = substr $text, $end+1, 20;
		if (($rest =~ /\b(and )?( *)([A-Za-z]+)\b/ig)){
		    my $new_start = $end + 1 + length($`) + length($1)+length($2);
		    my $new_end = $new_start + length ($3);

		    my $keyAfter = "$new_start-$new_end";
		    my $wordAfter = substr $rest,   (length ($`)+ length($1) + length($2)) , length ($3);
		  

		    if ( !isNameIndicator($wordAfter) && ( (  !isCommon($wordAfter) || 
			((isType($keyAfter, "Name", 1) && isType($keyAfter, "(un)"))  ||
			(isType($keyAfter, "Name", 1) && ($wordAfter =~ /\b(([A-Z])([a-z]+))\b/g)) ||
			(!isCommonest($wordAfter) && isType($keyAfter, "Name", 1)) ||
			(isType($keyAfter, "popular",1)) ) )  ) ) {
	
			if ($rest =! /\b[\d]\b/ig) { #disregard if the rest contains numeric patterns
			    addType ($keyAfter, "Name2 (NI)");
			}
		    }

		    elsif ($1 =~ /and/ig){
			if (! (isCommon($wordAfter) || isNameIndicator($wordAfter))) {
			    addType ($keyAfter, "Name2 (NI)");
			}
		    }
		} #end if rest
	      
		
	    } # end of while

	} #end for each name indicator

	#**********************************************************************************************************
	# Searches for the name pattern LASTNAME, FIRSTNAME
	# First checks if word2 is a firstname 
	# If it is, then if word1 is not a common or commonest word, identifies word1 as a lastname
	while ($text =~ /\b([A-Za-z]+)( ?\, ?)([A-Za-z]+)\b/ig) { 
	    $input1 = $1;
	    $input2 = $3;
	    my $st1 = length($`);
	    my $end1 = $st1 + length($input1);
	    my $key = $key1;
	    my $key1 = "$st1-$end1";
	    my $st2 = $end1+length($2);
	    my $end2 = $st2 + length($input2);
	    my $key = $key2;
	    my $key2 = "$st2-$end2";
	    
	    if ((isType($key2, "Name", 1)) && (isType($key1, "Name (ambig)", 1)) && (!isNameIndicator($input1)) ) {
		addType ($key1, "Last Name (LF)");
		addType ($key2, "First Name1 (LF)");
	    }
	    
	    if ((isType($key1, "Name", 1)) && (isType($key2, "Name (ambig)", 1)) && (!isNameIndicator($input1))  ) {
		addType ($key2, "Last Name (LF)");
		addType ($key1, "First Name2 (LF)");
	    }
	    
	    if (isType($key2, "First Name", 1)) {
		if (   (isType($key1, "Last Name", 1) && (!isCommonest($input1)) &&  (!isNameIndicator($input1))) || 
		       ((!isCommon($input1)) && (!isCommonest($input1)))   ) {
		    addType ($key1, "Last Name (LF)");
		    addType ($key2, "First Name3 (LF)");
		}
	    }	
	}
    }
}
# End of function name1()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: seasonYear()
# Checks for both season and year from patterns like "<season> of? <year>"

sub seasonYear {
    $text = $_[0];   
    
    @seasons = ("winter", "spring", "summer", "autumn", "fall");
    
	foreach $i (@seasons) {	
	    while ($text =~ /\b(($i)(( +)of( +))? ?\,?( ?)\'?(\d{2}|\d{4}))\b/gi) {
		$f2=$2;
		$f3=$3;
		$f6=$6;
		$f7=$7;
		if (length($f7)==4) {
		    if (($f7<=$longyear) && ($f7>1900)) {	
			my $st1 = length($`);
			my $end1 = (length $f2) + $st1;
			my $key1 = "$st1-$end1";
			
			my $st2 = $end1+(length $f3)+(length $f6);
			my $key2 = "$st2-".((length $f7) + $st2);
			addType ($key2, "Year (4 digits)");		
		    }
		}
		else {	    			 
		    my $st1 = length($`);
		    my $end1 = (length $f2) + $st1;
		    my $key1 = "$st1-$end1";
		    
		    my $st2 = $end1+(length $f3)+(length $f6);
		    my $key2 = "$st2-".((length $f7) + $st2);
		    addType ($key2, "Year (4 digits)");	    	    	    
		}
	    }
	}
    
}
# End of function seasonYear()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: name2()
# Checks for more than 1 name following plural drs, drs., doctors, professors, 
# Checks up to 3 names
 
sub name2 {
    $text = $_[0];   
    if ($namefilter =~ /y/) {

    @plural_titles = ("doctors", "drs", "drs\.", "professors");
    
    foreach $p (@plural_titles) {
	while ($text =~ /\b((($p +)([A-Za-z]+) *(and +)?\,? *)([A-Za-z]+) *(and +)?\,? *)([A-Za-z]+)?\b/gi) {  
	    my %names = ();
	    $st3 = length($`);
	    $st4 = $st3+length($3);
	    $end4 = $st4+length($4);
	    $key4 = "$st4-$end4";
	    $st6 = $st3+length($2);
	    $end6 = $st6+length($6);
	    $key6 = "$st6-$end6";
	    $st8 = $st3+length($1);
	    $end8 = $st8+length($8);
	    $key8= "$st8-$end8";
	    $names{$4} = $key4;
	    $names{$6} = $key6;
	    $names{$8} = $key8;
	    foreach $i (keys %names) {
		$val = $names{$i};
		if (length($i)>0) {
		    if (!(isCommonest($i)) || (isType($val, "Name", 1))) {
			#print "addtype, val is $val\n";
			addType ($val, "Name5 (PTitle)");
		    }
		}
	    }
	}
    }




#****************************************************************************************
# Checks for names followed by "MD" or "M.D"
# Checks up to 3 previous words
    while ($text =~ /\b((([A-Za-z\']+) +)?(([A-Za-z])\. +)?([A-Za-z\-\']+)((\, *)|(\s+))(rrt|md|m\.d\.|crt|np|rn|nnp|msw|r\.n\.)(\.|\,)*\b)/ig) {
	
	$name = $1;
	$start = length($`);
	$end = $start + length($name);
	$key = "$start-$end";
	
	$name1 = $3; #if present, would be first name
	$name2 = $4;  #if present, would be initial
	$name3 = $6;  #if present would be last name

	$st1 = length($`);
	$end1 = $st1 + (length $name1);
	$key1 = "$st1-$end1";

	$st2 = $st1 + length($2);
	$end2 = $st2 + (length $name2);
	$key2 = "$st2-$end2";	

	$st3 = length($`) + (length $2) + (length $4);
	$end3 = $st3 + (length $name3);
	$key3 = "$st3-$end3";
	
	if ((!($text =~ /(m\.?d\.?\')/)) && (!($text =~ /(m\.?d\.?s)/))) {
	
	    if (length($name1)>0) {
	        if ((length($name1)==1) || ((length($name1)==2) && ($name1 =~ /\b([A-Za-z])\.+\b/ig))) {   
		    addType($key1, "Name Initial (MD)");
		}	
		else {
		    if (isProbablyName($key1, $name1)) {
			addType($key1,"Name6 (MD)" );
		    }
		}
	    }

	    if (length($name2)>0 && length($name3)>0) {
		if ((length($name2)==1) || ((length($name2)==2) && ($name2 =~ /\b([A-Za-z])\.+\b/ig))) {    
		     #addType($key2, "Name Initial (MD)");
		}	
		else {
		    #if (!(isCommon($name2) && !(isType($key2, "Name", 1)))) {
		    if (isProbablyName($key2, $name2)) {
			addType($key2,"Name7 (MD)" );
		    }
		}
	    }

	    if (length($name3)>0) {
		if ((length($name3)==1) || ((length($name3)==2) && ($name3 =~ /\b([A-Za-z])\.\b/ig))) {  
		    #addType($key3, "Name Initial (MD)");
		}	
		else {
		    if (isProbablyName($key3, $name3)) {	
			
			addType($key3,"Name8 (MD)" );

		    }
		} # end else
	    } #endif
	} #end if text does not have M.D.' or M.D.s
    }


#****************************************************************************************
# Removes PCP name field, leaving "PCP name:" intact, from discharge summaries
# Does not check for name patterns, since these should be caught by the other methods
# Required mainly for unknown names, checks up to 3 words following "PCP Name"
# Follows the pattern seen in discharge summaries, may not work well in nursing notes

    #@name_pre = ("PCP", "physician", "provider", "created by", "name");
    @name_pre = ("PCP", "physician", "provider", "created by");
    
    foreach $l (@name_pre) {
	while ($text =~/\b(($l( +name)?( +is)?\s\s*)([A-Za-z\-]+)((\s*\,*\s*)? *)([A-Za-z\-]+)(((\s*\,*\s*)? *)([A-Za-z\-]+))?)\b/ig) {  
	    my $key1 = $5;
	    my $st1 = length($`)+(length $2);
	    my $end1 = $st1+(length $5);
	    my $keyloc1 = "$st1-$end1";
	    my $key2 = $8;
	    my $st2 = $end1+(length $6);
	    my $end2 = $st2+(length $8);
	    my $keyloc2 = "$st2-$end2";
	    my $key3 = $12;
	    my $st3 = $end2+(length $10);
	    my $end3 = $st3+(length $12);
	    my $keyloc3 = "$st3-$end3";    
	    my %pcp = ();
	    $pcp{$keyloc1} = $key1;
	    $pcp{$keyloc2} = $key2;
	    $pcp{$keyloc3} = $key3;
	    
	    foreach my $keyloc (keys %pcp ) {
		my $val = $pcp{$keyloc};
		if (length($val)>0) {
		    if ((length($val)==1) || ($val =~ /\b([A-Za-z])\.\b/ig)) {    
			addType($keyloc, "Name Initial (PRE)");
		    }	
		    else {
			#if (!(isCommonest($val) && !(isType($keyloc, "Name", 1)))) {
			if (isProbablyName($keyloc, $val)){
			
			    addType($keyloc,"Name9 (PRE)" );
			}
		    }
		}
	    }
	}
		
        #followed by pattern "name is"
	while ($text =~ /\b(($l( +name)?( +is)? ?([\#\:\-\=\.\,])+ *)([A-Za-z\-]+)((\s*\,*\s*)? *)([A-Za-z\-]+)((\s*\,*\s*)? *)([A-Za-z\-]+)?)\b/ig) { 
	    my $key1 = $6;
	    my $st1 = length($`)+(length $2);
	    my $end1 = $st1+(length $6);
	    my $keyloc1 = "$st1-$end1";
	    my $key2 = $9;
	    my $st2 = $end1+(length $7);
	    my $end2 = $st2+(length $9);
	    my $keyloc2 = "$st2-$end2";
	    my $key3 = $12;
	    my $st3 = $end2+(length $10);
	    my $end3 = $st3+(length $12);
	    my $keyloc3 = "$st3-$end3";
	    my %pcp = ();
	    my $firstfound = 0;
	    my $secondfound = 0;
	    $pcp{$keyloc1} = $key1;
	    $pcp{$keyloc2} = $key2;
	    $pcp{$keyloc3} = $key3;
	    $blah = isCommonest($key3);
	    $blah2 = isType($keyloc3, "Name", 1);
	    
	    if (length($key1)>0) {
		if ((length($key1)==1) || ($key1 =~ /\b([A-Za-z])\.\b/ig)) {
		    addType($keyloc1, "Name Initial (NameIs)");
		    $firstfound = 1;
		}
		else {
		    if (isProbablyName($keyloc1, key1)){
			addType($keyloc1,"Name10 (NameIs)" );
			$firstfound = 1;
		    }
		}
	    }
	    if ($firstfound == 1) {
		if (length($key2)>0) {
		    if ((length($key2)==1) || ($key2 =~ /\b([A-Za-z])\.\b/ig)) {
			addType($keyloc2, "Name Initial (NameIs)");
			$secondfound = 1;
		    }
		    else {
			if (isProbablyName($keyloc2, $key2)){
			    addType($keyloc2,"Name11 (NameIs)" );
			    $secondfound = 1;
			}
		    }
		}
	    }
	    if ($secondfound == 1) {
		if (length($key3)>0) {
		    if ((length($key3)==1) || ($key3 =~ /\b([A-Za-z])\.\b/ig)) {
			addType($keyloc3, "Name Initial (NameIs)");
		    }
		    else {
			if (isProbablyName ($keyloc3, $key3)){
			    addType($keyloc3,"Name12 (NameIs)" );
			}
		    }
		}
	    }
	}
    }
}
}
# End of function name2()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: providerNumber()
# Removes "provider number", whole field, from discharge summaries
# Does not remove the field if there is no number following it
 
sub providerNumber {
    $text = $_[0];       
    if ($unitfilter =~ /y/) {
	
	while ($text =~ /\b(provider(( +)number)?( ?)[\#\:\-\=\s\.]?( ?)(\d+)([\/\-\:](\d+))?)\b/gi) {  
	    my $unit = $1;
	    my $st = length($`);
	    my $key = "$st-".((length $unit) + $st);
	    addType ($key, "Provider Number");
	}
    }
}
# End of function providerNumber()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: signatureField()
# Removes signature fields from discharge summaries
# signature field taken as 3 or more underscores
# does not remove doctor names, since these are handled by other name handlers
    
sub signatureField {
    $text = $_[0];   

    while ($text =~ /\b(\_\_+)\b/gi) {
	
	my $sigfield = $1;
	my $st = length($`);
	my $key = "$st-".((length $sigfield) + $st);
	addType ($key, "Signature");
    }
}
# End of function signatureField()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: location1()
# Removes complete street addresses only when including one of the terms in @street_add_suff
 
sub location1 {
    $text = $_[0];    

    if ($locfilter =~ /y/) {
	#check if ambiguous locations are preceded by any of the location indicators,
        #if so, add in PHI list
   	foreach $i (@location_indicators){
	 
	    while ($text =~ /\b($i)(\s+)([A-Za-z]+)\b/ig) { 
		#print "Location Match 1 is $1, 2 is $2, 3 is $3\n";
		my $st = length ($`) +  length ($1) + length ($2);
                my $end = $st + length ($3);
		my $key = "$st-$end";
		my $word = substr $text, $st, ($end-$st);
		#print "word is $word\n";
	       
		if (isType($key, "Location",1)  || (length ($word) > 1 && !(isCommon($word))) ) {	
		    
		    addType ($key, "Location");
		}
	    }
	} #end for each i in location indicators



	#if the company dictionary is loaded, check if any of the ambiguous company names
	#are preceded by the employment indicators
	if ($company_list =~/y/){
	    #print "company list is on\n";
	    foreach $i (@employment_indicators_pre){
		while ($text =~ /\b($i)(\s+)([A-Za-z]+)\b/ig) { 
		    
		    $st = length ($`) +  length ($1) + length ($2);
		    $end = $st + length ($3);
		    $key = "$st-$end";
		    my $word = substr $text, $st, ($end-$st);
		    
		    my $tmp = isCommon($word);
		    

		    if (isType($key, "Company",1)|| (length ($word) > 1 && !(isCommon($word)))  ) {
			#print "adding  $3 key $key as company unambig";
			addType ($key, "Company");
		    }  
		}
	    } #end for each i in location indicators
	}



	#strict address suffix, case-sensitive match, PHI regardless of ambiguity
	foreach $i (@strict_street_add_suff) {	
	    #make it a case-sensitive match for street address suffix
	    while ($text =~ /\b(([0-9]+ +)?(([A-Za-z\.\']+) +)?([A-Za-z\.\']+) +\b$i\.?\b)\b/g) {

		$st = length($`);
		$end = $st + length($1);

		#check next segment for apartment, suite, floor #s
		my $nextSeg = substr $text, $end, 30;
		#print "check nextSeg for apt and sutie #, seg is  $nextSeg\n";
		foreach $k (@apt_indicators){
		    if ($nextSeg =~ /\b($k\.?\#? +[\w]+)\b/gi) {
			$end += length ($`) + length($1);
		    }
		}
		$key = "$st-$end";
		#addType ($key, "Street Address");

		if (length($3) == 0) {
		    if (!isUnambigCommon($5)) {
			addType ($key, "Street Address");
		    }
		}
		elsif (!((isUnambigCommon($4)) && (isUnambigCommon($5)))) {
		    addType($key, "Street Address");
		}
	    } # end while
	} #end foreach
    }#end if

    #Non-strict address suffix, case-insensitive match, PHI if no ambiguity
    if ($locfilter =~ /y/) {
   
    foreach $i (@street_add_suff) {	

        while ($text =~ /\b(([0-9]+) +(([A-Za-z]+) +)?([A-Za-z]+) +$i)\b/gi) {
	    $st = length($`);
	    $end = $st + length($1);
	    $key = "$st-$end";

	    if (length($3) == 0) {
		if (!isUnambigCommon($word)){
		    addType ($key, "Street Address");
		}
	    }
	    elsif ( ! (isUnambigCommon($4) || isUnambigCommon($5))){
		addType($key, "Street Address");
	    }
	}
    }
}
#****************************************************************************************
    # Removes 2-word location PHI ending with @loc_indicators_suff or preceded by @loc_indicators_pre

    # Words potentially PHI
    if ($locfilter =~ /y/) {
	
	foreach $i (@loc_indicators_suff) {
	    while ($text =~ /\b(([A-Za-z\-]+)? +)?(([A-Za-z\-]+) + *$i +)\b/ig) {
		if (!isCommon($4)) {		
		    $st2 = length($`)+length($1);
		    $end2 = $st2 + length($3);
		    $key2 = "$st2-$end2";
		    addType ($key2, "Location");
		    
		    if (length $2>0) {
			if (!isCommon($2)) {
			    $st1 = length($`);
			    $end1 = $st1 + length($2);
			    $key1 = "$st1-$end1";
			    addType ($key1, "Location");}
		    }
		    
		}
	    }	
	}
    }
    if ($locfilter =~ /y/) {
	
	# Words most likely PHI
	foreach $i (@loc_ind_suff_c) {
	    
	    while ($text =~ /\b(([A-Za-z]+ +)?)(([A-Za-z]+)$i+)\b/ig) {
		if (!isCommon($3)) {		
		    $st2 = length($`)+length($1);
		    $end2 = $st2 + length($3);
		    $key2 = "$st2-$end2";
		    addType ($key2, "Location");
		}
	    }
	}
    }
    
    if ($locfilter =~ /y/) {
	
	# Words potentially PHI
	foreach $i (@loc_indicators_pre) {
	    while ($text =~ /\b((($i + *([A-Za-z\-]+)) *)([A-Za-z\-]+)?)\b/ig) {
		if (!isCommon($4)) {		
		    $st2 = length($`);
		    $end2 = $st2 + length($3);
		    $key2 = "$st2-$end2";
		    addType ($key2, "Location");
		    
		    if (length $5>0) {
			if (!isCommon($5)) {
			    $st1 = length($`)+length($2);
			    $end1 = $st1 + length($5);
			    $key1 = "$st1-$end1";
			    addType ($key1, "Location");
			}
		    }				
		}
	    }
	}
    } # end if locfilter =~ /y/


    @universities_pre = ("University", "U", "Univ", "Univ.");

    #catches "University of", "U of", "Univ of", "Univ. of" 
    if ($locfilter =~ /y/) {
	
	# Words potentially PHI
	foreach $i (@universities_pre) {
	    while ($text =~ /\b((($i +of *([A-Za-z\-]+)) *)([A-Za-z\-]+)?)\b/ig) {
		my $tmp = isUSStateAbbre($4);

		if (isUSStateAbbre($4) || isUSState($4) ||  !isCommon($4) ) {		
		    $st2 = length($`);
		    $end2 = $st2 + length($3);
		    $key2 = "$st2-$end2";
		    addType ($key2, "Location");
		    
		    if (length $5>0) {
			if (!isCommon($5)) {
			    $st1 = length($`)+length($2);
			    $end1 = $st1 + length($5);
			    $key1 = "$st1-$end1";
			    addType ($key1, "Location (Universities)");
			}
		    }				
		}
	    }
	}
    } # end if locfilter =~ /y/

   

}
# End of function location1()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: location2()
# Searches for multiple hospital and location terms

sub location2 {
    $text = $_[0];
    if ($locfilter =~ /y/) {
	
	foreach $hos (@hospital) {
	    
	    my @hospital_terms = split " ", $hos;
	    $len = 0;
	    foreach $h (@hospital_terms) {
		if (length($h) != 0) {
		    $len = $len+1;
		    $hos[$len] = $h;
		}
	    }
	    
	    if ($len == 1) {
		while ($text =~ /\b($hos[1])\b/ig) {
		    $hospital = $1;
		    $st = length($`);
		    $end = $st + length($hospital);
		    $key = "$st-$end";
		    addType($key, "Hospital1");	   
		}
	    }
	    
	    if ($len == 2) {
		while ($text =~ /\b($hos[1])( )($hos[2])\b/ig) {
		    
		    $hos1 = $1;
		    $hos2 = $3;
		    $space = $2;
		    $st1 = length($`);
		    $end1 = $st1 + length($hos1);
		    $key1 = "$st1-$end1";
		    addType($key1, "Hospital2");
		    $st2 = $end1 + length($space);
		    $end2 = $st2 + length($hos2);
		    $key2 = "$st2-$end2";
		    addType($key2, "Hospital3");	   
		}
	    }
	    
	    if ($len == 3) {
		while ($text =~ /\b($hos[1])( )($hos[2])( )($hos[3])\b/ig) {
		    $hos1 = $1;
		    $hos2 = $3;
		    $hos3 = $5;
		    $st1 = length($`);
		    $end1 = $st1 + length($hos1);
		    $key1 = "$st1-$end1";
		    addType($key1, "Hospital4");
		    $st2 = $end1 + length($2);
		    $end2 = $st2 + length($hos2);
		    $key2 = "$st2-$end2";
		    addType($key2, "Hospital5");
		    $st3 = $end2 + length($4);
		    $end3 = $st3 + length($hos3);
		    $key3 = "$st3-$end3";
		    addType($key3, "Hospital6");
		}
	    }
	    	    	    
	    if ($len == 4) {
		while ($text =~ /\b($hos[1])( )($hos[2])( )($hos[3])( )($hos[4])\b/ig) {
		    $hos1 = $1;
		    $hos2 = $3;
		    $hos3 = $5;	    
		    $st1 = length($`);
		    $end1 = $st1 + length($hos1);
		    $key1 = "$st1-$end1";
		    addType($key1, "Hospital");
		    $st2 = $end1 + length($2);
		    $end2 = $st2 + length($hos2);
		    $key2 = "$st2-$end2";
		    addType($key2, "Hospital");
		    $st3 = $end2 + length($4);
		    $end3 = $st3 + length($hos3);
		    $key3 = "$st3-$end3";
		    addType($key3, "Hospital");
		    $st4 = $end3 + length($6);
		    $end4 = $st4 + length($hos4);
		    $key4 = "$st4-$end4";
		    addType($key4, "Hospital");
		}
	    }	    	
	}
		
	foreach $loc (@loc_unambig) {
	    
	    my @loc_terms = split " ", $loc;
	    $len = 0;
	    foreach $h (@loc_terms) {
		if (length($h) != 0) {
		    $len = $len+1;
		    $loc[$len] = $h;
		}
	    }
	    
	    if ($len == 1) {
		while ($text =~ /\b($loc[1])\b/ig) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "Location");	   
		}
	    }
	    
	    if ($len == 2) {
		while ($text =~ /\b($loc[1])( )($loc[2])\b/ig) {
		    $loc1 = $1;
		    $loc2 = $3;
		    $st1 = length($`);
		    $end1 = $st1 + length($loc1);
		    $key1 = "$st1-$end1";
		    addType($key1, "Location");
		    $st2 = $end1 + length($2);
		    $end2 = $st2 + length($loc2);
		    $key2 = "$st2-$end2";
		    addType($key2, "Location");	   
		}
	    }
	    
	    if ($len == 3) {
		while ($text =~ /\b($loc[1])( )($loc[2])( )($loc[3])\b/ig) {
		    $loc1 = $1;
		    $loc2 = $3;
		    $loc3 = $5;
		    $st1 = length($`);
		    $end1 = $st1 + length($loc1);
		    $key1 = "$st1-$end1";
		    addType($key1, "Location");
		    $st2 = $end1 + length($2);
		    $end2 = $st2 + length($loc2);
		    $key2 = "$st2-$end2";
		    addType($key2, "Location");
		    $st3 = $end2 + length($4);
		    $end3 = $st3 + length($loc3);
		    $key3 = "$st3-$end3";
		    addType($key3, "Location");
		}
	    }
	    	   	    
	    if ($len == 4) {
		while ($text =~ /\b($loc[1])( )($loc[2])( )($loc[3])( )($loc[4])\b/ig) {
		    $loc1 = $1;
		    $loc2 = $3;
		    $loc3 = $5;	    
		    $st1 = length($`);
		    $end1 = $st1 + length($loc1);
		    $key1 = "$st1-$end1";
		    addType($key1, "Location");
		    $st2 = $end1 + length($2);
		    $end2 = $st2 + length($loc2);
		    $key2 = "$st2-$end2";
		    addType($key2, "Location");
		    $st3 = $end2 + length($4);
		    $end3 = $st3 + length($loc3);
		    $key3 = "$st3-$end3";
		    addType($key3, "Location");
		    $st4 = $end3 + length($6);
		    $end4 = $st4 + length($loc4);
		    $key4 = "$st4-$end4";
		    addType($key4, "Location");
		}
	    }
	}

        #######
        #PO Box number
	
        while ($text =~ /\b(P[\.]?O[\.]? *Box *[\#]? *[0-9]+)\b/gi) {
	      $location = $1;
	      $st = length($`);
	      $end = $st + length($location);
	      $key = "$st-$end";
	      addType($key, "PO Box");	  
	}

	



        ######
        #Zipcodes 
	foreach $loc (@us_states_abbre) {
	    	while ($text =~ /\b($loc *[\.\,]*\s*\d{5}[\-]?[0-9]*)\b/gi) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State/Zipcode");	  
		}

	}

        #Zipcodes with more US states abbreviations
	foreach $loc (@more_us_states_abbre) {
	    	while ($text =~ /\b($loc *[\.\,]*\s*\d{5}[\-]?[0-9]*)\b/gi) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State/Zipcode");	  
		}

	}      
	#Zipcodes with full US state names
	foreach $loc (@us_states) {
	    	while ($text =~ /\b($loc *[\.\,]*\s*\d{5}[\-]?[0-9]*)\b/gi) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State/Zipcode");	  
		}

	}
        ##########
        #remove US states if filter flag for State is on

	if ($us_state_filter =~ /y/) {

  	  foreach $loc (@us_states) {
	    
	    my @loc_terms = split " ", $loc;
	    $len = 0;
	    foreach $h (@loc_terms) {
		if (length($h) != 0) {
		    $len = $len+1;
		    $loc[$len] = $h;
		}
	    }
	    
	    if ($len == 1) {
		while ($text =~ /\b($loc[1])\b/ig) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State");	   
		}
	    }
	    
	    if ($len == 2) {
		while ($text =~ /\b(($loc[1])( )($loc[2]))\b/ig) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State");	      
		}
	    }
	    
	    if ($len == 3) {
		while ($text =~ /\b(($loc[1])( )($loc[2])( )($loc[3]))\b/ig) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State");	
		}
	    }
	    	   	    
	    if ($len == 4) {
		while ($text =~ /\b(($loc[1])( )($loc[2])( )($loc[3])( )($loc[4]))\b/ig) {
		    $location = $1;
		    $st = length($`);
		    $end = $st + length($location);
		    $key = "$st-$end";
		    addType($key, "State");
		    
		}
	    }
	}
      } #end if us_state_filter is on








        #######
	# Sub-function: hospitalIndicators()
	# Searches for hospital indicators and checks if previous and following words are hospitals
	
	foreach $h (@hospital_indicators) {

	    while ($text =~ /((([A-Za-z\-\']+)( + *))?(([A-Za-z\-\']+)( + *))?($h\b)(( + *)([A-Za-z\-\']+))?(( + *)([A-Za-z\-\']+))?\b)/ig) {  

		
		my $typeadded = 0;
		$st1 = length($`);
		$end1 = $st1 + length($3);
		$key1 = "$st1-$end1";
		$st2 = $st1 + length($2);
		$end2 = $st2 + length($6);
		$key2 = "$st2-$end2";
		$st3 = $st1 + length($2) + length ($5) + length($8) + length($10);
		$end3 = $st3 + length($11);
		$key3 = "$st3-$end3";
		$st4 = $end3 + length($13);
		$end4 = $st4 + length($14);
		$key4 = "$st4-$end4";
		$st5 = $end2 + length($7);
		$end5 = $st5 + length($8);
		$key5 = "$st5-$end5";

		
		if (length($5)==0) {
		
		    if ((length($3) > 1) &&  (!isUnambigCommon($3)) && (!(isCommon ($3)) || (isType ($key1, "Hospital", 1)))) {
			addType ($key1, "Hospital");
			#addType ($key5, "Hospital-Ind");
			$typeadded = 1;
		    }
		} 

		 elsif ((length($6) > 1) && (!isUnambigCommon($6)) && (!(isCommon ($6)) || isUSState($6) || isUSStateAbbre($6) || (isType ($key2, "Hospital", 1)))) { 
	
		    addType ($key2, "Hospital");
                    #addType ($key5, "Hospital-Ind");
		    $typeadded = 1;
		    
		    if ((length($3) > 1) &&  (!isUnambigCommon($3)) &&  (!(isCommon ($3)) || isUSState($3) || isUSStateAbbre($3) || (isType ($key1, "Hospital", 1)))) {
			addType ($key1, "Hospital");
			#addType ($key5, "Hospital-Ind");
			$typeadded = 1;
		    }
		}

		#	#Generating too many false positives. 
		#	#Need a better common word dictionary to enable this.
		#if ($typeadded == 0) {
		#    if ((length($11) > 1) && (!(isCommonest ($11)) || (isType ($key3, "Hospital", 1)))) {
		#	#addType ($key3, "Hospital"); 
                #       #addType ($key5, "Hospital-Ind");
		#	#if ((length($14) > 1) && (!(isCommonest ($14)) || (isType ($key4, "Hospital", 1)))) {
		#	#      # addType ($key4, "Hospital");
		#	#	    #addType ($key5, "Hospital-Ind");			
		#	#	}
		#    }
		#} #end if (typeadded == 0)
	    }
	}
    }
}
# End of function location2()


#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: problem()
# Checks for names preceded by "problem", pattern found in discharge summaries

sub problem {
    $text = $_[0];   

    $k = "problem";
    $l = ":";
    while ($text =~ /\b(([A-Za-z\-]+) + *($k))\b/ig) {
	if ((!isCommon($2)) || (isNameAmbig($2))) {
	    $st = length($`);
	    $end = $st + length($2);
	    $key = "$st-$end";    
	    addType ($key, "Last Name");
	}
    }
}
# End of function problem()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: mrn()
# Checks for medical record numbers, i.e. numbers preceded by "mrn" or "medical record number"
 
sub mrn {
    $text = $_[0];      
    if ($unitfilter =~ /y/) {
	
	while ($text =~ /\b(mrn( *)[\#\:\-\=\s\.]?( *)(\t*)( *)(\d+)([\/\-\:](\d+))?)\b/gi) {
	    my $unit = $1;
	    my $st = length($`);
	    my $key = "$st-".((length $unit) + $st);
	    addType ($key, "Medical Record Number");
	}
	
	@numbers = ("number", "no", "num", "");
	
	foreach $i (@numbers) {
	    while ($text =~ /\b(medical record( *)$i?( *)[\#\:\-\=\s\.]?( *)(\t*)( *)(\d+)([\/\-\:](\d+))?)\b/gi) {
		my $unit = $1;
		my $st = length($`);
		my $key = "$st-".((length $unit) + $st);
		addType ($key, "Medical Record Number");
	    }
	}
    }
}
# End of function mrn()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: unit()
# Checks for unit numbers in discharge summaries
# Removes the entire field of "unit <number>" or unit <number>/<number>
# If "unit" is not followed by a number, does not remove it

sub unit {
    $text = $_[0];       
    if ($unitfilter =~ /y/) {
	
	@numbers = ("number", "no", "num", "");
	
	foreach $i (@numbers) {
	    while ($text =~ /\b(unit( ?)$i?( *)[\#\:\-\=\s\.]?( *)(\t*)( *)(\d+)([\/\-\:](\d+))?)\b/gi) {
		my $unit = $1;
		my $st = length($`);
		my $key = "$st-".((length $unit) + $st);
		addType ($key, "Unit Number");
	    }
	}
    }
}
# End of function unit()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: name3()
# Checks every lastnameprefix
# If the following word is either a name or not commonest, identifies it as lastname

sub name3 {
    $text = $_[0];   
    if ($namefilter =~ /y/) {

    foreach $line (@prefixes_unambig) {
	while ($text =~ /\b(($line)([\s\'\-])+ *)([A-Za-z]+)\b/ig) { 
	    my $pre = $2;
	    my $prestart = length($`);
	    my $preend = $prestart+(length $pre);
	    my $prekey = "$prestart-$preend";
	    my $lname = $4;
	    my $lstart = $prestart+length($1);
	    my $lend = $lstart+length($4);
	    my $lnamekey = "$lstart-$lend";
	    if ((!(isCommonest ($lname))) || (isType ($lnamekey, "Name", 1))) {
		addType ($prekey, "Name Prefix (Prefixes)");
		addType ($lnamekey, "Last Name (Prefixes)");
	    }
	}
    }
       #****************************************************************************************
	
	@specific_titles = ("MR", "MISTER", "MS");
	foreach $i (@specific_titles) {
	    
	    while ($text =~ /\b($i\.( *))([A-Za-z\'\-]+)\b/ig) { 
		$potential_name = $3;
		$start = length($`)+length($1);
		$end = $start + length($potential_name);
		$key = "$start-$end";
		if (isType($key, "Name", 1)) {
		    addType ($key, "Name13 (STitle)");
		}
		
		elsif (!(isCommon($potential_name))) {
		    addType ($key, "Name14 (STitle)");
		}
	    }
	}
        #****************************************************************************************
	# Goes through word by word looking for unspotted names
	# All words have already been marked as potential names (where appropriate) by the previous routines
	# Looks for last names following titles (Dr. Smith)
	# Also should pick up "Dr. S"
	# Looks for the last name prefixes
	
	foreach $i (@strict_titles) {		
	  L:
 
	    while ($text =~ /\b($i\b\.? *)([A-Za-z\'\-]+)\b/ig) { # added ' - 

 		my $tt = $1;
       		my $word = $2;
			
		my $st = length($`) + length($1);
		my $fi = $st + length($2);
		my $key = "$st-$fi";
		if (exists $prefixes{uc($word)}) {
	
		    addType ($key, "Last Name (STitle)");
		    my $start = $fi;
		    my $nextWord = substr $text, $start;

		    if ($nextWord =~ /\A( ?)(\')?( ?)([A-Za-z]+)\b/g) { 
		    
			my $token = $4;
			my $lstart = $start+length($1)+length($2)+length($3);
			my $lend = $lstart+length($4);
			my $fi += length($1)+length($4);
			if (exists $prefixes{uc($token)}){
			    addType ("$start-$fi", "Last Name (STitle)");
			    my $start = $fi;
			    my $nextWord = $nextWord;
			    my $token = $token;
			    if ($nextWord =~ /\A( ?$token( ?))([A-Za-z]+)\b/g) { 
				$word = $3;
				$key = "$fi-".($fi + length($2) + length($3));
			    } else {
				next L;
			    }
			} 
			else {
			    # Has already identified one prefix, should now check to see if next word is name or is not commonest	
			    $word = $token;
			    $key = "$lstart-$lend";
			
			    if (isProbablyName($key, $word)){  				
				addType ($key, "Last Name (STitle)");
			    }
			}
		    } else {
			next L;
		    }
		} else { #else $word is not a prefix

		    if ($word =~ /\'([A-Za-z]+)/) { 
			$word = $1;
			$st--;
			$key = $st."-".$fi;
		    }
		    if ($word =~ /([A-Za-z]+)\'/) { 
			$word = $1;
			$key =  $st."-".($fi-1);	
		    }
		}
		

		###########################################################
		if (exists $phi{$key}) {
		
		    addType($key, "Last Name (STitle)");
		    if ((isType($key, "First Name", 1))) {
		
		       addType($key, "First Name (STitle)");
		    }
		} else {
		    if (isProbablyName($key, $word)){ 
			addType ($key, "Last Name (STitle)"); 
		
		    }
		    else {
			addType ($key, "Last Name (STitle)"); 

		    }
		} #end else (!exists $phi{$key})



		################################
                #added to catch Dr. <firstname> <lastname> 
		#check the word after $word
		my ($tmpStart,$tmpEnd) = split '-', $key; 
		my $following = substr $text, $tmpEnd;

		if($following =~/\A(\s+)([A-Za-z\-\']{2,})\b/g){
		    my $fword = $2;
		    my $newst = $tmpEnd + (length ($1));
		    my $nextKey = "$newst-".($newst + length($2));
	
		    if (isProbablyName($nextKey, $fword)){
			addType($nextKey, "Name (STitle)");
		    }
		}
		##########################################

	    } #end while text matches the pattern
	}  #end for each $i strict_titles



        #****************************************************************************************
	# Goes through word by word looking for unspotted names
	# All words have already been marked as potential names (where appropriate) by the previous routines
	# Looks for last names following titles (Dr. Smith)
	# Also should pick up "Dr. S"
	# Looks for the last name prefixes
	
        #mark as ambiguous if common words 
	foreach $i (@titles) {		
	  L:
	    while ($text =~ /\b($i\b\.? ?)([A-Za-z]+) *([A-Za-z]+)?\b/ig) {
	
		my $tt = $1;
		my $word = $2;		
		my $st = length($`) + length($1);
		my $fi = $st + length($2);
		my $key = "$st-$fi";

		my $wordAfter = $3; ##added to catch last names
		my $stAfter = $fi + 1;
		my $fiAfter = $stAfter + length ($3);
	        my $keyAfter = "$stAfter-$fiAfter";
		

		if (exists $prefixes{uc($word)}) {	
		    
		    addType ($key, "Last Name (Titles)");
		    my $start = $fi;
		    my $nextWord = substr $text, $start;
		    if ($nextWord =~ /\A( ?)(\')?( ?)([A-Za-z]+)\b/g) {
			my $token = $4;
			my $lstart = $start+length($1)+length($2)+length($3);
			my $lend = $lstart+length($4);
			my $fi += length($1)+length($4);
			if (exists $prefixes{uc($token)}){
			    addType ("$start-$fi", "Last Name (Titles)");
			    my $start = $fi;
			    my $nextWord = $nextWord;
			    my $token = $token;
			    if ($nextWord =~ /\A( ?$token( ?))([A-Za-z]+)\b/g) { 
				$word = $3;
				$key = "$fi-".($fi + length($2) + length($3));
			    } else {
				next L;
			    }
			} 
			else {
			    # Has already identified one prefix, should now check to see if next word is name or is not commonest	
			    $word = $token;
			    $key = "$lstart-$lend";

			    if (isProbablyName($key, $word) && length($word) > 1 ){ 

				addType ($key, "Last Name (Titles)");
			    }
			}
		    } else {
			next L;
		    }
		} else {
		    if ($word =~ /\'([A-Za-z]+)/) {
			$word = $1;
			$st--;
			$key = $st."-".$fi;
		    }
		    if ($word =~ /([A-Za-z]+)\'/) {
			$word = $1;
			$key =  $st."-".($fi-1);
		    }
		}
		
	        if (length ($wordAfter) > 1) {

		    my $tmp = isCommon($wordAfter);
		    if (!isCommonest($wordAfter)  ||  (isType($keyAfter, "Name", 1) && isType($keyAfter, "(un)"))  ||
			    (isType($keyAfter, "Name", 1) && ($wordAfter =~ /\b(([A-Z])([a-z]+))\b/g)) ) {
			
			addType($keyAfter, "Last Name (Titles)");
			addType($key, "First Name (Titles)");
		    }  
		} 

		elsif (exists $phi{$key}) {
		    if ((isType($key, "Name", 1))) {
			addType($key, "Last Name (Titles)");
		    }
		} else {
		    if ( length($word)  > 1 && !(isCommon($word)) ) { 
			addType ($key, "Last Name (Titles)"); 
		    }
		    else {
			if (($word =~ /\b[A-Z][a-z]+\b/) || ($tt =~ /$i\. /)) {
		      
			    addType ($key, "Last Name (Titles  ambig)");
			    
			} else {
			    addType ($key, "Last Name (Titles ambig)"); 
			}
		    }
		}
	    }
	}

    

    
        #****************************************************************************************
	# Implements simple rules for finding names that aren't in the list or are ambiguous...
	# first name + last name -> first name + last name (ambig), first name + 
        #not-on-any-safe-word-list, else save the second word and see whether it appears 
        #in the patient text not associated with the first name or any other name indicator
	# Also first + initial + last name
	# Finds each prefix, labels the next not uncommonest word     
	# Finds all first names (unambig), look at following word -> make last name unambigs
	
	foreach $k (keys %phi) {
	   if (((isType($k, "Male First Name", 1)) || (isType($k, "Female First Name", 1))) && ((isType($k, "(un)", 1)) || (isType($k, "pop", 1)))) {	    
	
	    my ($start, $end) = split '-', $k;
		my $following = substr $text, $end;
		
		# No middle initial
	       
		if ($following =~ /\A( +)([A-Za-z\']{2,})\b/g) { #added to catch firstname s.a. O'Connell
		    my $fword = $2;
		    my $st = $end + (length $1);
		    my $nextKey = "$st-".($st + length($2));

		    if (exists $phi{$nextKey}) {

			if ((isType($nextKey, "Name", 1) == 1) && isProbablyName($nextKey, $fword)) {    
			    addType($nextKey, "Last Name (NamePattern1)");
			    addType($k,"First Name4 (NamePattern1)"); # make it unambig
			}
		    } 
		    else {
			if (isProbablyName($nextKey, $fword)){
			  
			    addType ($nextKey, "Last Name (NamePattern1)");
			    addType($k,"First Name5 (NamePattern1)"); }}}# make it unambig
				
				# Looks for that middle initial
				if ($following =~ /\A( +)([A-Za-z])(\.? )([A-Za-z\-][A-Za-z\-]+)\b/g) {
				    my $initial = $2;
				    my $lastN = $4;
				    my $st = $end + (length $1);
				    my $iniKey = "$st-".($st+1);
				    my $stn = $st + (length $2) + (length $3);
				    my $nextKey = "$stn-".($stn + (length $4));
				    if (exists $phi{$nextKey}) {
					if ((isType($nextKey, "Last Name", 0) == 0)) {
					    addType($nextKey, "Last Name (NamePattern1)");
					    addType($iniKey, "Initial (NamePattern1)");
					    addType($k,"First Name11 (Name Pattern1)");
					}
				    } 
				    else {	       
					if ($following =~ /\A( +)([A-Za-z])(\.? )([A-Za-z][A-Za-z]+)\b\s*\Z/g){ 
					    addType ($nextKey, "Last Name (NamePattern1)");
					    addType($iniKey, "Initial (NamePattern1)");
					    addType($k,"First Name6 (NamePattern1)"); 
					} 
					elsif (!(isCommonest($lastN))) {
					    addType ($nextKey, "Last Name (NamePattern1)");
					    addType($iniKey, "Initial (NamePattern1)");
					    addType($k,"First Name7 (NamePattern1)"); 
					}
				    }
				}
	    }
	}
	
	# Finds all last names (unambig), looks at proceeding word -> make first names unambigs
	foreach $k (keys %phi) {
	    if (isType($k, "Last Name", 1) && (isType($k, "(un)", 1))) {
		
		my ($start, $end) = split '-', $k;
		my $preceding = substr $text, 0, $start;
		
		if ($preceding =~ /\b([A-Za-z]+)( *)\Z/g) {  
		    my $pword = $1;
		    my $st = length($`);
		    my $prevKey = "$st-".($st + (length $1));
		    if (exists $phi{$prevKey}) {
			#my $result = isNameIndicator($pword);
			#print "pword is $pword, isNameIndicator returns $result";
			#if ((isType($prevKey, "First Name", 1)) && (!isType($prevKey, "Name Indicator", 0))) {
			if ((isType($prevKey, "First Name", 1)) && (!isNameIndicator($pword)) ) {
			    addType($prevKey, "First Name8 (NamePattern2)");
			} # Else it's been positively identified as something that is not a name so leave it
		    } 
		    else {
			# Sees whether it appears in the common words... 
			if (!(isCommon($pword))) {
			    
			    addType ($prevKey, "First Name9 (NamePattern2)");
			}
		    }
		}
	    }
	}   
        #****************************************************************************************
	# Looks for compound last names -> last name + last name (ambig), last name + not-on-any-safe-word-list, last name "-" another word
	# Last name with an ambiguous name preceding it has already labeled the preceding thing a first name; no huge loss if it's just a weird first part of a compound last name
	
	foreach $k (keys %phi) {
	    if (isType($k, "Last Name", 0)) {
		
		my ($start, $end) = split '-', $k;
		my $following = substr $text, $end;
		
		if ($following =~ /\A-([A-Za-z]+)\b/g) { #hypen-ated last name 
		    my $newend = $end+length($1)+1;
		    my $nextKey = "$end-$newend";
		    addType ($nextKey, "Last Name (NamePattern3)");
		}
		if ($following =~ /\A( *)([A-Za-z]+)\b/g) { 
		    my $fword = $2;
		my $st = $end + (length $1);
		    my $nextKey = "$st-".($st + length($2));
		    if (exists $phi{$nextKey}) {
		    if (!(isType($nextKey, "ambig", 1))) {
			if (isType($nextKey, "Last Name", 0) == 0) {
			    addType($nextKey, "Last Name (NamePattern3)");
			}
		    } # Else it's been positively identified as something that is not a name so leaves it
		} 
		    else {
			# Sees whether it appears in the common words
			if (!(isCommon($fword))) {
			    addType ($nextKey, "Last Name (NamePattern3)");
			}
		    }
		}
	    }
	}
       #****************************************************************************************
	# Looks for initials
	# Many last names get classified as first names and other PHI -> looks for initial before all unambig names and locations
	
      INI:
	foreach $k (keys %phi) {
	    if (  ((!(isType($k, "ambig", 1))) ||    isType($k, "(un)",1))   && (isType($k, "Name", 1))) {
	    #if (isType($k, "Name", 1)) {	
		my ($start, $end) = split '-', $k;
		my $preceding = substr $text, 0, $start;
		
		# Checks for two initials
	
	   	if ($preceding =~ /\b([A-Za-z][\. ] ?[A-Za-z]\.?) ?\Z/g) {		    
		    my $key = (length ($`))."-".(length($`) + (length $1));
		    addType ($key, "Initials (NamePattern4)");
		    if (!(isType($k, "Last Name", 0))) {
		    }
		}
		
		# Checks if preceding word is an initial
		elsif ($preceding =~ /\b([A-Za-z]\.?) ?\Z/g) { #1 initial
		
		    my $tmp = substr $text, $start, $end - $start +1;
		
		    my $init = $1;
		    my $key = (length ($`))."-".(length($`) + (length $1));
		    if (lc($init) eq "s") { 
			if ((substr $preceding, (length($`) - 1), 1) eq "'") {  #for 's
#			next INI;
			} 
		    }
		    if ((lc($init) eq "a") || (lc($init) eq "i")) {
			if (isCommon(substr $text, $start, ($end - $start))) {
#			next INI;
			}
		    }
		
		    if (length($init)==2 || length($init)==1) {
			addType ($key, "Initials (NamePattern4)");
		    }
		    if (!(isType($k, "Last Name", 0))) {
			addType ($k, "Last Name (NamePattern4)");
		    }
		}	    
	    }
	}
       #****************************************************************************************
       # Looks for initials; similar to previous code block
	
	foreach $k (keys %phi) {
	    if (isType($k, "Last Name", 1) && (!isType ($k, "ambig", 1))) {
		
		my ($start, $end) = split '-', $k;
		my $preceding = substr $text, 0, $start;
		#two initials (why would they write that?  Why not?) {
		if ($preceding =~ /\b([A-Za-z][\. ] ?[A-Za-z]\.?) ?\Z/g) {
		    my $key = (length ($`))."-".(length($`) + (length $1));
		    addType ($key, "Initials (NamePattern5)");
		    if (!(isType($k, "Last Name", 0))) {
			addType ($k, "Last Name (NamePattern5)");
		    }
		}
		
		elsif ($preceding =~ /\b([A-Za-z]\.?) ?\Z/g) { #1 initial
		    my $init = $1;
		    my $key = (length ($`))."-".(length($`) + (length $1));
		    if (lc($init) eq "s") { 
			if ((substr $preceding, (length($`) - 1), 1) eq "'") {  #for 's
			    #next INI;
			} 
		    }
		    if ((lc($init) eq "a") || (lc($init) eq "i")) {
			if (isCommon(substr $text, $start, ($end - $start))) {
#			next INI;
			}
		    }
	
		}		
	    }
	}
        #****************************************************************************************

	# Searches for patterns "name and/or," comma list names
	foreach $k (keys %phi) {
	    
	    if ((isType($k, "Last Name", 0)) || (isType($k, "Male First Name", 0)) || (isType($k, "Female First Name", 0))) {
		my ($start, $end) = split '-', $k;
		my $following = substr $text, $end;
		
		if ((length $following) == 0) { next; }
		
		# First just looks for "and"/"or"
		if ($following =~ /\A and ([A-Za-z]+)\p{IsPunct}/ig) { 
		    my $word = $text1;
		    my $key = ($end + 5)."-".($end + 5 + length($1));
		    if ((isType($key, "Name", 1))  || (!(isCommon($word)))) { 
			addType ($key, "Last Name (NamePattern6)"); 
		    }
		} 
		elsif ($following =~ /\A and ([A-Za-z]+)\b/ig) { 
		    my $word = $1;
		    my $key = ($end + 5)."-".($end + 5 + length($1));
		    if (!(isCommon($word))) { 
			addType ($key, "Last Name (NamePattern6)"); 
		    }
		}
		elsif ($following =~ /\A or ([A-Za-z]+)\b/ig) { 
		    my $word = $1;
		    my $key = ($end + 4)."-".($end + 4 + length($1));
		    if (!(isCommon($word))) { 
			addType ($key, "Last Name (NamePattern6)"); 
		    }
		}
		elsif ($following =~ /\A( ?[\&\+] ?)([A-Za-z]+)\b/ig) {
		    my $word = $2;
		    my $st = $end + (length $1);
		    my $key = "$st-".($st + length($2));
		    if (!(isCommon($word))) { 
			addType ($key, "Last Name (NamePattern6)"); 
		    }
		}
		elsif ($following =~ /\A, ([A-Za-z]+)(,? and )([A-Za-z]+)\b/ig) { 
		    # Searches up to 3 names in a list 
		    my $name1 = $1;
		    my $name2 = $3;
		    my $st2 = $end + 2 + (length $name1) + length($2);
		    my $key1 = ($end + 2)."-".($end + 2 + (length $name1));
		    my $key2 = "$st2-".($st2 + length($name2));
		    if (!(isCommon($name1))) { 
			addType ($key1, "Last Name (NamePattern6)"); 
		    }
		    if (!(isCommon($name2))) { 
			addType ($key2, "Last Name (NamePattern6)"); 
		    }
		}
	    }
	}
}
}
# End of function name3()



#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: commonHoliday()
# Searches for some common holiday names that can identify the date
# Extension: Add new holiday names to this regex

sub commonHoliday() {
    $text = $_[0];
    if ($datefilter =~ /y/) {
	
	while ($text =~ /\b(christmas|thanksgiving|easter|hannukah|rosh hashanah|ramadan)\b/ig) {
	    $holidayname = $1;
	    $start = length($`);
	    $end = $start + length($holidayname);
	    $key = $start."-".$end;
	    addType ($key, "Holiday");
	}
    }
}
# End of function commonHoliday()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************    
# Function: knownPatientName()
# Searches for PID-specific patient names known a priori, i.e. the patient first and last names for this particular PID
# Indiscriminately removes these PHI from anywhere in the text
# Extension: To include new PID-patient name mappings, extend the file $patient_file

sub knownPatientName {
    $text = $_[0];
    if ($namefilter =~ /y/) {

	foreach $i (@known_first_name) {
	    while ($text =~ /\b($i)\b/ig) {
		my $start = length($`);
		my $end = $start + length($1);
		my $key = "$start-$end";
		addType ($key, "Known patient firstname");
	    }
	}
	
	foreach $j (@known_last_name) {
	    while ($text =~ /\b($j)\b/ig) {
		my $start = length($`);
		my $end = $start + length($1);
		my $key = "$start-$end";
		addType ($key, "Known patient lastname");
	    }
	}       
    }
}
# End of function knownPatientName()




#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Returns true if the number passed in matches a defined us area code
sub isCommonAreaCode  {
    $areacode = $_[0];
    return ($us_area_code{$areacode});

}



#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: telephone()
# Searches for telephone numbers, with or without area codes, with or without extensions
# Extension: To add new formats, add a new rule

sub telephone() {
    $text = $_[0];
    if ($telfilter =~ /y/) {
       	while ($text =~ /\b\(?\d{3}\s*[ \-\.\/\=\,]*\s*\d{4}\)?\b/g) { #added back \b to avoid high fp
	#while ($text =~ /\b\d{3}\s*[ \-\.\/\=\,]*\s*\d{4}\b/g) { #added back \b to avoid high fp
	    my $start = length($`);
	    my $end = $start + length($&);

	    my $nextSeg = substr $text, $end, 20;

	    #catch extensions
	    if ($nextSeg =~ /\A(\s*x\.?\s*[\(]?[\d]+[\)]?)\b/) {		
		$end += length($1);
	    } elsif ($nextSeg =~ /\A(\s*ext[\.]?\s*[\(]?[\d]+[\)]?)\b/) {
		$end += length($1);
	    } elsif ($nextSeg =~ /\A(\s*extension\s*\(?[\d]+\)?)\b/) {
		$end += length($1);
	    }

	    
	    my $key = "$start-$end";

	    #now checks the context
	    $context_len = 20;
	    my $start_pos = $start - $context_len; 
	    if ($start_pos < 0) {
		$start_pos = 0;
	    }
	    my $len = $context_len;
	    if  (length ($text) < ($end + $context_len)){
		$len = length($text) - $end;
	    } 
	    my $textBefore = substr $text, $start_pos, ($start - $start_pos);
	    my $textAfter = substr $text, $end, $len;
	    if (isProbablyPhone($textBefore)){
		addType ($key, "Telephone/Fax (1)");
	    }
	}
	
    
       #pattern such as ###-###-####
       #let's not worry about patterns such as ###-HART and ###-LUNG for now
	#while ($text =~ /\(?\d{3}?\s?[\)\.\/\-\=\, ]*\s?\d{3}\s?[ \-\.\/\=]*\s?\d{4}\b/g) {
        while ($text =~ /\d{3}\s*[\)\.\/\-\, ]*\s*\d{3}\s*[ \-\.\/]*\s*\d{4}/g) {

	   
	#if (isCommonAreaCode($1)){ 
	    my $st = length($`);
	    my $end = $st + length($&);

	    my $nextSeg = substr $text, $end, 20;
	    
	    if ($nextSeg =~ /\A(\s*x\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		$end += length($1);
	    }  elsif ($nextSeg =~ /\A(\s*ex\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		$end += length($1);
	    }  elsif ($nextSeg =~ /\A([\,]?\s?ext[\.]?\s*[\(]?[\d]+[\)]?)\b/) {
		
		$end += length($1);
	    } elsif ($nextSeg =~ /\b(\s?extension\s*\(?[\d]+\)?)\b/) {
		
		$end += length($1);
	    }

	    my $key = "$st-$end";	   
	    addType ($key, "Telephone/Fax (2)");

	}

	#allow arbitrary line break (almost) anywhere in the phone numbers (except first 3 digit to reduce fp)
	#only scrubbs the pattern, if it's a known area code
	while ($text =~ /(\d\d\d)\s*[\)\.\/\-\, ]*\s*\d\s*\d\s*\d\s*[ \-\.\/]*\s*\d\s*\d\s*\d\s*\d/g) {
	    
	    if (isCommonAreaCode($1)){ 
		my $st = length($`);
		my $end = $st + length($&);

		
		my $nextSeg = substr $text, $end, 20;
	    
		if ($nextSeg =~ /\A(\s*x\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		}  elsif ($nextSeg =~ /\A(\s*ex\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		}  elsif ($nextSeg =~ /\A([\,]?\s?ext[\.]?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		} elsif ($nextSeg =~ /\b(\s?extension\s*\(?[\d]+\)?)\b/) {
		
		    $end += length($1);
		}

		my $key = "$st-$end";	   
		addType ($key, "Telephone/Fax (2)");
	    }
	}

	#check phone pattern that has 1 extra or 1 less digit at end
	#in case pattern such as xxx-xxx-xxx?, check if the first 3 digits match with
        #common area code

	while (($text =~ /\(?(\d{3})\s*[\)\.\/\-\=\, ]*\s*\d{3}\s*[ \-\.\/\=]*\s*\d{3}\b/g)){
	    
	    #match it with common local area code
	    if (isCommonAreaCode($1)){
		my $st = length($`);
		my $end = $st + length($&);		
		
		my $nextSeg = substr $text, $end, 20;
		
		if ($nextSeg =~ /\A(\s*x\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		}  elsif ($nextSeg =~ /\A(\s*ex\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		}  elsif ($nextSeg =~ /\A(\s?ext[\.]?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		} elsif ($nextSeg =~ /\A(\s?extension\s*\(?[\d]+\)?)\b/) {
		
		    $end += length($1);
		}
		
		my $key = "$st-$end";	   
		addType ($key, "Telephone/Fax (3)");
	    } #end if the first 3 digits are area codes
	}  #end while

	#check phone pattern that has 1 extra  digit at end
	#in case pattern such as xxx-xxx-xxxxx, check if the first 3 digits match with
        #common area code
	while (
	       ($text =~ /\(?(\d{3})\s*[\)\.\/\-\=\, ]*\s*\d{3}\s*[ \-\.\/\=]*\s*\d{5}\b/g)) {

	    
	    #match it with common local area code
	    if (isCommonAreaCode($1)){
		my $st = length($`);
		my $end = $st + length($&);		
		
		my $nextSeg = substr $text, $end, 20;
		
		if ($nextSeg =~ /\A(\s*x\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		}  elsif ($nextSeg =~ /\A(\s*ex\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		    $end += length($1);
		}  elsif ($nextSeg =~ /\A(\s?ext[\.]?\s*[\(]?[\d]+[\)]?)\b/) {
		    
		    $end += length($1);
		} elsif ($nextSeg =~ /\A(\s?extension\s*\(?[\d]+\)?)\b/) {
		   
		    $end += length($1);
		}
	
		my $key = "$st-$end";	   
		addType ($key, "Telephone/Fax (4)");
	    } #end if the first 3 digits are area codes
	}  #end while


     #in case typed in pattern such as ###-####-### 
       while ($text =~ /\(?\d{3}?\s?[\)\.\/\-\=\, ]*\s?\d{4}\s?[ \-\.\/\=]*\s?\d{3}\b/g) {
	    my $st = length($`);
	    my $end = $st + length($&);
	    my $nextSeg = substr $text, $end, 20;

	    if ($nextSeg =~ /\A(\s*x\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		$end += length($1);
	    }  elsif ($nextSeg =~ /\A(\s*ex\.?\s*[\(]?[\d]+[\)]?)\b/) {
		
		$end += length($1);
	    }
	    elsif ($nextSeg =~ /\A(\s*ext[\.]?\s*[\(]?[\d]+[\)]?)\b/) {
		
		$end += length($1);
	    } elsif ($nextSeg =~ /\A(\s*extension\s*\(?[\d]+\)?)\b/) {
		
		$end += length($1);
	    }


	    my $key = "$st-$end";	   
	    
	    addType ($key, "Telephone/Fax (5)");
	}
    }    
}
# End of function telephone()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Add new function here >>>>>>>>>>
# Follow format shown here if necessary 
# sub functionName {
#    $text = $_[0];
#    while ($text =~ /(<search pattern>)/) {
#       $startIndex = length($');
#       $endIndex = $startIndex + length($1);
#       $phiKey = $startIndex."-".$endIndex;
#       addType ($phiKey, "Name of PHI Category");
#   }
# }

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: pruneKeys()
# Arguments: hash %keys, string $text
# Returns: array @keylst
# Called by: findPHI()
# Description: Extracts PHI locations from hash %keys, compares each loc with previous loc to prevent overlaps
# Returns an array of pruned PHI keys

sub pruneKeys {
    my ($keyh,$text) = @_;
    my $lk = "";
    my ($ls,$le)=(0,0);
    my ($cs,$ce)=(0,0);
    my @keylst = ();
    foreach $k (sort numerically keys %{$keyh}) {
	#print "prunkey, key = $k  values = \n";
	$ls = $cs;
	$le = $ce;
	($cs,$ce)= split ('-',$k);
	if ($cs > $le){push (@keylst,$lk);} # proper relation
	elsif($cs > $ls){
	    if($ce > $le) {
		my $stgl = substr($text,$ls,$le-$ls);	       
		my $stgc = substr($text,$cs,$ce-$cs);	
		$cs = $ls; $k = "$ls-$ce"; $$keyh{$k} = $$keyh{$lk}} # include both transfer types
	    else{$cs = $ls; $ce = $le; $k = $lk;}} # use previous (current in previous)
	elsif($le > $ce){$cs = $ls; $ce = $le; $k = $lk;} # use previous (current in previous)
	$lk = $k;}
    #print "pushing $lk to keylst\n";
    push (@keylst,$lk); # last one
    return (@keylst)
    }    
# End of pruneKeys()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: addType()
# Arguments: string $key ("start-end" of PHI loc), string $type (PHI type)
# Returns: None
# Called by: findPHI()
# Description: Pushes PHI key and type into the hash %phi
# Keeps track of all possible PHI types for each PHI key

sub addType {

    my ($key,$type) = @_;
    ($st,$end) = split '-',$key;
    if ($end > $end{$st}) {
	$end{$st} = $end;
    } 
    #print "in addType, key is $key\n";
    push @{$phi{$key}}, $type;
    $t = (@{$phiT{$key}}); 
    $start = $st - 1 - 64;
    $ending = $end - 1 - 64;
    return;
}
# End of addType()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isType()
# Arguments: string $key ("start-end" of PHI loc), string $type (PHI type), int $pattern (1 if PHI type can be matched with '=~'; 0 otherwise)
# Returns: 1 if PHI $key is of PHI type $type; 0 otherwise
# Called by: findPHI()
# Description: Given a PHI loc, checks its PHI type in the existing PHI hash. If the type in the hash is equal to the given type, then returns 1.

sub isType {
    my ($key, $type, $pattern) = @_;
    foreach $tt (@{$phi{$key}}){
#	print "isType, tt is $tt key is $key\n";
	if ($pattern) {
	    if ($tt =~ /$type/) {
		return 1;
	    }
	}
	elsif ($tt eq $type) {
	    return 1;
	}
    }
    return 0;
}

# End of isType()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isPHIType()
# Arguments: string $mytype (PHI type),  array of string @phiTypes
# Returns: 1 if PHI $mytype appears in @phiTypes, 0 otherwise.
# Called by: deid()
# Description: Given a PHI type, checks if it appears in @phiTypes, if so, returns 1. Returns 0 otherwise.

sub isPHIType {
  my (  $mytype,  @phiTypes) = @_;
	
    #foreach $tt (@{$phi{$key}}){
    foreach $tt (@phiTypes){
	
	if ($tt =~ /$mytype/) {
	    return 1;
	} #end if
    } #end foreach
    return 0;
}

# End of isPHIType()


#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isCommon()
# Arguments: string $word
# Returns: 1 if given word is a common word; 0 otherwise
# Called by: findPHI()
# Description: Compares the given word to the common_words association, compiled from dictionary files for common English words and from SNOMED.
# Returns 1 if given word is in one of those lists, i.e. is a common word.

sub isCommon {
    my $word = $_[0];
    chomp $word;
    $word = uc($word);
    return  ($common_words{$word} || $unambig_common_words{$word});
    
}
# End of isCommon()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isUnambigCommon()
# Arguments: string $word
# Returns: 1 if given word is a really common word or unambig med terms; 0 otherwise
sub isUnambigCommon {
    my $word = $_[0];
    $word = uc($word);
    return $unambig_common_words{$word};
}
# End of isUnambigCommon()


#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isNameAmbig()
# Arguments: string $word
# Returns: 1 if given word is an ambiguous name
# Called by: findPHI()
# Description: Searches for given word in lists of ambiguous male, female and last names
# Returns 1 if word is in any of those lists
sub isNameAmbig {
    my $word = $_[0];
    $word = uc($word);
    return (($male_ambig{$word}) || ($female_ambig{$word}) || ($last_ambig{$word}));
}

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isProbablyName()
#Arguments: string $key, $potential_name
#Returns true if
#name is Not a common word  OR
#name is Unambiguous name OR
#name maybe ambiguous BUT starts with Capital_letter followed by small_case letter OR
#name is popular
sub isProbablyName{
    my ($key, $potential_name) = @_;

    if ( (!isCommon($potential_name)) ||
	 ((isType($key, "Name", 1) && isType($key, "(un)"))  ||
	  (isType($key, "Name", 1) && ($potential_name =~ /\b(([A-Z])([a-z]+))\b/g)) ||
	  (isType($key, "popular",1)) )) {
     
	return 1;
    } else {
	return 0;
    }

}
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isUSStateAbbre
#Data structure used for us states
#Returns true if the word is a US state abbreviation
sub isUSStateAbbre {
    my $word = $_[0];
    $word = uc($word);

    foreach $loc (@us_states_abbre){
	if ($word =~/\b$loc\b/gi){
	    return 1;
	}
    }
    foreach $loc (@more_us_states_abbre){
	if ($word =~/\b$loc\b/gi){
	    return 1;
	}
    }
    return 0;

}

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isNameIndicator
#Returns true if the word is a name indicator
sub isNameIndicator {
    my $word = $_[0];
    $word = uc($word);

    foreach $nam (@name_indicators){
	#print "nam in name indicators is $nam";
	if ($word =~/\b$nam\b/gi){
	    
	    return 1;
	}
    }

    return 0;
}

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isUSState
#Returns true if the word is a US State
sub isUSState {
    my $word = $_[0];
    $word = uc($word);
    #return (($us_states{$word}));
    foreach $loc (@us_states){
	if ($word =~/\b$loc\b/gi){
	    return 1;
	}
    }
    return 0;


}

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isFirstName()
# Arguments: string $word
# Returns: 1 if given word is an ambiguous or unambiguous firstname
# Called by: findPHI()

sub isFirstName {
    my $word = $_[0];
    #$word = ($word);
    $word = uc($word);
    return (($male_ambig{$word}) || ($female_ambig{$word}) || ($male_unambig{$word}) || ($female_unambig{$word}) || ($male_popular{$word}) || ($female_popular{$word}));
}
# End of isFirstName()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isCommonest()
# Arguments: string $word
# Returns: 1 if given word is a commonest word; 0 otherwise
# Called by: findPHI()
# Description: Compares the given word to the commonest_words association, compiled from dictionary file for commonest English words.
# Returns 1 if given word is in that list, i.e. is a commonest word.

sub isCommonest {
    my $word = $_[0];
    $word = uc($word);
    return ($very_common_words{$word} || isUnambigCommon($word));
}

# End of isCommonest()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: getNote()
# Arguments: int $patient (patient number), int $note (note number)
# Returns: string $noteText
# Called by: deidStats() (obsolete)
# Description: Given patient and note numbers, looks up header in $header_file
# If it finds the header, extracts the body of the note, and returns text until the end pattern 
sub getNote{

    my ($patient, $note) = @_;    
    open DF, $data_file or die "Cannot open $data_file";
    my $noteFound = 0;
    my $noteText = "";
    
  D:    
    # Parses the data file line-by-line to match the header found in the header file
    while ($line = <DF>) {
	chomp $line;
	

	# If header is found in the text, then matches the end pattern, and sets the body of the note (excluding the header) as the note text

	if ($line =~ /\b$patient\|\|\|\|$note\|\|\|\|/) {
	    $noteFound = 1;
	    $noteText = "";
	} 
	else {		
	    if ($noteFound) {
		if ($line eq "||||END_OF_RECORD"){
		    #$noteText = $noteText."\n".$1;
		    #$noteText = $noteText.$1."\n";
		    $end = $2;
		    last D;
		} 
		else { 
		    $noteText = $noteText.$line."\n";
		}
	    }
	}
    }
    close DF;
    
    # If the note text has zero length, prints an error message
    if ((length $noteText) == 0) {
	print("Warning. No text found for Patient $patient, Note $note ");
    }

    # Returns the body of the note (everything excluding the header) as the note text
    return $noteText;
}
# End of getNote()




#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isValidDate()
# Arguments: int $month, int $day, int $year (If the date being validated doesn't specify year, the "year" argument should be "-1")
# Returns: 1 if given date is valid based on the calendar
# Called by: findPHI(), isValidDay()
# Description: Verifies if the given date is valid or not.

sub isValidDate{
    my ($month, $day, $year) = @_;
    if (($year!=-1) && (length $year) == 2) {
	#if ($year < 30) { 
	if ($year <= $TWO_DIGIT_YEAR_THRESHOLD) { 
	    $year = "20".$year; 
	} 
	else {
	    $year = "19".$year; 
	}
    }
   
    #if (($year != -1) && ($year < 1900 || $year > 2030)){
    #if (($year != -1) && ($year <= $VALID_YEAR_LOW || $year >= $VALID_YEAR_HIGH)){
    if (($year != -1) && ($year < $VALID_YEAR_LOW || $year > $VALID_YEAR_HIGH)){
	
	return 0;
    }
    
    # Invalid months and days
    if (($month< 1) || ($month > 12) || ($day < 1) || ($day > 31)) { 
	return 0;
    }

    # Checks validity of February days
    if ($month == 2) {
	if (($year != -1) && (($year % 4) == 0) && ($year != 2000)) {
	    return ($day <= 29);
	}
	return ($day <= 28);
	
	# Checks validity of months consisting of 30 days
    } 
    elsif (($month == 4) || ($month == 6) || ($month== 9) || ($month == 11)) {
	return ($day <= 30);
    }
    
    # Checks validity of months consisting of 31 days
    return ($day <= 31);
}
# End of isValidDate()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: isValidDay()
# Arguments: int $day, string $month, int $year
# Returns: 1 if given date is valid; 0 otherwise
# Called by: findPHI()
# Description: Verifies validity of date when month is printed, by calling isValidDate()

sub isValidDay {
    my ($day, $month, $year) = @_;
    my $mnum = 0;

    # Converts printed out months to numerical months
    if ($month =~ /Jan|January|Januar/i) { $mnum = 1; }
    elsif ($month =~ /Feb|February|Februar/i) { $mnum = 2; }
    elsif ($month =~ /Mar|March|Maerz/i) { $mnum = 3; }
    elsif ($month =~ /Apr|April/i) { $mnum = 4; }
    elsif ($month =~ /May|Mai/i) { $mnum = 5; }
    elsif ($month =~ /June|Jun|Juni/i) { $mnum = 6; }
    elsif ($month =~ /July|Jul|Juli/i) { $mnum = 7; }
    elsif ($month =~ /August|Aug/i) { $mnum = 8; }
    elsif ($month =~ /September|Sept|Sep/i) { $mnum = 9; }
    elsif ($month =~ /October|Oct/i) { $mnum = 10; }
    elsif ($month =~ /November|Nov/i)  { $mnum = 11; }
    elsif ($month =~ /December|Dec/i) { $mnum = 12; }
    if ($mnum == 0) { return 0; }
    
    return (isValidDate($mnum, $day, $year));
}
# End of isValidDay()


#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: outputText()
# Arguments: hash %deids (key=PHI start index, value=PHI end index), hash %phiT (key=PHI start-end indices, value=PHI type)
# Returns: None
# Called by: deid()
# Description: Creates the de-identified version of the text
# Replaces dates with shifted dates, and other PHI with their PHI types
sub outputText {
    my %deids = %{$_[0]};
    my %phiT = %{$_[1]};

    # These are the date and PID of the medical record. The year needs to be initialized.
   # my $checkYear = "2005";
    my $checkYear;
    my $checkDate;
    my $checkID;

    # Forms associations between printed months and numerical ones
    # This is because the date-shifting function only accepts numerical months, and months in the text can be non-numerical as well
    my %months;
    $months{"jan"} = 1;
    $months{"feb"} = 2;
    $months{"mar"} = 3;
    $months{"apr"} = 4;
    $months{"may"} = 5;
    $months{"jun"} = 6;
    $months{"jul"} = 7;
    $months{"aug"} = 8;
    $months{"sep"} = 9;
    $months{"oct"} = 10;
    $months{"nov"} = 11;
    $months{"dec"} = 12;

    #TF is the .res file (de-identified corpus), and OF is the (.phi file) list of PHIs
    # open TF, ">$deid_text_file" or die "Cannot open $deid_text_file";
    open TF, ">>$deid_text_file" or die "Cannot open $deid_text_file";   #now open in append mode
    my $lastEnd = 0; 
    #open OF, ">>$output_file_old" or die "Cannot open $output_file_old";

    my $phiType = "";

    # Prints the PHI locations to the output file (.phi)
    foreach $k (sort numerically keys %deids) {		    
	my @deidsval = @{$deids{$k}};
	local $added = 0;
	my $phiID;

	# Loops over each PHI recorded in %deids
	# %deids maps each PHI start index to an array of 3 items
	# These items are in order: the PHI end index, the PID of the PHI, the record date of the PHI    
	#if (exists ${@{$deids{$k}}}[0]) {
	if (exists $deidsval[0]){
	    # Sets some key variables for the PHI

	    #the following no longer works with perl v5.10
	    #$deidsend = ${@{$deids{$k}}}[0]; # End index 
	    #$checkID = ${@{$deids{$k}}}[1]; # PID
	    #$checkDate = ${@{$deids{$k}}}[2]; # Record date

	    $deidsend = $deidsval[0]; # End index 
	    $checkID = $deidsval[1]; # PID
	    $checkDate = $deidsval[2]; # Record date
	    $checkYear = (substr $checkDate, 6, 4); # Record year
	    if (length($checkYear) ==0) {
		$checkYear = extractYear($DEFAULT_DATE);
		print "Warning, in outputText(), cannot extract year from noteDate, setting year to default year $checkYear.";
	    }

	    # Immediately prints the start and end indices of the PHI to the .phi file
	    #print OF "$k\t$deidsend\n";

	    # Sets the $key to the current PHI
	    my $key = $k."-".$deidsend;
	    my $lastlast = $lastEnd;
	    my $phiText;
	    
	    # If this PHI is a date element, shifts the date and replaces it in the text
	    # Output format is YYYY/MM/DD always
	    # For month/date formats, assumes that year = record year; for month/year formats, assumes that day = 1	

	    # Needs to go over %phiT for every PHI in %deids
	    # %phiT maps each PHI key to its type, e.g. "Mary" -> "First Name"
	    # This part is necessary because re-identification depends on the PHI's type
	    foreach $ky (sort numerically keys %phiT) {

		my $ky = $ky;
		($startp, $endp) = split "-", $ky;
		$notAmbig = 0;	
		
		# Checks to see if PHI type matches any of the date patterns
		# Each PHI may have more than one listed type, e.g. First Name AND Last Name
		# For each PHI type listed for the specific PHI
		foreach $t (@{$phiT{$ky}}) {

		    $datephi1 = "Year/Month/Day"; # e.g. 1999/2/23
		    $datephi2 = "Year/Day/Month"; # e.g. 1999/23/2, note: pattern currently not filtered in sub date()!
		    $datephi3 = "Month/Day/Year"; # e.g. 2/23/1999
		    $datephi5 = "Day/Month/Year"; # 23/2/1999, note: pattern currently not filtered in sub date()!
		    $datephi4 = "Month/Day"; # e.g. 2/23, using record year as year
		    $datephi6 = "Day/Month"; # e.g. 23/2, using record current year as year, note: pattern currently not filtered in sub date()!
		    $datephi7 = "Month/Year";  # e.g. 2/1999, using 1 as day
		    $datephi8 = "Year/Month";  # e.g. 1999/2, using 1 as day
		    $datephi9 = "Day Month Year"; # e.g. 23 february 1999
		    $datephi10 = "Month Day Year"; # e.g. feb 23 1999 or feb. 23rd 1999
		    $datephi11 = "Month Day"; # e.g. feb 23, using record year as year
		    $datephi12 = "Day Month"; # e.g. 23 february, using record year as year
		    $datephi13 = "Month Year"; # e.g. feb 1999, or february of 1999 or feb. 1999, using 1 as day
		    $datephi14 = "Header Date"; # not important
		    $datephi15 = "4 digits"; # 4-digit year, e.g. 1999
		    $datephi16 = "2 digits"; # 2-digit year, e.g. '99
		    $datephi17 = "Day Month Year 2"; # e.g. 23rd february 1999

		    
		    #if ($ky =~/$key/) {$phiType = $t;}
		    if ($ky eq $key) {$phiType = $t;}

		    # Calls the date-shifting function alterdate() with a date argument appropriate for the date pattern
		    # This is because alterdate() accepts an argument of a fixed date pattern
		    # Prints the resulting shifted date in deid_text_file (.res)
		    
		    # If the current PHI has not been output to the .res file yet, checks if PHI type is date
		    # Shifts the date and writes the shifted date to TF (.res file)
		    if ($added == 0) {
			
			#if (($t =~ /$datephi1/)  && ($ky=~/$key/)){
			if (($t =~ /$datephi1/)  && ($ky eq $key)){		    
			    $date = (substr $allText, $k, ($deidsend-$k));			   
			    $date =~ s/\-/\//g;		
			    $date =~ s/\./\//g;
			    $altereddate = &alterdate($date, $checkID);
			    $date =~ /(\d+)(.)(\d+)(.)(\d+)/;
			    $longyear = $1;
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";		       			    
			    $added = 1;
			    $lastEnd = $deidsend;
			    
			}
			elsif (($t =~ /$datephi17/)  && ($ky eq $key)){   
			    $date = (substr $allText, $k, ($deidsend-$k));		   
			    
			    $date =~ /\b(((\d{1,2})(|st|nd|rd|th|)?\s+(of\s)?[\-]?\b([A-Za-z]+)\.?,?)\s+(\d{2,4}))\b/ig; # 12-Apr, or Second of April

			    $mon = $6;
			    $day = $3;
			    $year = $7; 
			    foreach $m (sort keys %months) {
				if ($mon =~ /$m/ig) {
				    $month = $months{$m};
				}
			    }			    
			    $date =  "$year/$month/$day";

			    $altereddate = &alterdate($date, $checkID );
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";
			    
			    $added = 1;
			    $lastEnd = $deidsend;
			}				
			#elsif (($t =~ /$datephi9/)  && ($ky=~/$key/)){ 
			elsif (($t =~ /$datephi9/)  && ($ky eq $key)){   
			    $date = (substr $allText, $k, ($deidsend-$k));		   
			    $date =~ /(\d+) ([A-Za-z]+)\,? (\d+)/;
			    $mon = $2;
			    $day = $1;
			    $year = $3;
			    foreach $m (sort keys %months) {
				if ($mon =~ /$m/ig) {
				    $month = $months{$m};
				}
			    }			    
			    $date =  "$year/$month/$day";
			    $longyear = $5;
			    $altereddate = &alterdate($date, $checkID );
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";
			    
			    #local $added = 1; 
			    $added = 1;
			    $lastEnd = $deidsend;
			}			
			#elsif (($t =~ /$datephi10/)  && ($ky=~/$key/)){   
			elsif (($t =~ /$datephi10/)  && ($ky eq $key)){ 

			    $date = (substr $allText, $k, ($deidsend-$k));	
			   
			    $date =~ /\b(([A-Za-z]+)\b\.?,? ?(\d{1,2})(|st|nd|rd|th|)? ?[\,\s]+ *\'?(\d{2,4}))\b/ig; 
			    $mon = $2;
			    $day = $3;
			    $year = $5;
			    #$date =~ /([A-Za-z]+) (\d+)\,? (\d+)/;
			    #$mon = $1;
			    #$day = $2;
			    #$year = $3;
			    #print "DatePHI10: Before date shift: month= $mon, day = $day , year = $year \n";

			    foreach $m (sort keys %months) {
				if ($mon =~ /$m/ig) {
				    $month = $months{$m};
				}
			    }
			    $date =  "$year/$month/$day";
			    $altereddate = &alterdate($date, $checkID);
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";
			    
			    #local $added = 1; 
			    $added = 1;
			    $lastEnd = $deidsend;
			}					
			#elsif (($t =~ /$datephi2/)  && ($ky=~/$key/)){   
			elsif (($t =~ /$datephi2/)  && ($ky eq $key)){   
			    $date = (substr $allText, $k, ($deidsend-$k));		   			    
			    $date =~ /(\d+)(.)(\d+)(.)(\d+)/;
			    $date =  "$1/$5/$3";
			    $longyear = $1;
			    $altereddate = &alterdate($date, $checkID);
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    #local $added = 1; 
			    $added = 1;
			    $lastEnd = $deidsend;
			}		
			#elsif (($t =~ /$datephi3/)  && ($ky=~/$key/)){  
			elsif (($t =~ /$datephi3/)  && ($ky eq $key)){   
			    $date = (substr $allText, $k, ($deidsend-$k));		   			    
			    $date =~ /(\d+)(.)(\d+)(.)(\d+)/;
			    $date =  "$5/$1/$3";
			    $altereddate = &alterdate($date,  $checkID);
			    $longyear = $5;
			   
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    $added = 1;
			    $lastEnd = $deidsend;			    
			}
			#elsif (($t =~ /$datephi5/)  && ($ky=~/$key/)){  	
			elsif (($t =~ /$datephi5/)  && ($ky eq $key)){   			    
			    $date = (substr $allText, $k, ($deidsend-$k));		   			    
			    $date =~ /(\d+)(.)(\d+)(.)(\d+)/;
			    $date =  "$5/$3/$1";
			    $altereddate = &alterdate($date, $checkID );
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";
			    $longyear = $5;
			    $added = 1;
			    $lastEnd = $deidsend;			    
			}	
			#elsif (($t =~ /$datephi4/)  && ($ky=~/$key/)){   
			elsif (($t =~ /$datephi4/)  && ($ky eq $key)){   			    
			    $date = (substr $allText, $k, ($deidsend-$k));	
			    $date =~ s/\-/\//g;		
			    $date = "$checkYear/$date";			    
			    $altereddate = &alterdate($date, $checkID);
			    $altereddate = (substr $altereddate, 5, (length($altereddate)-5));
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    $added = 1;
			    $lastEnd = $deidsend;			    
			}	
			#elsif (($t =~ /$datephi11/)  && ($ky=~/$key/)){  
			elsif (($t =~ /$datephi11/)  && ($ky eq $key)){   			    
			    $date = (substr $allText, $k, ($deidsend-$k));		   
			    #$date =~ /([A-Za-z]+) (\d+)/;
			    #$mon = $1;
			    #$day = $2;
			    $date =~ /\b(([A-Za-z]+)\b\.?,?\s*(\d{1,2})(|st|nd|rd|th|)?)\b/ig;  # Apr. 12
			    $mon = $2;
			    $day = $3;
			   
			    foreach $m (sort keys %months) {
				if ($mon =~ /$m/ig) {
				    $month = $months{$m};
				}
			    }
			    $date =  "$checkYear/$month/$day";
			    $altereddate = &alterdate($date,  $checkID);
			    $altereddate = substr($altereddate, 5, (length($altereddate)-5));			    
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    $added = 1;
			    $lastEnd = $deidsend;
			}
				
			#elsif (($t =~ /$datephi6/)  && ($ky=~/$key/)){   
			elsif (($t =~ /$datephi6/)  && ($ky eq $key)){   			    
			    $date = (substr $allText, $k, ($deidsend-$k));		   			    
			    $date =~ /(\d+)(.)(\d+)/;
			    #print "DatePHI6: date is $date, 3 is $3, 1 is $1\n";
			    $date =  "$3/$1";
			    $date = "$checkYear/$date";
			    $altereddate = &alterdate($date,  $checkID);
			    $altereddate = substr($altereddate, 5, (length($altereddate)-5));
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    $added = 1;
			    $lastEnd = $deidsend;			    
			}
			#elsif (($t =~ /$datephi12/)  && ($ky=~/$key/)){   	
			elsif (($t =~ /$datephi12/)  && ($ky eq $key)){  			    
			    $date = (substr $allText, $k, ($deidsend-$k));	
			    #$date =~ /(\d+) ([A-Za-z]+)/;
			    #$mon = $2;
			    #$day = $1;
			    $date =~ /\b((\d{1,2})(|st|nd|rd|th|)?( of)?[ \-]\b([A-Za-z]+))\b/ig;
			   
			    $mon = $5;
			    $day = $2;
			    #print "month is $month, day is $day\n";
			    foreach $m (sort keys %months) {
				if ($mon =~ /$m/ig) {
				    $month = $months{$m};
				}
			    }
			    $date =  "$checkYear/$month/$day";
			    $altereddate = &alterdate($date,  $checkID);
			    $altereddate = substr($altereddate, 5, (length($altereddate)-5));			    
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";
			    $added = 1;
			    $lastEnd = $deidsend;
			}
			#elsif (($t =~ /$datephi13/)  && ($ky=~/$key/)){   
			elsif (($t =~ /$datephi13/)  && ($ky eq $key)){   
			    $date = (substr $allText, $k, ($deidsend-$k));		   
			    $date =~ /([A-Za-z]+)(\.)?(\s+)(of\s+)?(\d+)/ig;
			    $mon = $1;
			    $year = $5;
			    foreach $m (sort keys %months) {
				if ($mon =~ /$m/ig) {				
				    $month = $months{$m};
				}
			    }
 
			    $date = "$year/$month/1";
			    $longyear = $3;
			    $altereddate = &alterdate($date, $checkID );
			    
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    $added = 1;
			    $lastEnd = $deidsend;
			}
			#elsif (($t =~ /$datephi7/)  && ($ky=~/$key/)){   	
			elsif (($t =~ /$datephi7/)  && ($ky eq $key)){   			    
			    $date = (substr $allText, $k, ($deidsend-$k));		   
			    $date =~ /(\d+)(.)(\d+)/;		
			    $date =  $3.'/'.$1.'/1';
			    $altereddate = &alterdate($date,  $checkID);
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";
			    $longyear = $3;
			    $added = 1;
			    $lastEnd = $deidsend;
			}
			#elsif (($t =~ /$datephi8/)  && ($ky=~/$key/)){  
			elsif (($t =~ /$datephi8/)  && ($ky eq $key)){   			    
			    $date = (substr $allText, $k, ($deidsend-$k));		   
			    $date =~ /(\d+)(.)(\d+)/;		
			    $date =  $1.'/'.$3.'/1';
			    $altereddate = &alterdate($date,  $checkID);
			    $longyear = $1;
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$altereddate**]";			    
			    $added = 1;
			    $lastEnd = $deidsend;
			}
			#elsif (($t =~ /$datephi14/)  && ($ky=~/$key/)) {
			elsif (($t =~ /$datephi14/)  && ($ky eq $key)) {
			    $date = (substr $allText, $k, ($deidsend-$k));
			    $date =~ /(\d+)(\-)(\d+)(\-)(\d+)/;
			    $date = $1.'/'.$3.'/'.$5;
			    $altereddate = &alterdate($date,  $checkID);
			    $longyear = $1;
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."$date";
			    $added = 1;
			    $lastEnd = $deidsend;
			}
			#elsif (($t =~ /$datephi15/)  && ($ky=~/$key/)) {
			elsif (($t =~ /$datephi15/)  && ($ky eq $key)) {
			    $year  = (substr $allText, $k, ($deidsend-$k));
			    $date = $year.'/1/1';
			    $altereddate = &alterdate($date, $checkID);
			    $alteredyear = (substr $altereddate, 0, 4);
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$alteredyear**]";
			    $added = 1;
			    $lastEnd = $deidsend;
			}	
			#elsif (($t =~ /$datephi16/)  && ($ky=~/$key/)) {
			elsif (($t =~ /$datephi16/)  && ($ky eq $key)) {
			    $year  = (substr $allText, $k, ($deidsend-$k));	

			    #if ($year > 20) {
			    #	$year = '19'.$year;
			    #} else {
			    #	#$year = '20.'.$year;	
			    #	$year = '20'.$year;
			    #    }
			 
			    $date = $year.'/1/1';

			    $altereddate = &alterdate($date, $checkID);
			    $alteredyear = (substr $altereddate, 2, 2);
			    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$alteredyear**]";
			    $added = 1;
			    $lastEnd = $deidsend;
			} 
			# If the current PHI is not a date, then indicates that it has not been output yet
			else { my $added = 0;}		    
		    }
		}
	    }    
	    
	    # If the PHI is not a date, replaces it in deid_text_file (.res) by its PHI type tag
	    if ($added==0) {
		
		if ($k > $lastEnd || ($k==0)) {
		    $phiText = (substr $allText, $k, ($deidsend-$k));
		

		    # Parentheses are eliminated so that they do not trip up the run
		    $phiText =~ s/\(//g;
		    $phiText =~ s/\)//g;
		    $phiText =~ s/\+//g;		
		    
		    $found = 0;

		    # Assigns a unique ID to each PHI, e.g. all instances of "Mary" may be assigned "1", but "John" may be assigned "2"
		    # %ID maps each PHI (e.g. "Mary") to its ID (e.g. "1")
		    foreach $phik (keys %ID) {
			if ($phik =~/$phiText/ig) {
			    $found = 1;
			}
		    }

		    # If the current PHI to be added to .res file is already recorded in %ID, then retrieves its unique ID
		    if ($found==1) {
			$phiID = $ID{$phiText};
		    }

		    # If the current PHI is not recorded in %ID, records it in %ID and assigns the PHI a unique ID
		    else {
			$ID{$phiText} = keys(%ID) + 1;
			$phiID = $ID{$phiText};
		    }
		    		    
		    # Prints the PHI type and PHI ID in place of the original PHI in the .res file
		    print TF (substr $allText, $lastEnd, ($k - $lastEnd))."[**$phiType $phiID**]";
		    $lastEnd = $deidsend;
		} 

		else {
		    if ($lastEnd < $deidsend) {
			$lastEnd = $deidsend;
		    }
	    }
		
		if ($lastEnd == 0) { 
		    $lastEnd = $lastlast;
		}
	    }	    
	}
    }
    #close OF;
    #print "Finished outputing to the .phi file.";
    
    # Prints the remaining non-PHI text to the .res file    
    print TF (substr $allText, $lastEnd);   
    #print "finished outputing to the .res file";

    close TF;   
}
# End of outputText()


#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: alterdate()
# Arguments: string $date (yyyy/mm/dd), int $pid (patient ID)
# Returns: string $year-$month-$day
# Called by: outputText()
# Description: Converts given date to shifted date, depending on date-shift-mode, by calling doalterdate().
# Returns shifted date

sub alterdate { 
    # Separates date fields by splitting along "/" or "-"
    # Then calls doalterdate on the resulting array of date elements
    $d = $_[0];   
    if (substr($d,0,6) =~ /(\/)/) { 
	@d = split '/', $d;
    }
    elsif (substr($d,0,6) =~ /(\-)/) {
	@d = split '-', $d;
    }

    ($entryyear, $entrymonth)=@d[0..1];
    return join "-", &doalterdate(@d, $_[1]);
} 
# End of alterdate()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: doalterdate()
# Arguments: int $year, int $month, int $day, int $pid (patient ID)
# Returns: array @($year, $month, $day)
# Called by: alterdate()
# Description: Converts given date, depending on date-shift-mode, to shifted date.
# Returns shifted date in an array format to calling function alterdate(). alterdate() converts the shifted date to a string.

sub doalterdate {
	my $year=$_[0];
	if (length $year == 2) {

            # Limits 2-digit years between 1900 and 2020
	    # Converts them to 4-digit years
	    #if ($year<=10) {$year = 2000+$year;}  
	    #if ($year<=20) {$year = 2000+$year;}
	    if ($year<=$TWO_DIGIT_YEAR_THRESHOLD) {$year = 2000+$year;}
	    else {$year = 1900+$year;}
	}
	my $month=$_[1];
	my $day=$_[2];
	my $pid=$_[3];       	
   
	if ($pid_dateshift_list =~ /y/) {
	    open SF, $date_shift_file or die "Cannot open $date_shift_file";
	    while ($line = <SF>) {
		chomp $line;
		if ($line =~ /\A($pid)\|\|\|\|([0-9\-]+)/) {
		    $offset = $2;
		}	    
	    }
	    close SF;
	}

	my $ml=&monthlength($month, $year);
	
	# $offset = days of offset (positive or negative shift)
	# Sets the shifted year
	$offset_local = $offset;
	if ($offset_local>0) {
	    $year += 4*int($offset_local/1461);
	    $offset_local -=1461*int($offset_local/1461);
	}
	if ($offset_local<0){
	    $year -= 4*int(-$offset_local/1461);
	    $offset_local +=1461*int(-$offset_local/1461);
	}
	
	# Shifts number of days
	$day +=$offset_local;
	
	$ml=&monthlength($month, $year);

	# Changes $day, $month, $year based on the remaining offset after shifting $year
	while ($day>$ml) {
	    $ml=&monthlength($month, $year);
	    $day=$day-$ml;
	    $month++;
	    if ($month>12) {
		$month -=12;
		$year++;
	    }
	    $ml = &monthlength($month, $year);
	} 
	while ($day<1) {
	    $ml=&monthlength($month-1, $year);
	    $day=$day + $ml;
	    $month--;
	    if ($month<1) {
		$month +=12;
		$year--;
	    }
	}
	
	# Formats the output of single-digit month and day: "2" becomes "02"
	if (length($month)<2) {
	    $month="0".$month;
	}
	if (length($day)<2) {
	    $day="0".$day;
	}
	
	# Returns the shifted date as an array
	return ($year, $month, $day);    
    }
# End of doalterdate()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: altermonthdate()
# Arguments: int $month, int $day, int $pid (patient ID)
# Returns: call doalterdate(), returns array ($year, $month, $day)
# Called by: None
# Description: Calls doalterdate() which performs dateshift
# This function is not used

sub altermonthdate { 
    my ($month, $day, $pid)=@_;
    my $year;
    
    if (($month-$entrymonth)%12<6) {
	if ($month<$entrymonth) {
	    $year=$entryyear+1;
	} 
	else {
	    $year=$entryyear;
	}
    } 
    else { 
	if ($month>$entrymonth) {
	    $year=$entryyear-1;
	}
	else {
	    $year=$entryear;
	}
    }
    return (&doalterdate($year, $month, $day, $pid))[1,2];    
}
# End of altermonthdate()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: getcentury()
# Arguments: int 2-digit $year
# Returns: int
# Called by: None
# Description: Converts a 2-digit year into a 4-digit year based on entryyear
# This function is not used

sub getcentury { 
    my $year=$_[0];

    if (($year-$entryyear)%100<10) { 
	$year=$entryyear+(($year-$entryyear)%100);
    }
    else { 
	$year=$entryyear-(($entryyear-$year)%100);
    }
}
# End of getcentury()
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: monthlength()
# Arguments: int $m, int $y
# Returns: int 
# Called by: doalterdate()
# Description: Returns the number of days in given month-year

sub monthlength {
    my($m, $y)=@_;

    while ($m<=0) {
	$m += 12;
	$y --;
    }
    while ($m>=13) {
	$m -= 12;
	$y ++;
    }    
    # Checks for February
    if ($m==2) {
	if ($y % 4 ==0) {
	    if($y % 100 ==0) {
		if ($y % 400 ==0){
		    return 29;
		}
		else {
		    return 28; 
		}
	    } 
	    else { 		
		return 29;
	    }
	} 
	else {		
	    return 28;
	}
    } 
    # Checks for months consisting of 30 days    
    elsif (($m==4) || ($m==6) || ($m==9) || ($m==11)) {	
	return 30;
    } 
    # Checks for months consisting of 31 days    
    else {		
	return 31;
    }
}
# End of monthlength()









#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Application-specific code follows. Code may contain patterns specific to our medical notes.
# Customize by replacing with your application-specific filters. 
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************


#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isProbablyPhone
#Argument: context string
#Returns: Always returns 1 (true) unless the context is one of the words defined in
#phone_pre_disqualifier. For future extensions, can add qualifier words 
#such as "phone", "pager", etc.

sub isProbablyPhone { 
    @phone_pre_disqualifier = ("HR","Heart", "BP", "SVR", "STV", "VT", "Tidal Volumes", "Tidal Volume", "TV", "CKS"); 
    $context = $_[0];
    foreach $i (@phone_pre_disqualifier) {
	if ($context =~ /\b$i\b/i){
	    return 0;
	}
    }	    
    return 1;
}
#end of isProbablyPhone()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# Function: wardname()
# Argument: string
# Searches for ward names specific to our hospital
sub wardname() {
    $text = $_[0];
	
    #Added to catch gs specific wardnames
    if ($gs_specific_filter =~ /y/){
       
	@ward_indicators = ("Quartermain");
	foreach $ward_ind (@ward_indicators){
	    while ($text =~ /\b(($ward_ind) ?(\d))\b/ig){
		$wardname = $1;
		$start = length($`);
		$end = $start + length($wardname);
		$key = $start."-".$end;
		addType ($key, "Wardname");
	    }
	}
    } 

}

# End of function wardname()



#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isProbablyMeasurement
#Argument: context string
#Returns: Returns true if the text passed in contains (more specifically, ends with) any of the measurement indicators.
sub isProbablyMeasurement {
 @measurement_indicators_pre = ("increased to","decreased from","rose to","fell from", "down to",
			   "increased from", "dropped to", "dec to", "changed to","remains on", "change to");
    $context = $_[0];

    foreach $i (@measurement_indicators_pre) {

	if ($context =~ /\b$i\b/i){  #only match if it ends with the phrase
	    return 1;
	}
    }	   

    return 0;
}

#end isProbablyMeasurement()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isProbablyDate
#Argument: textBefore string and textAfter string
#Returns: returns 1 if the context check determines that textBefore or textAfter
#are most likely strings preceding or following a date PHI; returns 0 otherwise. 
#Description: Subroutine performs a context check on the textBefore and textAfter. If it contains one of the 
#keywords (see below) that indicates it's probably not a date, then return false; otherwise return true.
#Called by dateWithContextCheck on partial dates MM-DD
sub isProbablyDate{ 
    my ($textBefore, $textAfter) = @_;
    
    if ((!isProbablyMeasurement($textBefore)) && ($textBefore !~ /\b(drop|up|cc|dose|doses|range|ranged|pad|rate|bipap|pap|unload|ventilation|scale|cultures|blood|at|up|with|in|of|RR|ICP|CVP|strength|PSV|SVP|PCWP|PCW|BILAT|SRR|VENT|PEEP\/PS|flowby|drinks|stage) ?\Z/i) && ($textAfter !~ /\A ?(packs|litres|puffs|mls|liters|L|pts|patients|range|psv|scale|beers|per|esophagus|tabs|tablets|systolic|sem|strength|hours|pts|times|drop|up|cc|mg|\/hr|\/hour|mcg|ug|mm|PEEP|hr|hrs|hour|hours|bottles|bpm|ICP|CPAP|years|days|weeks|min|mins|minutes|seconds|months|mons|cm|mm|m|sessions|visits|episodes|drops|breaths|wbcs|beat|beats|ns|units|amp|qd|chest pain|intensity)\b/i)) { 
     return 1;
 } 

 return 0;

}
#end isProbablyDate()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: isProbablyDate2
#Argument: textBefore string and textAfter string
#Returns: returns 1 if the context check determines that textBefore or textAfter
#are most likely strings preceding or following a date PHI; returns 0 otherwise. 
#Subroutine performs a context check on the textBefore and textAfter.  If it contains one of the 
#keywords (see below) that indicates it's probably not a date, then return false; otherwise return true.
#Called by dateWithContextCheck on partial dates MM/DD.  
sub isProbablyDate2{ 

if ( (!isProbablyMeasurement($textBefore)) && ($textBefore !~ /\b(drop|up|cc|range|ranged|pad|rate|rating|bipap|pap|unload|ventilation|scale|blood|at|up|with|RR|ICP|CVP|strength|PSV|SVP|PCWP|BILAT|SRR|VENT|PEEP\/PS|flowby) ?\Z/i) && ($textAfter !~ /\A ?(packs|litres|puffs|mls|liters|L|pts|patients|range|psv|scale|drinks|beers|per|esophagus|tabs|tab|tablet|tablets|systolic|sem|strength|hours|pts|times|drop|up|cc|mg|\/hr|\/hour|mcg|ug|mm|hr|hrs|hour|hours|bottles|bpm|ICP|CPAP|years|days|weeks|min|mins|minutes|seconds|months|mons|cm|mm|m|sessions|visits|drops|breaths|wbcs|beat|beats|ns|units|amp)\b/i)) { 
     return 1;
 } 
 return 0;


}
#end isProbablyDate2()

#***********************************************************************************************************
#***********************************************************************************************************
#Function: extractYear
#Argument: a date string in the format MM/DD/YYYY
#Returns: the 4-digit year if the date is in the correct format
#returns 0000 otherwise.
sub extractYear{

  $date = $_[0];

  if ($date =~ /\b(\d\d)\/(\d\d)\/(\d\d\d\d)\b/){ 
      $year = $3;
  } else{
      $year = 0000;
  }
  return $year;
}

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: dateWithContextCheck
#Argument: text string
#Returns: none
#Description: Find date patterns.  Performs context check on text before and after the date patterns
#to determine if its an actual date.
sub dateWithContextCheck{
    #$text = $_[0];    
    my ($text, $date) = @_;
    my $year = extractYear($date);

    #my $year = substr $date, 0, 4;  
    #**********************************************************************************************
    # Searches for numerical date formats
    # Checks if dates should be filtered
    if ($datefilter =~ /y/) {
	
	# Searches for mm/dd or mm/yy
	while ($text =~ /\b([A-Za-z0-9%\/]+ +)?(\d\d?)([\/\-])(\d\d?)\/?\/?( +[A-Za-z]+)?\b/g) {	      		
	
	    $pre = $1;
	    $post = $5;
	    my $first_num = $2;
	    my $divider = $3;
	    my $second_num = $4;
	    my $postdate = $5;
	   	    
	    my $startI = length($`) + length($pre);
	    my $endI = $startI + length($first_num)+length($divider)+length($second_num);
	    my $key = $startI."-".$endI;
	    
	    my $beginr = substr $text, ($startI - 2), 2;
	    my $endr = substr $text, $endI, 2;
	    
	    #Excludes nn/nn formats when preceded by any in array @prev
	    #@prev = ("cvp", "noc", "peep/ps","%");
	    @prev = ("cvp", "noc", "%", "RR", "PCW");
	    my $dateorno = 1;
	    foreach $j (@prev) {
		if ((!($pre =~ /\b$j/ig)) && (!($post =~ /\bpersantine\b/ig))) {
		}
		else {
		    $dateorno = 0;
		}
	    }

	    my $context_len = 12; #number of characters we extract before the date

	    if ($dateorno == 1) {
		if (($beginr !~ /\d[\/\.\-]/) && ($endr !~ /\A[\%]/) && ($endr !~ /\S\d/)) {
		    
		    # Checks if date identified is valid as mm/dd; then adds the date as PHI
		    if (isValidDate ($first_num, $second_num, -1)) {
			
			if ($second_num == 5) {
			    
			    my $start_pos = $startI - $context_len; 
			    if ($start_pos < 0) {
				$start_pos = 0;
			    }
			    my $len = $context_len;
			    if  (length($text) < ($endI + $context_len)){
				$len = length($text) - $endI;
			    } 
			       
			    my $textBefore = substr $text, $start_pos, ($startI - $start_pos);
			    my $textAfter = substr $text, $endI, $len;

			    
			    if (  (!isProbablyMeasurement($textBefore)) &&   ($textBefore !~ /\bPSV? \Z/i) && ($textBefore !~ /\b(CPAP|PS|range|bipap|pap|pad|rate|unload|ventilation|scale|strength|drop|up|cc|rr|cvp|at|up|in|with|ICP|PSV|of) \Z/i) && ($textAfter !~ /\A ?(packs|psv|puffs|pts|patients|range|scale|mls|liters|litres|drinks|beers|per|esophagus|tabs|pts|tablets|systolic|sem|strength|times|bottles|drop|drops|up|cc|mg|\/hr|\/hour|mcg|ug|mm|PEEP|L|hr|hrs|hour|hours|dose|doses|cultures|blood|bpm|ICP|CPAP|years|days|weeks|min|mins|minutes|seconds|months|mons|cm|mm|m|sessions|visits|episodes|drops|breaths|wbcs|beat|beats|ns)\b/i)) {

				addType ($key, "Month/Day (1)");
			    }
			
			} elsif ($second_num == 2) {
			
			    my $start_pos = $startI - $context_len; 
			    if ($start_pos < 0) {
				$start_pos = 0;
			    }
			    my $len = $context_len;
			    if  (length ($text) < ($endI + $context_len)){
				$len = length($text) - $endI;
			    } 
			    my $textBefore = substr $text, $start_pos, ($startI - $start_pos);
			    my $textAfter = substr $text, $endI, $len;

			   
			    if (   (!isProbablyMeasurement($textBefore)) &&   ($textAfter !~ /\A ?hour\b/i) && ($textBefore !~ /\b(with|drop|bipap|pap|range|pad|rate|unload|ventilation|scale|strength|up|cc|rr|cvp|at|up|with|in|ICP|PSV|of) \Z/i) && ($textAfter !~ /\A ?hr\b/i) && ($textAfter !~ /\A ?(packs|L|psv|puffs|pts|patients|range|scale|dose|doses|cultures|blood|mls|liters|litres|pts|drinks|beers|per|esophagus|tabs|tablets|systolic|sem|strength|bottles|times|drop|cc|up|mg|\/hr|\/hour|mcg|ug|mm|PEEP|hr|hrs|hour|hours|bpm|ICP|CPAP|years|days|weeks|min|mins|minutes|seconds|months|mons|cm|mm|m|sessions|visits|episodes|drops|breaths|wbcs|beat|beats|ns)\b/i)) { 
			   
				
				addType ($key, "Month/Day (2)");
			    }
			#} elsif (($divider eq "-") && ($startI > 4)) {
			} elsif (($divider eq "-")) {
			    my $start_pos = $startI - $context_len; 
			    if ($start_pos < 0) {
				$start_pos = 0;
			    }
			    my $len = $context_len;
			    if  (length ($text) < ($endI + $context_len)){
				$len = length($text) - $endI;
			    } 
			    my $textBefore = substr $text, $start_pos, ($startI - $start_pos);
			    my $textAfter = substr $text, $endI, $len;
			    			    
			    if (isProbablyDate($textBefore, $textAfter)){
				
				addType ($key, "Month/Day (3)");
			    }
			}
			else {

			    my $start_pos = $startI - $context_len; 
			    if ($start_pos < 0) {
				$start_pos = 0;
			    }
			    my $len = $context_len;
			    if  (length ($text) < ($endI + $context_len)){
				$len = length($text) - $endI;
			    } 
			    my $textAfter = substr $text, $endI, $len;  
			    my $textBefore = substr $text, $start_pos, ($startI - $start_pos);
			    			
			   
			    if (isProbablyDate($textBefore, $textAfter)){	
				addType ($key, "Month/Day (4)");
			    }
			}
		    }
		    
		    # Checks if date identified is valid as mm/yy; then adds the date as PHI 
                    # Checks for years of length 2, restricted to 1950-2030
		    if (($first_num <= 12) && ($first_num > 0) && ((length $second_num) == 2) 
			&& (($second_num>=50) || ($second_num<=30))) { 		

			    #my $textAfter = substr $text, $endI, 9; 
			    my $start_pos = $startI - $context_len; 
			    if ($start_pos < 0) {
				$start_pos = 0;
			    }
			    my $len = $context_len;
			    if  (length ($text) < ($endI + $context_len)){
				$len = length($text) - $endI;
			    } 
			    my $textAfter = substr $text, $endI, $len;  
			    my $textBefore = substr $text, $start_pos, ($startI - $start_pos);
			   #  print "checking mm/yy text before is $textBefore, text after is $textAfter\n";
			    if (isProbablyDate($textBefore, $textAfter)){
				addType ($key, "Month/Year (2)");  
			    }
		       } #end if the first num and second num are month/year 

		}
	    }  #end if dateno ==1		    

	} #end while the pattern match
    } # end if datefilter is on
}

#end dateWithContextCheck()

#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
#Function: yearWithContextCheck
#Argument: text string
#Returns: none
#Description: Find date patterns.  Performs context check on text before and after the year patterns
#to determine if it is a year.
sub yearWithContextCheck {
    #$text = $_[0];    
    my ($text, $date) = @_;
    #my $year = substr $date, 0, 4;  
    my $year = extractYear($date);


    # Checks for 2-digit year written as '01, &c, only when preceded by the following medical terms
    while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|avr|x2|x3|CHOLECYSTECTOMY|cva|ca|PTC|PTCA|stent|since|surgery|year) + *(\')?)(\d\d)\b/ig) {
	    my $num = $1;
	    #print "2-digit date, 1 is $1, 2 is $2, 3 is $3, 4 is $4, 5 is $5\n";
	    #my $key = (1 + (length($`))+length($1))."-".(pos $text);
	    my $startd =  (length($`))+length($1);
	    my $endd = $startd + length($4);
	    my $key =  $startd."-".$endd;

	    #check if the match is part of number followed by decimal point and a number
	    my $textAfter = substr $text, $endd, 2;
	    
	    if ($textAfter !~ /\.\d/){
		addType($key, "Year (2 digits)");
		
	    }
     }
	    

     while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|avr|x2|x3|CHOLECYSTECTOMY|cva|ca|PTCA|since|surgery|year)(\'+))(\d\d)\b/ig) {
	    my $num = $1;

	    my $startd =  (length($`))+length($1);
	    my $endd = $startd + length($4);
	    my $key =  $startd."-".$endd;

	    #check if the match is part of number followed by decimal point and a number
	    #or if it is a time (HH:MM)
	    my $textAfter = substr $text, $endd, 2;
	    
	    if ($textAfter !~ /(\.|\:)\d/){
		addType($key, "Year (2 digits)");
	    }
     }

     # Checks for 4-digit year written as 2001, &c, only when preceded by the following medical terms
     while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|x2|x3|CHOLECYSTECTOMY|cva|ca|in|PTCA|since|from|year) + *)(\d{4})((\,? )\d{4})?\b/ig) {
		my $num1 = $1;
		$s1 = length($`) + length($1);
		$e1 = $s1+length($3);
		$s2 = $e1+length($5);
		$e2 = $e1+length($4);
		$k1 = "$s1-$e1";
		$k2 = "$s2-$e2";

		
		#for 4-digit year, check if the matched number is in the range of [$VALID_YEAR_LOW,$VALID_YEAR_HIGH]
		#if ($3 <= 2030 && $3 >= 1950){
		if ($3 <= $VALID_YEAR_HIGH && $3 >= $VALID_YEAR_LOW){
		    addType($k1, "Year (4 digits)");
		    addType($k2, "Year (4 digits)");
	        }
       }
	    
      # Looks for year only (esp Patient Medical History): looks for year numbers within the 30 years before 
      # and 2 years after the date passed in as an argument.
	    
      # for $n (($year - 30) .. $year) {
      for $n (($year - 30) .. ($year+2)) {
		my $short = substr $n, 2, 2;
		if ($n =~ /\d\d\d\d/) {
		while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|x2|x3|CHOLECYSTECTOMY|cva|ca|in|PTCA|since|from|year) + *)$n\b/ig) {
		    my $key = (length($`)+length($1))."-".(pos $text);
		    addType ($key, "Year (4 digits)");
		}}
		if ($short =~ /\d\d/) {
		#while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|x2|x3|CHOLECYSTECTOMY|cva|ca|PTCA|since|from|year) + *(\'?))$short\b/ig) {
		while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|x2|x3|CHOLECYSTECTOMY|cva|ca|PTCA|since|year) + *(\'?))$short\b/ig) {
		    my $key = (length($`)+length($1))."-".(pos $text);
		    addType ($key, "Year (2 digits)");
		}}
		if ($short =~ /\d\d/) {
	#	while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|x2|x3|CHOLECYSTECTOMY|cva|ca|PTCA|since|from|year)(\'+))$short\b/ig) {
		while ($text =~ /\b((embolus|mi|mvr|REDO|pacer|ablation|cabg|x2|x3|CHOLECYSTECTOMY|cva|ca|PTCA|since|year)(\'+))$short\b/ig) {
		    my $key = (length($`)+length($1))."-".(pos $text);
		    addType ($key, "Year (2 digits)");
		}}
	 }

}

#end yearWithContextCheck()




#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
# End of De-Identification Algorithm
#***********************************************************************************************************
#***********************************************************************************************************
#***********************************************************************************************************
