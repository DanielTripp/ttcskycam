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
	fontsize = {13:3.5, 14:4, 15:4, 16:4.5, 17:5, 18:5, 19:5, 20:5, 21:5}[zoom_]
	# In SVG the y location of text seems to be the baseline i.e. bottom of upper-case letters.  So if we set that baseline 
	# to be the vertical middle of the graphic, and also use that vertical middle to coincide with the middle of the 
	# google maps polyline (which we do) then to get the text to sit in the middle of the polyline, we'll have to shift the 
	# text down.  I don't know why shifting it down by 1/3 of the font size does what we want, but it does. 
	textshift = fontsize/3.0 
	# SVG transforms are evaluated right to left.  So below we're translating, then rotating. 
	svgstr = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 100 100" version="1.1">
<g transform="rotate(%(rotation)d 50 50) translate(0 %(textshift)f)" >
<text x="49.7" y="49.7" fill="rgb(255,255,255)" font-family="sans-serif" font-size="%(fontsize)f">%(text)s</text>
<text x="50" y="50" fill="rgb(80,50,20)" font-family="sans-serif" font-size="%(fontsize)f">%(text)s</text>
</g>
</svg>''' % {'text': text_, 'rotation': rotation_, 'fontsize': fontsize, 'textshift': textshift}
	return svgstr

@mc.decorate
def get_streetlabel_png(text_, rotation_, zoom_):
	return svg_to_png(get_streetlabel_svg(text_, rotation_, zoom_))

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
args = get_arg_objvals(vars)

print 'Cache-control: max-age=86400'
print 'Content-type: image/png\n'
print get_streetlabel_png(*args)

