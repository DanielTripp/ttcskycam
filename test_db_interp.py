#!/usr/bin/python2.6

import sys, os, urlparse, json, pprint, time, pickle, xml.dom, xml.dom.minidom, datetime, time, getopt, unittest
from itertools import *
from misc import *
from backport_OrderedDict import *
import routes, traffic, db, vinfo, geom, mc, tracks, util, predictions, paths, c, reports, streetlabels, snapgraph, picklestore

class T(unittest.TestCase):

	def test_interp_tracks_simple(self):
		vis = []
		vis.append(vinfo.makevi((43.6552287,-79.4185429), '12:00', '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6534278,-79.4224052), '12:01', '4999', 'dundas'))
		assert all(vi.mofr == -1 for vi in vis)
		latlng, heading, mofr = db.interp_latlonnheadingnmofr(vis[0], vis[1], 0.5, None, True, vis)
		self.assertTrue(latlng.is_close(geom.LatLng(43.6547969,-79.4206612)))
		self.assertTrue(is_close(heading, 250, 10))

	def test_interp_tracks_stuck(self):
		vis = []
		for minute in range(10):
			vis.append(vinfo.makevi((43.6552287,-79.4185429), '12:%02d' % minute, '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6552365, -79.4184571), '12:10', '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6552326, -79.4182961), '12:11', '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6552481, -79.4180923), '12:12', '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6552365, -79.4178563), '12:13', '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6552403, -79.4177007), '12:14', '4999', 'dundas'))
		assert all(vi.mofr == -1 for vi in vis)
		latlng, heading, mofr = db.interp_latlonnheadingnmofr(vis[0], vis[1], 0.5, None, True, vis)
		self.assertTrue(latlng.is_close(vis[0].latlng, 5))
		self.assertTrue(is_close(heading, 260, 10))

	def test_interp_onroute_simple(self):
		vis = []
		vis.append(vinfo.makevi((43.6499656, -79.4179206), '12:00', '4999', 'dundas'))
		vis.append(vinfo.makevi((43.6506565, -79.4136184), '12:01', '4999', 'dundas'))
		latlng, heading, mofr = db.interp_latlonnheadingnmofr(vis[0], vis[1], 0.5, None, True, vis)
		self.assertTrue(latlng.is_close(geom.LatLng(43.6503315, -79.4157781)))
		self.assertTrue(is_close(heading, 75, 10))
		self.assertTrue(is_close(mofr, avg(vis[0].mofr, vis[1].mofr), 10))

	def test_interp_list(self):
		raw_vis = []
		raw_vis.append(vinfo.makevi(150, '2007-02-26 12:00:30', '1999', 'dundas', 0))
		raw_vis.append(vinfo.makevi(250, '2007-02-26 12:01:30', '1999', 'dundas', 0))
		raw_vis.append(vinfo.makevi(350, '2007-02-26 12:02:30', '1999', 'dundas', 0))
		interp_result = db.interp_by_time(raw_vis[::-1], True, True, dir_=0, 
				start_time_=str_to_em('2007-02-26 12:00'), end_time_=str_to_em('2007-02-26 12:03'))
		interped_vis = sum((x[1:] for x in interp_result), [])
		self.assertTrue(len(interped_vis) == 3)
		self.assertTrue([vi.mofr for vi in interped_vis] == [200, 300, 350])
		self.assertTrue([vi.time for vi in interped_vis] 
				== [str_to_em(x) for x in ['2007-02-26 12:01', '2007-02-26 12:02', '2007-02-26 12:03']])


