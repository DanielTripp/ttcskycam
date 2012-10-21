#!/usr/bin/python2.6

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

