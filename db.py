#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, pprint, json, socket, datetime, calendar
from collections import defaultdict
import vinfo, geom, traffic, routes, yards
from misc import *

ON_PRODUCTION_BOX = socket.gethostname().endswith('theorem.ca')

DATABASE_DRIVER_MODULE_NAME = 'psycopg2'
db_host = ('24.52.231.206' if ON_PRODUCTION_BOX else 'localhost')
DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='postgres' host='%s' password='doingthis'" % (db_host),)
DATABASE_CONNECT_KEYWORD_ARGS = {}

VI_COLS = ' dir_tag, heading, vehicle_id, lat, lon, predictable, route_tag, secs_since_report, time_epoch, time '

def get_db_conn():
	if ON_PRODUCTION_BOX:
		driver_module = __import__(DATABASE_DRIVER_MODULE_NAME)
	else:
		saved_syspath = sys.path
		while os.getcwd() in sys.path:
			sys.path.remove(os.getcwd())
		driver_module = __import__(DATABASE_DRIVER_MODULE_NAME)
		sys.path = saved_syspath
	return getattr(driver_module, 'connect')(*DATABASE_CONNECT_POSITIONAL_ARGS, **DATABASE_CONNECT_KEYWORD_ARGS)

g_conn = get_db_conn()

def trans(f):
	"""Decorator that calls commit() after the method finishes normally, or rollback() if an
	exception is raised.  

	That we call commit() / rollback() is of course necessary in the absence of any standard
	'auto-commit mode' that we can count on.
	""" 
	def new_f(*args, **kwds):
		self = args[0]
		try:
			returnval = f(*args, **kwds)
			g_conn.commit()
			return returnval
		except:
			g_conn.rollback()
			raise
	return new_f

@trans
def insert_vehicle_info(vi_):
	curs = g_conn.cursor()
	cols = [vi_.vehicle_id, vi_.route_tag, vi_.dir_tag, vi_.lat, vi_.lng, vi_.secs_since_report, vi_.time_epoch, \
		vi_.predictable, vi_.heading, vi_.time]
	curs.execute('INSERT INTO ttc_vehicle_locations VALUES (%s)' % ', '.join(['%s']*len(cols)), cols)
	curs.close()

def massage_dir_arg(in_):
	if in_ not in (None, 'east', 'west', 0, 1):
		raise Exception('invalid direction arg: %s' % (in_))
	if in_ == 'east':
		return 0
	elif in_ == 'west':
		return 1
	else:
		return in_

def vi_select_generator(route_, end_time_em_, start_time_em_, dir_=None, include_unpredictables_=False, vid_=None):
	curs = (g_conn.cursor('cursor_%d' % (int(time.time()*1000))) if start_time_em_ == 0 else g_conn.cursor())
	dir = massage_dir_arg(dir_)
	dir_clause = ('and dir_tag like \'%%%%\\\\_%s\\\\_%%%%\' ' % (str(dir)) if dir != None else ' ')
	sql = 'select '+VI_COLS+' from ttc_vehicle_locations where route_tag = %s '\
		+('' if include_unpredictables_ else ' and predictable = true ') \
		+' and time <= %s and time >= %s '\
		+(' and vehicle_id = %s ' if vid_ else '') \
		+ dir_clause \
		+' order by time desc'
	curs.execute(sql, [route_, end_time_em_, start_time_em_] + ([vid_] if vid_ else []))
	while True:
		row = curs.fetchone()
		if not row:
			break
		vi = vinfo.VehicleInfo(*row)
		yield vi
	curs.close()

def get_latest_vehicle_info_list(config_route_, num_minutes_, end_time_em_=now_em(), 
			dir_=None, include_unpredictables_=False, log_=False):
	r = []
	gen = vi_select_generator(config_route_, end_time_em_, end_time_em_ - num_minutes_*60*1000, dir_, include_unpredictables_)
	for vi in gen:
		r.append(vi)
	add_inside_overshots_for_traffic(r, dir_, end_time_em_, log_=log_)
	return r

# returns a list of 2-tuples - (fore VehicleInfo, stand VehicleInfo) 
# list probably has max_ elements.
def get_recent_passing_vehicles(route_, post_, max_, end_time_em_=now_em(), dir_=None, include_unpredictables_=False):
	vid_to_lastvi = {}
	n = 0
	r = []
	for curvi in vi_select_generator(route_, end_time_em_, 0, dir_, include_unpredictables_):
		if len(r) >= max_:
			break
		vid = curvi.vehicle_id
		if vid in vid_to_lastvi:
			lastvi = vid_to_lastvi[vid]
			if geom.passes(curvi.latlng, lastvi.latlng, post_):
				r.append((curvi, lastvi))
		vid_to_lastvi[vid] = curvi
	return r

def find_passing(route_, vid_, dir_, t_, post_):
	assert isinstance(route_, str) and isinstance(vid_, basestring) and isinstance(t_, long) and isinstance(post_, geom.LatLng)
	lastvi = None
	gen = vi_select_generator(route_, t_, 0, dir_=dir_, include_unpredictables_=True, vid_=vid_)
	for curvi in gen:
		if lastvi and geom.passes(curvi.latlng, lastvi.latlng, post_):
			return (curvi, lastvi)
		lastvi = curvi

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
		r = re.sub(r'time around (\d+)', repl2, r)

		def repl3(mo_):
			t = int(mo_.group(3))
			def rangestr_to_em(str_):
				if str_.endswith('h'):
					return int(str_[:-1])*60*60*1000
				else:
					return int(str_)*60*1000
			lo_range = rangestr_to_em(mo_.group(1)); hi_range = rangestr_to_em(mo_.group(2))
			return 'time > %d and time < %d' % (t - lo_range, t + hi_range)
		r = re.sub(r'time around\((\w+),(\w+)\) (\d+)', repl3, r)
		return r

def massage_whereclause_lat_args(whereclause_):
	with open('debug-vehicle-lat-grid.json') as fin:
		grid_lats = json.load(fin)
	def repl(mo_):
		return str(grid_lats[int(mo_.group(1))])
	return re.sub(r'\b(\d+)lat\b', repl, whereclause_)

def massage_whereclause_lon_args(whereclause_):
	with open('debug-vehicle-lon-grid.json') as fin:
		grid_lons = json.load(fin)
	def repl(mo_):
		return str(grid_lons[int(mo_.group(1))])
	return re.sub(r'\b(\d+)lon\b', repl, whereclause_)

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
		+ (whereclause if whereclause else 'true')+' order by route_tag, time desc limit %d' % (maxrows_)
	curs = g_conn.cursor()
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

def query2(fudgeroute_, num_minutes_, direction_, current_conditions_, time_window_end_, log_=False):
	assert type(fudgeroute_) == str and type(num_minutes_) == int and direction_ in (0,1)
	r = []
	configroutes = routes.fudgeroute_to_configroutes(fudgeroute_)
	sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
		+ ' where route_tag in ('+(','.join(['%s']*len(configroutes)))+')' \
		+' and time <= %s and time >= %s ' + ('and (dir_tag = \'\' or dir_tag like \'%%%%\\\\_%d\\\\_%%%%\') ' % (direction_)) \
		+ ' order by time desc' 
	curs = g_conn.cursor()
	starttime = time_window_end_ - num_minutes_*60*1000
	curs.execute(sqlstr, configroutes + [time_window_end_, starttime])
	for row in curs:
		vi = vinfo.VehicleInfo(*row)
		if log_: printerr('raw vinfo: '+str(vi))
		r.append(vi)
	curs.close()
	remove_unwanted_detours(r, fudgeroute_, direction_, log_)
	r += get_outside_overshots(r, starttime, False, log_=log_)
	if current_conditions_:
		add_inside_overshots_for_locations(r, direction_, time_window_end_, log_=log_)
	else:
		r = get_outside_overshots(r, time_window_end_, True, log_=log_) + r
	geom.remove_bad_gps_readings(r)
	yards.remove_vehicles_in_yards(r)
	r = interp_by_time(r, True, True, current_conditions_, direction_, time_window_end_)
	r = filter(lambda vilist: str_to_em(vilist[0]) >= starttime, r) # first elem is a date/time string. 
	return r

# The idea here is, for each vid, to get one more vi from the db, greater in time than the pre-existing
# max time vi.  This new vi may be on a different route or direction, but it will help us show that vehicle
# a little longer on the screen, which I think is desirable.
def add_inside_overshots_for_locations(r_vis_, direction_, time_window_end_, log_=False):
	new_vis = []
	for vid in set([vi.vehicle_id for vi in r_vis_]):
		time_to_beat = max(vi.time for vi in r_vis_ if vi.vehicle_id == vid)
		sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
			+ ' where vehicle_id = %s and time > %s and time <= %s order by time limit 1' 
		curs = g_conn.cursor()
		curs.execute(sqlstr, [vid, time_to_beat, time_window_end_])
		row = curs.fetchone()
		vi = None
		if row:
			vi = vinfo.VehicleInfo(*row)
			if log_: printerr('Got inside overshot: %s' % (str(vi)))
			new_vis.append(vi)
		else:
			if log_: printerr('No inside overshot found for vid %s.' % (vid))
		curs.close()
	r_vis_ += new_vis
	r_vis_.sort(key=lambda vi: vi.time, reverse=True)

# The idea here is mostly to get from the db those vis which got a blank dirtag because they are stuck in traffic
# very badly.  eg. dundas westbound 2012-09-24 13:00.  I want these stuck vehicles to contribute to the traffic report.
def add_inside_overshots_for_traffic(r_vis_, direction_, time_window_end_, log_=False):
	assert all(vi1.route_tag == vi2.route_tag for vi1, vi2 in hopscotch(r_vis_))
	new_vis = []
	for vid in set([vi.vehicle_id for vi in r_vis_]):
		old_vis = [vi for vi in r_vis_ if vi.vehicle_id == vid]
		time_to_beat = max(vi.time for vi in old_vis)
		if log_: printerr('Looking for inside overshots for %s.  Time to beat: %s / %d.' % (vid, em_to_str(time_to_beat), time_to_beat))
		sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
			+ ' where vehicle_id = %s and time > %s and time <= %s and route_tag = %s and dir_tag = \'\' order by time' 
		curs = g_conn.cursor()
		curs.execute(sqlstr, [vid, time_to_beat, time_window_end_, old_vis[0].route_tag])
		for row in curs:
			vi = vinfo.VehicleInfo(*row)
			if vi.mofr != -1:
				if log_: printerr('Got inside overshot: (time: %d) %s' % (vi.time, str(vi)))
				new_vis.append(vi)
		curs.close()
	r_vis_ += new_vis
	r_vis_.sort(key=lambda vi: vi.time, reverse=True)

# When I say detour I mean a vehicle with a blank dir_tag.  
# See http://groups.google.com/group/nextbus-api-discuss/browse_thread/thread/61fc64649ab928b5 
# "Detours and dirTag (Toronto / TTC)"
# Vehicles that are stuck badly also, at least sometimes, have a blank dir_tag for that time.  eg. vid 4104, 2012-09-24 13:00.  
def remove_unwanted_detours(r_vis_, fudgeroute_, direction_, log_=False):
	routes_general_heading = routes.get_routeinfo(fudgeroute_).general_heading(direction_)
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
		logstr = 'vehicle %s from %s to %s.' % (detour[0].vehicle_id, em_to_str(detour[-1].time), em_to_str(detour[0].time))
		if unwanted:
			if log_: printerr('Discarding apparent detour: %s' % (logstr))
		else:
			if log_: printerr('Keeping apparent detour: %s' % (logstr))

def detour_moves(detour_):
	assert all(vi.dir_tag == '' for vi in detour_)

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

# fetch one row before startime, to give us something to interpolate with. 
def get_outside_overshots(vilist_, time_window_boundary_, forward_in_time_, log_=False):
	forward_str = ('forward' if forward_in_time_ else 'backward')
	if not vilist_:
		return []
	r = []
	for vid in set([vi.vehicle_id for vi in vilist_]):
		vis_for_vid = [vi for vi in vilist_ if vi.vehicle_id == vid]
		assert all(vi1.time >= vi2.time for vi1, vi2 in hopscotch(vis_for_vid)) # i.e. is in reverse order 
		vid_extreme_time = vis_for_vid[0 if forward_in_time_ else -1].time
		if log_: printerr('Looking for %s overshot for vid %s.  Time to beat is %s.' % (forward_str, vid, em_to_str(vid_extreme_time)))
		if (vid_extreme_time >= time_window_boundary_ if forward_in_time_ else vid_extreme_time <= time_window_boundary_):
			continue
		routes = [vi.route_tag for vi in vilist_]
		sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
			+ ' where vehicle_id = %s ' + ' and route_tag in ('+(','.join(['%s']*len(routes)))+')' + ' and time < %s and time > %s '\
			+ ' order by time '+('' if forward_in_time_ else 'desc')+' limit 1' 
		curs = g_conn.cursor()
		curs.execute(sqlstr, [vid] + routes \
			+ ([time_window_boundary_+20*60*1000, vid_extreme_time] if forward_in_time_ else [vid_extreme_time, time_window_boundary_-20*60*1000]))
		row = curs.fetchone()
		if row:
			vi = vinfo.VehicleInfo(*row)
			if log_: printerr('Got %s outside overshot: %s' % (forward_str, str(vi)))
			r.append(vi)
		else:
			if log_: printerr('No %s outside overshot found for vid %s.' % (forward_str, vid))
		curs.close()
	return r

def group_by_time(vilist_):
	times = sorted(list(set([vi.time for vi in vilist_])))
	r = [[em_to_str(time)] for time in times]
	for vi in vilist_:
		time_idx = times.index(vi.time)
		r[time_idx].append(vi)
	return r

def vis_bridge_detour(lo_, hi_):
	assert (lo_.vehicle_id == hi_.vehicle_id) and (lo_.time != hi_.time)
	lo, hi = ((lo_, hi_) if lo_.time < hi_.time else (hi_, lo_))
	curs = g_conn.cursor()
	try:
		curs.execute('select '+VI_COLS+' from ttc_vehicle_locations where vehicle_id = %s and time > %s and time < %s ', \
			[lo.vehicle_id, lo.time, hi.time])
		for row in curs:
			vi = vinfo.VehicleInfo(*row)
			if vi.mofr != -1:
				return False
		return True
	finally:
		curs.close()

# Takes a flat list of VehicleInfo objects.  Returns a list of lists of Vehicleinfo objects, interpolated.
# Also, with a date/time string as element 0 in each list.
def interp_by_time(vilist_, try_for_mofr_based_loc_interp_, use_db_for_heading_inference_, current_conditions_, dir_=None, end_time_=None):
	if len(vilist_) == 0:
		return []
	starttime = round_down_by_minute(min(vi.time for vi in vilist_))
	endtime = end_time_ if end_time_!=None else max(vi.time for vi in vilist_)
	vids = set(vi.vehicle_id for vi in vilist_)
	time_to_vis = {}
	for interptime in lrange(starttime, endtime+1, 60*1000):
		interped_timeslice = []
		for vid in vids:
			lo_vi, hi_vi = get_nearest_time_vis(vilist_, vid, interptime)
			i_vi = None
			if lo_vi and hi_vi:
				if (min(interptime - lo_vi.time, hi_vi.time - interptime) > 3*60*1000) or dirs_disagree(dir_, hi_vi.dir_tag_int)\
				or (lo_vi.route_tag != hi_vi.route_tag):
					continue
				ratio = (interptime - lo_vi.time)/float(hi_vi.time - lo_vi.time)
				i_latlon, i_heading = interp_latlonnheading(lo_vi, hi_vi, ratio, try_for_mofr_based_loc_interp_)
				i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, i_heading, vid, i_latlon.lat, i_latlon.lng,
										 lo_vi.predictable and hi_vi.predictable,
										 lo_vi.route_tag, 0, interptime, interptime)
			elif lo_vi and not hi_vi:
				if current_conditions_:
					if (interptime - lo_vi.time > 3*60*1000) or dirs_disagree(dir_, lo_vi.dir_tag_int):
						continue
					i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, lo_vi.heading, vid, lo_vi.lat, lo_vi.lng,
											 lo_vi.predictable, lo_vi.route_tag, 0, interptime, interptime)

			if i_vi:
				interped_timeslice.append(i_vi)

		time_to_vis[interptime] = interped_timeslice
	infer_headings(time_to_vis, use_db_for_heading_inference_)
	return massage_to_list(time_to_vis)

# Either arg could be None (i.e. blank dir_tag).  For this we consider None to 'agree' with 0 or 1.
def dirs_disagree(dir1_, dir2_):
	return (dir1_ == 0 and dir2_ == 1) or (dir1_ == 1 and dir2_ == 0)

def interp_latlonnheading(vi1_, vi2_, ratio_, try_for_mofr_based_loc_interp_):
	r = None
	if try_for_mofr_based_loc_interp_ and vi1_.dir_tag and vi2_.dir_tag:
		if routes.CONFIGROUTE_TO_FUDGEROUTE[vi1_.route_tag] == routes.CONFIGROUTE_TO_FUDGEROUTE[vi2_.route_tag]:
			config_route = vi1_.route_tag
			vi1mofr = routes.latlon_to_mofr(config_route, vi1_.latlng)
			vi2mofr = routes.latlon_to_mofr(config_route, vi2_.latlng)
			if vi1mofr!=-1 and vi2mofr!=-1:
				interp_mofr = geom.avg(vi1mofr, vi2mofr, ratio_)
				dir_tag_int = vi2_.dir_tag_int
				if dir_tag_int == None:
					raise Exception('Could not determine dir_tag_int of %s' % (str(vi2_)))
				r = routes.mofr_to_latlonnheading(config_route, interp_mofr, dir_tag_int)
	if r==None:
		r = (geom.LatLng(*(geom.avg(vi1_.latlng.lat, vi2_.latlng.lat, ratio_), avg(vi1_.latlng.lng, vi2_.latlng.lng, ratio_))),
			 avg_headings(vi1_.heading, vi2_.heading, ratio_))
	return r

def avg_headings(heading1_, heading2_, ratio_):
	if heading1_==-4 or heading2_==-4:
		return -4
	else:
		return avg(heading1_, heading2_, ratio_)

def round_down_by_minute(t_em_):
	dt = datetime.datetime.utcfromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute)
	r = long(calendar.timegm(dt.timetuple())*1000)
	return r

def infer_headings(r_time_to_vis_, use_db_for_heading_inference_):
	assert isinstance(use_db_for_heading_inference_, bool)
	times = sorted(r_time_to_vis_.keys())
	for timei, time in enumerate(times):
		if timei==0:
			continue
		for target_vi in r_time_to_vis_[time]:
			# -4 means blank, or at least that's what nextbus seems to mean by it.
			if target_vi.heading == -4:
				infer_headings_technique1(target_vi, r_time_to_vis_, times, timei)
			if target_vi.heading == -4:
				infer_headings_technique2(target_vi, r_time_to_vis_, times, timei)
	if use_db_for_heading_inference_:
		infer_headings_technique3(r_time_to_vis_)

# As a last resort, use the database to look further back in time.
def infer_headings_technique3(r_time_to_vis_):
	vid_to_latlng_to_heading = defaultdict(lambda: {}) # Whatever we've seen so far.  Will contain -4 if our searching of the db yielded no heading.
	for tyme in sorted(r_time_to_vis_.keys()):
		for vi in (vi for vi in r_time_to_vis_[tyme] if vi.heading == -4):
			for latlng, heading in vid_to_latlng_to_heading[vi.vehicle_id].items():
				if vi.latlng.dist_m(latlng) < 5:
					vi.heading = heading
			if vi.heading == -4:
				curs = g_conn.cursor('cursor_%d' % (int(time.time()*1000)))
				curs.execute('select lat, lon from ttc_vehicle_locations where vehicle_id = %s and time > %s and time < %s order by time desc', \
						[vi.vehicle_id, vi.time - 1000*60*60*12, vi.time])
				for row in curs:
					past_latlng = geom.LatLng(row[0], row[1])
					if past_latlng.dist_m(vi.latlng) > 20:
						heading = past_latlng.heading(vi.latlng)
						vid_to_latlng_to_heading[vi.vehicle_id][vi.latlng.clone()] = heading
						vi.heading = heading
						break
				else:
					vid_to_latlng_to_heading[vi.vehicle_id][vi.latlng.clone()] = -4
				curs.close()

# Look back in time (amongst our in-memory list here) for a previous appearance of this vid which indicates
# a direction by change of mofr, then get a heading from our route info based on that direction.
def infer_headings_technique1(r_target_vi_, time_to_vis_, times_, timei_):
	if r_target_vi_.mofr != -1:
		prev_vi = None
		for timej in range(timei_-1, -1, -1):
			if prev_vi != None:
				break
			for older_vi in time_to_vis_[times_[timej]]:
				if (older_vi.vehicle_id == r_target_vi_.vehicle_id) and (older_vi.mofr != -1)\
				   and (older_vi.fudgeroute == r_target_vi_.fudgeroute)\
				and (abs(r_target_vi_.mofr - older_vi.mofr) >= 5):
					prev_vi = older_vi
					break
		if prev_vi != None:
			dir = (0 if prev_vi.mofr < r_target_vi_.mofr else 1)
			r_target_vi_.heading = routes.get_routeinfo(r_target_vi_.route_tag).mofr_to_heading(r_target_vi_.mofr, dir)

# If the above didn't work out then try again using lat/lons instead of mofrs.
def infer_headings_technique2(r_target_vi_, time_to_vis_, times_, timei_):
	prev_vi = None
	for timej in range(timei_-1, -1, -1):
		if prev_vi != None:
			break
		for older_vi in time_to_vis_[times_[timej]]:
			if (older_vi.vehicle_id == r_target_vi_.vehicle_id) and (older_vi.latlng.dist_m(r_target_vi_.latlng) >= 20):
				prev_vi = older_vi
				break
	if prev_vi != None:
		r_target_vi_.heading = prev_vi.latlng.heading(r_target_vi_.latlng)

def massage_to_list(time_to_vis_):
	time_to_vis = time_to_vis_.copy()

	# Deleting all empty timeslices at the end of the time frame.
	# doing this because the last timeslice is the current vehicle locations of course, and that is an important
	# timeslice and will be rendered differently in the GUI.
	for time in sorted(time_to_vis.keys(), reverse=True):
		if len(time_to_vis[time]) == 0:
			del time_to_vis[time]
		else:
			break

	r = []
	for time in sorted(time_to_vis.keys()):
		vis = time_to_vis[time]
		r.append([em_to_str(time)] + vis)
	for i in range(len(r)-1, -1, -1):
		if len(r[i]) == 1: # Delete all empty (empty except for the date/time string) timeslices at the end.
			del r[i] # doing this because the last timeslice is the current vehicle locations of course, and that is an important
		else: # timeslice and will be rendered differently in the GUI.
			break
	return r

def get_nearest_time_vis(vilist_, vid_, t_):
	assert type(t_) == long
	lo_vi = None; hi_vi = None
	for vi in (vi for vi in vilist_ if vi.vehicle_id == vid_):
		if vi.time < t_:
			if lo_vi==None or lo_vi.time < vi.time:
				lo_vi = vi
		elif vi.time > t_:
			if hi_vi==None or hi_vi.time > vi.time:
				hi_vi = vi
	return (lo_vi, hi_vi)

def t():
	#curs = g_conn.cursor('cursor_%d' % (int(time.time()*1000)))
	curs = g_conn.cursor()
	sql = "select * from ttc_vehicle_locations where route_tag = '505' and time <= 1330492156395 and time >= 1330491481877 and dir_tag like '%%%%\\_0\\_%%%%' and predictable = true order by time desc"
	curs.execute(sql, [])
	while True:
		row = curs.fetchone()
		if not row:
			break
		#print row[0]

if __name__ == '__main__':

	pass



