#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

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

