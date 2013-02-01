#!/usr/bin/python2.6

# Tables involved: 
# 
# create table ttc_vehicle_locations (vehicle_id varchar(100), route_tag varchar(100), dir_tag varchar(100), lat double precision, lon double precision, secs_since_report integer, time_retrieved bigint, time_str varchar(100), predictable boolean, heading integer, rowid serial unique, mofr integer, widemofr integer);
# create index ttc_vehicle_locations_idx on ttc_vehicle_locations (route_tag, time_retrieved desc);
# create index ttc_vehicle_locations_idx2 on ttc_vehicle_locations (vehicle_id, time_retrieved desc);
# 
# create table predictions (fudgeroute VARCHAR(100), configroute VARCHAR(100), stoptag VARCHAR(100), time_retrieved_str varchar(30), time_of_prediction_str varchar(30), dirtag VARCHAR(100), vehicle_id VARCHAR(100), is_departure boolean, block VARCHAR(100), triptag VARCHAR(100), branch VARCHAR(100), affected_by_layover boolean, is_schedule_based boolean, delayed boolean, time_retrieved bigint, time_of_prediction bigint, rowid serial unique);
# create index predictions_idx on predictions (fudgeroute, stoptag, time_retrieved desc);

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, pprint, json, socket, datetime, calendar, math
from collections import defaultdict, Sequence
import vinfo, geom, traffic, routes, yards, tracks, predictions, mc
from misc import *

HOSTMONIKER_TO_IP = {'theorem': '72.2.4.176', 'black': '24.52.231.206'}

VI_COLS = ' dir_tag, heading, vehicle_id, lat, lon, predictable, route_tag, secs_since_report, time_retrieved, time, mofr, widemofr '

PREDICTION_COLS = ' fudgeroute, configroute, stoptag, time_retrieved, time_of_prediction, vehicle_id, is_departure, block, dirtag, triptag, branch, affected_by_layover, is_schedule_based, delayed'

WRITE_MOFRS = os.path.exists('WRITE_MOFRS')

g_conn = None
g_forced_hostmoniker = None

def force_host(hostmoniker_):
	global g_forced_hostmoniker
	g_forced_hostmoniker = hostmoniker_

def connect():
	global g_conn
	DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='postgres' host='%s' password='doingthis'" % (get_host()),)
	DATABASE_CONNECT_KEYWORD_ARGS = {}
	DATABASE_DRIVER_MODULE_NAME = 'psycopg2'
	USE_DB_DRIVER_IN_CURRENT_DIRECTORY = socket.gethostname().endswith('theorem.ca')
	if USE_DB_DRIVER_IN_CURRENT_DIRECTORY:
		driver_module = __import__(DATABASE_DRIVER_MODULE_NAME)
	else:
		saved_syspath = sys.path
		for path_elem_to_remove in ('', '.', os.getcwd()):
			while path_elem_to_remove in sys.path:
				sys.path.remove(path_elem_to_remove)
		driver_module = __import__(DATABASE_DRIVER_MODULE_NAME)
		sys.path = saved_syspath
	g_conn = getattr(driver_module, 'connect')(*DATABASE_CONNECT_POSITIONAL_ARGS, **DATABASE_CONNECT_KEYWORD_ARGS)

def get_host():
	if g_forced_hostmoniker is not None:
		hostmoniker = g_forced_hostmoniker
	else:
		with open('HOST') as fin:
			hostmoniker = fin.read().strip()
	if hostmoniker == 'local':
		if socket.gethostname().endswith('theorem.ca'):
			hostmoniker = 'theorem'
		else:
			hostmoniker = 'black'
	if hostmoniker not in HOSTMONIKER_TO_IP:
		raise Exception('Unknown host moniker: "%s"' % hostmoniker)
	return HOSTMONIKER_TO_IP[hostmoniker]

def conn():
	if g_conn is None:
		connect()
	return g_conn

def reconnect():
	global g_conn
	# Not sure if this try/except is necessary.  Doing it because I would hate for a close() throwing 
	# something to ruin my day here. 
	try:
		g_conn.close()
	except:
		pass
	g_conn = None
	connect()

def trans(f):
	"""Decorator that calls commit() after the method finishes normally, or rollback() if an
	exception is raised.  

	That we call commit() / rollback() is of course necessary in the absence of any standard
	'auto-commit mode' that we can count on.
	""" 
	def new_f(*args, **kwds):
		try:
			returnval = f(*args, **kwds)
			conn().commit()
			return returnval
		except:
			conn().rollback()
			raise
	return new_f

@trans
def insert_vehicle_info(vi_):
	curs = conn().cursor()
	if WRITE_MOFRS:
		mofr = vi_.mofr; widemofr = vi_.widemofr
	else:
		mofr = None; widemofr = None
	cols = [vi_.vehicle_id, vi_.route_tag, vi_.dir_tag, vi_.lat, vi_.lng, vi_.secs_since_report, vi_.time_retrieved, \
		vi_.predictable, vi_.heading, vi_.time, em_to_str(vi_.time), mofr, widemofr]
	curs.execute('INSERT INTO ttc_vehicle_locations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,default,%s,%s)', cols)
	curs.close()

def vi_select_generator(configroute_, end_time_em_, start_time_em_, dir_=None, include_unpredictables_=False, vid_=None, \
			forward_in_time_order_=False):
	curs = (conn().cursor('cursor_%d' % (int(time.time()*1000))) if start_time_em_ == 0 else conn().cursor())
	dir_clause = ('and dir_tag like \'%%%%\\\\_%s\\\\_%%%%\' ' % (str(dir_)) if dir_ != None else ' ')
	sql = 'select '+VI_COLS+' from ttc_vehicle_locations where route_tag = %s '\
		+('' if include_unpredictables_ else ' and predictable = true ') \
		+' and time <= %s and time >= %s and time_retrieved <= %s '\
		+(' and vehicle_id = %s ' if vid_ else '') \
		+ dir_clause \
		+(' order by time' if forward_in_time_order_ else ' order by time desc')
	curs.execute(sql, [configroute_, end_time_em_, start_time_em_, end_time_em_] + ([vid_] if vid_ else []))
	while True:
		row = curs.fetchone()
		if not row:
			break
		vi = vinfo.VehicleInfo(*row)
		yield vi
	curs.close()

# arg for_traffic_ True means intended for colour-coded traffic display.  False means for vehicle animations. 
# return dict.  key: vid.  value: list of list of VehicleInfo.

# Note [1]: Here we attempt to remove what we consider trivial and unimportant (or even misleading) stretches of vis.
# Currently using a heuristic of greater than 5 vis, or 300 meters.  Doing this because often due to inaccurate GPS readings
# or other things, especially after our 'dirtag fixing' (where we ignore the direction of the dirtag reported by NextBus and
# set it to one determined by mofr changes).  This can result in a vehicle appearing to reverse direction for a short time
# before continuing in it's original direction, but the reality is not so.
#
# When this function is used for vehicle locations (as opposed to color-coded traffic) and it involves vehicles taking detours,
# a less than desirable situation can occur sometimes.  If a vehicle takes a detour and the angle of the streets in that area
# makes the widemofrs of the vehicle appear to be reversing (for example an eastbound Dundas vehicle detouring up Ossington
# the continuing east on College) then the dirtag will be 'fixed' via widemofr and will appear to reverse for part of the detour.
# While going eastbound on Dundas the vehicle will have increasing mofrs (and widemofrs) but then while going up Ossington it will have
# decreasing widemofrs until it turns onto College where it will have increasing widemofrs again.
#
# So we want those vis going up Ossington, but only if the vehicle is going to continue east after.  We can't tell if it is or not
# if in the time window in question, it hasn't done that yet.  So in that case the vehicle will disappear from the vehicle locations.
# That is undesirable but not the end of the world.  For a user watching current conditions, that situation for that vehicle will
# usually last only a couple of minutes, until the vehicle gets onto part of the detour that is closer to parallel to the origanal route
# (i.e. Colleg).  Then the widemofrs will increase again, and the vehicle-location-interpolating code will having something to
# interpolate between (presumably something on Dundas right before it turned up Ossington, and something on College right after it
# turned onto College.)  These interpolated locations will not be as accurate as if we hadn't removed them in the first place,
# but I don't see this as a major problem right now.    Again this will only happen in a small number of cases where detours are happening
# on streets at odd angles.  With detours on streets at right angles, the mofr while going up the first street of the detour will
# hopefully stay pretty close to unchanged for that stretch, so hopefully the dirtag won't be fixed.  But the more I think about it,
# the less I would count on it.  I haven't tested that.  More work is warranted here. Question for dirtag-fixing:
# if widemofrs go like this: [0, 50, 100, 101, 100, 101, 100, 101, 100, 150, 200, ...] do we throw out the whole middle part
# [100, 101, 100, 101, 100]?  Wouldn't it be better if we tried to keep the two 101s in there?  That would give us more accurate
# interpolations in that area.
def get_vid_to_vis(fudge_route_, dir_, num_minutes_, end_time_em_, for_traffic_, current_conditions_, log_=False):
	assert dir_ in (0, 1)
	MIN_DESIRABLE_DIR_STRETCH_LEN = 6
	start_time = end_time_em_ - num_minutes_*60*1000
	vi_list = []
	for configroute in routes.fudgeroute_to_configroutes(fudge_route_):
		vis = list(vi_select_generator(configroute, end_time_em_, start_time, None, True))
		# We want to get a lot of overshots, because we need a lot of samples in order to determine directions with any certainty.
		vis += get_outside_overshots(vis, start_time, False, MIN_DESIRABLE_DIR_STRETCH_LEN-1, log_=log_)
		if not for_traffic_:
			if current_conditions_:
				pass # TODO: think about whether to re-introduce the call below.
				# add_inside_overshots_for_locations(r, direction_, time_window_end_, log_=log_)
			else:
				vis[:] = get_outside_overshots(vis, end_time_em_, True, log_=log_) + vis
		vi_list += vis
	# TODO: maybe get outside overshots /forward/ here too, for the benefit of historical traffic reports.
	vid_to_vis = file_under_key(vi_list, lambda vi: vi.vehicle_id)
	for vis in vid_to_vis.values():
		vis.sort(key=lambda x: x.time, reverse=True)
	for vid, vis in vid_to_vis.items():
		yards.remove_vehicles_in_yards(vis)
		remove_time_duplicates(vis)
		geom.remove_bad_gps_readings_single_vid(vis, log_=log_)
		fix_dirtags(vis)
		if len(vis) == 0: del vid_to_vis[vid]
	for vid, vis in vid_to_vis.items():
		vis_grouped_by_dir = get_maximal_sublists3(vis, lambda vi: vi.dir_tag_int) # See note [1] above
		def is_desirable(vis__):
			return (vis__[0].dir_tag_int == dir_) and (len(vis__) >= MIN_DESIRABLE_DIR_STRETCH_LEN or abs(vis__[0].widemofr - vis__[-1].widemofr) > 300)
		vis_desirables_only = filter(is_desirable, vis_grouped_by_dir)
		vis[:] = sum(vis_desirables_only, [])
	for vid in vid_to_vis.keys():
		if len(vid_to_vis[vid]) == 0:
			del vid_to_vis[vid]
	return vid_to_vis

def remove_time_duplicates(vis_):
	for i in range(len(vis_)-2, -1, -1): # Removing duplicates by time.  Not sure if this ever happens.
		if vis_[i].time == vis_[i+1]:
			del vis_[i]

def fix_dirtags(r_vis_):
	assert len(set(vi.vehicle_id for vi in r_vis_)) <= 1
	for prevvi, vi in hopscotch(r_vis_[::-1]):
		if prevvi.widemofr < vi.widemofr:
			fix_dirtag(vi, 0)
		elif prevvi.widemofr > vi.widemofr:
			fix_dirtag(vi, 1)
		elif (prevvi.widemofr == vi.widemofr) and (prevvi.dir_tag_int in (0, 1)):
			fix_dirtag(vi, prevvi.dir_tag_int)

def fix_dirtag(vi_, dir_):
	assert isinstance(vi_, vinfo.VehicleInfo) and dir_ in (0, 1)
	if dir_ == vi_.dir_tag_int:
		pass
	elif vi_.dir_tag_int == 1 and dir_ == 0:
		vi_.dir_tag = vi_.dir_tag.replace('_1_', '_0_')
		vi_.is_dir_tag_corrected = True
	elif vi_.dir_tag_int == 0 and dir_ == 1:
		vi_.dir_tag = vi_.dir_tag.replace('_0_', '_1_')
		vi_.is_dir_tag_corrected = True
	elif vi_.dir_tag_int is None:
		assert vi_.dir_tag == ''
		vi_.dir_tag = '%s_%d_%s' % (vi_.route_tag, dir_, vi_.route_tag)
		vi_.is_dir_tag_corrected = True
	else:
		raise Exception('Don\'t know how to fix dir_tag on %s' % str(vi_))

def fix_dirtag_str(dir_tag_, dir_, route_tag_):
	assert isinstance(dir_tag_, basestring) and dir_ in (0, 1)
	dir_tag_int = get_dir_tag_int(dir_tag_)
	if dir_ == dir_tag_int:
		return dir_tag_
	elif dir_tag_int == 1 and dir_ == 0:
		return dir_tag_.replace('_1_', '_0_')
	elif dir_tag_int == 0 and dir_ == 1:
		return dir_tag_.replace('_0_', '_1_')
	elif dir_tag_int is None:
		assert dir_tag_ == ''
		return '%s_%d_%s' % (route_tag_, dir_, route_tag_)
	else:
		raise Exception('Don\'t know how to fix dir_tag "%s"' % dir_tag_)

def find_passing(croute_, vid_, start_time_, end_time_, post_, dir_):
	assert isinstance(croute_, str) and isinstance(vid_, basestring) and isinstance(post_, geom.LatLng)
	lastvi = None
	gen = vi_select_generator(croute_, end_time_, start_time_, dir_=dir_, include_unpredictables_=True, vid_=vid_, forward_in_time_order_=True)
	for curvi in gen:
		if lastvi and geom.passes(curvi.latlng, lastvi.latlng, post_, tolerance_=1) \
				and lastvi.mofr != -1 and curvi.mofr != -1 and mofrs_to_dir(lastvi.mofr, curvi.mofr) == dir_:
			return (lastvi, curvi)
		lastvi = curvi
	return None

def massage_whereclause_time_args(whereclause_):
	if not whereclause_:
		return whereclause_
	else:
		r = whereclause_
		def repl1(mo_):
			return str(str_to_em(mo_.group(0).strip('\'"')))
		r = re.sub(r'[\'"]\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?[\'"]', repl1, r)

		r = re.sub(r'\bnow\b', str(now_em()), r)

		def repl2(mo_):
			t = int(mo_.group(1))
			range = 15*60*1000
			return 'time > %d and time < %d' % (t - range, t + range)
		r = re.sub(r'time +around +(\d+)', repl2, r)

		def repl3(mo_):
			t = int(mo_.group(3))
			def rangestr_to_em(str_):
				if str_.endswith('h'):
					return int(str_[:-1])*60*60*1000
				else:
					return int(str_)*60*1000
			lo_range = rangestr_to_em(mo_.group(1)); hi_range = rangestr_to_em(mo_.group(2))
			return 'time > %d and time < %d' % (t - lo_range, t + hi_range)
		r = re.sub(r'time +around\((\w+),(\w+)\) +(\d+)', repl3, r)
		return r

def massage_whereclause_lat_args(whereclause_):
	with open('debug-vehicle-lat-grid.json') as fin:
		grid_lats = json.load(fin)
	def repl(mo_):
		n = float(mo_.group(1))
		floorn = int(math.floor(n)); ceiln = int(math.ceil(n))
		lat = get_range_val((floorn, grid_lats[floorn]), (ceiln, grid_lats[ceiln]), n)
		return str(lat)
	return re.sub(r'\b(\d+(?:\.\d+)?)lat\b', repl, whereclause_)

def massage_whereclause_lon_args(whereclause_):
	with open('debug-vehicle-lon-grid.json') as fin:
		grid_lons = json.load(fin)
	def repl(mo_):
		n = float(mo_.group(1))
		floorn = int(math.floor(n)); ceiln = int(math.ceil(n))
		lon = get_range_val((floorn, grid_lons[floorn]), (ceiln, grid_lons[ceiln]), n)
		return str(lon)
	return re.sub(r'\b(\d+(?:\.\d+)?)lon\b', repl, whereclause_)

def massage_whereclause_dir_args(whereclause_):
	r = whereclause_
	r = re.sub('dir *= *0', 'dir_tag like \'%%%%\\\\\\\\_0\\\\\\\\_%%%%\'', r)
	r = re.sub('dir *= *1', 'dir_tag like \'%%%%\\\\\\\\_1\\\\\\\\_%%%%\'', r)
	r = re.sub('dir +blank', 'dir_tag = \'\'', r)
	return r

def massage_whereclause_route_args(whereclause_):
	r = whereclause_
	r = re.sub(r'route += +(\w+)', 'route_tag = \'\\1\'', r)
	return r

def massage_whereclause_vid_args(whereclause_):
	r = whereclause_
	r = re.sub(r'vid += +(\w+)', 'vehicle_id = \'\\1\'', r)
	return r

def massage_whereclause(whereclause_):
	r = whereclause_
	r = massage_whereclause_time_args(r)
	r = massage_whereclause_lat_args(r)
	r = massage_whereclause_lon_args(r)
	r = massage_whereclause_dir_args(r)
	r = massage_whereclause_route_args(r)
	r = massage_whereclause_vid_args(r)
	r = make_whereclause_safe(r)
	printerr('Post-massage sql str: '+r)
	return r

# returns a list of lists of VehicleInfo objects.  each sub-list represents a timeslice.  
def query1(whereclause_, maxrows_, interp_by_time_):
	assert type(whereclause_) == str and type(maxrows_) == int and type(interp_by_time_) == bool
	whereclause = massage_whereclause(whereclause_)
	r = []
	sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations where ' \
		+ (whereclause if whereclause else 'true')+' order by time desc limit %d' % (maxrows_)
	curs = conn().cursor()
	curs.execute(sqlstr)
	for row in curs:
		r.append(vinfo.VehicleInfo(*row))
	curs.close()
	if interp_by_time_:
		r = interp_by_time(r, False, False, False)
	else:
		r = group_by_time(r)
	return r

def make_whereclause_safe(whereclause_):
	return re.sub('(?i)insert|delete|drop|create|truncate|alter|update|;', '', whereclause_)

def get_recent_vehicle_locations(fudgeroute_, num_minutes_, direction_, current_conditions_, time_window_end_, log_=False):
	assert type(fudgeroute_) == str and type(num_minutes_) == int and direction_ in (0,1)
	vid_to_vis = get_vid_to_vis(fudgeroute_, direction_, num_minutes_, time_window_end_, False, current_conditions_, log_=log_)
	r = []
	for vid, vis in vid_to_vis.iteritems():
		if log_: printerr('For locations, pre-interp: vid %s: %d vis, from %s to %s (widemofrs %d to %d)' \
				% (vid, len(vis), em_to_str_hms(vis[-1].time), em_to_str_hms(vis[0].time), vis[-1].widemofr, vis[0].widemofr))
		r += [vi for vi in vis if vi.widemofr != -1]
	starttime = time_window_end_ - num_minutes_*60*1000
	r = interp_by_time(r, True, True, current_conditions_, direction_, starttime, time_window_end_, log_=log_)
	return r

# The idea here is, for each vid, to get one more vi from the db, greater in time than the pre-existing
# max time vi.  This new vi may be on a different route or direction, but it will help us show that vehicle
# a little longer on the screen, which I think is desirable.
# ^^ I'm not sure of the usefulness of this any more. 
def add_inside_overshots_for_locations(r_vis_, vid_, time_window_end_, log_=False):
	assert len(set([vi.vehicle_id for vi in r_vis_])) == 1
	new_vis = []
	time_to_beat = max(vi.time for vi in r_vis_ if vi.vehicle_id == vid_)
	sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
		+ ' where vehicle_id = %s and time > %s and time <= %s order by time limit 1' 
	curs = conn().cursor()
	curs.execute(sqlstr, [vid_, time_to_beat, time_window_end_])
	row = curs.fetchone()
	vi = None
	if row:
		vi = vinfo.VehicleInfo(*row)
		if log_: printerr('Got inside overshot: %s' % (str(vi)))
		new_vis.append(vi)
	else:
		if log_: printerr('No inside overshot found for vid %s.' % (vid_))
	curs.close()
	r_vis_ += new_vis
	r_vis_.sort(key=lambda vi: vi.time, reverse=True)

# Temporary detours typically have a blank dirTag eg. dundas eastbound 2012-06-09 12:00. 
# See http://groups.google.com/group/nextbus-api-discuss/browse_thread/thread/61fc64649ab928b5 
# "Detours and dirTag (Toronto / TTC)"
# Vehicles that are stuck badly also, at least sometimes, have a blank dir_tag for that time.  eg. vid 4104, 2012-09-24 13:00.
# So here we make a point of not removing those.
def remove_unwanted_detours(r_vis_, fudgeroute_, direction_, log_=False):
	routes_general_heading = routes.routeinfo(fudgeroute_).general_heading(direction_)
	for detour in get_blank_dirtag_stretches(r_vis_):
		unwanted = False
		# Keep detours with a length of 1. This might not be right but they probably won't do much harm either.  
		# Also making an attempt here to not throw out vehicles stopped dead.  
		if (len(detour) >= 2) and (detour[-1].latlng.dist_m(detour[0].latlng) > 15):
			assert all(e1.time > e2.time for e1, e2 in hopscotch(detour))
			detours_heading = detour[-1].latlng.heading(detour[0].latlng)
			heading_diff = geom.diff_headings(routes_general_heading, detours_heading)
			if heading_diff > 80:
				unwanted = True
		if unwanted:
			remove_all_by_identity(r_vis_, detour)
		if log_:
			logstr = 'vehicle %s from %s to %s.' % (detour[0].vehicle_id, em_to_str(detour[-1].time), em_to_str(detour[0].time))
			printerr('%sing apparent detour: %s' % (('Discard' if unwanted else 'Keep'), logstr))

def remove_all_by_identity(r_list_, to_remove_list_):
	for to_remove_elem in to_remove_list_:
		for r_list_i, r_list_elem in enumerate(r_list_):
			if r_list_elem is to_remove_elem:
				del r_list_[r_list_i]
				break

def get_blank_dirtag_stretches(vis_):
	r = []
	for vid in set(vi.vehicle_id for vi in vis_):
		vid_vis = [vi for vi in vis_ if vi.vehicle_id == vid]
		r += get_maximal_sublists(vid_vis, lambda vi: vi.dir_tag == '')
	return r

def get_maximal_sublists(list_, predicate_):
	cur_sublist = None
	r = []
	for e in list_:
		if predicate_(e):
			if cur_sublist == None:
				cur_sublist = []
				r.append(cur_sublist)
			cur_sublist.append(e)
		else:
			cur_sublist = None
	return r

# Fetch one row before startime (or after endtime), to give us something to interpolate with.
def get_outside_overshots(vilist_, time_window_boundary_, forward_in_time_, n_=1, log_=False):
	forward_str = ('forward' if forward_in_time_ else 'backward')
	if not vilist_:
		return []
	r = []
	for vid in set([vi.vehicle_id for vi in vilist_]):
		vis_for_vid = [vi for vi in vilist_ if vi.vehicle_id == vid]
		assert all(vi1.time >= vi2.time for vi1, vi2 in hopscotch(vis_for_vid)) # i.e. is in reverse order 
		vid_extreme_time = vis_for_vid[0 if forward_in_time_ else -1].time
		if log_: printerr('Looking for %s overshot for vid %s.  Time to beat is %s.' % (forward_str, vid, em_to_str(vid_extreme_time)))
		routes = [vi.route_tag for vi in vilist_]
		sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
			+ ' where vehicle_id = %s ' + ' and route_tag in ('+(','.join(['%s']*len(routes)))+')' + ' and time < %s and time > %s '\
			+ ' order by time '+('' if forward_in_time_ else 'desc')+' limit '+str(n_)
		curs = conn().cursor()
		curs.execute(sqlstr, [vid] + routes \
			+ ([time_window_boundary_+20*60*1000, vid_extreme_time] if forward_in_time_ else [vid_extreme_time, time_window_boundary_-20*60*1000]))
	 	# TODO: 20 minutes (above) may be a bit much, especially now that I'm using this function for traffic (not just vehicle locations).
		# TODO: Think about this.
		for row in curs:
			vi = vinfo.VehicleInfo(*row)
			if log_: printerr('Got %s outside overshot: %s' % (forward_str, str(vi)))
			r.append(vi)
		curs.close()
	return r

def group_by_time(vilist_):
	times = sorted(list(set([vi.time for vi in vilist_])))
	r = [[em_to_str(time)] for time in times]
	for vi in vilist_:
		time_idx = times.index(vi.time)
		r[time_idx].append(vi)
	return r

# Takes a flat list of VehicleInfo objects.  Returns a list of lists of Vehicleinfo objects, interpolated.
# Also, with a date/time string as element 0 in each list.
def interp_by_time(vilist_, be_clever_, use_db_for_heading_inference_, current_conditions_, dir_=None, start_time_=None, end_time_=None, log_=False):
	assert isinstance(vilist_, Sequence)
	if len(vilist_) == 0:
		return []
	starttime = (round_up_by_minute(start_time_) if start_time_ is not None else round_down_by_minute(min(vi.time for vi in vilist_)))
	endtime = (round_up_by_minute(end_time_) if end_time_ is not None else max(vi.time for vi in vilist_))
	vids = set(vi.vehicle_id for vi in vilist_)
	time_to_vis = {}
	for interptime in lrange(starttime, endtime+1, 60*1000):
		interped_timeslice = []
		for vid in vids:
			lolo_vi, lo_vi, hi_vi = get_nearest_time_vis(vilist_, vid, interptime)
			i_vi = None
			if lo_vi and hi_vi:
				if (min(interptime - lo_vi.time, hi_vi.time - interptime) > 3*60*1000) or dirs_disagree(dir_, hi_vi.dir_tag_int)\
						or (lo_vi.route_tag != hi_vi.route_tag):
					continue
				ratio = (interptime - lo_vi.time)/float(hi_vi.time - lo_vi.time)
				i_latlon, i_heading, i_mofr = interp_latlonnheadingnmofr(lo_vi, hi_vi, ratio, be_clever_)
				i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, i_heading, vid, i_latlon.lat, i_latlon.lng,
										 lo_vi.predictable and hi_vi.predictable,
										 lo_vi.route_tag, 0, interptime, interptime, i_mofr, None)
			elif lo_vi and not hi_vi:
				if current_conditions_:
					if (interptime - lo_vi.time > 3*60*1000) or dirs_disagree(dir_, lo_vi.dir_tag_int):
						continue
					heading = (lolo_vi.latlng.heading(lo_vi.latlng) if lolo_vi is not None else lo_vi.heading)
					i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, heading, vid, lo_vi.lat, lo_vi.lng,
											 lo_vi.predictable, lo_vi.route_tag, 0, interptime, interptime, lo_vi.mofr, lo_vi.widemofr)

			if i_vi:
				interped_timeslice.append(i_vi)

		time_to_vis[interptime] = interped_timeslice
	return massage_to_list(time_to_vis, starttime, endtime)

# Either arg could be None (i.e. blank dir_tag).  For this we consider None to 'agree' with 0 or 1.
def dirs_disagree(dir1_, dir2_):
	return (dir1_ == 0 and dir2_ == 1) or (dir1_ == 1 and dir2_ == 0)

# be_clever_ - means use routes if mofrs are valid, else use 'tracks' if a streetcar.
def interp_latlonnheadingnmofr(vi1_, vi2_, ratio_, be_clever_):
	assert isinstance(vi1_, vinfo.VehicleInfo) and isinstance(vi2_, vinfo.VehicleInfo) and (vi1_.vehicle_id == vi2_.vehicle_id)
	assert vi1_.time < vi2_.time
	r = None
	if be_clever_ and vi1_.dir_tag and vi2_.dir_tag:
		if routes.CONFIGROUTE_TO_FUDGEROUTE[vi1_.route_tag] == routes.CONFIGROUTE_TO_FUDGEROUTE[vi2_.route_tag]:
			config_route = vi1_.route_tag
			vi1mofr = routes.latlon_to_mofr(config_route, vi1_.latlng)
			vi2mofr = routes.latlon_to_mofr(config_route, vi2_.latlng)
			if vi1mofr!=-1 and vi2mofr!=-1:
				interp_mofr = geom.avg(vi1mofr, vi2mofr, ratio_)
				dir_tag_int = vi2_.dir_tag_int
				if dir_tag_int == None:
					raise Exception('Could not determine dir_tag_int of %s' % (str(vi2_)))
				r = routes.mofr_to_latlonnheading(config_route, interp_mofr, dir_tag_int) + (interp_mofr,)
			elif vi1_.is_a_streetcar():
				vi1_tracks_snap_result = tracks.snap(vi1_.latlng); vi2_tracks_snap_result = tracks.snap(vi2_.latlng)
				if vi1_tracks_snap_result is not None and vi2_tracks_snap_result is not None:
					simple_interped_loc = vi1_.latlng.avg(vi2_.latlng, ratio_)
					interped_loc_snap_result = tracks.snap(simple_interped_loc, 5000)
					if interped_loc_snap_result is not None:
						tracks_based_heading = tracks.heading(interped_loc_snap_result[1], interped_loc_snap_result[2])
						if geom.diff_headings(tracks_based_heading, vi1_.latlng.heading(vi2_.latlng)) > 90:
							tracks_based_heading = geom.normalize_heading(tracks_based_heading+180)
						r = (interped_loc_snap_result[0], tracks_based_heading, None)

	if r is None:
		r = (vi1_.latlng.avg(vi2_.latlng, ratio_), vi1_.latlng.heading(vi2_.latlng), None)
	return r

def massage_to_list(time_to_vis_, start_time_, end_time_):
	time_to_vis = time_to_vis_.copy()

	# Deleting one empty timeslice at the end of the time frame.
	# doing this because the last timeslice is the current vehicle locations of course, and that is an important
	# timeslice and will be rendered differently in the GUI.
	#latest_time = sorted(time_to_vis.keys())[-1]
	#if len(time_to_vis[latest_time]) == 0:
	#	del time_to_vis[latest_time]

	for time in time_to_vis.keys():
		if time < start_time_ or time > end_time_:
			del time_to_vis[time]

	r = []
	for time in sorted(time_to_vis.keys()):
		vis = time_to_vis[time]
		r.append([em_to_str(time)] + vis)
	return r

# return (lolo, lo, hi).  lo and hi bound t_ by time.  lolo is one lower than lo.
def get_nearest_time_vis(vilist_, vid_, t_):
	assert type(t_) == long
	vis = [vi for vi in vilist_ if vi.vehicle_id == vid_]
	if len(vis) == 0:
		return (None, None, None)
	assert is_sorted(vis, reverse=True, key=lambda vi: vi.time)
	r_lo = None; r_hi = None
	for hi_idx in range(len(vis)-1):
		lo_idx = hi_idx+1
		hi = vis[hi_idx]; lo = vis[lo_idx]
		if hi.time > t_ >= lo.time:
			return ((vis[lo_idx+1] if lo_idx < len(vis)-1 else None), lo, hi)
	if t_ >= vis[0].time:
		return (vis[1] if len(vis) >= 2 else None, vis[0], None)
	elif t_ < vis[-1].time:
		 return (None, None, vis[-1])
	else:
		return (None, None, None)

# returns a list of 2-tuples - (fore VehicleInfo, stand VehicleInfo)
# list probably has max_ elements.
def get_recent_passing_vehicles(route_, post_, max_, end_time_em_=now_em(), dir_=None, include_unpredictables_=False):
	vid_to_lastvi = {}
	n = 0
	r = []
	for curvi in vi_select_generator((route_,), end_time_em_, 0, dir_, include_unpredictables_):
		if len(r) >= max_:
			break
		vid = curvi.vehicle_id
		if vid in vid_to_lastvi:
			lastvi = vid_to_lastvi[vid]
			if geom.passes(curvi.latlng, lastvi.latlng, post_):
				r.append((curvi, lastvi))
		vid_to_lastvi[vid] = curvi
	return r

def purge():
	if not socket.gethostname().endswith('theorem.ca'):
		raise Exception('Not running on theorem.ca?')

	force_host('theorem')

	purge_delete()
	purge_vacuum()

@trans
def purge_delete():
	curs = conn().cursor()
	# Delete all rows older than 12 hours:
	curs.execute('delete from ttc_vehicle_locations where time < round(extract(epoch from clock_timestamp())*1000) - 1000*60*60*12;')
	curs.execute('delete from predictions where time_retrieved < round(extract(epoch from clock_timestamp())*1000) - 1000*60*60*12;')
	curs.close()

def purge_vacuum():
	old_isolation_level = conn().isolation_level
	conn().set_isolation_level(0)
	curs = conn().cursor()
	curs.execute('vacuum full;')
	curs.close()
	conn().set_isolation_level(old_isolation_level)

@trans
def insert_predictions(predictions_):
	assert isinstance(predictions_, Sequence)
	curs = conn().cursor()
	if len(predictions_) > 0:
		for p in predictions_:
			assert isinstance(p, predictions.Prediction)
			cols = [p.froute, p.croute, p.stoptag, em_to_str(p.time_retrieved), em_to_str(p.time), p.dirtag, p.vehicle_id, 
					p.is_departure, p.block, p.triptag, p.branch, p.affected_by_layover, p.is_schedule_based, p.delayed, 
					p.time_retrieved, p.time]
			curs.execute('INSERT INTO predictions VALUES (%s)' % ', '.join(['%s']*len(cols)), cols)
	curs.close()

# returns list of Prediction 
def get_predictions(froute_, start_stoptag_, dest_stoptag_, time_):
	assert routes.routeinfo(froute_).are_predictions_recorded(start_stoptag_)
	time_ = massage_time_arg(time_, 60*1000)
	curs = conn().cursor()
	where_clause = ' where fudgeroute = %s and stoptag = %s and time_retrieved between %s and %s' 
	sqlstr = 'select '+PREDICTION_COLS+' from predictions '+where_clause\
		+ ' and time_retrieved = (select max(time_retrieved) from predictions '+where_clause+') ' \
		+ ' order by time_of_prediction'
	curs.execute(sqlstr, [froute_, start_stoptag_, time_-1000*60*15, time_]*2)
	r = []
	for row in curs:
		prediction = predictions.Prediction(*row)

		if prediction.time < time_: # Not a big deal.  Handling the case of the query above
			continue # returning some predictions from towards the beginning of the 15-minute window,
				# and the predicted arrival time of some of those having already passed (assuming that time_ is the current time)
				# so there is no point in returning them.  This will tend to happen more if predictions
				# have been not showing up in the db for the last few minutes.

		if dest_stoptag_ is not None:
			if prediction.dirtag in routes.routeinfo(froute_).get_stop(dest_stoptag_).dirtags_serviced:
				r.append(prediction)
		else:
			r.append(prediction)
	curs.close()
	return r

# a generator.  yields a Prediction.
def get_predictions_gen(froute_, start_stoptag_, dest_stoptag_, time_retrieved_min_, time_retrieved_max_):
	time_retrieved_min_ = massage_time_arg(time_retrieved_min_)
	time_retrieved_max_ = massage_time_arg(time_retrieved_max_)
	assert routes.routeinfo(froute_).are_predictions_recorded(start_stoptag_) and (time_retrieved_min_ < time_retrieved_max_)
	curs = conn().cursor()
	sqlstr = 'select '+PREDICTION_COLS+' from predictions where fudgeroute = %s and stoptag = %s and time_retrieved between %s and %s '\
			+' order by time_retrieved'
	curs.execute(sqlstr, [froute_, start_stoptag_, time_retrieved_min_, time_retrieved_max_])
	for row in curs:
		prediction = predictions.Prediction(*row)
		if (dest_stoptag_ is None) or (prediction.dirtag in routes.routeinfo(froute_).get_stop(dest_stoptag_).dirtags_serviced):
			yield prediction
	curs.close()

# a generator.  yields a list of Prediction.
def get_predictions_group_gen(froute_, start_stoptag_, dest_stoptag_, time_retrieved_min_, time_retrieved_max_):
	predictions = [] # build this up, yield it, clear it, repeat.
	def sort_predictions():
		predictions.sort(key=lambda p: p.time)
	for prediction in get_predictions_gen(froute_, start_stoptag_, dest_stoptag_, time_retrieved_min_, time_retrieved_max_):
		if len(predictions) == 0 or predictions[0].time_retrieved == prediction.time_retrieved:
			predictions.append(prediction)
		else:
			sort_predictions()
			yield predictions
			del predictions[:]
			predictions.append(prediction)
	if len(predictions) > 0:
		sort_predictions()
		yield predictions

def t():
	#curs = conn().cursor('cursor_%d' % (int(time.time()*1000)))
	curs = conn().cursor()
	sql = "select * from ttc_vehicle_locations where route_tag = '505' and time <= 1330492156395 and time >= 1330491481877 and dir_tag like '%%%%\\_0\\_%%%%' and predictable = true order by time desc"
	curs.execute(sql, [])
	while True:
		row = curs.fetchone()
		if not row:
			break
		#print row[0]

def routes_clause(froute_):
	return 'route_tag in ('+(','.join(["'%s'" % croute for croute in routes.FUDGEROUTE_TO_CONFIGROUTES[froute_]]))+')'

# Scenario - waiting at startmofr_ at time_ for the next vehicle to come.
# Return map containing keys 'time_caught', 'time_arrived', and 'vid'.
# Times are absolute epoch times in millis, not a relative time spent travelling.
def get_observed_arrival_time(froute_, startstoptag_, deststoptag_, time_):
	return mc.get(get_observed_arrival_time_impl, [froute_, startstoptag_, deststoptag_, time_])

def get_observed_arrival_time_impl(froute_, startstoptag_, deststoptag_, time_):
	assert startstoptag_ != deststoptag_
	time_ = massage_time_arg(time_)
	ri = routes.routeinfo(froute_)
	assert ri.get_stop(startstoptag_).direction == ri.get_stop(deststoptag_).direction
	startmofr = ri.get_stop(startstoptag_).mofr; destmofr = ri.get_stop(deststoptag_).mofr
	startvi1, startvi2 = _get_observed_arrival_time_caught_vehicle_passing_vis(froute_, startstoptag_, deststoptag_, time_)
	assert startvi1.vehicle_id == startvi2.vehicle_id

	time_caught = startvi1.get_pass_time_interp(startvi2, startmofr)
	time_arrived = _get_observed_arrival_time_arrival_time(startvi1, startstoptag_, deststoptag_)
	return {'time_caught': time_caught, 'time_arrived': time_arrived, 'vid': startvi1.vehicle_id}

def _get_observed_arrival_time_arrival_time(startvi1_, startstoptag_, deststoptag_):
	assert isinstance(startvi1_, vinfo.VehicleInfo) and isinstance(startstoptag_, basestring) and isinstance(deststoptag_, basestring)
	ri = routes.routeinfo(routes.CONFIGROUTE_TO_FUDGEROUTE[startvi1_.route_tag])
	startmofr = ri.get_stop(startstoptag_).mofr; destmofr = ri.get_stop(deststoptag_).mofr
	direction = mofrs_to_dir(startmofr, destmofr)
	curs = conn().cursor()
	curs.execute('select '+VI_COLS+' from ttc_vehicle_locations where vehicle_id = %s and time > %s and time < %s order by time',
			[startvi1_.vehicle_id, startvi1_.time, startvi1_.time + 1000*60*60*2])
	lastvi = startvi1_
	r = None
	for row in curs:
		curvi = vinfo.VehicleInfo(*row)
		if curvi.mofr != -1 and (curvi.mofr >= destmofr if direction==0 else curvi.mofr <= destmofr):
			if (lastvi.mofr != -1) and abs(curvi.mofr - lastvi.mofr) < 1000:
				r = lastvi.get_pass_time_interp(curvi, destmofr)
			# else - lastvi.mofr == -1 could mean that the vehicle is coming back from a detour.  the >= 1000 could mean
			# a large gap in GPS readings.  Both could mean both - such as the odd short-turn / detour that vid 4040 (route 505)
			# does around 2013-01-15 16:50.  In some cases like this, mabye we could (and should) get a useful return value for
			# this method out of this.  But this would at least require more coding here, such as searching backwards in these rows
			# for the last row with mofr != -1.
			# TODO: do filtering out of buggy GPS readings here, like graphical vehicle locations interpolation does.
			break
		lastvi = curvi
	curs.close()
	return r

# note [1] - TODO: do more here.  Handle cases of caught vehicle being stuck and rescued by another vehicle. three sub-cases:
# 1) rescue from behind (must be a bus),
# 2) rescue by vehicle in front (i.e. caught vehicle short turns, passengers transfer onto vehicle in front)
# 3) rescue from the side (i.e rescue bus shows up not from behind.  I have never seen this, in person or in the data.)
def _get_observed_arrival_time_caught_vehicle_passing_vis(froute_, startstoptag_, deststoptag_, time_):
	ri = routes.routeinfo(froute_)
	startmofr = ri.get_stop(startstoptag_).mofr; destmofr = ri.get_stop(deststoptag_).mofr
	direction = mofrs_to_dir(startmofr, destmofr)
	curs = conn().cursor()
	try:
		curs.execute('select '+VI_COLS+' from ttc_vehicle_locations where '+routes_clause(froute_)+' and time >= %s and time < %s order by time',
					 [time_ - 1000*60*5, time_ + 1000*60*60])
		candidate_vid_to_lastvi = {}
		for row in curs:
			curvi = vinfo.VehicleInfo(*row)
			if curvi.vehicle_id in candidate_vid_to_lastvi:
				lastvi = candidate_vid_to_lastvi[curvi.vehicle_id]
				if lastvi.mofr != -1 and curvi.mofr != -1 \
						and (lastvi.mofr <= startmofr <= curvi.mofr if direction == 0 else lastvi.mofr >= startmofr >= curvi.mofr)\
						and fix_dirtag_str(curvi.dir_tag, direction, curvi.route_tag) in ri.get_stop(deststoptag_).dirtags_serviced \
						and lastvi.get_pass_time_interp(curvi, startmofr) >= time_:
					#print 'fixed:', fix_dirtag_str(curvi.dir_tag, direction, curvi.route_tag)# in ri.get_stop(deststoptag_).dirtags_serviced\
					return (lastvi, curvi)
			candidate_vid_to_lastvi[curvi.vehicle_id] = curvi
		else:
			raise Exception('No passing vehicle found at start point within reasonable time frame.')
	finally:
		curs.close()

if __name__ == '__main__':

	# lansdowne: 5294     east of humber (kingsway): 3374     west of humber (mimico creek): 6830
	for deststoptag in ('3374', '6830'):
		r = get_observed_arrival_time('queen', '5294', deststoptag, '2012-01-07 12:00')
		print 'vid = %s    %s -> %s ' % (r['vid'], em_to_str(r['time_caught']), em_to_str(r['time_arrived']))
		#break



