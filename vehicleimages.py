#!/usr/bin/python2.6

# By 'client args' I mean what the client knows i.e. static vs. moving.  
# I would rather size wasn't a client arg (zoom would be the sensible value for the client to worry about) 
# but unfortunately to center it in that google maps marker on the client side I need to kow the size of the image, 
# and that's we maintain the zoom-to-size map (zoom_to_vehicle_size.json) in a file where both the PHP and 
# the python can get at it. 
def get_vehicle_svg_by_client_args(size_, heading_, static_aot_moving_):
	assert isinstance(size_, int) and isinstance(heading_, int) and isinstance(static_aot_moving_, bool)
	color = ('rgb(100,100,100)' if static_aot_moving_ else 'rgb(150,150,150)')
	opacity = (0.8 if static_aot_moving_ else 0.3)
	return get_vehicle_svg_by_graphic_args(size_, heading_, color, opacity)

def get_vehicle_svg_by_graphic_args(size_, heading_, color_, opacity_):
	return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 91 91" width="%dpx" height="%dpx" version="1.1">' + \
			'<g transform="rotate(%d 45 45)" >' + \
			'<polygon points="30,30, 45,15, 60,30, 60,75, 30,75" fill="%s" fill-opacity="%f" stroke="rgb(0,0,0)" stroke-width="1" />' + \
			'</g>' + \
			'</svg>') % (size_, size_, heading_, color_, opacity_)

