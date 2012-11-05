#!/usr/bin/python2.6

import re, os, urlparse

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
	return [int(strvals[0]), int(strvals[1]), strvals[2], float(strvals[3])]



def get_vehicle_svg(size_, heading_, color_, opacity_):
	return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 91 91" width="%dpx" height="%dpx" version="1.1">' + \
			'<g transform="rotate(%d 45 45)" >' + \
			'<polygon points="30,30, 45,15, 60,30, 60,75, 30,75" fill="%s" fill-opacity="%f" stroke="rgb(0,0,0)" stroke-width="1" />' + \
			'</g>' + \
			'</svg>') % (size_, size_, heading_, color_, opacity_)

def get_vehicle_png(size_, heading_, color_, opacity_):
	svgstr = get_vehicle_svg(size_, heading_, color_, opacity_)
	import os, tempfile, subprocess
	svg_fileno, svg_filename = tempfile.mkstemp('.svg', 'temp-vehicle-svg', '/tmp/dt')
	svg_file = os.fdopen(svg_fileno, 'w')
	svg_file.write(svgstr)
	svg_file.close()
	subprocess.check_call(['java', '-jar', 'batik-1.7/batik-rasterizer.jar', svg_filename], \
			stdout=open('/dev/null', 'w'), stderr=open('/dev/null', 'w'))
	assert svg_filename[-4:] == '.svg'
	png_filename = svg_filename[:-4] + '.png' # batik just created this .png file, with a name based on the svg filename. 
	with open(png_filename, 'rb') as png_fin:
		png_contents = png_fin.read()
	os.remove(svg_filename)
	os.remove(png_filename)
	return png_contents

vars = urlparse.parse_qs(os.getenv('QUERY_STRING'))
args = get_arg_objvals(vars)

user_agent = os.getenv('HTTP_USER_AGENT')
if any(x in user_agent for x in ('MSIE 6', 'MSIE 7', 'MSIE 8')):
	print 'Content-type: image/png\n'
	print get_vehicle_png(*args)
else:
	print 'Content-type: image/svg+xml\n'
	print get_vehicle_svg(*args)

