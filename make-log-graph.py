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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, subprocess, random
from itertools import *
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mpldates
import matplotlib.ticker as ticker
import matplotlib.transforms
import pylab as pl
import numpy as np
from misc import *

def get_color(vid_):
	colors = [(0,0,0), (0.4,0.4,0.4), 
			(0,1,0), (0,1,1), (1,0,1), (0,0,1), (0.7,0.7,0), 
			(0,0.4,0), (0.4,0.4,0), (0,0.4,0.4), (0.4,0,0.4), (0,0,0.4), 
			(0.2,0.2,1), 
			]
	r = colors[hash(vid_) % len(colors)]
	return r

class TimeSample(object):

	def __init__(self, finishtime_, timetaken_):
		self.finishtime = finishtime_
		self.timetaken = timetaken_

if __name__ == '__main__':

	random.seed(37)

	timeframe = sys.argv[1]
	if timeframe not in ('day', '3day', 'week', 'month'):
		raise Exception('invalid timeframe')

	output_directory = 'log-graphs'
	logs_directory = '~/ttc-logs'

	output_directory = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), output_directory))
	logs_directory = os.path.expanduser(logs_directory)

	version_to_timesamples = defaultdict(list)

	finishtime_cutoff_numdaysago = {'day': 1, '3day': 3, 'week': 7, 'month': 30}[timeframe]
	finishtime_cutoff_em = now_em() - finishtime_cutoff_numdaysago*24*60*60*1000

	error_times = []
	poll_slow_times = []

	for dirpath, dirnames, filenames in os.walk(logs_directory):
		dirnames[:] = []
		for filename in (f for f in filenames if f.startswith('reports_generation_')):
			full_filename = os.path.join(dirpath, filename)
			if os.stat(full_filename).st_mtime*1000 < finishtime_cutoff_em:
				continue
			with open(full_filename) as fin:
				for line in fin:
					splits = line.strip().split(',')
					if splits[-1] == '--generate-time--':
						finishtime_em = str_to_em(splits[0])
						if finishtime_em > finishtime_cutoff_em:
							timetaken = int(splits[1])
							timesample = TimeSample(finishtime_em, timetaken)
							version = splits[2]
							version_to_timesamples[version].append(timesample)
					elif line.rstrip().endswith('--poll-slow--'):
						t = str_to_em(line[:16])
						if t > finishtime_cutoff_em:
							poll_slow_times.append(t)
					elif line.rstrip().endswith('--generate-error--'):
						t = str_to_em(line[:16])
						if t > finishtime_cutoff_em:
							error_times.append(t)

	poll_error_times = []

	for dirpath, dirnames, filenames in os.walk(logs_directory):
		dirnames[:] = []
		for filename in (f for f in filenames if f.startswith('poll_locations_')):
			full_filename = os.path.join(dirpath, filename)
			if os.stat(full_filename).st_mtime*1000 < finishtime_cutoff_em:
				continue
			with open(full_filename) as fin:
				for line in fin:
					splits = line.strip().split(',')
					if splits[-1] == '--poll-error--':
						try:
							t = str_to_em(splits[0])
							if t > finishtime_cutoff_em:
								poll_error_times.append(t)
						except ValueError: # this is to skip lines jumbled by multiprocessing.  multiproc in poll_locations won't 
							pass # be around for long.  so remove this after it's gone.

	if not version_to_timesamples:
		# An empty plot produces an error message in our date formatting function.  Here we're preventing that. 
		version_to_timesamples['x'].append(TimeSample(now_em(), 0))

	plt.figure(1)
	fig, ax = plt.subplots()
	fig.set_size_inches(15, 8)

	def format_date(x, pos=None):
		if timeframe == 'month':
			return pl.num2date(x).strftime('%b %d')
		else:
			return pl.num2date(x).strftime('%a %H:%M')

	ax.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
	ax.yaxis.tick_right()

	for timesamples in version_to_timesamples.itervalues():
		timesamples.sort(key=lambda s: s.finishtime)

	versions_in_time_order = sorted(version_to_timesamples.keys(), key=lambda v: version_to_timesamples[v][0].finishtime)

	def get_texty(versionidx_):
		ys = [0.85, 0.90, 0.95]
		return ys[versionidx_ % len(ys)]

	def split_timesamples_into_stretches(timesamples_):
		cur_stretch = None
		r = []
		for s in timesamples_:
			if not cur_stretch or s.finishtime - cur_stretch[-1].finishtime > 1000*60*30:
				cur_stretch = [s]
				r.append(cur_stretch)
			else:
				cur_stretch.append(s)
		return r

	max_yval = 120

	for poll_slow_time in poll_slow_times:
		plt.axvline(em_to_datetime(poll_slow_time), color='grey', alpha=0.5, linestyle='dashed')

	for poll_error_time in poll_error_times:
		plt.axvline(em_to_datetime(poll_error_time), color='black', linestyle='dashed')

	for error_time in error_times:
		plt.axvline(em_to_datetime(error_time), color='red')

	TOO_HIGH_Y_CUTOFF = 120

	for versionidx, version in enumerate(versions_in_time_order):
		all_timesamples = version_to_timesamples[version]
		for timesamples in split_timesamples_into_stretches(all_timesamples):
			regular_finishtimes = []; too_high_finishtimes = []
			regular_yvals = []
			for timesample in timesamples:
				if timesample.timetaken < TOO_HIGH_Y_CUTOFF:
					regular_finishtimes.append(timesample.finishtime)
					regular_yvals.append(timesample.timetaken)
				else:
					too_high_finishtimes.append(timesample.finishtime)
			regular_xvals = [em_to_datetime(x) for x in regular_finishtimes]
			too_high_xvals = [em_to_datetime(x) for x in too_high_finishtimes]
			too_high_yvals = [max_yval]*len(too_high_xvals)

			color = get_color(version)
			plt.plot(regular_xvals, regular_yvals, color=color, marker='+', linestyle='None')
			plt.plot(too_high_xvals, too_high_yvals, color=color, marker='o', linestyle='None')

			textx = float(versionidx+1)/(len(version_to_timesamples)+1)

			all_xvals_em = [timesample.finishtime for timesample in timesamples]
			min_x_em = min(all_xvals_em)
			max_x_em = max(all_xvals_em)
			arrow_target_x = em_to_datetime(average([min_x_em, max_x_em]))
			if regular_yvals:
				some_random_yvals = []
				for i in xrange(100):
					some_random_yvals.append(random.choice(regular_yvals))
				arrow_target_y = average(some_random_yvals)*1.1
			else:
				arrow_target_y = max_yval
			ax.annotate(version, xy=(arrow_target_x, arrow_target_y), textcoords='axes fraction', xytext=(textx, get_texty(versionidx)), 
					arrowprops=dict(arrowstyle='->', linestyle='dotted', color=color), color=color)

			if regular_yvals:
				start_yval = min(max(regular_yvals[:30])*1.2, TOO_HIGH_Y_CUTOFF)
				end_yval = min(max(regular_yvals[-30:])*1.2, TOO_HIGH_Y_CUTOFF)
			else:
				start_yval = end_yval = TOO_HIGH_Y_CUTOFF/2
			plt.vlines([em_to_datetime(timesamples[0].finishtime)], 0.1, start_yval, color=color, alpha=0.5)
			plt.vlines([em_to_datetime(timesamples[-1].finishtime)], 0.1, end_yval, color=color, alpha=0.5)

			#for timesample in [timesamples[0], timesamples[-1]]:
			#	plt.vlines([em_to_datetime(timesample.finishtime)], 0, 30, color=color)

	plt.axhline(10,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(20,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(30,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(40,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(50,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(60,  color='black',       alpha=0.5, linestyle='-')
	plt.axhline(70,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(80,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(90,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(100,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(110, color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(120, color=(0.5,0.5,0.5), alpha=0.5, linestyle='-')
	plt.yticks(np.arange(0, max_yval+20, 10)) # Do this after the axhline() calls or else the min value might not be respected. 

	fig.autofmt_xdate()

	out_png_filename = timeframe
	plt.savefig(os.path.join(output_directory, out_png_filename), bbox_inches='tight')



