#!/usr/bin/python2.6

import sys, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json, getopt
T0 = time.time()
from collections import *
from xml.parsers.expat import ExpatError
import db, vinfo, routes, tracks, streets
from misc import *

POLL_PERIOD_SECS = 60

def get_data_from_web_as_str(route_, time_es_):
	wget_args = ['wget', '--tries=5', '--timeout=3', '-O', '-', 'http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=ttc&r=%s&t=%d' \
		% (route_, time_es_)]
	stdout, stderr = subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
	if not stdout:
		raise Exception('Got no output from NextBus.  stderr from wget:_%s_' % stderr)
	return stdout

def get_data_from_web_as_xml(route_, time_es_, xml_fout_):
	data_str = get_data_from_web_as_str(route_, time_es_)
	if xml_fout_:
		print >> xml_fout_, data_str
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

def deal_with_xml(xmldoc_, insert_into_db_, vis_fout_):
	vehicles = []
	nextbus_lasttime = None
	for elem in (node for node in xmldoc_.documentElement.childNodes if isinstance(node, xml.dom.minidom.Element)):
		if elem.nodeName == 'vehicle':
			vi = vinfo.VehicleInfo.from_xml_elem(elem)
			if vi.vehicle_id: # because once I saw an empty vid string in the database, and I didn't like that. 
				vehicles.append(vi)
		elif elem.nodeName == 'lastTime':
			nextbus_lasttime = long(elem.getAttribute('time'))
	if not nextbus_lasttime:
		raise Exception("Couldn't find lastTime in document:\n%s" % xmldoc_.toprettyxml(newl='\n'))

	for vehicle_info in vehicles:
		vehicle_info.time_retrieved = nextbus_lasttime
		vehicle_info.calc_time()
		if insert_into_db_:
			db.insert_vehicle_info(vehicle_info)
		if vis_fout_:
			print >> vis_fout_, vehicle_info.str_long()

	return {'nextbus_lasttime': nextbus_lasttime, 'our_system_time_on_poll_finish': now_em()}

# We maintain, in the pollstate.json file, two times for each route - nextbus_lasttime and our_system_time_on_poll_finish.
# nextbus_lasttime is the time that we get from the <lastTime> element of the last NextBus poll, and pass as part of the URL
#	of the next one.
# our_system_time_on_poll_finish is our local machine's time after that NextBus poll finishes.  It's probably pretty close
# 	to nextbus_lasttime most of the time.  The important point of this one is not that it's our local system time, but that
#	it's going to tend to increase after each NextBus poll /across routes/ - unlike nextbus_lasttime which is only (I think)
#	guaranteed to increase after each poll in the same route.  One example where I noticed a big difference between these two
# 	two times is during the day when certain late-night routes aren't in service and return no vehicles.  NextBus seems not to 
#	care much about the lastTime on these so I saw it returning a time some 5 minutes in the past.  If we are in a state where we
#	are running out of polling period before polling all routes and hence the polling of the entire route set is spread across
# 	several runs of this program i.e. cron minutes, then we need to take care to loop through the routes sensibly so we
# 	don't poll routes X, Y, and Z repeatedly while polling the others not at all.  So we need to sort by something to ensure
#	that we cycle through the routes.  nextbus_lasttime is inappropriate because in the scenario mentioned above, NextBus will
# 	return a lastTime several minutes in the past for NextBus - so if, when deciding which routes to poll first, we sorted
#	by nextbus_lasttime, this would bias towards those night routes being polled first and possibly, no other routes being polled
#	at all.  So that's why we maintain our_system_time_on_poll_finish and use it to decide which routes to poll first.
def poll_once(routelist_, insert_into_db_, pollstate_filename_, xml_fout_, vis_fout_):
	try:
		with open(pollstate_filename_) as fin:
			route_to_times = json.load(fin)
	except:
		route_to_times = {}
	# Sorting like this will make sure that any routes that were left unpolled on the last run (due to poll period 
	# running out) will be polled first on this run: 
	sortkey = lambda route: route_to_times[route]['our_system_time_on_poll_finish'] if route in route_to_times else 0
	routelist_in_priority_order = sorted(routelist_, key=sortkey)
	for routei, route in enumerate(routelist_in_priority_order):
		if (time.time() - T0) > POLL_PERIOD_SECS - 5:
			sys.exit('poll_locations - poll period has passed, with %d of %d route(s) left unpolled.' \
					% (len(routelist_in_priority_order) - routei, len(routelist_in_priority_order)))
		try:
			nextbus_lasttime = route_to_times[route]['nextbus_lasttime'] if route in route_to_times else 0
			data_xmldoc = get_data_from_web_as_xml(route, nextbus_lasttime, xml_fout_)
			route_to_times[route] = deal_with_xml(data_xmldoc, insert_into_db_, vis_fout_)
		except Exception, e:
			print 'At %s: error getting route %s' % (em_to_str(now_em()), route)
			traceback.print_exc(e)
		with open(pollstate_filename_, 'w') as fout:
			json.dump(route_to_times, fout, indent=0)

def get_graphs_into_ram():
	# Doing this because this is currently called as a cron job every minute i.e. new process every minute. 
	# If we poll nextbus THEN read these large snapgraphs into memory (which takes several seconds) on first use, 
	# then the information for that first route polled will be a few seconds more out of date than it needs to be. 
	# If we ever change our polling of NextBus here to be done in a long-lived process rather than cron, 
	# then this can be removed.
	tracks.get_snapgraph()
	streets.get_snapgraph()

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['routes=', 'pollstatefile=', 'redirect-stdstreams-to-file', 
			'dont-insert-into-db', 'touch-flag-file-on-finish', 'dump-xml=', 'dump-vis='])
	if args:
		sys.exit('No arguments allowed.  Only options.')

	pollstate_filename = (get_opt(opts, 'pollstatefile') or 'pollstate.json')

	if get_opt(opts, 'redirect-stdstreams-to-file'):
		redirect_stdstreams_to_file('poll_locations_')

	if get_opt(opts, 'routes'):
		routelist = get_opt(opts, 'routes').split(',')
	else:
		routelist = list(routes.CONFIGROUTES)

	xml_fout = (open(get_opt(opts, 'dump-xml'), 'a') if get_opt(opts, 'dump-xml') else None)
	vis_fout = (open(get_opt(opts, 'dump-vis'), 'a') if get_opt(opts, 'dump-vis') else None)
	insert_into_db = not get_opt(opts, 'dont-insert-into-db')

	get_graphs_into_ram()

	poll_once(routelist, insert_into_db, pollstate_filename, xml_fout, vis_fout)

	if xml_fout:
		xml_fout.close()
	if vis_fout:
		vis_fout.close()

	if get_opt(opts, 'touch-flag-file-on-finish'):
		touch('/tmp/ttc-poll-locations-finished-flag')
		

