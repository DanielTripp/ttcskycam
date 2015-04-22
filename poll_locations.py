#!/usr/bin/python

import sys, os, subprocess, re, time, xml.dom, xml.dom.minidom, traceback, json, getopt
from collections import *
from xml.parsers.expat import ExpatError
import db, vinfo, routes, tracks, streets
from misc import *

def get_data_from_web_as_str(route_, time_es_):
	wget_args = ['wget', '--tries=5', '--timeout=25', '-O', '-', 'http://webservices.nextbus.com/service/publicXMLFeed?command=vehicleLocations&a=ttc&r=%s&t=%d' \
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
	return parse_xml(data_str)

def parse_xml(xml_str_):
	def print_error(msg__):
		printerr('%s,%s,--poll-error--' % (now_str(), msg__))
		printerr('---')
		printerr(xml_str_)
		printerr('---')
	try:
		r = xml.dom.minidom.parseString(xml_str_)
	except ExpatError:
		print_error('Failed to parse output from NextBus')
		raise
	if [e for e in r.documentElement.childNodes if e.nodeName.lower() == 'error']:
		print_error('Detected error(s) in output from NextBus (Will try to get data from this document regardless)')
	return r

def dump_xml(fout_, route_, time_es_, xml_headers_, data_str_):
	if xml_headers_:
		cur_time = now_em()
		cur_timestr = em_to_str(now_em())
		print >> fout_, 'Route %s, t=%d.  (Current time: %d / %s.)' % (route_, time_es_, cur_time, cur_timestr)
	print >> fout_, data_str_

def test_parse_xml_file(xml_filename_):
	with open(xml_filename_) as fin:
		xml_str = fin.read()
	xmldoc = parse_xml(xml_str)
	deal_with_xml(xmldoc, False, 'stdout')

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
				print vi.str_long()
		else:
			with open(vis_filename_, 'a') as fout:
				for vi in vehicles:
					print >> fout, vi.str_long()

	return nextbus_lasttime

# Some configroutes are polled more than once per cycle - if they belong to more than one fudgeroute.  Oh well. 
def poll_once(froutes_, insert_into_db_, pollstate_filename_, xml_filename_, xml_headers_, vis_filename_, forever_, 
		touch_flag_files_on_finish_):
	allroutes_start_wallclock_time = now_em()
	try:
		with open(pollstate_filename_) as fin:
			croute_to_time = json.load(fin)
	except:
		croute_to_time = {}
	for froutei, froute in enumerate(froutes_):
		if forever_:
			next_route_ideal_wallclock_time = allroutes_start_wallclock_time + (froutei+1)*60*1000/len(froutes_)
		for croute in routes.FUDGEROUTE_TO_CONFIGROUTES[froute]:
			try:
				nextbus_lasttime = croute_to_time[croute] if croute in croute_to_time else 0
				croute_to_time[croute] = get_data_from_web_and_deal_with_it(
						croute, nextbus_lasttime, insert_into_db_, xml_filename_, xml_headers_, vis_filename_)
			except Exception, e:
				printerr('%s,error getting configroute %s,--poll-error--' % (now_str_millis(), croute))
				traceback.print_exc(e)
		if touch_flag_files_on_finish_:
			touch('/tmp/ttc-poll-locations-finished-flag-%s' % froute)
		if forever_:
			if froutei < len(froutes_)-1 and next_route_ideal_wallclock_time > now_em():
				time.sleep((next_route_ideal_wallclock_time - now_em())/1000.0)
		with open(pollstate_filename_, 'w') as fout:
			json.dump(croute_to_time, fout, indent=0)

def get_data_from_web_and_deal_with_it(route_, nextbus_lasttime_, insert_into_db_, xml_filename_, xml_headers_, vis_filename_):
	data_xmldoc = get_data_from_web_as_xml(route_, nextbus_lasttime_, xml_filename_, xml_headers_)
	r = deal_with_xml(data_xmldoc, insert_into_db_, vis_filename_)
	return r

def get_graphs_into_ram():
	# Reading these large snapgraphs into memory before the first time we poll 
	# NextBus because it's slightly smarter.  If we don't - i.e. poll NextBus 
	# THEN read these large snapgraphs into memory (which takes 20 seconds or 
	# more) on first use, then the data for those first routes polled will 
	# be eg. 20 seconds more out of date than it needs to be.  
	tracks.get_snapgraph()
	streets.get_snapgraph()

def wait_until_start_of_next_minute(max_secs_to_sleep_=61):
	now = now_em()
	target_time = round_up_by_minute(now)
	secs_to_sleep = min((target_time - now)/1000.0, max_secs_to_sleep_)
	time.sleep(secs_to_sleep)

if __name__ == '__main__':

	if len(sys.argv) >= 2 and sys.argv[1] == '--testfile':
		test_parse_xml_file(sys.argv[2])
	else:
		opts, args = getopt.getopt(sys.argv[1:], '', ['routes=', 'pollstatefile=', 'redirect-stdstreams-to-file', 
				'dont-insert-into-db', 'touch-flag-files-on-finish', 'dump-xml=', 'dump-vis=', 'xml-headers', 'forever'])
		if args:
			sys.exit('No arguments allowed.  Only options.')

		pollstate_filename = (get_opt(opts, 'pollstatefile') or 'pollstate.json')

		if get_opt(opts, 'redirect-stdstreams-to-file'):
			redirect_stdstreams_to_file('poll_locations_')

		if get_opt(opts, 'routes'):
			routelist = get_opt(opts, 'routes').split(',')
		else:
			routelist = list(routes.NON_SUBWAY_FUDGEROUTES)

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
		xml_headers = get_opt(opts, 'xml-headers')
		touch_flag_files_on_finish = get_opt(opts, 'touch-flag-files-on-finish')
		forever = get_opt(opts, 'forever')

		if forever:
			get_graphs_into_ram()

		def call_poll_once():
			poll_once(routelist, insert_into_db, pollstate_filename, xml_filename, xml_headers, vis_filename, forever, touch_flag_files_on_finish)
		if forever:
			wait_until_start_of_next_minute()
			while True:
				call_poll_once()
				wait_until_start_of_next_minute(20)
		else:
			call_poll_once()
		

