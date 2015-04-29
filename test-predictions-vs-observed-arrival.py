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
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions

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

	start_time = '2013-01-10 08:00'; end_time =  '2013-01-10 10:00'
	froute = 'dundas'
	direction = 0
	# dundas  6205 broadview   6046 spadina      3665 bathurst    3702 ossington    1063 dufferin    1606 lansdowne    2954 howard
	# lansdowne   6574 dundas    dupont 9085
	stoptag = '6046'
	stop_latlng = geom.LatLng(43.6527999, -79.39825)
	vid_to_tminus_n_howlate = defaultdict(lambda: [])
	for prediction in db.get_predictions_gen(froute, stoptag, None, start_time, end_time):
		if PRINT:
			print prediction
		start_time = prediction.time - 1000*60*15
		end_time = prediction.time + 1000*60*30
		vis = db.find_passing(prediction.froute, prediction.vehicle_id, start_time, end_time, stop_latlng, direction)
		if vis is None:
			if PRINT:
				print '---> Passing not found'
		else:
			if PRINT:
				print vis[0]
				print vis[1]
			pass_time = vis[0].get_pass_time_interp(vis[1], stop_latlng)
			time_diff = pass_time - prediction.time
			mins = abs(time_diff/1000) / 60
			secs = abs(time_diff/1000) - mins*60
			tminus = (prediction.time_retrieved - pass_time)/(1000*60.0)
			howlate = time_diff/(1000*60.0)
			if 1:
				if tminus > -20 and howlate < -5:
					print prediction
					print 'Observed arrival:', em_to_str(pass_time)
			if 0:
				if tminus > 2:
					print prediction
					print 'Observed arrival:', em_to_str(pass_time)


			vid_to_tminus_n_howlate[prediction.vehicle_id].append((tminus, howlate))
			if PRINT:
				print '---> Prediction was %s into the future.  Predicted time: %s.  Real arrival: %s.  Vehicle was %s %s' \
					  % (em_to_ms(prediction.time - prediction.time_retrieved),
						 em_to_str(prediction.time), em_to_str(pass_time),
						 em_to_ms(time_diff), ('late' if time_diff > 0 else 'early'))
		if PRINT:
			print '------'

	if GRAPH:
		plt.figure(1)
		for vid, tminus_n_howlate in vid_to_tminus_n_howlate.iteritems():
			plt.plot([x[0] for x in tminus_n_howlate], [x[1] for x in tminus_n_howlate],\
					color=get_color(vid), marker=get_marker(vid), linestyle='None')
		plt.savefig('matplotoutput')
		subprocess.call(['/cygdrive/c/Program Files/Mozilla Firefox/firefox.exe', 'matplotoutput.png'])

