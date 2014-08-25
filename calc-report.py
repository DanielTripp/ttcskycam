#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	reporttype, froute, directionstr, datazoomstr, timestr = sys.argv[1:]
	direction = int(directionstr)
	datazoom = int(datazoomstr)
	time_em = str_to_em(timestr)
	if reporttype == 't':
		traffic.traffic.get_traffics_impl(froute, direction, datazoom, time_em)
	elif reporttype == 'l':
		traffic.get_recent_vehicle_locations_impl(froute, direction, datazoom, time_em)
	else:
		raise Exception()


