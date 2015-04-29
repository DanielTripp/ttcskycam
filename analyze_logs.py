#!/usr/bin/env python

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

