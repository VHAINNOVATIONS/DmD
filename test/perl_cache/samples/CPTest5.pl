# CPTest5.pl, demonstrate Perl binding
# Demonstrate processing of datatype collections
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
  
    # Iterate over the FavoriteColors collection */
    $colors = $person->get("FavoriteColors");
    print "Number of colors: ",$colors->get("Size"), "\n";
    do {
        $color = $colors->run_obj_method("GetNext",$i);
        print "    Element # $i -> $color\n" if defined($i);
    } while (defined($i));
    
    print("Modifying 'FavoriteColors' ...\n");
    
    # Remove the first element
    $colors->run_obj_method("RemoveAt", 1) if $colors->get("Size") > 0;
    
    # Insert a new element
    $colors->run_obj_method("Insert","red");
    
    # Show the changes to the collection
    do {
        $color = $colors->run_obj_method("GetNext",$i);
        print "    Element # $i -> $color\n" if defined($i);
    } while (defined($i));
    
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



