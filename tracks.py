#!/usr/bin/env python

import os, json
import geom, snapgraph, mc, picklestore
from misc import *
from collections import Sequence
from lru_cache import lru_cache

@lru_cache(1)
@picklestore.decorate
def get_snapgraph():
	return snapgraph.SnapGraph(get_polylines_from_files(), forpaths=True, forpaths_disttolerance=15, name='tracks')

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
	
if __name__ == '__main__':

	pass


