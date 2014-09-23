#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['print', 'datazoom=', 'log', 'restartmc'])
	if len(args) != 4:
		sys.exit('Need 4 args: reporttype, froute, direction, and date/time.')

	doprint = get_opt(opts, 'print')
	datazoom = get_opt(opts, 'datazoom') or 0
	dolog = get_opt(opts, 'log')
	restartmc = get_opt(opts, 'restartmc')

	reporttype, froute, directionstr, timestr = args
	direction = int(directionstr)
	if direction not in (0, 1):
		raise Exception()
	time_em = str_to_em(timestr)

	if restartmc:
		mc.restart()

	if reporttype == 't':
		report = traffic.get_traffics_impl(froute, direction, datazoom, time_em, log_=dolog)
	elif reporttype == 'l':
		report = traffic.get_recent_vehicle_locations_impl(froute, direction, datazoom, time_em, log_=dolog)
	else:
		raise Exception()
	
	if doprint:
		pprint.pprint(report)



