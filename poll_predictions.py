#!/usr/bin/python2.6

POLL_PERIOD_SECS = 2*60

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json, getopt
from collections import defaultdict
from xml.parsers.expat import ExpatError
import db, vinfo, routes, predictions
from misc import *

CROUTENSTOPTAGS_TO_OMIT = [('306', '8763'), ('306', '9132'), ('306', '8999'), ('306', '4538'), ('306', '14260_ar'), ('310', '14142_ar'),
	('316', '14050'), ('316', '14197_ar'), ('329', '6113_arx')]

def get_data_from_web_as_str(froute_, stoptag_):
	url_stops_part = ''.join('&stops=%s|%s' % (croute, stoptag_) for croute in routes.FUDGEROUTE_TO_CONFIGROUTES[froute_] \
			if (croute, stoptag_) not in CROUTENSTOPTAGS_TO_OMIT)
	url = 'http://webservices.nextbus.com/service/publicXMLFeed?command=predictionsForMultiStops&a=ttc'+url_stops_part+'&useShortTitles=true'
	wget_args = ['wget', '-O', '-', url]
	return subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]

def get_data_from_web_as_xml(froute_, stoptag_):
	data_str = get_data_from_web_as_str(froute_, stoptag_)
	if not data_str:
		raise Exception('Got no output from NextBus.')
	def print_data_str(msg_):
		print >> sys.stderr, '--- %s - %s:' % (now_str(), msg_)
		print >> sys.stderr, '---'
		print >> sys.stderr, data_str,
		print >> sys.stderr, '---'
	try:
		r = xml.dom.minidom.parseString(data_str)
	except ExpatError:
		print_data_str('Failed to parse output from NextBus.')
		raise
	if [e for e in r.documentElement.childNodes if e.nodeName.lower() == 'error']:
		print_data_str('Detected error(s) in output from NextBus.  (Will try to get data from this document regardless.)')
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

def poll_once(insert_into_db_):
	for froute, stoptag in routes.get_recorded_froutenstoptags():
		try:
			predictions = get_predictions_from_web(froute, stoptag)
			if insert_into_db_:
				db.insert_predictions(predictions)
		except Exception, e:
			print 'At %s: error during route %s stoptag %s' % (em_to_str(now_em()), froute, stoptag)
			traceback.print_exc(e)

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['redirect-stdstreams-to-file', 'dont-insert-into-db'])
	if args:
		sys.exit('No arguments allowed.  Only options.')

	if get_opt(opts, 'redirect-stdstreams-to-file'):
		redirect_stdstreams_to_file('poll_predictions_')

	poll_once(not get_opt(opts, 'dont-insert-into-db'))


