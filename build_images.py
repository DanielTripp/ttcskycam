#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, streetlabels, vehicleimages, c

def get_streetlabel_filename(text_, rotation_, zoom_):
	return 'streetlabel_%s_%d_%d.png' % (text_.replace(' ', '_'), rotation_, zoom_)

def build_streetlabel_images():
	texts_rotations_zooms = set()
	for zoom in range(13, 22):
		for froute in routes.NON_SUBWAY_FUDGEROUTES:
			for label in streetlabels.get_labels_for_zoom(froute, zoom):
				text = label['text']; rotation = label['rotation']
				texts_rotations_zooms.add((text, rotation, zoom))
	
	pngfilenames_and_svgstrs = []
	for text, rotation, zoom in texts_rotations_zooms:
		png_filename = os.path.join('img', get_streetlabel_filename(text, rotation, zoom))
		svgstr = streetlabels.get_streetlabel_svg(text, rotation, zoom)
		pngfilenames_and_svgstrs.append((png_filename, svgstr))

	svgs_to_pngs(pngfilenames_and_svgstrs)

def get_vehicle_filename(size_, heading_, static_aot_moving_):
	return 'vehicle_arrow_%d_%d_%s.png' % (size_, heading_, ('static' if static_aot_moving_ else 'moving'))

def build_vehicle_images():
	with open('zoom_to_vehicle_size.json') as fin:
		zoom_to_vehicle_size = json.load(fin)
	all_sizes = set(zoom_to_vehicle_size)
	with open('HEADING_ROUNDING') as fin:
		HEADING_ROUNDING = int(fin.read())

	pngfilenames_and_svgstrs = []
	for size in all_sizes:
		for heading in range(0, 360, HEADING_ROUNDING):
			for static_aot_moving in (True, False):
				png_filename = os.path.join('img', get_vehicle_filename(size, heading, static_aot_moving))
				svgstr = vehicleimages.get_vehicle_svg_by_client_args(size, heading, static_aot_moving)
				pngfilenames_and_svgstrs.append((png_filename, svgstr))

	svgs_to_pngs(pngfilenames_and_svgstrs)
	

if __name__ == '__main__':


	build_streetlabel_images()
	build_vehicle_images()


