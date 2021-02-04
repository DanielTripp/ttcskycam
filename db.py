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

'''
Tables involved: 
 

create table ttc_vehicle_locations (vehicle_id varchar(100), fudgeroute varchar(20), route_tag varchar(10), dir_tag varchar(100), 
     lat double precision, lon double precision, secs_since_report integer, time_retrieved bigint, 
     predictable boolean, heading integer, time bigint, time_str varchar(100), rowid serial unique, mofr integer, widemofr integer, 
		 graph_locs varchar(1000), graph_version integer, froute_version integer not null);
create index ttc_vehicle_locations_idx on ttc_vehicle_locations (fudgeroute, time_retrieved desc);
create index ttc_vehicle_locations_idx2 on ttc_vehicle_locations (vehicle_id, time_retrieved desc);
create index ttc_vehicle_locations_idx3 on ttc_vehicle_locations  (time_retrieved) ; 

create table predictions (fudgeroute VARCHAR(100), configroute VARCHAR(100), stoptag VARCHAR(100), 
     time_retrieved_str varchar(30), time_of_prediction_str varchar(30), dirtag VARCHAR(100), vehicle_id VARCHAR(100), 
     is_departure boolean, block VARCHAR(100), triptag VARCHAR(100), branch VARCHAR(100), affected_by_layover boolean, 
     is_schedule_based boolean, delayed boolean, time_retrieved bigint, time_of_prediction bigint, rowid serial unique);
create index predictions_idx on predictions (fudgeroute, stoptag, time_retrieved desc);
create index predictions_idx2 on predictions ( time_retrieved );

create table reports (app_version varchar(100), report_type varchar(20), froute varchar(100), direction integer, 
     datazoom integer, time bigint, timestr varchar(30), time_inserted_str varchar(30), report_json text);
create index reports_idx on reports (app_version, report_type, froute, direction, datazoom, time desc) ;
create index reports_idx_3 on reports ( time desc, time_inserted_str desc ) ;
# The last index above is for my personal browsing of the database, not for the code's needs. 

'''

import psycopg2
import sys, subprocess, re, time, xml.dom, xml.dom.minidom, pprint, json, socket, datetime, calendar, math, copy, threading
from collections import defaultdict, Sequence
from lru_cache import lru_cache
import vinfo, geom, grid, traffic, routes, yards, tracks, streets, snapgraph, predictions, mc, c, util
from misc import *

SECSSINCEREPORT_BUG_WORKAROUND_ENABLED = True
SECSSINCEREPORT_BUG_WORKAROUND_CONSTANT = 12

VI_COLS = ' dir_tag, heading, vehicle_id, lat, lon, predictable, fudgeroute, route_tag, secs_since_report, time_retrieved, time, mofr, widemofr, graph_locs, graph_version, froute_version '

PREDICTION_COLS = ' fudgeroute, configroute, stoptag, time_retrieved, time_of_prediction, vehicle_id, is_departure, block, dirtag, triptag, branch, affected_by_layover, is_schedule_based, delayed'

DISABLE_GRAPH_PATHS = False

INTERP_USE_PATCHCACHE = c.USE_PATCHCACHES

PASSWORD = file_to_string(os.path.expanduser('~/.ttcskycam/DB_PASSWORD')).strip()

g_conn = None
g_lock = threading.RLock()

g_debug_gridsquaresys = grid.GridSquareSystem(None, None, None, None, None)

def connect():
	global g_conn
	DATABASE_CONNECT_POSITIONAL_ARGS = ("dbname='postgres' user='dt' host='localhost' password='%s'" % PASSWORD,)
	DATABASE_CONNECT_KEYWORD_ARGS = {}
	g_conn = psycopg2.connect(*DATABASE_CONNECT_POSITIONAL_ARGS, **DATABASE_CONNECT_KEYWORD_ARGS)

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

def lock(f):
	'''
	'''
	def new_f(*args, **kwds):
		with g_lock:
			return f(*args, **kwds)
	return new_f

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

@lock
@trans
def insert_vehicle_info(vi_):
	curs = conn().cursor()
	cols = [vi_.vehicle_id, vi_.fudgeroute, vi_.route_tag, vi_.dir_tag, vi_.lat, vi_.lng, vi_.secs_since_report, vi_.time_retrieved, \
		vi_.predictable, vi_.heading, vi_.time, em_to_str(vi_.time), vi_.mofr, vi_.widemofr, vi_.get_graph_locs_json_str(), vi_.get_cur_graph_version(), vi_.get_cur_froute_version()]
	curs.execute('INSERT INTO ttc_vehicle_locations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,default,%s,%s,%s,%s,%s)', cols)
	curs.close()

@lock
def vi_select_generator(froute_, end_time_em_, start_time_em_, dir_=None, include_unpredictables_=False, vid_=None, \
			forward_in_time_order_=False, include_blank_fudgeroute_=True):
	assert vid_ is None or len(vid_) > 0
	assert froute_ in (routes.NON_SUBWAY_FUDGEROUTES + [''])
	curs = (conn().cursor('cursor_%d' % (int(time.time()*1000))) if start_time_em_ == 0 else conn().cursor())
	dir_clause = ('and dir_tag like \'%%%%\\\\_%s\\\\_%%%%\' ' % (str(dir_)) if dir_ != None else ' ')
	sql = 'select '+VI_COLS+' from ttc_vehicle_locations where '\
		+('fudgeroute in (\'\', %s) ' if include_blank_fudgeroute_ else 'fudgeroute = %s ')\
		+('' if include_unpredictables_ else ' and predictable = true ') \
		+' and time_retrieved <= %s and time_retrieved > %s '\
		+(' and vehicle_id = %s ' if vid_ else ' and vehicle_id != \'\' ') \
		+ dir_clause \
		+(' order by time' if forward_in_time_order_ else ' order by time desc')
	curs.execute(sql, [froute_, end_time_em_, start_time_em_] + ([vid_] if vid_ else []))
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
# Currently using a rule that less than 6 vis or 300 meters is undesirable.  We try to fix GPS noise small and large 
# so a stretch is unlikely to be considered undesirable because of that.  But I think that showing a vehicle for a 
# small stretch would not be useful to the user and might confuse them too. 
#
# When this function is used for vehicle locations (as opposed to color-coded traffic) and it involves vehicles taking detours,
# a less than desirable situation can occur sometimes.  If a vehicle takes a detour and the angle of the streets in that area
# makes the widemofrs of the vehicle appear to be reversing (for example an eastbound Dundas vehicle detouring up Ossington
# then continuing east on College) then the dirtag will be 'fixed' via widemofr and will appear to reverse for part of the detour.
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
#
# Note 23946278623746 
# Here we're making an effort, in a place where the vehicle is turning around, 
# to get one more vi than we would if we just looked at the dirtag.  Doing this 
# because the dirtags aren't perfect and are often a little slow to change - 
# being 1 for the first vi after a turn-around when it should be 0, and vice 
# versa.  eg. when the vi mofrs are like this: 75, 0, 25, 500, ....  The "25" 
# vi will probably be set to 1 during our "fix dirtags" stage (which has 
# already happened), because the difference between 0 and 25 is less than the 
# threshold required for that code to consider it a change in direction.  In an 
# area where the vehicles are slow for the first couple of minutes in the new 
# direction, this won't be much of a problem.  But if they're fast enough (for 
# example, going from mofr 25 to 500 in a minute) then there will be a visually 
# large stretch where that vehicle doesn't show up.  I noticed this on the 
# wellesley on ossington.  
@lru_cache(10)
def get_vid_to_vis_singledir(fudge_route_, dir_, num_minutes_, end_time_em_, log_=False):
	assert dir_ in (0, 1)
	src = get_vid_to_vis_bothdirs(fudge_route_, num_minutes_, end_time_em_, log_=log_)
	r = {}
	for vid, vis in src.iteritems():
		out_vis = []
		for i, vi in enumerate(vis):
			if vi.dir_tag_int == dir_:
				out_vis.append(vi)
			elif i < len(vis)-1:
				# See note 23946278623746 
				next_vi = vis[i+1]
				if next_vi.dir_tag_int == dir_ and \
						(next_vi.widemofr > vi.widemofr if dir_ == 0 else next_vi.widemofr < vi.widemofr):
					out_vis.append(vi)
		r[vid] = out_vis
	return r

# 'stretch' here means a list of consecutive (time-wise) vis, for a single vehicle, 
# that have the same direction. 
def remove_undesirable_dirstretches(vis_, pvis_, log_=False):
	assert vinfo.same_vid(vis_)
	dirstretches = get_maximal_sublists3(vis_, lambda vi: vi.dir_tag_int) # See note [1] somewhere 
	if pvis_ is not None:
		pvis_.dirstretches = copy.deepcopy(dirstretches)
	desirability_by_dirstretchidx = [is_dirstretch_desirable(stretch, log_) for stretch in dirstretches]
	if pvis_ is not None:
		pvis_.desirability_by_dirstretchidx = copy.deepcopy(desirability_by_dirstretchidx)
	desirable_dirstretches = [stretch for i, stretch in enumerate(dirstretches) if desirability_by_dirstretchidx[i]]
	vis_[:] = sum(desirable_dirstretches, [])

def get_history_overshoot_start_time(end_time_, num_minutes_):
	start_time = end_time_ - num_minutes_*60*1000
	return start_time - (end_time_ - start_time)/2

@lru_cache(10)
def get_vid_to_vis_bothdirs(froute_, num_minutes_, end_time_, log_=False):
	time_window = TimeWindow(get_history_overshoot_start_time(end_time_, num_minutes_), end_time_)
	vid_to_vis = get_vid_to_vis_bothdirs_raw(froute_, time_window, log_=log_)
	for vid in sorted(vid_to_vis.keys()): # sorting by vid just to ease debugging. 
		vis = vid_to_vis[vid]
		adopt_or_discard_vis_with_blank_froutes(froute_, vis, log_=log_) # We have to call this before the filtering on 
				# widemofr below, because to get a widemofr we need a fudgeroute to refer to. 
		vis[:] = [vi for vi in vis if vi.widemofr != -1]
		yards.remove_vehicles_in_yards(vis)
		remove_time_duplicates(vis)
		if len(vis) == 0:
			del vid_to_vis[vid]
			continue
		plausgroups = get_plausgroups(vis, froute_, time_window)
		vis[:] = get_best_plausgroup(plausgroups, log_=log_)
		fix_doubleback_gps_noise(vis, log_=log_)
		fix_dirtags(vis, froute_, time_window, log_=log_)
		remove_undesirable_dirstretches(vis, None, log_=log_)
		if len(vis) == 0: del vid_to_vis[vid]
	return vid_to_vis

g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw = {}

def get_vid_to_vis_bothdirs_raw(froute_, time_window_, log_=False):
	assert froute_ and isinstance(time_window_, TimeWindow)
	r = None
	if c.USE_PATCHCACHES and froute_ in g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw:
		old_time_window, old_vid_to_vis_bothdirs_raw = g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw[froute_]
		if old_time_window.span == time_window_.span and 0 <= time_window_.end - old_time_window.end < 1000*60*20:
			r = copy_vid_to_vis_bothdirs_raw_for_patchcache(old_vid_to_vis_bothdirs_raw)
			for vid, vis in r.items():
				time_window_.trim_vilist(vis)
				if not vis:
					del r[vid]
			new_all_vids_vis = list(vi_select_generator(froute_, time_window_.end, old_time_window.end, None, True))
			for vid, new_vis in file_under_key(new_all_vids_vis, lambda vi: vi.vehicle_id).iteritems():
				new_vis.sort(key=lambda x: x.time)
				work_around_secssincereport_bug(new_vis)
				if vid in r:
					r[vid] += new_vis
					r[vid].sort(key=lambda vi: vi.time) # In case NextBus gives us some out-of-order vis.  I haven't seen this, 
							# except for the 'secssincereport' bug, which we work around elsewhere, so this isn't here for that. 
							# It's here in case I disable that work-around one day and then some out-of-order vis shows up anyway. 
				else:
					r[vid] = new_vis
	if r is None:
		all_vids_vis = list(vi_select_generator(froute_, time_window_.end, time_window_.start, None, True))
		# We want to get a lot of overshots, because we need a lot of samples in order to determine directions with any certainty.
		r = file_under_key(all_vids_vis, lambda vi: vi.vehicle_id)
		for vid, vis in r.iteritems():
			vis.sort(key=lambda x: x.time)
			work_around_secssincereport_bug(vis)
	prune_patchcache_get_vid_to_vis_bothdirs_raw(time_window_)
	g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw[froute_] = \
			(time_window_, copy_vid_to_vis_bothdirs_raw_for_patchcache(r))
	if log_: log_get_vid_to_vis_bothdirs_raw(froute_, time_window_, r)
	return r 

def log_get_vid_to_vis_bothdirs_raw(froute_, time_window_, r_):
	printerr('Raw vis for froute=%s, %s' % (froute_, time_window_))
	for vid, vis in iteritemssorted(r_):
		printerr('raw vis for vid %s:' % vid)
		for vi in vis:
			printerr(vi)

def prune_patchcache_get_vid_to_vis_bothdirs_raw(time_window_):
	global g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw
	for vid, (time_window, data) in g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw.items():
		if abs(time_window_.end - time_window.end) > 1000*60*30:
			del g_patchcache_froute_to_time_window_n_vid_to_vis_bothdirs_raw[vid]

def copy_vid_to_vis_bothdirs_raw_for_patchcache(orig_vid_to_vis_bothdirs_raw_):
	r = {}
	for vid, vis in orig_vid_to_vis_bothdirs_raw_.iteritems():
		r[vid] = vis[:]
	return r

def adopt_or_discard_vis_with_blank_froutes(froute_, vis_, log_=False):
	assert len(froute_) > 0 and vinfo.same_vid(vis_)
	assert is_sorted(vis_, key=lambda vi: vi.time)
	idxes_to_discard = []
	for i, vi in enumerate(vis_):
		if vi.fudgeroute == '':
			for j in range(i-1, -1, -1):
				prev_vi = vis_[j]
				if prev_vi.fudgeroute != '':
					if vi.time - prev_vi.time < 1000*60*2:
						if log_:
							printerr('Adopting vi w/ blank froute: %s' % vi)
						vis_[i] = vis_[i].copy() # Making a copy b/c vi might be cached. 
						vis_[i].correct_fudgeroute(froute_)
					else:
						if log_:
							printerr('Discarding vi w/ blank froute: %s' % vi)
						idxes_to_discard.append(i)
					break
	for idx in idxes_to_discard[::-1]:
		vis_.pop(idx)

# Can handle multiple vids. 
def work_around_secssincereport_bug(vis_):
	assert all(isinstance(e, vinfo.VehicleInfo) for e in vis_)
	if SECSSINCEREPORT_BUG_WORKAROUND_ENABLED:
		for vi in vis_:
			vi.secs_since_report = SECSSINCEREPORT_BUG_WORKAROUND_CONSTANT
			vi.calc_time()
		vis_.sort(key=lambda vi: vi.time)

def is_dirstretch_desirable(vis_, log_):
	assert vinfo.same_vid(vis_) and vinfo.same_dir(vis_)
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
	for i in range(len(vis_)-1, 0, -1): # Removing duplicates by time.  Not sure if this ever happens.
			# I think that it could happen if the code that gets overshots is sloppy. 
		prev_vi = vis_[i-1]
		if vis_[i].time == prev_vi.time:
			del vis_[i]

def fix_dirtags(vis_, froute_, time_window_, log_=False):
	assert vis_ and vinfo.same_vid(vis_) and is_sorted(vis_, key=lambda vi: vi.time)
	D = 50
	if log_:
		printerr('Fixing dirtags for vid %s' % vis_[0].vehicle_id)
		printerr('dir=? %s' % vis_[0])
	for curi in xrange(1, len(vis_)):
		for olderi in xrange(curi-1, -1, -1):
			widemofr_diff = vis_[curi].widemofr - vis_[olderi].widemofr
			if widemofr_diff > D:
				fix_dirtag(vis_, curi, 0)
				if log_: printerr('dir=0 %s' % vis_[curi])
				break
			elif widemofr_diff < -D:
				fix_dirtag(vis_, curi, 1)
				if log_: printerr('dir=1 %s' % vis_[curi])
				break
		else:
			if log_: printerr('dir=? %s' % vis_[curi])

def fix_dirtag(vis_, i_, dir_):
	vi = vis_[i_]
	assert isinstance(vi, vinfo.VehicleInfo) and dir_ in (0, 1)
	if dir_ == vi.dir_tag_int:
		pass
	else:
		# Making a copy to modify b/c the original might be cached. 
		new_vi = vi.copy()
		vis_[i_] = new_vi
		if vi.dir_tag_int == 1 and dir_ == 0:
			new_vi.dir_tag = new_vi.dir_tag.replace('_1_', '_0_')
			new_vi.is_dir_tag_corrected = True
		elif vi.dir_tag_int == 0 and dir_ == 1:
			new_vi.dir_tag = new_vi.dir_tag.replace('_0_', '_1_')
			new_vi.is_dir_tag_corrected = True
		elif vi.dir_tag_int is None:
			assert vi.dir_tag == ''
			new_vi.dir_tag = '%s_%d_%s' % (new_vi.route_tag, dir_, new_vi.route_tag)
			new_vi.is_dir_tag_corrected = True
		else:
			raise Exception('Don\'t know how to fix dir_tag on %s' % str(vi))

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
@lock
def query1(whereclause_, maxrows_, interp_):
	assert type(whereclause_) == str and type(maxrows_) == int and type(interp_) == bool
	whereclause = massage_whereclause(whereclause_)
	sqlstr = 'select '+VI_COLS+' from ttc_vehicle_locations where ' \
		+ (whereclause if whereclause else 'true')+' order by time desc limit %d' % (maxrows_)
	curs = conn().cursor()
	curs.execute(sqlstr)
	all_vis = []
	for row in curs:
		all_vis.append(vinfo.VehicleInfo.from_db(*row))
	curs.close()
	work_around_secssincereport_bug(all_vis)
	if interp_:
		vid_to_raw_vis = file_under_key(all_vis, lambda vi: vi.vehicle_id)
		vid_to_interptime_to_vi = {}
		for vid, raw_vis in vid_to_raw_vis.iteritems():
			vid_to_interptime_to_vi[vid] = interp(sorted(raw_vis, key=lambda vi: vi.time), False, False)
		times = set(sum((interptime_to_vi.keys() for interptime_to_vi in vid_to_interptime_to_vi.itervalues()), []))
		starttime = min(times); endtime = max(times)
		all_vis = get_locations_clientside_list(vid_to_interptime_to_vi, TimeWindow(starttime, endtime))
	else:
		all_vis = group_by_time(all_vis)
	return all_vis

def make_whereclause_safe(whereclause_):
	return re.sub('(?i)insert|delete|drop|create|truncate|alter|update|;', '', whereclause_)

# arg  direction_ can be an integer direction (0 or 1) or a pair of LatLngs from which we will infer that integer direction.
# returns a list of 'timeslices'.  A timeslice is a list of vis with a timestamp string prepended.
def get_recent_vehicle_locations(fudgeroute_, num_minutes_, direction_, datazoom_, time_window_end_, log_=False):
	assert (fudgeroute_ in routes.NON_SUBWAY_FUDGEROUTES) and type(num_minutes_) == int and datazoom_ in c.VALID_DATAZOOMS 
	direction = massage_direction(direction_, fudgeroute_)
	vid_to_vis = get_vid_to_vis_bothdirs(fudgeroute_, num_minutes_, time_window_end_, log_=log_)
	time_window_start = time_window_end_ - num_minutes_*60*1000
	time_window = TimeWindow(time_window_start, time_window_end_)
	vid_to_interptime_to_vi = {}
	for vid, vis in iteritemssorted(vid_to_vis):
		if log_:
			printerr('For locations, pre-interpolation: vid %s: %d vis, from %s to %s (widemofrs %d to %d)' \
				% (vid, len(vis), em_to_str_hms(vis[0].time), em_to_str_hms(vis[-1].time), vis[0].widemofr, vis[-1].widemofr))
			for vi in vis:
				printerr('\t%s' % vi)
		vid_to_interptime_to_vi[vid] = \
				interp(vis, True, True, direction, datazoom_, time_window, log_=log_)
	return get_locations_clientside_list(vid_to_interptime_to_vi, time_window, log_=log_)

def massage_direction(direction_, fudgeroute_):
	assert direction_ in (0, 1) or (len(direction_) == 2 and all(isinstance(e, geom.LatLng) for e in direction_))
	if direction_ in (0, 1):
		return direction_
	else:
		return routes.routeinfo(fudgeroute_).dir_from_latlngs(direction_[0], direction_[1])

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
@lock
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
@lock
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

g_interp_patchcache_vid_to_infos = defaultdict(list)
g_interp_patchcache_prune_counter = 0

# note [1]: This is for the scenario of eg. this function is meant to get 
# dir=1, and we're looking at a vehicle for which raw vis exist
# at mofr=0 @ 12:00, mofr=1000 @ 12:15, and mofr=1100 @ 12:16.  The vehicle was 
# probably going in dir=0 between
# 12:00 and 12:15, but that doesn't matter.  What matters is that if we're not 
# careful, we will interpolate inappropriately
# between 12:00 and 12:15 - though probably just 3 minutes after 12:00 and 3 
# minutes before 12:15, as 3 minutes is our current
# hi/lo time gap max for interpolation - you can also see this below.   But 
# does it make sense for us to return something like mofr=67 for 12:01,
# mofr=134 for 12:02, etc. (making these interpolated returned vis effectively 
# dir=0)?  No it does not.  It's not what the user asked
# for (they asked for dir=1 vehicles) and it looks awful too - looking at 
# vehicles going both directions on a route is visual chaos and
# makes it a lot harder to make sense of the dir=1 vehicles that they do want 
# to see.
def interp(vis_, be_clever_, current_conditions_, dir_=None, datazoom_=None, time_window_=None, log_=False):
	assert isinstance(vis_, Sequence) and vinfo.same_vid(vis_)
	if len(vis_) == 0:
		return []
	vid = vis_[0].vehicle_id
	old_info, num_old_vis_lost = get_interp_info_from_patchcache(vis_, be_clever_, current_conditions_, dir_, datazoom_, time_window_)
	starttime = (round_up_by_minute(time_window_.start) if time_window_ else round_down_by_minute(min(vi.time for vi in vis_)))
	endtime = (round_up_by_minute(time_window_.end) if time_window_ else max(vi.time for vi in vis_))
	interptimes = list(lrange(starttime, endtime+1, 60*1000))
	grades, paths = get_grade_stretch_info(vis_, time_window_, be_clever_, log_)
	if old_info is None:
		interptime_to_vi = dict((interptime, None) for interptime in interptimes)
		important_vi_idxes = None
		if log_: printerr('Not using patch-cache for interp of vid %s' % vid)
	else:
		interptime_to_vi = old_info.r_interptime_to_vi.copy()
		for interptime in interptime_to_vi.keys():
			if interptime not in interptimes:
				del interptime_to_vi[interptime]

		important_vi_idxes = set()
		for new_idx in xrange(len(vis_)):
			old_idx = new_idx + num_old_vis_lost
			if new_idx < 2 or old_idx >= len(old_info.vis)-2 or old_info.grades[old_idx] != grades[new_idx] \
					or old_info.paths[old_idx] != paths[new_idx]:
				important_vi_idxes.add(new_idx)

		if log_:
			printerr('Using patch-cache for interp of vid %s' % vid)
			printerr('old vis:')
			for i, vi in enumerate(old_info.vis):
				printerr('[%2d] %s' % (i, vi))
			printerr('new vis:')
			for i, vi in enumerate(vis_):
				printerr('[%2d] %s' % (i, vi))
			printerr('Important indexes in new vis: %s' % sorted(important_vi_idxes))

	if log_: printerr('Interpolating locations for vid %s...' % vid)
	assert is_sorted(vis_, key=lambda vi: vi.time)
	interp_impl(interptime_to_vi, interptimes, important_vi_idxes, vis_, grades, paths, 
			be_clever_, current_conditions_, dir_, datazoom_, log_)
	if log_: printerr('Finished interpolating locations for vid %s.' % vid)
	prune_interp_patchcache(time_window_)
	if interp_should_use_patchcache(be_clever_, current_conditions_, dir_, datazoom_, time_window_):
		g_interp_patchcache_vid_to_infos[vid].append(
				(InterpInfo(vis_, time_window_, dir_, datazoom_, grades, paths, interptime_to_vi)))
	return interptime_to_vi

def prune_interp_patchcache(time_window_):
	global g_interp_patchcache_prune_counter
	g_interp_patchcache_prune_counter += 1
	if g_interp_patchcache_prune_counter > 200:
		g_interp_patchcache_prune_counter = 0
		vids_to_remove = []
		for vid, infos in g_interp_patchcache_vid_to_infos.iteritems():
			info_idxes_to_remove = []
			for idx, info in enumerate(infos):
				if info.time_window.end <= time_window_.end - 1000*60*20:
					info_idxes_to_remove.append(idx)
			for idx in info_idxes_to_remove[::-1]:
				del infos[idx]
			if not infos:
				vids_to_remove.append(vid)
		for vid in vids_to_remove:
			del g_interp_patchcache_vid_to_infos[vid]

# Note 238947623476324: here we're ignoring the direction of lo_vi for the same reason discussed at note 23946278623746. 
# 
# arg important_vi_idxes_: None means they're all important.   Non-None means we're patching. 
def interp_impl(r_interptime_to_vi_, interptimes_, important_vi_idxes_, vis_, grades_, paths_, 
		be_clever_, current_conditions_, dir_, datazoom_, log_):
	if important_vi_idxes_ is not None:
		assert isinstance(important_vi_idxes_, set)
		assert -1 not in important_vi_idxes_
		assert all(idx in range(len(vis_)) for idx in important_vi_idxes_)
	vid = vis_[0].vehicle_id
	for interptime in interptimes_:
		lolo_vi, lo_vi, hi_vi, lolo_idx, lo_idx, hi_idx = get_nearest_time_vis(vis_, interptime)
		if important_vi_idxes_ is not None:
			if not any(idx in important_vi_idxes_ for idx in (lolo_idx, lo_idx, hi_idx)):
				continue
			elif interptime in r_interptime_to_vi_:
				del r_interptime_to_vi_[interptime]
		i_vi = None
		time_ratio = 0.0
		if lo_vi and hi_vi:
			if be_clever_ and ((min(interptime - lo_vi.time, hi_vi.time - interptime) > 3*60*1000) or dirs_disagree(dir_, hi_vi.dir_tag_int)\
					or (lo_vi.fudgeroute != hi_vi.fudgeroute)): # see note 238947623476324 
				continue
			time_ratio = (interptime - lo_vi.time)/float(hi_vi.time - lo_vi.time)
			lo_grade = grades_[lo_idx]; hi_grade = grades_[hi_idx]
			if (lo_grade, hi_grade) in (('g', 'g'), ('g', 'r'), ('r', 'g')):
				i_latlon, i_heading, i_mofr = path_interp_single_latlonnheadingnmofr(
						lo_vi, hi_vi, time_ratio, lo_idx, hi_idx, grades_, paths_, log_)
			else:
				i_latlon, i_heading, i_mofr = \
						nonpath_interp_single_latlonnheadingnmofr(lo_vi, hi_vi, time_ratio, datazoom_, be_clever_, log_)
			i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, i_heading, vid, i_latlon.lat, i_latlon.lng,
									 lo_vi.predictable and hi_vi.predictable,
									 lo_vi.fudgeroute, lo_vi.route_tag, 0, interptime, interptime, i_mofr, None, 
									 None, None, None)
		elif lo_vi and not hi_vi:
			if current_conditions_:
				if be_clever_ and ((interptime - lo_vi.time > 3*60*1000) or dirs_disagree(dir_, lo_vi.dir_tag_int)):
					continue
				if grades_[lo_idx] == 'g':
					latlng, heading = paths_[lo_idx].get_piece(-1).mapl_to_latlngnheading('max')
				else:
					latlng, heading = get_latlonnheadingnmofr_from_lo_sample(lolo_vi, lo_vi, datazoom_, be_clever_, log_)[:2]
				i_vi = vinfo.VehicleInfo(lo_vi.dir_tag, heading, vid, latlng.lat, latlng.lng,
						lo_vi.predictable, lo_vi.fudgeroute, lo_vi.route_tag, 0, interptime, interptime, lo_vi.mofr, lo_vi.widemofr, 
						None, None, None)

		if i_vi:
			r_interptime_to_vi_[interptime] = i_vi
			if log_:
				printerr('vid %s, interpolation result for %s %s' % 
						(vid, em_to_str_hms(interptime), ('(time ratio: %.2f)' % time_ratio if time_ratio else '')))
				printerr('\tlo: %s' % lo_vi)
				if hi_vi:
					printerr('\thi: %s' % hi_vi)
				printerr('\t==> %s' % i_vi)

def get_interp_info_from_patchcache(vis_, be_clever_, current_conditions_, dir_, datazoom_, time_window_):
	r = (None, None)
	should_use_patchcache = interp_should_use_patchcache(be_clever_, current_conditions_, dir_, datazoom_, time_window_)
	vid = vis_[0].vehicle_id
	if should_use_patchcache:
		if vid in g_interp_patchcache_vid_to_infos:
			infos = g_interp_patchcache_vid_to_infos[vid]
			info = max2((info for info in infos if info.args_match(dir_, datazoom_)), key=lambda info: info.time_window.end)
			if info is not None and info.time_window.span == time_window_.span \
						and time_window_.end - 1000*60*20 < info.time_window.end < time_window_.end:
				earliest_new_vi_in_old_vis_idx = is_there_a_useful_vi_subseq_for_interp_patchcache(info.vis, vis_)
				if earliest_new_vi_in_old_vis_idx != -1:
					r = (info, earliest_new_vi_in_old_vis_idx)
	return r

def is_there_a_useful_vi_subseq_for_interp_patchcache(old_vis_, new_vis_):
	for vis in (old_vis_, new_vis_):
		assert vis
		assert is_sorted(vis, key=lambda vi: vi.time)
		assert len(set(vi.time for vi in vis)) == len(vis)
	r = -1
	timekeyfunc = lambda vi: vi.time
	earliest_new_vi_time = new_vis_[0].time
	earliest_new_vi_in_old_vis_idx = find(old_vis_, earliest_new_vi_time, timekeyfunc)
	if earliest_new_vi_in_old_vis_idx != -1:
		old_vis_subseq = old_vis_[earliest_new_vi_in_old_vis_idx:]
		if len(old_vis_subseq) > 5: # arbitrary 
			new_vis_subseq = new_vis_[:len(old_vis_subseq)]
			if are_lists_equal(old_vis_subseq, new_vis_subseq, vinfo.VehicleInfo.fast_partial_eq):
				r = earliest_new_vi_in_old_vis_idx
	return r

def interp_should_use_patchcache(be_clever_, current_conditions_, dir_, datazoom_, time_window_):
	return INTERP_USE_PATCHCACHE and be_clever_ and current_conditions_ and dir_ is not None \
			and datazoom_ is not None and time_window_ is not None

class InterpInfo(object):

	def __init__(self, vis_, time_window_, dir_, datazoom_, grades_, paths_, interptime_to_vi_):
		self.time_window = time_window_
		self.direction = dir_
		self.datazoom = datazoom_
		assert len(vis_) == len(grades_)
		self.vis = vis_ # these are the source vis, from the database. 
		self.grades = grades_
		self.paths = paths_
		self.r_interptime_to_vi = interptime_to_vi_ # these are the generated, interpolated vis.

	def args_match(self, dir_, datazoom_):
		return (self.direction == dir_ and self.datazoom == datazoom_)

	def latest_vi_dir(self):
		return self.src_vi_time_to_dir[max(self.src_vi_time_to_dir.iterkeys())]

def path_interp_single_latlonnheadingnmofr(lo_vi_, hi_vi_, time_ratio_, lo_idx_, hi_idx_, grades_, paths_, log_):
	assert lo_vi_.vehicle_id == hi_vi_.vehicle_id
	lo_grade = grades_[lo_idx_]
	path = paths_[lo_idx_ if lo_grade == 'g' else hi_idx_]
	pieceidx = get_piece_idx(lo_idx_, grades_)
	i_latlng, i_heading = get_latlngnheading_from_path(path, pieceidx, time_ratio_)
	i_mofr = None
	if log_:
		printerr('vid %s path interpolation between %s and %s /\n%s and %s:' % \
				(lo_vi_.vehicle_id, lo_vi_.latlng, hi_vi_.latlng, lo_vi_.timestr, hi_vi_.timestr))
		printerr('\ttime_ratio=%.2f, pieceidx=%d' % (time_ratio_, pieceidx))
		printerr('\tpiece=%s' % path.latlngs(pieceidx))
		printerr('\tresult=%s' % i_latlng)
	return (i_latlng, i_heading, i_mofr)

def get_latlngnheading_from_path(path_, pieceidx_, time_ratio_):
	piece = path_.get_piece(pieceidx_)
	mapl = piece.length_m() * time_ratio_
	return piece.mapl_to_latlngnheading(mapl)

def get_piece_idx(lo_idx_, grades_):
	r = -1
	for i in range(lo_idx_, -1, -1):
		r += 1
		grade = grades_[i]
		if grade != 'g':
			if grade == 'o':
				r -= 1
			break
	return r

def get_grade_stretch_info(vis_, time_window_, be_clever_, log_):
	vid = vis_[0].vehicle_id
	return get_grade_stretch_info_impl(tuple(vis_), time_window_, vis_[0].time, vis_[-1].time, be_clever_, vid, log_)

# returns (grades, paths): 
#   Both lists have the same length as vis_, and their elements correspond to vis_. 
# 	- grades: all elements are meaningful.  values are 'r', 'g', or 'o'.
#		- paths: only indexes which have a value of 'g' in grades are not None. 
@lru_cache(100, posargkeymask=(0,1,1,1,1,1,1))
# Re: lru_cache - It's important that this cache at least the maximum number of 
# vehicles that will ever appear in the locations 
# report for one route / one direction.  If this cache size is even 1 less than 
# that, then every time around the loop over the datazooms in reports.py / 
# make_all_reports_and_insert_into_db_once(), these will be forgotten, and 
# performance will suffer badly. 
def get_grade_stretch_info_impl(vis_, time_window_, t1_, t2_, be_clever_, vid_, log_):
	assert vis_ and vinfo.same_vid(vis_)
	assert is_sorted(vis_, key=lambda vi: vi.time)

	n = len(vis_)

	if not be_clever_:
		return (['o']*n, [None]*n)

	if log_: printerr('Calculating grades for vid %s...' % vis_[0].vehicle_id)

	offroute = [vi.mofr == -1 for vi in vis_]

	def mofr(i__):
		return vis_[i__].mofr

	# Set the vis near the ends of on-route stretches to be off-route.  
	# Precisely: all vis within GRAPH_SNAP_RADIUS of the last (or first) on-route vi 
	# right before (or after) an off-route stretch (including that vi itself). 
	stretches = get_maximal_sublists3(range(n), lambda i: offroute[i])
	for stretchi in range(len(stretches)):
		stretch = stretches[stretchi]
		if not offroute[stretch[0]]:
			if stretchi > 0:
				ref_mofr = mofr(stretch[0])
				offroute[stretch[0]] = True
				if log_: printerr('Set grade to OFF-ROUTE due to it being near end of on-route stretch:\n%s' % vis_[stretch[0]])
				for i in stretch[1:]:
					if abs(mofr(i) - ref_mofr) < c.GRAPH_SNAP_RADIUS:
						offroute[i] = True
						if log_: printerr('Set grade to OFF-ROUTE due to it being near end of on-route stretch:\n%s' % vis_[i])
					else:
						break
			if stretchi < len(stretches) - 1:
				ref_mofr = mofr(stretch[-1])
				offroute[stretch[-1]] = True
				if log_: printerr('Set grade to OFF-ROUTE due to it being near end of on-route stretch:\n%s' % vis_[stretch[-1]])
				for i in stretch[-2::-1]:
					if abs(mofr(i) - ref_mofr) < c.GRAPH_SNAP_RADIUS:
						offroute[i] = True
						if log_: printerr('Set grade to OFF-ROUTE due to it being near end of on-route stretch:\n%s' % vis_[i])
					else:
						break
			
	# Set vis that are part of trivially short (distance-wise) on-route stretches to be off-route: 
	stretches = get_maximal_sublists3(range(n), lambda i: offroute[i])
	for stretchi in range(len(stretches)):
		stretch = stretches[stretchi]
		if not offroute[stretch[0]]:
			mofrs = [mofr(i) for i in stretch]
			mofr_span = max(mofrs) - min(mofrs)
			if mofr_span < c.GRAPH_SNAP_RADIUS:
				for i in stretch:
					offroute[i] = True
					if log_: printerr('Set grade to OFF-ROUTE due to it being part of an on-route stretch that is too short:\n%s' % vis_[i])

	grades = ['o' if offroute[i] else 'r' for i in xrange(n)]

	if DISABLE_GRAPH_PATHS:
		return (grades, [None]*n)

	sg = (tracks.get_snapgraph() if vis_[0].is_a_streetcar() else streets.get_snapgraph())
	for i in xrange(n):
		if grades[i] == 'o':
			locs = vis_[i].graph_locs
			if len(locs) > 0:
				grades[i] = 'g'

	def get_grade(stretch__):
		return grades[stretch__[0]]

	# We can't use 'g' stretches of length 1 which are surrounded by either 'o' stretches or nothing.  
	# So here we remove them and make them 'o'. 
	# Because what would we do with them?  There is no graph path between an 'o' point and a 'g' point - 
	# that is, eg. the last 'o' point in the stretch before this length=1 'g' stretch.  
	# This is unlike a length=1 'g' stretch which has an 'r' stretch before or after.  Because 
	# of our assumption that the (streetcar or street) graph is a superset of the route in question, 
	# we can always get a graph path between an 'r' point and a 'g' point. 
	# So here we filter out those useless stretches, both because they are useless, and because if we 
	# don't, the find_multipath() code below will fail because it doesn't like being passed a latlngs 
	# list of length 1. 
	stretches = get_maximal_sublists3(range(n), lambda i: grades[i])
	for i, stretch, isfirst, islast in enumerate2(stretches):
		if get_grade(stretch) == 'g' and len(stretch) == 1 and \
					(isfirst or get_grade(stretches[i-1]) == 'o') and (islast or get_grade(stretches[i+1]) == 'o'):
			grades[stretch[0]] = 'o'
			if log_: printerr('Set grades to \'o\' due to it being part of len=1 by itself:\n%s' % vis_[stretch[0]])

	stretches = get_maximal_sublists3(range(n), lambda i: grades[i])

	paths = [None]*n
	for stretchi, stretch in enumerate(stretches):
		if get_grade(stretch) == 'g':
			latlngs = [vis_[i].latlng for i in stretch]
			locses = [vis_[i].graph_locs for i in stretch]
			path_vis = [vis_[i] for i in stretch]
			if stretchi > 0 and get_grade(stretches[stretchi-1]) == 'r':
				vi = vis_[stretches[stretchi-1][-1]]
				latlngs.insert(0, vi.latlng)
				locses.insert(0, vi.graph_locs)
				path_vis.insert(0, vi)
			if stretchi < len(stretches)-1 and get_grade(stretches[stretchi+1]) == 'r':
				vi = vis_[stretches[stretchi+1][0]]
				latlngs.append(vi.latlng)
				locses.append(vi.graph_locs)
				path_vis.append(vi)
			if log_:
				printerr('vid %s - latlngs / locses for stretch %d:' % (vid_, stretchi))
				for i, (latlng, locs) in enumerate(zip(latlngs, locses)): 
					printerr('[%3d] %s, %s' % (i, latlng, locs))
			path = sg.find_multipath(latlngs, path_vis, locses, log_)
			if path is None:
				raise Exception('No multipath for:\n%s' % '\n'.join(['%s / %s' % x for x in zip(latlngs, locses)]))
			if log_:
				first_vi = vis_[stretch[0]]; last_vi = vis_[stretch[-1]]
				printerr('vid %s - path for stretch %d (%s to %s):' % (vid_, stretchi, first_vi.timestr, last_vi.timestr))
				for piecei, piecesteps in enumerate(path.piecestepses):
					printerr('piece %d: %s' % (piecei, piecesteps))
				printerr('vid %s - path for stretch %d, all latlngs: %s' % (vid_, stretchi, path.latlngs()))
			for i in stretch:
				paths[i] = path

	if log_:
		printerr('vid %s - final grades:' % vid_)
		for i, vi in enumerate(vis_):
			printerr('\t%s / %s: %s' % (vi.timestr, vi.latlng, grades[i]))

	return (grades, paths)

# Either arg could be None (i.e. blank dir_tag).  For this we consider None to 'agree' with 0 or 1.
def dirs_disagree(dir1_, dir2_):
	return (dir1_ == 0 and dir2_ == 1) or (dir1_ == 1 and dir2_ == 0)

# To do it this way may seem odd but we get the latest of these things by interpolating between the second-last (lolo) and 
# the last (lo) with a ratio of 1.0, because that extrapolation code (nonpath_interp_single_latlonnheadingnmofr()) has some nice code that does 
# snap-by-mofr or snap-to-tracks, which I don't feel like copying and pasting and stripping down for the ratio = 1.0 case. 

# lolo_vi_ may seem unnecessary here because of the ratio of 1.0, but it is used to find the heading 
# if tracks are being used - will be a choice between X and X + 180.  If we have only one sample (lo_vi_) then common sense 
# says that there's no way that we can figure out that heading.  
def get_latlonnheadingnmofr_from_lo_sample(lolo_vi_, lo_vi_, datazoom_, be_clever_, log_):
	assert lo_vi_ is not None
	if lolo_vi_ is not None:
		return nonpath_interp_single_latlonnheadingnmofr(lolo_vi_, lo_vi_, 1.0, datazoom_, be_clever_, log_)
	else:
		# We would do something like this:
		#return nonpath_interp_single_latlonnheadingnmofr(lo_vi_, lo_vi_, 1.0, datazoom_, be_clever_, log_)
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
def nonpath_interp_single_latlonnheadingnmofr(vi1_, vi2_, time_ratio_, datazoom_, be_clever_, log_):
	assert isinstance(vi1_, vinfo.VehicleInfo) and isinstance(vi2_, vinfo.VehicleInfo) and (vi1_.vehicle_id == vi2_.vehicle_id)
	assert vi1_.time < vi2_.time and (datazoom_ is None or datazoom_ in c.VALID_DATAZOOMS)
	r = None
	can_be_clever = vi1_.dir_tag and vi2_.dir_tag and (vi1_.fudgeroute == vi2_.fudgeroute)
	being_clever = be_clever_ and can_be_clever
	if being_clever:
		froute = vi1_.fudgeroute
		if vi1_.mofr!=-1 and vi2_.mofr!=-1:
			interp_mofr = geom.avg(vi1_.mofr, vi2_.mofr, time_ratio_)
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
		r = (vi1_latlng.avg(vi2_latlng, time_ratio_), vi1_latlng.heading(vi2_latlng), -1) # see note 23906728947234 

	if log_:
		printerr('vid %s non-path interpolation between %s and %s /\n%s and %s:' % \
				(vi1_.vehicle_id, vi1_.latlng, vi2_.latlng, vi1_.timestr, vi2_.timestr))
		printerr('\ttime_ratio=%.2f' % time_ratio_)
		printerr('\tresult=%s' % r[0])

	return r

def get_locations_clientside_list(vid_to_interptime_to_vi_, time_window_, log_=False):
	time_to_vis = {time: [] for time in lrange(time_window_.start, time_window_.end+1, 60*1000)}
	for interptime_to_vi in vid_to_interptime_to_vi_.itervalues():
		for interptime, vi in interptime_to_vi.iteritems():
			if vi is not None:
				time_to_vis[interptime].append(vi)

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
	# Making sure that all times that were in the time_to_vis arg are in the 
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
	purge_delete(num_days_)
	purge_vacuum()

@lock
@trans
def purge_delete(num_days_):
	curs = conn().cursor()
	# Delete all rows older than X days: 
	num_millis = 1000*60*60*24*num_days_
	curs.execute('delete from ttc_vehicle_locations where time_retrieved < round(extract(epoch from clock_timestamp())*1000) - %d;' % num_millis)
	curs.execute('delete from predictions where time_retrieved < round(extract(epoch from clock_timestamp())*1000) - %d;' % num_millis)
	curs.execute('delete from reports where time < round(extract(epoch from clock_timestamp())*1000) - %d;' % num_millis)
	curs.close()

@lock
def purge_vacuum():
	old_isolation_level = conn().isolation_level
	conn().set_isolation_level(0)
	curs = conn().cursor()
	curs.execute('vacuum analyze;')
	curs.close()
	conn().set_isolation_level(old_isolation_level)

@lock
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
@lock
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
@lock
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

@lock
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
@lock
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
@lock
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

@lock
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
		raise Exception('route=%s, dir=%d - either the most current report in database is too old (max age=%d minutes), '\
				'or no reports for this app version (%s) exist.' % (froute_, dir_, c.REPORTS_MAX_AGE_MINS, c.VERSION))
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
@lock
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

@lock
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

@lock
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

# This is not precise, but hopefully will be helpful for the /developer/ using traffic.php. 
@lock
@trans
def get_debug_reports_froute_and_dir(report_time_):
	curs = conn().cursor()
	curs.execute('''select froute, char_length(report_json) from reports where time = %s 
			and report_type = 'locations' and datazoom = 0 and app_version = 'dev' order by direction''', [report_time_])
	rows = []
	while True:
		row = curs.fetchone()
		if row:
			rows.append(row)
		else:
			break
	curs.close()
	if len(rows) not in (0, 2):
		raise Exception('Was expecting either 0 or 2 rows.')
	if len(rows) == 0:
		return None
	else:
		if rows[0][0] != rows[1][0]:
			raise Exception('Was expecting same froute in both rows.')
		froute = rows[0][0]
		# Figuring that the locations report with the longer JSON string is probably where most of the data is: 
		direction = (0 if rows[0][1] > rows[1][1] else 1)
		return (froute, direction)

@lock
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

g_patchcache_froute_n_vid_to_time_window_n_plausgroups = {}

# This is for removing large buggy GPS readings (example: vehicle 4116 2012-06-15 13:30 to 14:00.)
def get_plausgroups(vis_, froute_, time_window_):
	global g_patchcache_froute_n_vid_to_time_window_n_plausgroups
	assert vis_ and is_sorted(vis_, key=lambda vi: vi.time) and vinfo.same_vid(vis_) and isinstance(time_window_, TimeWindow)
	vid = vis_[0].vehicle_id
	r = None
	cachekey = (froute_, vid)
	if c.USE_PATCHCACHES and cachekey in g_patchcache_froute_n_vid_to_time_window_n_plausgroups:
		old_time_window, old_plausgroups = g_patchcache_froute_n_vid_to_time_window_n_plausgroups[cachekey]
		assert old_plausgroups
		if old_time_window.span == time_window_.span and 0 <= time_window_.end - old_time_window.end < 1000*60*20:
			r = copy_plausgroups_for_patchcache(old_plausgroups)
			trim_plausgroups_by_time_window(r, time_window_)
			new_vis = old_time_window.gt_trimmed_vilist(vis_)
			for new_vi in new_vis:
				add_vi_to_appropriate_plausgroup(r, new_vi)
	if not r:
		r = []
		for vi in vis_:
			add_vi_to_appropriate_plausgroup(r, vi)
	prune_patchcache_get_plausgroups(time_window_)
	g_patchcache_froute_n_vid_to_time_window_n_plausgroups[cachekey] = (time_window_, copy_plausgroups_for_patchcache(r))
	return r

# deepcopy is slow.  So for performance we're sharing vis a lot.  Be careful and don't modify them.
def copy_plausgroups_for_patchcache(orig_groups_):
	r = []
	for orig_group in orig_groups_:
		r_group = []
		r.append(r_group)
		for vi in orig_group:
			r_group.append(vi)
	return r

def prune_patchcache_get_plausgroups(time_window_):
	global g_patchcache_froute_n_vid_to_time_window_n_plausgroups
	for key, (time_window, plausgroups) in g_patchcache_froute_n_vid_to_time_window_n_plausgroups.items():
		if abs(time_window_.end - time_window.end) > 1000*60*30:
			del g_patchcache_froute_n_vid_to_time_window_n_plausgroups[key]

def trim_plausgroups_by_time_window(groups_, time_window_):
	for group in groups_:
		time_window_.trim_vilist(group)
	groups_[:] = [group for group in groups_ if group]

def add_vi_to_appropriate_plausgroup(groups_, vi_):

	if len(groups_) == 0:
		groups_.append([vi_])
	else:
		def get_dist_from_group(group_):
			groups_last_vi = group_[-1]
			groups_last_vi_to_cur_vi_metres = vi_.latlng.dist_m(groups_last_vi.latlng)
			return groups_last_vi_to_cur_vi_metres

		def get_mps_from_group(group_):
			groups_last_vi = group_[-1]
			groups_last_vi_to_cur_vi_metres = vi_.latlng.dist_m(groups_last_vi.latlng)
			groups_last_vi_to_cur_vi_secs = abs((vi_.time - groups_last_vi.time)/1000.0)
			return groups_last_vi_to_cur_vi_metres/groups_last_vi_to_cur_vi_secs

		def is_plausible_group(group_):
			return is_plausible(get_dist_from_group(group_), mps_to_kmph(get_mps_from_group(group_)))

		closest_group = min(groups_, key=get_dist_from_group)
		if is_plausible_group(closest_group):
			closest_group.append(vi_)
		else:
			groups_.append([vi_])

def new_add_vi_to_appropriate_plausgroup(groups_, vi_):

	if len(groups_) == 0:
		groups_.append([vi_])
	else:
		def get_meters_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			groups_last_vi_to_cur_vi_metres = vi_.latlng.dist_m(groups_last_vi.latlng)
			return groups_last_vi_to_cur_vi_metres

		def get_secs_from_vigroup(vigroup_):
			groups_last_vi = vigroup_[-1]
			return abs((vi_.time - groups_last_vi.time)/1000.0)

		def is_plausible_vigroup(vigroup_):
			dist_from_vigroup = get_meters_from_vigroup(vigroup_)
			secs_from_vigroup = get_secs_from_vigroup(vigroup_)
			kmph_from_vigroup = mps_to_kmph(dist_from_vigroup/secs_from_vigroup)
			return is_plausible(dist_from_vigroup, kmph_from_vigroup)

		closest_vigroup = min(groups_, key=get_meters_from_vigroup)
		if is_plausible_vigroup(closest_vigroup):
			closest_vigroup.append(vi_)
		else:
			groups_.append([vi_])

def get_best_plausgroup(groups_, log_=False):
	if len(groups_):
		r = max(groups_, key=len)
		if log_:
			vid = r[0].vehicle_id
			if len(groups_) == 1:
				printerr('Plausibility groups - vid %s - there was only one group.' % vid)
			else:
				printerr('Plausibility groups - vid %s - chose group %d.' % (vid, groups_.index(r)))
				printerr('---')
				for vi in r:
					groupidx = firstidx(groups_, lambda vigroup: vi in vigroup)
					printerr('%d - %s' % (groupidx, vi))
				printerr('---')
				for groupidx, vigroup in enumerate(groups_):
					for vi in vigroup:
						printerr('%d - %s' % (groupidx, vi))
				printerr('---')
			printerr('Plausibility groups - vid %s - groups as JSON:' % vid)
			printerr([[vi.latlng.ls() for vi in vigroup] for vigroup in groups_])
		return r
	else:
		if log_:
			printerr('Plausibility groups - no vis.')
		return []

def fix_doubleback_gps_noise(vis_, startidx=0, log_=False):
	assert is_sorted(vis_, key=lambda vi: vi.time)
	if len(vis_) == 0:
		return
	assert vinfo.same_vid(vis_)
	if log_:
		vid = vis_[0].vehicle_id
		printerr('vid %s - fix_doubleback_gps_noise - before:' % vid)
		for vi in vis_:
			printerr(vi)
		fixes = []
	D = 20
	i = startidx
	while i < len(vis_):
		if i < 2:
			i += 1
		else:
			preref_pos = vis_[i-2].latlng; ref_vi = vis_[i-1]; ref_pos = ref_vi.latlng; i_pos = vis_[i].latlng
			if ref_pos.dist_m(i_pos) > D:
				i += 1
			else:
				ref_heading = preref_pos.heading(ref_pos)
				i_heading = ref_pos.heading(i_pos)
				if geom.diff_headings(ref_heading, i_heading) < 90:
					i += 1
				else:
					if vis_[i].latlng != ref_pos:
						if log_:
							fix = [vis_[i].latlng, ref_pos]
							printerr('vid %s - fix_doubleback_gps_noise - fixing vi #%d (%s) - from/to: %s' % 
								(vid, i, vis_[i].timestr, fix))
							fixes.append(fix)
						vis_[i] = vis_[i].copy() # Making a copy b/c that vi might be cached. 
						vis_[i].copy_pos_info(ref_vi)
					for j in range(i+1, len(vis_)):
						i = j
						j_pos = vis_[j].latlng
						if ref_pos.dist_m(j_pos) > D:
							break
						else:
							if vis_[j].latlng != ref_pos:
								if log_:
									fix = [vis_[j].latlng, ref_pos]
									printerr('vid %s - fix_doubleback_gps_noise - fixing vi #%d (%s) - from/to: %s' % 
										(vid, j, vis_[j].timestr, fix))
									fixes.append(fix)
								vis_[j] = vis_[j].copy() # Making a copy b/c that vi might be cached. 
								vis_[j].copy_pos_info(ref_vi)
					else:
						i = len(vis_)
	if log_:
		printerr('vid %s - fix_doubleback_gps_noise - fixes: %s' % (vid, fixes))
		printerr('vid %s - fix_doubleback_gps_noise - after:' % vid)
		for vi in vis_:
			printerr(vi)

if __name__ == '__main__':

	pass


