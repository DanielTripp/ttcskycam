#!/usr/bin/python2.6

import pprint
from collections import *
from lru_cache import lru_cache
import vinfo, db, routes, geom, mc, yards, c
from misc import *

TIME_WINDOW_MINUTES = 30
RAWSPEEDS_USE_PATCHCACHE = c.USE_PATCHCACHES

def get_recent_vehicle_locations(fudgeroute_, dir_, datazoom_, time_, last_returned_timestr_, log_=False):
	assert (fudgeroute_ in routes.NON_SUBWAY_FUDGEROUTES)
	time_ = massage_time_arg(time_, 60*1000)
	r_timestr = em_to_str_ymdhms(time_)
	if r_timestr != last_returned_timestr_:
		r_data = get_recent_vehicle_locations_impl(fudgeroute_, dir_, datazoom_, time_, log_)
	else:
		r_data = None
	return (r_timestr, r_data)

def get_recent_vehicle_locations_impl(fudgeroute_, dir_, datazoom_, time_, log_=False):
	assert (time_!=0)
	return db.get_recent_vehicle_locations(fudgeroute_, TIME_WINDOW_MINUTES, dir_, datazoom_, time_window_end_=time_, log_=log_)

# returns: key: vid.  value: list of list of VehicleInfo
# second list - these are 'stretches' of increasing (or decreasing) mofr.  Doing it this way so that if the database gives us a
# single vehicle that say goes from mofr = 1000 to mofr = 1500 (over however many VehicleInfo objects), then goes AWOL for a while,
# then reappears and goes from mofr = 500 to mofr = 1200 (i.e. it doubled back and did part of the same route again), then we can
# handle that.
# The above case is in my opinion only moderately important to handle.  Our traffic-determining interpolating code needs monotonic
# vis like this, but we could get them another way eg. removing the earlier stretch, because it's probably not very crucial
# to the result anyway.  But the more important case to handle is a buggy GPS or mofr case where a vehicle only appears to double back
# (even a little bit) and thus appears to be going in a different direction for a while.  I wouldn't want a case like that to result in
# the discarding of the more important stretch, and I don't want to write code that makes a judgement call about how many metres or
# for how many readings should a vehicle have to go in an opposite direction before we believe that it is really going in that direction.
# So I do it by stretches, like this.
# Example: routes 501/301, westbound, vid = 1531, 2012-10-30 00:45 to 01:15.  The vehicle goes west from 00:45 to 00:54.  Fine.
# Then it also appears to go west briefly between 01:07 and 01:08, but that's a fluke of the mofr reading as it gets bask onto queen
# there.  Then it stands still for a few minutes there.  Then it continues eastward.  I don't want that to mess things up.
# TODO: improve this comment.
def get_vid_to_vis_from_db_for_traffic(fudgeroute_name_, dir_, time_, window_minutes_, usewidemofr_=False, log_=False):
	src = db.get_vid_to_vis_singledir(fudgeroute_name_, dir_, window_minutes_, time_, log_=log_) 
		# We must be careful not to modify this, because it is cached in memory. 
	r = {}
	for vid, vis in src.iteritems():
		r[vid] = filter(lambda vi: (vi.widemofr if usewidemofr_ else vi.mofr) != -1, vis)
	return r

def between(bound1_, value_, bound2_):
	return (bound1_ < value_ < bound2_) or (bound1_ > value_ > bound2_) 

# arg time_ - 0 means "now" i.e. current conditions. 
# 
# returns elem 0: visuals list - [{'start_latlon':..., 'end_latlon':..., 'mofr':..., 'start_mofr':..., 'end_mofr':...}, ...] 
#         elem 1: speed map - {mofr1: {'kmph': kmph, 'weight': weight}, ...}
def get_traffics(fudgeroute_name_, dir_, datazoom_, time_, last_returned_timestr_, window_minutes_=TIME_WINDOW_MINUTES, log_=False):
	assert (fudgeroute_name_ in routes.NON_SUBWAY_FUDGEROUTES) and isinstance(window_minutes_, int) and (1 <= window_minutes_ < 120)
	time_ = massage_time_arg(time_, 60*1000)
	r_timestr = em_to_str_ymdhms(time_)
	if r_timestr != last_returned_timestr_:
		r_data = get_traffics_impl(fudgeroute_name_, dir_, datazoom_, time_, window_minutes_, log_)
	else:
		r_data = None
	return (r_timestr, r_data)

def get_traffics_impl(fudgeroute_name_, dir_, datazoom_, time_, window_minutes_=TIME_WINDOW_MINUTES, log_=False):
	assert dir_ in (0, 1) or (len(dir_) == 2 and all(isinstance(e, geom.LatLng) for e in dir_)) and (time_!=0)
	if dir_ in (0, 1):
		direction = dir_
	else:
		direction = routes.routeinfo(fudgeroute_name_).dir_from_latlngs(dir_[0], dir_[1])
	mofr_to_avgspeedandweight = get_traffic_avgspeedsandweights(fudgeroute_name_, direction, datazoom_, time_, True, window_minutes_, log_=log_)
	return [get_traffics_visuals(mofr_to_avgspeedandweight, fudgeroute_name_, direction, datazoom_), \
			get_traffics__mofr2speed(mofr_to_avgspeedandweight)]

def get_traffics__mofr2speed(mofr_to_avgspeedandweight_):
	r = {}
	for mofr, traf in mofr_to_avgspeedandweight_.items():
		if traf != None:
			r[mofr] = {'kmph': traf['kmph'], 'weight': traf['weight']}
		else:
			r[mofr] = None
	return r

def get_traffics_visuals(mofr_to_avgspeedandweight_, froute_, dir_, datazoom_):
	assert datazoom_ in c.VALID_DATAZOOMS
	mofrstep = c.DATAZOOM_TO_MOFRSTEP[datazoom_]
	r = []
	ri = routes.routeinfo(froute_)
	for routept1_mofr, routept2_mofr in hopscotch(ri.routeptmofrs(dir_, datazoom_)):
		route_seg_len = routept2_mofr - routept1_mofr
		routept1_mofr_ref = roundbystep(routept1_mofr, mofrstep); routept2_mofr_ref = roundbystep(routept2_mofr, mofrstep)
		for mofr_ref in range(routept1_mofr_ref, routept2_mofr_ref+1, mofrstep):
			if mofr_ref not in mofr_to_avgspeedandweight_: continue
			seg_start_mofr = max(mofr_ref - mofrstep/2, routept1_mofr)
			seg_end_mofr = min(mofr_ref + mofrstep/2, routept2_mofr)
			routept1 = ri.mofr_to_latlon(routept1_mofr, dir_, datazoom_)
			routept2 = ri.mofr_to_latlon(routept2_mofr, dir_, datazoom_)
			seg_start_latlng = routept1.add(routept2.subtract(routept1).scale((seg_start_mofr-routept1_mofr)/float(route_seg_len)))
			seg_end_latlng   = routept1.add(routept2.subtract(routept1).scale((seg_end_mofr  -routept1_mofr)/float(route_seg_len)))
			if seg_start_latlng.dist_m(seg_end_latlng) > c.DATAZOOM_TO_RDP_EPSILON[datazoom_]: 
				# Any smaller and they'll be too small to see. 
				# Using the rdp epsilon b/c for most cases because 2*epsilon will be visible when zoomed out.  
				r.append({'start_latlon': seg_start_latlng, 'end_latlon': seg_end_latlng, 'mofr': mofr_ref, 
						'start_mofr': routept1_mofr, 'end_mofr': routept2_mofr})
	return r

def get_mofr_to_kmph(froute_, dir_, current_, time_, window_minutes_=TIME_WINDOW_MINUTES, log_=False):
	time_ = massage_time_arg(time_, 60*1000)
	return mc.get(get_mofr_to_kmph_impl, [froute_, dir_, current_, time_, window_minutes_, log_])

def get_mofr_to_kmph_impl(froute_, dir_, current_, time_, window_minutes_, log_=False):
	r = {}
	for mofr, avgspeedandweight in get_traffic_avgspeedsandweights(froute_, dir_, MAX_DATAZOOM, time_, current_, window_minutes_, log_=log_).iteritems():
		if avgspeedandweight is not None:
			r[mofr] = avgspeedandweight['kmph']
		else:
			r[mofr] = None
	return r

@lru_cache(5)
def get_traffic_avgspeedsandweights(fudgeroute_name_, dir_, datazoom_, time_, current_, window_minutes_, log_=False):
	r = {}
	mofr_to_rawtraffics = get_traffic_rawspeeds(fudgeroute_name_, dir_, datazoom_, time_, window_minutes_, log_=log_)
	for mofr, rawtraffics in sorted(mofr_to_rawtraffics.iteritems()): # Here we iterate in sorted key order only to print easier-to-read log msgs.
		if log_: printerr('mofr=%d:' % mofr)
		if not rawtraffics:
			if log_: printerr('\tNo raw traffics.')
			r[mofr] = None
		else:
			rawtraffics = [x.copy() for x in rawtraffics] # copying b/c it's cached.
			for rawtraf in rawtraffics:
				rawtraf['weight'] = (time_to_weight(rawtraf['time'], time_, window_minutes_) if current_ else 1.0)
				if log_: printerr('\tInterpolated time %s (kmph=%.1f, vid=%s) ==> weight %.3f' \
						% (em_to_str_hms(rawtraf['time']), rawtraf['speed_kmph'], rawtraf['vid'], rawtraf['weight']))
			weights_total = sum([x['weight'] for x in rawtraffics])
			if weights_total >= 0.01:
				weighted_avg_speed = abs(sum([x['speed_kmph']*x['weight']/weights_total for x in rawtraffics]))
				r[mofr] = {'kmph': weighted_avg_speed, 'weight': weights_total}
				if log_: printerr('\tWeighted speed: %.1f kmph.' % weighted_avg_speed)
			else:
				if log_: printerr('\tWeighted speed: none.  (Due to zero or negligible weight tally at this mofr.')
				r[mofr] = None
	return r

def time_to_weight(time_, now_, window_minutes_):
	window = window_minutes_*60*1000
	window_begin = now_ - window
	if time_ >= now_: # must be an extrapolation 
		return 1.0
	elif time_ < window_begin + 1000:
		return 0.0
	else:
		# I believe this is a quarter circle: 
		return (1 - ((float(time_ - now_))/window)**2)**0.5

def get_traffic_rawspeeds(froute_, dir_, datazoom_, time_, window_minutes_, usewidemofr_=False, singlemofr_=None, log_=False):
	assert dir_ in (0, 1) and datazoom_ in c.VALID_DATAZOOMS
	time_window = TimeWindow(time_-1000*60*window_minutes_, time_)
	mofrstep = c.DATAZOOM_TO_MOFRSTEP[datazoom_]
	mofr_to_rawtraffics = {}
	mofrs_to_get = (range(0, routes.max_mofr(froute_), mofrstep) if singlemofr_ is None else [singlemofr_])
	for mofr in mofrs_to_get:
		mofr_to_rawtraffics[mofr] = []
	for vid, vis_all_stretches in \
				get_vid_to_vis_from_db_for_traffic(froute_, dir_, time_, window_minutes_, usewidemofr_=usewidemofr_, log_=log_).items():
		vis_all_stretches = vis_all_stretches[::-1]
		for vis in get_stretches(vis_all_stretches, dir_):
			for mofr, rawtraffic in get_traffic_rawspeeds_single_stretch(froute_, dir_, vis[::-1], datazoom_, time_window, usewidemofr_, 
						mofrs_to_get, log_).iteritems():
				mofr_to_rawtraffics[mofr].append(rawtraffic)
	return (mofr_to_rawtraffics if singlemofr_ is None else mofr_to_rawtraffics.values()[0])

g_froute_to_vid_to_rawspeedsinfos = defaultdict(lambda: defaultdict(list))

def get_traffic_rawspeeds_single_stretch(froute_, dir_, vis_, datazoom_, time_window_, usewidemofr_, mofrs_to_get_, log_):
	mofrstep = c.DATAZOOM_TO_MOFRSTEP[datazoom_]
	vid = vis_[0].vehicle_id
	if log_: printerr('For vid "%s":' % (vid))
	if log_:
		for vi in vis_[::-1]:
			printerr('\traw vinfo: %s' % (str(vi)))
	mofr_to_rawtraffic = {}
	if len(vis_) >= 2:
		get_mofr = (lambda vi__: vi__.widemofr) if usewidemofr_ else (lambda vi__: vi__.mofr)
		assert all(get_mofr(vi) != -1 for vi in vis_)

		chunked_vilist = None
		if RAWSPEEDS_USE_PATCHCACHE:
			old_info, num_old_vis_lost = get_rawspeeds_info_from_patchcache(froute_, dir_, vis_, datazoom_, time_window_, 
					usewidemofr_, mofrs_to_get_)
			if old_info is not None:
				mofr_to_rawtraffic = copy_mofr_to_rawtraffic(old_info.r_mofr_to_rawtraffic)
				new_vis = vis_[len(old_info.vis)-num_old_vis_lost:]
				lost_vis = old_info.vis[:num_old_vis_lost]
				if not lost_vis and not new_vis:
					return mofr_to_rawtraffic
				chunked_vilist = old_info.chunked_vilist.copy()
				influenced_traffic_mofrs = chunked_vilist.get_influenced_traffic_mofrs(new_vis)
				influenced_mofrs = chunked_vilist.add_new_vis(new_vis)
				chunked_vilist.remove_old_vis(lost_vis)
				influenced_traffic_mofrs |= chunked_vilist.get_influenced_traffic_mofrs(lost_vis)
				if log_:
					printerr('\tLost vis:') 
					for vi in lost_vis:
						printerr('\t', vi)
					printerr('\tNew vis:') 
					for vi in new_vis:
						printerr('\t', vi)
					printerr('\tPatching traffic at mofrs %s' % (sorted(influenced_traffic_mofrs),))
				real_mofrs_to_get = sorted(set(mofrs_to_get_) & influenced_traffic_mofrs)
		if chunked_vilist is None:
			chunked_vilist = ChunkedViList.create(vis_, mofrstep, usewidemofr_)
			real_mofrs_to_get = (mofr for mofr in mofrs_to_get_ if chunked_vilist.influences_traffic_at(mofr))
		for mofr in real_mofrs_to_get:
			if log_: printerr('\tFor mofr %d:' % (mofr))
			vi_lo, vi_hi = get_bounding_mofr_vis(mofr, mofrstep, chunked_vilist, usewidemofr_)
			if vi_lo and vi_hi:
				if log_: printerr('\t\tFound bounding vis at mofrs %d and %d (%s and %s).' % (get_mofr(vi_lo), get_mofr(vi_hi), vi_lo.timestr, vi_hi.timestr))
				interp_ratio = (mofr - get_mofr(vi_lo))/float(get_mofr(vi_hi) - get_mofr(vi_lo))
				interp_t = int(vi_lo.time + interp_ratio*(vi_hi.time - vi_lo.time))
				speed_kmph = ((get_mofr(vi_hi) - get_mofr(vi_lo))/1000.0)/((vi_hi.time - vi_lo.time)/(1000.0*60*60))
				if log_: printerr('\t\tSpeed: %.1f.  Interpolated time at this mofr: %s' % (speed_kmph, em_to_str_hms(interp_t)))
				# TODO: fix buggy negative speeds a better way, maybe.
				mofr_to_rawtraffic[mofr] = {'speed_kmph': speed_kmph, 'time':interp_t, 'vid': vid}
			else:
				if log_: printerr('\t\tNo bounding vis found for this mofr step / vid.')
				mofr_to_rawtraffic.pop(mofr, None)
		if RAWSPEEDS_USE_PATCHCACHE:
			prune_rawspeeds_patchcache(time_window_)
			if rawspeeds_should_use_patchcache(mofrs_to_get_):
				g_froute_to_vid_to_rawspeedsinfos[froute_][vid].append(
						RawSpeedsInfo(dir_, vis_, datazoom_, time_window_, usewidemofr_, mofrs_to_get_, chunked_vilist, mofr_to_rawtraffic))
	return mofr_to_rawtraffic

g_prune_rawspeeds_counter = 0

def prune_rawspeeds_patchcache(time_window_):
	global g_prune_rawspeeds_counter
	g_prune_rawspeeds_counter += 1
	if g_prune_rawspeeds_counter > 3000:
		g_prune_rawspeeds_counter = 0
		froutes_to_remove = []
		for froute, vid_to_rawspeedsinfos in g_froute_to_vid_to_rawspeedsinfos.iteritems():
			vids_to_remove = []
			for vid, rawspeedsinfos in vid_to_rawspeedsinfos.iteritems():
				idxes_to_remove = []
				for idx, rawspeedsinfo in enumerate(rawspeedsinfos):
					if rawspeedsinfo.time_window.end <= time_window_.end - 1000*60*20:
						idxes_to_remove.append(idx)
				for idx in idxes_to_remove[::-1]:
					del rawspeedsinfos[idx]
				if not rawspeedsinfos:
					vids_to_remove.append(vid)
			for vid in vids_to_remove:
				del vid_to_rawspeedsinfos[vid]
			if not vid_to_rawspeedsinfos:
				froutes_to_remove.append(froute)
		for froute in froutes_to_remove:
			g_froute_to_vid_to_rawspeedsinfos[froute]

def get_rawspeeds_info_from_patchcache(froute_, dir_, vis_, datazoom_, time_window_, usewidemofr_, mofrs_to_get_):
	assert vinfo.same_vid(vis_)
	r = (None, None)
	if rawspeeds_should_use_patchcache(mofrs_to_get_):
		vid = vis_[0].vehicle_id
		infos = g_froute_to_vid_to_rawspeedsinfos[froute_][vid]
		info = max2((info for info in infos if info.args_match(dir_, datazoom_, usewidemofr_, mofrs_to_get_)), 
				key=lambda info: info.time_window.end)
		if info is not None and info.time_window.span == time_window_.span \
					and time_window_.end - 1000*60*20 < info.time_window.end < time_window_.end:
			earliest_new_vi_in_old_vis_idx = is_there_a_useful_vi_subseq_for_rawspeeds_patchcache(info.vis, vis_)
			if earliest_new_vi_in_old_vis_idx != -1:
				r = (info, earliest_new_vi_in_old_vis_idx)
	return r

def is_there_a_useful_vi_subseq_for_rawspeeds_patchcache(old_vis_, new_vis_):
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

def rawspeeds_should_use_patchcache(mofrs_to_get_):
	return len(mofrs_to_get_) > 1

class RawSpeedsInfo(object):

	def __init__(self, dir_, vis_, datazoom_, time_window_, usewidemofr_, mofrs_to_get_, chunked_vilist_, r_mofr_to_rawtraffic_):
		self.direction = dir_
		self.vis = vis_
		self.datazoom = datazoom_
		self.time_window = time_window_
		self.usewidemofr = usewidemofr_
		self.mofrs_to_get = mofrs_to_get_
		self.chunked_vilist = chunked_vilist_
		self.r_mofr_to_rawtraffic = r_mofr_to_rawtraffic_

	def args_match(self, dir_, datazoom_, usewidemofr_, mofrs_to_get_):
		return self.direction == dir_ and self.datazoom == datazoom_ and self.usewidemofr == usewidemofr_ \
				and self.mofrs_to_get == mofrs_to_get_

	def __str__(self):
		return 'RawSpeedsInfo(dir=%d,datazoom=%d,time_window=%s,usewidemofr=%s,mofrs_to_get=*%d*)' \
				% (self.direction, self.datazoom, self.time_window, self.usewidemofr, len(self.mofrs_to_get))

	def __repr__(self):
		return self.__str__()

def copy_mofr_to_rawtraffic(mofr_to_rawtraffic_):
	r = {}
	for mofr, rawtraffic in mofr_to_rawtraffic_.iteritems():
		r[mofr] = rawtraffic.copy()
	return r

# This is almost a great way to get all the pertinent bounding vi pairs, 
# except it doesn't handle correctly the case where there are multiple vis in chunk X, 
# no vis in chunk X+1, and the next vi in chunk X+2.  
#def get_all_mofrstep_bounding_vi_pairs(vis_, mofrstep_, dir_):
#	if len(vis_) < 2:
#		return
#	vis = (vis_ if dir_==1 else vis_[::-1])
#	lo_idx = 0; hi_idx = 1
#	while hi_idx < len(vis):
#		lo_vi = vis[lo_idx]; hi_vi = vis[hi_idx]
#		lo_chunk = lo_vi.mofrchunk(mofrstep_); hi_chunk = hi_vi.mofrchunk(mofrstep_)
#		if lo_chunk != hi_chunk:
#			interp_mofr = max(lo_chunk, hi_chunk)*mofrstep_
#			yield (lo_vi, hi_vi, interp_mofr)
#			lo_idx = hi_idx
#			hi_idx += 1
#		else:
#			hi_idx += 1

def get_stretches(vis_, dir_):
	if len(vis_) == 0:
		return []
	cur_stretch = [vis_[0]]
	r = [cur_stretch]
	for vi in vis_[1:]:
		lastvi = cur_stretch[-1]
		if abs(lastvi.time - vi.time) < 1000*60*10:
			if (dir_ and (vi.widemofr >= lastvi.widemofr)) or (not dir_ and (vi.widemofr <= lastvi.widemofr)):
				cur_stretch.append(vi)
		else:
			cur_stretch = [vi]
			r.append(cur_stretch)
	return r

# return a tuple - (headway in millis, time of earlier passing vehicle, time of later passing vehicle)
# 	or None if no headway could be found from the vehicles that passed the stop in the given window-minutes.
# ---------- Probably broken ------------ 
def get_observed_headway(froute_, stoptag_, time_, window_minutes_, usewidemofr_=False, log_=False):
# ---------- Probably broken ------------ 
	stop = routes.routeinfo(froute_).get_stop(stoptag_)
	mofr = stop.mofr
	rawtraffics = get_traffic_rawspeeds(froute_, stop.direction, time_+(window_minutes_*60*1000/2), window_minutes_, usewidemofr_=False,
			singlemofr_=mofr, log_=log_)
	if not rawtraffics:
		return None
	earlier_rawtraffics = [rawtraffic for rawtraffic in rawtraffics if rawtraffic['time'] <= time_]
	later_rawtraffics = [rawtraffic for rawtraffic in rawtraffics if rawtraffic['time'] >= time_]
	if earlier_rawtraffics and later_rawtraffics:
		lo_time = max(earlier_rawtraffics, key=lambda rawtraffic: rawtraffic['time'])['time']
		hi_time = min(later_rawtraffics,   key=lambda rawtraffic: rawtraffic['time'])['time']
		return (hi_time - lo_time, lo_time, hi_time)
	else:
		return None

# [1] Here I am trying to implement the following judgement call:
# It is better to show no traffic at all (white) than a misleading orange
# that is derived from one or more vehicles that never traversed that stretch of road,
# but detoured around it.   This will happen in the case of major incidents involving detours eg.
# dundas westbound 2012-09-24 13:35 (preceeding half-hour thereof).  See how vid 4087 detours around
# ossington and college, how no vehicles traverse westbound dundas between ossington and lansdowne
# between 13:05 and 13:35, and how this could result in vid 4087 single-handedly causing a
# decent-looking traffic report for that stretch of road.  I would rather show white (or whatever
# I'm showing to signify 'no traffic data' now) and thus encourage the user to look for the detour.
def get_bounding_mofr_vis(mofr_, mofrstep_, chunked_vilist_, usewidemofr_):
	assert isinstance(mofr_, int) and isinstance(chunked_vilist_, ChunkedViList) and isinstance(usewidemofr_, bool)

	prev_mofrchunk = mofr_/mofrstep_ - 1
	vi_lo = chunked_vilist_.get_min_vi(prev_mofrchunk)
	if not vi_lo:
		for mofrchunk in xrange(min(prev_mofrchunk-1,chunked_vilist_.max_mofrchunk), chunked_vilist_.min_mofrchunk-1, -1):
			vi_lo = chunked_vilist_.get_max_vi(mofrchunk)
			if vi_lo:
				break

	vi_hi = None
	for mofrchunk in xrange(max(mofr_/mofrstep_,chunked_vilist_.min_mofrchunk), chunked_vilist_.max_mofrchunk+1):
		vi_hi = chunked_vilist_.get_min_vi(mofrchunk)
		if vi_hi:
			break

	if vi_lo and vi_hi:
		assert chunked_vilist_.mofr_time_key(vi_lo) < chunked_vilist_.mofr_time_key(vi_hi)

	if vi_lo and vi_hi and (abs(vi_hi.time - vi_lo.time) > 1000*60*8): # see [1] above.
		return (None, None)
	else:
		return (vi_lo, vi_hi)

class ChunkedViList(object):

	def __init__(self, mofrstep_, usewidemofr_):
		self.mofrstep = mofrstep_

		self.usewidemofr = usewidemofr_
		if self.usewidemofr:
			self.get_mofr = lambda vi__: vi__.widemofr
		else:
			self.get_mofr = lambda vi__: vi__.mofr

		self.mofr_time_key = lambda vi__: (self.get_mofr(vi__), vi__.time)

	@classmethod
	def create(cls_, vis_, mofrstep_, usewidemofr_):
		assert vis_
		assert all(vi1.vehicle_id == vi2.vehicle_id for vi1, vi2 in hopscotch(vis_))
		assert all(vi1.fudgeroute == vi2.fudgeroute for vi1, vi2 in hopscotch(vis_))

		r = cls_(mofrstep_, usewidemofr_)

		r.vis_by_idx = []
		for vi in vis_:
			mofrchunk = r.get_mofrchunk(vi)
			assert mofrchunk >= 0
			while mofrchunk >= len(r.vis_by_idx):
				r.vis_by_idx.append([])
			r.vis_by_idx[mofrchunk].append(vi)
		r.max_mofrchunk = len(r.vis_by_idx)-1
		r.min_mofrchunk = 0
		while len(r.vis_by_idx) > 0 and len(r.vis_by_idx[0]) == 0:
			del r.vis_by_idx[0]
			r.min_mofrchunk += 1

		r.min_vi_by_idx = [None]*(r.max_mofrchunk - r.min_mofrchunk + 1)
		r.max_vi_by_idx = [None]*(r.max_mofrchunk - r.min_mofrchunk + 1)
		for mofrchunk in r.mofrchunks():
			r.calc_minmax(mofrchunk)

		return r

	def copy(self):
		r = self.__class__(self.mofrstep, self.usewidemofr)
		r.vis_by_idx = self.vis_by_idx[:]
		r.min_mofrchunk = self.min_mofrchunk
		r.max_mofrchunk = self.max_mofrchunk
		r.min_vi_by_idx = self.min_vi_by_idx[:]
		r.max_vi_by_idx = self.max_vi_by_idx[:]
		return r

	def influences_traffic_at(self, mofr_):
		if mofr_ % self.mofrstep != 0:  
			return True # The 'getting single mofr' case.  Don't care about optimizing it. 
		else:
			chunk_of_mofr = mofr_/self.mofrstep
			return self.min_mofrchunk < chunk_of_mofr <= self.max_mofrchunk 
	
	def mofrchunks(self):
		return xrange(self.min_mofrchunk, self.max_mofrchunk+1)

	def calc_minmax(self, mofrchunk_):
		vis = self.get_vis(mofrchunk_)
		if vis:
			min_vi, max_vi = minmax(vis, key=self.mofr_time_key)
		else:
			min_vi, max_vi = (None, None)
		idx = self._idx(mofrchunk_)
		self.min_vi_by_idx[idx], self.max_vi_by_idx[idx] = min_vi, max_vi

	def add_new_vis(self, new_vis_):
		new_vis_mofrchunks = set()
		for new_vi in new_vis_:
			new_vi_mofrchunk = self.get_mofrchunk(new_vi)
			new_vis_mofrchunks.add(new_vi_mofrchunk)
			while new_vi_mofrchunk < self.min_mofrchunk:
				self.vis_by_idx.insert(0, [])
				self.min_vi_by_idx.insert(0, None)
				self.max_vi_by_idx.insert(0, None)
				self.min_mofrchunk -= 1
			while new_vi_mofrchunk > self.max_mofrchunk:
				self.vis_by_idx.append([])
				self.min_vi_by_idx.append(None)
				self.max_vi_by_idx.append(None)
				self.max_mofrchunk += 1
			self.get_vis(new_vi_mofrchunk).append(new_vi)
		for new_vi_mofrchunk in new_vis_mofrchunks:
			self.calc_minmax(new_vi_mofrchunk)

	def remove_old_vis(self, old_vis_):
		old_vi_times = set(vi.time for vi in old_vis_)

		affected_mofrchunks = set()
		for mofrchunk in self.mofrchunks():
			vis = self.get_vis(mofrchunk)
			old_len = len(vis)
			vis[:] = [vi for vi in vis if vi.time not in old_vi_times]
			if len(vis) != old_len:
				affected_mofrchunks.add(mofrchunk)

		while len(self.vis_by_idx) > 0 and len(self.vis_by_idx[0]) == 0:
			del self.vis_by_idx[0]
			del self.min_vi_by_idx[0]
			del self.max_vi_by_idx[0]
			self.min_mofrchunk += 1

		while len(self.vis_by_idx) > 0 and len(self.vis_by_idx[-1]) == 0:
			del self.vis_by_idx[-1]
			del self.min_vi_by_idx[-1]
			del self.max_vi_by_idx[-1]
			self.max_mofrchunk -= 1

		assert len(self.vis_by_idx) > 0 # We don't support an empty ChunkedViList.  Assuming some new vis were already added.

		mofrchunks = self.mofrchunks()
		for affected_mofrchunk in (x for x in affected_mofrchunks if x in mofrchunks):
			self.calc_minmax(affected_mofrchunk)

	def get_influenced_traffic_mofrs(self, vis_):
		r = set()
		for vi in vis_:
			vi_mofrchunk = self.get_mofrchunk(vi)
			r.add(vi_mofrchunk*self.mofrstep)
			all_mofrchunks = set(self.mofrchunks())
			for mofrchunk in xrange(vi_mofrchunk+1, self.max_mofrchunk+1):
				r.add(mofrchunk*self.mofrstep)
				if mofrchunk in all_mofrchunks and len(self.get_vis(mofrchunk)) > 0:
					break
			for mofrchunk in xrange(vi_mofrchunk-1, self.min_mofrchunk-1, -1):
				if mofrchunk in all_mofrchunks and len(self.get_vis(mofrchunk)) > 0:
					break
				else:
					r.add(mofrchunk*self.mofrstep)
		return r

	def _idx(self, mofrchunk_):
		return mofrchunk_ - self.min_mofrchunk

	def get_vis(self, mofrchunk_):
		return self.vis_by_idx[self._idx(mofrchunk_)]

	def get_mofrchunk(self, vi_):
		return int(self.get_mofr(vi_))/self.mofrstep

	def get_min_vi(self, mofrchunk_):
		if self.min_mofrchunk <= mofrchunk_ <= self.max_mofrchunk:
			return self.min_vi_by_idx[self._idx(mofrchunk_)]
		else:
			return None

	def get_max_vi(self, mofrchunk_):
		if self.min_mofrchunk <= mofrchunk_ <= self.max_mofrchunk:
			return self.max_vi_by_idx[self._idx(mofrchunk_)]
		else:
			return None

# return -1 if one or more parts of the route have no traffic data.
# otherwise - return value is in seconds.
def get_est_riding_time_secs(froute_, start_mofr_, dest_mofr_, current_, time_):
	assert all(0 <= mofr <= routes.routeinfo(froute_).max_mofr() for mofr in (start_mofr_, dest_mofr_))
	mofrstep = c.DATAZOOM_TO_MOFRSTEP[MAX_DATAZOOM]
	if mofrs_to_dir(start_mofr_, dest_mofr_) == 0:
		startmofr = start_mofr_
		destmofr = dest_mofr_
	else:
		startmofr = dest_mofr_
		destmofr = start_mofr_
	mofr_to_kmph = get_mofr_to_kmph(froute_, mofrs_to_dir(startmofr, destmofr), current_, time_)
	r_secs = 0
	if startmofr != round_up_off_step(startmofr, mofrstep):
		dist_m = round_up_off_step(startmofr, mofrstep) - startmofr
		speed_kmph = mofr_to_kmph[roundbystep(startmofr, mofrstep)]
		if speed_kmph is None:
			return None
		speed_mps = kmph_to_mps(speed_kmph)
		r_secs += dist_m/speed_mps
	cur_offstep_mofr = round_up_off_step(startmofr, mofrstep)
	while cur_offstep_mofr < round_down_off_step(destmofr, mofrstep):
		mofr_with_ref_speed = round_up(cur_offstep_mofr, mofrstep)
		speed_kmph = mofr_to_kmph[mofr_with_ref_speed]
		if speed_kmph is None:
			return None
		speed_mps = kmph_to_mps(speed_kmph)
		r_secs += mofrstep/speed_mps
		cur_offstep_mofr += mofrstep
	if destmofr != round_down_off_step(destmofr, mofrstep):
		dist_m = destmofr - round_down_off_step(destmofr, mofrstep)
		speed_kmph = mofr_to_kmph[roundbystep(destmofr, mofrstep)]
		if speed_kmph is None:
			return None
		speed_mps = kmph_to_mps(speed_kmph)
		r_secs += dist_m/speed_mps
	return r_secs


if __name__ == '__main__':

	pass 

