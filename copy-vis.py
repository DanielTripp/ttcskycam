#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

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
		
