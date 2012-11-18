#!/usr/bin/python2.6

import os, json
import geom, snaptogrid
from misc import *
from collections import Sequence

g_snaptogridcache = None

def _init():
	global g_snaptogridcache
	if g_snaptogridcache is None:
		g_snaptogridcache = snaptogrid.SnapToGridCache(_get_polylines_from_files())

def _get_polylines_from_files():
	def get_polyline(polyline_):
		r_e = []
		for raw_latlng in track_file_contents:
			assert len(raw_latlng) and isinstance(raw_latlng[0], float) and isinstance(raw_latlng[1], float)
			r_e.append(geom.LatLng(raw_latlng[0], raw_latlng[1]))
		return r_e

	r = []
	for track_filename in sorted(f for f in os.listdir('.') if f.startswith('tracks_') and f.endswith('.json')):
		with open(track_filename) as track_fin:
			track_file_contents = json.load(track_fin)
			assert isinstance(track_file_contents, Sequence) and isinstance(track_file_contents[0], Sequence)
			if isinstance(track_file_contents[0][0], float):
				r.append(get_polyline(track_file_contents))
			else:
				assert isinstance(track_file_contents[0][0], Sequence)
				for polyline in track_file_contents:
					r.append(get_polyline(polyline))
	return r

def is_on_a_track(latlng_):
	return (snap(latlng_) is not None)

# Default search radius here is the same as tolerance "0" in routes.RouteInfo.latlon_to_mofr().  This may be important.
# Maybe we should maintain a central constant for it somewhere.
def snap(latlng_, searchradius_=50):
	assert isinstance(latlng_, geom.LatLng)
	_init()
	return g_snaptogridcache.snap(latlng_, searchradius_)

def heading(linesegaddr_, referencing_point_aot_lineseg_):
	return g_snaptogridcache.heading(linesegaddr_, referencing_point_aot_lineseg_)

def get_all_tracks_polylines():
	_init()
	return g_snaptogridcache.polylines

if __name__ == '__main__':

	print is_on_a_track(geom.LatLng(43.66510164255672, -79.4030074616303))

