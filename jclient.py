#!/usr/bin/env python

import sys

if 1:
	import jsonrpclib
	from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
	import socket
	s = jsonrpclib.Server('http://localhost:112029')
	#s = jsonrpclib.Server('unix://www/htdocs/virtual/dt.theorem.ca/test/sock')
	if sys.argv[1] == 'exit':
		s.exit()
	elif sys.argv[1] == 'ping':
		print s.ping()
	else:
		sys.exit('error.')
else:
	import xmlrpclib
	s = xmlrpclib.ServerProxy('http://localhost:112029')
	print s.x()
