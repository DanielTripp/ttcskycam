#!/usr/bin/python2.6

from collections import *
import os, os.path, json, getopt
import vinfo, db, routes, geom, mc, yards, traffic, c, util
from misc import *

GET_CURRENT_REPORTS_FROM_DB = os.path.exists('GET_CURRENT_REPORTS_FROM_DB')
DISALLOW_HISTORICAL_REPORTS = os.path.exists('DISALLOW_HISTORICAL_REPORTS')

# returns JSON. 
def get_report(report_type_, froute_, dir_, time_, last_gotten_timestr_, log_=False):
	assert report_type_ in ('traffic', 'locations')
	assert isinstance(froute_, basestring) and (dir_ in (0, 1)) and (time_ == 0 or abs(str_to_em(time_) - now_em()) < 1000*60*60*24*365*10)
	assert (last_gotten_timestr_ is None) or isinstance(last_gotten_timestr_, basestring)
	if time_ == 0:
		return get_current_report(report_type_, froute_, dir_, last_gotten_timestr_, log_=log_)
	else:
		return get_historical_report(report_type_, froute_, dir_, str_to_em(time_), log_=log_)

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
		return util.to_json_str((em_to_str(time_arg), None))
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
	return util.to_json_str((em_to_str(time_), report_data_obj))

def get_current_report_from_db(report_type_, froute_, dir_, last_gotten_timestr_, log_=False):
	last_gotten_time = (None if last_gotten_timestr_ is None else str_to_em(last_gotten_timestr_))
	now_epoch_millis = now_em()
	cur_time_rounded_up = round_up_by_minute(now_epoch_millis)
	if cur_time_rounded_up == last_gotten_time:
		return (last_gotten_timestr_, None)
	else:
		# db.get_report() is memcached, so it's our first choice, for performance reasons.  (Will avoid hitting db): 
		try:
			report_json = db.get_report(report_type_, froute_, dir_, cur_time_rounded_up)
			return '[%s, %s]' % (json.dumps(em_to_str(cur_time_rounded_up)), report_json)
		except db.ReportNotFoundException:
			cur_time_rounded_down = round_down_by_minute(now_epoch_millis)
			if cur_time_rounded_down == last_gotten_time:
				return (last_gotten_timestr_, None)
			else:
				try:
					report_json = db.get_report(report_type_, froute_, dir_, cur_time_rounded_down)
					return '[%s, %s]' % (json.dumps(em_to_str(cur_time_rounded_down)), report_json)
				except db.ReportNotFoundException:
					# But maybe the reports in the database are lagging behind by a couple of minutes for some reason.  
					# Here we gracefully degrade in that scenario, and return the most recent report that we do have, within reason. 
					report_time_str, report_json = db.get_latest_report(report_type_, froute_, dir_)
					if str_to_em(report_time_str) == last_gotten_time:
						return (last_gotten_timestr_, None)
					else:
						return '[%s, %s]' % (json.dumps(report_time_str), report_json)

def get_traffic_report(froute_, dir_, time_, last_gotten_timestr_, log_=False):
	return get_report('traffic', froute_, dir_, time_, last_gotten_timestr_, log_=log_)

def get_locations_report(froute_, dir_, time_, last_gotten_timestr_, log_=False):
	return get_report('locations', froute_, dir_, time_, last_gotten_timestr_, log_=log_)







def get_flag_file_mtime():
	filename = '/tmp/ttc-poll-locations-finished-flag'
	if os.path.exists(filename):
		return os.path.getmtime(filename)
	else:
		return None

def wait_for_locations_poll_to_finish():
	MAX_WAIT_MINS = 5
	t0 = time.time()
	mtime0 = get_flag_file_mtime()
	while True:
		mtime1 = get_flag_file_mtime()
		if mtime1 != mtime0:
			break
		time.sleep(2)
		if (time.time() - t0) > 60*MAX_WAIT_MINS:
			raise Exception('poll locations flag file was not touched in %d minutes.' % MAX_WAIT_MINS)

def make_all_reports_and_insert_into_db():
	report_time = round_up_by_minute(now_em())
	for froute in routes.NON_SUBWAY_FUDGEROUTES:
		for direction in (0, 1):
			traffic_data = traffic.get_traffics_impl(froute, direction, report_time)
			db.insert_report('traffic', froute, direction, report_time, traffic_data)
			locations_data = traffic.get_recent_vehicle_locations_impl(froute, direction, report_time)
			db.insert_report('locations', froute, direction, report_time, locations_data)


if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['dont-wait-for-poll-to-finish'])
	if not get_opt(opts, 'dont-wait-for-poll-to-finish'):
		wait_for_locations_poll_to_finish()
	make_all_reports_and_insert_into_db()


