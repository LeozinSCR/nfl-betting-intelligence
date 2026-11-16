import sys,os,runpy
sys.dont_write_bytecode=True
script=sys.argv[1]
def guard(event,args):
 if event.startswith(('socket.connect','socket.bind','subprocess.','os.system')):raise PermissionError('probe forbids network/processes')
 if event=='open':
  mode,flags=args[1:3]
  if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):raise PermissionError('probe forbids writes')
sys.addaudithook(guard)
sys.argv=[script,'--help']
runpy.run_path(script,run_name='__main__')
