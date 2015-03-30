# CPTest4.pl - illustrate updating embedded object in instance of Sample.Person
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
    print "Name: ", $person->get("Name"),"\n";
    print "SSN:  ", $person->get("SSN"), "\n";
    
    # Display existing values
    print "Existing Address:\n";
    my $addr = $person->get("Home");
    print "Street: ", $addr->get("Street"), "\n";
    print "City:   ", $addr->get("City"), "\n";
    print "State:  ", $addr->get("State"), "\n";
    print "Zip:  ", $addr->get("Zip"), "\n";
    

    # Modify some values 
    $addr->set("Street", "One Memorial Drive" );
    $addr->set("City", "Cambridge" );
    $addr->set("State", "MA" );
    $addr->set("Zip", "02142" );

    # Display the new values 
    print  "New Address:\n";
    print  "Street: ", $addr->get("Street") ,"\n";
    print  "City:   ", $addr->get("City") ,"\n";
    print  "State:  ", $addr->get("State") ,"\n";
    print  "Zip:    ", $addr->get("Zip") ,"\n";

    # Save the changes made to this object instance
    # If there is a problem with the save, such as a key value not
    # being unique, then an exception will be thrown and caught by the
    # eval block.
       
    $person->run_obj_method("%Save");
    
};
if ($@) {
    print "Caught exception: $@\n";
} else {
    print "\nSample finished running\n";
}

