#!/usr/bin/env python

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import daemon
import sys, socket, os, threading, time, signal
import traffic
name = 'ttc-rpc-server'
namenpid = '%s-%d' % (name, os.getpid())
def exit():
	def run():
		time.sleep(1)
		os.kill(os.getpid(), signal.SIGKILL)
	threading.Thread(target=run).start()

with daemon.DaemonContext(stdout=open('/tmp/dt/%s-stdout' % (namenpid), 'w'), stderr=open('/tmp/dt/%s-stderr' % (namenpid), 'w')):
	server = SimpleJSONRPCServer(("localhost", 112029))
	server.register_function(exit, 'exit')
	server.register_function(lambda: 'pinged', 'ping')
	server.register_function(traffic.get_traffics, 'get_traffics')
	server.serve_forever()

