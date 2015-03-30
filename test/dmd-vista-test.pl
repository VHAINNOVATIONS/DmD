#!/usr/bin/perl
use RPC; 

my $host='23.23.185.153';
my $port='9210';

my $conn = RPC->connect($host, $port);
my $answer = $conn->rpc('ask_sheep', 
                        "Ba ba black sheep, have you any wool ?");
print "$answer\n";

The client sets up an RPC connection, given a host and port. A subroutine that is normally invoked as

$answer = ask_sheep ($question);

is invoked by using RPC as follows:

$answer = $conn->rpc ("ask_sheep", $question);

The client code knows it is making an RPC call. Making this transparent (as typical RPC systems do) is quite simple, really. Using eval , we can dynamically create a dummy client stub called ask_sheep on the caller's side and have it make the call to rpc() .

The called subroutine, however, does not know whether it has been invoked locally or from a remote process (unless of course, it uses caller() to find out).

The remote process (call it the RPC server) provides the required subroutines and invokes new_server and event_loop to accept incoming RPC calls; ask_sheep will get called at the right time. Simple!

# Server stuff
RPC->new_rpc_server($host, $port);
RPC->event_loop();

sub ask_sheep {  # Sample subroutine to be invoked from client
    print "Question: @_\n";
    return "No";
}
