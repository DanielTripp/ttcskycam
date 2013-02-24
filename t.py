#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c

def t(orig_latlng_, dest_latlng_):
	return paths.get_path_froutendirs_by_pathgridsquare_near_bounding_box_latlngs(paths.PathGridSquare(orig_latlng_), paths.PathGridSquare(dest_latlng_))

if __name__ == '__main__':

	key = 'dev-paths.get_paths_by_latlngs((43.649391,-79.424465),(43.665111,-79.404638))'
	print mc.g_memcache_client.get(key)

