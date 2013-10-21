#!/usr/bin/python2.6

from collections import defaultdict
from itertools import *
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

	def corner_latlngs(self):
		r = []
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng+1)))
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng)))
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng)))
		r.append(geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng+1)))
		return r

	def center_latlng(self):
		sw = geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))
		ne = geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng+1))
		return sw.avg(ne)

	def diagonal_dist_m(self):
		sw = geom.LatLng(gridlat_to_lat(self.gridlat), gridlng_to_lng(self.gridlng))
		ne = geom.LatLng(gridlat_to_lat(self.gridlat+1), gridlng_to_lng(self.gridlng+1))
		return sw.dist_m(ne)

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
		return geom.LineSeg(polyline[linesegaddr_.startptidx], polyline[linesegaddr_.startptidx+1])

	def get_point(self, linesegaddr_):
		return self.polylines[linesegaddr_.polylineidx][linesegaddr_.startptidx]

	# arg searchradius_ is in metres.  None means unlimited i.e. keep looking forever.  
	# As long as this object contains some lines, something will be found and returned.  Probably quickly, too. 
	# The word 'forever' is misleading. 
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
		assert isinstance(target_, geom.LatLng) and (isinstance(searchradius_, int) or searchradius_ is None)
		# Guarding against changes in LATSTEP/LNGSTEP while a SnapToGridCache object was sitting in memcached:
		assert self.latstep == LATSTEP and self.lngstep == LNGSTEP
		target_gridsquare = GridSquare(target_)
		a_nearby_linesegaddr = self.get_a_nearby_linesegaddr(target_gridsquare, searchradius_)
		if a_nearby_linesegaddr is None:
			return None
		a_nearby_lineseg = self.get_lineseg(a_nearby_linesegaddr)
		endgame_search_radius = self._snap_get_endgame_search_radius(a_nearby_lineseg, target_gridsquare)
		best_yet_snapresult = None; best_yet_linesegaddr = None
		for linesegaddr in self._snap_get_endgame_linesegaddrs(target_gridsquare, endgame_search_radius):
			lineseg = self.get_lineseg(linesegaddr)
			cur_snapresult = target_.snap_to_lineseg(lineseg)
			if best_yet_snapresult==None or cur_snapresult[2]<best_yet_snapresult[2]:
				best_yet_snapresult = cur_snapresult
				best_yet_linesegaddr = linesegaddr
		if (best_yet_snapresult == None) or (searchradius_ is not None and best_yet_snapresult[2] > searchradius_):
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

	def _snap_get_endgame_linesegaddrs(self, target_gridsquare_, search_radius_):
		assert isinstance(target_gridsquare_, GridSquare)
		r = set()
		for linesegaddr in self.nearby_linesegaddrs_gen(target_gridsquare_, search_radius_):
			r.add(linesegaddr)
		return r

	def _snap_get_endgame_search_radius(self, a_nearby_lineseg_, target_gridsquare_):
		assert isinstance(a_nearby_lineseg_, geom.LineSeg) and isinstance(target_gridsquare_, GridSquare)
		r = max(snap_result[2] for snap_result in [latlng.snap_to_lineseg(a_nearby_lineseg_) for latlng in target_gridsquare_.corner_latlngs()])
		return int(r)

	def heading(self, linesegaddr_, referencing_lineseg_aot_point_):
		assert isinstance(linesegaddr_, LineSegAddr)
		# TODO: do something fancier on corners i.e. when referencing_lineseg_aot_point_ is False.
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

	# Return a linesegaddr, any linesegaddr.  It will probably be one nearby, but definitely not guaranteed to be the closest. 
	def get_a_nearby_linesegaddr(self, gridsquare_, searchradius_):
		for linesegaddr in self.nearby_linesegaddrs_gen(gridsquare_, searchradius_):
			return linesegaddr
		return None

	def nearby_linesegaddrs_gen(self, gridsquare_, searchradius_):
		assert isinstance(gridsquare_, GridSquare)
		for gridsquare in gridsquare_spiral_gen_by_geom_vals(gridsquare_, searchradius_):
			if gridsquare in self.gridsquare_to_linesegaddrs:
				for linesegaddr in self.gridsquare_to_linesegaddrs[gridsquare]:
					yield linesegaddr

# arg searchradius_ None means unlimited. 
def get_reach(target_gridsquare_, searchradius_):
	assert isinstance(target_gridsquare_, GridSquare)
	if searchradius_ is None:
		return (None, None)
	else:
		lat_reach = get_reach_single(target_gridsquare_, searchradius_, True)
		lon_reach_top = get_reach_single(GridSquare((target_gridsquare_.gridlat+lat_reach+1, target_gridsquare_.gridlng)), searchradius_, False)
		lon_reach_bottom = get_reach_single(GridSquare((target_gridsquare_.gridlat-lat_reach, target_gridsquare_.gridlng)), searchradius_, False)
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

# yields a 2-tuple of integer offsets - that is, lat/lng offsets eg. (0,0), (1,0), (1,1), (-1, 1), etc.
def gridsquare_offset_spiral_gen(latreach_, lngreach_):
	assert (isinstance(latreach_, int) and isinstance(lngreach_, int)) or (latreach_ is None and lngreach_ is None)

	unlimited = (latreach_ is None)

	def offsets_for_square_spiral_gen(square_reach_):
		r = [0, 0]
		yield r
		for spiralidx in (count() if unlimited else range(square_reach_+2)):
			for i in range(spiralidx*2 + 1): # north 
				r[0] += 1
				yield r
			for i in range(spiralidx*2 + 1): # east 
				r[1] += 1
				yield r
			for i in range(spiralidx*2 + 2): # south
				r[0] -= 1
				yield r
			for i in range(spiralidx*2 + 2): # west
				r[1] -= 1
				yield r

	# Note that max(None,None) == None
	for offsetlat, offsetlng in offsets_for_square_spiral_gen(max(latreach_, lngreach_)):
		if unlimited or (abs(offsetlat) <= latreach_ and abs(offsetlng) <= lngreach_):
			yield (offsetlat, offsetlng)


# reach args - None means unlimited.
def gridsquare_spiral_gen_by_grid_vals(center_gridsquare_, latreach_, lngreach_):
	assert isinstance(center_gridsquare_, GridSquare)
	assert (latreach_ is None) == (lngreach_ is None)
	for offsetlat, offsetlng in gridsquare_offset_spiral_gen(latreach_, lngreach_):
		yield GridSquare((center_gridsquare_.gridlat + offsetlat, center_gridsquare_.gridlng + offsetlng))

# arg searchradius_ meters or None for unlimited. 
def gridsquare_spiral_gen_by_geom_vals(center_gridsquare_, searchradius_):
	latreach, lngreach = get_reach(center_gridsquare_, searchradius_)
	for gridsquare in gridsquare_spiral_gen_by_grid_vals(center_gridsquare_, latreach, lngreach):
		yield gridsquare

if __name__ == '__main__':


	if 0:
		import routes
		gc = routes.routeinfo('dundas').snaptogridcache
		latlng = geom.LatLng(43.6507574, -79.4138221)
		for linesegaddr in gc.get_nearby_linesegaddrs_old(geom.LatLng(43.6507574, -79.4138221), 2000):
			print linesegaddr 

		print 


		for linesegaddr in gc.nearby_linesegaddrs_gen(latlng, 2000):
			print linesegaddr 


	for offsetlat, offsetlng in gridsquare_offset_spiral_gen(3, 2):
		print offsetlat, offsetlng 




