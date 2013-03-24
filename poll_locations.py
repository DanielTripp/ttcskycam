#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json, getopt
from collections import defaultdict
from xml.parsers.expat import ExpatError
import db, vinfo, routes
from misc import *

ADDITIONAL_ROUTES = ['512', '508', '509']
ROUTES_TO_POLL = routes.CONFIGROUTES + ADDITIONAL_ROUTES
POLL_PERIOD_SECS = 60

def get_data_from_web_as_str(route_, time_es_=0):
	wget_args = ['wget', '--tries=5', '--timeout=3', '-O', '-', 'http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=ttc&r=%s&t=%d' \
		% (route_, time_es_)]
	return subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]

def get_data_from_web_as_xml(route_, time_es_=0):
	data_str = get_data_from_web_as_str(route_, time_es_)
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
 
def insert_xml_into_db(xmldoc_, really_insert_into_db_):
	vehicles = []
	last_time = None
	for elem in (node for node in xmldoc_.documentElement.childNodes if isinstance(node, xml.dom.minidom.Element)):
		if elem.nodeName == 'vehicle':
			vehicles.append(vinfo.VehicleInfo.from_xml_elem(elem))
		elif elem.nodeName == 'lastTime':
			last_time = long(elem.getAttribute('time'))
	if not last_time:
		raise Exception("Couldn't find lastTime")

	for vehicle_info in vehicles:
		vehicle_info.time_retrieved = last_time
		vehicle_info.calc_time()
		if really_insert_into_db_:
			db.insert_vehicle_info(vehicle_info)

	return last_time

def poll_once(insert_into_db_):
	route_to_lasttime_em = defaultdict(lambda: 0)
	try:
		with open('pollstate.json') as fin:
			for key, val in json.load(fin).items():
				route_to_lasttime_em[key] = val
	except:
		pass
	for route in ROUTES_TO_POLL:
		try:
			#print 'Using %d for %s' % (route_to_lasttime_em[route], route)
			data_xmldoc = get_data_from_web_as_xml(route, route_to_lasttime_em[route])
			route_to_lasttime_em[route] = insert_xml_into_db(data_xmldoc, insert_into_db_)
		except Exception, e:
			print 'At %s: error getting route %s' % (em_to_str(now_em()), route)
			traceback.print_exc(e)
		# Prune routes that were in pollstate.json but are not (no longer) in this file's list ROUTES_TO_POLL: 
		for route_in_map in route_to_lasttime_em.keys():
			if route_in_map not in ROUTES_TO_POLL:
				del route_to_lasttime_em[route_in_map]
		with open('pollstate.json', 'w') as fout:
			json.dump(route_to_lasttime_em, fout)

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['redirect-stdstreams-to-file', 'dont-insert-into-db', 'touch-flag-file-on-finish'])
	if args:
		sys.exit('No arguments allowed.  Only options.')

	if get_opt(opts, 'redirect-stdstreams-to-file'):
		redirect_stdstreams_to_file('poll_locations_')

	poll_once(not get_opt(opts, 'dont-insert-into-db'))

	if get_opt(opts, 'touch-flag-file-on-finish'):
		touch('/tmp/ttc-poll-locations-finished-flag')
		

