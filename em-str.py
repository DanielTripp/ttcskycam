#!/usr/bin/python2.6

import sys, time, re
from misc import *

if len(sys.argv) == 1:
	print now_em()
else:
	arg = sys.argv[1]
	if re.match('^\\d+$', arg):
		print em_to_str(int(arg))
	else:
		print str_to_em(arg)
	

