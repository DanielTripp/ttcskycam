#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom
from misc import * 
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths

if __name__ == '__main__':

	def em_to_ms(t_):
		assert t_ < 1000*60*60
		mins = abs(t_/1000) / 60
		secs = abs(t_/1000) - mins*60
		return '%02d:%02d' % (mins, secs)
		

	t = '2013-01-05 20:30'
	froute = 'king'
	stoptag = '4748'
	stop = routes.routeinfo(froute).get_stop(stoptag)
	predictions = db.get_predictions(froute, stoptag, None, t)
	for prediction in predictions:
		print prediction
		start_time = prediction.time - 1000*60*15
		end_time = prediction.time + 1000*60*30
		vis = db.find_passing(prediction.croute, prediction.vehicle_id, start_time, end_time, stop.latlng)
		if vis is None:
			print '---> Passing not found'
		else:
			print vis[0]
			print vis[1]
			pass_time = vis[0].get_pass_time_interp(vis[1], stop.latlng)
			time_diff = pass_time - prediction.time
			mins = abs(time_diff/1000) / 60
			secs = abs(time_diff/1000) - mins*60
			print '---> Prediction was %s into the future.  Vehicle was %s %s' % (em_to_ms(prediction.time - prediction.time_retrieved), \
					em_to_ms(time_diff), ('late' if time_diff > 0 else 'early'))
		print '------'


