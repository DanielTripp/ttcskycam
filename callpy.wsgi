#!/usr/bin/python2.6

import sys, os, os.path, urlparse, json, time, re
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

def call_func(query_string_, referer_):
	vars = urlparse.parse_qs(query_string_)
	module_and_funcname = vars['module_and_funcname'][0]
	allowables = ['web.get_vehicle_svg', 'traffic.get_traffics', 'traffic.get_recent_vehicle_locations', 'routes.get_all_routes_latlons', 'routes.get_trip_endpoint_info', 'routes.snaptest', 'util.get_current_wrong_dirs', 'tracks.get_all_tracks_polylines', 'snaptogrid.get_display_grid', 'routes.get_configroute_to_fudgeroute_map', 'routes.get_fudgeroutes_for_map_bounds', 'routes.get_fudgeroute_to_intdir_to_englishdesc', 'routes.get_stops_dir_to_stoptag_to_latlng', 'paths.get_paths_by_latlngs', 'routes.routepts', 'paths.get_pathgridsquare', 'routes.get_all_froute_latlngs', 'streetlabels.get_labels', 'reports.get_traffic_report', 'reports.get_locations_report', 'geom.heading']
	if (module_and_funcname in allowables) or \
			((referer_ is not None and os.path.basename(referer_).startswith('test.24972394874134958')) and module_and_funcname.startswith('t.')):
		modulename = module_and_funcname.split('.')[0]
		funcname = module_and_funcname.split('.')[1]
		args = get_arg_objvals(vars)
		if LOG_CALLS:
			printerr('callpy - %s %s' % (module_and_funcname, args))
		r = getattr(__import__(modulename), funcname)(*args)
		if looks_like_json_already(r):
			return r
		else:
			return util.to_json_str(r)
	else:
		printerr('Method %s not in allowed list.' % module_and_funcname)

g_mc_clear_in_process_cache_last_time_es = time.time()

def clear_mc_in_process_cache_maybe():
	global g_mc_clear_in_process_cache_last_time_es
	now = time.time()
	if now - g_mc_clear_in_process_cache_last_time_es > 60*10:
		mc.clear_in_process_cache()
		g_mc_clear_in_process_cache_last_time_es = now

# WSGI entry point.
def application(environ, start_response):
	if '.' not in sys.path:
		printerr('----------- having to add to sys.path') # temporary 
		printerr('sys.path was:', sys.path) # temporary 
		sys.path.append('.')
	try:
		query_string = environ['QUERY_STRING']
		referer = environ['HTTP_REFERER'] if 'HTTP_REFERER' in environ else None
		output = call_func(query_string, referer)

		response_headers = [('Content-type', 'text/plain')]
		start_response('200 OK', response_headers)

		clear_mc_in_process_cache_maybe()

		return [output]

	except:
		mc.close_connection()
		db.close_connection()
		raise


