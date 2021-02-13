#!/usr/bin/env python
#!/usr/bin/env PYTHONOPTIMIZE=on python

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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy, random
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, system, c, reports, streetlabels, snapgraph, streets, testgraph
from misc import *
import geom
import numpy as np

if __name__ == '__main__':

	t0 = 1611669166101
	rounded_set = set()
	for arg in range(t0, t0+1000L*60*30, 7):
		rounded = round_up_by_minute(arg)
		rounded_set.add(rounded)
		#print '%s=%s %s=%s diff=%s' % (arg, em_to_str_z(arg), rounded, em_to_str_z(rounded), arg - rounded) 
	for rounded in sorted(rounded_set):
		if 0:
			assert round_down_by_minute(rounded-1) == rounded - 1000L*60
			assert round_down_by_minute(rounded) == rounded
			assert round_down_by_minute(rounded+1) == rounded
			assert round_down_by_minute(rounded+1000L*60-1) == rounded
			assert round_down_by_minute(rounded+1000L*60) == rounded+1000L*60
		elif 0:
			step = 15
			assert round_down_by_minute_step(rounded-1, step) == rounded - 1000L*60*step
			assert round_down_by_minute_step(rounded, step) == rounded
			assert round_down_by_minute_step(rounded+1, step) == rounded
			assert round_down_by_minute_step(rounded+1000L*60*step-1, step) == rounded
			assert round_down_by_minute_step(rounded+1000L*60*step, step) == rounded+1000L*60*step
		else:
			for d in range(-3000, -1):
				#print d
				#print round_up_by_minute(rounded + d) , rounded
				assert round_up_by_minute(rounded + d) == rounded
			#assert round_up_by_minute(rounded-1) == rounded
			assert round_up_by_minute(rounded) == rounded
			assert round_up_by_minute(rounded+1) == rounded + 1000L*60 
			assert round_up_by_minute(rounded+1000L*60-1) == rounded + 1000L*60
			assert round_up_by_minute(rounded+1000L*60) == rounded + 1000L*60
			assert round_up_by_minute(rounded+1000L*60+1) == rounded + 1000L*60*2






