#!/usr/bin/perl
# set up and execute mlcp for import of test xml files
# written by: BC
# date: 20141211
# email: william.collins@va.gov 

my $mlcp="../util/mlcp/bin/mlcp.sh";
my $username="bciv";
my $password="at0mic!!";
my $host='localhost';
my $port='8776';
my $input_file_path="/opt/dmd/test/import";
my $input_file_pattern="\'>\.xml\'";

my $cmd="$mlcp import -host $host -port $port -username $username -password $password -input_file_path $input_file_path -mode local -input_file_pattern '.*\.xml'";
print "$cmd\n";
system($cmd);
 
