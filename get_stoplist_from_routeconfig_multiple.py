#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, subprocess
from misc import * 
import traffic, db, vinfo, routes, geom, mc, tracks, util

if __name__ == '__main__':
	
	for froute in routes.FUDGEROUTES:
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



