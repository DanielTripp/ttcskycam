#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time
from misc import * 
import traffic, db, vinfo, routes, geom, mc

if __name__ == '__main__':

	print routes.latlon_to_mofr(geom.LatLng(43.63726, -79.41623), 'king', 2)
	print routes.latlon_to_mofr(geom.LatLng(43.63731, -79.41623), 'king', 2)
	#pprint.pprint(geom.LatLng(43.0, -75.0))

	#for t in traffic.get_recent_vehicle_locations('dundas', 1, False, str_to_em('2012-09-24 13:20'), log_=True):
	#t = traffic.get_recent_vehicle_locations('dundas', 1, True, '2012-09-24 13:20', log_=False)
	#for mofr in sorted(t.keys()):
	#for t in traffic.get_traffics('queen', 1, True, '2012-10-16 02:24', log_=True):
		#print '%d: %.1f' % (mofr, speednweight[0])
#		print mofr, t[mofr]


