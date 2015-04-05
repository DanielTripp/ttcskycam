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

	output_directory = 'report-generation-times'
	logs_directory = '~/ttc-logs'

	output_directory = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), output_directory))
	logs_directory = os.path.expanduser(logs_directory)

	version_to_timesamples = defaultdict(list)

	for dirpath, dirnames, filenames in os.walk(logs_directory):
		dirnames[:] = []
		for filename in (f for f in filenames if f.startswith('reports_generation_')):
			with open(os.path.join(dirpath, filename)) as fin:
				for line in fin:
					splits = line.strip().split(',')
					if len(splits) == 3 and (splits[0].startswith(str(current_year())) or splits[0].startswith(str(current_year()-1))):
						finishtime = str_to_em(splits[0])
						timetaken = int(splits[1])
						timesample = TimeSample(finishtime, timetaken)
						version = splits[2]
						version_to_timesamples[version].append(timesample)

	plt.figure(1)
	fig, ax = plt.subplots()
	fig.set_size_inches(15, 8)

	def format_date(x, pos=None):
		return pl.num2date(x).strftime('%a %H:%M')

	ax.xaxis.set_major_formatter(ticker.FuncFormatter(format_date))
	for version, timesamples in version_to_timesamples.iteritems():
		plt.plot([em_to_datetime(s.finishtime) for s in timesamples], [s.timetaken for s in timesamples], 
				color=get_color(version), marker='+', linestyle='None')
	fig.autofmt_xdate()
	plt.savefig(os.path.join(output_directory, 'matplotoutput'), bbox_inches='tight')




