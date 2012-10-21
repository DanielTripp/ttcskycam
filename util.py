#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math, json
from collections import defaultdict
from itertools import ifilter
import vinfo, db, routes, geom, mc, yards, c
from misc import *

MILLIS_IN_A_DAY = 1000*60*60*24

def get_vids(route_, day_start_time_):
	sql = 'select distinct(vehicle_id) from ttc_vehicle_locations where route_tag = %s and time >  %s and time < %s + '+str(MILLIS_IN_A_DAY)
	curs = db.g_conn.cursor()
	curs.execute(sql, [route_, day_start_time_, day_start_time_])
	r = []
	for row in curs:
		r.append(row[0])
	curs.close()
	return r

def find_wrong_dirs(route_, day_start_time_):
	vids = get_vids(route_, day_start_time_)
	print len(vids)
	for vid in vids:
		print vid
		curs = db.g_conn.cursor()
		sql = 'select dir_tag, heading, vehicle_id, lat, lon, predictable, route_tag, secs_since_report, time_epoch, time from ttc_vehicle_locations where vehicle_id = %s and time >  %s and time < %s + '+str(MILLIS_IN_A_DAY)+' order by time' 
		curs.execute(sql, [vid, day_start_time_, day_start_time_])
		for vis in windowiter((vinfo.VehicleInfo(*row) for row in curs), 5):
			if all(vi0.dir_tag_int == vi1.dir_tag_int for vi0, vi1 in hopscotch(vis)) \
					and none(vi.mofr == -1 or vi.mofr < 100 or vi.mofr > routes.max_mofr(vi.route_tag) - 100 for vi in vis):
				dir_tag_int = vis[0].dir_tag_int
				if dir_tag_int in (0, 1):
					if dir_tag_int == 0:
						going_the_right_way = all(vi1.mofr >= vi0.mofr for vi0, vi1 in hopscotch(vis))
					else:
						going_the_right_way = all(vi1.mofr <= vi0.mofr for vi0, vi1 in hopscotch(vis))
					if not going_the_right_way:
						print 'not going the right way: vid %s from %s to %s'  % (vid, vis[0].timestr, vis[-1].timestr)
						
		curs.close()

if __name__ == '__main__':

	find_wrong_dirs('505', str_to_em('2012-10-01 00:00'))


