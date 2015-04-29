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

from collections import *
import sys, os, os.path, json, argparse, traceback, time, pprint
import vinfo, db, routes, geom, mc, yards, traffic, c, util, multiproc, streets, tracks
from misc import *

GET_CURRENT_REPORTS_FROM_DB = os.path.exists('GET_CURRENT_REPORTS_FROM_DB')
GET_HISTORICAL_REPORTS_FROM_DB = os.path.exists('GET_HISTORICAL_REPORTS_FROM_DB')
DISALLOW_HISTORICAL_REPORTS = os.path.exists('DISALLOW_HISTORICAL_REPORTS')
LOG_INDIV_ROUTE_TIMES = False

if os.path.exists('MAKE_REPORTS_FROUTES'):
	with open('MAKE_REPORTS_FROUTES') as fin:
		FROUTES = json.load(fin)
		FROUTES = [str(e) for e in FROUTES] # getting rid of unicode 
else:
	FROUTES = routes.NON_SUBWAY_FUDGEROUTES

# returns JSON. 
# dir_ can be an int (0 or 1) or a latlng pair.
# The returned JSON is a list containing three things - [0] time string of data, [1] the data, and [2] direction returned. 
# if the dir_ arg is 0 or 1 then [2] will be the same as the dir_  arg, 
# but if the dir_ arg is a latlng pair then [2] wil be more informative. 
def get_report(report_type_, froute_, dir_, datazoom_, time_, last_gotten_timestr_, log_=False):
	assert report_type_ in ('traffic', 'locations')
	assert isinstance(froute_, basestring) and (time_ == 0 or abs(str_to_em(time_) - now_em()) < 1000*60*60*24*365*100)
	assert (dir_ in (0, 1)) or (len(dir_) == 2 and all(isinstance(e, geom.LatLng) for e in dir_))
	assert (last_gotten_timestr_ is None) or isinstance(last_gotten_timestr_, basestring)
	assert datazoom_ in c.VALID_DATAZOOMS 
	if dir_ in (0, 1):
		direction = dir_
	else:
		direction = routes.routeinfo(froute_).dir_from_latlngs(dir_[0], dir_[1])
	if time_ == 0:
		return get_current_report(report_type_, froute_, direction, datazoom_, last_gotten_timestr_, log_=log_)
	else:
		return get_historical_report(report_type_, froute_, direction, datazoom_, str_to_em(time_), log_=log_)

def get_historical_report(report_type_, froute_, dir_, datazoom_, time_, log_=False):
	assert isinstance(time_, long)
	if DISALLOW_HISTORICAL_REPORTS:
		raise Exception('Historical reports are disallowed.')
	time_arg = round_down_by_minute(time_)
	if GET_HISTORICAL_REPORTS_FROM_DB:
		return get_historical_report_from_db(report_type_, froute_, dir_, datazoom_, time_)
	else:
		return calc_report_json(report_type_, froute_, dir_, datazoom_, time_arg)

def get_current_report(report_type_, froute_, dir_, datazoom_, last_gotten_timestr_, log_=False):
	if GET_CURRENT_REPORTS_FROM_DB:
		return get_current_report_from_db(report_type_, froute_, dir_, datazoom_, last_gotten_timestr_, log_=log_)
	else:
		return calc_current_report(report_type_, froute_, dir_, datazoom_, last_gotten_timestr_)

def calc_current_report(report_type_, froute_, dir_, datazoom_, last_gotten_timestr_):
	time_arg = round_down_by_minute(now_em())
	if (last_gotten_timestr_ is not None) and (str_to_em(last_gotten_timestr_) == time_arg):
		return util.to_json_str((em_to_str(time_arg), None, dir_))
	else:
		return calc_report_json(report_type_, froute_, dir_, datazoom_, time_arg)

def calc_report_obj(report_type_, froute_, dir_, datazoom_, time_, log_=False):
	assert isinstance(time_, long) and (time_ != 0)
	if report_type_ == 'traffic':
		return traffic.get_traffics_impl(froute_, dir_, datazoom_, time_, log_=log_)
	elif report_type_ == 'locations':
		return traffic.get_recent_vehicle_locations_impl(froute_, dir_, datazoom_, time_, log_=log_)
	else:
		assert False

def calc_report_json(report_type_, froute_, dir_, datazoom_, time_):
	assert isinstance(time_, long) and (time_ != 0)
	report_obj = calc_report_obj(report_type_, froute_, dir_, datazoom_, time_)
	return util.to_json_str((em_to_str(time_), report_obj, dir_))

def get_current_report_from_db(report_type_, froute_, dir_, datazoom_, last_gotten_timestr_, log_=False):
	last_gotten_time = (None if last_gotten_timestr_ is None else str_to_em(last_gotten_timestr_))
	now_epoch_millis = now_em()
	cur_time_rounded_up = round_up_by_minute(now_epoch_millis)
	if cur_time_rounded_up == last_gotten_time:
		return (last_gotten_timestr_, None, dir_)
	else:
		latest_report_time = db.get_latest_report_time(froute_, dir_)
		if latest_report_time == last_gotten_time:
			return (last_gotten_timestr_, None, dir_)
		else:
			report_json = db.get_report(report_type_, froute_, dir_, datazoom_, latest_report_time)
			return '[%s, %s, %d]' % (json.dumps(em_to_str(latest_report_time)), report_json, dir_)

def get_historical_report_from_db(report_type_, froute_, dir_, datazoom_, time_):
	report_json = db.get_report(report_type_, froute_, dir_, datazoom_, time_)
	return '[%s, %s, %d]' % (json.dumps(em_to_str(time_)), report_json, dir_)

# return: JSON string.  array.  elements of it: [time, data, direction].  data = [visuals, speeds]. 
def get_traffic_report(froute_, dir_, datazoom_, time_, last_gotten_timestr_, log_=False):
	return get_report('traffic', froute_, dir_, datazoom_, time_, last_gotten_timestr_, log_=log_)

def get_locations_report(froute_, dir_, datazoom_, time_, last_gotten_timestr_, log_=False):
	return get_report('locations', froute_, dir_, datazoom_, time_, last_gotten_timestr_, log_=log_)






def get_reports_finished_flag_file_mtime():
	filename = '/tmp/ttc-reports-version-%s-finished-flag' % (c.VERSION)
	if os.path.exists(filename):
		return os.path.getmtime(filename)
	else:
		return 0

def get_poll_finished_flag_file_mtime(froute_):
	filename = '/tmp/ttc-poll-locations-finished-flag-%s' % froute_
	if os.path.exists(filename):
		return int(os.path.getmtime(filename)*1000)
	else:
		return 0

# arg froute_to_poll_file_mtime_ we modify this. 
# arg stale_froutes_ we modify this. 
def wait_for_a_location_poll_to_finish(froute_to_poll_file_mtime_, stale_froutes_, poll_file_watching_start_time_):
	assert set(froute_to_poll_file_mtime_.keys()) == set(routes.NON_SUBWAY_FUDGEROUTES)
	MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS = 90
	while True:
		r = None
		
		changed_froutes_n_mtimes = []
		for froute in routes.NON_SUBWAY_FUDGEROUTES:
			mtime = get_poll_finished_flag_file_mtime(froute)
			if mtime != froute_to_poll_file_mtime_[froute]:
				changed_froutes_n_mtimes.append((froute, mtime))

		if changed_froutes_n_mtimes:
			changed_froutes_n_mtimes.sort(key=lambda x: x[1])
			r, mtime = changed_froutes_n_mtimes[0]
			if r in stale_froutes_:
				wait_time_secs = (now_em() - max(froute_to_poll_file_mtime_[r], poll_file_watching_start_time_))/1000
				printerr('%s,reports: watched %s poll locations flag file for %d seconds before it was touched,--poll-slow--' % \
						(now_str(), r, wait_time_secs))
				stale_froutes_.remove(r)
			froute_to_poll_file_mtime_[r] = mtime

		for froute in routes.NON_SUBWAY_FUDGEROUTES:
			wait_time_secs = (now_em() - max(froute_to_poll_file_mtime_[froute], poll_file_watching_start_time_))/1000
			if wait_time_secs > MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS and froute not in stale_froutes_:
				stale_froutes_.add(froute)
				printerr('%s,reports: watched %s poll locations flag file for %d seconds, still hasn\'t been touched,--poll-slow--' % \
						(now_str(), froute, wait_time_secs))

		if r is not None:
			return r

		time.sleep(0.5)

g_froute_to_times = None

@multiproc.include_entire_traceback
def make_reports_single_route(report_time_, froute_, insert_into_db_):
	global g_froute_to_times
	if LOG_INDIV_ROUTE_TIMES:
		t0 = time.time()
	got_errors = False
	for direction in (0, 1):
		reporttype_to_datazoom_to_reportdataobj = defaultdict(lambda: {})
		for datazoom in c.VALID_DATAZOOMS:
			try:
				traffic_data = traffic.get_traffics_impl(froute_, direction, datazoom, report_time_)
				reporttype_to_datazoom_to_reportdataobj['traffic'][datazoom] = traffic_data
			except:
				printerr('%s,error generating traffic report for %s / %s / dir=%d / datazoom=%d,--generate-error--' % (now_str(), em_to_str(report_time_), froute_, direction, datazoom))
				traceback.print_exc()
				got_errors = True
			try:
				locations_data = traffic.get_recent_vehicle_locations_impl(froute_, direction, datazoom, report_time_)
				reporttype_to_datazoom_to_reportdataobj['locations'][datazoom] = locations_data
			except:
				printerr('%s,error generating locations report for %s / %s / dir=%d / datazoom=%d,--generate-error--' % (now_str(), em_to_str(report_time_), froute_, direction, datazoom))
				traceback.print_exc()
				got_errors = True
		if not got_errors and insert_into_db_:
			db.insert_reports(froute_, direction, report_time_, reporttype_to_datazoom_to_reportdataobj)
	if LOG_INDIV_ROUTE_TIMES:
		t1 = time.time()
		if g_froute_to_times is not None:
			g_froute_to_times[froute_].append(t1 - t0)
	return got_errors

def make_shardpool():
	return multiproc.ShardPool(shardfunc, 8)

# Dead code? 
def shardfunc(func_, args_):
	assert func_ == make_reports_single_route
	froute = args_[1]
	assert froute in routes.NON_SUBWAY_FUDGEROUTES
	froute_to_shard = {
			# These choices were arrived at by experiments: 
			'king': 5,
			'queen': 0,
			'dufferin': 1,
			'bathurst': 3,
			'keele': 7,
			'spadina': 2,
			'carlton': 6,
			'dundas': 4,
			'dupont': 4,
			'lansdowne': 5,
			'ossington': 6,
			'stclair': 7, 
			# These weren't: 
			'wellesley': 0, 
			'harbourfront': 1, 
			'sherbourne': 2, 
			'parliament': 3, 
			'symington': 4, 
			'davenport': 5, 
			'junction': 6, 
		}
	return froute_to_shard[froute]

def get_init_froute_to_poll_file_mtime():
	froute_to_poll_file_mtime = {}
	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		froute_to_poll_file_mtime[froute] = get_poll_finished_flag_file_mtime(froute)
	return froute_to_poll_file_mtime

def make_all_reports_forever(redir_, insert_into_db_):
	routes.prime_routeinfos()
	prime_graphs()
	froute_to_poll_file_mtime = get_init_froute_to_poll_file_mtime()
	stale_froutes = set()
	poll_file_watching_start_time = now_em()
	froutes_left_in_round = set(routes.NON_SUBWAY_FUDGEROUTES)
	all_reports_in_round_generate_time_secs = 0.0
	while True:
		froute = wait_for_a_location_poll_to_finish(froute_to_poll_file_mtime, stale_froutes, poll_file_watching_start_time)
		if redir_:
			redirect_stdstreams_to_file('reports_generation_')
		t0 = time.time()
		got_errors = make_reports_single_route(round_up_by_minute(now_em()), froute, insert_into_db_)
		t1 = time.time()
		report_generate_time_secs = t1 - t0
		if froute in froutes_left_in_round: # else: not all froutes flag files touched?  probably a bad sign, but what can we do about it.
			froutes_left_in_round.remove(froute)
			all_reports_in_round_generate_time_secs += report_generate_time_secs
			if not froutes_left_in_round:
				froutes_left_in_round = set(routes.NON_SUBWAY_FUDGEROUTES)
				printerr('%s,%d,%s,--generate-time--' % (now_str(), all_reports_in_round_generate_time_secs, c.VERSION))
				all_reports_in_round_generate_time_secs = 0.0
		if got_errors:
			sys.exit(37)
		sys.stdout.flush()
		sys.stderr.flush()

def make_all_reports_once(report_time_, insert_into_db_):
	got_errors = False
	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		got_errors |= make_reports_single_route(report_time_, froute, insert_into_db_)
	if got_errors:
		sys.exit(37)

def prime_graphs():
	tracks.get_snapgraph()
	streets.get_snapgraph()

if __name__ == '__main__':

	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('--dont-insert-into-db', action='store_true')
	arg_parser.add_argument('--time')
	arg_parser.add_argument('--redir', action='store_true')
	args = arg_parser.parse_args()
	if args.time is not None and args.redir:
		raise Exception('redir not allowed when doing a single time.')
	if LOG_INDIV_ROUTE_TIMES and args.multiproc == 'y':
		raise Exception('Don\'t know how to log individual route times when multiproc is on.')

	insert_into_db = not args.dont_insert_into_db
	if args.time is not None:
		report_time = (round_down_by_minute(now_em()) if args.time == 'now' else str_to_em(args.time))
		make_all_reports_once(report_time, insert_into_db)
	else:
		make_all_reports_forever(args.redir, insert_into_db)


