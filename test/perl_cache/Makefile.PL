use ExtUtils::MakeMaker;
# See lib/ExtUtils/MakeMaker.pm for details of how to influence
# the contents of the Makefile that is written.
use strict;
my $libname; my $dllext; my $libdir; my $dll; my $CacheInstallDir; my $libfile; my $incdir;my $libarg;
print '$^O='.$^O,"\n";
my $define="";
if ($^O eq "MSWin32" || $^O eq "Windows_NT") {
    $libname = "cbind.lib";
    $libarg = "cbind.lib";
    $libdir = "dev/cpp/lib";
	$define = "-D_CRT_SECURE_NO_WARNINGS"
} elsif ($^O eq "VMS") {
    $libname = "cbind.exe";
    $libarg = "cbind.exe";
    $libdir = "bin";
} elsif ($^O eq "darwin") {
    $libname = "libcbind.so";
    $libdir = "bin";
} else {
    $libname = "libcbind.so";
    $libdir = "bin";
}
if ($#ARGV < 0) {
    do {
        print "Enter directory where Cache' is installed\n";
        chomp($CacheInstallDir = <STDIN>
        );
        &NormalizeDir($CacheInstallDir);
        $libfile = &MakeFileName($CacheInstallDir,$libdir,$libname);
        print "Error! $libfile does not exist!\n" if (!-e $libfile);
    } while (!-e $libfile);
    
} else {
    $CacheInstallDir = shift @ARGV;
    &NormalizeDir($CacheInstallDir);
    $dll = &MakeFileName($CacheInstallDir,$libdir,$libname);
    die "$dll does not exist!" if !-e $dll;
}
$libfile = &MakeFileName($CacheInstallDir,$libdir,$libname);
my $cppincdir = &MakeDirName($CacheInstallDir,"dev/cpp/include");
if ($^O eq "MSWin32") {
    $incdir = "-I. -I$cppincdir";
    $libarg = &MakeFileName($CacheInstallDir,$libdir,$libarg);
} elsif ($^O eq "VMS") {
    $incdir = "-I. -I$cppincdir";
} elsif ($^O eq "darwin") {
    $libdir = &MakeDirName($CacheInstallDir,$libdir);
    $libarg = "-L$libdir -lcbind -lcppbind";
    my $sqlincdir = &MakeDirName($CacheInstallDir,"dev/odbc/redist/iodbc/include");
    $incdir = "-I. -I$cppincdir -I$sqlincdir"
} else {
    $libdir = &MakeDirName($CacheInstallDir,$libdir);
    $libarg = "-L$libdir -lcbind";
    my $sqlincdir = &MakeDirName($CacheInstallDir,"dev/odbc/redist/iodbc/include");
    $incdir = "-I. -I$cppincdir -I$sqlincdir"
}
print "libdir=$libdir libarg=$libarg\n";
WriteMakefile(
    'NAME'		=> 'Intersys::PERLBIND',
    'VERSION_FROM'	=> 'PERLBIND.pm', # finds $VERSION
    'PREREQ_PM'		=> {}, # e.g., Module::Name => 1.1
    ($] >= 5.005 ?    ## Add these new keywords supported since 5.005
      (ABSTRACT_FROM => 'PERLBIND.pm', # retrieve abstract from module
       AUTHOR     => 'InterSystems <support@intersystems.com>') : ()),
     'LIBS'	=> $libarg,
#    'CCFLAGS' => ' /MTd /W3 /Gm /GX /ZI /Od /D "WIN32" /D "_DEBUG" /D "_CONSOLE" /D "_MBCS"',
    'DEFINE'		=> $define, # e.g., '-DHAVE_SOMETHING'
    'INC'		=> $incdir, # e.g., '-I. -I/usr/include/other'
#    'OPTIMIZE'=>'/ZI',
	# Un-comment this if you add C files to link with later:
    # 'OBJECT'		=> '$(O_FILES)', # link all the C files too
);
sub NormalizeDir() {
    return $_[0] if $^O eq "VMS";
    $_[0] =~ s/\\/\//g;
    $_[0] .= "/" if (! ($CacheInstallDir =~ /.*\/$/))
    
}
   
sub MakeDirName() {
    my ($dir, $subdir) = @_;
    if ($^O ne "VMS") {
        return $dir.$subdir."/";
    } else {
        $dir =~ s/\]$//g; # remove final ]
        $subdir =~ s/\//./g; # change / to period
        return $dir.".".$subdir."]";
    }
}

sub MakeFileName() {
    my ($dir, $subdir, $filename) = @_;
    return &MakeDirName($dir, $subdir).$filename;
}
