#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, subprocess
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
#matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.dates as mpldates
from misc import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths

def em_to_datetime(em_):
	return datetime.datetime.fromtimestamp(em_/1000.0)

def em_to_mpldatenum(em_):
	return mpldates.date2num(em_to_datetime(em_))

def get_color(hash_):
	colors = [(0,0,0), (0.4,0.4,0.4), (0,1,0), (0,0.4,0), (0.2,0.2,1), (0,0,0.4), (0.4,0.4,0), (0,1,1), (0,0.4,0.4), (1,0,1), (0.4,0,0.4)]
	return colors[hash_ % len(colors)]

if __name__ == '__main__':

	froute = 'dundas'
	start_stoptag = '1606'
	dest_stoptag = '6046'
	sim_time_inc = 1000*60*15

	plt.figure(1)

	def em_to_x(em_):
		return datetime.datetime(2013, 01, 01) + datetime.timedelta(0, 0, 0, em_ - round_down_to_midnight(em_))

	def plot(time_to_val_, color_, label_):
		sorted_times = sorted(time_to_val_.keys())
		plt.plot([em_to_x(tyme) for tyme in sorted_times],
				 [time_to_val_[tyme] for tyme in sorted_times],
				 color=color_, label=label_)

	sim_times = []
	#for day in range(7, 12) + range(14, 19):
	for i, day in enumerate(range(21,30)):
		#for hour in range(8, 20):
		sim_time_to_observed_ride_time = {}
		for hour in range(12, 18):
			for minute in range(0, 60, 5):
				timestr = '2013-01-%02d %02d:%02d' % (day, hour, minute)
				print timestr
				sim_time = str_to_em(timestr)
				sim_times.append(sim_time)

				observation = db.get_observed_arrival_time(froute, start_stoptag, dest_stoptag, sim_time)
				if observation is not None and observation['time_arrived'] is not None:
					ride_time_mins = (observation['time_arrived'] - observation['time_caught'])/(1000*60.0)
					if ride_time_mins < 40:
						sim_time_to_observed_ride_time[sim_time] = ride_time_mins
		plot(sim_time_to_observed_ride_time, get_color(i), str(day))


	if 0:
		print 'observed...'
		sim_time_to_observed_ride_time = {}
		for sim_time in sim_times:
			print em_to_str(sim_time)
			observation = db.get_observed_arrival_time(froute, start_stoptag, dest_stoptag, sim_time)
			if observation is not None and observation['time_arrived'] is not None:
				ride_time_mins = (observation['time_arrived'] - observation['time_caught'])/(1000*60.0)
				sim_time_to_observed_ride_time[sim_time] = ride_time_mins

	#plot(sim_time_to_observed_ride_time, (0,0,0), 'observed')

	if 0:
	#for i, style in enumerate(('predictions', 'traffic', 'schedule')):
		print '%s...' % style
		sim_time_to_est_ride_time = {}
		for sim_time in sim_times:
			print em_to_str(sim_time)
			estimation = paths.get_est_arrival_time(froute, start_stoptag, dest_stoptag, sim_time, sim_time, style)
			if estimation is None:
				print 'No estimate for %s %s' % (style, em_to_str(sim_time))
			else:
				ride_time_mins = (estimation['time_arrived'] - estimation['time_caught'])/(1000*60.0)
				sim_time_to_est_ride_time[sim_time] = ride_time_mins
		color = {'predictions': (1,0,0), 'traffic': (0,0,1), 'schedule': (0,1,1)}[style]

		for k, v in sim_time_to_est_ride_time.iteritems():
			sim_time_to_est_ride_time[k] = sim_time_to_observed_ride_time[k] - sim_time_to_est_ride_time[k]
		plot(sim_time_to_est_ride_time, color, style)


	plt.legend(loc=0)

	plt.savefig('matplotoutput')
	#subprocess.call(['/cygdrive/c/Program Files/Mozilla Firefox/firefox.exe', 'matplotoutput.png'])
	subprocess.call(['/cygdrive/c/WINDOWS/system32/mspaint', 'matplotoutput.png'])



