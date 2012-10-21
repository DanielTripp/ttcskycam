#!/usr/bin/python2.6

from Tkinter import *
import tkFont
import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math
from collections import defaultdict
import db, vinfo, geom, report, bmpgui
from misc import *

if __name__ == '__main__':

	routes = [
		{'routeid':'505', 'orig':(43.655, -79.39), 'post':(43.650, -79.42)}, 
		{'routeid':'501', 'orig':(43.651, -79.386), 'post':(43.644, -79.42)}, 
		{'routeid':'504', 'orig':(43.6475, -79.385), 'post':(43.641, -79.415)}, 
	]

	direction = 'west'
	for route in routes:
		routeid = route['routeid']
		orig = geom.XY.from_latlon(route['orig'])
		post = geom.XY.from_latlon(route['post'])

		print '%s:' % (routeid)
		for vid, post_t_em, travel_time in report.get_recent_travel_times(routeid, orig, post, direction, 5):
			print '%s took %s arriving at %s' % (vid, m_to_str(travel_time), em_to_str(post_t_em))

	frame = bmpgui.MainFrame()
	vilist_allroutes = []
	for routeid in (route['routeid'] for route in routes):
		vilist = db.get_latest_vehicle_info_list(routeid, 10, dir_=direction)
		vilist = geom.interp_by_time(vilist)
		vilist_allroutes += vilist

	t = bmpgui.VehicleInfoDrawingThread(frame, vilist_allroutes, (0.1, 1))
	t.start()
	frame.mainloop()


