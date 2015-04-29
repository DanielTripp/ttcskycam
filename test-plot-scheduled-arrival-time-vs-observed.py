#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, subprocess
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mpldates
from misc import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths

def em_to_datetime(em_):
	return datetime.datetime.fromtimestamp(em_/1000.0)

def em_to_mpldatenum(em_):
	return mpldates.date2num(em_to_datetime(em_))

if __name__ == '__main__':

	froute = 'lansdowne'
	start_stoptag = '5107'
	dest_stoptag = '5145_ar'
	sim_time_inc = 1000*60*15

	sim_times = []
	for day in range(7, 12) + range(14, 19):
	#for day in range(17, 18):
	#for day in (15,):
		for hour in range(8, 20):
		#for hour in (16,):
			for minute in range(0, 60, 15):
			#for minute in (30,):
				timestr = '2013-01-%02d %02d:%02d' % (day, hour, minute)
				sim_times.append(str_to_em(timestr))

	plt.figure(1)
	sim_time_to_lateness_mins = {}
	for sim_time in sim_times:
		print em_to_str(sim_time)
		observed_arrival_time = db.get_observed_arrival_time(froute, start_stoptag, dest_stoptag, sim_time)['time_arrived']
		if observed_arrival_time is None:
			print 'No observed arrival time %s' % em_to_str(sim_time)
		else:
			scheduled_arrival_time = routes.schedule(froute).get_arrival_time(start_stoptag, dest_stoptag, sim_time)
			lateness_mins = (observed_arrival_time - scheduled_arrival_time)/(1000.0*60)
			if abs(lateness_mins) < 30:
				sim_time_to_lateness_mins[sim_time] = lateness_mins

	def em_to_x(em_):
		#return (em_ - round_down_to_midnight(em_))/(1000*60*60.0)
		return datetime.datetime(2013, 01, 01) + datetime.timedelta(0, 0, 0, em_ - round_down_to_midnight(em_))

	plt.plot([em_to_x(e) for e in sim_time_to_lateness_mins.iterkeys()],
			 [e for e in sim_time_to_lateness_mins.itervalues()],
			color=(0,0,1), marker='.', linestyle='None')

	#plt.legend(loc=0)

	plt.savefig('matplotoutput')
	subprocess.call(['/cygdrive/c/Program Files/Mozilla Firefox/firefox.exe', 'matplotoutput.png'])


