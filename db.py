#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, pprint, json
from collections import defaultdict
import vinfo, geom, traffic, routes, yards
from misc import *

DATABASE_DRIVER_MODULE_NAME = 'psycopg2'
DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='postgres' host='24.52.231.206' password='doingthis'",)
DATABASE_CONNECT_KEYWORD_ARGS = {}

VI_COLS = ' dir_tag, heading, vehicle_id, lat, lon, predictable, route_tag, secs_since_report, time_epoch, time '

def get_db_conn():
	driver_module = __import__(DATABASE_DRIVER_MODULE_NAME)
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
	cols = [vi_.vehicle_id, vi_.route_tag, vi_.dir_tag, vi_.xy.latlon()[0], vi_.xy.latlon()[1], vi_.secs_since_report, vi_.time_epoch, \
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
			if geom.passes(curvi.xy, lastvi.xy, post_):
				r.append((curvi, lastvi))
		vid_to_lastvi[vid] = curvi
	return r

def find_passing(route_, vid_, dir_, t_, post_):
	assert type(route_) == str and type(vid_) == str and type(t_) == long and isinstance(post_, geom.XY)
	lastvi = None
	gen = vi_select_generator(route_, t_, 0, dir_=dir_, include_unpredictables_=True, vid_=vid_)
	for curvi in gen:
		if lastvi and geom.passes(curvi.xy, lastvi.xy, post_):
			return (curvi, lastvi)
		lastvi = curvi

def get_latest_vehicle_info_dict(route_, num_minutes_, end_time_em_=now_em(), dir_=None, include_unpredictables_=False):
	r = defaultdict(lambda: {}) # {vehicle_id: {time_em: (lat, lon)}}
	for vi in get_latest_vehicle_info_list(route_, num_minutes_, end_time_em_, dir_):
		r[vi.vehicle_id][vi.time] = vi.xy.latlon()
	return r

def massage_whereclause_time_args(whereclause_):
	if not whereclause_:
		return whereclause_
	else:
		r = whereclause_
		def repl1(mo_):
			return str(str_to_em(mo_.group(0).strip('\'"')))
		r = re.sub(r'[\'"]\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?[\'"]', repl1, r)
		def repl2(mo_):
			t = int(mo_.group(1))
			range = 15*60*1000
			return 'time > %d and time < %d' % (t - range, t + range)
		r = re.sub(r'time around (\d+)', repl2, r)

		r = re.sub(r'time around now', 'time around(45,10) %d' % (now_em()), r)

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
		r = geom.interp_by_time(r, False, False)
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
	r = geom.interp_by_time(r, True, current_conditions_, direction_, time_window_end_)
	r = filter(lambda vilist: str_to_em(vilist[0]) >= starttime, r) # first elem is a date/time string. 
	return r

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
		if (len(detour) >= 2) and (detour[-1].xy.dist_m(detour[0].xy) > 15): 
			assert all(e1.time > e2.time for e1, e2 in hopscotch(detour))
			detours_heading = geom.heading_from_latlons(geom.LatLon(*(detour[-1].latlon)), geom.LatLon(*(detour[0].latlon)))
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
	for vehicle_id, time_to_latlon in get_latest_vehicle_info_dict('501', 15).iteritems():
		print vehicle_id
		for time, latlon in time_to_latlon.iteritems():
			print time, latlon


