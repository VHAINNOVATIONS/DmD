# CPTest2.pl illustrate getting and setting properties of an instance of Sample.Person
use Intersys::PERLBIND;
$|=1; # set autoflush so output is easier to read
my $user="_SYSTEM";
my $password="SYS";
my $host = "localhost";
my $port = "1972";

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
    } else {
        die "Unknown option: $arg";
    }
}

eval {
    srand(time|$$);
    $conn = Intersys::PERLBIND::Connection->new(${host}."[$port]:Samples",$user,$password,0);
    $database = Intersys::PERLBIND::Database->new($conn);
    # Create a new instance of Sample.Person
    $person =  $database->create_new("Sample.Person", undef);
    # Set some properties
    $person->set("Name","Doe, Joe A");
    $person->set("SSN", &generateSSN());
    print "Name: ",$person->get("Name"), "\n";
    print "SSN: ",$person->get("SSN"), "\n";
    # Save instance of Person
    $person->run_obj_method("%Save");
    print "Saved id: ", $person->run_obj_method("%Id"),"\n";
    # Create a new instance of Sample.Person to be spouse
    $spouse =  $database->create_new("Sample.Person", undef);
    $spouse->set("Name","Doe, Mary");
    $spouse->set("SSN", &generateSSN());
    print "Name: ",$spouse->get("Name"), "\n";
    print "SSN: ",$spouse->get("SSN"), "\n";
    $person->set("Spouse",$spouse);
    $person->run_obj_method("%Save");
    # Save instance of Person
    $spouse->set("Spouse",$person);
    $spouse->run_obj_method("%Save");
    print "Saved id: ", $spouse->run_obj_method("%Id"),"\n";
    
    # empty field
    print "DOB is empty as expected\n" if (!defined($person->get("DOB"))) ;
};
if ($@) {
    print "Caught exception: $@\n";
} else {
    print "\nSample finished running\n";
}

sub generateSSN() {
    my $ssn="";
    $ssn .= int(rand(10));
    $ssn .= int(rand(10));
    $ssn .= int(rand(10));
    $ssn .= "-";
    $ssn .= int(rand(10));
    $ssn .= int(rand(10));
    $ssn .= "-";
    $ssn .= int(rand(10));
    $ssn .= int(rand(10));
    $ssn .= int(rand(10));
    $ssn .= int(rand(10));
    return $ssn;
    
}
