#!/usr/bin/python2.6

print 'Content-type: text/plain\n'

import sys, os, urlparse, json
import geom, vinfo
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

def wants_to_be_a_LatLng(obj_):
	return isinstance(obj_, MutableSequence) and len(obj_) == 2 and isinstance(obj_[0], float) and isinstance(obj_[1], float) \
			and (43.0 < obj_[0] < 44.0) and (-80 < obj_[1] < -79)

def get_arg_objvals(vardict_):
	r = []
	for arg_strval in get_arg_strvals(vardict_):
		arg_objval = json.loads(decode_url_paramval(arg_strval))
		if isinstance(arg_objval, unicode):
			arg_objval = str(arg_objval)
		elif wants_to_be_a_LatLng(arg_objval):
			arg_objval = geom.LatLng(arg_objval[0], arg_objval[1])
		r.append(arg_objval)
	return r

def first(iterable_, func_=bool):
	for e in iterable_:
		if func_(e):
			return e
	return None



class OurJSONEncoder(json.JSONEncoder):

	def default(self, o):
		if isinstance(o, geom.LatLng):
			return (o.lat, o.lng)
		elif isinstance(o, vinfo.VehicleInfo):
			return o.to_json_dict()
		else:
			return json.JSONEncoder.default(self, o)

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
module_and_funcname = vars['module_and_funcname'][0]
allowables = ['web.get_vehicle_svg', 'traffic.get_traffics', 'traffic.get_traffics_dirfromlatlngs', 'traffic.get_recent_vehicle_locations', 'traffic.get_recent_vehicle_locations_dirfromlatlngs', 'routes.get_all_routes_latlons', 'routes.get_endpoint_info', 'routes.snaptest', 'util.get_current_wrong_dirs', 'tracks.get_all_tracks_polylines', 'snaptogrid.get_display_grid', 'routes.get_configroute_to_fudgeroute_map', 'routes.get_fudgeroutes_for_map_bounds', 'routes.get_fudgeroute_to_compassdir_to_intdir']
if (module_and_funcname in allowables) or os.getenv('HTTP_REFERER').endswith('test.24972394874134958.html') \
		or module_and_funcname.startswith('t.'):
	modulename = module_and_funcname.split('.')[0]
	funcname = module_and_funcname.split('.')[1]
	args = get_arg_objvals(vars)
	r = getattr(__import__(modulename), funcname)(*args)
	print json.dumps(r, cls=OurJSONEncoder)

