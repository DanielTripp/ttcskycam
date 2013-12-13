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

var g_objects = [];

function initialize() {

	init_map();
	g_map.setZoom(17);

	add_delayed_event_listener(g_map, 'bounds_changed', on_bounds_changed, 750);

}

function on_bounds_changed() {
	if(g_map.getZoom() < 16) {
		console.log('Zoom in more.');
		forget_objects();
		return;
	}
	var map_sw = g_map.getBounds().getSouthWest(), map_ne = g_map.getBounds().getNorthEast();
	callpy('browse_snapgraph.get_infos_for_box', map_sw, map_ne, 
		{success: function(r_) {
			forget_objects();
			var plineidx_to_pline = r_['plineidx_to_pline'], vertexid_to_info = r_['vertexid_to_info'];
			for(var plineidx in plineidx_to_pline) {
				var pline_pts = plineidx_to_pline[plineidx];
				make_pline(parseInt(plineidx, 10), pline_pts);
			}
			for(var vertexid in vertexid_to_info) {
				var vertinfo = vertexid_to_info[vertexid];
				make_vert_circle(vertinfo);
			}
			g_objects.push(new google.maps.Rectangle({map: g_map, bounds: g_map.getBounds(), fillOpacity: 0, clickable: false, 
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
	add_hover_listener(circle, function(latlng__) { 
			var infowin_content = sprintf('Vertex %d<br>', vertinfo_.id);
			vertinfo_.ptaddrs.forEach(function(ptaddr) {
				infowin_content += sprintf('pline %d pt %d, ', ptaddr[0], ptaddr[1]);
			});
			infowin_content = infowin_content.substring(0, infowin_content.length-2) + '<br>';
			infowin_content += 'Connected to: '+toJsonString(vertinfo_.connectedids);
			var infowin = new google.maps.InfoWindow({content: infowin_content, position: vertpos});
			infowin.open(g_map);

			var connected_vert_latlngs = callpy_sync('browse_snapgraph.get_connected_vert_latlngs', vertinfo_.id);
			var connected_vertex_map_objects = [];
			connected_vert_latlngs.forEach(function(latlng) {
				var color = 'rgb(75,75,75)';
				connected_vertex_map_objects.push(new google.maps.Circle({map: g_map, center: google_LatLng(latlng), radius: 30, 
						fillColor: color, fillOpacity: 1, strokeWeight: 0, zIndex: 0}));
				connected_vertex_map_objects.push(new google.maps.Polyline({map: g_map, path: [google_LatLng(latlng), vertpos], 
						strokeColor: color, strokeWeight: 20, zIndex: 0}));
			});

			// We (or rather the code inside add_hover_listener) doesn't always get the mouseout events, 
			// so here we provide a manual way to delete all of the map objects - by manually closing the info window. 
			google.maps.event.addListener(infowin, 'closeclick', function () {
				connected_vertex_map_objects.forEach(function(map_object) {
					map_object.setMap(null);
				});
			});

			return [infowin].concat(connected_vertex_map_objects);
		}, 250);
	g_objects.push(circle);
}

function make_pline(plineidx_, pline_pts_) {
	var glatlngs = google_LatLngs(pline_pts_);
	var pline = new google.maps.Polyline({map: g_map, path: glatlngs, strokeColor: get_polyline_color(glatlngs), 
			strokeWeight: 8, zIndex: 1});
	add_hover_listener(pline, function(latlng__) { 
			var infowin = new google.maps.InfoWindow({content: sprintf('pline %d', plineidx_), 
					position: latlng__});
			infowin.open(g_map);
			return infowin;
		}, 250);
	g_objects.push(pline);

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
	g_objects.push(circle);
}

function forget_objects() {
	g_objects.forEach(function(obj) {
		obj.setMap(null);
	});
	g_objects = [];
}

function get_polyline_color(polyline_latlngs_) {
	var colors = [[0, 0, 0], [150, 150, 150], [255, 0, 0], [255, 0, 255], [0, 255, 255], [0, 127, 0], 
			[130, 127, 0], [127, 0, 0], [127, 0, 127], [0, 127, 127, ], [0, 255, 0], [0, 0, 255]];
	var r = colors[get_polyline_color_hash(polyline_latlngs_) % colors.length];
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
		<p id="p_latlngs"/>
		<p id="p_loading_urls"/>
  </body>
</html>
