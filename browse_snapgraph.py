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

def find_multipath(sgname_, latlngs_):
	path = sg(sgname_).find_multipath(latlngs_)[1]
	return (path.latlngs() if path is not None else None)

def multisnap(sgname_, latlng_, radius_):
	posaddrs = sg(sgname_).multisnap(latlng_, radius_)
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


