#!/usr/bin/python2.6

import sys, os, os.path, subprocess, signal, re, time
if len(sys.argv[0]) > 0 and (sys.argv[0] != '-c'): # b/c sys.argv[0] will be '' if this is imported from an interactive interpreter, 
	os.chdir(os.path.dirname(sys.argv[0])) # and we don't want to chdir in that case anyway. 
import memcache
import c

NUM_MEGS = 100

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
def _make_key(func_, args_, kwargs_):
	name = '%s.%s' % (func_.__module__, func_.__name__)
	str_arg_list = [str(arg) for arg in args_] + ['%s=%s' % (kwargname, kwargs_[kwargname]) for kwargname in sorted(kwargs_.keys())]
	r = '%s-%s(%s)' % (c.VERSION, name, ','.join(str_arg_list))
	SPACE_REPLACER = '________'
	assert SPACE_REPLACER not in r
	r = r.replace(' ', SPACE_REPLACER)
	return r

def get(func_, args_=[], kwargs_={}):
	args_ = args_[:]
	key = _make_key(func_, args_, kwargs_)
	if key in g_in_process_cache_key_to_value:
		r = g_in_process_cache_key_to_value[key]
	else:
		r = get_memcache_client().get(key)
		if r is None:
			r = func_(*args_, **kwargs_)
			get_memcache_client().set(key, r)
		g_in_process_cache_key_to_value[key] = r
	return r

def decorate(user_function_):
	def decorating_function(*args, **kwargs):
		return get(user_function_, args, kwargs)
	
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
	return (get_server_pid(instance_) is not None)

def get_server_pid(instance_):
	if we_are_on_linux():
		return get_server_pid_linux(instance_)
	else:
		return get_server_pid_windows(instance_)

def start_memcache(instance_):
	if is_server_running(instance_):
		print 'Server was already started.  (Or another process is using that port.)'
	else:
		subprocess.Popen(['memcached', '-u', 'dt', '-l', '127.0.0.1', '-m', str(NUM_MEGS), '-p', str(server_get_port(instance_))])

# Using netstat's "-p" option as we do here requires netstat to run as root so I've setuid'ed it on my machine to make this work. 
def get_server_pid_linux(instance_):
	netstat_stdout_contents = subprocess.Popen(['netstat', '--tcp', '-p', '-a'], stdout=subprocess.PIPE).communicate()[0]
	for line in netstat_stdout_contents.split('\n'):
		if re.search(r':%d\b' % server_get_port(instance_), line) and 'LISTEN' in line:
			pid = int(re.sub(r'^.*?(\d+)[^\d]*$', r'\1', line))
			return pid
	return None

def stop_memcache_linux(instance_):
	pid = get_server_pid_linux(instance_)
	if pid is None:
		print 'Was not started.'
	else:
		os.kill(pid, signal.SIGKILL)
		time.sleep(1) # This is here for the same reason as the sleep in stop_memcache_windows(), but 
			# where I witnessed the problem on Windows every time, I only saw this happening on Linux very occasionally, 
			# and only second-hand.  Oh well. 

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
		time.sleep(2) # I've routinely witnessed the process still showing up in 'ps' and 'netstat' output
			# shortly (a fraction of a second) after 'taskkill' returns.  So here we fudge it to make sure.
			# This is not so important on a stop, but very important on a restart, because an 'is running'
			# check (which uses netstat) will be done before the start.

def stop_memcache(instance_):
	if we_are_on_linux():
		stop_memcache_linux(instance_)
	else:
		stop_memcache_windows(instance_)

def list_running_instances():
	def p(instance__):
		pid = get_server_pid(instance__)
		if pid is None:
			print '%s instance is not running.' % instance__
		else:
			print '%s instance is running as pid %d' % (instance__, pid)
	p('dev')
	p('prod')

def clear_in_process_cache():
	g_in_process_cache_key_to_value.clear()

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



