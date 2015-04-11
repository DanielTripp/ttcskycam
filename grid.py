#!/usr/bin/python2.6

import datetime, calendar, math, time, random
from math import *
from lru_cache import lru_cache
import geom
from misc import *

DEFAULT_LATSTEP = 0.000875; DEFAULT_LNGSTEP = 0.00125 # implies squares about 100 meters on a side.

# Grid squares are offset from a point that has no large importance, it just makes for more easily
# readable values during debugging:
DEFAULT_LATREF = 43.62696696859263; DEFAULT_LNGREF = -79.4579391022553

class GridSquareSystem(object):
	
	def __init__(self, latref_, lngref_, latstep_, lngstep_, boundingbox_):
		self.latref = (latref_ if latref_ is not None else DEFAULT_LATREF)
		self.lngref = (lngref_ if lngref_ is not None else DEFAULT_LNGREF)
		self.latstep = (latstep_ if latstep_ is not None else DEFAULT_LATSTEP)
		self.lngstep = (lngstep_ if lngstep_ is not None else DEFAULT_LNGSTEP)
		assert all(x > 0 for x in (self.latstep, self.lngstep))
		if boundingbox_ is not None:
			self.southwest_gridsquare = GridSquare.from_latlng(boundingbox_.southwest, self)
			self.northeast_gridsquare = GridSquare.from_latlng(boundingbox_.northeast, self)
		else:
			self.southwest_gridsquare = self.northeast_gridsquare = None

	def has_boundingbox(self):
		assert (self.southwest_gridsquare is None) == (self.northeast_gridsquare is None)
		return (self.southwest_gridsquare is not None)

	def lat_to_gridlat(self, lat_):
		return fdiv(lat_ - self.latref, self.latstep)

	def gridlat_to_lat(self, gridlat_):
		return gridlat_*self.latstep + self.latref

	def lng_to_gridlng(self, lng_):
		return fdiv(lng_ - self.lngref, self.lngstep)

	def gridlng_to_lng(self, gridlng_):
		return gridlng_*self.lngstep + self.lngref

	def num_idxes(self):
		if not self.has_boundingbox():
			raise Exception()
		sw, ne = self.southwest_gridsquare, self.northeast_gridsquare
		return (ne.gridlat - sw.gridlat + 1)*(ne.gridlng - sw.gridlng + 1)
		
	def idx(self, sq_):
		if not self.has_boundingbox():
			raise Exception()
		sw, ne = self.southwest_gridsquare, self.northeast_gridsquare
		if not ((sw.gridlat <= sq_.gridlat <= ne.gridlat) and (sw.gridlng <= sq_.gridlng <= ne.gridlng)):
			return -1
		else:
			numlngcolumns = (ne.gridlng - sw.gridlng + 1)
			latrow = (sq_.gridlat - sw.gridlat)
			r = (sq_.gridlng - sw.gridlng) + latrow*numlngcolumns
			return r

	def gridsquare(self, idx_):
		if not self.has_boundingbox():
			raise Exception()
		if not (0 <= idx_ < self.num_idxes()):
			return None
		else:
			numlngcolumns = (self.northeast_gridsquare.gridlng - self.southwest_gridsquare.gridlng + 1)
			r_gridlat = self.southwest_gridsquare.gridlat + idx_/numlngcolumns
			r_gridlng = self.southwest_gridsquare.gridlng + idx_ % numlngcolumns
			return GridSquare.from_ints(r_gridlat, r_gridlng, self)

	def idxes(self, gridsquares_):
		if not self.has_boundingbox():
			raise Exception()
		for gridsquare in gridsquares_:
			gridsquareidx = self.idx(gridsquare)
			if gridsquareidx != -1:
				yield gridsquareidx

	def rein_in_gridsquare(self, sq_):
		if not self.has_boundingbox():
			raise Exception()
		sq_.gridlat = max(sq_.gridlat, self.southwest_gridsquare.gridlat)
		sq_.gridlat = min(sq_.gridlat, self.northeast_gridsquare.gridlat)
		sq_.gridlng = max(sq_.gridlng, self.southwest_gridsquare.gridlng)
		sq_.gridlng = min(sq_.gridlng, self.northeast_gridsquare.gridlng)

	def is_in_boundingbox(self, latlng_):
		assert isinstance(latlng_, geom.LatLng)
		boundingbox = geom.BoundingBox([self.southwest_gridsquare.sw(), self.northeast_gridsquare.ne()])
		return boundingbox.is_inside(latlng_)

# Supposed to be immutable. 
class GridSquare(object):

	@classmethod
	def from_ints(cls_, gridlat_, gridlng_, sys_):
		assert all(isinstance(x, int) for x in (gridlat_, gridlng_)) and isinstance(sys_, GridSquareSystem)
		r = cls_()
		r.gridlat = gridlat_
		r.gridlng = gridlng_
		r.sys = sys_
		return r

	@classmethod
	def from_latlng(cls_, latlng_, sys_):
		assert isinstance(latlng_, geom.LatLng) and isinstance(sys_, GridSquareSystem)
		r = cls_()
		r.gridlat = sys_.lat_to_gridlat(latlng_.lat)
		r.gridlng = sys_.lng_to_gridlng(latlng_.lng)
		r.sys = sys_
		return r

	def __eq__(self, other):
		return (self.gridlat == other.gridlat) and (self.gridlng == other.gridlng)

	def __hash__(self):
		return self.gridlat + self.gridlng

	def __str__(self):
		return '(%d,%d)' % (self.gridlat, self.gridlng)

	def __repr__(self):
		return self.__str__()

	def latlng(self):
		return geom.LatLng(self.sys.gridlat_to_lat(self.gridlat), self.sys.gridlng_to_lng(self.gridlng))

	def corner_latlngs(self):
		r = []
		r.append(geom.LatLng(self.sys.gridlat_to_lat(self.gridlat+1), self.sys.gridlng_to_lng(self.gridlng+1)))
		r.append(geom.LatLng(self.sys.gridlat_to_lat(self.gridlat+1), self.sys.gridlng_to_lng(self.gridlng)))
		r.append(geom.LatLng(self.sys.gridlat_to_lat(self.gridlat), self.sys.gridlng_to_lng(self.gridlng)))
		r.append(geom.LatLng(self.sys.gridlat_to_lat(self.gridlat), self.sys.gridlng_to_lng(self.gridlng+1)))
		return r

	def corner_latlng(self, which_):
		return self.corner_latlngs()[{'ne': 0, 'nw': 1, 'sw': 2, 'se': 3}[which_]]

	def sw(self):
		return self.corner_latlng('sw')

	def se(self):
		return self.corner_latlng('se')

	def nw(self):
		return self.corner_latlng('nw')

	def ne(self):
		return self.corner_latlng('ne')

	def center_latlng(self):
		sw = geom.LatLng(self.sys.gridlat_to_lat(self.gridlat), self.sys.gridlng_to_lng(self.gridlng))
		ne = geom.LatLng(self.sys.gridlat_to_lat(self.gridlat+1), self.sys.gridlng_to_lng(self.gridlng+1))
		return sw.avg(ne)

	def diagonal_dist_m(self):
		sw = geom.LatLng(self.sys.gridlat_to_lat(self.gridlat), self.sys.gridlng_to_lng(self.gridlng))
		ne = geom.LatLng(self.sys.gridlat_to_lat(self.gridlat+1), self.sys.gridlng_to_lng(self.gridlng+1))
		return sw.dist_m(ne)

	def idx(self):
		return self.sys.idx(self)


if __name__ == '__main__':

	pass



