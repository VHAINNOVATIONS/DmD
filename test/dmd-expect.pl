#!/usr/bin/perl
use Expect;
# If you don't know the code, don't mess around below -BCIV
# the purpose of this code is to programmatically manipulate a VistA from the
# roll and scroll terminal environment via SSH in lieu of RPC

my $exp=new Expect;
$exp->raw_pty(1);
# This gets the size of your terminal window
$exp->slave->clone_winsize_from(\*STDIN);
my $PROMPT = '[\]\$\>\#\:]\s$';
$SIG{WINCH} = \&winch;  # best strategy

my $user='vista';
my $access='CPRS1234';
my $verify='CPRS4321$';
my $host='vista2.vaftl.us';
my $namespace='GOLD';
my $timeout=4;
my $patientname="SIX,INPATIENT";
my $logfile="dmd-expect.log";

# use \cM as <return> under VistA which is the same as ^M used in MUMPS

my @result;

# login to VistA
# login: access code, verify code, login delay
login($access,$verify,8);

# enter programmer mode passing DUZ or whatever you want to set up environment such as
# "K  D ^XUP,Q^DI" and any other commands for example setting DUZ
# pass the commands to set up programmer mode as an array to the programmer_mode function
my @setup=(" ","D ^%CD","GOLD","D ^XUP","S DUZ=1");
programmer_mode(@setup);

my $dfn=get_dfn_by_lastfirst($patientname);

print "$patientname dfn: $dfn\n";

exit;

# ---------------------------------------------------------------------------
# functions to be made into library... VistA.pm
# ---------------------------------------------------------------------------
sub programmer_mode {
  my(@setup)=@_; my $error=1;
  $exp->expect($timeout,
    [ qr/Systems/, sub { my $self=shift; $self->send("^programmer options\cM"); exp_continue; }],
    [ qr/Programmer Options/, sub { my $self=shift; $self->send("PG\cM"); exp_continue; }],
    [ qr/OPTION NAME/, sub { $error=0; my $self=shift; $self->send("\cM"); exp_continue; }],
    # improve the next match so it knows we are at a prompt but not specifically called CPM
    [ qr/CPM\>/, sub { 
        my $self=shift;
        foreach my $cmd (@setup) { $self->send("$cmd\cM"); }
        $error=0;
        exp_continue;
    }],
  );
  if ($error eq '1') {die "cannot enter programmer mode.\n";}
}

sub get_dfn_by_lastfirst {
  my($patientname)=@_; my $retval='';
  my $patientlookup=substr($patientname,0,-1);
  # must be in programmer mode for this routine to work
  #$exp->log_file(undef);
  $exp->expect($timeout,
    [ qr/>/, sub {
      $error=0;
      my $self=shift;
      $self->send("S U=\"^\"\cM");
      $self->send("S Y=\"\"\cM");
      $self->send("S DIR=\"1\"\cM");
      $self->send("D LISTALL^ORWPT(.Y,\"$patientlookup\",.DIR)\cM");
      $self->send("ZWRITE Y\cM");
      $self->send("\cM");
      $exp->log_file("dmd-expect-zwrite.log","w");
      $self->send("H\cM"); # H^XUS
      #exp_continue;
    }],
  );
  if ($error eq '1') {
    print "Not in programmer mode.  Cannot perform patient_lookup\n";
    return -1;
  }  

  #  #$exp->log_file(undef);
  $exp->soft_close();
  @result=fileToArray("dmd-expect-zwrite.log","^Y","destroy");
  my $num=0; my $match=1;
  foreach my $line (@result){
    ++$num;
    #print ++$num." $line\n";
    if($line=~m/Y\(\d+\)/){
      $line=~s/^Y\(\d+\)\=\"//;
      my($dfm,$name)=split(/\^/,$line);
      if($patientname eq $name){
        if($debug eq 'true'){print "$num $dfm $name\n";}
        $retval=$dfm;
      }
      else{ if($debug eq 'true'){print "$num $dfm $name\n";} }
    }    
  }
  #$exp->log_file($logfile);
  return $retval;
}

# login to vista
sub login {
  my($access,$verify,$delay)=@_;
  my $error=1;

  # uses existing system ssh command to negotiate session
  $exp=Expect->spawn("ssh -q $user\@$host") or die "Cannot spawn command: $!\n";

  # log everything
  $exp->log_file("$logfile","w");
  
  # send access and verify code ~also send return for default terminal type
  my $ret=$exp->expect($delay,
    [ qr/The authenticity of host/, sub { my $self=shift; $self->send("yes\r"); exp_continue;}],
    [ qr/ACCESS CODE/, sub { my $self=shift; $self->send("$access\cM"); exp_continue;}],
    [ qr/VERIFY CODE/, sub { my $self=shift; $self->send("$verify\cM"); exp_continue;}],
    [ qr/TERMINAL/, sub { $error=0; my $self=shift; $self->send("\cM"); exp_continue;}],
  );
  if($error eq '1'){die "cannot connect to VistA.\n";}  
}

sub fileToArray {
  my($file,$filter,$destroy)=@_;
  print "fileToArray: $file, $filter, $destroy\n";
  my @retval;
  open(my $fh, '<:encoding(UTF-8)', $file) or die "cannot read $file : $!\n";
  while(my $line=<$fh>) {
    chomp $line;
    if ($filter ne "" && $line=~m/$filter/) {
      push @retval, $line;
    }
    else{    
      push @retval, $line;
    }
  }  
  close($fh);
  if ($destroy eq 'destroy') {
    unlink $file;
  }  
  return @retval;
}

# This function traps WINCH signals and passes them on
sub winch {
    my $signame = shift;
    my $pid = $exp->pid;
    $shucks++;
    print "count $shucks,pid $pid, SIG$signame\n";
    $exp->slave->clone_winsize_from(\*STDIN);
    kill WINCH => $exp->pid if $exp->pid;
}
