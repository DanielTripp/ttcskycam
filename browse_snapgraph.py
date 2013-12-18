#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore, streets

def sg():
	return streets.get_snapgraph()

def get_infos_for_box(sw_, ne_):
	return sg().get_infos_for_box(sw_, ne_)

def get_connected_vert_latlngs(vertid_):
	return [vert.pos() for vert in sg().get_connected_vertexes(vertid_)]

def find_paths(start_latlng_, dest_latlng_):
	dists_n_paths = sg().find_paths(start_latlng_, dest_latlng_)
	paths = [x[1] for x in dists_n_paths]
	return [path.latlngs() for path in paths]

def multisnap(latlng_):
	return [sg().get_latlng(posaddr) for posaddr in sg().multisnap(latlng_, 100)]

if __name__ == '__main__':

	for i in range(300):
		try:
			print get_connected_vert_latlngs(i)
		except KeyError:
			print 'keyerror on', i


