#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, subprocess
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mpldates
import matplotlib.ticker as ticker
import matplotlib.transforms
import pylab as pl
from misc import *

def get_color(vid_):
	colors = [(0,0,0), (0.4,0.4,0.4), (0,1,0), (0,0.4,0), (0.2,0.2,1), (0,0,0.4), (0.4,0.4,0), (0,1,1), (0,0.4,0.4), (1,0,1), (0.4,0,0.4), (1,0,0), (0,0,1)]
	r = colors[hash(vid_) % len(colors)]
	return r

class TimeSample(object):

	def __init__(self, finishtime_, timetaken_):
		self.finishtime = finishtime_
		self.timetaken = timetaken_

if __name__ == '__main__':

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

	for versionidx, version in enumerate(versions_in_time_order):
		timesamples = version_to_timesamples[version]
		xvals = [em_to_datetime(s.finishtime) for s in timesamples]
		yvals = [s.timetaken for s in timesamples]

		textx = float(versionidx+1)/(len(version_to_timesamples)+1)
		ax.annotate(version, xy=(xvals[0], yvals[0]), textcoords='axes fraction', xytext=(textx, get_texty(versionidx)), 
				arrowprops=dict(arrowstyle='->'))

		plt.plot(xvals, yvals, color=get_color(version), marker='+', linestyle='None')

	plt.axhline(15,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(30,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(45,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(60,  color='black',       alpha=0.5, linestyle='-')
	plt.axhline(75,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(90,  color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(105, color=(0.5,0.5,0.5), alpha=0.5, linestyle='--')
	plt.axhline(120, color=(0.5,0.5,0.5), alpha=0.5, linestyle='-')

	fig.autofmt_xdate()

	out_png_filename = timeframe
	plt.savefig(os.path.join(output_directory, out_png_filename), bbox_inches='tight')



