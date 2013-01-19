#!/usr/bin/python2.6

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

	start_time = '2013-01-10 08:00'; end_time =  '2013-01-10 10:00'
	froute = 'dundas'
	direction = 0
	# dundas  6205 broadview   6046 spadina      3665 bathurst    3702 ossington    1063 dufferin    1606 lansdowne    2954 howard
	# lansdowne   6574 dundas    dupont 9085
	stoptag = '6046'
	stop = routes.routeinfo(froute).get_stop(stoptag)
	vid_to_tminus_n_howlate = defaultdict(lambda: [])
	for prediction in db.get_predictions_gen(froute, stoptag, None, start_time, end_time):
		if PRINT:
			print prediction
		start_time = prediction.time - 1000*60*15
		end_time = prediction.time + 1000*60*30
		vis = db.find_passing(prediction.croute, prediction.vehicle_id, start_time, end_time, stop.latlng, direction)
		if vis is None:
			if PRINT:
				print '---> Passing not found'
		else:
			if PRINT:
				print vis[0]
				print vis[1]
			pass_time = vis[0].get_pass_time_interp(vis[1], stop.latlng)
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

