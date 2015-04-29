#!/usr/bin/env python

import sys, time, re
from misc import *

if len(sys.argv) == 1:
	print now_em()
else:
	for arg in sys.argv[1:]:
		if re.match('^\\d+$', arg):
			print em_to_str_millis(int(arg))
		else:
			print str_to_em(arg)
	

