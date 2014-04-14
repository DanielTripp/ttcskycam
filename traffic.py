#!/usr/bin/python2.6

from collections import *
from lru_cache import lru_cache
import vinfo, db, routes, geom, mc, yards, c
from misc import *

TIME_WINDOW_MINUTES = 30

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
			if seg_start_latlng.dist_m(seg_end_latlng) > max(2, c.DATAZOOM_TO_RSDT[datazoom_]): 
				# Any smaller and they'll be too small to see. 
				# Using the rsdt there for most cases because 2*rsdt is quite visible when zoomed out.  
				# Using the 2 because the way we generate those route pts results in a lot of ~1 meter segments. 
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

def get_traffic_rawspeeds(fudgeroute_name_, dir_, datazoom_, time_, window_minutes_, usewidemofr_=False, singlemofr_=None, log_=False):
	assert dir_ in (0, 1) and datazoom_ in c.VALID_DATAZOOMS
	mofrstep = c.DATAZOOM_TO_MOFRSTEP[datazoom_]
	mofr_to_rawtraffics = {}
	mofrs_to_get = (range(0, routes.max_mofr(fudgeroute_name_), mofrstep) if singlemofr_ is None else [singlemofr_])
	for mofr in mofrs_to_get:
		mofr_to_rawtraffics[mofr] = []
	for vid, vis_all_stretches in \
				get_vid_to_vis_from_db_for_traffic(fudgeroute_name_, dir_, time_, window_minutes_, usewidemofr_=usewidemofr_, log_=log_).items():
		for vis in get_stretches(vis_all_stretches, dir_):
			if log_: printerr('For vid "%s":' % (vid))
			if log_:
				for vi in vis[::-1]:
					printerr('\traw vinfo: %s' % (str(vi)))
			if len(vis) < 2:
				continue
			def mofr(vi__): return (vi__.widemofr if usewidemofr_ else vi__.mofr)
			assert all(mofr(vi) != -1 for vi in vis)
			mofrchunk_to_vis = get_mofrchunk_to_vis(vis, mofrstep)
			for interp_mofr in mofrs_to_get:
				if log_: printerr('\tFor mofr %d:' % (interp_mofr))
				vi_lo, vi_hi = get_bounding_mofr_vis(interp_mofr, mofrstep, mofrchunk_to_vis, usewidemofr_)
				if vi_lo and vi_hi:
					if log_: printerr('\t\tFound bounding vis at mofrs %d and %d (%s and %s).' % (mofr(vi_lo), mofr(vi_hi), vi_lo.timestr, vi_hi.timestr))
					interp_ratio = (interp_mofr - mofr(vi_lo))/float(mofr(vi_hi) - mofr(vi_lo))
					interp_t = int(vi_lo.time + interp_ratio*(vi_hi.time - vi_lo.time))
					speed_kmph = ((mofr(vi_hi) - mofr(vi_lo))/1000.0)/((vi_hi.time - vi_lo.time)/(1000.0*60*60))
					if log_: printerr('\t\tSpeed: %.1f.  Interpolated time at this mofr: %s' % (speed_kmph, em_to_str_hms(interp_t)))
					# TODO: fix buggy negative speeds a better way, maybe.
					mofr_to_rawtraffics[interp_mofr].append({'speed_kmph': speed_kmph, 'time':interp_t, 'vid': vid})
				else:
					if log_: printerr('\t\tNo bounding vis found for this mofr step / vid.')
	return (mofr_to_rawtraffics if singlemofr_ is None else mofr_to_rawtraffics.values()[0])

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

def get_mofrchunk_to_vis(vis_, mofrstep_):
	r = defaultdict(lambda: [])
	for vi in vis_:
		r[int(vi.widemofr)/mofrstep_].append(vi)
	r = sorteddict(r)
	if __debug__:
		assert all(len(vis) > 0 for vis in r.values())
	return r

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
def get_observed_headway(froute_, stoptag_, time_, window_minutes_, usewidemofr_=False, log_=False):
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

# arg mofrchunk_to_vis_: This might have (or we might put) a key of -1 in it, which might seem to represent 
# mofr==-1, but it's not - the value for -1 is going to be an empty list, and the code is slightly cleaner 
# if we use than rather than having a special case for -1 which amounts to the same thing.
# 
# [1] Here I am trying to implement the following judgement call:
# It is better to show no traffic at all (white) than a misleading orange
# that is derived from one or more vehicles that never traversed that stretch of road,
# but detoured around it.   This will happen in the case of major incidents involving detours eg.
# dundas westbound 2012-09-24 13:35 (preceeding half-hour thereof).  See how vid 4087 detours around
# ossington and college, how no vehicles traverse westbound dundas between ossington and lansdowne
# between 13:05 and 13:35, and how this could result in vid 4087 single-handedly causing a
# decent-looking traffic report for that stretch of road.  I would rather show white (or whatever
# I'm showing to signify 'no traffic data' now) and thus encourage the user to look for the detour.
def get_bounding_mofr_vis(mofr_, mofrstep_, mofrchunk_to_vis_, usewidemofr_):
	assert isinstance(mofr_, int) and isinstance(mofrchunk_to_vis_, sorteddict) and isinstance(usewidemofr_, bool)
	if __debug__:
		all_vis = sum(mofrchunk_to_vis_.values(), [])
		assert all(vi1.vehicle_id == vi2.vehicle_id for vi1, vi2 in hopscotch(all_vis))
		assert all(vi1.fudgeroute == vi2.fudgeroute for vi1, vi2 in hopscotch(all_vis))

	def mofr_time_key(vi__):
		return ((vi__.widemofr if usewidemofr_ else vi__.mofr), vi__.time)

	prev_mofrchunk = mofr_/mofrstep_ - 1
	prev_chunk_vis = (mofrchunk_to_vis_[prev_mofrchunk] if prev_mofrchunk in mofrchunk_to_vis_ else [])
	if len(prev_chunk_vis) > 0:
		vi_lo = min(prev_chunk_vis, key=mofr_time_key)
	else:
		for mofrchunk in (x for x in xrange(mofr_/mofrstep_ - 2, mofrchunk_to_vis_.minkey()-1, -1) if x in mofrchunk_to_vis_):
			vis_in_chunk = mofrchunk_to_vis_[mofrchunk]
			if len(vis_in_chunk) > 0:
				vi_lo = max(vis_in_chunk, key=mofr_time_key)
				break
		else:
			vi_lo = None

	for mofrchunk in (x for x in xrange(mofr_/mofrstep_, mofrchunk_to_vis_.maxkey()+1) if x in mofrchunk_to_vis_):
		vis_in_chunk = mofrchunk_to_vis_[mofrchunk]
		if len(vis_in_chunk) > 0:
			vi_hi = min(vis_in_chunk, key=mofr_time_key)
			break
	else:
		vi_hi = None

	if vi_lo and vi_hi:
		assert mofr_time_key(vi_lo) < mofr_time_key(vi_hi)

	if vi_lo and vi_hi and (abs(vi_hi.time - vi_lo.time) > 1000*60*8): # see [1] above.
		return (None, None)
	else:
		return (vi_lo, vi_hi)

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

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

