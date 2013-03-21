#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, streetlabels, c

def get_streetlabel_filename(text_, rotation_, zoom_):
	return '%s_%d_%d.png' % (text_.replace(' ', '_'), rotation_, zoom_)

def build_streetlabel_images():
	for zoom in range(13, 22):
		print 'Zoom %d...' % zoom
		for froute in routes.NON_SUBWAY_FUDGEROUTES:
			for label in streetlabels.get_labels_for_zoom(froute, zoom):
				png_contents = streetlabels.get_streetlabel_png(label['text'], label['rotation'], zoom)
				png_filename = get_streetlabel_filename(label['text'], label['rotation'], zoom)
				with open(os.path.join('img', png_filename), 'w') as fout:
					fout.write(png_contents)
			

if __name__ == '__main__':


	build_streetlabel_images()
	
