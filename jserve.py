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

