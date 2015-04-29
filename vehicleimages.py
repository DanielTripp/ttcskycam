#!/usr/bin/env python

'''
This file is part of ttcskycam.

ttcskycam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ttcskycam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ttcskycam.  If not, see <http://www.gnu.org/licenses/>.
'''

import os.path, subprocess, json

with open('HEADING_ROUNDING') as fin:
	HEADING_ROUNDING = int(fin.read())

def get_all_vehicle_img_sizes():
	with open('zoom_to_vehicle_rendered_img_size.json') as fin:
		zoom_to_vehicle_size = json.load(fin)
	return set(zoom_to_vehicle_size)

# By 'client args' I mean what the client knows i.e. static vs. moving.  
# I would rather size wasn't a client arg (zoom would be the sensible value for the client to worry about) 
# but unfortunately to center it in that google maps marker on the client side I need to kow the size of the image, 
# and that's we maintain the zoom-to-size map (zoom_to_vehicle_size.json) in a file where both the PHP and 
# the python can get at it. 
def get_vehicle_arrow_svg_by_client_args(size_, heading_, static_aot_moving_):
	assert isinstance(size_, int) and isinstance(heading_, int) and isinstance(static_aot_moving_, bool)
	color = ('rgb(100,100,100)' if static_aot_moving_ else 'rgb(150,150,150)')
	opacity = (0.8 if static_aot_moving_ else 0.3)
	return get_vehicle_arrow_svg_by_graphic_args(size_, heading_, color, opacity)

def get_vehicle_arrow_svg_by_graphic_args(size_, heading_, color_, opacity_):
	return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 91 91" width="%dpx" height="%dpx" version="1.1">' + \
			'<g transform="rotate(%d 45 45)" >' + \
			'<polygon points="30,30, 45,15, 60,30, 60,75, 30,75" fill="%s" fill-opacity="%f" stroke="rgb(0,0,0)" stroke-width="1" />' + \
			'</g>' + \
			'</svg>') % (size_, size_, heading_, color_, opacity_)


def do_imagemagick_convert(src_filename_, dest_filename_, opacity_, dest_size_):
	subprocess.check_call(['convert', src_filename_, '-transparent', '#99BD90', \
			'-channel', 'a', '-fx', '(u == 0  ? 0 : %f )' % opacity_,\
			'-resize', '%dx%d' % (dest_size_, dest_size_), '-strip', dest_filename_])

def build_vehicle_icon_images():
	for vehicletype in ('streetcar', 'bus'):
	#for vehicletype in ('bus',):  # DEV 
		for heading in range(0, 360, HEADING_ROUNDING):
		#for heading in range(0, 185, HEADING_ROUNDING):  # DEV
		#for heading in [315]:  # DEV
			for size in sorted(get_all_vehicle_img_sizes()):
			#for size in [100]: # DEV
			#if size not in (60,): continue # DEV
				src_filename = os.path.join('vehicle-rendered-source-imgs', 'orig-%s-heading-%d.png' % (vehicletype, heading))
				for static_aot_moving in (True, False):
				#for static_aot_moving in (True,): # DEV 
					opacity = {True: 0.7, False: 0.4}[static_aot_moving]
					static_str = ('static' if static_aot_moving else 'moving')
					dest_filename = os.path.join('img', '%s-%s-size-%d-heading-%d.png' % (vehicletype, static_str, size, heading))
					do_imagemagick_convert(src_filename, dest_filename, opacity, size)
	

def get_vehicle_arrow_filename(size_, heading_, static_aot_moving_):
	return 'vehicle_arrow_%d_%d_%s.png' % (size_, heading_, ('static' if static_aot_moving_ else 'moving'))

def build_vehicle_arrow_images():
	pngfilenames_and_svgstrs = []
	for size in get_all_vehicle_img_sizes():
		for heading in range(0, 360, HEADING_ROUNDING):
			for static_aot_moving in (True, False):
				png_filename = os.path.join('img', get_vehicle_arrow_filename(size, heading, static_aot_moving))
				svgstr = get_vehicle_arrow_svg_by_client_args(size, heading, static_aot_moving)
				pngfilenames_and_svgstrs.append((png_filename, svgstr))

	svgs_to_pngs(pngfilenames_and_svgstrs)
	
if __name__ == '__main__':

	build_vehicle_icon_images()



