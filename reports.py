#!/cygdrive/c/Python27/python.exe

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
import vinfo, db, routes, geom, mc, yards, traffic, c, util, streets, tracks
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






def get_poll_finished_flag_file_mtime(froute_):
	filename = '/tmp/ttc-poll-locations-finished-flag-%s' % froute_
	if os.path.exists(filename):
		return int(os.path.getmtime(filename)*1000)
	else:
		return 0

# arg froute_to_poll_file_mtime_ we modify this. 
# arg froute_to_last_complain_wallclock_time_ we modify this. 
def wait_for_a_location_poll_to_finish(froute_to_poll_file_mtime_, froute_to_last_complain_wallclock_time_, 
		froutes_left_in_round_, poll_file_watching_start_time_):
	assert set(froute_to_poll_file_mtime_.keys()) == set(routes.NON_SUBWAY_FUDGEROUTES)
	MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS = 90
	while True:
		r = None
		
		changed_froutes_n_mtimes = []
		for froute in (froute for froute in routes.NON_SUBWAY_FUDGEROUTES if froute in froutes_left_in_round_):
			mtime = get_poll_finished_flag_file_mtime(froute)
			if mtime != froute_to_poll_file_mtime_[froute]:
				changed_froutes_n_mtimes.append((froute, mtime))

		if changed_froutes_n_mtimes:
			changed_froutes_n_mtimes.sort(key=lambda x: x[1])
			r, mtime = changed_froutes_n_mtimes[0]
			froute_to_poll_file_mtime_[r] = mtime

		for froute in routes.NON_SUBWAY_FUDGEROUTES:
			wait_time_secs = (now_em() - max(get_poll_finished_flag_file_mtime(froute), poll_file_watching_start_time_))/1000
			if wait_time_secs > MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS:
				if froute not in froute_to_last_complain_wallclock_time_ or now_em() - froute_to_last_complain_wallclock_time_[froute] > 60*1000:
					printerr('%s,reports: watched %s poll locations flag file for %d seconds, still hasn\'t been touched,--poll-slow--' % \
							(now_str(), froute, wait_time_secs))
					froute_to_last_complain_wallclock_time_[froute] = now_em()

		if r is not None:
			return r

		time.sleep(0.5)

g_froute_to_times = None

def make_reports_single_route(report_time_, froute_, insert_into_db_, insert_db_dupes_, datazooms_, make_traffic_report_, make_locations_report_):
	global g_froute_to_times
	if LOG_INDIV_ROUTE_TIMES:
		t0 = time.time()
	got_errors = False
	for direction in (0, 1):
		reporttype_to_datazoom_to_reportdataobj = defaultdict(lambda: {})
		for datazoom in datazooms_:
			if make_traffic_report_:
				assert False # letting this code (i.e. all of traffic reports) go unmaintained 
				try:
					traffic_data = traffic.get_traffics_impl(froute_, direction, datazoom, report_time_)
					reporttype_to_datazoom_to_reportdataobj['traffic'][datazoom] = traffic_data
				except:
					printerr('%s,error generating traffic report for %s / %s / dir=%d / datazoom=%d,--generate-error--' % (now_str(), em_to_str(report_time_), froute_, direction, datazoom))
					traceback.print_exc()
					got_errors = True
			if make_locations_report_ and we_should_calc_report(insert_into_db_, insert_db_dupes_, 'locations', froute_, direction, datazoom, report_time):
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

def we_should_calc_report(insert_into_db_, insert_db_dupes_, report_type_, froute_, dir_, datazoom_, time_):
	if not insert_into_db_:
		return True
	else:
		if insert_db_dupes_:
			return True
		else:
			return not db.does_report_exist_in_db(report_type_, froute_, dir_, datazoom_, time_)

def get_init_froute_to_poll_file_mtime():
	froute_to_poll_file_mtime = {}
	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		froute_to_poll_file_mtime[froute] = get_poll_finished_flag_file_mtime(froute)
	return froute_to_poll_file_mtime

def make_all_reports_forever(redir_, insert_into_db_):
	routes.prime_routeinfos()
	prime_graphs()
	froute_to_poll_file_mtime = get_init_froute_to_poll_file_mtime()
	froute_to_last_complain_wallclock_time = {}
	poll_file_watching_start_time = now_em()
	froutes_left_in_round = set(routes.NON_SUBWAY_FUDGEROUTES)
	all_reports_in_round_generate_time_secs = 0.0
	while True:
		froute = wait_for_a_location_poll_to_finish(froute_to_poll_file_mtime, froute_to_last_complain_wallclock_time, 
				froutes_left_in_round, poll_file_watching_start_time)
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

def make_all_reports_once(report_time_, insert_into_db_, insert_db_dupes_, froutes_, datazooms_):
	assert isinstance(froutes_, list)
	got_errors = False
	for froute in froutes_:
		got_errors |= make_reports_single_route(report_time_, froute, insert_into_db_, insert_db_dupes_, datazooms_, False, True)
	if got_errors:
		sys.exit(37)

def prime_graphs():
	tracks.get_snapgraph()
	streets.get_snapgraph()

def generate_backfill_report_times(start_time_, end_time_):
	step_in_minutes = 15
	start_time, end_time = (round_down_by_minute_step(e, step_in_minutes) for e in (start_time_, end_time_))
	cur_time = start_time
	while cur_time < end_time:
		yield cur_time
		cur_time += 1000L*60*step_in_minutes
		# ^^ This code might have bugs w.r.t. DST and/or leap seconds. 
		assert cur_time == round_down_by_minute_step(cur_time, step_in_minutes)

if __name__ == '__main__':

	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('--dont-insert-into-db', action='store_true')
	arg_parser.add_argument('--time')
	arg_parser.add_argument('--backfill-time-range')
	arg_parser.add_argument('--froutes')
	arg_parser.add_argument('--redir', action='store_true')
	args = arg_parser.parse_args()
	if args.time and args.backfill_time_range:
		raise Exception('Specifying both a single time and a time range is not supported')
	if args.time is not None and args.redir:
		raise Exception('redir not supported when doing a single time.')

	froutes = routes.NON_SUBWAY_FUDGEROUTES if args.froutes is None else args.froutes.split(',')
	insert_into_db = not args.dont_insert_into_db
	if args.time is not None:
		report_time = long(round_down_by_minute(now_em()) if args.time == 'now' else str_to_em(args.time))
		datazooms = [max(c.VALID_DATAZOOMS)]
		make_all_reports_once(report_time, insert_into_db, False, froutes, datazooms)
	elif args.backfill_time_range is not None:
		start_time_em, end_time_em = (str_to_em(e) for e in args.backfill_time_range.split(',', 1))
		# ^^ This code ignores time zones and DST, and probably has bugs. 
		datazooms = [max(c.VALID_DATAZOOMS)]
		for report_time in generate_backfill_report_times(start_time_em, end_time_em):
			print 'Backfilling reports for %s.' % em_to_str(report_time)
			insert_db_dupes = False
			make_all_reports_once(report_time, insert_into_db, insert_db_dupes, froutes, datazooms)
	else:
		make_all_reports_forever(args.redir, insert_into_db)


