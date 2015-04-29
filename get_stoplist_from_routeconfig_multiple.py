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

import sys, os, urlparse, json, pprint, time, pickle, subprocess
from misc import * 
import traffic, db, vinfo, routes, geom, mc, tracks, util

if __name__ == '__main__':
	
	if len(sys.argv) == 2:
		froutes = [sys.argv[1]]
	else:
		froutes = routes.FUDGEROUTES
		
	for froute in froutes:
		rc_filenames = []
		for croute in routes.FUDGEROUTE_TO_CONFIGROUTES[froute]:
			url = 'http://webservices.nextbus.com/service/publicXMLFeed?command=routeConfig&a=ttc&r=%s&verbose' % croute
			wget_args = ['wget', '-O', '-', url]
			rc_contents = subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]
			rc_filename = 'rc-%s' % croute
			rc_filenames.append(rc_filename)
			with open(rc_filename, 'w') as fout:
				print >> fout, rc_contents

		new_stops_content = subprocess.Popen(['./get_stoplist_from_routeconfig.py'] + rc_filenames, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]
		new_stops_filename = 'stops_%s.json' % froute
		with open(new_stops_filename, 'w') as fout:
			print >> fout, new_stops_content, 



