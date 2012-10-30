#!/usr/bin/python2.6

import datetime, calendar, math
from math import *
import vinfo, routes
from misc import *

class LatLng:

	def __init__(self, lat_, lng_=None):
		if type(lat_) == float:
			latlng = (lat_, lng_)
		else:
			assert lng_==None
			latlng = lat_
		assert len(latlng) == 2 and type(latlng[0]) == float and type(latlng[1]) == float
		self.lat = latlng[0]
		self.lng = latlng[1]

	def clone(self):
		return LatLng(self.lat, self.lng)

	# returns: meters. float.
	def dist_m(self, other_):
		assert isinstance(other_, LatLng)
		# 'Haversine formula' from http://en.wikipedia.org/wiki/Great-circle_distance
		lat1 = radians(self.lat); lng1 = radians(self.lng)
		lat2 = radians(other_.lat); lng2 = radians(other_.lng)
		dlat = lat2 - lat1
		dlng = lng2 - lng1
		central_angle = 2*asin(sqrt(sin(dlat/2)**2 + cos(lat1)*cos(lat2)*(sin(dlng/2)**2)))
		RADIUS_OF_EARTH = 6367.44465
		return central_angle*RADIUS_OF_EARTH*1000

	def add(self, other_):
		assert isinstance(other_, LatLng)
		return LatLng(self.lat+other_.lat, self.lng+other_.lng)

	def subtract(self, other_):
		return LatLng(self.lat - other_.lat, self.lng - other_.lng)

	def scale(self, factor_):
		assert isinstance(factor_, float)
		return LatLng(self.lat*factor_, self.lng*factor_)

	# Returns 'absolute angle' between two points (measured counter-clockwise from the positive X axis)
	# Returns between -pi and +pi.
	def abs_angle(self, other_):
		assert isinstance(other_, LatLng)
		opposite = LatLng(self.lat, other_.lng).dist_m(LatLng(other_.lat, other_.lng))
		adjacent = LatLng(self.lat, other_.lng).dist_m(LatLng(self.lat, self.lng))
		r = math.atan2(opposite, adjacent)
		latdiff = other_.lat - self.lat; londiff = other_.lng - self.lng
		if londiff > 0 and latdiff > 0: # first quadrant 
			pass
		elif londiff <= 0 and latdiff > 0: # second quadrant 
			r = math.pi - r
		elif londiff <= 0 and latdiff <= 0: # third quadrant 
			r = -math.pi + r
		else: # fourth quadrant 
			r = -r
		return r

	def heading(self, other_):
		ang = math.degrees(self.abs_angle(other_))
		if ang > 90:
			heading = get_range_val((90, 360), (180, 270), ang)
		else:
			heading = get_range_val((0, 90), (90, 0), ang)
		return int(heading)

	def inside_polygon(self, poly_):
		assert all(isinstance(x, LatLng) for x in poly_)
		sum_angles = 0
		for polypt1, polypt2 in hopscotch(poly_ + [poly_[0]]):
			sum_angles += angle(polypt1, self, polypt2)
		return (2*math.pi - sum_angles) < 0.0001

	def __eq__(self, other_):
		assert isinstance(other_, LatLng)
		return self.lat == other_.lat and self.lng == other_.lng

	def __str__(self):
		return '(%.6f, %.6f)' % (self.lat, self.lng)

	def __repr__(self):
		return self.__str__()


def get_range_val(p1_, p2_, domain_val_):
	x1 = float(p1_[0]); y1 = float(p1_[1])
	x2 = float(p2_[0]); y2 = float(p2_[1])
	r = (y2 - y1)*(domain_val_ - x1)/(x2 - x1) + y1
	if any(type(x) == float for x in p1_ + p2_ + (domain_val_,)):
		return r
	else:
		return int(r)

def avg(lo_, hi_, ratio_):
	r = lo_ + (hi_ - lo_)*ratio_
	if type(lo_) == int and type(hi_) == int:
		return int(r)
	elif type(lo_) == long or type(hi_) == long:
		return long(r)
	else:
		return r

def round_down_by_minute(t_em_):
	dt = datetime.datetime.utcfromtimestamp(t_em_/1000.0)
	dt = datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute)
	r = long(calendar.timegm(dt.timetuple())*1000)
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

# Takes a flat list of VehicleInfo objects.  Returns a list of lists of Vehicleinfo objects, interpolated. 
# Also, with a date/time string as element 0 in each list.
def interp_by_time(vilist_, try_for_mofr_based_loc_interp_, current_conditions_, dir_=None, end_time_=None):
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
				if (min(interptime - lo_vi.time, hi_vi.time - interptime) > 3*60*1000) or dirs_disagree(dir_, hi_vi.dir_tag_int) \
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
	fill_in_blank_headings(time_to_vis)
	return massage_to_list(time_to_vis)

def fill_in_blank_headings(r_time_to_vis_):
	times = sorted(r_time_to_vis_.keys())
	for timei, time in enumerate(times):
		if timei==0:
			continue
		for target_vi in r_time_to_vis_[time]:
			if target_vi.heading == -4: # -4 means blank, or at least that's what nextbus seems to mean by it. 
				# Now look back in time for a previous appearance of this vid which indicates a direction by change of by mofr, then 
				# get a heading from our static route info based on that direction. 
				if target_vi.mofr != -1:
					prev_vi = None
					for timej in range(timei-1, -1, -1):
						if prev_vi != None:
							break
						for older_vi in r_time_to_vis_[times[timej]]:
							if (older_vi.vehicle_id == target_vi.vehicle_id) and (older_vi.mofr != -1) \
									and (older_vi.fudgeroute == target_vi.fudgeroute) \
									and (abs(target_vi.mofr - older_vi.mofr) >= 5):
								prev_vi = older_vi
								break
					if prev_vi != None:
						dir = (0 if prev_vi.mofr < target_vi.mofr else 1)
						target_vi.heading = routes.get_routeinfo(target_vi.route_tag).mofr_to_heading(target_vi.mofr, dir)
			if target_vi.heading == -4: # If the above didn't work out then try again using lat/lons instead of mofrs. 
				prev_vi = None
				for timej in range(timei-1, -1, -1):
					if prev_vi != None:
						break
					for older_vi in r_time_to_vis_[times[timej]]:
						if (older_vi.vehicle_id == target_vi.vehicle_id) and (older_vi.latlng.dist_m(target_vi.latlng) >= 10):
							prev_vi = older_vi
							break
				if prev_vi != None:
					target_vi.heading = prev_vi.latlng.heading(target_vi.latlng)

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
				interp_mofr = avg(vi1mofr, vi2mofr, ratio_)
				dir_tag_int = vi2_.dir_tag_int
				if dir_tag_int == None:
					raise Exception('Could not determine dir_tag_int of %s' % (str(vi2_)))
				r = routes.mofr_to_latlonnheading(config_route, interp_mofr, dir_tag_int)
	if r==None:
		r = (LatLng(*(avg(vi1_.latlng.lat, vi2_.latlng.lat, ratio_), avg(vi1_.latlng.lng, vi2_.latlng.lng, ratio_))),
				avg_headings(vi1_.heading, vi2_.heading, ratio_))
	return r

def avg_headings(heading1_, heading2_, ratio_):
	if heading1_==-4 or heading2_==-4:
		return -4
	else:
		return avg(heading1_, heading2_, ratio_)

def angle(arm1_, origin_, arm2_):
	assert isinstance(arm1_, LatLng) and isinstance(origin_, LatLng) and isinstance(arm2_, LatLng)
	abs_ang1 = origin_.abs_angle(arm1_)
	abs_ang2 = origin_.abs_angle(arm2_)
	r = abs(abs_ang2 - abs_ang1)
	if r > math.pi:
		r = abs(r - 2*math.pi)
	elif r < -math.pi:
		r = r + 2*math.pi
	return r

def passes(standpt_, forept_, post_, tolerance_=0):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)

	if standpt_ == forept_:
		return False
	ang1 = angle(forept_, standpt_, post_)
	ang2 = angle(standpt_, forept_, post_)
	r = all(x < math.pi/2 for x in (ang1, ang2))
	if r:
		passpt = get_pass_point(standpt_, forept_, post_)
		# There is no precise meaning behind the numbers below.
		r = (passpt.dist_m(post_) < {0:35, 1:175, 2:415}[tolerance_])
	return r

def get_pass_point(standpt_, forept_, post_):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)
	ratio = get_pass_ratio(standpt_, forept_, post_)
	r = standpt_.add(forept_.subtract(standpt_).scale(ratio))
	return r

def get_pass_ratio(standpt_, forept_, post_):
	assert isinstance(standpt_, LatLng) and isinstance(forept_, LatLng) and isinstance(post_, LatLng)
	ang = angle(post_, standpt_, forept_)
	hypot = standpt_.dist_m(post_)
	adjacent = hypot*math.cos(ang)
	return adjacent/forept_.dist_m(standpt_)

def get_passing_vehicles(vilist_, dest_):
	r = []
	vids = set(vi.vehicle_id for vi in vilist_)
	for vid in vids:
		vid_visublist = sorted([vi for vi in vilist_ if vi.vehicle_id == vid], key=lambda vi: vi.time)
		for vis in hopscotch(vid_visublist):
			vpt0 = (vis[0].lat, vis[0].lon)
			vpt1 = (vis[1].lat, vis[1].lon)
			if passes(vpt0, vpt1, dest_):
				r.append(vis)
	return r

def normalize_heading(heading_):
	r = heading_
	while r < 0:
		r += 360
	while r >= 360:
		r -= 360
	return r

def diff_headings(h1_, h2_):
	if h1_ > h2_:
		r = h1_ - h2_
	else:
		r = h2_ - h1_
	return normalize_heading(r)

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

def remove_consecutive_duplicates(list_, key=None):
	def get_key(val_):
		return (val_ if key==None else key(val_))
	curkey = get_key(list_[0]); prevkey = None
	i = 1
	while i < len(list_):
		prevkey = curkey
		curkey = get_key(list_[i])
		if prevkey == curkey:
			del list_[i]
			i -= 1
			curkey = prevkey
		i += 1

def kmph_to_mps(kmph_):
	return kmph_*1000.0/(60*60)

def mps_to_kmph(mps_):
	return mps_*60.0*60/1000;

def is_plausible(dist_m_, speed_kmph_):
	if dist_m_ < 1000:
		return speed_kmph_ < 60
	elif dist_m_ < 5000:
		return speed_kmph_ < 40
	else:
		return speed_kmph_ < 30

def remove_bad_gps_readings_single_vid(vis_):
	assert len(set(vi.vehicle_id for vi in vis_)) == 1
	if not vis_:
		return []
	vis = vis_[:]
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

		vigroup = min(vigroups, key=get_dist_from_vigroup)
		if is_plausible_vigroup(vigroup):
			vigroup.append(cur_vi)
		else:
			vigroups.append([cur_vi])
	vis_[:] = max(vigroups, key=len)

if __name__ == '__main__':

	#print LatLng(43.65094370994158, -79.41905780037541)
	print LatLng(43.65094, -79.41906).dist_m(LatLng(43.650941, -79.419061))



