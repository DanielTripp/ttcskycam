# First we pull in the standard API hooks.
require 'sketchup.rb'

UI.menu("PlugIns").add_item("export all headings") {
	export_headings(5)
}

UI.menu("PlugIns").add_item("export a few headings") {
	export_headings(45)
}

UI.menu("PlugIns").add_item("rotate everything 45 degrees") {
	rotate_all(45)
}

def to_degrees(radians_)
	return (radians_*180)/Math::PI
end

def to_radians(degrees_)
	return (degrees_/180.0)*Math::PI
end


def average(val1_, val2_, ratio_)
	return (1.0 - ratio_)*val1_ + ratio_*val2_
end

def heading_to_camera_pos_radians(heading_)

	if heading_ % 5 != 0
		raise 'Heading increment must be a multiple of 5.'
	end

	heading = heading_
	mirror = (heading > 180)
	if mirror
		heading = 360 - heading
	end

	# I almost arrived at a formula for these angles, but it's a few degrees off in some places.  
	# The formula is below.  These cases here fudge the input heading so that it looks good.  
	# I got both these fudge factors and the formula by trial and error. 
	if [5, 10].include?(heading)
		heading += 3.5
	elsif [15, 20].include?(heading)
		heading += 3
	elsif [25, 30].include?(heading)
		heading += 2
	elsif [100, 105].include?(heading)
		heading += 0.5
	elsif [110, 115, 120, 125, 130].include?(heading)
		heading += 1
	elsif [150, 155].include?(heading)
		heading -= 0.5
	elsif [160, 165, 170, 175].include?(heading)
		heading -= 1
	end

	# This is the function that almost looks good: a sine wave average with the identity line: 
	headingradians = to_radians(heading)
	sin_result = (Math::PI/2)*Math.sin(headingradians - Math::PI/2) + Math::PI/2
	identity_line_result = headingradians
	r = average(sin_result, identity_line_result, 0.5)

	if mirror
		r = 2*Math::PI - r
	end
	return r
end

def rotate_all(degrees_)
	transformation = Geom::Transformation.rotation [0, 0, 0], [0, 0, 1], to_radians(degrees_)
	entities = Sketchup.active_model.entities
	entities.transform_entities(transformation, entities.to_a)
end

def export_headings(incr_)

	if Sketchup.active_model.title != 'bus' && Sketchup.active_model.title != 'streetcar'
		raise 'Can\'t figure out if this is a bus or a streetcar.'
	end
	vehicletype = Sketchup.active_model.title

	status = Sketchup.active_model.start_operation("Export Heading PNGs", true)

	dist_from_origin = 1900
	side = Math.sqrt(2) * dist_from_origin
	camera_z = side
	camera_heading_degrees = 90
	camera_heading_radians = to_radians(camera_heading_degrees)
	camera_x = side * Math.cos(camera_heading_radians)
	camera_y = side * Math.sin(camera_heading_radians)
	eye = [camera_x, camera_y, camera_z]
	target = [0,0,0]
	up = [0,0,1]
	my_camera = Sketchup::Camera.new eye, target, up
	my_camera.perspective = false
	view = Sketchup.active_model.active_view
	view.camera = my_camera

	vehicle_heading = 0
	while vehicle_heading < 360
		#if vehicle_heading > 180 # TDR 
		#if vehicle_heading != 315 # TDR 
		#	vehicle_heading += incr_
		#	next
		#end # TDR 
		view_heading_degrees = to_degrees(heading_to_camera_pos_radians(vehicle_heading))
		rotate_all(-view_heading_degrees)
		view.write_image('C:\\cygwin\\home\\dt\\PycharmProjects\\ttc\\trunk\\vehicle-rendered-source-imgs\\orig-%s-heading-%d.png' % [vehicletype, vehicle_heading], 1000, 1000, true)
		rotate_all(view_heading_degrees)
		vehicle_heading += incr_
	end

	view.camera.perspective = true
	Sketchup.active_model.commit_operation
	Sketchup.undo
	UI.messagebox('Done.')

end

