#!/usr/bin/python2.6

ROUTES = ['505', '501', '504', '301', '511', '510']
POLL_PERIOD_SECS = 60

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json
from collections import defaultdict
import db, vinfo
from misc import *

def get_data_from_web_as_str(route_, time_es_=0):
	wget_args = ['wget', '-O', '-', 'http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=ttc&r=%s&t=%d' \
		% (route_, time_es_)]
	return subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]

def get_data_from_web_as_xml(route_, time_es_=0):
	data_str = get_data_from_web_as_str(route_, time_es_)
	r = xml.dom.minidom.parseString(data_str)
	return r
 
def insert_xml_into_db(xmldoc_):
	db.reconnect()
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
		vehicle_info.time_epoch = last_time
		vehicle_info.calc_time()
		db.insert_vehicle_info(vehicle_info)

	return last_time

def poll_all_routes_forever():
	while True:
		route_to_lasttime_em = defaultdict(lambda: 0)
		for route in ROUTES:
			try:
				data_xmldoc = get_data_from_web_as_xml(route, route_to_lasttime_em[route])
				route_to_lasttime_em[route] = insert_xml_into_db(data_xmldoc)
			except Exception, e:
				print 'At %s: error getting route %s' % (em_to_str(now_em()), route)
				traceback.print_exc(e)
				#print sys.exc_info()[2]):
				#for line in traceback.format_tb(sys.exc_info()[2]):
				#	print line
			time.sleep(POLL_PERIOD_SECS/len(ROUTES))

def poll_once():
	route_to_lasttime_em = defaultdict(lambda: 0)
	try:
		with open('pollstate.json') as fin:
			for key, val in json.load(fin).items():
				route_to_lasttime_em[key] = val
	except:
		pass
	for route in ROUTES:
		try:
			#print 'Using %d for %s' % (route_to_lasttime_em[route], route)
			data_xmldoc = get_data_from_web_as_xml(route, route_to_lasttime_em[route])
			route_to_lasttime_em[route] = insert_xml_into_db(data_xmldoc)
		except Exception, e:
			print 'At %s: error getting route %s' % (em_to_str(now_em()), route)
			traceback.print_exc(e)
		# Prune routes that were in pollstate.json but are not (no longer) in this file's list ROUTES: 
		for route_in_map in route_to_lasttime_em.keys():
			if route_in_map not in ROUTES:
				del route_to_lasttime_em[route_in_map]
		with open('pollstate.json', 'w') as fout:
			json.dump(route_to_lasttime_em, fout)

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == '--once':
		db.use_localhost(True)
		poll_once()
	else:
		poll_all_routes_forever()


