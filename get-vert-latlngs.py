#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	sgname = sys.argv[1]
	if sgname == 'system':
		sg = system.get_snapgraph()
	elif sgname == 'streets':
		sg = streets.get_snapgraph()
	elif sgname == 'tracks':
		sg = tracks.get_snapgraph()
	else:
		raise Exception()
	vertidxesstr = sys.argv[2]
	vertidxes = json.loads(vertidxesstr)
	for vertidx in vertidxes:
		print sg.verts[vertidx].pos()
	dist = 0.0
	for vertidx1, vertidx2 in hopscotch(vertidxes):
		dist += sg.get_wdist(vertidx1, vertidx2)
	printerr('dist: %.3f' % dist)

