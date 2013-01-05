#!/usr/bin/python2.6

POLL_PERIOD_SECS = 2*60

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json
from collections import defaultdict
import db, vinfo, routes, predictions
from misc import *

def get_data_from_web_as_str(froute_, stoptag_):
	url_stops_part = ''.join('&stops=%s|%s' % (croute, stoptag_) for croute in routes.FUDGEROUTE_TO_CONFIGROUTES[froute_])
	url = 'http://webservices.nextbus.com/service/publicXMLFeed?command=predictionsForMultiStops&a=ttc'+url_stops_part+'&useShortTitles=true'
	wget_args = ['wget', '-O', '-', url]
	return subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]

def get_data_from_web_as_xml(froute_, stoptag_):
	data_str = get_data_from_web_as_str(froute_, stoptag_)
	r = xml.dom.minidom.parseString(data_str)
	return r

# return list of Prediction. 
def get_predictions_from_web(froute_, stoptag_):
	r = []
	dom = get_data_from_web_as_xml(froute_, stoptag_)
	time_retrieved = now_em()
	for prediction_elem in dom.getElementsByTagName('prediction'):
		assert prediction_elem.parentNode.parentNode.nodeName == 'predictions'
		croute = prediction_elem.parentNode.parentNode.getAttribute('routeTag')
		assert croute
		prediction = predictions.Prediction.from_xml(froute_, croute, stoptag_, time_retrieved, prediction_elem)
		r.append(prediction)
	return r

def poll_once():
	for i in routes.get_intersections():
		for froute, stoptag in ((i.froute1, i.froute1_dir0_stoptag), (i.froute1, i.froute1_dir1_stoptag), 
				(i.froute2, i.froute2_dir0_stoptag), (i.froute2, i.froute2_dir1_stoptag)):
			db.insert_predictions(get_predictions_from_web(froute, stoptag))

	
if __name__ == '__main__':

	assert len(sys.argv) == 1
	poll_once()



