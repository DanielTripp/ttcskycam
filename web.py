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

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, json
from collections import defaultdict
import vinfo, geom, db, traffic
from misc import *


def massage(vis_by_time_):
	r = []
	for vilist_for_timeslice in vis_by_time_:
		vilist_jsondicts_for_timeslice = []
		r.append(vilist_jsondicts_for_timeslice)
		vilist_jsondicts_for_timeslice.append(vilist_for_timeslice[0]) # first elem is a date/time string 
		for vi in vilist_for_timeslice[1:]:
			vilist_jsondicts_for_timeslice.append(vi.to_json_dict())
	return json.dumps(r)
	

def query1(whereclause_, maxrows_, interp_by_time_):
	return massage(db.query1(whereclause_, maxrows_, interp_by_time_))

def get_traffic(route_, direction_, time_=now_em()):
	return json.dumps(traffic.get_traffics(route_, direction_, time_))
	
def get_vehicle_svg():
	#return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
	return				'<svg xmlns="http://www.w3.org/2000/svg" width="35" height="20" version="1.1">' + \
					'<text x="0" y="15" fill="rgb(0,0,255)">testing</text>' + \
					'</svg>'

