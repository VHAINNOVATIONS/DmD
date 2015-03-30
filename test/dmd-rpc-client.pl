#!/usr/bin/perl -w
use strict;
use Socket; #IO::Socket::INET;
# auto-flish on socket
#$|=1;

# initialize host and port
my $host = shift || 'localhost';
my $port = shift || 9210;
my $server = 'vista1.vaftl.us';

# create the socket, connect to the port
socket(SOCKET,PF_INET,SOCK_STREAM,(getprotobyname('tcp'))[2]) 
  or die "Can't create a socket $!\n";

print "Created socket...\n";

connect(SOCKET,pack_sockaddr_in($port,inet_aton($server)))
  or die "Can't connect to port $port!\n";

print "Connected to $server...\n";
my $cmd="[XUS]16XUS SIGNON SETUP\nM";
print SOCKET $cmd;
print "sent $cmd\n";
my $line=<SOCKET>;
while ($line=<SOCKET>){
  print "$line\n";  
}

close SOCKET or die "close $!";


