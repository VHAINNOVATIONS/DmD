# CPTest6.pl, demonstrate Perl binding
# Demonstrate processing of a result set, ByName query
use Intersys::PERLBIND;
$|=1; # set autoflush so output is easier to read
my $user="_SYSTEM";
my $password="SYS";
my $host = "localhost";
my $port = "1972";
my $query = "A";

# @ARGV is array of parameters passed to the application via the command line
while (@ARGV) {
    $arg = shift @ARGV;
    if ($arg eq "-user") {
        $user = shift @ARGV;
    } elsif ($arg eq "-password") {
        $password = shift @ARGV;
    } elsif ($arg eq "-host") {
        $host = shift @ARGV;
    } elsif ($arg eq "-port") {
        $port = shift @ARGV;
    } elsif ($arg eq "-query") {
        $query = shift @ARGV;
    } else {
        die "Unknown option: $arg";
    }
}

eval {
    
    # Connect to specified machine, in the SAMPLES namespace
    $conn = Intersys::PERLBIND::Connection->new($host."[$port]:Samples",$user,$password,0);
    $database = Intersys::PERLBIND::Database->new($conn);
    
    # create a query
    print "Creating a query\n";
    $cq = $database->alloc_query();
    $sqlcode=0;
    $cq->prepare_class("Sample.Person", "ByName", $sqlcode);
    $cq->set_par(1,$query);
    $cq->execute($sqlcode);
    while (@cols = $cq->fetch($sqlcode)) {
        # dump the columns in each row
        $line = join ":", @cols;
        print "$line\n";
    }
    
};
if ($@) {
    print "Caught exception: $@\n";
} else {
    print "\nSample finished running\n";
}


