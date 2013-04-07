#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, os.path, urlparse, json
from collections import Sequence
import geom, vinfo
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

class OurJSONEncoder(json.JSONEncoder):

	def default(self, o):
		if isinstance(o, geom.LatLng):
			return (o.lat, o.lng)
		elif isinstance(o, vinfo.VehicleInfo):
			return o.to_json_dict()
		else:
			return json.JSONEncoder.default(self, o)

def looks_like_json_already(obj_):
	return isinstance(obj_, basestring) and ((obj_[0] == '[' and obj_[-1] == ']') or (obj_[0] == '{' and obj_[-1] == '}'))

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
module_and_funcname = vars['module_and_funcname'][0]
allowables = ['web.get_vehicle_svg', 'traffic.get_traffics', 'traffic.get_recent_vehicle_locations', 'routes.get_all_routes_latlons', 'routes.get_trip_endpoint_info', 'routes.snaptest', 'util.get_current_wrong_dirs', 'tracks.get_all_tracks_polylines', 'snaptogrid.get_display_grid', 'routes.get_configroute_to_fudgeroute_map', 'routes.get_fudgeroutes_for_map_bounds', 'routes.get_fudgeroute_to_intdir_to_englishdesc', 'routes.get_stops_dir_to_stoptag_to_latlng', 'paths.get_paths_by_latlngs', 'routes.routepts', 'paths.get_pathgridsquare', 'routes.get_all_froute_latlngs', 'streetlabels.get_labels', 'reports.get_traffic_report', 'reports.get_locations_report', 'geom.heading']
if (module_and_funcname in allowables) or os.getenv('HTTP_REFERER').endswith('test.24972394874134958.html') \
		or module_and_funcname.startswith('t.'):
	modulename = module_and_funcname.split('.')[0]
	funcname = module_and_funcname.split('.')[1]
	args = get_arg_objvals(vars)
	if LOG_CALLS:
		printerr('callpy - %s %s' % (module_and_funcname, args))
	r = getattr(__import__(modulename), funcname)(*args)
	if looks_like_json_already(r):
		print r
	else:
		print json.dumps(r, cls=OurJSONEncoder)
else:
	printerr('Method %s not in allowed list.' % module_and_funcname)

