#!/usr/bin/python2.6

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

	froute = 'dundas'
	start_stoptag = '1606'
	dest_stoptag = '6046'
	sim_time_inc = 1000*60*15

	sim_times = []
	for day in range(7, 12) + range(14, 19):
	#for day in (15,):
		for hour in range(8, 20):
		#for hour in (16,):
			for minute in range(0, 60, 15):
				timestr = '2013-01-%02d %02d:%02d' % (day, hour, minute)
				sim_times.append(str_to_em(timestr))

	sim_time_to_observed_arrival_time = {}
	for sim_time in sim_times:
		print em_to_str(sim_time)
		t = db.get_observed_arrival_time(froute, start_stoptag, dest_stoptag, sim_time)['time_arrived']
		sim_time_to_observed_arrival_time[sim_time] = t

	plt.figure(1)
	for i, style in enumerate(('predictions', 'traffic', 'schedule')):
	#if 0:
		sim_time_to_estimate_inaccuracy_mins = {}
		for sim_time in sim_times:
			print em_to_str(sim_time)
			est_arrival_time = paths.get_est_arrival_time(froute, start_stoptag, dest_stoptag, sim_time, sim_time, style)
			if est_arrival_time is None:
				print 'No estimate for %s %s' % (style, em_to_str(sim_time))
			else:
				observed_arrival_time = sim_time_to_observed_arrival_time[sim_time]
				if observed_arrival_time is None:
					print 'No observed arrival time %s' % em_to_str(sim_time)
				else:
					inaccurary_mins = (observed_arrival_time - est_arrival_time)/(1000*60.0)
					sim_time_to_estimate_inaccuracy_mins[sim_time] = inaccurary_mins
					if 1:
						print 'estimated(%11s)=%s, observed=%s, howlate=%.1f' \
							  % (style, em_to_str(est_arrival_time), em_to_str_hms(observed_arrival_time), inaccurary_mins)
		color = {'predictions': (1,0,0), 'traffic': (0,0,1), 'schedule': (0,1,1)}[style]
		def em_to_x(em_):
			#return (em_ - round_down_to_midnight(em_))/(1000*60*60.0)
			return datetime.datetime(2013, 01, 01) + datetime.timedelta(0, 0, 0, em_ - round_down_to_midnight(em_))
		plt.plot([em_to_x(e+1000*60*i*5) for e in sim_time_to_estimate_inaccuracy_mins.iterkeys()],
				 [e for e in sim_time_to_estimate_inaccuracy_mins.itervalues()],
				color=color, marker='.', linestyle='None', label=style)

	plt.legend(loc=0)

	plt.savefig('matplotoutput')
	subprocess.call(['/cygdrive/c/Program Files/Mozilla Firefox/firefox.exe', 'matplotoutput.png'])


