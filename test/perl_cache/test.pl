# Before `make install' is performed this script should be runnable with
# `make test'. After `make install' it should work as `perl test.pl'

#########################

# change 'tests => 1' to 'tests => last_test_to_print';

use Test;
BEGIN { plan tests => 3 };
use Intersys::PERLBIND;
ok(1); # If we made it this far, we're ok.

#########################

# Insert your test code below, the Test module is use()ed here so read
# its man page ( perldoc Test ) for help writing this test script.
$|=1; # set autoflush so output is easier to read
print "Enter port for Cache' or enter line feed for default of 1972\n";
chomp($port = <STDIN>);
$port = 1972 if $port eq "";
eval {
    $conn = Intersys::PERLBIND::Connection->new("127.0.0.1[$port]:Samples","_SYSTEM","SYS",0);
    $database = Intersys::PERLBIND::Database->new($conn);
    $object =  $database->openid("Sample.Person", "1", -1, -1);
    $ans = $object->run_obj_method("Addition", 17, 20);
    ok($ans,37);
};
if ($@) {
    print "test failed\n";
    print "error message is $@\n";
    ok(0);
} else {
    ok(1);
}
