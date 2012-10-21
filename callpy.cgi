#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, urlparse, json
from misc import *

def get_arg_strvals(vardict_):
	r = []
	argi = 0
	while True:
		argname='arg%d' % (argi)
		if argname not in vardict_:
			break
		r.append(vardict_[argname][0])
		argi+=1
	return r

def get_arg_objvals(vardict_):
	r = []
	for arg_strval in get_arg_strvals(vardict_):
		try:
			arg_objval = json.loads(arg_strval)
		except ValueError:
			arg_objval = arg_strval
		r.append(arg_objval)
	return r

def first(iterable_, func_=bool):
	for e in iterable_:
		if func_(e):
			return e
	return None

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
module_and_funcname = vars['module_and_funcname'][0]
allowables = ['t.t', 'web.get_vehicle_svg', 'traffic.get_traffics', 'traffic.get_recent_vehicle_locations', 'routes.get_all_routes_latlons', 'routes.get_endpoint_info']
if module_and_funcname in allowables:
	modulename = module_and_funcname.split('.')[0]
	funcname = module_and_funcname.split('.')[1]
	args = get_arg_objvals(vars)
	print json.dumps(getattr(__import__(modulename), funcname)(*args))

