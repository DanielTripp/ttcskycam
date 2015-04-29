#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, c, reports 

if __name__ == '__main__':

	froute = 'dundas'
	src_start_time = str_to_em('2030-01-01 11:00')
	src_end_time = str_to_em('2030-01-01 13:00')
	dest_start_time = str_to_em('2034-09-26 11:00')

	dest_time_offset = dest_start_time - src_start_time

	i = 0
	for vi in db.vi_select_generator(froute, src_end_time, src_start_time, include_unpredictables_=True):
		vi.time_retrieved += dest_time_offset
		vi.calc_time()
		print 'Writing...'
		db.insert_vehicle_info(vi)
		i += 1
	print 'Copied %d vis.' % i
		
