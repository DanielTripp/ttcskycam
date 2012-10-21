#!/usr/bin/python2.6

import sys, os, socket
import daemon, lockfile
from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
name = 'daemontest'
namenpid = '%s-%d' % (name, os.getpid())
with daemon.DaemonContext(pidfile=lockfile.FileLock('/tmp/dt/%s.pid' % (name)), 
		stdout=open('/tmp/dt/%s-stdout' % (namenpid), 'w'), stderr=open('/tmp/dt/%s-stderr' % (namenpid), 'w')):
	server = SimpleJSONRPCServer(("localhost", 112029))
	server.register_function(lambda: 'success 123', 'x')
	server.serve_forever()


from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import socket
if 1:
	server = SimpleJSONRPCServer(("localhost", 112029))
	server.register_function(lambda: 'success 123', 'x')
	server.serve_forever()
else:
	from xmlrpclib import *
	from SimpleXMLRPCServer import *
	server = SimpleXMLRPCServer(("localhost", 112029))
	server.register_function(lambda: 'success 123', 'x')
	server.serve_forever()

