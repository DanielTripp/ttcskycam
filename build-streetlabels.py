#!/usr/bin/env python

import sys
import streetlabels

froutes_arg = sys.argv[1]

if froutes_arg == 'all':
	streetlabels.build_streetlabel_images(None)
else:
	froutes = froutes_arg.split(',')
	for froute in froutes:
		streetlabels.build_streetlabel_images(froute)
		
