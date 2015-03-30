use Intersys::PERLBIND;
use utf8;

$|=1; # set autoflush so output is easier to read
#Intersys::PERLBIND::setlocale(0,"English");
my $user="_SYSTEM";
my $password="SYS";
my $host = "localhost";
my $port = "1972";

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
    } else {
        die "Unknown option: $arg";
    }
}



$version = Intersys::PERLBIND::get_client_version();
print "version=$version\n";
$conn = Intersys::PERLBIND::Connection->new($host."[$port]:SAMPLES",$user,$password,0);
if ($conn->is_two_factor_enabled()) {
        my $input = <>;
        chomp($input);
        if ($conn->send_two_factor_token($input)) {
                print "two factor authentication succeeded\n";
        } else {
                print "two factor authentication failed\n";                
        }
} else {
        print "two factor authentication disabled\n";
}
print "connection=$conn\n";
my $database = Intersys::PERLBIND::Database->new($conn);
print "database->refcnt=".$database->refcnt(),"\n";
