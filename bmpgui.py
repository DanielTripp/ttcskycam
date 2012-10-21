#!/usr/bin/python2.6

from Tkinter import *
import tkFont
import sys, subprocess, re, time, xml.dom, xml.dom.minidom, threading, bisect, datetime, calendar, math
from collections import defaultdict
import db, vinfo, geom, report
from misc import *

X_SIZE = 10

def get_polygon(center_, rad_, n_):
	r = []
	for angle in frange(0.0, 2*math.pi, 2*math.pi/n_):
		r.append([rad_*math.cos(angle), rad_*math.sin(angle)])
	for xy in r:
		xy[0] += center_[0]
		xy[1] += center_[1]
	return tuple((tuple(xy) for xy in r))

class MainFrame(Frame):
	def __init__(self, master=None):
		Frame.__init__(self, master)
		self.master.title('TTC')
		self.grid()
		self.create_canvas()
		self.draw_vehicle_text_reset_offset()
		self.master.geometry('1444x802+0+0')

	def create_canvas(self):
		self.canvas = Canvas(self)
		self.img = PhotoImage(file="map.gif")
		self.config(width=self.img.width(), height=self.img.height())
		self.draw_map()
		self.grid()
		#self.canvas.create_line(0, 0, self.img.width(), self.img.height())
		self.canvas.config(width=self.img.width(), height=self.img.height())
		self.canvas.grid()

	def draw_map(self):
		self.canvas.create_image((self.img.width()/2, self.img.height()/2), image=self.img)

	def draw_text_latlon(self, latlon_, text_):
		self.draw_text_pix(get_xy(latlon_), text_)

	def draw_text_pix(self, xy_, text_):
		self.canvas.create_text(xy_[0], xy_[1], text=text_, font=('Helvetica', '14'))
		self.canvas.grid()

	def draw_vehicle_text_reset_offset(self):
		self.draw_vehicle_time_y_offset = 20
		self.draw_vehicle_time_top = False

	def draw_vehicle_text_incr_offset(self):
		self.draw_vehicle_time_y_offset = ((self.draw_vehicle_time_y_offset + 20) % 140)
		if self.draw_vehicle_time_y_offset == 0:
			self.draw_vehicle_time_y_offset = 20
		self.draw_vehicle_time_top = not self.draw_vehicle_time_top 

	def draw_x(self, cen_, color_):
		cen = massage_to_pixels(cen_)
		self.canvas.create_line(cen[0]-X_SIZE, cen[1]-X_SIZE, cen[0]+X_SIZE, cen[1]+X_SIZE, fill=color_)
		self.canvas.create_line(cen[0]-X_SIZE, cen[1]+X_SIZE, cen[0]+X_SIZE, cen[1]-X_SIZE, fill=color_)
		self.canvas.grid()

	def draw_x_circ(self, center_, color_):
		cen = massage_to_pixels(center_)
		self.draw_x(cen, color_)
		rad = math.hypot(X_SIZE, X_SIZE)
		self.canvas.create_oval(cen[0]-rad, cen[1]-rad, cen[0]+rad, cen[1]+rad, outline=color_)

	def draw_vehicle_text(self, latlon_, vid_, time_em_, color_):
		xy = get_xy(latlon_)
		self.canvas.create_line(xy[0]-X_SIZE, xy[1]-X_SIZE, xy[0]+X_SIZE, xy[1]+X_SIZE)
		self.canvas.create_line(xy[0]-X_SIZE, xy[1]+X_SIZE, xy[0]+X_SIZE, xy[1]-X_SIZE)
		self.canvas.create_text(xy[0], xy[1]-30, text=str(vid_), font=('Verdana', '14'))
		time_xy = (xy[0], xy[1] + (-1 if self.draw_vehicle_time_top else 1)*self.draw_vehicle_time_y_offset)
		self.canvas.create_text(time_xy[0], time_xy[1], text=em_to_str_hms(time_em_), font=('Verdana', '14', 'bold'), 
				fill='red')
		self.canvas.create_line(xy[0], xy[1], time_xy[0], time_xy[1] + (1 if self.draw_vehicle_time_top else -1)*12)
		#self.canvas.create_text(xy[0], xy[1]+60, text=str(self.draw_vehicle_i), font=('Helvetica', '8'))
		self.canvas.grid()
		self.draw_vehicle_text_incr_offset()

	def draw_circle_stipple(self, center_, rad_, color_):
		self.canvas.create_polygon(*get_polygon(center_, rad_, 8), **{'fill':color_, 'stipple':'gray50'})
		return
		for x in range(center_[0] - rad_, center_[0] + rad_+1, 5):
			for y in range(center_[1] - rad_, center_[1] + rad_+1, 5):
				#self.canvas.create_line(x, y, x+1, y+1, fill=color_)
				self.canvas.create_rectangle(x, y, x, y, fill=color_, stipple='gray25')

	def draw_vehicle_circle(self, latlon_, vid_, time_em_, color_, rad_):
		xy = get_xy(latlon_)
		#self.canvas.create_oval(xy[0]-rad_, xy[1]-rad_, xy[0]+rad_, xy[1]+rad_, fill=color_, outline=color_)
		self.draw_circle_stipple(xy, rad_, color_)
		self.canvas.grid()

# pass in either two float or one tuple containing two floats. 
def get_xy(lat_, lon_=None):
	if type(lat_) in [list, tuple] and lon_==None:
		lat_, lon_ = lat_[0], lat_[1]
	return geom.XY.from_latlon((lat_, lon_)).bmp()

def get_range_val(p1_, p2_, domain_val_):
	x1 = float(p1_[0]); y1 = float(p1_[1])
	x2 = float(p2_[0]); y2 = float(p2_[1])
	return (y2 - y1)*(domain_val_ - x1)/(x2 - x1) + y1

# convert lat/lon to pixels.  leave pixels as-is.  always returns pixels.
def massage_to_pixels(coords_):
	assert type(coords_) in [tuple, list] and len(coords_) == 2
	if all(type(e) == float and (int(e) in [43, -79]) for e in coords_):
		return get_xy(coords_)
	else:
		return coords_

def trim_dict(d_):
	# TODO: remove 
	if 0:
		vids_to_remove = []
		for vid, time_to_latlon in d_.iteritems():
			for t, latlon in time_to_latlon.iteritems():
				if not (-79.4646 < latlon[1] < -79.3627):
					vids_to_remove.append(vid)
					break
		for vid in vids_to_remove:
			del d_[vid]

	# TODO: remove 
	if 0:
		vid_to_keep = '4112'
		for vid in d_.keys():
			if vid != vid_to_keep:
				del d_[vid]

def make_color_generator():
	if 0:
		while True:
			yield '#ff8800'
			yield '#ff0000'

	while True:
		yield '#ff0000'
		yield '#ff8800'
		yield '#00ff00'
		yield '#0000ff'

		yield '#ff00ff'
		yield '#00aaaa'

		yield '#999999'
		yield '#000000'


def draw_vilist(frame_, vilist_, sleep_=None, circles_=True, vid_to_color_=None):
	times = sorted(set(vi.time for vi in vilist_))
	for tidx, t in enumerate(times):
		circ_rad = tidx*10/len(times) + 5
		for vi in (vi for vi in vilist_ if vi.time == t):
			color = vid_to_color_[vi.vehicle_id] if vid_to_color_!=None else 'red'
			if circles_:
				frame_.draw_vehicle_circle(vi.xy.latlon(), str(vi.vehicle_id), t, color, circ_rad)
			else:
				frame_.draw_vehicle_text((vi.lat, vi.lon), str(vi.vehicle_id), t, color)
		if sleep_:
			time.sleep(sleep_)

class VehicleInfoDrawingThread(threading.Thread):

	def __init__(self, frame_, vilist_, sleeps_=None, circles_=True):
		threading.Thread.__init__(self)
		self.setDaemon(True)
		self.frame = frame_
		self.vilist = vilist_
		self.sleeps = sleeps_
		self.circles = circles_

	def run(self):
		while True:
			vehicle_color_generator = make_color_generator()
			vid_to_color = defaultdict(lambda: vehicle_color_generator.next())
			draw_vilist(self.frame, self.vilist, (self.sleeps[0] if self.sleeps else None), self.circles, vid_to_color)
			if self.sleeps:
				time.sleep(self.sleeps[1])
			else:
				break
			self.frame.draw_vehicle_text_reset_offset()
			self.frame.draw_map()

class RouteDrawingThread(threading.Thread):

	def __init__(self, frame_):
		threading.Thread.__init__(self)
		self.setDaemon(True)
		self.frame = frame_

	def run(self):
		path_color_generator = make_color_generator()
		for path in route.get_paths():
			path_color = path_color_generator.next()
			for point in path:
				frame.draw_x(point, path_color)
			time.sleep(1)

if __name__ == '__main__':
	frame = MainFrame()

	if len(sys.argv) > 2 and sys.argv[1] == 'draw':
		for i in range(2, len(sys.argv), 2):
			latlon = tuple([float(x.strip('(),')) for x in sys.argv[i:i+2]])
			print 'x'
			frame.draw_x_circ(latlon, 'red')
	else:

		if 0:
			route = '505'
			post = geom.XY.from_latlon((43.650, -79.409))
			orig =  geom.XY.from_latlon((43.652, -79.449))
		else:
			route = '501'
			post =  geom.XY.from_latlon((43.652, -79.38))
			orig = geom.XY.from_latlon((43.645, -79.409))
		direction = 'east'

		for vid, post_t_em, travel_time in report.get_recent_travel_times(route, orig, post, direction, 5):
			print '%s took %s arriving at %s' % (vid, m_to_str(travel_time), em_to_str(post_t_em))

		vilist = db.get_latest_vehicle_info_list(route, 140, dir_=direction)
		vilist = geom.interp_by_time(vilist)
		t = VehicleInfoDrawingThread(frame, vilist, (0.1, 1))
		t.start()

	frame.mainloop()


