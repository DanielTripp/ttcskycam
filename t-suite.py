#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph

if __name__ == '__main__':

	#pprint.pprint(traffic.get_traffics_impl('dundas', 0, c.VALID_ZOOMS[-1], str_to_em('2013-09-28 17:00')))

	log = False

	for day in ['2013-11-14']:
		for hour in range(0, 24):
		#for hour in (0,):
			for minute in (0, 30):
			#for minute in (0,):
				tstr = '%s %02d:%02d' % (day, hour, minute)
				t = str_to_em(tstr)
				for froute in routes.NON_SUBWAY_FUDGEROUTES:
				#for froute in ('king',):
					for direction in (0, 1):
					#for direction in (1,):
						print tstr, froute, direction, 'traffic:'
						print util.to_json_str(reports.calc_report_obj('traffic', froute, direction, c.MIN_DATAZOOM, t, log_=log), indent=1)
						print tstr, froute, direction, 'locations:'
						print util.to_json_str(reports.calc_report_obj('locations', froute, direction, c.MIN_DATAZOOM, t, log_=log), indent=1)


