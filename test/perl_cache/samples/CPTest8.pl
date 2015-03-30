# CPTest8.pl - illustrate processing employee subclass and company/employee relationship
use Intersys::PERLBIND;
$|=1; # set autoflush so output is easier to read
my $id=101;
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
    
    # Open an instance of the Sample.Employee object
    die "There is no employee with id $id in the database." if (!($database->run_class_method("Sample.Employee","%ExistsId",$id)));
    $employee =  $database->openid("Sample.Employee",$id,-1,0);
    
    # Fetch some properties
    print "Name: ", $employee->get("Name"),"\n";
    print "SSN:  ", $employee->get("SSN"), "\n";
    
    # Display existing values
    print "Existing Address:\n";
    my $addr = $employee->get("Home");
    print "Street: ", $addr->get("Street"), "\n";
    print "City:   ", $addr->get("City"), "\n";
    print "State:  ", $addr->get("State"), "\n";
    print "Zip:  ", $addr->get("Zip"), "\n";
    
    # look at referenced object
    my $spouse = $employee->get("Spouse");
    print "Spouse Name: ",$spouse->get("Name") if defined $spouse;

    $company = $employee->get("Company");

    print "Works at: " , $company->get("Name"), "\n";
    print "Title:  " , $employee->get("Title"), "\n";
    print "Salary: " , $employee->get("Salary"), "\n";

    $colleagues = $company->get("Employees");
    # Iterate over the colleagues relationship */
    print "Number of colleagues: ",$colleagues->run_obj_method("Count"), "\n";
    do {
        $colleague = $colleagues->run_obj_method("GetNext",$i);
        #print "    i=$i\n";
        print "    ","colleague # $i: ",$colleague->get("Name"),"\n" if defined($colleague);
        
    } while (defined($colleague));
    
    $employee->set("Name", $employee->get("Name"));
    $employee->run_obj_method("%Save");
   

    # Save the changes made to this object instance
    # If there is a problem with the save, such as a key value not
    # being unique, then an exception will be thrown and caught by the
    # eval block.
       
    $employee->run_obj_method("%Save");
    
};
if ($@) {
    print "Caught exception: $@\n";
} else {
    print "\nSample finished running\n";
}
