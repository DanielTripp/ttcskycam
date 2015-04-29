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


	class C(object):

		def __init__(self, i_):
			self.i = i_

		def __hash__(self):
			print 'in hash %d' % self.i
			return hash(self.i)

	c1 = C(1)
	c2 = C(2)

	d = {}
	d[c1] = None
	d[c2] = None


