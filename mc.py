#!/usr/bin/python2.6

import sys, os, os.path, subprocess, signal, re
os.chdir(os.path.dirname(sys.argv[0]))
import memcache
import c

INSTANCE_TO_PORT = {'dev': 2029, 'prod': 2030}

g_memcache_client = None

g_in_process_cache_key_to_value = {}

# Meaning: this process is going to be a client of the memcache.  Which port should it use? 
def client_get_port():
	if c.VERSION == 'dev':
		return INSTANCE_TO_PORT['dev']
	else:
		return INSTANCE_TO_PORT['prod']

def get_memcache_client():
	global g_memcache_client
	if g_memcache_client is None:
		g_memcache_client = memcache.Client(['127.0.0.1:%d' % client_get_port()], debug=0)
	return g_memcache_client

# Important that the return value of this is a str because that's what the memcache client insists on.  
# Unicode will cause an error right away. 
# Also - memcached can't handle spaces in keys, so we avoid that. 
def _make_key(func_, args_):
	name = '%s.%s' % (func_.__module__, func_.__name__)
	r = '%s-%s(%s)' % (c.VERSION, name, ','.join([str(arg) for arg in args_]))
	SPACE_REPLACER = '________'
	assert SPACE_REPLACER not in r
	r = r.replace(' ', SPACE_REPLACER)
	return r

def get(func_, args_=[]):
	args_ = args_[:]
	key = _make_key(func_, args_)
	if key in g_in_process_cache_key_to_value:
		r = g_in_process_cache_key_to_value[key]
	else:
		r = get_memcache_client().get(key)
		if r is None:
			r = func_(*args_)
			get_memcache_client().set(key, r)
		g_in_process_cache_key_to_value[key] = r
	return r

def decorate(user_function_):
	def decorating_function(*args):
		return get(user_function_, args)
	
	return decorating_function



# Above were functions for dealing with memcache when this process is a client. 
# Below are functions for starting and stopping memcache servers.  This process might start a memcache server 
# but it won't BE a memcache server. 




# Meaning: this process is going to be starting or stopping a memcache server.  Which port is it using? 
def server_get_port(instance_):
	return INSTANCE_TO_PORT[instance_]

def we_are_on_linux():
	return ('linux' in sys.platform.lower())

def is_server_running(instance_):
	if we_are_on_linux():
		pid = get_server_pid_linux(instance_)
	else:
		pid = get_server_pid_windows(instance_)
	return (pid is not None)

def start_memcache(instance_):
	if is_server_running(instance_):
		print 'Server was already started.  (Or another process is using that port.)'
	else:
		subprocess.Popen(['memcached', '-l', '127.0.0.1', '-m', '2', '-p', str(server_get_port(instance_))])

def get_server_pid_linux(instance_):
	lsof_stdout_contents = subprocess.Popen(['lsof'], stdout=subprocess.PIPE).communicate()[0]
	for line in lsof_stdout_contents.split('\n'):
		if re.search(r':%d\b' % server_get_port(instance_), line) and 'LISTEN' in line:
			pid = int(re.sub(r'^.*?(\d+).*$', r'\1', line))
			return pid
	return None

def stop_memcache_linux(instance_):
	pid = get_server_pid_linux(instance_)
	if pid is None:
		print 'Was not started.'
	else:
		os.kill(pid, signal.SIGKILL)

def get_server_pid_windows(instance_):
	netstat_stdout_contents = subprocess.Popen(['netstat', '-a', '-b', '-n', '-p', 'tcp'], stdout=subprocess.PIPE).communicate()[0]
	for line in netstat_stdout_contents.split('\n'):
		if re.search(r':%d\b' % server_get_port(instance_), line) and 'LISTENING' in line:
			pid = int(re.sub(r'^.*?(\d+)\s*$', r'\1', line))
			return pid
	return None

def stop_memcache_windows(instance_):
	pid = get_server_pid_windows(instance_)
	if pid is None:
		print 'Was not started.'
	else:
		subprocess.check_call(['taskkill', '/f', '/pid', str(pid)])

def stop_memcache(instance_):
	if we_are_on_linux():
		stop_memcache_linux(instance_)
	else:
		stop_memcache_windows(instance_)

def list_running_instances():
	print 'dev instance is running: %s' % is_server_running('dev')
	print 'prod instance is running: %s' % is_server_running('prod')
	


if __name__ == '__main__':

	if len(sys.argv) == 2 and sys.argv[1] == 'list':
		list_running_instances()
	else:
		command, instance = sys.argv[1:3]
		if instance not in INSTANCE_TO_PORT or command not in ('start', 'stop', 'restart'):
			sys.exit('Invalid arguments.')
		if command in ('stop', 'restart'):
			stop_memcache(instance)
		if command in ('restart', 'start'):
			start_memcache(instance)




