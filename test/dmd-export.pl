#!/usr/bin/perl
# set up and execute mlcp for export of test xml files from dmd-alpha
# written by: BC
# date: 20141211
# email: william.collins@va.gov 

my $mlcp="../util/mlcp/bin/mlcp.sh";
my $username="bciv";
my $password="at0mic!!";
my $host='localhost';
my $port='8776';
my $export_file_path="/opt/dmd/test/export";

my $cmd="$mlcp export -host $host -port $port -username $username -password $password -mode local -output_file_path $export_file_path -compress true";
print "$cmd\n";
system($cmd);

