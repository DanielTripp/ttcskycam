#!/usr/bin/python2.6

from collections import defaultdict
import pprint
import math
import geom
from misc import *

LATSTEP = 0.00175; LNGSTEP = 0.0025

# Grid squares are offset from a point that has no large importance, it just makes for more easily
# readable values during debugging:
LATREF = 43.62696696859263; LNGREF = -79.4579391022553

def lat_to_gridlat(lat_):
	return fdiv(lat_ - LATREF, LATSTEP)

def gridlat_to_lat(gridlat_):
	return gridlat_*LATSTEP + LATREF

def lng_to_gridlng(lng_):
	return fdiv(lng_ - LNGREF, LNGSTEP)

def gridlng_to_lng(gridlng_):
	return gridlng_*LNGSTEP + LNGREF

class GridSquare(object):

	def __init__(self, arg_):
		if isinstance(arg_, geom.LatLng):
			self.gridlat = lat_to_gridlat(arg_.lat)
			self.gridlng = lng_to_gridlng(arg_.lng)
		else:
			self.gridlat = arg_[0]
			self.gridlng = arg_[1]

	def __eq__(self, other):
		return (self.gridlat == other.gridlat) and (self.gridlng == other.gridlng)

	def __hash__(self):
		return self.gridlat + self.gridlng

	def __str__(self):
		return '(%d,%d)' % (self.gridlat, self.gridlng)

	def __repr__(self):
		return self.__str__()

	def latlng(self):
		return geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))

class LineSegAddr(object):

	def __init__(self, polylineidx_, startptidx_):
		self.polylineidx = polylineidx_
		self.startptidx = startptidx_

	def __eq__(self, other):
		return (self.polylineidx == other.polylineidx) and (self.startptidx == other.startptidx)

	def __hash__(self):
		return self.polylineidx + self.startptidx

	def __str__(self):
		return 'LineSegAddr(%d,%d)' % (self.polylineidx, self.startptidx)

	def __repr__(self):
		return self.__str__()

class LineSeg(object):

	def __init__(self, start_, end_):
		assert isinstance(start_, geom.LatLng) and isinstance(end_, geom.LatLng)
		self.start = start_
		self.end = end_

	def __str__(self):
		return '[%s -> %s]' % (self.start, self.end)

	def __repr__(self):
		return self.__str__()

# This can be pickled i.e. memcached. 
class SnapToGridCache(object):

	def __init__(self, polylines_):
		assert isinstance(polylines_[0][0], geom.LatLng)
		self.latstep = LATSTEP; self.lngstep = LNGSTEP
		self.polylines = polylines_
		self.gridsquare_to_linesegaddrs = defaultdict(lambda: set()) # key: GridSquare.  value: set of LineSegAddr
		for polylineidx, polyline in enumerate(self.polylines):
			for startptidx in range(0, len(polyline)-1):
				linesegstartgridsquare = GridSquare(polyline[startptidx])
				linesegendgridsquare = GridSquare(polyline[startptidx+1])
				linesegaddr = LineSegAddr(polylineidx, startptidx)
				# TODO: be more specific in the grid squares considered touched by a line.  We are covering a whole bounding box.
				# we could narrow down that set of squares a lot.
				for gridlat in intervalii(linesegstartgridsquare.gridlat, linesegendgridsquare.gridlat):
					for gridlng in intervalii(linesegstartgridsquare.gridlng, linesegendgridsquare.gridlng):
						gridsquare = GridSquare((gridlat, gridlng))
						self.gridsquare_to_linesegaddrs[gridsquare].add(linesegaddr)
		self.gridsquare_to_linesegaddrs = dict(self.gridsquare_to_linesegaddrs) # b/c a defaultdict can't be pickled i.e. memcached

	def get_lineseg(self, linesegaddr_):
		polyline = self.polylines[linesegaddr_.polylineidx]
		return LineSeg(polyline[linesegaddr_.startptidx], polyline[linesegaddr_.startptidx+1])

	def get_point(self, linesegaddr_):
		return self.polylines[linesegaddr_.polylineidx][linesegaddr_.startptidx]

	# arg searchradius_ is in metres.
	#
	# returns None, or a tuple - (geom.LatLng, LineSegAddr, bool)
	# if None: no line was found within the search radius.
	# if tuple:
	#	elem 0: snapped-to point.  geom.LatLng.
	# 	elem 1: reference line segment address (or point address) that the snapped-to point is on.
	#	elem 2: 'snapped-to point is along a line' flag.
	#			if True: then interpret elem 1 as the address of a line segment (not a point).  The snapped-to point
	# 				(i.e. elem 0) is somewhere along that line segment.
	# 			if False: then intepret elem 1 as the address of a point (not a line) - and the snapped-to point (elem 0)
	# 				is exactly the point referenced by elem 1.
	def snap(self, target_, searchradius_):
		assert isinstance(target_, geom.LatLng) and isinstance(searchradius_, int)
		# Guarding against changes in LATSTEP/LNGSTEP while a SnapToGridCache object was sitting in memcached:
		assert self.latstep == LATSTEP and self.lngstep == LNGSTEP
		best_yet_snapresult = None; best_yet_linesegaddr = None
		for linesegaddr in self.get_nearby_linesegaddrs(target_, searchradius_):
			lineseg = self.get_lineseg(linesegaddr)
			cur_snapresult = snap_to_line(target_, lineseg)
			if best_yet_snapresult==None or cur_snapresult[2]<best_yet_snapresult[2]:
				best_yet_snapresult = cur_snapresult
				best_yet_linesegaddr = linesegaddr
		if best_yet_snapresult == None or best_yet_snapresult[2] > searchradius_:
			return None
		else:
			if best_yet_snapresult[1] == None:
				return (best_yet_snapresult[0], best_yet_linesegaddr, True)
			else:
				if best_yet_snapresult[1] == 0:
					reference_point_addr = best_yet_linesegaddr
				else:
					reference_point_addr = LineSegAddr(best_yet_linesegaddr.polylineidx, best_yet_linesegaddr.startptidx+1)
				return (self.get_point(reference_point_addr).clone(), reference_point_addr, False)

	def heading(self, linesegaddr_, referencing_lineseg_aot_point_):
		assert isinstance(linesegaddr_, LineSegAddr)
		# TODO: do something fancier on corners i.e. when referencing_lineseg_aot_point_ is True.
		assert (0 <= linesegaddr_.polylineidx < len(self.polylines))
		if referencing_lineseg_aot_point_:
			assert 0 <= linesegaddr_.startptidx < len(self.polylines[linesegaddr_.polylineidx])-1
		else:
			assert 0 <= linesegaddr_.startptidx < len(self.polylines[linesegaddr_.polylineidx])
		startptidx = linesegaddr_.startptidx
		if linesegaddr_.startptidx == len(self.polylines[linesegaddr_.polylineidx])-1:
			assert not referencing_lineseg_aot_point_
			startptidx -= 1
		linesegaddr = LineSegAddr(linesegaddr_.polylineidx, startptidx)
		lineseg = self.get_lineseg(linesegaddr)
		return lineseg.start.heading(lineseg.end)

	def get_nearby_linesegaddrs(self, target_, searchradius_):
		assert isinstance(target_, geom.LatLng)
		target_gridsquare = GridSquare(target_)
		r = set()
		reach = get_reach(target_, searchradius_)
		for gridlat in intervalii(target_gridsquare.gridlat-reach[0], target_gridsquare.gridlat+reach[0]):
			for gridlng in intervalii(target_gridsquare.gridlng-reach[1], target_gridsquare.gridlng+reach[1]):
				searching_gridsquare = GridSquare((gridlat, gridlng))
				if searching_gridsquare in self.gridsquare_to_linesegaddrs:
					r |= self.gridsquare_to_linesegaddrs[searching_gridsquare]
		if 0: # debugging
			printerr(len(r), target_)
			l = []
			for linesegaddr in r:
				print linesegaddr
				lineseg = self.get_lineseg(linesegaddr)
				l.append([lineseg.start.lat, lineseg.start.lng])
				l.append([lineseg.end.lat, lineseg.end.lng])
			import json
			printerr(json.dumps(l, indent=0))
		return r

def get_reach(target_, searchradius_):
	assert isinstance(target_, geom.LatLng) and isinstance(searchradius_, int)
	target_gridsquare = GridSquare(target_)
	lat_reach = get_reach_single(target_gridsquare, searchradius_, True)
	lon_reach_top = get_reach_single(GridSquare((target_gridsquare.gridlat+lat_reach+1, target_gridsquare.gridlng)), searchradius_, False)
	lon_reach_bottom = get_reach_single(GridSquare((target_gridsquare.gridlat-lat_reach, target_gridsquare.gridlng)), searchradius_, False)
	return (lat_reach, max(lon_reach_top, lon_reach_bottom))

def get_reach_single(reference_gridsquare_, searchradius_, lat_aot_lng_):
	assert isinstance(reference_gridsquare_, GridSquare) and isinstance(searchradius_, int) and isinstance(lat_aot_lng_, bool)
	reference_gridsquare_latlng = reference_gridsquare_.latlng()
	r = 1
	while True:
		if lat_aot_lng_:
			cur_latlng = geom.LatLng(reference_gridsquare_latlng.lat + r*LATSTEP, reference_gridsquare_latlng.lng)
		else:
			cur_latlng = geom.LatLng(reference_gridsquare_latlng.lat, reference_gridsquare_latlng.lng + r*LNGSTEP)
		if cur_latlng.dist_m(reference_gridsquare_latlng) >= searchradius_:
			return r
		r += 1

def steps_satisfy_searchradius(target_, searchradius_):
	assert isinstance(target_, geom.LatLng) and isinstance(searchradius_, int)
	ref_gridsquare = GridSquare(target_)
	ref_gridsquare.gridlat += 2
	if ref_gridsquare.latlng().dist_m(GridSquare((ref_gridsquare.gridlat+1, ref_gridsquare.gridlng)).latlng()) < searchradius_:
		return False
	if ref_gridsquare.latlng().dist_m(GridSquare((ref_gridsquare.gridlat, ref_gridsquare.gridlng+1)).latlng()) < searchradius_:
		return False
	return True

# returns a tuple - (snapped point, 0|1|None, dist)
# 0 if the first point of the line is the snapped-to point, 1 if the second, None if neither.
def snap_to_line(target_, lineseg_):
	assert isinstance(target_, geom.LatLng) and isinstance(lineseg_, LineSeg)
	ang1 = geom.angle(lineseg_.end, lineseg_.start, target_)
	ang2 = geom.angle(lineseg_.start, lineseg_.end, target_)
	if (ang1 < math.pi/2) and (ang2 < math.pi/2):
		snappedpt = geom.get_pass_point(lineseg_.start, lineseg_.end, target_)
		return (snappedpt, None, snappedpt.dist_m(target_))
	else:
		dist0 = target_.dist_m(lineseg_.start); dist1 = target_.dist_m(lineseg_.end)
		if dist0 < dist1:
			return (lineseg_.start, 0, dist0)
		else:
			return (lineseg_.end, 1, dist1)

# A list of line segments.  Line segments points are geom.LatLng.
def get_display_grid(southwest_latlng_, northeast_latlng_):
	assert isinstance(southwest_latlng_, geom.LatLng) and isinstance(northeast_latlng_, geom.LatLng)
	southwest_gridsquare = GridSquare(southwest_latlng_)
	northeast_gridsquare = GridSquare(northeast_latlng_)
	northeast_gridsquare.gridlat += 1; northeast_gridsquare.gridlng += 1
	r = []
	for gridlat in range(southwest_gridsquare.gridlat, northeast_gridsquare.gridlat+1):
		for gridlng in range(southwest_gridsquare.gridlng, northeast_gridsquare.gridlng+1):
			r.append([GridSquare((gridlat, gridlng)).latlng(), GridSquare((gridlat, gridlng+1)).latlng()])
			r.append([GridSquare((gridlat, gridlng)).latlng(), GridSquare((gridlat+1, gridlng)).latlng()])
	return r

if __name__ == '__main__':

	start = geom.LatLng(43.659854903367034, -79.43536563118596)
	end = start.clone()
	while start.dist_m(end) < 1000:
		end.lat += 0.0000001
	print end.lat - start.lat





