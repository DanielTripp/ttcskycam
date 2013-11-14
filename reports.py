#!/usr/bin/python2.6

from collections import *
import sys, os, os.path, json, getopt
import vinfo, db, routes, geom, mc, yards, traffic, c, util
from misc import *

GET_CURRENT_REPORTS_FROM_DB = os.path.exists('GET_CURRENT_REPORTS_FROM_DB')
DISALLOW_HISTORICAL_REPORTS = os.path.exists('DISALLOW_HISTORICAL_REPORTS')

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
	assert isinstance(froute_, basestring) and (time_ == 0 or abs(str_to_em(time_) - now_em()) < 1000*60*60*24*365*10)
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
	return calc_report(report_type_, froute_, dir_, datazoom_, time_arg)

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
		return calc_report(report_type_, froute_, dir_, datazoom_, time_arg)

def calc_report(report_type_, froute_, dir_, datazoom_, time_):
	assert isinstance(time_, long) and (time_ != 0)
	if report_type_ == 'traffic':
		report_data_obj = traffic.get_traffics_impl(froute_, dir_, datazoom_, time_)
	elif report_type_ == 'locations':
		report_data_obj = traffic.get_recent_vehicle_locations_impl(froute_, dir_, datazoom_, time_)
	else:
		assert False
	return util.to_json_str((em_to_str(time_), report_data_obj, dir_))

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
	MAX_WAIT_SECS = 60*2
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

		if (cur_wait_secs >= MAX_WAIT_SECS) and (prev_wait_secs < MAX_WAIT_SECS):
			printerr('%s: reports: watched poll locations flag file for %d seconds, still hasn\'t been touched.' % (now_str(), MAX_WAIT_SECS))
			
		time.sleep(2)

	if cur_wait_secs > MAX_WAIT_SECS:
		printerr('%s: reports: watched poll locations flag file for %d seconds before it was touched.' % (now_str(), cur_wait_secs))

def make_all_reports_and_insert_into_db_once():
	report_time = round_up_by_minute(now_em())
	for froute in sorted(FROUTES):
		for direction in (0, 1):
			reporttype_to_datazoom_to_reportdataobj = defaultdict(lambda: {})
			for datazoom in c.VALID_DATAZOOMS:
				try:
					traffic_data = traffic.get_traffics_impl(froute, direction, datazoom, report_time)
					reporttype_to_datazoom_to_reportdataobj['traffic'][datazoom] = traffic_data
					locations_data = traffic.get_recent_vehicle_locations_impl(froute, direction, datazoom, report_time)
					reporttype_to_datazoom_to_reportdataobj['locations'][datazoom] = locations_data
				except:
					printerr('%s: Problem during %s / dir=%d / datazoom=%d' % (now_str(), froute, direction, datazoom))
					raise
			db.insert_reports(froute, direction, report_time, reporttype_to_datazoom_to_reportdataobj)

def make_all_reports_and_insert_into_db_forever():
	routes.prime_routeinfos()
	i = 0
	while True:
		wait_for_locations_poll_to_finish()
		t0 = time.time()
		make_all_reports_and_insert_into_db_once()
		t1 = time.time()
		reports_took_secs = t1 - t0
		if reports_took_secs > 60:
			printerr('Reports took too long to generate - %s seconds.  (Finished at %s.)' % (int(reports_took_secs), now_str()))
		i += 1
		if i % 10 == 0:
			mc.clear_in_process_cache() # Avoid memory leak.  This cache will contain (among other things) 
					# all the reports we make, and will grow indefinitely.


if __name__ == '__main__':

	if len(sys.argv) == 2 and sys.argv[1] == '--once':
		make_all_reports_and_insert_into_db_once()
	else:
		make_all_reports_and_insert_into_db_forever()


