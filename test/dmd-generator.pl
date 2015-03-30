#!/usr/bin/perl
#use strict;
#use warnings;
# Purpose: generate test files for ingestion into marklogic database
# Written by: Will BC Collins IV
# Email: william.collins@va.gov

#use Date::Day;
use POSIX;
use constant DATETIME => strftime("%Y-%m-%d\@%H:%M:%S",localtime);

# -------------------- user configurable options ------------------------

my $output_directory="importdir";

my $number_of_files_to_generate=250;

# -------------------- end of user options ------------------------------

# define data dictionary list I found here: http://www-01.sil.org/linguistics/wordlists/english/wordsEn.txt
# load dictionary to array
my $dictionary='lib/wordsEn.txt'; my @words=load_dictionary($dictionary);
my $number_of_words=@words;
print "Number of words: $number_of_words\n";

my $id=0;

create_number_of_files($number_of_files_to_generate);

sub create_number_of_files{
    my ($num)=@_;
    print "Creating $num xml files...";
    for(my $i=0; $i<$num; ++$i){create_xml_file();}
}

sub create_xml_file{
    my $data; my $stamp=DATETIME;
    my $name=random_word();
    my $sentence=random_sentence();
    my $paragraph=random_paragraph();
    my $filename="$output_directory/test-$id-$name.xml";
    print "creating '$filename'...\n";
    $data="<?xml version \"1.0\"?>\n";
    $data.="<test>\n";
    $data.="  <item id='".++$id."'>\n";
    $data.="    <name>$name</name>\n";
    $data.="    <timestamp>$stamp</timestamp>\n";
    $data.="    <description>$sentence</description>\n";
    $data.="    <payload>$paragraph</payload>\n";
    $data.="  </item>\n";
    $data.="</test>\n";
    open OUT, '>:encoding(UTF-8)',$filename or die "Unable to create $filename";
    print OUT $data;
    close OUT;
}

sub random_paragraph{
  my $retval; for (my $i=0; $i<6; ++$i){$retval.='  '.random_sentence();}
  $retval=~s/^\s\s//; return $retval;
}

sub random_sentence{
  my $retval; for (my $i=0; $i<20; ++$i){$retval.=' '.random_word();}
  $retval.='.'; $retval=~s/^\s//; $retval=~s/^([a-z])/\u$1/;
  return $retval;
}

# return a random word
sub random_word{
    my $num=random_number();
    my $word=$words[$num];
    return $word;
}

# return a random number
sub random_number{
    return int(rand($number_of_words));
}

# list all the words in the dictionary
sub list_words{
  foreach my $word (@words){ print $word.' ';}
}

# creates an array containing all of the words in the english dictionary that were
# from here: http://www-01.sil.org/linguistics/wordlists/english/wordsEn.txt
# returns array
sub load_dictionary{
  my ($dictionary_file)=@_;
  open(my $fh, '<',$dictionary_file) or die "Could not open dictionary '$dictionary_file' $!";
  while (my $word=<$fh>){
    # remove crap from end of word because chomp ate everything when I tried it;
    $word=~s/(\n|\r|\x0d)//g;
    push @dictionary,$word;
#    print "pushed '$word' to array\n";  
  }
  close($fh);
  return @dictionary;
}

sub create_file{
 #   my 
}

