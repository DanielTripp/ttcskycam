<!DOCTYPE html>
<html>
  <head>
		<title>browse_snapgraph</title>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 70%; margin: 0; padding: 0 }
    </style>
    <script type="text/javascript"
		      src="http://maps.googleapis.com/maps/api/js?sensor=false">
					    </script>
		<script type="text/javascript" src="js/richmarker-compiled.js"></script>
		<script type="text/javascript" src="js/jquery-1.7.1.min.js"></script>
		<script type="text/javascript" src="js/buckets-minified.js"></script>
		<script type="text/javascript" src="common.js"></script>
		<script type="text/javascript" src="js/infobox_packed.js"></script>
    <script type="text/javascript">

var MULTISNAP_RADIUS = 100;
var RADIUS_OF_EARTH_METERS = 6367.44465*1000;

var g_static_graph_objects = [];
var g_path_objects = [];
var g_path_markers = [];
var g_connected_vertex_map_objects = [];
var g_multisnap_objects = [];
var g_found_polyline = null, g_found_vertex = null;

function initialize() {

	init_map();
	g_map.setZoom(17);

	add_path_marker(new google.maps.LatLng(43.6540022, -79.4124381));
	add_path_marker(new google.maps.LatLng(43.6545922, -79.4086401));

	google.maps.event.addListener(g_map, 'click', on_map_clicked);
	google.maps.event.addListener(g_map, 'rightclick', function(mouseevent_) { 
			add_path_marker(mouseevent_.latLng); 
			get_path_from_server();
		});
	google.maps.event.addListener(g_map, 'zoom_changed', function() {
		if(is_selected('arrows_checkbox')) {
			get_path_from_server();
		}
	});

	add_delayed_event_listener(g_map, 'bounds_changed', refresh_graph_visuals, 750);

	$('#plineidx_field').keydown(function (e) {
		if(e.keyCode == 13) {
			$('#plineidx_button').trigger('click');
		}
	});
	$('#vertid_field').keydown(function (e) {
		if(e.keyCode == 13) {
			$('#vertid_button').trigger('click');
		}
	});
}

function add_path_marker(latlng_) {
	var marker = new google.maps.Marker({map: g_map, position: latlng_, 
			icon: 'http://www.google.com/mapfiles/marker_grey.png', draggable: true});
	google.maps.event.addListener(marker, 'click', clear_or_reget_path);
	google.maps.event.addListener(marker, 'dragend', get_path_from_server);
	google.maps.event.addListener(marker, 'rightclick', function() { 
			for(var i=0; i<g_path_markers.length; i++) {
				if(g_path_markers[i] == marker) {
					g_path_markers.splice(i, 1);
					marker.setMap(null);
					break;
				}
			}
			get_path_from_server();
		});
	g_path_markers.push(marker);
}

function clear_or_reget_path() {
	if(g_path_objects.length > 0) {
		forget_path_objects();
	} else {
		get_path_from_server();
	}
}

function get_sgname() {
	return radio_val('sgname');
}

function on_map_clicked(mouseevent_) {
	forget_multisnap_objects();
	set_contents('p_multisnap_info', 'Multisnap: ...');
	callpy('browse_snapgraph.multisnap', get_sgname(), mouseevent_.latLng, MULTISNAP_RADIUS, is_selected('multisnap_reducepts_checkbox'), 
		{success: function(latlng_n_posaddrstrs__) {
			var infostr = sprintf('Multisnap: arg: geom.LatLng(%.8f,%.8f) <br>%d result(s):', 
					mouseevent_.latLng.lat(), mouseevent_.latLng.lng(), latlng_n_posaddrstrs__.length);
			latlng_n_posaddrstrs__.forEach(function(latlng_n_posaddrstr) {
				var latlng = latlng_n_posaddrstr[0], posaddrstr = latlng_n_posaddrstr[1];
				var marker = new google.maps.Marker({map: g_map, position: google_LatLng(latlng), draggable: false});
				g_multisnap_objects.push(marker);
				if(is_selected('multisnap_show_infowindows')) {
					var infowin = new google.maps.InfoWindow({content: posaddrstr, disableAutoPan: true});
					infowin.open(g_map, marker);
					g_multisnap_objects.push(infowin);
				}
				infostr += sprintf('<br>(%.8f,%.8f) %s', latlng[0], latlng[1], posaddrstr);
			});
			set_contents('p_multisnap_info', infostr);
			g_multisnap_objects.push(new google.maps.Marker({map: g_map, position: mouseevent_.latLng, draggable: false, 
					icon: 'http://labs.google.com/ridefinder/images/mm_20_red.png', clickable: false}));
			g_multisnap_objects.push(new google.maps.Circle({map: g_map, center: mouseevent_.latLng, radius: MULTISNAP_RADIUS, 
					fillOpacity: 0, zIndex: 1, clickable: false}));

			g_multisnap_objects.forEach(function(marker) {
				google.maps.event.addListener(marker, 'click', forget_multisnap_objects);
			});
		}
	});
}

function forget_multisnap_objects() {
	g_multisnap_objects.forEach(function(obj) {
		if(obj.close != undefined) {
			obj.close();
		} else {
			obj.setMap(null);
		}
	});
	g_multisnap_objects = [];
}

function get_path_from_server() {
	forget_path_objects();
	if(!is_selected('path_checkbox')) {
		set_contents('p_marker_latlngs', 'Paths: disabled.');
	} else if(g_path_markers.length < 2) {
		set_contents('p_marker_latlngs', 'Paths: need at least two markers.');
	} else {
		set_path_text_display();
		callpy('browse_snapgraph.find_multipath', get_sgname(), g_path_markers.map(function(marker) { return marker.getPosition(); } ), 
				{success: function(path__) {
					if(path__ == null) {
						set_contents('p_marker_latlngs', get_contents('p_marker_latlngs')+' - <b>NO PATH POSSIBLE</b>');
					} else {
						var path_latlngs = google_LatLngs(path__);
						var path_pline = new google.maps.Polyline({map: g_map, path: path_latlngs, zIndex: 12, 
								strokeColor: 'rgb(100,100,100)', strokeWeight: 6, clickable: false, strokeOpacity: 1, 
								icons: (is_selected('arrows_checkbox') ? make_polyline_arrow_icons(g_map.getZoom(), path_latlngs) : null)});
						g_path_objects.push(path_pline);
					}
				} 
			});
	}
}

function set_path_text_display() {
	var contents = 'Path markers: ';
	g_path_markers.forEach(function(marker) {
		var latlng = marker.getPosition();
		contents += sprintf('(%.8f,%.8f), ', latlng.lat(), latlng.lng());
	});
	contents = contents.substring(0, contents.length-2);
	set_contents('p_marker_latlngs', contents);
}

function forget_found_polyline() {
	if(g_found_polyline != null) {
		g_found_polyline.setMap(null);
		g_found_polyline = null;
	}
}

function forget_found_vertex() {
	if(g_found_vertex != null) {
		g_found_vertex.setMap(null);
		g_found_vertex = null;
	}
}

function refresh_graph_visuals() {
	if((get_sgname() == 'streets' && g_map.getZoom() < 16) || (get_sgname() == 'tracks' && g_map.getZoom() < 13)) {
		console.log('Zoom in more.');
		forget_static_graph_objects();
		return;
	}
	var map_sw = g_map.getBounds().getSouthWest(), map_ne = g_map.getBounds().getNorthEast();
	callpy('browse_snapgraph.get_infos_for_box', get_sgname(), map_sw, map_ne, 
		{success: function(r_) {
			forget_static_graph_objects();
			var plineidx_to_pline = r_['plineidx_to_pline'], vertexid_to_info = r_['vertexid_to_info'];
			for(var plineidx in plineidx_to_pline) {
				var pline_pts = plineidx_to_pline[plineidx];
				make_pline(parseInt(plineidx, 10), pline_pts);
			}
			if(is_selected('show_points_and_vertexes_checkbox')) {
				for(var vertexid in vertexid_to_info) {
					var vertinfo = vertexid_to_info[vertexid];
					make_vert_circle(vertinfo);
				}
			}
			g_static_graph_objects.push(new google.maps.Rectangle({map: g_map, bounds: g_map.getBounds(), fillOpacity: 0, clickable: false, 
					strokeWeight: 0.5}));
		}, 
		error: function() {
			console.log('error');
		}}
		);
}

function make_vert_circle(vertinfo_) {
	var vertpos = google_LatLng(vertinfo_.pos);
	var radius = 20;
	var circle = new google.maps.Circle({map: g_map, center: vertpos, radius: radius, 
			fillOpacity: 0, zIndex: 10});
	add_hover_listener(circle, function(latlng__) { 
			var infowin_content = sprintf('Vertex %d - (%.8f,%.8f)<br>', vertinfo_.id, vertpos.lat(), vertpos.lng());
			vertinfo_.ptaddrs.forEach(function(ptaddr) {
				infowin_content += sprintf('pline %d pt %d, ', ptaddr[0], ptaddr[1]);
			});
			infowin_content = infowin_content.substring(0, infowin_content.length-2) + '<br>';
			var infowin_pos = new google.maps.LatLng(vertpos.lat() + 60*(radius/RADIUS_OF_EARTH_METERS), vertpos.lng()); 
					// ^^ that 60 is a fudge factor.  I don't know why it's necessary. 
			var infowin = new google.maps.InfoWindow({content: infowin_content,
					position: infowin_pos, disableAutoPan: true, zIndex: 1});
			infowin.open(g_map);
			return infowin;
		}, 250);
	google.maps.event.addListener(circle, 'click', function() {
			forget_connected_vertex_map_objects();
			var infowin_content = sprintf('Vertex %d - (%.8f,%.8f)<br>', vertinfo_.id, vertpos.lat(), vertpos.lng());
			vertinfo_.ptaddrs.forEach(function(ptaddr) {
				infowin_content += sprintf('pline %d pt %d, ', ptaddr[0], ptaddr[1]);
			});
			infowin_content = infowin_content.substring(0, infowin_content.length-2) + '<br>';
			infowin_content += 'Connected to: '+toJsonString(vertinfo_.connectedids);
			var infowin = new google.maps.InfoWindow({content: infowin_content, position: vertpos, disableAutoPan: true, zIndex: 2});
			g_connected_vertex_map_objects.push(infowin);
			infowin.open(g_map);

			var connected_vert_latlngs = callpy_sync('browse_snapgraph.get_connected_vert_latlngs', get_sgname(), vertinfo_.id);
			connected_vert_latlngs.forEach(function(latlng) {
				var color = 'rgb(75,75,75)';
				g_connected_vertex_map_objects.push(new google.maps.Circle({map: g_map, center: google_LatLng(latlng), radius: 30, 
						fillColor: color, fillOpacity: 1, strokeWeight: 0, zIndex: 2}));
				g_connected_vertex_map_objects.push(new google.maps.Polyline({map: g_map, path: [google_LatLng(latlng), vertpos], 
						strokeColor: color, strokeWeight: 15, zIndex: 3, strokeOpacity: 0.6}));
			});

			google.maps.event.addListener(infowin, 'closeclick', forget_connected_vertex_map_objects);
		});
	g_static_graph_objects.push(circle);
}

function forget_connected_vertex_map_objects() {
	g_connected_vertex_map_objects.forEach(function(map_object) {
		map_object.setMap(null);
	});
	g_connected_vertex_map_objects = [];
}

function make_pline(plineidx_, pline_pts_) {
	var glatlngs = google_LatLngs(pline_pts_);
	var pline = new google.maps.Polyline({map: g_map, path: glatlngs, strokeColor: get_polyline_color(glatlngs), 
			strokeWeight: 6, zIndex: 2, strokeOpacity: 0.6});
	google.maps.event.addListener(pline, 'click', function() { find_pline(plineidx_, false); });
	add_hover_listener(pline, function(latlng__) { 
			var map_height_lat= g_map.getBounds().getNorthEast().lat() - g_map.getBounds().getSouthWest().lat();
			var pos = new google.maps.LatLng(latlng__.lat() + map_height_lat*0.03, latlng__.lng());
			var infowin = new google.maps.InfoWindow({content: sprintf('pline %d', plineidx_), 
					position: pos, disableAutoPan: true});
			infowin.open(g_map);
			return infowin;
		}, 250);
	g_static_graph_objects.push(pline);

	if(is_selected('show_points_and_vertexes_checkbox')) {
		for(var i in pline_pts_) {
			var pline_pt = pline_pts_[i];
			make_pline_pt_circle(plineidx_, parseInt(i, 10), pline_pt);
		}
	}
}

function make_pline_pt_circle(plineidx_, ptidx_, pt_) {
	var circle_pos = google_LatLng(pt_);
	var circle = new google.maps.Circle({map: g_map, center: circle_pos, radius: 10, 
			fillOpacity: 0.4, strokeOpacity: 0, zIndex: 9});
	add_hover_listener(circle, function(latlng__) { 
			var map_height_lat = g_map.getBounds().getNorthEast().lat() - g_map.getBounds().getSouthWest().lat();
			var pos = new google.maps.LatLng(circle_pos.lat() + map_height_lat*0.03, circle_pos.lng());
			var infowin = new google.maps.InfoWindow({content: sprintf('pline %d, pt %d', plineidx_, ptidx_), 
					position: pos});
			infowin.open(g_map);
			return infowin;
		}, 250);
	g_static_graph_objects.push(circle);
}

function forget_static_graph_objects() {
	g_static_graph_objects.forEach(function(obj) {
		obj.setMap(null);
	});
	g_static_graph_objects = [];
}

function forget_path_objects() {
	g_path_objects.forEach(function(obj) {
		obj.setMap(null);
	});
	g_path_objects = [];
}

function get_polyline_color(polyline_latlngs_) {
	var colors = [[255, 0, 0], [255, 0, 255], [0, 255, 255], [0, 127, 0], 
			[130, 127, 0], [127, 0, 0], [127, 0, 127], [0, 127, 127, ], [0, 255, 0], [0, 0, 255]];
	var hashval = get_polyline_color_hash(polyline_latlngs_);
	var base_color = colors[hashval % colors.length];
	var num_gradients = 11;
	var gradient_num = hashval % num_gradients;
	var percent_shift_to_white = (gradient_num/num_gradients)*0.75;
	var r = [avg(base_color[0], 255, percent_shift_to_white), 
					avg(base_color[1], 255, percent_shift_to_white), 
					avg(base_color[2], 255, percent_shift_to_white)];
	return sprintf('rgb(%d,%d,%d)', r[0], r[1], r[2]);
}

// This seems to always return something that ends in '1'.  I don't know why. 
function get_polyline_color_hash(polyline_latlngs_) {
	var r = 0;
	polyline_latlngs_.forEach(function(latlng) {
		r += latlng.lat()*100000 + latlng.lng()*100000;
	});
	return Math.round(Math.abs(r));
}

function find_pline(plineidx_, pan_to_) {
	forget_found_polyline();
	callpy('browse_snapgraph.get_pline_latlngs', get_sgname(), plineidx_, 
		{success: function(latlngs__) {
			if(latlngs__ === null) {
				alert('Polyline not found.');
			} else {
				g_found_polyline = new google.maps.Polyline({map: g_map, path: google_LatLngs(latlngs__), zIndex: 1, 
						strokeWeight: 50, strokeColor: 'rgb(255,230,0)', strokeOpacity: 0.6}); // max strokeWeight might be 32. 
				google.maps.event.addListener(g_found_polyline, 'click', forget_found_polyline);
				if(pan_to_) {
					var closest_point = null, closest_point_dist = 0;
					for(var i=0; i<latlngs__.length; i++) {
						var latlng = google_LatLng(latlngs__[i]);
						var cur_pt_dist = dist_m(latlng, g_map.getCenter());
						if(closest_point === null || closest_point_dist > cur_pt_dist) {
							closest_point = latlng;
							closest_point_dist = cur_pt_dist;
						}
					}
					g_map.panTo(closest_point);
				}
			}
		}
	});
	
}

function on_sgname_changed() {
	refresh_graph_visuals();
	forget_path_objects();
	forget_multisnap_objects();
	forget_found_polyline();
	forget_found_vertex();
}

function on_vertid_button_clicked() {
	forget_found_vertex();
	var vertid = parseInt(get_value('vertid_field'));
	callpy('browse_snapgraph.get_vert_pos', get_sgname(), vertid, 
		{success: function(latlng__) {
			if(latlng__ === null) {
				alert('Vertex ID not found.');
			} else {
				var latlng = google_LatLng(latlng__);
				g_found_vertex = new google.maps.Circle({map: g_map, center: latlng, zIndex: 1, 
						radius: 200, fillColor: 'rgb(255,230,0)', fillOpacity: 0.6, strokeOpacity: 0});
				google.maps.event.addListener(g_found_vertex, 'click', forget_found_vertex);
				g_map.panTo(latlng);
			}
		}
	});
	
}


    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<br>
		Find polyline by index:<input type="text" size="10" name="plineidx_field" id="plineidx_field" value="790"/> <input type="button" id="plineidx_button" onclick="find_pline(parseInt(get_value('plineidx_field')), true)" value="Ok" /> 
		/////// Find vertex by ID:<input type="text" size="10" name="vertid_field" id="vertid_field" value="0"/> <input type="button" id="vertid_button" onclick="on_vertid_button_clicked()" value="Ok" /> <br>
		<input id="streets_button" type="radio" name="sgname" value="streets" onclick="on_sgname_changed()"  />
		<label for="streets_button">streets</label>
		<input id="tracks_button" type="radio" name="sgname" value="tracks" onclick="on_sgname_changed()" checked />
		<label for="tracks_button">tracks</label>
		 ////////
		<input type="checkbox" id="show_points_and_vertexes_checkbox" checked="checked" onclick="refresh_graph_visuals()" />
		<label for="show_points_and_vertexes_checkbox">Show points and vertexes</label> /////
		 ////////
		<input type="checkbox" id="path_checkbox" checked onclick="get_path_from_server()" />
		<label for="path_checkbox">Do path</label>
		<input type="checkbox" id="arrows_checkbox" name="arrows_checkbox" checked onclick="get_path_from_server()"/>
		<label for="arrows_checkbox">Show arrows on path</label>
		 ////////
		<input type="checkbox" id="multisnap_show_infowindows" />
		<label for="multisnap_show_infowindows">Multisnap: show infowindows</label> , 
		<input type="checkbox" id="multisnap_reducepts_checkbox" />
		<label for="multisnap_reducepts_checkbox">Multisnap: reduce points</label>
		<p id="p_error"/>
		<p id="p_marker_latlngs">Path markers: ...</p>
		<p id="p_multisnap_info"/>
		<p id="p_loading_urls"/>
  </body>
</html>
