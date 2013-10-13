#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels

if __name__ == '__main__':

	#pprint.pprint(traffic.get_traffics_impl('dundas', 0, c.VALID_ZOOMS[-1], str_to_em('2013-09-28 17:00')))

	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		for direction in (0, 1):
			for zoom in c.VALID_ZOOMS:
				print reports.get_traffic_report(froute, direction, zoom, '2013-09-28 17:00', None)
				print reports.get_locations_report(froute, direction, zoom, '2013-09-28 17:00', None)



