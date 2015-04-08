#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt
from misc import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, streetlabels, vehicleimages, c

def get_streetlabel_filename(text_, rotation_, zoom_):
	return 'streetlabel_%s_%d_%d.png' % (text_.replace(' ', '_'), rotation_, zoom_)

def build_streetlabel_images(froutes_=None):
	texts_rotations_zooms = set()
	for zoom in streetlabels.GUIZOOMS_WITH_STREETLABELS:
		for froute in (froutes_ if froutes_ is not None else routes.NON_SUBWAY_FUDGEROUTES):
			for direction in (0, 1):
				for label in streetlabels.get_labels_for_zoom(froute, direction, zoom):
					text = label['text']; rotation = label['rotation']
					texts_rotations_zooms.add((text, rotation, zoom))
	
	pngfilenames_and_svgstrs = []
	for text, rotation, zoom in texts_rotations_zooms:
		png_filename = os.path.join('img', get_streetlabel_filename(text, rotation, zoom))
		svgstr = streetlabels.get_streetlabel_svg(text, rotation, zoom)
		pngfilenames_and_svgstrs.append((png_filename, svgstr))

	svgs_to_pngs(pngfilenames_and_svgstrs)

def get_vehicle_arrow_filename(size_, heading_, static_aot_moving_):
	return 'vehicle_arrow_%d_%d_%s.png' % (size_, heading_, ('static' if static_aot_moving_ else 'moving'))

def build_vehicle_arrow_images():
	pngfilenames_and_svgstrs = []
	for size in vehicleimages.get_all_vehicle_img_sizes():
		for heading in range(0, 360, vehicleimages.HEADING_ROUNDING):
			for static_aot_moving in (True, False):
				png_filename = os.path.join('img', get_vehicle_arrow_filename(size, heading, static_aot_moving))
				svgstr = vehicleimages.get_vehicle_arrow_svg_by_client_args(size, heading, static_aot_moving)
				pngfilenames_and_svgstrs.append((png_filename, svgstr))

	svgs_to_pngs(pngfilenames_and_svgstrs)
	

if __name__ == '__main__':

	which = sys.argv[1]
	if which not in ('streetlabels', 'vehiclearrows', 'all'):
		raise Exception()

	if which in ('streetlabels', 'all'):
		build_streetlabel_images()

	if which in ('vehiclearrows', 'all'):
		build_vehicle_arrow_images()


