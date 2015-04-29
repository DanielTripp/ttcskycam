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

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, threading, copy
from collections import *

if __name__ == '__main__':

	ipaddr2count = defaultdict(int)
	with open('/tmp/3', 'r') as fin:
		for line in fin:
			ipaddr2count[line.strip()] += 1

	sorted_by_count = sorted(ipaddr2count.items(), key=lambda x: x[1], reverse=True)
	for ipaddr, count in sorted_by_count:
		print '%10d %s' % (count, ipaddr)

