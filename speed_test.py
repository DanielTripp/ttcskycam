#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time
from misc import * 
import traffic, db, vinfo, routes, geom, mc

if __name__ == '__main__':

	assert mc.client.set('290486246234', 'a') == 0
	routes.get_routeinfo('queen')
	t0 = time.time()
	traffic.get_recent_vehicle_locations('queen', 1, False, str_to_em('2012-09-24 13:20'), log_=False)
	t1 = time.time()
	print 'time', (t1 - t0)
	traffic.get_traffics('queen', 1, False, str_to_em('2012-09-24 13:20'), log_=False)
	t2 = time.time()
	print 'time', (t2 - t1)
