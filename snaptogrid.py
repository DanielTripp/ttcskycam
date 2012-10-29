#!/usr/bin/python2.6

from collections import defaultdict
import pprint
import math
import geom
from misc import *

LATSTEP = 0.007; LNGSTEP = 0.01

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

class SnapToGridCache(object):

	def __init__(self, polylines_):
		assert isinstance(polylines_[0][0], geom.LatLng)
		self.polylines = polylines_
		self.gridsquare_to_linesegaddrs = defaultdict(lambda: set())
		for polylineidx, polyline in enumerate(self.polylines):
			for startptidx in range(0, len(polyline)-1):
				linesegstartgridsquare = GridSquare(polyline[startptidx])
				linesegendgridsquare = GridSquare(polyline[startptidx+1])
				linesegaddr = LineSegAddr(polylineidx, startptidx)
				# TODO: be more specific in the grid squares considered touched by a line.  We are covering a whole bounding box.
				for gridlat in intervalii(linesegstartgridsquare.gridlat, linesegendgridsquare.gridlat):
					for gridlng in intervalii(linesegstartgridsquare.gridlng, linesegendgridsquare.gridlng):
						gridsquare = GridSquare((gridlat, gridlng))
						self.gridsquare_to_linesegaddrs[gridsquare].add(linesegaddr)

	def get_lineseg(self, linesegaddr_):
		polyline = self.polylines[linesegaddr_.polylineidx]
		return LineSeg(polyline[linesegaddr_.startptidx], polyline[linesegaddr_.startptidx+1])

	# returns a geom.LatLng
	# arg searchradius_ is in metres.
	def snap(self, target_, searchradius_):
		assert isinstance(target_, geom.LatLng) and isinstance(searchradius_, int)
		assert steps_satisfy_searchradius(target_, searchradius_)
		best_yet_snapresult = None; best_yet_linesegaddr = None
		for linesegaddr in self.get_nearby_linesegaddrs(target_):
			lineseg = self.get_lineseg(linesegaddr)
			cur_snapresult = snap_to_line(target_, lineseg)
			if best_yet_snapresult==None or cur_snapresult[2]<best_yet_snapresult[2]:
				best_yet_snapresult = cur_snapresult
				best_yet_linesegaddr = linesegaddr
		if best_yet_snapresult == None or best_yet_snapresult[2] > searchradius_:
			return None
		else:
			if best_yet_snapresult[1] == None:
				return (best_yet_linesegaddr, best_yet_snapresult[0])
			elif best_yet_snapresult[1] == 0:
				return (best_yet_linesegaddr, None)
			else:
				return (LineSegAddr(best_yet_linesegaddr.polylineidx, best_yet_linesegaddr.startptidx+1), None)

	def get_nearby_linesegaddrs(self, target_):
		isinstance(target_, geom.LatLng)
		target_gridsquare = GridSquare(target_)
		r = set()
		for gridlat in intervalii(target_gridsquare.gridlat-1, target_gridsquare.gridlat+1):
			for gridlng in intervalii(target_gridsquare.gridlng-1, target_gridsquare.gridlng+1):
				searching_gridsquare = GridSquare((gridlat, gridlng))
				r |= self.gridsquare_to_linesegaddrs[searching_gridsquare]
		return r

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

if __name__ == '__main__':

	#print GridSquare(geom.LatLng(43.66187293424293, -79.3975142975678)).latlng()
	#sys.exit(1)


	pass


