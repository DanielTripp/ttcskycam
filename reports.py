#!/usr/bin/python2.6

from collections import *
import os, os.path, json, getopt
import vinfo, db, routes, geom, mc, yards, traffic, c, util
from misc import *

GET_CURRENT_REPORTS_FROM_DB = os.path.exists('GET_CURRENT_REPORTS_FROM_DB')
DISALLOW_HISTORICAL_REPORTS = os.path.exists('DISALLOW_HISTORICAL_REPORTS')

# returns JSON. 
# dir_ can be an int (0 or 1) or a latlng pair.
# The returned JSON is a list containing three things - [0] time string of data, [1] the data, and [2] direction returned. 
# if the dir_ arg is 0 or 1 then [2] will be the same as the dir_  arg, 
# but if the dir_ arg is a latlng pair then [2] wil be more informative. 
def get_report(report_type_, froute_, dir_, time_, last_gotten_timestr_, log_=False):
	assert report_type_ in ('traffic', 'locations')
	assert isinstance(froute_, basestring) and (time_ == 0 or abs(str_to_em(time_) - now_em()) < 1000*60*60*24*365*10)
	assert (dir_ in (0, 1)) or (len(dir_) == 2 and all(isinstance(e, geom.LatLng) for e in dir_))
	assert (last_gotten_timestr_ is None) or isinstance(last_gotten_timestr_, basestring)
	if dir_ in (0, 1):
		direction = dir_
	else:
		direction = routes.routeinfo(froute_).dir_from_latlngs(dir_[0], dir_[1])
	if time_ == 0:
		return get_current_report(report_type_, froute_, direction, last_gotten_timestr_, log_=log_)
	else:
		return get_historical_report(report_type_, froute_, direction, str_to_em(time_), log_=log_)

def get_historical_report(report_type_, froute_, dir_, time_, log_=False):
	assert isinstance(time_, long)
	if DISALLOW_HISTORICAL_REPORTS:
		raise Exception('Historical reports are disallowed.')
	time_arg = round_down_by_minute(time_)
	return calc_report(report_type_, froute_, dir_, time_arg)

def get_current_report(report_type_, froute_, dir_, last_gotten_timestr_, log_=False):
	if GET_CURRENT_REPORTS_FROM_DB:
		return get_current_report_from_db(report_type_, froute_, dir_, last_gotten_timestr_, log_=log_)
	else:
		return calc_current_report(report_type_, froute_, dir_, last_gotten_timestr_)

def calc_current_report(report_type_, froute_, dir_, last_gotten_timestr_):
	time_arg = round_down_by_minute(now_em())
	if (last_gotten_timestr_ is not None) and (str_to_em(last_gotten_timestr_) == time_arg):
		return util.to_json_str((em_to_str(time_arg), None, dir_))
	else:
		return calc_report(report_type_, froute_, dir_, time_arg)

def calc_report(report_type_, froute_, dir_, time_):
	assert isinstance(time_, long) and (time_ != 0)
	if report_type_ == 'traffic':
		report_data_obj = traffic.get_traffics_impl(froute_, dir_, time_)
	elif report_type_ == 'locations':
		report_data_obj = traffic.get_recent_vehicle_locations_impl(froute_, dir_, time_)
	else:
		assert False
	return util.to_json_str((em_to_str(time_), report_data_obj, dir_))

def get_current_report_from_db(report_type_, froute_, dir_, last_gotten_timestr_, log_=False):
	last_gotten_time = (None if last_gotten_timestr_ is None else str_to_em(last_gotten_timestr_))
	now_epoch_millis = now_em()
	cur_time_rounded_up = round_up_by_minute(now_epoch_millis)
	if cur_time_rounded_up == last_gotten_time:
		return (last_gotten_timestr_, None, dir_)
	else:
		# db.get_report() is memcached, so it's our first choice, for performance reasons.  (Will avoid hitting db): 
		try:
			report_json = db.get_report(report_type_, froute_, dir_, cur_time_rounded_up)
			return '[%s, %s, %d]' % (json.dumps(em_to_str(cur_time_rounded_up)), report_json, dir_)
		except db.ReportNotFoundException:
			cur_time_rounded_down = round_down_by_minute(now_epoch_millis)
			if cur_time_rounded_down == last_gotten_time:
				return (last_gotten_timestr_, None)
			else:
				try:
					report_json = db.get_report(report_type_, froute_, dir_, cur_time_rounded_down)
					return '[%s, %s, %d]' % (json.dumps(em_to_str(cur_time_rounded_down)), report_json, dir_)
				except db.ReportNotFoundException:
					# But maybe the reports in the database are lagging behind by a couple of minutes for some reason.  
					# Here we gracefully degrade in that scenario, and return the most recent report that we do have, within reason. 
					report_time_str, report_json = db.get_latest_report(report_type_, froute_, dir_)
					if str_to_em(report_time_str) == last_gotten_time:
						return (last_gotten_timestr_, None, dir_)
					else:
						return '[%s, %s, %d]' % (json.dumps(report_time_str), report_json, dir_)

def get_traffic_report(froute_, dir_, time_, last_gotten_timestr_, log_=False):
	return get_report('traffic', froute_, dir_, time_, last_gotten_timestr_, log_=log_)

def get_locations_report(froute_, dir_, time_, last_gotten_timestr_, log_=False):
	return get_report('locations', froute_, dir_, time_, last_gotten_timestr_, log_=log_)






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
	MAX_WAIT_MINS = 1
	t0 = time.time()
	mtime0 = get_poll_finished_flag_file_mtime()
	mtime1 = mtime0
	while True:
		mtime1 = get_poll_finished_flag_file_mtime()
		if mtime1 != mtime0:
			break
		time.sleep(2)
		if (time.time() - t0) > 60*MAX_WAIT_MINS:
			raise Exception('reports: poll locations flag file was not touched in %d minute(s).' % MAX_WAIT_MINS)
	return (mtime0, mtime1)

def make_all_reports_and_insert_into_db():
	report_time = round_up_by_minute(now_em())
	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		for direction in (0, 1):
			traffic_data = traffic.get_traffics_impl(froute, direction, report_time)
			db.insert_report('traffic', froute, direction, report_time, traffic_data)
			locations_data = traffic.get_recent_vehicle_locations_impl(froute, direction, report_time)
			db.insert_report('locations', froute, direction, report_time, locations_data)

def check_last_reports_finished_time(prev_poll_finish_time_, cur_poll_finish_time_):
	last_reports_finish_time = get_reports_finished_flag_file_mtime()
	if last_reports_finish_time != 0:
		if not (prev_poll_finish_time_ <= last_reports_finish_time <= cur_poll_finish_time_):
			print 'Last round of reports seems not to have finished yet.'
			print 'Previous poll finish time: %s, current finish time: %s, last reports finish time: %s' % \
					(em_to_str(t) for t in (prev_poll_finish_time_, cur_poll_finish_time_, last_reports_finish_time))
			sys.exit(1)

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['dont-wait-for-poll-to-finish'])
	if not get_opt(opts, 'dont-wait-for-poll-to-finish'):
		prev_poll_finish_time, cur_poll_finish_time = wait_for_locations_poll_to_finish()
	else:
		prev_poll_finish_time, cur_poll_finish_time = (0, now_em())
	check_last_reports_finished_time(prev_poll_finish_time, cur_poll_finish_time)
	make_all_reports_and_insert_into_db()
	touch('/tmp/ttc-reports-version-%s-finished-flag' % (c.VERSION))


