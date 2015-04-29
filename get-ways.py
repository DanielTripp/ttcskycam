#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	def latlng_from_arg(str_):
		r = str_.strip()
		r = r.replace('(', '[').replace(')', ']')
		if not (r.startswith('[') and r.endswith(']')):
			r = '[%s]' % r
		r = json.loads(r)
		return geom.LatLng(r)

	if len(sys.argv) != 4:
		printerr("Need args: orig_latlng dest_latlng PACKED")
	else:
		orig = latlng_from_arg(sys.argv[1])
		dest = latlng_from_arg(sys.argv[2])

		if sys.argv[3] == '--packed':
			print system.get_packed_ways(orig, dest)
		elif sys.argv[3] == '--nopacked':
			sg = system.get_snapgraph()
			result = sg.get_ways(orig, dest)
			for i, froutesndirs in enumerate(result):
				print i, froutesndirs
		else:
			raise Exception()

