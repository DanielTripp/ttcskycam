#!/usr/bin/env python

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, random
from misc import *
from backport_OrderedDict import *
import traffic, db, vinfo, routes, geom, mc, tracks, util, predictions, paths, c, reports 


random.seed(0)

def apply(froute_, locations_, n_, detour_latlngs_=None, randomize_=True):
	if n_ >= 0:
		r = locations_[n_:]
	else:
		r = locations_[:]
		for i in range(abs(n_)):
			r.insert(0, None)
	if randomize_:
		for i in range(len(r)):
			random_mofr_shift = random.randint(0, 5)
			for j in range(i, len(r)):
				assert isinstance(r[j], int) or (r[j] is None)
				if r[j] is not None:
					r[j] += random_mofr_shift

	if detour_latlngs_ is not None:
		detour_start_mofr = routes.routeinfo(froute_).latlon_to_mofr(geom.LatLng(detour_latlngs_[0]), 2)
		detour_end_mofr = routes.routeinfo(froute_).latlon_to_mofr(geom.LatLng(detour_latlngs_[-1]), 2)
		for i, location in enumerate(r):
			if location is not None and location >= detour_start_mofr:
				for j in range(min(len(detour_latlngs_), len(r)-i)):
					r.insert(i+j, detour_latlngs_[j])
				while (i+j+1 < len(r)) and (r[i+j+1] < detour_end_mofr):
					r.pop(i+j+1)
				break

	r = r[:31]
	while len(r) < 31:
		r.append(None)

	return r

def make_demo_dundas():
	froute = 'dundas'

	mofr_to_kmph = {0:18, 560: 20, 1200: 15, 1350: 12, 1450: 5, 1570: 22, 2100: 10, 2210: 15, 2970: 8, 3100: 20, 
		4190: 8, 4330: 20, 4650: 8, 4900: 4, 5100: 8, 5500: 10, 5700: 8, 6300: 4, 6570: 10, 6730: 10, 6793: 20, 7710: 10, 7890: 20, 
		8950: 8, 9080: 20, 9310: 10, 9480: 15, 9690: 22}
	locations = [0]
	mofr = 0
	t_secs = 0
	while mofr <= routes.routeinfo(froute).max_mofr():
		for speed_ref_mofr in range(round_down(mofr, 100), -1, -10): 
		                                            # ^^ this is, or was, a mofrs step.  not sure if it matters much.  
																								# was changing some things and didn't understand this code.  sorry. 
			if speed_ref_mofr in mofr_to_kmph:
				speed_kmph = mofr_to_kmph[speed_ref_mofr]
				break
		else:
			assert False
		mofr_diff = traffic.kmph_to_mps(speed_kmph)*1
		mofr = int(mofr + mofr_diff)
		t_secs += 1
		if t_secs % 60 == 0:
			locations.append(mofr)
		
	detour_latlngs = []
	detour_latlngs.append((43.657608, -79.377601))
	detour_latlngs.append((43.661132, -79.379082))
	detour_latlngs.append((43.662110, -79.377987))
	detour_latlngs.append((43.663150, -79.373352))
	detour_latlngs.append((43.664066, -79.368997))
	detour_latlngs.append((43.663662, -79.367752))
	detour_latlngs.append((43.662032, -79.367087))
	detour_latlngs.append((43.660433, -79.366443))

	demo_report_timestr = '2007-01-01 12:00'
	db.delete_demo_locations(froute, demo_report_timestr)
	db.insert_demo_locations(froute, demo_report_timestr, '4940', apply(froute, locations, -40, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4930', apply(froute, locations, -30, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4920', apply(froute, locations, -20, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4910', apply(froute, locations, -12, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4903', apply(froute, locations, -5, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4902', apply(froute, locations, -2, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4000', apply(froute, locations, 0, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4010', apply(froute, locations, 9, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4015', apply(froute, locations, 15, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4018', apply(froute, locations, 18, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4030', apply(froute, locations, 30, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4040', apply(froute, locations, 40, detour_latlngs))
	db.insert_demo_locations(froute, demo_report_timestr, '4050', apply(froute, locations, 45, detour_latlngs))

def mofr_to_kmph_to_locations(froute_, mofr_to_kmph_):
	locations = [0]
	mofr = 0
	t_secs = 0
	while mofr <= routes.routeinfo(froute_).max_mofr() and len(locations) < 1000:
		for speed_ref_mofr in range(round_down(mofr, 100), -1, -10):
		                                            # ^^ this is, or was, a mofrs step.  not sure if it matters much.  
																								# was changing some things and didn't understand this code.  sorry. 
			if speed_ref_mofr in mofr_to_kmph_:
				speed_kmph = mofr_to_kmph_[speed_ref_mofr]
				break
		else:
			assert False
		mofr_diff = traffic.kmph_to_mps(speed_kmph)*1
		mofr = int(mofr + mofr_diff)
		t_secs += 1
		if t_secs % 60 == 0:
			locations.append(mofr)
	return locations

def make_demo_dundas_stopped():
	froute = 'dundas'

	mofr_to_kmph_1 = {0:18, 560: 20, 1200: 15, 1350: 12, 1450: 5, 1570: 22, 1900: 10, 2970: 8, 3100: 20, 
		4190: 8, 4330: 20, 4650: 8, 4900: 4, 5100: 8, 5500: 10, 5700: 8, 6300: 4, 6570: 10, 6730: 10, 6793: 20, 7710: 10, 7890: 20, 
		8950: 8, 9080: 20, 9310: 10, 9480: 15, 9690: 22}
	mofr_to_kmph_2 = mofr_to_kmph_1.copy()
	mofr_to_kmph_2[2700] = 0
	mofr_to_kmph_3 = mofr_to_kmph_1.copy()
	mofr_to_kmph_3[2100] = 8
	mofr_to_kmph_3[2600] = 0
	mofr_to_kmph_4 = mofr_to_kmph_1.copy()
	mofr_to_kmph_4[1950] = 5
	mofr_to_kmph_4[2400] = 0
	locations1 = mofr_to_kmph_to_locations(froute, mofr_to_kmph_1)
	locations2 = mofr_to_kmph_to_locations(froute, mofr_to_kmph_2)
	locations3 = mofr_to_kmph_to_locations(froute, mofr_to_kmph_3)
	locations4 = mofr_to_kmph_to_locations(froute, mofr_to_kmph_4)

	demo_report_timestr = '2007-01-01 13:00'
	db.delete_demo_locations(froute, demo_report_timestr)
	db.insert_demo_locations(froute, demo_report_timestr, '4940', apply(froute, locations4, -40, randomize_=False))
	db.insert_demo_locations(froute, demo_report_timestr, '4930', apply(froute, locations4, -25, randomize_=False))
	db.insert_demo_locations(froute, demo_report_timestr, '4920', apply(froute, locations4, -10, randomize_=False))
	db.insert_demo_locations(froute, demo_report_timestr, '4903', apply(froute, locations3, -5, randomize_=False))
	db.insert_demo_locations(froute, demo_report_timestr, '4000', apply(froute, locations2, 0, randomize_=False))
	db.insert_demo_locations(froute, demo_report_timestr, '4010', apply(froute, locations1, 9))
	db.insert_demo_locations(froute, demo_report_timestr, '4015', apply(froute, locations1, 15))
	db.insert_demo_locations(froute, demo_report_timestr, '4018', apply(froute, locations1, 18))
	db.insert_demo_locations(froute, demo_report_timestr, '4030', apply(froute, locations1, 30))
	db.insert_demo_locations(froute, demo_report_timestr, '4040', apply(froute, locations1, 40))
	db.insert_demo_locations(froute, demo_report_timestr, '4050', apply(froute, locations1, 45))

def make_demo_bathurst():
	froute = 'bathurst'

	# king 2682  front 3019
	locations = range(2545, 0, -70)[::-1]
	print locations

	demo_report_timestr = '2007-01-01 12:00'
	db.delete_demo_locations(froute, demo_report_timestr)
	db.insert_demo_locations(froute, demo_report_timestr, '4001', apply(froute, locations, 0))
	db.insert_demo_locations(froute, demo_report_timestr, '1001', apply(froute, locations, -6))

if __name__ == '__main__':

	#make_demo_dundas()
	#make_demo_bathurst()
	make_demo_dundas_stopped()


