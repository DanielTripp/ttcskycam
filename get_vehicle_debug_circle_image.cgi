#!/usr/bin/python2.6

import re, os, urlparse, tempfile, subprocess
import mc

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
	return [strvals[0]]

def get_color(vid_):
	colors = ((255, 0, 0), (255, 0, 255), (0, 255, 255), (0, 127, 0, ), (130, 127, 0), (255, 255, 0), (102, 102, 102), (127, 0, 0),
		(127, 0, 127), (0, 127, 127, ), (0, 255, 0), (0, 0, 255))
	color = colors[hash(vid_) % len(colors)]
	return 'rgb(%d,%d,%d)' % color

def get_svg(vid_):
	color = get_color(vid_)
	size = 30
	heading = 100
	opacity = 1.0
	return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 91 91" width="%dpx" height="%dpx" version="1.1">' + \
			'<circle cx="45" cy="45" r="45" fill="%s" stroke="rgb(0,0,0)" stroke-width="1" />' + \
			'<text x="0" y="58" fill="rgb(0,0,0)" font-size="35">%s</text>' +
			'</svg>') % (size, size, color, vid_)

def get_png(vid_):
	return mc.get(get_png_impl, [vid_])

def get_png_impl(vid_):
	svgstr = get_svg(vid_)
	tmpdir = ('/tmp/dt' if os.path.isdir('/tmp/dt') else '/tmp')
	svg_fileno, svg_filename = tempfile.mkstemp('.svg', 'temp-debug-vehicle-svg', tmpdir)
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

print 'Content-type: image/png\n'
print get_png(*args)

