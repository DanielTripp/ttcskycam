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

if __name__ == '__main__':

	for i in range(300):
		try:
			print get_connected_vert_latlngs(i)
		except KeyError:
			print 'keyerror on', i


