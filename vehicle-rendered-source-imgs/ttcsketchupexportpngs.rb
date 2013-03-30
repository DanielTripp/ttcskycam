# First we pull in the standard API hooks.
require 'sketchup.rb'

UI.menu("PlugIns").add_item("bus - export all headings") {
	export_headings('bus', 5)
}

UI.menu("PlugIns").add_item("bus - export a few headings") {
	export_headings('bus', 45)
}

UI.menu("PlugIns").add_item("streetcar - export all headings") {
	export_headings('streetcar', 5)
}

UI.menu("PlugIns").add_item("streetcar - export a few headings") {
	export_headings('streetcar', 45)
}

UI.menu("PlugIns").add_item("rotate all") {
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

def heading_radians_to_camera_pos_radians(heading_)
	heading = heading_
	shift = (heading > Math::PI)
	if shift
		heading -= Math::PI
	end
	sin_result = (Math::PI/2)*Math.sin(heading - Math::PI/2) + Math::PI/2
	if shift
		sin_result += Math::PI
	end

	return average(sin_result, heading_, 0.5)
end

def rotate_all(degrees_)
	transformation = Geom::Transformation.rotation [0, 0, 0], [0, 0, 1], to_radians(degrees_)
	entities = Sketchup.active_model.entities
	entities.transform_entities(transformation, entities.to_a)
end

def export_headings(vehicletype_, incr_)

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
		view_heading_degrees = to_degrees(heading_radians_to_camera_pos_radians(to_radians(vehicle_heading)))
		rotate_all(-view_heading_degrees)
		view.write_image('C:\\cygwin\\home\\dt\\PycharmProjects\\ttc\\trunk\\vehicle-icon-source-images\\orig-%s-heading-%d.png' % [vehicletype_, vehicle_heading], 1000, 1000, true)
		rotate_all(view_heading_degrees)
		vehicle_heading += incr_
	end

	view.camera.perspective = true
	Sketchup.active_model.commit_operation
	UI.messagebox('Done.')

end

