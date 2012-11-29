#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle
from misc import * 
import traffic, db, vinfo, routes, geom, mc, tracks

if __name__ == '__main__':

	LIMIT = 50000

	vis = []
	for route in ('505', '501', '504', '301', '511', '510', '508', '506', '509', '512'):
		printerr(route+'...')
		curs = db.conn().cursor()
		t0 = str_to_em('2012-11-17 00:00');
		curs.execute('select '+db.VI_COLS+' from ttc_vehicle_locations where route_tag = %s and time > %s and time < %s and vehicle_id like %s',\
				[route, t0, t0+1000*60*60*48, '4%'])
		for row in curs:
			vi = vinfo.VehicleInfo(*row)
			if not tracks.is_on_a_track(vi.latlng):
			#if vi.mofr == -1:
				vis.append(vi)
				if len(vis) % 1000 == 0:
					printerr(len(vis))

				if len(vis) >= LIMIT:
					break
		curs.close()
		if len(vis) >= LIMIT:
			break

	print json.dumps([(vi.lat, vi.lng) for vi in vis], indent=1)

