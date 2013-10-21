#!/usr/bin/python2.6

import os, json
import geom, snaptogrid, mc
from misc import *
from collections import Sequence
from lru_cache import lru_cache

def snaptogridcache():
	return mc.get(snaptogridcache_impl)

def snaptogridcache_impl():
	return snaptogrid.SnapToGridCache(_get_polylines_from_files())

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

# This uses no search radius for the snap.  That is - it is unlimited, and will keep going until a line segment is found, 
# no matter how far away.  This is okay here for a few reasons:
# 
# 1) There are not that very many streetcar tracks in Toronto, therefore we know about all of them, 
# 2) New streetcar tracks are not being built, 
# 3) We're confident that well not be incorrectly identifying something that is not a streetcar as a streetcar. 
# 
# The difference in real-world results between us putting None here as the search radius and us putting 1000 meters 
# is probably nothing. 
@lru_cache(1000)
def snap(latlng_):
	assert isinstance(latlng_, geom.LatLng)
	return snaptogridcache().snap(latlng_, None)

def heading(linesegaddr_, referencing_lineseg_aot_point_):
	return snaptogridcache().heading(linesegaddr_, referencing_lineseg_aot_point_)

def get_all_tracks_polylines():
	return snaptogridcache().polylines

if __name__ == '__main__':

	print is_on_a_track(geom.LatLng(43.66510164255672, -79.4030074616303))

