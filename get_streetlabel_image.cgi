#!/usr/bin/python2.6

import re, os, urlparse, tempfile, subprocess
import mc
from misc import *

def get_arg_strvals(vardict_):
	r = []
	argi = 0
	while True:
		argname='arg%d' % (argi)
		if argname not in vardict_:
			break
		r.append(vardict_[argname][0])
		argi+=1
	return r

def get_arg_objvals(vardict_):
	strvals = get_arg_strvals(vardict_)
	return [strvals[0], int(strvals[1]), int(strvals[2])]

def get_streetlabel_svg(text_, rotation_, zoom_):
	fontsize = {13:7, 14:8, 15:8, 16:9, 17:10, 18:10, 19:10, 20:10, 21:10}[zoom_]/2
	textshift = fontsize/2
	svgstr = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 100 100" version="1.1">
<g transform="translate(0 %(textshift)d) rotate(%(rotation)d 50 50)" >
<text x="49.7" y="49.7" fill="rgb(255,255,255)" font-family="sans-serif" font-size="%(fontsize)s">%(text)s</text>
<text x="50" y="50" fill="rgb(80,50,20)" font-family="sans-serif" font-size="%(fontsize)s">%(text)s</text>
</g>
</svg>''' % {'text': text_, 'rotation': rotation_, 'fontsize': fontsize, 'textshift': textshift}
	return svgstr

@mc.decorate
def get_streetlabel_png(text_, rotation_, zoom_):
	return svg_to_png(get_streetlabel_svg(text_, rotation_, zoom_))

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
args = get_arg_objvals(vars)

print 'Content-type: image/png\n'
print get_streetlabel_png(*args)

