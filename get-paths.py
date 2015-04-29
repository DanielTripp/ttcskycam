#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	def jsonloads(str_):
		return json.loads(str_.replace('(', '[').replace(')', ']'))
		
	def latlng_from_arg(str_):
		r = str_.strip()
		r = r.replace('(', '[').replace(')', ']')
		if not (r.startswith('[') and r.endswith(']')):
			r = '[%s]' % r
		r = json.loads(r)
		return geom.LatLng(r)

	if len(sys.argv) != 6:
		printerr("Need args: orig_latlng dest_latlng ('1'|'m') snap_tolerance k")
	else:
		orig = latlng_from_arg(sys.argv[1])
		dest = latlng_from_arg(sys.argv[2])
		snap_arg = sys.argv[3]
		if snap_arg not in ('1', 'm'):
			raise Exception()
		snap_tolerance = int(sys.argv[4])
		k = jsonloads(sys.argv[5])
		if isinstance(k, Sequence):
			k = tuple(k)

		sg = system.get_snapgraph()
		result = sg.find_paths(orig, snap_arg, dest, snap_arg, snap_tolerance=snap_tolerance, k=k)
		for i, (dist, pathsteps) in enumerate(result):
			print 'Path [%d]:' % i
			print 'dist: %.3f' % dist
			print pathsteps
			for pt in snapgraph.Path([pathsteps], sg).latlngs():
				print pt
			print '---'

