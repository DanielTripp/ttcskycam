#!/usr/bin/python2.6

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
			(0,1,0), (0,1,1), (1,0,1), (1,0,0), (0,0,1), (0.7,0.7,0), 
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

	output_directory = 'report-generation-times'
	logs_directory = '~/ttc-logs'

	output_directory = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), output_directory))
	logs_directory = os.path.expanduser(logs_directory)

	version_to_timesamples = defaultdict(list)

	finishtime_cutoff_numdaysago = {'day': 1, '3day': 3, 'week': 7, 'month': 30}[timeframe]
	finishtime_cutoff_em = now_em() - finishtime_cutoff_numdaysago*24*60*60*1000

	for dirpath, dirnames, filenames in os.walk(logs_directory):
		dirnames[:] = []
		for filename in (f for f in filenames if f.startswith('reports_generation_')):
			full_filename = os.path.join(dirpath, filename)
			if os.stat(full_filename).st_mtime*1000 < finishtime_cutoff_em:
				continue
			with open(full_filename) as fin:
				for line in fin:
					splits = line.strip().split(',')
					if len(splits) == 3 and (splits[0].startswith(str(current_year())) or splits[0].startswith(str(current_year()-1))):
						finishtime_em = str_to_em(splits[0])
						if finishtime_em > finishtime_cutoff_em:
							timetaken = int(splits[1])
							timesample = TimeSample(finishtime_em, timetaken)
							version = splits[2]
							version_to_timesamples[version].append(timesample)

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

	for timesamples in version_to_timesamples.itervalues():
		timesamples.sort(key=lambda s: s.finishtime)

	versions_in_time_order = sorted(version_to_timesamples.keys(), key=lambda v: version_to_timesamples[v][0].finishtime)

	def get_texty(versionidx_):
		ys = [0.85, 0.90, 0.95]
		return ys[versionidx_ % len(ys)]

	max_yval = 120

	for versionidx, version in enumerate(versions_in_time_order):
		timesamples = version_to_timesamples[version]

		regular_xvals = []; too_high_xvals = []; regular_yvals = []
		for timesample in timesamples:
			if timesample.timetaken < 120:
				regular_xvals.append(em_to_datetime(timesample.finishtime))
				regular_yvals.append(timesample.timetaken)
			else:
				too_high_xvals.append(em_to_datetime(timesample.finishtime))

		color = get_color(version)
		plt.plot(regular_xvals, regular_yvals, color=color, marker='+', linestyle='None')

		textx = float(versionidx+1)/(len(version_to_timesamples)+1)
		arrow_target_x = average(datetime_to_em(x) for x in chain(regular_xvals, too_high_xvals))
		all_xvals_em = [datetime_to_em(x) for x in regular_xvals + too_high_xvals]
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
				arrowprops=dict(arrowstyle='->'), color=color)

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
	plt.yticks(np.arange(0, max_yval, 10)) # Do this after the axhline() calls or else the min value might not be respected. 

	fig.autofmt_xdate()

	out_png_filename = timeframe
	plt.savefig(os.path.join(output_directory, out_png_filename), bbox_inches='tight')



