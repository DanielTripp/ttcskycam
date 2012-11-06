#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle
from misc import * 
import traffic, db, vinfo, routes, geom, mc, tracks

if __name__ == '__main__':

	vis = []
	for route in routes.CONFIGROUTES:
		curs = db.conn().cursor()
		t0 = str_to_em('2012-10-01 00:00');
		curs.execute('select '+db.VI_COLS+' from ttc_vehicle_locations where route_tag = %s and time > %s and time < %s and vehicle_id like %s',\
				[route, t0, t0+1000*60*60*24, '4%'])
		for row in curs:
			vi = vinfo.VehicleInfo(*row)
			if not tracks.is_on_a_track(vi.latlng):
			#if vi.mofr == -1:
				vis.append(vi)
				if len(vis) % 1000 == 0:
					printerr(len(vis))

				# TDR
				# TDR
				if len(vis) == 5000: # TDR
					break  # TDR
				# TDR
				# TDR
				# TDR
		curs.close()
		if len(vis) == 5000: # TDR
			break  # TDR

	print json.dumps([(vi.lat, vi.lng) for vi in vis], indent=1)

