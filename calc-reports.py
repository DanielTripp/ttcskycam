#!/usr/bin/python2.6

'''
Examples of date/time args: 
'2014-09-{20..23} {12:00..23:55..120}'
'2014-{09..11}-20 {12:00,12:07}'
'''

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, cProfile 
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

def expand(str_):
	if str_.startswith('{') and str_.endswith('}'):
		if ',' in str_:
			return str_[1:-1].split(',')
		elif '..' in str_:
			parts = str_[1:-1].split('..')
			if len(parts) not in (2, 3):
				raise Exception()
			if len(parts[0]) != len(parts[1]):
				raise Exception()
			if ':' in parts[0]:
				assert (':' in parts[1]) and all(re.match(r'\d\d:\d\d', x) for x in parts[:2])
				def toint(x__):
					splits = x__.split(':')
					return int(splits[0])*60 + int(splits[1])
				def tostr(x__):
					return '%02d:%02d' % (x__/60, x__%60)
			else:
				def toint(x__):
					return int(x__)
				length = len(parts[0])
				def tostr(x__):
					return ('%0'+str(length)+'d') % x
			start = toint(parts[0]); stop = toint(parts[1])
			inc = int(parts[2]) if len(parts) == 3 else 1
			return [tostr(x) for x in range(start, stop+1, inc)]
	else:
		return [str_]

def get_locations_by_vid(report_):
	r = defaultdict(list)
	for timeslice in report_:
		for vi in timeslice[1:]:
			r[vi.vehicle_id].append(vi)
	return dict(r)

def print_traffic_report(report_):
	pprint.pprint(report_)

def print_locations_report(report_, locsbyvid_):
	if locsbyvid_:
		for vid, vis in get_locations_by_vid(report_).iteritems():
			print 'vid=%s' % vid
			for vi in vis:
				print '  %s' % vi
	else:
		for timeslice in report_:
			timestr = timeslice[0]
			print timestr
			for vi in timeslice[1:]:
				print '  %s' % vi

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['print', 'datazooms=', 'log', 'norestartmc', 'nolocsbyvid'])
	if len(args) != 4:
		printerr('Usage:')
		printerr('Mandatory args: reporttype(s), froute(s), direction(s), and date/time(s).')
		printerr('Option args: --print, --datazooms=, --log, --norestartmc')
		sys.exit(1)

	doprint = get_opt(opts, 'print')
	datazooms_arg = get_opt(opts, 'datazooms')
	if not datazooms_arg:
		datazooms = [c.MAX_DATAZOOM]
	elif datazooms_arg == 'all':
		datazooms = c.VALID_DATAZOOMS[:]
	else:
		datazooms = [int(e) for e in datazooms_arg.split(',')]
	dolog = get_opt(opts, 'log')
	norestartmc = get_opt(opts, 'norestartmc')
	nolocsbyvid = get_opt(opts, 'nolocsbyvid')

	reporttypes, froutes, directions, times = args

	reporttypes = reporttypes.split(',')
	if any(x not in ('t', 'l') for x in reporttypes):
		raise Exception('Invalid reporttypes arg.')

	if froutes == 'all':
		froutes = routes.NON_SUBWAY_FUDGEROUTES
	else:
		froutes = froutes.split(',')
		if any(x not in routes.NON_SUBWAY_FUDGEROUTES for x in froutes):
			raise Exception('Invalid froutes arg.')

	directions = [int(x) for x in directions.split(',')]
	if any(x not in (0, 1) for x in directions):
		raise Exception('Invalid directions arg.')

	mo = re.match('(.*?)-(.*?)-(.*?) (.*)', times)
	if not mo:
		sys.exit('Invalid times arg.')
	yeararg, montharg, dayarg, timearg = [mo.group(i) for i in range(1, 5)]

	stdout_and_stderr_both_ttys = os.isatty(sys.stdout.fileno()) and os.isatty(sys.stderr.fileno())
	stderr_is_a_tty = os.isatty(sys.stderr.fileno())
	date_field_combos = list(product(expand(yeararg), expand(montharg), expand(dayarg), expand(timearg)))
	datetimestrs = ['%s-%s-%s %s' % (year, month, day, tyme) for year, month, day, tyme in date_field_combos]
	printerr('Will calculate %d date/times:' % len(datetimestrs))
	for datetimestr in datetimestrs:
		printerr(datetimestr)
	printerr('--')

	if not norestartmc:
		mc.restart()

	streets.get_snapgraph()
	tracks.get_snapgraph()
	print 'Got sgs.'

	profile = False

	total_t0 = time.time()
	for i, datetimestr in enumerate(datetimestrs):
		time_em = str_to_em(datetimestr)
		for froute in froutes:
			for direction in directions:
				for reporttype in reporttypes:
					for datazoom in datazooms:
						log_args_str = '- %s, %s, %s, %s, datazoom=%d -' % (datetimestr, froute, direction, reporttype, datazoom)
						print log_args_str
						if not stdout_and_stderr_both_ttys:
							printerr(log_args_str)
						if stderr_is_a_tty:
							print_est_time_remaining('', total_t0, i, len(datetimestrs))
						if reporttype == 't':
							report = traffic.get_traffics_impl(froute, direction, datazoom, time_em, log_=dolog)
						elif reporttype == 'l':
							report = traffic.get_recent_vehicle_locations_impl(froute, direction, datazoom, time_em, log_=dolog)
						else:
							raise Exception()
						if doprint:
							if reporttype == 't':
								print_traffic_report(report)
							else:
								print_locations_report(report, not nolocsbyvid)
		if profile:
			if i == 0:
				profiler = cProfile.Profile() # tdr 
				profiler.enable()
		cpu_prof_exit_early_maybe()
	if profile:
		dump_profiler_to_svg_file(profiler, None)


