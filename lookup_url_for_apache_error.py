#!/usr/bin/env python

import sys, re, os, subprocess, time
from misc import *

if __name__ == '__main__':

	ACCESS_LOG_TIME_FORMAT = '%d/%b/%Y:%H:%M:%S'

	def get_log_file_for_timestamp(file_prefix_, timestamp_):
		timestamp_epochsecs = time.mktime(timestamp_)
		logs_dir = '/var/log/apache2'
		access_log_files = [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.startswith(file_prefix_)]
		access_log_files.sort(key=lambda f: os.stat(f).st_mtime)
		access_log_files = [f for f in access_log_files if os.stat(f).st_mtime >= timestamp_epochsecs]
		if not access_log_files:
			return None
		else:
			return access_log_files[0]

	def get_error_log_filename(err_line_timestamp_):
		return get_log_file_for_timestamp('error', err_line_timestamp_)

	def get_access_log_filename(access_line_timestamp_):
		return get_log_file_for_timestamp('access', access_line_timestamp_)

	def get_timestamp_str_from_access_log_line(line_):
		return line_.split(' ')[3][1:]

	def get_access_log_line(ip_addr_, timestamp_):
		timestamp_in_access_log_format = time.strftime(ACCESS_LOG_TIME_FORMAT, timestamp_)
		access_log_filename = get_access_log_filename(timestamp_)
		if not access_log_filename:
			return None
		r = None
		with open(access_log_filename) as access_log_fin:
			for access_log_line in access_log_fin:
				if access_log_line.startswith(ip_addr_) \
						and timestamp_in_access_log_format == get_timestamp_str_from_access_log_line(access_log_line):
					r = access_log_line.rstrip()
					break
		return r

	def get_possible_access_log_lines(ip_addr_, err_log_timestamp_):
		access_log_filename = get_access_log_filename(err_log_timestamp_)
		if not access_log_filename:
			return None
		r = []
		with open(access_log_filename) as access_log_fin:
			for access_log_line in access_log_fin:
				if access_log_line.startswith(ip_addr_):
					timestamp_from_access_log_line = \
							time.strptime(get_timestamp_str_from_access_log_line(access_log_line), ACCESS_LOG_TIME_FORMAT)
					if time.mktime(timestamp_from_access_log_line) < time.mktime(err_log_timestamp_):
						r.append(access_log_line.rstrip())
		r = r[-5:]
		return r

	def get_error_log_context_lines(error_log_line_, err_timestamp_):
		error_log_filename = get_error_log_filename(err_timestamp_)
		r = []
		if error_log_filename:
			with open(error_log_filename) as error_log_fin:
				desired_line_prefix = re.sub(r'((.*?\]){3}).*', r'\1', error_log_line_.rstrip())
				for error_log_line in error_log_fin:
					if error_log_line.startswith(desired_line_prefix):
						r.append(error_log_line.rstrip())
		return r

	def decode_url_in_access_log_line(access_log_line_):
		proc = subprocess.Popen(['./decode_url_params.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		return proc.communicate(access_log_line_)[0].rstrip()

	def read_file(error_log_fin_):
		for err_log_line in error_log_fin_:
			mo = re.match(r'^\[([^]]*)\].*\[client ([^ ]*)\]', err_log_line)
			if mo:
				timestamp_in_err_log_format = mo.group(1)
				ip_addr = mo.group(2)
				err_timestamp = time.strptime(timestamp_in_err_log_format, '%a %b %d %H:%M:%S %Y')
				for error_log_line in get_error_log_context_lines(err_log_line, err_timestamp):
					print 'error log:', error_log_line
				access_log_line = get_access_log_line(ip_addr, err_timestamp)
				if access_log_line:
					print '--> access log:', access_log_line
					print '-->    decoded:', decode_url_in_access_log_line(access_log_line)
				else:
					possible_access_log_lines = get_possible_access_log_lines(ip_addr, err_timestamp)
					if possible_access_log_lines:
						for access_log_line in possible_access_log_lines:
							print '--> possible access log:', access_log_line
							print '-->             decoded:', decode_url_in_access_log_line(access_log_line)
					else:
						print '--> access log line not found.'

	args = sys.argv[1:]
	if args:
		for filename in args:
			with open(filename) as error_log_fin:
				read_file(error_log_fin)
	else:
		read_file(sys.stdin)

