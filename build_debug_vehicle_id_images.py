#!/usr/bin/python2.6

import re, os, urlparse, tempfile, subprocess
from misc import *

def get_color(vid_):
	colors = ((255, 0, 0), (255, 0, 255), (0, 255, 255), (0, 127, 0, ), (130, 127, 0), (255, 255, 0), (102, 102, 102), (127, 0, 0),
		(127, 0, 127), (0, 127, 127, ), (0, 255, 0), (0, 0, 255))
	color = colors[hash(vid_) % len(colors)]
	return 'rgb(%d,%d,%d)' % color

def get_svg(vid_):
	color = get_color(vid_)
	size = 36
	opacity = 1.0
	return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 91 91" width="%dpx" height="%dpx" version="1.1">' + \
			'<circle cx="45" cy="45" r="45" fill="%s" stroke="rgb(0,0,0)" stroke-width="1" />' + \
			'<text x="3" y="56" fill="rgb(0,0,0)" font-size="32">%s</text>' +
			'</svg>') % (size, size, color, vid_)

if __name__ == '__main__':

	pngfilenames_n_svgstrs = []
	for vid_int in range(1000, 10000):
		vid = str(vid_int)
		png_filename = 'img/debug-vehicle-id-%s.png' % vid
		svgstr = get_svg(vid)
		pngfilenames_n_svgstrs.append((png_filename, svgstr))

	png_filename = 'img/debug-vehicle-id-unknown.png'
	svgstr = get_svg('????')
	pngfilenames_n_svgstrs.append((png_filename, svgstr))

	svgs_to_pngs(pngfilenames_n_svgstrs)


