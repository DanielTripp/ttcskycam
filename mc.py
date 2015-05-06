#!/usr/bin/env python

# Memcache connections (i.e. memcache.Client objects) behave in some unique ways that are different from 
# eg. a typical database connection. 
# If connection fails at creation time, then no error will be raised at connection time or when calling 
# set() or get() on the client - but all get() calls will return None.
# If however the memcache server goes down later, after we have made a connection, then 
# future calls to get() seem to return None, same as ever.  But future calls to set() might raise an Exception.  
# They seem to do this only if they haven't been immediately preceeded by a get().  
# As for a memcache server (that was down) coming up - there is a 30-second retry time window implemented, where 
# the memcache client will retry the connection after no less than 30 seconds.  After that, it seems all will be well.  

# I find this behaviour unusual but it works with our current setup.  If the mc client raises an exception in the case 
# mentioned above, then callpy.wsgi will notice this and dispose of the mc connection (and the db connection too for that 
# matter), to be re-created on the next incoming request. 


import sys, os, os.path, subprocess, signal, re, time, functools, collections, functools, hashlib
from itertools import ifilterfalse
from heapq import nsmallest
from operator import itemgetter
if len(sys.argv[0]) > 0 and (sys.argv[0] != '-c'): 
	# b/c sys.argv[0] will be '' if this is imported from an interactive interpreter, 
	# and we don't want to chdir in that case anyway. 
	new_cwd = os.path.dirname(sys.argv[0])
	if len(new_cwd) > 0:
		os.chdir(new_cwd) 
import memcache
from lru_cache import lru_cache
import c
from misc import *

LOG = os.path.exists('LOG_MEMCACHE')

NUM_MEGS = 100

INSTANCE_TO_PORT = {'dev': 2029, 'prod': 2030}

g_memcache_client = None

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

# Important that the return value of this is a str, because that's what the memcache client insists on.  
# Unicode will cause an error right away. 
# Also - memcached can't handle spaces in keys, so we avoid that. 
def make_key(func_, args_, kwargs_, posargkeymask=None):
	assert posargkeymask is None or len(posargkeymask) == len(args_)
	if isinstance(func_, str):
		name = func_
	else:
		name = '%s.%s' % (func_.__module__, func_.__name__)
	str_arg_list = [str(arg) for i, arg in enumerate(args_) if posargkeymask is None or posargkeymask[i]] 
	str_arg_list += ['%s=%s' % (kwargname, kwargs_[kwargname]) for kwargname in sorted(kwargs_.keys())]
	r = '%s-%s(%s)' % (c.VERSION, name, ','.join(str_arg_list))
	SPACE_REPLACER = '________'
	assert SPACE_REPLACER not in r
	r = r.replace(' ', SPACE_REPLACER)
	return r

def set(func_, args_, kwargs_, value_):
	key = make_key(func_, args_, kwargs_)
	get_memcache_client().set(key, value_)

# Will try to get from memcache, and if that fails, then call the func_ (the implementation function.) 
def get(func_, args_=[], kwargs_={}, key=None, posargkeymask=None):
	assert not (key is not None and posargkeymask is not None)
	args_ = args_[:]
	if key is None:
		key2 = make_key(func_, args_, kwargs_, posargkeymask=posargkeymask)
	else:
		key2 = key
	sha1_key = hashlib.sha1(key2).hexdigest()
	r = get_memcache_client().get(sha1_key)
	if r is None:
		if LOG: printerr('Not found in memcache:     %s / "%s"' % (sha1_key, key2))
		r = func_(*args_, **kwargs_)
		get_memcache_client().set(sha1_key, r)
	else:
		if LOG: printerr('Found in memcache:         %s / "%s"' % (sha1_key, key2))
	return r

def get_from_memcache(func_, args_, kwargs_):
	key = make_key(func_, args_, kwargs_)
	return get_memcache_client().get(key)

def decorate(user_function_, posargkeymask=None):
	@functools.wraps(user_function_)
	def decorating_function(*args, **kwargs):
		return get(user_function_, args, kwargs, posargkeymask=posargkeymask)
	
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

def start_memcache(instance_, log=True):
	if is_server_running(instance_):
		if log:
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

def stop_memcache_linux(instance_, log=True):
	pid = get_server_pid_linux(instance_)
	if pid is None:
		if log:
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

def stop_memcache_windows(instance_, log=True):
	pid = get_server_pid_windows(instance_)
	if pid is None:
		if log:
			print 'Was not started.'
	else:
		subprocess.check_call(['taskkill', '/f', '/pid', str(pid)])
		time.sleep(2) # I've routinely witnessed the process still showing up in 'ps' and 'netstat' output
			# shortly (a fraction of a second) after 'taskkill' returns.  So here we fudge it to make sure.
			# This is not so important on a stop, but very important on a restart, because an 'is running'
			# check (which uses netstat) will be done before the start.

def stop_memcache(instance_, log=True):
	if we_are_on_linux():
		stop_memcache_linux(instance_, log=log)
	else:
		stop_memcache_windows(instance_, log=log)

def print_running_instances():
	def p(instance__):
		pid = get_server_pid(instance__)
		if pid is None:
			print '%s instance is not running.' % instance__
		else:
			print '%s instance is running as pid %d' % (instance__, pid)
	p('dev')
	p('prod')

def close_connection():
	global g_memcache_client
	if g_memcache_client is not None:
		try:
			g_memcache_client.close_socket()
		except:
			pass
		g_memcache_client = None

def forget_connection():
	global g_memcache_client
	g_memcache_client = None

def restart():
	if c.VERSION == 'dev':
		instance = 'dev'
	else:
		instance = 'prod'
	stop_memcache(instance, log=False)
	start_memcache(instance, log=False)

if __name__ == '__main__':

	if len(sys.argv) == 2 and sys.argv[1] == 'list':
		print_running_instances()
	elif len(sys.argv) == 3:
		command, instance = sys.argv[1:3]
		if instance not in INSTANCE_TO_PORT or command not in ('start', 'stop', 'restart', 'start-if-not-running'):
			sys.exit('Invalid arguments.')
		if command in ('stop', 'restart'):
			stop_memcache(instance)
		if command in ('restart', 'start'):
			start_memcache(instance)
		if command == 'start-if-not-running':
			if not is_server_running(instance):
				print 'Memcache instance %s was not running.  Will start it now.' % instance 
				start_memcache(instance)
	else:
		sys.exit('Usage: mc.py COMMAND [INSTANCE]')


