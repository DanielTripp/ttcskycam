#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore, streets

def sg(sgname_):
	if sgname_ == 'streets':
		return streets.get_snapgraph()
	elif sgname_ == 'tracks':
		return tracks.get_snapgraph()
	else:
		raise Exception()

def get_infos_for_box(sgname_, sw_, ne_):
	return sg(sgname_).get_infos_for_box(sw_, ne_)

def get_connected_vert_latlngs(sgname_, vertid_):
	return [vert.pos() for vert in sg(sgname_).get_connected_vertexes(vertid_)]

def find_paths(sgname_, start_latlng_, dest_latlng_):
	dists_n_paths = sg(sgname_).find_paths(start_latlng_, None, dest_latlng_, None)
	paths = [x[1] for x in dists_n_paths]
	return [path.latlngs() for path in paths]

def multisnap(sgname_, latlng_, radius_, reducepts_):
	posaddrs = sg(sgname_).multisnap(latlng_, radius_, reducepts=reducepts_)
	return [(sg(sgname_).get_latlng(posaddr), str(posaddr)) for posaddr in posaddrs]

def get_pline_latlngs(sgname_, plineidx_):
	plines = sg(sgname_).polylines
	if plineidx_ in xrange(len(plines)):
		return plines[plineidx_]
	else:
		return None

def get_vert_pos(sgname_, vertid_):
	vert = sg(sgname_).get_vertex(vertid_)
	return (vert.pos() if vert is not None else None)

if __name__ == '__main__':

	for i in range(300):
		try:
			print get_connected_vert_latlngs(i)
		except KeyError:
			print 'keyerror on', i


