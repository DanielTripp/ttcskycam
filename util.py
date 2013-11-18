#!/usr/bin/python2.6

import json
import vinfo, db, routes, mc, geom, snapgraph
from misc import *

def get_vids(route_, start_time_, end_time_):
	assert isinstance(start_time_, (int,long)) and isinstance(end_time_, (int,long))
	sql = 'select distinct(vehicle_id) from ttc_vehicle_locations where route_tag = %s and time >  %s and time < %s'
	curs = db.conn().cursor()
	curs.execute(sql, [route_, start_time_, end_time_])
	r = []
	for row in curs:
		r.append(row[0])
	curs.close()
	return r

def is_at_end_of_route(vi_):
	return vi_.mofr < 100 or vi_.mofr > routes.max_mofr(vi_.route_tag) - 100

def is_going_wrong_way(vi1_, vi2_):
	if (vi1_.dir_tag_int == vi2_.dir_tag_int) and (vi1_.mofr!=-1 and vi2_.mofr!=-1) and (vi1_.dir_tag_int in (0, 1)) \
			and not is_at_end_of_route(vi1_) and not is_at_end_of_route(vi2_):
		dir = vi1_.dir_tag_int
		if dir==0:
			return vi1_.mofr > vi2_.mofr
		else:
			return vi2_.mofr > vi1_.mofr
	else:
		return False


def print_old_wrong_dirs(route_, day_start_time_):
	for vid, stretches in get_old_wrong_dirs(route_, day_start_time_, day_start_time_ + 1000*60*60*24).items():
		for stretch in stretches:
			print 'vid %s going wrong way for %d readings - from %s to %s.'\
				  % (vid, len(stretch), em_to_str_hms(stretch[0].time), em_to_str_hms(stretch[-1].time))

def get_old_wrong_dirs(route_, start_time_, end_time_):
	vids = get_vids(route_, start_time_, end_time_)
	r = {}
	for vid in vids:
		curs = db.conn().cursor()
		sql = 'select '+db.VI_COLS+' from ttc_vehicle_locations where vehicle_id = %s and route_tag = %s and time >  %s and time < %s order by time'
		curs.execute(sql, [vid, route_, start_time_, end_time_])
		vis = []
		for row in curs:
			vis.append(vinfo.VehicleInfo.from_db(*row))
		curs.close()

		wrong_dir_stretches = get_maximal_sublists2(vis, is_going_wrong_way)
		wrong_dir_stretches = filter(lambda l: len(l) >= 5, wrong_dir_stretches)
		r[vid] = wrong_dir_stretches
	return r

def get_current_wrong_dirs(start_time_ = now_em()-1000*60*30):
	return mc.get(get_current_wrong_dirs_impl, start_time_)

def get_current_wrong_dirs_impl(start_time_ = now_em()-1000*60*30):
	end_time = start_time_ + 1000*60*30
	r = {}
	for configroute in routes.CONFIGROUTES:
		vids = get_vids(configroute, start_time_, end_time)
		for vid in vids:
			curs = db.conn().cursor()
			sql = 'select '+db.VI_COLS+' from ttc_vehicle_locations where vehicle_id = %s and route_tag = %s and time >  %s and time < %s order by time'
			curs.execute(sql, [vid, configroute, start_time_, end_time])
			vis = []
			for row in curs:
				vis.append(vinfo.VehicleInfo.from_db(*row))
			curs.close()

			num_recent_vis_to_scutinize = 5
			if len(vis) >= num_recent_vis_to_scutinize:
				vis_under_scutiny = vis[-num_recent_vis_to_scutinize:]
				if all(is_going_wrong_way(vi1, vi2) for vi1, vi2 in hopscotch(vis_under_scutiny)):
					for prev_vi, vi in hopscotch(vis_under_scutiny):
						vi.heading = prev_vi.latlng.heading(vi.latlng)
					vis_under_scutiny[0].heading = vis_under_scutiny[1].heading
					r[vid] = vis_under_scutiny
	return r

def print_current_wrong_dirs(start_time_ = now_em()-1000*60*30):
	for vid, vis in get_current_wrong_dirs(start_time_).items():
		print 'vid %s is going the wrong way.' % vid
		for vi in vis:
			print vi

def file_to_latlngs(filename_):
	with open(filename_) as fin:
		r = []
		for raw_latlng in json.load(fin):
			r.append(geom.LatLng(raw_latlng[0], raw_latlng[1]))
		return r

class OurJSONEncoder(json.JSONEncoder):

	def default(self, o):
		if isinstance(o, geom.LatLng):
			return (o.lat, o.lng)
		elif isinstance(o, geom.LineSeg):
			return (o.start, o.end)
		elif isinstance(o, vinfo.VehicleInfo):
			return o.to_json_dict()
		elif isinstance(o, snapgraph.GridSquare):
			return (o.gridlat, o.gridlng)
		else:
			return json.JSONEncoder.default(self, o)

def to_json_str(object_, indent=None):
	return json.dumps(object_, cls=OurJSONEncoder, indent=indent, sort_keys=True)

def to_json_file(object_, filename_, indent=None):
	with open(filename_, 'w') as fout:
		json.dump(object_, fout, cls=OurJSONEncoder, indent=indent, sort_keys=True)

# Find the mid-point of a loop.  
# Pass in a completed loop i.e. last point is equal to first point. 
def split_route_loop(filename_):
	latlngs = file_to_latlngs(filename_)
	assert latlngs[0].dist_m(latlngs[-1]) < 0.01
	total_metres = sum(p1.dist_m(p2) for p1, p2 in hopscotch(latlngs))
	cur_metres = 0.0
	for i in range(1, len(latlngs)):
		cur_leg_metres = latlngs[i-1].dist_m(latlngs[i])
		cur_metres += cur_leg_metres
		if cur_metres >= total_metres/2.0:
			prevpt = latlngs[i-1]; curpt = latlngs[i]
			prev_metres = cur_metres - cur_leg_metres
			midpt = curpt.subtract(prevpt).scale((total_metres/2.0 - prev_metres)/float(cur_metres - prev_metres)).add(prevpt)
			def p(latlngs__):
				#print json.dumps(latlngs__, indent=0, cls=OurJSONEncoder)
				print '['
				for i, latlng in enumerate(latlngs__):
					print '[%.6f, %.6f]%s' % (latlng.lat, latlng.lng, (',' if i < len(latlngs__)-1 else ''))
				print ']'
			def dist(pts_):
				return sum(pt1.dist_m(pt2) for pt1, pt2 in hopscotch(pts_))
			path1 = latlngs[0:i] + [midpt]
			path2 = ([midpt] + latlngs[i:])[::-1]
			assert abs(dist(path1) - dist(path2)) < 0.001
			p(path1)
			print
			p(path2)
			break

if __name__ == '__main__':

	#print_old_wrong_dirs('301', str_to_em('2012-11-02 00:00'))
	#print_current_wrong_dirs(str_to_em('2012-10-02 01:00'))
	print_current_wrong_dirs()



