#!/usr/bin/python2.6

import sys, os, os.path, urlparse, json, time, re, cgi
from collections import Sequence
sys.path.append('.')
import geom, vinfo, mc, db, util
from misc import *

LOG_CALLS = os.path.exists('CALLPY_LOG_CALLS')

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

def wants_to_be_a_LatLng(obj_):
	return isinstance(obj_, Sequence) and len(obj_) == 2 and isinstance(obj_[0], float) and isinstance(obj_[1], float) \
			and (43.0 < obj_[0] < 44.0) and (-80 < obj_[1] < -79)

def wants_to_be_a_list_of_LatLngs(obj_):
	return isinstance(obj_, Sequence) and all(wants_to_be_a_LatLng(e) for e in obj_)

def to_LatLng(obj_):
	return geom.LatLng(obj_[0], obj_[1])

def get_arg_objvals(vardict_):
	r = []
	for arg_strval in get_arg_strvals(vardict_):
		arg_objval = json.loads(decode_url_paramval(arg_strval))
		if isinstance(arg_objval, unicode):
			arg_objval = str(arg_objval)
		elif wants_to_be_a_LatLng(arg_objval):
			arg_objval = to_LatLng(arg_objval)
		elif wants_to_be_a_list_of_LatLngs(arg_objval):
			arg_objval = [to_LatLng(e) for e in arg_objval]
		r.append(arg_objval)
	return r

def looks_like_json_already(obj_):
	return isinstance(obj_, basestring) and ((obj_[0] == '[' and obj_[-1] == ']') or (obj_[0] == '{' and obj_[-1] == '}'))

g_allowed_functions = [line.strip() for line in readfile('callpy_allowed_functions').split('\n')]

def get_call_func(query_string_, referer_):
	query_str_vars = urlparse.parse_qs(query_string_)
	module_and_funcname = query_str_vars['module_and_funcname'][0]
	args = get_arg_objvals(query_str_vars)
	return call_func(module_and_funcname, args, referer_)

def post_call_func(query_string_, args_, referer_):
	query_str_vars = urlparse.parse_qs(query_string_)
	module_and_funcname = query_str_vars['module_and_funcname'][0]
	return call_func(module_and_funcname, args_, referer_)

def call_func(module_and_funcname_, args_, referer_):
	if (module_and_funcname_ in g_allowed_functions) or \
			((referer_ is not None and os.path.basename(referer_).startswith('test.24972394874134958')) and module_and_funcname.startswith('t.')):
		modulename, funcname = module_and_funcname_.split('.')
		if LOG_CALLS:
			printerr('callpy - %s %s' % (module_and_funcname_, args))
		r = getattr(__import__(modulename), funcname)(*args_)
		if looks_like_json_already(r):
			return r
		else:
			return util.to_json_str(r)
	else:
		printerr('Method %s not in allowed list.' % module_and_funcname)

def post_get_args(environ_):
	content_type, pdict = cgi.parse_header(environ_['CONTENT_TYPE'])
	if content_type != 'multipart/form-data':
		raise Exception()
	argdict = cgi.parse_multipart(environ_['wsgi.input'], pdict)
	return (argdict['arg'] if 'arg' in argdict else [])

# WSGI entry point.
def application(environ, start_response):
	if '.' not in sys.path:
		printerr('----------- having to add to sys.path') # temporary 
		printerr('sys.path was:', sys.path) # temporary 
		sys.path.append('.')
	try:
		referer = environ['HTTP_REFERER'] if 'HTTP_REFERER' in environ else None
		query_string = environ['QUERY_STRING']
		if environ['REQUEST_METHOD'] == 'POST':
			output = post_call_func(query_string, post_get_args(environ), referer)
		elif environ['REQUEST_METHOD'] == 'GET':
			output = get_call_func(query_string, referer)
		else:
			raise Exception()

		response_headers = [('Content-type', 'text/plain')]
		start_response('200 OK', response_headers)

		return [output]

	except:
		mc.close_connection()
		db.close_connection()
		raise


