package Intersys::PERLBIND;

use 5.006;
use strict;
#use warnings;
use Carp qw(croak);

require Exporter;
require DynaLoader;

our @ISA = qw(Exporter DynaLoader);

# Items to export into callers namespace by default. Note: do not export
# names by default without a very good reason. Use EXPORT_OK instead.
# Do not simply export all your public functions/methods/constants.

# This allows declaration	use Intersys::PERLBIND ':all';
# If you do not need this, moving things directly into @EXPORT or @EXPORT_OK
# will save memory.
our %EXPORT_TAGS = ( 'all' => [ qw(
	
) ] );

our @EXPORT_OK = ( @{ $EXPORT_TAGS{'all'} } );

our @EXPORT = qw(
	
);
our $VERSION = '0.01';

bootstrap Intersys::PERLBIND $VERSION;

# Preloaded methods go here.
sub pack {
    my $template = shift(@_);
    pack $template, @_;
}

sub unpack {
    my ($template, $expr)=@_;
    unpack $template, $expr;
}

package PDATE_STRUCTPtr;
use overload '""' => "stringify";

sub stringify {
    my $self = shift;
    return $self->toString();
}

sub parse {
    my ($date,$dateptr) = @_;
    if ($date =~ /^(\d+)-(\d+)-(\d+)$/) {
        $dateptr->set_year($1);
        $dateptr->set_month($2);
        $dateptr->set_day($3);
        return 0;
    } else {
        return 1;
    }
    
}

package PTIME_STRUCTPtr;
use overload '""' => "stringify";

sub stringify {
    my $self = shift;
    return $self->toString();
}

sub parse {
    my ($time,$timeptr) = @_;
    if ($time =~ /^(\d+):(\d+):(\d+)$/) {
        $timeptr->set_hour($1);
        $timeptr->set_minute($2);
        $timeptr->set_second($3);
        return 0;
    } else {
        return 1;
    }
    
}

package PTIMESTAMP_STRUCTPtr;
use overload '""' => "stringify";

sub stringify {
    my $self = shift;
    return $self->toString();
}

sub parse {
    my ($timestamp,$timestampptr) = @_;
    $timestampptr->set_hour(0);
    $timestampptr->set_minute(0);
    $timestampptr->set_second(0);
    $timestampptr->set_fraction(0);
    
    if ($timestamp =~ /^(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)\.(\d+)$/) {
        $timestampptr->set_year($1);
        $timestampptr->set_month($2);
        $timestampptr->set_day($3);
        $timestampptr->set_hour($4);
        $timestampptr->set_minute($5);
        $timestampptr->set_second($6);
        $timestampptr->set_fraction($7);
        return 0;
    } elsif ($timestamp =~ /^(\d+)-(\d+)-(\d+)$/) {
        $timestampptr->set_year($1);
        $timestampptr->set_month($2);
        $timestampptr->set_day($3);
            
    } elsif ($timestamp =~ /^(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)$/) {
        $timestampptr->set_year($1);
        $timestampptr->set_month($2);
        $timestampptr->set_day($3);
        $timestampptr->set_hour($4);
        $timestampptr->set_minute($5);
        $timestampptr->set_second($6);
    } else {
        return 1;
    }
    
}

package Intersys::PERLBIND;

sub get_implementation_version {
        "1.0.2";
}


package Intersys::PERLBIND::Database;

package Intersys::PERLBIND::ObjectHash;

sub TIEHASH {
    my $pkg= shift @_;
    my $self = { @_ };
   return bless($self,$pkg);
}

sub ourtie {
    my $self = shift @_;
    my %hash = ();
    tie %hash , "Intersys::PERLBIND::Object", object=>$self;
    return %hash;
}

sub EXISTS {
    my ($self, $property) = @_;
    print "EXISTS\n";
    return 1 if $self->{_object}->is_property($property);
    return 0;
    
}

sub DELETE {
    my ($self, $key) = @_;
    Carp::croak("cannot delete $key on $self\n");
}

sub FIRSTKEY {
    my $self = shift;
    my @props = $self->get_properties();
    return $props[0];
}

sub NEXTKEY {
    my ($self,$lastkey)=@_;
    my @props = $self->get_properties();
    my $index = 0;
    my $i;
    for ($i = 0; $i < @props; $i++) {
        if ($lastkey eq $props[$i])  {
            $index = $i;
            last;
        }
    }
    if ($index +1 < scalar(@props)) {
        return $props[$index+1];
    } else {
        return undef;
    }
}

#sub CLEAR {
#}

sub FETCH {
    my ($self, $key) = @_;
    Carp::croak("$key is not a property on a $self") unless ($self->{_object}->is_property($key)==1);
    my $result = $self->{_object}->get($key);
    return $result;
}

sub STORE {
    my ($self, $key, $value) = @_;
    Carp::croak("$key is not a property on a $self") unless ($self->{_object}->is_property($key)==1);
    $self->{_object}->set($key,$value);
}

sub AUTOLOAD
{
    no strict "refs";
    # set $struct = $$self, see if set or get exists, if it does call it
    my ($self) = @_;
    my $rtn = our $AUTOLOAD;
    $rtn =~ s/.*:://;
    if ($rtn ne "DESTROY") {
        if ($self->{_object}->can($rtn) || $self->{_object}->is_method($rtn)) {
            *$AUTOLOAD = sub { # define rtn in symbol table, so no more need to AUTOLOAD it
                my ($self) = @_;
                shift @_;
                $self->{_object}->$rtn(@_);
            };
            goto &$AUTOLOAD # restart routine
        } else {
            Carp::croak("No such method as $rtn");
        }
    } else {
#        print "in destroy from AUTOLOAD\n;"
    }
}

package Intersys::PERLBIND::Object;

sub AUTOLOAD
{
    no strict "refs";
    # set $struct = $$self, see if set or get exists, if it does call it
    my ($self) = @_;
    my $rtn = our $AUTOLOAD;
    $rtn =~ s/.*:://;
    if ($rtn ne "DESTROY") {
        if ($self->is_method($rtn)) {
            *$AUTOLOAD = sub { # define rtn in symbol table, so no more need to AUTOLOAD it
                my ($self) = @_;
                shift @_;
                $self->run_obj_method($rtn,@_);
            };
            goto &$AUTOLOAD # restart routine
        } else {
            Carp::croak("No such method as $rtn");
        }
    } else {
#        print "in destroy from AUTOLOAD\n;"
    }
}

package Intersys::PERLBIND::Status;

use overload '0+' => 'make_number', '""' => 'stringify', '+' => 'add';

sub make_number {
    my $self = shift;
    return $self->toCode();
}

sub stringify {
    my $self = shift;
    return $self->toString();
}

sub code {
    my $self = shift;
    return $self->toCode();
}

sub add {
    my ($x, $y) = @_;
    my $ref=ref($y);
    my ($value) = (ref($x) && $x->isa("Intersys::PERLBIND::Status")) ? code($x) : $x;
    $value += (ref($y) && $y->isa("Intersys::PERLBIND::Status")) ? code($y) : $y;
    return $value;
}

package Intersys::PERLBIND::Decimal;

use overload '0+' => 'make_number', '""' => 'stringify';

sub stringify {
    my $self = shift;
    return "".($self->{_significand} * (10**$self->{_exponent}))
}

sub make_number {
   my $self = shift;
   return $self->{_significand} * (10**$self->{_exponent})        
}

sub get_significand {
    my $self = shift;
    return $self->{_significand};
}

sub get_exponent {
    my $self = shift;
    return $self->{_exponent};
}

sub parsedecimal {
    my ($number,$decimal) = @_;
    #$decimal->{_significand} = $x;
    #$decimal->{_exponent} = $y;

    return 0;

    
}

package Intersys::PERLBIND;
1;
__END__

=pod

=head1 NAME

Intersys::PERLBIND - Perl binding for Cache'

=head1 SYNOPSIS

use Intersys::PERLBIND;

This module requires 5.6 of Perl.

=head1 DESCRIPTION

Using the Perl binding:

=head2 RUNNING

Note you will need INSTALLDIR\bin in your PATH (or INSTALLDIR/bin) where INSTALLDIR is the place where you've installed Cache'.  It might be c:\cachesys\bin or /usr/cachesys/bin.  The reason is you need our cbind.dll, our C++ binding, and our ODBC driver, all in your path.  These are in INSTALLDIR\bin.

=head2 Getting version of InterSystems Perl binding

 $version = Intersys::PERLBIND->get_implementation_version();
 print "version=$version\n";

=head2 Creating a Connection to a Database

Just like in ODBC you need to create a connection and a database:

For example:

 $conn = Intersys::PERLBIND::Connection->new("localhost[1972]:Samples","_SYSTEM","SYS",0);

A connection has two uses.  One is to get a database.  The other is to use two-factor authentication.

Here is an example of getting a database.
   
 $database = Intersys::PERLBIND::Database->new($conn);

Here is an example of using two-factor authentication.

 // Given a connection called "conn"
 if ($conn->is_two_factor_enabled()) {
        # Prompt the user for the security token.
        # Store the token in the "token" variable of type string.
  if (!$conn->send_two_factor_token($token)) {
      # Process the error from a invalid authentication token here.
  } else {
      # two-factor authentication succeeded
  }
 else {
      # Handle if two-factor authentication is not enabled on the server.
  } 


Here is the syntax for getting a connection:

 $conn = Intersys::PERLBIND::Connection->new(<hoststring>,userid,password,timeout);

<hoststring> has the format <hostname>[<port>]:<NameSpace>

The default value for timeout is 0, which means no timeout.

=head2 Creating and Opening an object

Once you have a database you can create or open an object:

 $object =  $database->openid("Sample.Person", "1", -1, 0);

opens an object.

here is the syntax:

 $object = $database->openid(<ClassName>, <ID>, <concurrency>, <timeout> )

 -1 is the default value of <concurrency>.

 <timeout> is ODBC query timeout.
           
Here is how you create an object:

 $object =  $database->create_new("Sample.Person",undef);

 $object = $database->create_new(<ClassName>,<InitialValue>)

=head2 Running Methods

Once you have an object you can run methods on it and get the properties:

Here are some examples of running methods:

 $ans = $object->run_obj_method("Addition", 17, 20);

 $ans = $object->Addition(17,20);

 $ans = $object->run_obj_method(<MethodName>,<Args>)

 $ans = $object-><MethodName>(<Args>)

<Args> is a Perl list.

One can also run class methods, for example,

 $person = $database->run_class_method("Sample.Person","%OpenId",1);

By running methods such as %OpenId and %New you can see there are other ways of newing and creating objects.

 $result = $database->run_class_method(<ClassName>,<MethodName>,<Args>)

<Args> is a Perl list.

=head2 Getting and Setting Properties

One can also get and set properties:

For example,

    $name = $person->get("Name");
    print "person.name=$name\n";
    $person->set("Name","Adler, Mortimer");

The syntax is:

    $value = $object->get(<PropertyName>)

    $object->set(<PropertyName>,$value)

Note: Private and multidimensional properties are not accessible through the Perl binding.             

=head2 %TIME, %DATE, and %TIMESTAMP

If an argument, returntype, or property is of type %TIME, %DATE, or %TIMESTAMP there is a special API.

On times, we support get_hour(), get_minute(), and get_second() to get the values in a time.  And to set them, we have set_hour(value), set_minute(value), and set_second(value).  We have $time->toString() to convert the time to a string: hh:mm:ss.

For dates, we support get_year(), get_month(), get_day() to get the values in a date.  And to set them, we have set_year(value), set_month(value) and set_day(value).  And we have $date->toString() to convert the date to a string: yyyy-mm-dd.

For timestamps, we support get_year(), get_month(), get_day(), get_hour(), get_minute(), get_second(), and get_fraction().  And to set them, we have set_year(value), set_month(value), set_day(value), set_hour(value), set_minute(value), set_second(value), and set_fraction(value).  And we have $timestamp->toString() to convert the timestamp to a string yyyy-mm-dd hh:mm:ss.fffffffff.

Here are some examples of using times, dates, and timestamps:

    $date = $object->get("MyDate");
    print "date=$date\n"; # when interpolated a date becomes a string rather than a reference through overloading
    $timestamp = $object->get("MyTimeStamp");
    print "timestamp=$timestamp\n"; # when interpolated a timestamp becomes a string rather than a reference through overloading
    $time = $object->get("MyTime");
    print "time=$time\n"; # when interpolated a time becomes a string rather than a reference through overloading
    # we can set a date through accessors
    $date->set_year("2003");
    $date->set_month("2");
    $date->set_day("4");
    $object->set("MyDate", $date);
    # or we can set a date through a string
    $object->set("MyDate","2003-2-4");
    $date = $object->get("MyDate");
    print "date=$date should be 2003-02-04\n";  # note how date is a string when using string interpolation
    # we can set a time through accessors
    $time->set_hour(13);
    $time->set_minute(38);
    $time->set_second(12);
    $object->set("MyTime", $time);
    # or we can set a time through a string
    $object->set("MyTime,"13:38:12");
    $time = $object->get("MyTime");
    print "time=$time should be 13:38:12\n"; # note how time is a string when using string interpolation
    # We can set a timestamp through accessors
    $timestamp->set_year("2003");
    $timestamp->set_month("2");
    $timestamp->set_day("4");
    $timestamp->set_hour(13);
    $timestamp->set_minute(38);
    $timestamp->set_second(12);
    $object->set("MyTimeStamp", $timestamp);
    # or we can set a timestamp through a string
    $object->set("MyTimeStamp","2003-02-04 13:38:12.0000");
    $timestamp = $object->get("MyTimeStamp");
    print "timestamp=$timestamp should be 2003-02-04 13:38:12.0000\n"; # note how timestamp is a string when using string interpolation

=head2 Saving an object:

To save an object use the %Save method

   $obj->run_obj_method("%Save")

To get the id of a saved object use the %Id method

   $id = $obj->run_obj_method("%Id")

=head2 Exceptions

The Perl binding uses Perl exceptions to return errors from the C binding and elsewhere.

Here are some examples of using Perl exceptions:

    eval { # demonstrate Perl exception handling
        $ans = $variant2->run_obj_method("PassLastByRefAdd17","10","goodbye");
    };
    if ($@) {
        print "Perl exception $@\n";
    }
    eval { # demo2 of Perl exception handling
        $causeException = $database2->openid("NonExistent", "1", -1, 0);
    };
    if ($@) {
        print "Perl exception $@\n";
    }

=head2 Null support

We've programmed the Perl binding so that Cache' null (i.e., "") corresponds to Perl undef. 

Perl has the notion of an empty string - "" but this is not the same as Cache' null.  Cache' null corresponds to undef.

=head2 Collection support

We support collections through methods on the collection object.

For instance, the following illustrates how one would program favorite colors.

    $favorites = $person->get("FavoriteColors");
    print "favorites=$favorites\n";
    $index="";
    do {
        $color = $favorites->run_obj_method("GetNext",$index);
        print "index=$index color=$color\n";
    } while ($index != "");

The above code most closely resembles Cache' code but note that Perl counts undefs as == to "" and to 0.  This is because "==" is a numeric operator and how Perl does numeric conversions.  So the above can also be written:

    $index=undef;
    do {
        $color = $favorites->run_obj_method("GetNext",$index);
        print "index=$index color=$color\n";
    } while (defined($index));

=head2 Relationship Support

Relationships are supported through the relationship object and its methods.

Here are some examples:

    # scanning a relationship
    $company = $database->openid("Sample.Company", "1", -1, 0);
    $employees = $company->get("Employees");
    $index="";
    do {
        $employee = $employees->run_obj_method("GetNext",$index);
        if ($index != "") {
            $name = $employee->get("Name");
            $title = $employee->get("Title");
            $company = $employee->get("Company");
            $companyName = $company->get("Name");
            $SSN = $employee->get("SSN");
            if ($SSN =~ /\d\d\d-\d\d-(\d\d\d\d)/) {
                $last4=$1;
            }
            $max = $last4 if ($last4 > $max);
            print "index=$index employee name=$name SSN=$SSN title=$title companyname=$companyName\n";
        }
        }
    } while ($index != "");



We can also insert an object into the child relationship object and then save the parent to save object in the children.

    # inserting an employee into a relationship

    $employees->run_obj_method("Insert", $employee);
    $company->run_obj_method("%Save");

=head2 Error reporting

When processing an argument or a return value, errors messages from the C binding are specially formatted by the Perl binding layer.

Here is a sample error message:

   file=PERLBIND.xs line=71 err=-1 message=cbind_variant_set_buf() cpp_type=4 var.cpp_type=-1 var.obj.oref=1784835886 class_name=%Library.RelationshipObject mtd_name=GetNext argnum=0

We indicate the file where we failed, the line number of the fail, the return code from the C binding, the C binding error message, the cpp type of the method argument or return type, the variant cpp type, the variant oref, the class name of the object on which the method is invoked, the method name, and the argument number.  0 is the first argument and -1 indicates the return value.

This information can be used by WRC to help diagnose the customer problem or Perl binding / C binding issue.

=head2 Support for %Binary data

For data that is %Binary whether as method arguments or property types, the Perl binding works as follows.

On return the data is returned using the Perl pack built-in and the template is "c*".  On input the Perl binding expects the data to be in pack format with the template as "c*" and it uses the Perl built-in unpack to format the data for Cache'.

Each character unpacked by unpack() represents the original binary data as a Perl integer between 1 and 255.  One does not apply ord to the returned character to find out what it really is.

Suppose you have binary data stored on Cache' that equals "hello".

You have it stored as a property B that is %Binary.

You want to change the first letter to "j" so that it becomes "jello"

You have

$b = $db->openid("User.Bin",1,-1,0);
$pack = $b->get("B");
@B = unpack("c*",$pack);
$B[0] = ord("j");
$pack = pack("c*",@B);
$b->set("B",$pack);
$b->run_obj_method("%Save");

unpack()/pack() are just meant to be complementary routines for turning binary data into an array of ords (this is what "c*" means) and turning an array of ords back into binary data.

Here is another example:

    $pack = $testPerl->run_obj_method("GetBinary");
    @unpack = unpack("c*",$pack);
    foreach $c (@unpack) {
        printf "c=%c\n",$c
    }
    $testPerl->run_obj_method("SetBinary",$pack);

The output is the following:

    c=h
    c=e
    c=l
    c=l
    c=o

and in ^foobar is written "hello".

Note that in the above the "%c" turns an ord value into a character.

The Cache' methods in the above are the following:

    Method GetBinary() As %Binary
    {
        q "hello"
    }

    Method SetBinary(x AS %Binary)
    {
        s ^foobar=x
    }

=head2 Date/Time Interpolation
 
We overload the string operator "" so that when interpolated dates, times, and timestamps appear as strings.

For example,

 $date = $variant->get("DOB");
 print "date=$date\n";

appears as follows:

 date=1902-12-25

We allow dates, times, and timestamps to be set from strings.

Dates are in year-month-day format.  Times are in Hours:Minutes:Seconds format.  Timestamps are in year-month-day<space>Hours:Minutes:Seconds.Fractions format.

Here are some examples:

 $variant->set("DOB","2003-12-24");  # set %Date field DOB (Date of Birth)

 $regr->set("MyTime","12:00:01"); # set %Time field 1 minute after 12

 $regr->set("MyTimeStamp","2003-02-04 13:38:12.0000"); # set %Timestamp, note final fraction

=head2 Tied variables and Perl binding

We support tieing an object returned by the Perl binding to a hash and then accessing the properties of the object through the hash.

For instance,

 $object =  $database->openid("Sample.Person", "1", -1, 0);
 $person = tie %person,"Intersys::PERLBIND::ObjectHash",( _object => $object)
 $name = $person{"Name"};
 $person{"Name"} = "Tregar, Sam"; # this is equivalent to $person->set("Name","Tregar, Sam");

Instead of getting the the name of person through $person->get("Name"), one can use the tie to get it through the hash - $person{"Name"}.

One can use the return value from the tie to run methods or one can use the "tied" built-in of Perl to run methods, for example:

 $ans = $person->Addition(12,17);
 print "ans=$ans\n";
 $ans = tied(%person)->Addition(12,17);
 print "ans=$ans\n";

In both cases 29 is returned.

For more information about ties, read any book on Perl.

We support walking the properties through the tie, so one can do the following:

 while  (($property, $value ) = each(%person)) {
     print "propety=$property value=$value\n";
 }

Here is a complete example:

    $database = Intersys::PERLBIND::Database->new($conn);
    $personobj =  $database->openid("Sample.Person", "1", -1, 0);
    
    $person = tie %person,"Intersys::PERLBIND::ObjectHash",( _object => $personobj);
    while (($propname, $value) = each(%person)) {
            print "property $propname = $value\n";
    }

and this produces the output:

    property Age = 61
    property DOB = 1942-01-18
    property SSN = 295-62-8728
    property Home = Intersys::PERLBIND::Object=SCALAR(0x1831ee4)
    property Name = Adler, Mortimer
    property Office = Intersys::PERLBIND::Object=SCALAR(0x183eed0)
    property Spouse = 
    property FavoriteColors = Intersys::PERLBIND::Object=SCALAR(0x1831e3c)

The above code will display each property and its value.

=head2 %Decimal support

The Perl binding provides support for the Cache' %Decimal type through defining Perl objects of type Intersys::PERLBIND::Decimal.

Suppose we have a property called d which is of type Decimal in a class User.n19.

   Property d As %Decimal(SCALE = 19);

Suppose we have a method in this class that returns numbers of type %Decimal:

    ClassMethod n(d As %Decimal(SCALE=19)) As %Decimal
    {
	s ^foobar=d
	q 1e-19
    }

Here is an example of how a Perl program would define a decimal number, set and get the property and call the method:

    my $decimal = Intersys::PERLBIND::Decimal->new(1,-19);

    $ret = $db->run_class_method( "N19", "n", ( $decimal));

    printf( "decimal out: %.19f\n", $ret);

    my $obj = $db->create_new( "N19", "");
    $obj->set( "n19", $in);
    $obj->set( "d", $decimal);
    $obj->run_obj_method( "%Save", ());

    $obj = $db->openid( "N19", 1, -1, -1);
    printf( "open: %.19f %.19f\n", $obj->get( "n19"), $obj->get( "d" ));

Note that we use the new method to create a new decimal.  The first argument to new is the significand and the second argument to new is the exponent and the value of the decimal is signficand * 10 ** exponent.

   my $decimal = Intersys::PERLBIND::Decimal->new(signficand,exponent);

The significand and exponent of $decimal can be derived through the accessors get_significand() and get_exponent(), $decimal->get_significand() and $decimal->get_exponent().

=head2 Query Support

The Perl binding supports queries.

To do a query, one must first allocate and prepare a query, then one sets any parameters, executes the query, and fetches the results.

 1) allocate query: $query = $database2->alloc_query();
 2) prepare query: $query->prepare("SELECT * FROM SAMPLE.PERSON WHERE ID=?",$sqlcode);
 3) set any parameters: $query->set_par(1,2);
 4) execute query: $query->execute($sqlcode);
 5) fetch results

Note that set_par can only be used to send a parameter to Cache'.  It does not support by reference parameters.

$query->fetch($sqlcode) returns a list of the fetched columns when run in a LIST context and when run in a SCALAR context, it returns the number of columns.  When there is no more data remaining to be fetched it returns an empty list.

Here is an example of fetching the columns and printing the data contained in the columns:

 while (@cols = $query->fetch($sqlcode)) {
     $colnum = 1;
     foreach $col (@cols) {
         $col_name = $query->col_name($colnum);
         print "column name = $col_name, data=$col\n";
         $colnum++;
        
     }
 }

Here is an example of doing a class query:

    $query->prepare_class("Sample.Person","ByName",$sqlcode);
    print "sqlcode=$sqlcode\n";
    $query->set_par(1,"DeSantis");
    $query->execute($sqlcode);
    print "sqlcode=$sqlcode\n";
    $count = 0;
    $num_cols = $query->num_cols();

    while (@cols = $query->fetch($sqlcode)) {
        print "fetch sqlcode=$sqlcode\n";    
        $row = $count+1;
        print "row = $row\n";
        $col = 1;
        foreach $data (@cols) {
            $sql_type = $query->col_sql_type($col);
            $col_name = $query->col_name($col);
            print "column name = $col_name, sql type = $sql_type, data=$data\n";
            $col++;
        }
        print "\n";
        $count++;

    }


There are utility methods for extracting information about a query, for example:

$num_cols=$query->num_cols();

$sqltype=$query->col_sql_type(idx);

$name = $query->col_name(idx);

=head3 Query Methods

=over 4

=item $query->prepare($string, $sqlcode)

prepares a query using the string in string.

=item $query->prepare_class($class_name, $query_name, $sqlcode)

prepare a query in a class definition

=item $query->execute()

executes a query.

=item @column_data = $query->fetch($sqlcode), $column_count = scalar($query->fetch($sqlcode))

returns fetched columns.  In LIST context is list of column data, in SCALAR context is number of columns.

=item $num_cols = $query->num_cols()

returns number of columns in query

=item $sql_type = $query->col_sql_type($idx)

returns sql type of column

=item $name = $query->col_name($idx)

returns name of column

=item $length = $query->col_name_length(idx)

returns length of column name

=item $query->set_par($idx, $var)

set parameter

 example:

 $query->set_par(1,2);

 $query->set_par(1,"1983-04-03")

 Note that set_par can only be used to send a parameter to Cache'.  It does not support by reference parameters.

=item $num = $query->num_pars()

returns number of parameters in query

=item $type = $query->par_sql_type($idx)

returns sql type of parameter

=item $size = $query->par_col_size($idx)

returns size of parameter column

=item $num = $query->par_num_dec_digits($idx)

returns number of decimal digits in parameter

=item $nullable = $query->is_par_nullable($idx)

returns 1 if parameter is nullable, else 0

=item $unbound = $query->is_par_unbound($idx)

returns 1 if parameter is unbound, else 0

=back 

=head2 Transactions

We support methods for working with transactions from the Perl binding: tstart, tlevel, and tcommit.  Here is an example.

        $database->tstart();
        $obj1 = $database->openid($className,"1", 4, 10);
        $database->tlevel($level);
	... some operations ...
        $database->tcommit();

=head3 Transaction Methods

=over 4

=item $database->tstart()

Starts a transaction.  See TSTART in COS documentation.

=item $database->tlevel($level)

Returns tlevel of transaction.  See TLEVEL in COS documentation.

=item $database->trollback()

Rollsback a transaction.  See TROLLBACK in COS documentation.

=back

=head2 Cache synchronization

The Perl binding is built on a C binding which contains a cache of objects reflecting the state of objects on Cache'.  This cache is synchronized with Cache' whenever a Cache' method is run.  To synchronize this cache without running a Cache' method use $database->sync_cache.

=head3 Cache synchronization method

=over 4

=item $database->sync_cache()

=back

=head2 $LIST support

We support arguments of type %List by mapping those variables in the Perl binding to array references.

Suppose we have the following Cache' methods that use %List.

    Method GetDList() As %List 
    {
        q $LB(1,"hello",3.14)
    }

    Method SetDList(x As %List) {
        s ^foobar=x
    }


We can use these methods in the Perl binding as follows:

    $arrayref = $variant2->GetDList();
    print "arrayref=$arrayref\n";
    @array = @$arrayref;
    print "dumping array in arrayref\n";
    print "@array\n";
    foreach $val (@array) {
        print "val=$val\n";
    }

The output from the above code is:

    1 hello 3.14
    val=1
    val=hello
    val=3.14

We can also set a %List from a reference to a Perl array:

    @inarray = (1, undef, 2.78, "goodbye");
    $variant2->SetDList(\@inarray);

A null list element on Cache' corresponds to undef on Perl and a value of undef in a Perl array becomes a null list element in Cache'.

Note carefully that while a Perl array can be unlimited size, Cache' has a maximum list buffer size that is around 32K. (This is not the number of elements in the list but the total memory footprint of the list!)  See Cache' documentation for information about limitation of list size.

In the above, we see that the %List becomes a reference to an array. 

=head2 METHODS

=over 4

=item Intersys::PERLBIND::setlocale($category, $locale)

 see Microsoft MSDN doc
 set the locale, for instance

 Intersys::PERLBIND::setlocale(0, "English") # 0 stands for LC_ALL

 or

 Intersys::PERLBIND::setlocale(0, "Russian") # 0 stands for LC_ALL

=item Intersys::PERLBIND::set_thread_locale($lcid)

 The argument is the locale id. The id values for different languages can be found in http://msdn.microsoft.com/library/default.asp?url=/library/en-us/script56/html/vsmsclcid.asp

 Applications that need to work with locales at run time should call it to ensure proper conversions.

=item Intersys::PERLBIND::Connection->new

$conn = Intersys::PERLBIND::Connection->new($conn_str, $user, $pwd, $timeout)

Intersys::PERLBIND::Connection->new returns a connection that can be used to get a database from the Cache' database.

The format of conn_str is "<host>[<port>]:<namespace>".  Here is an example: "localhost[1972]:Samples".

Intersys::PERLBIND::Connection->new_secure

Signature:

$conn = Intersys::PERLBIND::Connection->new_secure($conn_str, $srv_principal_name, $security_level, $timeout)


Description:

Intersys::PERLBIND::Connection->new_secure returns the connection proxy that can be used to get the proxy for the Cache' namespace identified by $conn_str. The format of $conn_str is ``<host>[<port>]:<namespace>'', e.g. 'localhost[1972]:Samples'.

See also:

Intersys::PERLBIND::Database->new()

A Kerberos "principal" is an identity that is represented in the Kerberos database, has a permanent secret key that is shared only with the Kerberos KDCs (key distribution centers), can be assigned credentials, and can participate in the Kerberos authentication protocol.  

A "user principal" is associated with a person, and is used to authenticate to services which can then authorize the use of resources, e.g. computer accounts, or Cache' services.  

A "service principal" is associated with a service, and is used to authenticate user principals and can optionally authenticate itself to user principals.  A "service principal name" (such as $srv_principal_name) is the string representation of the name of a service principal, conventionally of the form:

<service>/<instance>@<REALM>,

e.g.

cache/turbo.iscinternal.com@ISCINTERNAL.COM

(There are other types of principals too.)

On Windows, The KDCs are embedded in the domain controllers, and service principal names are associated with domain accounts.

"Connection security level" ($security_level in the above) is an integer that indicates the client/server network security services that are requested or required.  Values:

0 - None

1 - Kerberos client/server mutual authentication, no protection for data

2 - 1 plus data source and content integrity protection

3 - 2 plus data encryption

=item is_uni_srv

$is_unicode = $db->is_uni_srv()

return 1 if UNICODE, 0 if 8-bit Cache'


=item open

$obj = $db->open($type, $oid, $concurrency, $timeout) opens a object instance from the class named by type and from the oid.

=item openid

$obj = $db->openid($type, $id, $concurrency, $timeout) opens an object instance from the class named by type and from the id.

=item create_new

$obj = $db->create_new($type, $init_val) creates a new object instance from the class named by type.  Normally $init_val is undef.

=item run_class_method

$value = $db->run_class_method($cl_name, $mtd_name, LIST)

run_class_method runs the class method named in mtd_name on the database specified by db. The db corresponds to a Cache' namespace.  Arguments are passed in the LIST.  Some of these arguments may be passed by reference depending on the class definition in Cache'. Return values correspond to the return values from the Cache' method


=item run_obj_method

$value = $object->run_obj_method($mtd_name, LIST)

run_obj_method runs the method named in mtd_name on the object specified by obj.  Arguments are passed in the LIST.  Some of these arguments may be passed by reference depending on the class definition in Cache'. Return values correspond to the return values from the Cache' method

=item get

$value = $obj->get($prop_name) is used to get a property from an object.

=item set

$obj->set($prop_name, $val) is used to set a prop_name to val.

=item get_properties

@props = $personobj->get_properties();

The above returns the names of properites in a list in list context and in scalar contexts returns the number of properties.  Private and multidimensional properties are not returned.  Private and multidimensional properties are not accessible through the Perl binding.

=item get_methods

@methods = $personobj->get_methods();

The above returns the names of methods in a list in list context and in scalar context returns the number of methods.

=item PDATE_STRUCTPtr->new()

used to create a new date

=item $year = $date->get_year()

return year

=item $month = $date->get_month()

return month

=item $day = $date->get_day()

return day

=item $date->set_year($year)

set year

=item $date->set_month($month)

set month

=item $date->set_day($day)

set day

=item $stringrep = $date->toString()

convert to string

=item PTIME_STRUCTPtr->new()

used to create a new time

=item $hour = $time->get_hour()

return hour

=item $minute = $time->get_minute()

return minute

=item $second = $time->get_second()

return second

=item $stringrep = $time->toString()

convert to string

=item $time->set_hour($hour)

set hour

=item $time->set_minute($minute)

set minute

=item $time->set_second($second) 

set second

=item PTIMESTAMP_STRUCTPtr->new()

used to create a new timestamp

=item $year = $timestamp->get_year()

return year

=item $month = $timestamp->get_month()

return month

=item $day = $timestamp->get_day() 

return day

=item $stringrep = $timestamp->toString()

convert to string

=item $timestamp->set_year($year)

set year

=item $timestamp->set_month($month)

set month

=item $timestamp->set_day($day)

set day

=item $hour = $timestamp->get_hour()

set hour

=item $minute = $timestamp->get_minute()

get minute

=item $second = $timestamp->get_second()

get second

=item $fraction = $timestamp->get_fraction()

get fraction

=item $timestamp->set_hour($hour)

set hour

=item $timestamp->set_minute($minute)

set minute

=item $timestamp->set_second($second)

set second

=item $timestamp->set_fraction($fraction)

set fraction

=back

=head2 EXPORT

None.

=head1 AUTHOR

Copyright 2005, InterSystems Corporation

=head1 SEE ALSO

Cache' documentation

=cut
