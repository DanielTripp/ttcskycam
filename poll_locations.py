#!/usr/bin/python

import sys, os, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json, getopt
from collections import *
from xml.parsers.expat import ExpatError
import db, vinfo, routes, tracks, streets, multiproc
from misc import *

def get_data_from_web_as_str(route_, time_es_):
	wget_args = ['wget', '--tries=5', '--timeout=10', '-O', '-', 'http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=ttc&r=%s&t=%d' \
		% (route_, time_es_)]
	stdout, stderr = subprocess.Popen(wget_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
	if not stdout:
		raise Exception('Got no output from NextBus.  stderr from wget:_%s_' % stderr)
	return stdout

def get_data_from_web_as_xml(route_, time_es_, xml_filename_, xml_headers_):
	data_str = get_data_from_web_as_str(route_, time_es_)
	if xml_filename_:
		if xml_filename_ == 'stdout':
			dump_xml(sys.stdout, route_, time_es_, xml_headers_, data_str)
		else:
			with open(xml_filename_, 'a') as fout:
				dump_xml(fout, route_, time_es_, xml_headers_, data_str)
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

def dump_xml(fout_, route_, time_es_, xml_headers_, data_str_):
	if xml_headers_:
		cur_time = now_em()
		cur_timestr = em_to_str(now_em())
		print >> fout_, 'Route %s, t=%d.  (Current time: %d / %s.)' % (route_, time_es_, cur_time, cur_timestr)
	print >> fout_, data_str_

def deal_with_xml(xmldoc_, insert_into_db_, vis_filename_):
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

	for vi in vehicles:
		vi.time_retrieved = nextbus_lasttime
		vi.calc_time()
		if insert_into_db_:
			db.insert_vehicle_info(vi)

	if vis_filename_:
		if vis_filename_ == 'stdout':
			for vi in vehicles:
				print >> sys.stdout, vi.str_long()
		else:
			with open(vis_filename_, 'a') as fout:
				for vi in vehicles:
					print >> fout, vi.str_long()

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
def poll_once(routelist_, insert_into_db_, pollstate_filename_, xml_filename_, xml_headers_, vis_filename_, multiproc_, 
		touch_flag_file_on_finish_):
	if multiproc_:
		pool = multiprocessing.Pool(8, multiproc.initializer)
	try:
		try:
			with open(pollstate_filename_) as fin:
				route_to_times = json.load(fin)
		except:
			route_to_times = {}
		# Sorting like this will make sure that any routes that were left unpolled on the last run (due to poll period 
		# running out) will be polled first on this run: 
		sortkey = lambda route: route_to_times[route]['our_system_time_on_poll_finish'] if route in route_to_times else 0
		routelist_in_priority_order = sorted(routelist_, key=sortkey)
		route_to_poolresult = {}
		for routei, route in enumerate(routelist_in_priority_order):
			try:
				nextbus_lasttime = route_to_times[route]['nextbus_lasttime'] if route in route_to_times else 0
				if multiproc_:
					route_to_poolresult[route] = pool.apply_async(get_data_from_web_and_deal_with_it, \
							(route, nextbus_lasttime, insert_into_db_, xml_filename_, xml_headers_, vis_filename_))
				else:
					route_to_times[route] = get_data_from_web_and_deal_with_it(
							route, nextbus_lasttime, insert_into_db_, xml_filename_, xml_headers_, vis_filename_)
			except Exception, e:
				print 'At %s: error getting route %s' % (em_to_str(now_em()), route)
				traceback.print_exc(e)
		if multiproc_:
			for route, poolresult in route_to_poolresult.iteritems():
				try:
					route_to_times[route] = poolresult.get()
				except Exception, e:
					print 'At %s: error getting route %s' % (em_to_str(now_em()), route)
					traceback.print_exc(e)
		with open(pollstate_filename_, 'w') as fout:
			json.dump(route_to_times, fout, indent=0)
		if touch_flag_file_on_finish_:
			touch('/tmp/ttc-poll-locations-finished-flag')
	finally:
		if multiproc_:
			pool.close()
			pool.join()

def get_data_from_web_and_deal_with_it(route_, nextbus_lasttime_, insert_into_db_, xml_filename_, xml_headers_, vis_filename_):
	data_xmldoc = get_data_from_web_as_xml(route_, nextbus_lasttime_, xml_filename_, xml_headers_)
	r = deal_with_xml(data_xmldoc, insert_into_db_, vis_filename_)
	return r

def get_graphs_into_ram():
	# Doing this because this is currently called as a cron job every minute i.e. new process every minute. 
	# If we poll nextbus THEN read these large snapgraphs into memory (which takes several seconds) on first use, 
	# then the information for that first route polled will be a few seconds more out of date than it needs to be. 
	# If we ever change our polling of NextBus here to be done in a long-lived process rather than cron, 
	# then this can be removed.
	tracks.get_snapgraph()
	streets.get_snapgraph()

def wait_until_start_of_next_minute():
	now = now_em()
	target_time = round_up_by_minute(now)
	secs_to_sleep = (target_time - now)/1000
	time.sleep(secs_to_sleep)

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['routes=', 'pollstatefile=', 'redirect-stdstreams-to-file', 
			'dont-insert-into-db', 'touch-flag-file-on-finish', 'dump-xml=', 'dump-vis=', 'xml-headers', 'forever'])
	if args:
		sys.exit('No arguments allowed.  Only options.')

	pollstate_filename = (get_opt(opts, 'pollstatefile') or 'pollstate.json')

	if get_opt(opts, 'redirect-stdstreams-to-file'):
		redirect_stdstreams_to_file('poll_locations_')

	if get_opt(opts, 'routes'):
		routelist = get_opt(opts, 'routes').split(',')
	else:
		routelist = list(routes.CONFIGROUTES)

	xml_filename = get_opt(opts, 'dump-xml')
	if xml_filename:
		xml_filename = os.path.expanduser(xml_filename)
		if os.path.isdir(xml_filename):
			xml_filename = os.path.join(xml_filename, time.strftime('vehicle_locations_xml_%Y-%m-%d--%H-%M.txt', time.localtime(time.time())))

	vis_filename = get_opt(opts, 'dump-vis')
	if vis_filename:
		vis_filename = os.path.expanduser(vis_filename)
		if os.path.isdir(vis_filename):
			vis_filename = os.path.join(vis_filename, time.strftime('vehicle_locations_vis_%Y-%m-%d--%H-%M.txt', time.localtime(time.time())))

	insert_into_db = not get_opt(opts, 'dont-insert-into-db')

	if insert_into_db or vis_filename:
		get_graphs_into_ram()

	do_multiproc = insert_into_db or vis_filename
	xml_headers = get_opt(opts, 'xml-headers')
	touch_flag_file_on_finish = get_opt(opts, 'touch-flag-file-on-finish')
	forever = get_opt(opts, 'forever')
	def call_poll_once():
		poll_once(routelist, insert_into_db, pollstate_filename, xml_filename, xml_headers, vis_filename, do_multiproc, 
				touch_flag_file_on_finish)
	if forever:
		wait_until_start_of_next_minute()
		while True:
			poll_start_time = time.time()
			call_poll_once()
			poll_end_time = time.time()
			if poll_end_time - poll_start_time < 60:
				wait_until_start_of_next_minute()
	else:
		call_poll_once()
		

