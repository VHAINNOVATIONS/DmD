var Connection=require('ssh2');
var conn = new Connection();
conn.on('ready',function(){
  console.log('Connection :: ready');
  conn.shell(function(err,stream){
    if (err) throw err;
    stream.on('close',function(){
      console.log('Stream :: close');
      conn.end();
    }).on('data',function(data){
      console.log('STDOUT: ' + data);
    }).stderr.on('data',function(data){
      console.log('STDERR: ' + data);
    });
    stream.end('cprs1234\nCPRS4321$\n^?\n');
  });
}).connect({
  host: '23.23.185.154',
  username: 'vista',
  password: '',
  port: 22,
  timeout: 1500

});
