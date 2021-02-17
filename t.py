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

	def pack_into_linesegidx(plineidx_, ptidx_):
		assert plineidx < 2**30
		assert ptidx < 2*30
		r = (plineidx << 30) ^ ptidx
		return r

	plineidx = (2**31 - 2)
	plineidx = int(sys.argv[1])
	ptidx = int(sys.argv[2])
	linesegidx = pack_into_linesegidx(plineidx, ptidx)
	print bin(linesegidx)

