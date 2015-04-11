#!/usr/bin/python2.6

from collections import *
import sys, os, os.path, json, argparse, traceback, time
import vinfo, db, routes, geom, mc, yards, traffic, c, util, multiproc
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

def get_poll_finished_flag_file_mtime():
	filename = '/tmp/ttc-poll-locations-finished-flag'
	if os.path.exists(filename):
		return os.path.getmtime(filename)
	else:
		return 0

def wait_for_locations_poll_to_finish():
	MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS = 60*2
	t0 = time.time()
	mtime0 = get_poll_finished_flag_file_mtime()
	mtime1 = mtime0
	prev_wait_secs = 0; cur_wait_secs = 0
	while True:
		prev_wait_secs = cur_wait_secs
		cur_wait_secs = int(time.time() - t0)

		mtime1 = get_poll_finished_flag_file_mtime()
		if mtime1 != mtime0:
			break

		if (cur_wait_secs >= MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS) and (prev_wait_secs < MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS):
			printerr('%s - reports: watched poll locations flag file for %d seconds, still hasn\'t been touched.  --poll-slow--' % (now_str(), MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS))
			
		time.sleep(2)

	if cur_wait_secs > MAX_WAIT_SECS_BEFORE_WE_COMPLAIN_IN_THE_LOGS:
		printerr('%s - reports: watched poll locations flag file for %d seconds before it was touched.  --poll-slow--' % (now_str(), cur_wait_secs))

g_froute_to_times = None

def make_all_reports_and_insert_into_db_once(report_time_, shardpool_):
	global g_froute_to_times
	if shardpool_ is not None:
		got_errors_by_froute = shardpool_.map(make_reports_and_insert_into_db_single_route, [(report_time_, froute) for froute in FROUTES])
		got_errors = any(got_errors_by_froute)
	else:
		got_errors = False
		for froute in FROUTES:
			got_errors_this_froute = make_reports_and_insert_into_db_single_route(report_time_, froute)
			got_errors |= got_errors_this_froute
	if LOG_INDIV_ROUTE_TIMES:
		if g_froute_to_times is None:
			g_froute_to_times = defaultdict(list)
		for froute, times in g_froute_to_times.iteritems():
			printerr(froute, average(times))
	if got_errors:
		sys.exit(37)

@multiproc.include_entire_traceback
def make_reports_and_insert_into_db_single_route(report_time_, froute_):
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
				printerr('%s - error generating traffic report for %s / %s / dir=%d / datazoom=%d --generate-error--' % (now_str(), em_to_str(report_time_), froute_, direction, datazoom))
				traceback.print_exc()
				got_errors = True
			try:
				locations_data = traffic.get_recent_vehicle_locations_impl(froute_, direction, datazoom, report_time_)
				reporttype_to_datazoom_to_reportdataobj['locations'][datazoom] = locations_data
			except:
				printerr('%s - error generating locations report for %s / %s / dir=%d / datazoom=%d --generate-error--' % (now_str(), em_to_str(report_time_), froute_, direction, datazoom))
				traceback.print_exc()
				got_errors = True
		if not got_errors:
			db.insert_reports(froute_, direction, report_time_, reporttype_to_datazoom_to_reportdataobj)
	if LOG_INDIV_ROUTE_TIMES:
		t1 = time.time()
		if g_froute_to_times is not None:
			g_froute_to_times[froute_].append(t1 - t0)
	return got_errors

def make_shardpool():
	return multiproc.ShardPool(shardfunc, 8)

def shardfunc(func_, args_):
	assert func_ == make_reports_and_insert_into_db_single_route
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
		}
	return froute_to_shard[froute]

def make_all_reports_and_insert_into_db_forever(shardpool_, redir_):
	routes.prime_routeinfos()
	while True:
		wait_for_locations_poll_to_finish()
		if redir_:
			redirect_stdstreams_to_file('reports_generation_')
		t0 = time.time()
		make_all_reports_and_insert_into_db_once(round_up_by_minute(now_em()), shardpool_)
		t1 = time.time()
		reports_took_secs = t1 - t0
		printerr('%s,%d,%s,--generate-time--' % (now_str(), reports_took_secs, c.VERSION))
		sys.stdout.flush()
		sys.stderr.flush()

if __name__ == '__main__':

	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('--multiproc', choices=('y', 'n'), default='n')
	arg_parser.add_argument('--time')
	arg_parser.add_argument('--redir', action='store_true')
	args = arg_parser.parse_args()
	if args.time is not None and args.redir:
		raise Exception('redir not allowed when doing a single time.')
	if LOG_INDIV_ROUTE_TIMES and args.multiproc == 'y':
		raise Exception('Don\'t know how to log individual route times when multiproc is on.')

	shardpool = (make_shardpool() if args.multiproc == 'y' else None)
	if args.time is not None:
		report_time = (round_down_by_minute(now_em()) if args.time == 'now' else str_to_em(args.time))
		make_all_reports_and_insert_into_db_once(report_time, shardpool)
	else:
		make_all_reports_and_insert_into_db_forever(shardpool, args.redir)


