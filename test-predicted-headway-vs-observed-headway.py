#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

PRINT = 0
GRAPH = 1

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, subprocess
from collections import defaultdict
import matplotlib
if GRAPH:
	matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mpldates
from misc import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths

def em_to_datetime(em_):
	return datetime.datetime.fromtimestamp(em_/1000.0)

def em_to_mpldatenum(em_):
	return mpldates.date2num(em_to_datetime(em_))

def get_color(vid_):
	colors = [(0,0,0), (0.4,0.4,0.4), (0,1,0), (0,0.4,0), (0.2,0.2,1), (0,0,0.4), (0.4,0.4,0), (0,1,1), (0,0.4,0.4), (1,0,1), (0.4,0,0.4), (1,0,0), (0,0,1)]
	return colors[hash(vid_) % len(colors)]

def get_marker(vid_):
	return '+'
	#markers = ['o', 'D', 'H', 's', '*']
	markers = ['.', '+', 'x']
	return markers[hash(vid_) % len(markers)]

if __name__ == '__main__':

	def em_to_ms(t_):
		assert t_ < 1000*60*60
		mins = abs(t_/1000) / 60
		secs = abs(t_/1000) - mins*60
		return '%02d:%02d' % (mins, secs)

	start_time = '2013-01-10 15:00'; end_time =  '2013-01-10 18:00'
	froute = 'dundas'
	direction = 0
	# dundas  6205 broadview   6046 spadina      3665 bathurst    3702 ossington    1063 dufferin    1606 lansdowne    2954 howard
	# lansdowne   6574 dundas    dupont 9085
	stoptag = '6046'
	stop = routes.routeinfo(froute).get_stop(stoptag)
	tminus_n_headwaydiff = []

	time_to_observed_headway = {}
	def get_observed_headway(target_time_):
		if target_time_ in time_to_observed_headway:
			return time_to_observed_headway[target_time_]
		else:
			r = traffic.get_observed_headway(froute, stoptag, target_time_, 60)
			time_to_observed_headway[target_time_] = r
			return r

	for predictions in db.get_predictions_group_gen(froute, stoptag, None, start_time, end_time):
		time_retrieved = predictions[0].time_retrieved
		#pprint.pprint(predictions)
		print em_to_str_hms(time_retrieved)
		# maybe broken feb 5 2021  time_retrieved_rounded_down = round_down_by_minute_step(time_retrieved, 5)
		for headway_target_time in range(time_retrieved_rounded_down, time_retrieved_rounded_down+1000*60*45, 1000*60*5):
			tminus = time_retrieved - headway_target_time
			lo_predictions = [prediction for prediction in predictions if prediction.time <= headway_target_time]
			hi_predictions = [prediction for prediction in predictions if prediction.time >= headway_target_time]
			if lo_predictions and hi_predictions:
				lo_prediction = max(lo_predictions, key=lambda p: p.time)
				hi_prediction = min(hi_predictions, key=lambda p: p.time)
				predicted_headway = hi_prediction.time - lo_prediction.time
				#print em_to_str_hms(time_retrieved), em_to_str_hms(headway_target_time), predicted_headway/(1000.0*60)
				observed_headway = get_observed_headway(headway_target_time)
				if observed_headway:
					headway_diff = predicted_headway - observed_headway[0]
					tminus_n_headwaydiff.append((tminus/(1000.0*60), headway_diff/(1000.0*60)))

	if GRAPH:
		plt.figure(1)
		plt.plot([x[0] for x in tminus_n_headwaydiff], [x[1] for x in tminus_n_headwaydiff],\
				color=(0.4,0.4,0.4), marker='+', linestyle='None')
		plt.savefig('matplotoutput')
		subprocess.call(['/cygdrive/c/Program Files/Mozilla Firefox/firefox.exe', 'matplotoutput.png'])

