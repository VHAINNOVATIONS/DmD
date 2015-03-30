# CPTest3.pl - illustrate getting properties of an embedded object, Home, in Sample.Person, illustrate looking at property of referenced object
use Intersys::PERLBIND;
$|=1; # set autoflush so output is easier to read
my $id=1;
my $user="_SYSTEM";
my $password="SYS";
my $host = "localhost";
my $port = "1972";

# @ARGV is array of parameters passed to the application via the command line
while (@ARGV) {
    $arg = shift @ARGV;
    if ($arg eq "-id") {
        $id = shift @ARGV;
    } elsif ($arg eq "-user") {
        $user = shift @ARGV;
    } elsif ($arg eq "-password") {
        $password = shift @ARGV;
    } elsif ($arg eq "-host") {
        $host = shift @ARGV;
    } elsif ($arg eq "-port") {
        $port = shift @ARGV;
    } else {
        die "Unknown option: $arg";
    }
}

eval {
    
    # Connect to specified machine, in the SAMPLES namespace
    $conn = Intersys::PERLBIND::Connection->new($host."[$port]:Samples",$user,$password,0);
    $database = Intersys::PERLBIND::Database->new($conn);
    
    # Open an instance of the Sample.Person object
    die "There is no person with id $id in the database." if (!($database->run_class_method("Sample.Person","%ExistsId",$id)));
    $person =  $database->openid("Sample.Person",$id,-1,0);
    
    # Fetch some properties
    print "ID:   ", $person->run_obj_method("%Id"),"\n";
    print "Name: ", $person->get("Name"),"\n";
    print "SSN:  ", $person->get("SSN"), "\n";
    print "DOB:  ", $person->get("DOB"), "\n";
    print "Age: ", $person->get("Age"), "\n";
    
    #Attempt to bring in an embedded object
    my $addr = $person->get("Home");
    print "Street: ", $addr->get("Street"), "\n";
    print "City:   ", $addr->get("City"), "\n";
    print "State:  ", $addr->get("State"), "\n";
    print "Zip:  ", $addr->get("Zip"), "\n";
    
    # look at referenced object
    my $spouse = $person->get("Spouse");
    print "Spouse Name: ",$spouse->get("Name") if defined $spouse;
        
    
};
if ($@) {
    print "Caught exception: $@\n";
} else {
    print "\nSample finished running\n";
}


