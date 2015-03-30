The sample programs are controlled by various switches that can be entered as arguments to the program on the command line.

-id id (which id to open)

for example,

perl CPTest3.pl -id 2

-user user (which user to login under)

for example,

perl CPTest2.pl -user _SYSTEM

-password password (which password to use)

-host host (which host computer to connect to)

-port port (which port to use)

-query query (arguments to stored procedure)

for exmaple,

perl CPTest7.pl -query A

The above gives all persons whose name starts with the letter A.

There are 7 samples.  They are named, numbered and implemented to correspond to Java samples.

(CP stands for Cache' Perl) 

CPTest2.pl - illustrate getting and setting properties of an instance of Sample.Person

CPTest3.pl - illustrate getting properties of an embedded object, Home, in Sample.Person, illustrate looking at property of referenced object

CPTest4.pl - illustrate updating embedded object in instance of Sample.Person

CPTest5.pl - demonstrate processing of datatype collections

CPTest6.pl - Demonstrate processing of a result set, ByName query

CPTest7.pl - Demonstrate processing of a result set using dynamic SQL

CPTest8.pl - illustrate processing employee subclass and company/employee relationship 
