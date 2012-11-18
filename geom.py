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

	def avg(self, other_, ratio_):
		assert isinstance(other_, LatLng)
		return LatLng(avg(self.lat, other_.lat, ratio_), avg(self.lng, other_.lng, ratio_))

	def inside_polygon(self, poly_):
		assert all(isinstance(x, LatLng) for x in poly_)
		sum_angles = 0
		for polypt1, polypt2 in hopscotch(poly_ + [poly_[0]]):
			sum_angles += angle(polypt1, self, polypt2)
		return (2*math.pi - sum_angles) < 0.0001

	def __eq__(self, other_):
		assert isinstance(other_, LatLng)
		return self.lat == other_.lat and self.lng == other_.lng

	def __hash__(self):
		return int(self.lat*1000 + self.lng*1000)

	def __str__(self):
		return '(%.6f, %.6f)' % (self.lat, self.lng)

	def __repr__(self):
		return self.__str__()

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

def diff_heading(h1_, h2_):
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
	assert len(set(vi.vehicle_id for vi in vis_)) <= 1
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



