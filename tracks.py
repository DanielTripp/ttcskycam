#!/usr/bin/python2.6

import os, json
import geom, snapgraph, mc
from misc import *
from collections import Sequence
from lru_cache import lru_cache

@mc.decorate
def get_snapgraph():
	return snapgraph.SnapGraph(get_polylines_from_files(), forpaths=False, disttolerance=15)

def get_polylines_from_files():
	r = []
	for track_filename in sorted(f for f in os.listdir('.') if f.startswith('tracks_') and f.endswith('.json')):
		r.append(get_polyline_from_file(track_filename))
	return r

def get_polyline_from_file(filename_):
	try:
		with open(filename_) as track_fin:
			track_file_contents = json.load(track_fin)
			assert isinstance(track_file_contents[0][0], float)
			r = []
			for raw_latlng in track_file_contents:
				assert len(raw_latlng) and isinstance(raw_latlng[0], float) and isinstance(raw_latlng[1], float)
				r.append(geom.LatLng(raw_latlng[0], raw_latlng[1]))
			return r
	except:
		printerr('error with %s' % track_filename)
		raise
	
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
	return get_snapgraph().snap(latlng_, None)

def heading(linesegaddr_, referencing_lineseg_aot_point_):
	return get_snapgraph().heading(linesegaddr_, referencing_lineseg_aot_point_)

def get_all_tracks_polylines():
	return get_snapgraph().polylines

def get_latlng(posaddr_):
	return get_snapgraph().get_latlng(posaddr_)

if __name__ == '__main__':

	print get_all_tracks_polylines()


