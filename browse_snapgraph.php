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

var g_static_graph_objects = [];
var g_path_objects = [];
var g_start_marker = null, g_dest_marker = null;
var g_connected_vertex_map_objects = [];
var g_multisnap_markers = [];

function initialize() {

	init_map();
	g_map.setZoom(17);

	g_start_marker = new google.maps.Marker({map: g_map, position: new google.maps.LatLng(43.6540022, -79.4124381), 
			icon: 'http://www.google.com/mapfiles/markerA.png', draggable: true});
	g_dest_marker  = new google.maps.Marker({map: g_map, position: new google.maps.LatLng(43.6545922, -79.4086401), 
			icon: 'http://www.google.com/mapfiles/markerB.png', draggable: true});
	google.maps.event.addListener(g_start_marker, 'click', forget_path_objects);
	google.maps.event.addListener(g_dest_marker, 'click', forget_path_objects);
	google.maps.event.addListener(g_start_marker, 'dragend', on_path_marker_dragged);
	google.maps.event.addListener(g_dest_marker, 'dragend', on_path_marker_dragged);

	google.maps.event.addListener(g_map, 'click', on_map_clicked);

	add_delayed_event_listener(g_map, 'bounds_changed', on_bounds_changed, 750);

}

function on_map_clicked(mouseevent_) {
	forget_multisnap_markers();
	set_contents('p_multisnap_latlng', '');
	callpy('browse_snapgraph.multisnap', mouseevent_.latLng, 
		{success: function(latlngs__) {
			set_contents('p_multisnap_latlng', sprintf('Multisnap:&nbsp;&nbsp;&nbsp;(%.8f,%.8f)', mouseevent_.latLng.lat(), mouseevent_.latLng.lng()));
			latlngs__.forEach(function(latlng) {
				var marker = new google.maps.Marker({map: g_map, position: google_LatLng(latlng), draggable: false});
				g_multisnap_markers.push(marker);
			});
			g_multisnap_markers.forEach(function(marker) {
				google.maps.event.addListener(marker, 'click', forget_multisnap_markers);
			});
		}
	});
}

function forget_multisnap_markers() {
	g_multisnap_markers.forEach(function(marker) {
		marker.setMap(null);
	});
	g_multisnap_markers = [];
}

function on_path_marker_dragged() {
	set_marker_latlngs_contents();

	forget_path_objects();
	callpy('browse_snapgraph.find_paths', g_start_marker.getPosition(), g_dest_marker.getPosition(), 
		{success: function(paths__) {
			if(paths__.length > 0) {
				var shortest_path_pline = new google.maps.Polyline({map: g_map, path: google_LatLngs(paths__[0]), zIndex: 12, 
						strokeColor: 'rgb(200,200,200)', strokeWeight: 6, clickable: false});
				g_path_objects.push(shortest_path_pline);
				for(var i=1; i<paths__.length; i++) {
					var path_pline = new google.maps.Polyline({map: g_map, path: google_LatLngs(paths__[i]), zIndex: 11, 
							strokeColor: 'rgb(100,100,100)', strokeWeight: 6, clickable: false});
					g_path_objects.push(path_pline);
				}
			}
		} 
		});
}

function set_marker_latlngs_contents() {
	var start = g_start_marker.getPosition(), dest = g_dest_marker.getPosition();
	set_contents('p_marker_latlngs', sprintf('Path markers:&nbsp;&nbsp;&nbsp;&nbsp;(%.8f,%.8f)&nbsp;&nbsp;&nbsp;&nbsp;(%.8f,%.8f)', 
			start.lat(), start.lng(), dest.lat(), dest.lng()));
}

function on_bounds_changed() {
	if(g_map.getZoom() < 16) {
		console.log('Zoom in more.');
		forget_static_graph_objects();
		return;
	}
	var map_sw = g_map.getBounds().getSouthWest(), map_ne = g_map.getBounds().getNorthEast();
	callpy('browse_snapgraph.get_infos_for_box', map_sw, map_ne, 
		{success: function(r_) {
			forget_static_graph_objects();
			var plineidx_to_pline = r_['plineidx_to_pline'], vertexid_to_info = r_['vertexid_to_info'];
			for(var plineidx in plineidx_to_pline) {
				var pline_pts = plineidx_to_pline[plineidx];
				make_pline(parseInt(plineidx, 10), pline_pts);
			}
			for(var vertexid in vertexid_to_info) {
				var vertinfo = vertexid_to_info[vertexid];
				make_vert_circle(vertinfo);
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
	var circle = new google.maps.Circle({map: g_map, center: vertpos, radius: 20, 
			fillOpacity: 0, zIndex: 10});
	google.maps.event.addListener(circle, 'click', function() {
			forget_connected_vertex_map_objects();
			var infowin_content = sprintf('Vertex %d<br>', vertinfo_.id);
			vertinfo_.ptaddrs.forEach(function(ptaddr) {
				infowin_content += sprintf('pline %d pt %d, ', ptaddr[0], ptaddr[1]);
			});
			infowin_content = infowin_content.substring(0, infowin_content.length-2) + '<br>';
			infowin_content += 'Connected to: '+toJsonString(vertinfo_.connectedids);
			var infowin = new google.maps.InfoWindow({content: infowin_content, position: vertpos, disableAutoPan: true});
			g_connected_vertex_map_objects.push(infowin);
			infowin.open(g_map);

			var connected_vert_latlngs = callpy_sync('browse_snapgraph.get_connected_vert_latlngs', vertinfo_.id);
			connected_vert_latlngs.forEach(function(latlng) {
				var color = 'rgb(75,75,75)';
				g_connected_vertex_map_objects.push(new google.maps.Circle({map: g_map, center: google_LatLng(latlng), radius: 30, 
						fillColor: color, fillOpacity: 1, strokeWeight: 0, zIndex: 0}));
				g_connected_vertex_map_objects.push(new google.maps.Polyline({map: g_map, path: [google_LatLng(latlng), vertpos], 
						strokeColor: color, strokeWeight: 20, zIndex: 0}));
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
			strokeWeight: 6, zIndex: 1});
	add_hover_listener(pline, function(latlng__) { 
			var infowin = new google.maps.InfoWindow({content: sprintf('pline %d', plineidx_), 
					position: latlng__, disableAutoPan: true});
			infowin.open(g_map);
			return infowin;
		}, 250);
	g_static_graph_objects.push(pline);

	for(var i in pline_pts_) {
		var pline_pt = pline_pts_[i];
		make_pline_pt_circle(plineidx_, parseInt(i, 10), pline_pt);
	}
}

function make_pline_pt_circle(plineidx_, ptidx_, pt_) {
	var circle = new google.maps.Circle({map: g_map, center: google_LatLng(pt_), radius: 10, 
			fillOpacity: 0.4, strokeOpacity: 0, zIndex: 9});
	add_hover_listener(circle, function(latlng__) { 
			var infowin = new google.maps.InfoWindow({content: sprintf('pline %d, pt %d', plineidx_, ptidx_), 
					position: latlng__});
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

function get_polyline_color_hash(polyline_latlngs_) {
	var r = 0;
	polyline_latlngs_.forEach(function(latlng) {
		r += latlng.lat()*100000 + latlng.lng()*100000;
	});
	return Math.round(Math.abs(r));
}



    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<br>
		<p id="p_error"/>
		<p id="p_loading_urls"/>
		<p id="p_marker_latlngs"/>
		<p id="p_multisnap_latlng"/>
  </body>
</html>
