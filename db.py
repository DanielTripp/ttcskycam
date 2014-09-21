#!/usr/bin/python2.6

'''
Tables involved: 
 

create table ttc_vehicle_locations (vehicle_id varchar(100), fudgeroute varchar(20), route_tag varchar(10), dir_tag varchar(100), 
     lat double precision, lon double precision, secs_since_report integer, time_retrieved bigint, 
     predictable boolean, heading integer, time bigint, time_str varchar(100), rowid serial unique, mofr integer, widemofr integer, 
		 graph_locs varchar(1000), graph_version integer);
create index ttc_vehicle_locations_idx on ttc_vehicle_locations (fudgeroute, time_retrieved desc);
create index ttc_vehicle_locations_idx2 on ttc_vehicle_locations (vehicle_id, time_retrieved desc);
create index ttc_vehicle_locations_idx3 on ttc_vehicle_locations  (time_retrieved) ; 

create table predictions (fudgeroute VARCHAR(100), configroute VARCHAR(100), stoptag VARCHAR(100), 
     time_retrieved_str varchar(30), time_of_prediction_str varchar(30), dirtag VARCHAR(100), vehicle_id VARCHAR(100), 
     is_departure boolean, block VARCHAR(100), triptag VARCHAR(100), branch VARCHAR(100), affected_by_layover boolean, 
     is_schedule_based boolean, delayed boolean, time_retrieved bigint, time_of_prediction bigint, rowid serial unique);
create index predictions_idx on predictions (fudgeroute, stoptag, time_retrieved desc);
create index predictions_idx2 on predictions ( time_retrieved );

create table reports (app_version varchar(20), report_type varchar(20), froute varchar(100), direction integer, 
     datazoom integer, time bigint, timestr varchar(30), time_inserted_str varchar(30), report_json text);
create index reports_idx on reports (app_version, report_type, froute, direction, datazoom, time desc) ;
create index reports_idx_3 on reports ( time desc, time_inserted_str desc ) ;
# The last index above is for my personal browsing of the database, not for the code's needs. 

'''

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, pprint, json, socket, datetime, calendar, math
from collections import defaultdict, Sequence
from lru_cache import lru_cache
import vinfo, geom, grid, traffic, routes, yards, tracks, streets, snapgraph, predictions, mc, c, util
from misc import *

SECSSINCEREPORT_BUG_WORKAROUND_ENABLED = True
SECSSINCEREPORT_BUG_WORKAROUND_CONSTANT = 12

HOSTMONIKER_TO_IP = {'theorem': '72.2.4.176', 'black': '24.52.231.206', 'u': 'localhost', 'v': 'localhost'}

VI_COLS = ' dir_tag, heading, vehicle_id, lat, lon, predictable, fudgeroute, route_tag, secs_since_report, time_retrieved, time, mofr, widemofr, graph_locs, graph_version '

PREDICTION_COLS = ' fudgeroute, configroute, stoptag, time_retrieved, time_of_prediction, vehicle_id, is_departure, block, dirtag, triptag, branch, affected_by_layover, is_schedule_based, delayed'

DISABLE_GRAPH_PATHS = False

g_conn = None
g_forced_hostmoniker = None

g_debug_gridsquaresys = grid.GridSquareSystem(None, None, None, None, None)

def force_host(hostmoniker_):
	global g_forced_hostmoniker
	g_forced_hostmoniker = hostmoniker_

def connect():
	global g_conn
	DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='dt' host='%s' password='doingthis'" % (get_host()),)
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
		if socket.gethostname().startswith('ip-'):
			hostmoniker = 'v'
		elif socket.gethostname() == 'unofficialttctrafficreport.ca':
			hostmoniker = 'u'
		elif socket.gethostname().endswith('theorem.ca'):
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

def forget_connection():
	global g_conn
	g_conn = None

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
	cols = [vi_.vehicle_id, vi_.fudgeroute, vi_.route_tag, vi_.dir_tag, vi_.lat, vi_.lng, vi_.secs_since_report, vi_.time_retrieved, \
		vi_.predictable, vi_.heading, vi_.time, em_to_str(vi_.time), vi_.mofr, vi_.widemofr, vi_.get_graph_locs_json_str(), vi_.get_cur_graph_version()]
	curs.execute('INSERT INTO ttc_vehicle_locations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,default,%s,%s,%s,%s)', cols)
	curs.close()

def vi_select_generator(froute_, end_time_em_, start_time_em_, dir_=None, include_unpredictables_=False, vid_=None, \
			forward_in_time_order_=False, include_blank_fudgeroute_=True):
	assert vid_ is None or len(vid_) > 0
	assert froute_ in (routes.NON_SUBWAY_FUDGEROUTES + [''])
	curs = (conn().cursor('cursor_%d' % (int(time.time()*1000))) if start_time_em_ == 0 else conn().cursor())
	dir_clause = ('and dir_tag like \'%%%%\\\\_%s\\\\_%%%%\' ' % (str(dir_)) if dir_ != None else ' ')
	sql = 'select '+VI_COLS+' from ttc_vehicle_locations where '\
		+('fudgeroute in (\'\', %s) ' if include_blank_fudgeroute_ else 'fudgeroute = %s ')\
		+('' if include_unpredictables_ else ' and predictable = true ') \
		+' and time <= %s and time >= %s and time_retrieved <= %s and time_retrieved >= %s '\
		+(' and vehicle_id = %s ' if vid_ else ' and vehicle_id != \'\' ') \
		+ dir_clause \
		+(' order by time' if forward_in_time_order_ else ' order by time desc')
	curs.execute(sql, [froute_, end_time_em_, start_time_em_, end_time_em_, start_time_em_-1000*60] + ([vid_] if vid_ else []))
	while True:
		row = curs.fetchone()
		if not row:
			break
		vi = vinfo.VehicleInfo.from_db(*row)
		yield vi
	curs.close()

MIN_DESIRABLE_DIR_STRETCH_LEN = 6

# arg for_traffic_ True means intended for colour-coded traffic display.  False means for vehicle animations.
# return dict.  key: vid.  value: list of list of VehicleInfo.

# The approach taken with regards to dirtags is to get all dirtags from the database (0, 1, and blank), then fix those dirtags
# ourselves to represent what the vehicle is really doing.  We need to do this, rather than straightforwardly getting
# only dir=0 or dir=1 dirtags from the database, for three reasons:
# 1) Vehicles on an unscheduled detour have blank dirtags, and we want those.
# See http://groups.google.com/group/nextbus-api-discuss/browse_thread/thread/61fc64649ab928b5 "Detours and dirTag (Toronto / TTC)"
# eg. dundas eastbound 2012-06-09 12:00.
# 2) Stuck vehicles (i.e. those that are on the route but haven't moved for say 5 or 30 minutes) tend to have blank dirtags too.
# We want those too.  (eg.: vid 4104, 2012-09-24 13:00.)
# 3) Vehicles that are moving normally sometimes have dirtags that indicate the opposite direction that they are going.
# My current theory on this is that this is due to bus driver error.
# I commented on this at https://groups.google.com/forum/#!topic/nextbus-api-discuss/mJHTmi4aLBw/discussion

# Note [1]: Here we attempt to remove what we consider trivial and unimportant (or even misleading) stretches of vis.
# Currently using a rule that less than 6 vis or 300 meters is undesirable.  Doing this because of inaccurate GPS readings
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
# usually last only a couple of minutes, until the vehicle gets onto part of the detour that is closer to parallel to the original route
# (i.e. College).  Then the widemofrs will increase again, and the vehicle-location-interpolating code will having something to
# interpolate between (presumably something on Dundas right before it turned up Ossington, and something on College right after it
# turned onto College.)  These interpolated locations will not be as accurate as if we hadn't removed them in the first place,
# but I don't see this as a major problem right now.    Again this will only happen in a small number of cases where detours are happening
# on streets at odd angles.  With detours on streets at right angles, the mofr while going up the first street of the detour will
# hopefully stay pretty close to unchanged for that stretch, so hopefully the dirtag won't be fixed.  But the more I think about it,
# the less I would count on it.  I haven't tested that.  More work is warranted here. Question for dirtag-fixing:
# if widemofrs go like this: [0, 50, 100, 101, 100, 101, 100, 101, 100, 150, 200, ...] do we throw out the whole middle part
# [100, 101, 100, 101, 100]?  Wouldn't it be better if we tried to keep the two 101s in there?  That would give us more accurate
# interpolations in that area.
@lru_cache(10)
def get_vid_to_vis_singledir(fudge_route_, dir_, num_minutes_, end_time_em_, log_=False):
	assert dir_ in (0, 1)
	src = get_vid_to_vis_bothdirs(fudge_route_, num_minutes_, end_time_em_, log_=log_)
	r = {}
	for vid, vis in src.iteritems():
		r[vid] = [vi for vi in vis if vi.dir_tag_int == dir_]
	return r

@lru_cache(10)
def get_vid_to_vis_bothdirs(fudge_route_, num_minutes_, end_time_em_, log_=False):
	start_time = end_time_em_ - num_minutes_*60*1000
	vi_list = []
	vis = list(vi_select_generator(fudge_route_, end_time_em_, start_time-2*MIN_DESIRABLE_DIR_STRETCH_LEN*60*1000, None, True))
	# We want to get a lot of overshots, because we need a lot of samples in order to determine directions with any certainty.
	vis += get_outside_overshots(fudge_route_, vis, start_time, False, MIN_DESIRABLE_DIR_STRETCH_LEN-1, log_=log_)
	vi_list += vis
	# TODO: maybe get outside overshots /forward/ here too, for the benefit of historical traffic reports.
	vid_to_vis = file_under_key(vi_list, lambda vi: vi.vehicle_id)
	for vis in vid_to_vis.values():
		vis.sort(key=lambda x: x.time, reverse=True)
	for vid, vis in vid_to_vis.items():
		work_around_secssincereport_bug(vis)
		adopt_or_discard_vis_with_blank_froutes(fudge_route_, vis, log_=log_) # We have to call this before the filtering on 
				# widemofr below, because to get a widemofr we need a fudgeroute to refer to. 
		vis[:] = [vi for vi in vis if vi.widemofr != -1]
		yards.remove_vehicles_in_yards(vis)
		remove_time_duplicates(vis)
		remove_bad_gps_readings_single_vid(vis, log_=log_)
		fix_doubleback_gps_noise(vis)
		fix_dirtags(vis)
		if len(vis) == 0: del vid_to_vis[vid]
	for vid, vis in vid_to_vis.items():
		vis_grouped_by_dir = get_maximal_sublists3(vis, lambda vi: vi.dir_tag_int) # See note [1] above
		vis_desirables_only = filter(lambda e: is_vis_stretch_desirable(e, log_), vis_grouped_by_dir)
		vis[:] = sum(vis_desirables_only, [])
	for vid in vid_to_vis.keys():
		if len(vid_to_vis[vid]) == 0:
			del vid_to_vis[vid]
	return vid_to_vis

def adopt_or_discard_vis_with_blank_froutes(froute_, vis_, log_=False):
	assert len(froute_) > 0
	num_vis_with_blank_route = sum(1 for vi in vis_ if vi.fudgeroute == '')
	if num_vis_with_blank_route < len(vis_)/2:
		for vi in (vi for vi in vis_ if vi.fudgeroute == ''):
			if log_:
				printerr('Adopting blank froute: %s' % vi)
			vi.correct_fudgeroute(froute_)
	else:
		if log_:
			for vi in (vi for vi in vis_ if vi.fudgeroute == ''):
				printerr('Discarding blank froute: %s' % vi)
		vis_[:] = [vi for vi in vis_ if vi.fudgeroute != '']

def work_around_secssincereport_bug(vis_):
	assert all(isinstance(e, vinfo.VehicleInfo) for e in vis_)
	if SECSSINCEREPORT_BUG_WORKAROUND_ENABLED:
		# I doubt that there will ever be any duplicates w.r.t. time_retrieved, but just in case: 
		remove_consecutive_duplicates(vis_, key=lambda vi: vi.time_retrieved)
		vis_.sort(key=lambda vi: vi.time_retrieved)
		for vi in vis_:
			vi.secs_since_report = SECSSINCEREPORT_BUG_WORKAROUND_CONSTANT
			vi.calc_time()
		vis_.reverse()

def is_vis_stretch_desirable(vis_, log_):
	stretch_len_good = (len(vis_) >= MIN_DESIRABLE_DIR_STRETCH_LEN)
	widemofr_span_good = abs(vis_[0].widemofr - vis_[-1].widemofr) > 300
	r = (stretch_len_good or widemofr_span_good)
	if log_:
		printerr('vi stretch %sdesirable.  (stretch len good: %s, widemofr span good: %s):' \
			% (('' if r else 'un'), stretch_len_good, widemofr_span_good))
		if len(vis_) == 0:
			printerr('\tstretch has zero length.')
		else:
			for vi in vis_:
				printerr('\t%s' % vi)
	return r

def remove_time_duplicates(vis_):
	for i in range(len(vis_)-2, -1, -1): # Removing duplicates by time.  Not sure if this ever happens.
			# I think that it could happen if the code that gets overshots is sloppy. 
		if vis_[i].time == vis_[i+1]:
			del vis_[i]

def fix_dirtags(r_vis_):
	assert len(set(vi.vehicle_id for vi in r_vis_)) <= 1
	D = 50
	vis = r_vis_[::-1] # we get these in reverse chronological order, but I don't want to think of them that way in this function.
	dirs = [None]*len(vis)
	assert all(vi1.time < vi2.time for vi1, vi2 in hopscotch(vis))
	for i in range(len(vis)):
		if (i > 0) and (abs(vis[i-1].widemofr - vis[i].widemofr) >= D):
			direction = mofrs_to_dir(vis[i-1].widemofr, vis[i].widemofr)
			assert direction is not None
			fix_dirtag(vis[i], direction)
		else:
			for lookin in range(1, len(vis)):
				def look(j__):
					if (0 <= j__ < len(vis)) and (abs(vis[j__].widemofr - vis[i].widemofr) > 10):
						if j__ < i:
							direction = mofrs_to_dir(vis[j__].widemofr, vis[i].widemofr)
						else:
							direction = mofrs_to_dir(vis[i].widemofr, vis[j__].widemofr)
						assert direction is not None
						return direction
					else:
						return None
				lo_look_dir = look(i-lookin)
				hi_look_dir = look(i+lookin)
				m = {(None,0): 0, (None,1): 1, (0,None):0, (0,0): 0, (1,None): 1, (1,1): 1}
				if (lo_look_dir,hi_look_dir) in m:
					direction = m[(lo_look_dir,hi_look_dir)]
					break
			else:
				direction = 0 # i.e. if we can't figure it out because it hasn't moved in a long time, 
					# then let's call it 0 by default.  Then at least all vis will have a direction. 
			fix_dirtag(vis[i], direction)


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

def find_passing(froute_, vid_, start_time_, end_time_, post_, dir_):
	assert isinstance(froute_, str) and isinstance(vid_, basestring) and isinstance(post_, geom.LatLng)
	lastvi = None
	gen = vi_select_generator(froute_, end_time_, start_time_, dir_=dir_, include_unpredictables_=True, vid_=vid_, forward_in_time_order_=True)
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

		# The index used to be on the 'time' column.  Now it's on 'time_retrieved'.   
		# So doing selects on 'time' will be slow now. 
		# I'm used to typing 'time' into the HTML page.  So here I allow myself to keep doing that: 
		r = re.sub(r'\btime\b', 'time_retrieved', r)

		useoldtimecol = bool(re.search(r'\buseoldtimecol\b', r))
		r = re.sub(r'\buseoldtimecol\b', '', r)

		mo = re.search(r'\bdev\b', r)
		if mo:
			printerr('trying.')
			dev_time = None
			with open('dev-options-for-traffic-php.txt') as fin:
				for line in fin:
					if 'HISTORICAL_TIME_DEFAULT' in line:
						dev_time = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', line).group(0)
						break
			if dev_time is None:
				raise Exception('time not found in dev options file.')
			r = re.sub(r'\bdev\b', "'%s'" % dev_time, r)

		def repl1(mo_):
			return str(str_to_em(mo_.group(0).strip('\'"')))
		r = re.sub(r'[\'"]\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?[\'"]', repl1, r)

		r = re.sub(r'\bnow\b', str(now_em()), r)

		def repl2(mo_):
			t = int(mo_.group(1))
			range = 30*60*1000
			return 'time_retrieved > %d and time_retrieved < %d' % (t - range, t + range)
		r = re.sub(r'time_retrieved +around +(\d+)', repl2, r)

		def repl3(mo_):
			t = int(mo_.group(3))
			def rangestr_to_em(str_):
				if str_.endswith('h'):
					return int(str_[:-1])*60*60*1000
				else:
					return int(str_)*60*1000
			lo_range = rangestr_to_em(mo_.group(1)); hi_range = rangestr_to_em(mo_.group(2))
			return 'time_retrieved > %d and time_retrieved < %d' % (t - lo_range, t + hi_range)
		r = re.sub(r'time_retrieved +around\((\w+),(\w+)\) +(\d+)', repl3, r)

		if useoldtimecol:
			r = re.sub('time_retrieved', 'time', r)
		return r

def massage_whereclause_lat_args(whereclause_):
	def repl(mo_):
		n = float(mo_.group(1))
		return ' '+str(g_debug_gridsquaresys.gridlat_to_lat(n))
	return re.sub(r'\s(-?\d+(?:\.\d+)?)lat\b', repl, whereclause_)

def massage_whereclause_lng_args(whereclause_):
	r = re.sub(r'\blng\b', 'lon', whereclause_)
	def repl(mo_):
		n = float(mo_.group(1))
		return ' '+str(g_debug_gridsquaresys.gridlng_to_lng(n))
	return re.sub(r'\s(-?\d+(?:\.\d+)?)lng\b', repl, r)

def massage_whereclause_dir_args(whereclause_):
	r = whereclause_
	r = re.sub('dir *= *0', 'dir_tag like \'%%\\_0\\_%%\'', r)
	r = re.sub('dir *= *1', 'dir_tag like \'%%\\_1\\_%%\'', r)
	r = re.sub('dir +blank', 'dir_tag = \'\'', r)
	return r

def massage_whereclause_route_args(whereclause_):
	r = whereclause_
	r = re.sub(r'route += +(\w+)', 'fudgeroute = \'\\1\'', r)
	return r

def massage_whereclause_vid_args(whereclause_):
	r = whereclause_
	r = re.sub(r'vid *= *(\w+)', 'vehicle_id = \'\\1\'', r)
	return r

def massage_whereclause(whereclause_):
	r = whereclause_
	r = massage_whereclause_time_args(r)
	r = massage_whereclause_lat_args(r)
	r = massage_whereclause_lng_args(r)
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
		r.append(vinfo.VehicleInfo.from_db(*row))
	curs.close()
	work_around_secssincereport_bug(r)
	if interp_by_time_:
		r = interp_by_time(r, False, False)
	else:
		r = group_by_time(r)
	return r

def make_whereclause_safe(whereclause_):
	return re.sub('(?i)insert|delete|drop|create|truncate|alter|update|;', '', whereclause_)

# direction_ can be an integer direction (0 or 1) or a pair of LatLngs from which we will infer that integer direction.
def get_recent_vehicle_locations(fudgeroute_, num_minutes_, direction_, datazoom_, time_window_end_, log_=False):
	assert direction_ in (0, 1) or (len(direction_) == 2 and all(isinstance(e, geom.LatLng) for e in direction_))
	assert (fudgeroute_ in routes.NON_SUBWAY_FUDGEROUTES) and type(num_minutes_) == int and datazoom_ in c.VALID_DATAZOOMS 
	if direction_ in (0, 1):
		direction = direction_
	else:
		direction = routes.routeinfo(fudgeroute_).dir_from_latlngs(direction_[0], direction_[1])
	vid_to_vis = get_vid_to_vis_bothdirs(fudgeroute_, num_minutes_, time_window_end_, log_=log_)
	r = []
	for vid, vis in vid_to_vis.iteritems():
		if log_:
			printerr('For locations, pre-interp: vid %s: %d vis, from %s to %s (widemofrs %d to %d)' \
				% (vid, len(vis), em_to_str_hms(vis[-1].time), em_to_str_hms(vis[0].time), vis[-1].widemofr, vis[0].widemofr))
			for vi in vis:
				printerr('\t%s' % vi)
		r += vis
	starttime = time_window_end_ - num_minutes_*60*1000
	r = interp_by_time(r, True, True, direction, datazoom_, starttime, time_window_end_, log_=log_)
	return r

# Return only elements for which predicate is true.  (It's a one-argument predicate.  It takes one element.)
# Group them as they appeared in input list as runs of trues.
def get_maximal_sublists(list_, predicate_):
	cur_sublist = None
	r = []
	for e in list_:
		if predicate_(e):
			if cur_sublist is None:
				cur_sublist = []
				r.append(cur_sublist)
			cur_sublist.append(e)
		else:
			cur_sublist = None
	return r

# Fetch some rows before startime (or after endtime), to give us something to interpolate with.
def get_outside_overshots(froute_, vilist_, time_window_boundary_, forward_in_time_, n_=1, log_=False):
	forward_str = ('forward' if forward_in_time_ else 'backward')
	if not vilist_:
		return []
	r = []
	for vid in set([vi.vehicle_id for vi in vilist_]):
		assert vid
		vis_for_vid = [vi for vi in vilist_ if vi.vehicle_id == vid]
		assert all(vi1.time >= vi2.time for vi1, vi2 in hopscotch(vis_for_vid)) # i.e. is in reverse order 
		assert set(vi.fudgeroute for vi in vis_for_vid).issubset(set([froute_, '']))

		num_overshots_already_present = num_outside_overshots_already_present(vis_for_vid, time_window_boundary_, forward_in_time_)
		if num_overshots_already_present >= n_:
			if log_: printerr('Don\'t need to get overshots for vid %s.  (Might need to get "more" overshots though.)' % vid)
		else:
			num_more_overshots_to_get = n_ - num_overshots_already_present
			vid_extreme_time = vis_for_vid[0 if forward_in_time_ else -1].time
			if log_: printerr('Looking for %s overshots for vid %s.  Time to beat is %s.' % (forward_str, vid, em_to_str(vid_extreme_time)))
			sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations ' \
				+ ' where vehicle_id = %s and fudgeroute in (\'\', %s) and time_retrieved < %s and time_retrieved > %s '\
				+ ' order by time '+('' if forward_in_time_ else 'desc')+' limit %s'
			curs = conn().cursor()
			query_times = [time_window_boundary_+20*60*1000, vid_extreme_time] if forward_in_time_ else [vid_extreme_time, time_window_boundary_-20*60*1000]
			args = [vid, froute_] + query_times + [num_more_overshots_to_get]
			curs.execute(sqlstr, args)
			for row in curs:
				vi = vinfo.VehicleInfo.from_db(*row)
				if log_: printerr('Got %s outside overshot: %s' % (forward_str, str(vi)))
				r.append(vi)
			curs.close()
		vis_for_vid = [vi for vi in r if vi.vehicle_id == vid]
		r += get_outside_overshots_more(froute_, vis_for_vid, time_window_boundary_, forward_in_time_, log_=log_)

	return r

def num_outside_overshots_already_present(single_vid_vis_, time_window_boundary_, forward_in_time_):
	assert len(set(vi.vehicle_id for vi in single_vid_vis_)) <= 1
	def is_overshot(vi__):
		return (vi__.time > time_window_boundary_ if forward_in_time_ else vi__.time < time_window_boundary_)
	overshots_already_present = [vi for vi in single_vid_vis_ if is_overshot(vi)]
	return len(overshots_already_present) 
	

# This function is for when we want to look back far enough to see a change in mofr, so that we can determine the
# direction of a long-stalled vehicle.
def get_outside_overshots_more(froute_, vis_so_far_, time_window_boundary_, forward_in_time_, log_=False):
	assert len(set(vi.vehicle_id for vi in vis_so_far_)) <= 1
	assert set(vi.fudgeroute for vi in vis_so_far_).issubset(set([froute_, '']))
	r = []
	more_vis = []
	if not forward_in_time_ and len(vis_so_far_) > 0:
		vid = vis_so_far_[0].vehicle_id
		assert vid
		r_mofr_min = min(vi.mofr for vi in vis_so_far_); r_mofr_max = max(vi.mofr for vi in vis_so_far_)
		if (r_mofr_max != -1) and (r_mofr_max - r_mofr_min < 50): # 50 metres = small, typical GPS errors.
			curs = conn().cursor()
			sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations '\
					 + ' where vehicle_id = %s and fudgeroute in (\'\', %s) and time_retrieved <= %s and time_retrieved >= %s '\
					 + ' order by time '+('' if forward_in_time_ else 'desc')+' limit %s'
			curs.execute(sqlstr, [vid, froute_, vis_so_far_[-1].time, time_window_boundary_-6*60*60*1000, 999999])
			for row in curs:
				vi = vinfo.VehicleInfo.from_db(*row)
				more_vis.append(vi)
				if (vis_so_far_ + more_vis)[-1].time - (vis_so_far_ + more_vis)[-2].time > 10*60*1000:
					del r[:] # Large time gap in these samples?  Not worth it.  This code is intended for typical stalled vehicles
					break # and every one I've looked at reports in several times per minute, save as every other vehicle.
				mofr_change_including_more_r = max(r_mofr_max, vi.mofr) - min(r_mofr_min, vi.mofr)
				if mofr_change_including_more_r > 50:
					if log_:
						printerr('Looked back more for vid %s.  Got %d more vis:' % (vid, len(more_vis)))
						for vi in more_vis:
							printerr('\t%s' % vi)
					break
			curs.close()
	return more_vis


def group_by_time(vilist_):
	times = sorted(list(set([vi.time for vi in vilist_])))
	r = [[em_to_str(time)] for time in times]
	for vi in vilist_:
		time_idx = times.index(vi.time)
		r[time_idx].append(vi)
	return r

# Takes a flat list of VehicleInfo objects.  Returns a list of lists of Vehicleinfo objects, interpolated.
# Also, with a date/time string as element 0 in each list.
#
# note [1]: This is for the scenario of eg. this function is meant to get dir=1, and we're looking at a vehicle for which raw vis exist
# at mofr=0 @ 12:00, mofr=1000 @ 12:15, and mofr=1100 @ 12:16.  The vehicle was probably going in dir=0 between
# 12:00 and 12:15, but that doesn't matter.  What matters is that if we're not careful, we will interpolate inappropriately
# between 12:00 and 12:15 - though probably just 3 minutes after 12:00 and 3 minutes before 12:15, as 3 minutes is our current
# hi/lo time gap max for interpolation - you can also see this below.   But does it make sense for us to return something like mofr=67 for 12:01,
# mofr=134 for 12:02, etc. (making these interpolated returned vis effectively dir=0)?  No it does not.  It's not what the user asked
# for (they asked for dir=1 vehicles) and it looks awful too - looking at vehicles going both directions on a route is visual chaos and
# makes it a lot harder to make sense of the dir=1 vehicles that they do want to see.
def interp_by_time(vilist_, be_clever_, current_conditions_, dir_=None, datazoom_=None, start_time_=None, end_time_=None, log_=False):
	assert isinstance(vilist_, Sequence) and all(isinstance(e, vinfo.VehicleInfo) for e in vilist_)
	if len(vilist_) == 0:
		return []
	starttime = (round_up_by_minute(start_time_) if start_time_ is not None else round_down_by_minute(min(vi.time for vi in vilist_)))
	endtime = (round_up_by_minute(end_time_) if end_time_ is not None else max(vi.time for vi in vilist_))
	vids = set(vi.vehicle_id for vi in vilist_)
	interptimes = list(lrange(starttime, endtime+1, 60*1000))
	time_to_out_vis = dict((interptime, []) for interptime in interptimes)
	for vid in vids:
		if log_: printerr('Interpolating locations for vid %s...' % vid)
		vis = [vi for vi in vilist_ if vi.vehicle_id == vid][::-1]
		assert is_sorted(vis, key=lambda vi: vi.time)
		vi_to_grade, vi_to_path = get_grade_stretch_info(vis, be_clever_, log_)
		for interptime in interptimes:
			lolo_vi, lo_vi, hi_vi, lolo_idx, lo_idx, hi_idx = get_nearest_time_vis(vis, interptime)
			i_vi = None
			if lo_vi and hi_vi:
				if (min(interptime - lo_vi.time, hi_vi.time - interptime) > 3*60*1000) or dirs_disagree(dir_, hi_vi.dir_tag_int)\
						or dirs_disagree(lo_vi.dir_tag_int, dir_) or (lo_vi.fudgeroute != hi_vi.fudgeroute):
					continue
				time_ratio = (interptime - lo_vi.time)/float(hi_vi.time - lo_vi.time)
				lo_grade = vi_to_grade[lo_vi]; hi_grade = vi_to_grade[hi_vi]
				if (lo_grade, hi_grade) in (('g', 'g'), ('g', 'r'), ('r', 'g')):
					i_latlon, i_heading, i_mofr = interp_with_path_latlonnheadingnmofr(
							lo_vi, hi_vi, time_ratio, lo_idx, vis, vi_to_grade, vi_to_path, log_)
				else:
					i_latlon, i_heading, i_mofr = interp_latlonnheadingnmofr(lo_vi, hi_vi, time_ratio, datazoom_, be_clever_)
				i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, i_heading, vid, i_latlon.lat, i_latlon.lng,
										 lo_vi.predictable and hi_vi.predictable,
										 lo_vi.fudgeroute, lo_vi.route_tag, 0, interptime, interptime, i_mofr, None, 
										 None, None)
			elif lo_vi and not hi_vi:
				if current_conditions_:
					if (interptime - lo_vi.time > 3*60*1000) or dirs_disagree(dir_, lo_vi.dir_tag_int):
						continue
					if vi_to_grade[lo_vi] == 'g':
						latlng, heading = vi_to_path[lo_vi].get_piece(-1).mapl_to_latlngnheading('max')
					else:
						latlng, heading = get_latlonnheadingnmofr_from_lo_sample(lolo_vi, lo_vi, datazoom_, be_clever_)[:2]
					i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, heading, vid, latlng.lat, latlng.lng,
							lo_vi.predictable, lo_vi.fudgeroute, lo_vi.route_tag, 0, interptime, interptime, lo_vi.mofr, lo_vi.widemofr, 
							None, None)

			if i_vi:
				time_to_out_vis[interptime].append(i_vi)
				if log_:
					printerr('vid %s, interp result for %s' % (vid, em_to_str_hms(interptime)))
					printerr('\tlo: %s' % lo_vi)
					if hi_vi:
						printerr('\thi: %s' % hi_vi)
					printerr('\t==> %s' % i_vi)
		if log_: printerr('Finished interpolating locations for vid %s.' % vid)

	return massage_to_list(time_to_out_vis, starttime, endtime, log_=log_)

def interp_with_path_latlonnheadingnmofr(lo_vi_, hi_vi_, time_ratio_, lo_idx_, vis_, vi_to_grade_, vi_to_path_, log_):
	assert lo_vi_.vehicle_id == hi_vi_.vehicle_id
	lo_grade = vi_to_grade_[lo_vi_]
	path = vi_to_path_[lo_vi_ if lo_grade == 'g' else hi_vi_]
	pieceidx = get_piece_idx(vis_, lo_idx_, vi_to_grade_)
	i_latlng, i_heading = get_latlngnheading_from_path(path, pieceidx, time_ratio_)
	i_mofr = None
	if log_:
		printerr('vid %s path interp between [%s,%s]:' % (lo_vi_.vehicle_id, lo_vi_.latlng, hi_vi_.latlng))
		printerr('\ttime_ratio=%.2f, pieceidx=%d' % (time_ratio_, pieceidx))
		printerr('\tpiece=%s' % path.latlngs(pieceidx))
		printerr('\tresult=%s' % i_latlng)
	return (i_latlng, i_heading, i_mofr)

def get_latlngnheading_from_path(path_, pieceidx_, time_ratio_):
	piece = path_.get_piece(pieceidx_)
	mapl = piece.length_m() * time_ratio_
	return piece.mapl_to_latlngnheading(mapl)

def get_piece_idx(vis_, lo_idx_, vi_to_grade_):
	r = -1
	for i in range(lo_idx_, -1, -1):
		r += 1
		grade = vi_to_grade_[vis_[i]]
		if grade != 'g':
			if grade == 'o':
				r -= 1
			break
	return r

def get_grade_stretch_info(vis_, be_clever_, log_):
	return get_grade_stretch_info_impl(tuple(vis_), be_clever_, log_)

@lru_cache(100) # It's important that this cache at least the maximum number of vehicle that will ever appear in the locations 
# report for one route / one direction.  If this cache size is even 1 less than that, then every time around the loop over 
# the datazooms in reports.py / make_all_reports_and_insert_into_db_once(), these will be forgotten, and performance will 
# suffer badly. 
def get_grade_stretch_info_impl(vis_, be_clever_, log_):
	assert len(set(vi.vehicle_id for vi in vis_)) == 1
	assert is_sorted(vis_, key=lambda vi: vi.time)

	if not be_clever_:
		return (defaultdict(lambda: 'o'), {})

	vi_to_offroute = dict((vi, vi.mofr == -1) for vi in vis_)

	stretches = get_maximal_sublists3(vis_, lambda vi: vi_to_offroute[vi])
	for stretchi in range(len(stretches)):
		stretch = stretches[stretchi]
		if not vi_to_offroute[stretch[0]]:
			if stretchi > 0:
				ref_mofr = stretch[0].mofr
				vi_to_offroute[stretch[0]] = True
				for vi in stretch[1:]:
					if abs(vi.mofr - ref_mofr) < c.GRAPH_SNAP_RADIUS:
						vi_to_offroute[vi] = True
					else:
						break
			if stretchi < len(stretches) - 1:
				ref_mofr = stretch[-1].mofr
				vi_to_offroute[stretch[-1]] = True
				for vi in stretch[-2::-1]:
					if abs(vi.mofr - ref_mofr) < c.GRAPH_SNAP_RADIUS:
						vi_to_offroute[vi] = True
					else:
						break
			
	stretches = get_maximal_sublists3(vis_, lambda vi: vi_to_offroute[vi])
	for stretchi in range(len(stretches)):
		stretch = stretches[stretchi]
		if not vi_to_offroute[stretch[0]]:
			mofrs = [vi.mofr for vi in stretch]
			mofr_span = max(mofrs) - min(mofrs)
			if mofr_span < c.GRAPH_SNAP_RADIUS:
				for vi in stretch:
					vi_to_offroute[vi] = True

	vi_to_grade = dict((vi, 'o' if vi_to_offroute[vi] else 'r') for vi in vis_)

	if DISABLE_GRAPH_PATHS:
		return (vi_to_grade, {})

	vi_to_locs = {}
	sg = (tracks.get_snapgraph() if vis_[0].is_a_streetcar() else streets.get_snapgraph())
	for vi in vis_:
		if vi_to_grade[vi] == 'o':
			locs = vi.graph_locs
			if len(locs) > 0:
				vi_to_grade[vi] = 'g'

	def get_grade(stretch__):
		return vi_to_grade[stretch__[0]]

	# We can't use 'g' stretches of length 1 which are surrounded by 'o' stretches or nothing.  
	# So here we remove them and make them 'o'. 
	# Because what would we do with them?  There is no graph path between an 'o' point and a 'g' point - 
	# that is, eg. the last 'o' point in the stretch before this length=1 'g' stretch.  
	# This is unlike a length=1 'g' stretch which has an 'r' stretch before or after.  Because 
	# of our assumption that the (streetcar or street) graph is a superset of the route in question, 
	# we can always get a graph path between an 'r' point and a 'g' point. 
	# So here we filter out those useless stretches, both because they are useless, and because if we 
	# don't, the find_multipath() code below will fail because it doesn't like being passed 1 latlngs 
	# list of length=1. 
	stretches = get_maximal_sublists3(vis_, lambda vi: vi_to_grade[vi])
	for i, stretch, isfirst, islast in enumerate2(stretches):
		if get_grade(stretch) == 'g' and len(stretch) == 1 and \
					(isfirst or get_grade(stretches[i-1])) and (islast or get_grade(stretches[i+1])):
			vi_to_grade[stretch[0]] = 'o'

	vi_to_path = {}
	stretches = get_maximal_sublists3(vis_, lambda vi: vi_to_grade[vi])
	for stretchi, stretch in enumerate(stretches):
		if get_grade(stretch) == 'g':
			latlngs = [vi.latlng for vi in stretch]
			locses = [vi.graph_locs for vi in stretch]
			if stretchi > 0 and get_grade(stretches[stretchi-1]) == 'r':
				vi = stretches[stretchi-1][-1]
				latlngs.insert(0, vi.latlng)
				locses.insert(0, vi.graph_locs)
			if stretchi < len(stretches)-1 and get_grade(stretches[stretchi+1]) == 'r':
				vi = stretches[stretchi+1][0]
				latlngs.append(vi.latlng)
				locses.append(vi.graph_locs)
			if log_:
				printerr('latlngs / locses for stretch %d:' % stretchi)
				for latlng, locs in zip(latlngs, locses): 
					printerr(latlng, locs)
			dist, path = sg.find_multipath(latlngs, locses, c.GRAPH_SNAP_RADIUS, log_)
			assert dist is not None and path is not None
			if log_:
				printerr('Path for stretch %d:' % stretchi)
				for piecei, piecesteps in enumerate(path.piecestepses):
					printerr('piece %d: %s' % (piecei, piecesteps))
			for vi in stretch:
				vi_to_path[vi] = path

	if log_:
		printerr('Grades for vid %s:' % vis_[0].vehicle_id)
		for vi in vis_:
			printerr('\t%s / %s: %s' % (vi.timestr, vi.latlng, vi_to_grade[vi]))

	return (vi_to_grade, vi_to_path)

# Either arg could be None (i.e. blank dir_tag).  For this we consider None to 'agree' with 0 or 1.
def dirs_disagree(dir1_, dir2_):
	return (dir1_ == 0 and dir2_ == 1) or (dir1_ == 1 and dir2_ == 0)

# To do it this way may seem odd but we get the latest of these things by interpolating between the second-last (lolo) and 
# the last (lo) with a ratio of 1.0, because that extrapolation code (interp_latlonnheadingnmofr()) has some nice code that does 
# snap-by-mofr or snap-to-tracks, which I don't feel like copying and pasting and stripping down for the ratio = 1.0 case. 

# lolo_vi_ may seem unnecessary here because of the ratio of 1.0, but it is used to find the heading 
# if tracks are being used - will be a choice between X and X + 180.  If we have only one sample (lo_vi_) then common sense 
# says that there's no way that we can figure out that heading.  
def get_latlonnheadingnmofr_from_lo_sample(lolo_vi_, lo_vi_, datazoom_, be_clever_):
	assert lo_vi_ is not None
	if lolo_vi_ is not None:
		return interp_latlonnheadingnmofr(lolo_vi_, lo_vi_, 1.0, datazoom_, be_clever_)
	else:
		# We would do something like this:
		#return interp_latlonnheadingnmofr(lo_vi_, lo_vi_, 1.0, datazoom_, be_clever_)
		# ... but I don't think we'll ever encounter this scenario, because we only want to return vehicle locations
		# if we have about 5 or 6 raw samples for that vid, right?
		# If we hit this case, that means that we have one sample.
		raise Exception()

		
# Interpolates via mofrs if possible, or off-route simple interpolation. 
# 
# be_clever_ - means use routes if mofrs are valid.
#
# note 23906728947234: slight lie about making mofr -1 here.  I used to set it to None, so that later whenever someone 
# used vi.mofr on this object (which would probably be during serialization to JSON), 
# vinfo.VehicleInfo would calculate it from the latlng.  It could be a valid mofr.  Something interpolated half-way between 
# eg. a position 500 meters to one side of a route and 500 meters to the other could be a valid mofr.  But it doesn't mean 
# much and more importantly - nobody is looking at this interpolated mofr - neither human nor code.  
# So even though None would be more honest, I'm setting it to -1 for a slight performance increase (about 5% of a full 
# reports generation run, as it stands now).
def interp_latlonnheadingnmofr(vi1_, vi2_, ratio_, datazoom_, be_clever_):
	assert isinstance(vi1_, vinfo.VehicleInfo) and isinstance(vi2_, vinfo.VehicleInfo) and (vi1_.vehicle_id == vi2_.vehicle_id)
	assert vi1_.time < vi2_.time and (datazoom_ is None or datazoom_ in c.VALID_DATAZOOMS)
	r = None
	can_be_clever = vi1_.dir_tag and vi2_.dir_tag and (vi1_.fudgeroute == vi2_.fudgeroute)
	being_clever = be_clever_ and can_be_clever
	if being_clever:
		assert (vi1_.dir_tag_int == vi2_.dir_tag_int)
		froute = vi1_.fudgeroute
		if vi1_.mofr!=-1 and vi2_.mofr!=-1:
			interp_mofr = geom.avg(vi1_.mofr, vi2_.mofr, ratio_)
			dir_tag_int = vi2_.dir_tag_int
			if dir_tag_int == None:
				raise Exception('Could not determine dir_tag_int of %s' % (str(vi2_)))
			r = routes.mofr_to_latlonnheading(froute, interp_mofr, dir_tag_int, datazoom_) + (interp_mofr,)

	if r is None:
		vi1_latlng = vi1_.latlng; vi2_latlng = vi2_.latlng
		if being_clever:
			if vi1_.mofr!=-1:
				vi1_latlng = routes.mofr_to_latlon(vi1_.fudgeroute, vi1_.mofr, vi1_.dir_tag_int, datazoom_)
			if vi2_.mofr!=-1:
				vi2_latlng = routes.mofr_to_latlon(vi2_.fudgeroute, vi2_.mofr, vi2_.dir_tag_int, datazoom_)
		r = (vi1_latlng.avg(vi2_latlng, ratio_), vi1_latlng.heading(vi2_latlng), -1) # see note 23906728947234 
	return r

def massage_to_list(time_to_vis_, start_time_, end_time_, log_=False):
	time_to_vis = time_to_vis_.copy() # No big need for this copy, I think.  
			# Just implementating behaviour of returning something and not modifying the argument, I think. 

	for time in time_to_vis.keys():
		if time < start_time_ or time > end_time_:
			del time_to_vis[time]

	vid_to_stretches = defaultdict(lambda: [])
	vid_to_cur_stretch = defaultdict(lambda: [])
	for time in sorted(time_to_vis.keys()):
		vis_for_time = time_to_vis[time]
		for vi in vis_for_time:
			vid_to_cur_stretch[vi.vehicle_id].append(vi)
		vids_for_time = [vi.vehicle_id for vi in vis_for_time]
		for vid in [vid for vid in vid_to_cur_stretch.keys() if vid not in vids_for_time]:
			vid_to_stretches[vid].append(vid_to_cur_stretch[vid])
			del vid_to_cur_stretch[vid]
	for vid, stretch in vid_to_cur_stretch.iteritems():
		vid_to_stretches[vid].append(stretch)

	for vid, stretches in vid_to_stretches.iteritems():
		new_stretches = []
		for stretch in stretches:
			if len(stretch) >= 2:
				new_stretches.append(stretch)
			else:
				if log_:
					printerr('Throwing out stretch:')
					for vi in stretch:
						printerr('\t%s' % vi)
		stretches[:] = new_stretches

	new_time_to_vis = {}
	# Making sure that all times that were in the time_to_vis_ arg are in the 
	# dict that we return, even if we have no vis left for some of those times.   
	# This is especially important because currently traffic.php, when showing 
	# multiple routes, shows locations only for the intersection of the times that 
	# it has for those routes.  So if we return from here only a couple of 
	# minutes for one of the routes (because for example that route is going out 
	# of service for the day) then that will result in most of the times for all 
	# of the other routes not being shown.  That would be unfortunate. 
	for tyme in time_to_vis.keys():
		new_time_to_vis[tyme] = []
	for vid, stretches in vid_to_stretches.iteritems():
		for stretch in stretches:
			for vi in stretch:
				new_time_to_vis[vi.time].append(vi)

	r = []
	for time in sorted(new_time_to_vis.keys()):
		vis = new_time_to_vis[time]
		vis.sort(key=lambda vi: vi.vehicle_id) # For debugging.  To ensure a predictable output order. 
		r.append([em_to_str(time)] + vis)
	return r

# return (lolo, lo, hi).  lo and hi bound t_ by time.  lolo is one lower than lo.
def get_nearest_time_vis(vis_, t_):
	assert (type(t_) == long) and (len(set(vi.vehicle_id for vi in vis_)) == 1)
	if len(vis_) == 0:
		return (None, None, None, -1, -1, -1)
	assert is_sorted(vis_, key=lambda vi: vi.time)
	r_lo = None; r_hi = None
	for hi_idx in range(len(vis_)-1, 0, -1):
		lo_idx = hi_idx-1
		hi = vis_[hi_idx]; lo = vis_[lo_idx]
		if hi.time > t_ >= lo.time:
			if lo_idx > 0:
				return (vis_[lo_idx-1], lo, hi, lo_idx-1, lo_idx, hi_idx)
			else:
				return (None, lo, hi, -1, lo_idx, hi_idx)
	if t_ >= vis_[-1].time:
		if len(vis_) >= 2:
			lolo_idx = len(vis_)-2; lo_idx = len(vis_)-1
			return (vis_[lolo_idx], vis_[lo_idx], None, lolo_idx, lo_idx, -1)
		else:
			lo_idx = len(vis_)-1
			return (None, vis_[lo_idx], None, -1, lo_idx, -1)
	elif t_ < vis_[-1].time:
		 hi_idx = len(vis_)-1
		 return (None, None, vis_[hi_idx], -1, -1, hi_idx)
	else:
		return (None, None, None, -1, -1, -1)

# returns a list of 2-tuples - (fore VehicleInfo, stand VehicleInfo)
# list probably has max_ elements.
def get_recent_passing_vehicles(froute_, post_, max_, end_time_em_=now_em(), dir_=None, include_unpredictables_=False):
	vid_to_lastvi = {}
	n = 0
	r = []
	for curvi in vi_select_generator(froute_, end_time_em_, 0, dir_, include_unpredictables_):
		if len(r) >= max_:
			break
		vid = curvi.vehicle_id
		if vid in vid_to_lastvi:
			lastvi = vid_to_lastvi[vid]
			if geom.passes(curvi.latlng, lastvi.latlng, post_):
				r.append((curvi, lastvi))
		vid_to_lastvi[vid] = curvi
	return r

def purge(num_days_):
	assert isinstance(num_days_, int)
	assert num_days_ >= 0
	if not socket.gethostname() == 'unofficialttctrafficreport.ca':
		raise Exception('Not running on prod machine?')

	force_host('u')

	purge_delete(num_days_)
	purge_vacuum()

@trans
def purge_delete(num_days_):
	curs = conn().cursor()
	# Delete all rows older than X days: 
	num_millis = 1000*60*60*24*num_days_
	curs.execute('delete from ttc_vehicle_locations where time_retrieved < round(extract(epoch from clock_timestamp())*1000) - %d;' % num_millis)
	curs.execute('delete from predictions where time_retrieved < round(extract(epoch from clock_timestamp())*1000) - %d;' % num_millis)
	curs.execute('delete from reports where time < round(extract(epoch from clock_timestamp())*1000) - %d;' % num_millis)
	curs.close()

def purge_vacuum():
	old_isolation_level = conn().isolation_level
	conn().set_isolation_level(0)
	curs = conn().cursor()
	curs.execute('vacuum analyze;')
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
		curvi = vinfo.VehicleInfo.from_db(*row)
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
		curs.execute('select '+VI_COLS+' from ttc_vehicle_locations where fudgeroute = %s and time >= %s and time < %s order by time',
					 [froute_, time_ - 1000*60*5, time_ + 1000*60*60])
		candidate_vid_to_lastvi = {}
		for row in curs:
			curvi = vinfo.VehicleInfo.from_db(*row)
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

# returns report json, always non-None.  raises ReportNotFoundException if report does not exist in db. 
@lru_cache(10)
@mc.decorate
def get_report(report_type_, froute_, dir_, datazoom_, time_):
	assert isinstance(time_, long)
	curs = conn().cursor()
	try:
		curs.execute('select report_json from reports where app_version = %s and report_type = %s and froute = %s and direction = %s '\
				+' and datazoom = %s and time = %s', [c.VERSION, report_type_, froute_, dir_, datazoom_, time_])
		for row in curs:
			return row[0]
		else:
			raise ReportNotFoundException()
	finally:
		curs.close()

class ReportNotFoundException(Exception):
	pass


def get_latest_report_time(froute_, dir_):
	r = mc.get_from_memcache('db.get_latest_report_time', [froute_, dir_], {})
	if r is not None:
		return r
	else:
		r = get_latest_report_time_impl(froute_, dir_)
		set_latest_report_time_in_memcache(froute_, dir_, r)
		return r

def get_latest_report_time_impl(froute_, dir_):
	curs = conn().cursor('cursor_%d' % (int(time.time()*1000)))
	try:
		# We assume here (and elsewhere) and all of the reports for a certain 
		# froute and direction (that is, all report types and datazooms thereof) 
		# were inserted at the same time i.e. atomically in the database. 
		curs.execute('select time from reports where app_version = %s and froute = %s and direction = %s '\
				+' and time > %s order by time desc limit 1', [c.VERSION, froute_, dir_, now_em() - 1000*60*c.REPORTS_MAX_AGE_MINS])
		for row in curs:
			reports_time = row[0]
			return reports_time
		raise Exception('Either the most current report in database is too old, or no reports for this app version exist.')
	finally:
		curs.close()

# As in - set a value in memcache for the function db.get_latest_report_time().
def set_latest_report_time_in_memcache(froute_, dir_, time_):
	assert froute_ in routes.NON_SUBWAY_FUDGEROUTES and dir_ in (0, 1)
	assert isinstance(time_, long)
	mc.set('db.get_latest_report_time', [froute_, dir_], {}, time_)

def set_report_in_memcache(report_type_, froute_, dir_, datazoom_, time_, data_):
	mc.set('db.get_report', [report_type_, froute_, dir_, datazoom_, time_], {}, data_)

def insert_reports(froute_, dir_, time_, reporttype_to_datazoom_to_reportdataobj_):
	assert froute_ in routes.NON_SUBWAY_FUDGEROUTES and dir_ in (0, 1)

	reporttype_to_datazoom_to_reportjson = defaultdict(lambda: {})
	for reporttype, datazoom_to_reportdataobj in reporttype_to_datazoom_to_reportdataobj_.iteritems():
		assert reporttype in ('traffic', 'locations') 
		assert set(datazoom_to_reportdataobj.keys()) == set(c.VALID_DATAZOOMS)
		for datazoom, reportdataobj in datazoom_to_reportdataobj.iteritems():
			reporttype_to_datazoom_to_reportjson[reporttype][datazoom] = util.to_json_str(reportdataobj)
	
	insert_reports_into_db(froute_, dir_, time_, reporttype_to_datazoom_to_reportjson)
	insert_reports_into_memcache(froute_, dir_, time_, reporttype_to_datazoom_to_reportjson)

# Here we want to insert all reports for a certain froute and direction (that 
# is, all datazooms, both report types) into the database at the same time 
# because there is some client side code that assumes this.  That client side 
# code assumes this because it's easier to write that way.  Also it could be 
# confusing if when the user changes zoom they might be forced back in time.  
# That is the main issue - inserting all datazooms at the same time.  We insert 
# both report types at the same time too, but that is less important.
@trans
def insert_reports_into_db(froute_, dir_, time_, reporttype_to_datazoom_to_reportjson_):
	time_inserted_str = now_str()
	for reporttype, datazoom_to_reportjson in reporttype_to_datazoom_to_reportjson_.iteritems():
		for datazoom, reportjson in datazoom_to_reportjson.iteritems():
			curs = conn().cursor()
			cols = [c.VERSION, reporttype, froute_, dir_, datazoom, time_, em_to_str(time_), time_inserted_str, reportjson]
			curs.execute('insert into reports values (%s,%s,%s,%s,%s,%s,%s,%s,%s)', cols)
			curs.close()

def insert_reports_into_memcache(froute_, dir_, time_, reporttype_to_datazoom_to_reportjson_):
	for reporttype, datazoom_to_reportjson in reporttype_to_datazoom_to_reportjson_.iteritems():
		for datazoom, reportjson in datazoom_to_reportjson.iteritems():
			set_report_in_memcache(reporttype, froute_, dir_, datazoom, time_, reportjson)
	set_latest_report_time_in_memcache(froute_, dir_, time_)

@trans
def insert_demo_locations(froute_, demo_report_timestr_, vid_, locations_):
	if len(locations_) != 31: raise Exception('Got %d locations.  Want 31.' % (len(locations_)))
	if not demo_report_timestr_.startswith('2020-'): raise Exception()
	demo_report_time = str_to_em(demo_report_timestr_)
	for locationi, location in enumerate(locations_):
		t = demo_report_time - 1000*60*30 + 1000*60*locationi
		if location is None:
			continue
		if isinstance(location, int):
			latlng = routes.mofr_to_latlon(froute_, location, 0)
		else:
			latlng = geom.LatLng(location)
		croute = demo_froute_to_croute(froute_)
		vi = vinfo.makevi1(vehicle_id=vid_, latlng=latlng, route_tag=croute, time=t, time_retrieved=t)
		insert_vehicle_info(vi)

def demo_froute_to_croute(froute_):
	return routes.FUDGEROUTE_TO_CONFIGROUTES[froute_][0]

@trans
def delete_debug_reports_locations(report_time_em_):
	if report_time_em_ < now_em() + 1000*60*60*24*365*10:
		raise Exception()
	delete_min_time = report_time_em_ - 1000*60*60*24
	delete_max_time = report_time_em_ + 1000*60*60*24
	curs = conn().cursor()
	curs.execute('delete from ttc_vehicle_locations where time_retrieved between %s and %s', \
			[delete_min_time, delete_max_time])
	curs.close()

@trans
def delete_debug_reports_reports(report_time_em_):
	if report_time_em_ < now_em() + 1000*60*60*24*365*10:
		raise Exception()
	delete_min_time = report_time_em_ - 1000*60*60*24
	delete_max_time = report_time_em_ + 1000*60*60*24
	curs = conn().cursor()
	curs.execute('delete from reports where time between %s and %s and app_version = %s', \
			[delete_min_time, delete_max_time, c.VERSION])
	curs.close()

@trans
def delete_demo_locations(froute_, demo_report_timestr_):
	if not demo_report_timestr_.startswith('2020-'): raise Exception()
	demo_time = str_to_em(demo_report_timestr_)
	delete_min_time = demo_time - 1000*60*60
	delete_max_time = demo_time + 1000*60*60
	curs = conn().cursor()
	croute = demo_froute_to_croute(froute_)
	curs.execute('delete from ttc_vehicle_locations where route_tag = %s and time_retrieved between %s and %s', \
			[croute, delete_min_time, delete_max_time])
	curs.close()

def close_connection():
	global g_conn
	if g_conn is not None:
		try:
			g_conn.close()
		except:
			pass
		g_conn = None

# This is for removing buggy GPS readings (example: vehicle 4116 2012-06-15 13:30 to 14:00.)
def remove_bad_gps_readings(vis_):
	if not vis_:
		return
	assert isinstance(vis_[0], vinfo.VehicleInfo)
	r = []
	for vid in set(vi.vehicle_id for vi in vis_):
		vis_single_vid = [vi for vi in vis_ if vi.vehicle_id == vid]
		vis_single_vid.sort(key=lambda vi: vi.time, reverse=True)
		remove_bad_gps_readings_single_vid(vis_single_vid)
		r += vis_single_vid
	r.sort(key=lambda vi: vi.time, reverse=True)
	vis_[:] = r

# Note [1]: This is to account for the small gps inaccuracies that nearly all readings seem to have.
# One can see this by drawing many vehicle locations on a google map with satellite view on.  Otherwise
# reasonable vehicles routinely appear in impossible places like on top of buildings.
# I don't know if there is any pattern to these inaccuracies.  I will assume that they are random and can
# change completely from one reading to the next.
# The large GPS errors (which are the entire reason for the 'remove bad gps' functions) have no limit to their
# magnitude that I can see.  The small GPS errors do, and it seems to be about 50 metres.  (That's 50 metres from one
# extreme to the other - i.e. 25 metres on either side of the road.  Note that we don't use mofrs here, only
# distance between latlngs.)
# (newer comment - 50 metres may not be enough.  eg. 2013-01-16 00:02:00.000 route: 505, vehicle: 4040, dir: '505_0_505' , ( 43.65366, -79.44915 ) , mofr: -1, heading: 140 
# These small GPS errors, combined with scenarios where a given reading in our database has a logged time very soon
# after the previous one (eg. 1 second or even less - as can happen in certain NextBus fluke scenarios I think, as well as
# the couple of times when I've mistakenly been polling for vehicle locations with two processes at the same time)
# can result in what looks like a very high speed.  This code treats a very high speed as a new 'vigroup'.  That is
# undesirable and in a bad case previously caused this code to create some erroneous vigroups, and then at the end when it
# picks the one containing the most vis, to throw out a lot of good vis.
# eg. vid 1660 between 2013-01-07 12:39:59 and 12:41:09, without the 'small GPS error if clause' below, would cause this code
# to create 2 new vigroups where it should have created no new ones.
def is_plausible(dist_m_, speed_kmph_):
	if dist_m_ < 50: # see note [1]
		return True
	elif dist_m_ < 1500:
		# The highest plausible speed that I've seen reported is 61.08 km/h.  This was on Queensway south of High Park, 
		# covering 1018 meters of track, over 60 seconds.   (vid 4119 around 2014-03-15 02:53.)
		return speed_kmph_ < 65 
	elif dist_m_ < 5000:
		return speed_kmph_ < 40
	else:
		return speed_kmph_ < 30

def remove_bad_gps_readings_single_vid(vis_, log_=False):
	assert is_sorted(vis_, reverse=True, key=lambda vi: vi.time)
	assert len(set(vi.vehicle_id for vi in vis_)) <= 1
	if not vis_:
		return []
	vis = vis_[::-1]
	remove_consecutive_duplicates(vis, key=lambda vi: vi.time)
	vigroups = [[vis[0]]]
	for cur_vi in vis[1:]:
		def get_dist_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = cur_vi.latlng.dist_m(groups_last_vi.latlng)
			return groups_last_vi_to_cur_vi_metres

		def get_mps_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = cur_vi.latlng.dist_m(groups_last_vi.latlng)
			groups_last_vi_to_cur_vi_secs = abs((cur_vi.time - groups_last_vi.time)/1000.0)
			return groups_last_vi_to_cur_vi_metres/groups_last_vi_to_cur_vi_secs

		def is_plausible_vigroup(vigroup_):
			return is_plausible(get_dist_from_vigroup(vigroup_), mps_to_kmph(get_mps_from_vigroup(vigroup_)))

		closest_vigroup = min(vigroups, key=get_dist_from_vigroup)
		if is_plausible_vigroup(closest_vigroup):
			closest_vigroup.append(cur_vi)
		else:
			vigroups.append([cur_vi])
	r_vis = max(vigroups, key=len)
	if log_:
		vid = vis_[0].vehicle_id
		if len(vigroups) == 1:
			printerr('Bad GPS filtering - vid %s - there was only one group.' % vid)
		else:
			printerr('Bad GPS filtering - vid %s - chose group %d.' % (vid, vigroups.index(r_vis)))
			printerr('---')
			for vi in vis:
				groupidx = firstidx(vigroups, lambda vigroup: vi in vigroup)
				printerr('%d - %s' % (groupidx, vi))
			printerr('---')
			for groupidx, vigroup in enumerate(vigroups):
				for vi in vigroup:
					printerr('%d - %s' % (groupidx, vi))
			printerr('---')
		printerr('Bad GPS filtering - vid %s - groups as JSON:' % vid)
		printerr([[vi.latlng.ls() for vi in vigroup] for vigroup in vigroups])
	vis_[:] = r_vis[::-1]

def fix_doubleback_gps_noise(vis_):
	assert is_sorted(vis_, key=lambda vi: vi.time, reverse=True)
	vis_[:] = vis_[::-1] # As is often the case, we get these in reverse time order but I don't want to write 
			# this code that way.  So we'll reverse them here then back again at the end of the function.
	if len(vis_) == 0:
		return
	assert len(set(vi.vehicle_id for vi in vis_)) == 1
	D = 20
	i = 2
	while i < len(vis_):
		preref_pos = vis_[i-2].latlng; ref_pos = vis_[i-1].latlng; i_pos = vis_[i].latlng
		if ref_pos.dist_m(i_pos) > D:
			i += 1
		else:
			ref_heading = preref_pos.heading(ref_pos)
			i_heading = ref_pos.heading(i_pos)
			if geom.diff_headings(ref_heading, i_heading) < 90:
				i += 1
			else:
				vis_[i].set_latlng(ref_pos)
				for j in range(i+1, len(vis_)):
					i = j
					j_pos = vis_[j].latlng
					if ref_pos.dist_m(j_pos) > D:
						break
					else:
						vis_[j].set_latlng(ref_pos)
				else:
					i = len(vis_)
	vis_[:] = vis_[::-1]

if __name__ == '__main__':

	pass

