#!/usr/bin/python2.6

'''
Examples of date/time args: 
'2014-09-{20..23} {12:00..23:55..120}'
'2014-{09..11}-20 {12:00,12:07}'
'''

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets
import numpy as np

if __name__ == '__main__':

	opts, args = getopt.getopt(sys.argv[1:], '', ['print', 'datazooms=', 'log', 'norestartmc', 'locsbyvid'])
	if len(args) != 4:
		printerr('Usage:')
		printerr('Mandatory args: reporttype(s), froute(s), direction(s), and date/time(s).')
		printerr('Option args: --print, --datazooms=, --log, --norestartmc')
		sys.exit(1)

	doprint = get_opt(opts, 'print')
	datazooms_arg = get_opt(opts, 'datazooms')
	if not datazooms_arg:
		datazooms = [0]
	elif datazooms_arg == 'all':
		datazooms = c.VALID_DATAZOOMS[:]
	else:
		datazooms = [int(e) for e in datazooms_arg.split(',')]
	dolog = get_opt(opts, 'log')
	norestartmc = get_opt(opts, 'norestartmc')
	locsbyvid = get_opt(opts, 'locsbyvid')

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

	stdout_is_a_tty = os.isatty(sys.stdout.fileno())
	t0 = time.time()
	date_field_combos = list(product(expand(yeararg), expand(montharg), expand(dayarg), expand(timearg)))
	datetimestrs = ['%s-%s-%s %s' % (year, month, day, tyme) for year, month, day, tyme in date_field_combos]
	printerr('Will calculate %d date/times:' % len(datetimestrs))
	for datetimestr in datetimestrs:
		printerr(datetimestr)
	printerr('--')

	if not norestartmc:
		mc.restart()

	t0 = time.time()
	streets.get_snapgraph()
	tracks.get_snapgraph()
	print 'Time to get sgs: %d seconds.' % (time.time() - t0)

	for i, datetimestr in enumerate(datetimestrs):
		time_em = str_to_em(datetimestr)
		for froute in froutes:
			for direction in directions:
				for reporttype in reporttypes:
					for datazoom in datazooms:
						print '- %s, %s, %s, %s, datazoom=%d -' % (datetimestr, froute, direction, reporttype, datazoom)
						if not stdout_is_a_tty:
							printerr('-', datetimestr, froute, direction, reporttype, '-')
						print_est_time_remaining('', t0, i, len(datetimestrs))
						if reporttype == 't':
							report = traffic.get_traffics_impl(froute, direction, datazoom, time_em, log_=dolog)
						elif reporttype == 'l':
							report = traffic.get_recent_vehicle_locations_impl(froute, direction, datazoom, time_em, log_=dolog)
							if locsbyvid:
								report = get_locations_by_vid(report)
						else:
							raise Exception()
						if doprint:
							pprint.pprint(report)
	printerr('All reports took %.3f seconds.' % (time.time() - t0))


