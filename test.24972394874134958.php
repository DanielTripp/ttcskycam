<!DOCTYPE html>
<html>
  <head>
		<title>test</title>
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


var g_start_marker, g_dest_marker;

var g_path_polyline = null;
var g_visited_vertex_markers = [];

var g_grid_objects = new Array();

var g_supercover_objects = [];

var LATREF = <?php 
  passthru('python -c "import snapgraph; print snapgraph.LATREF"'); ?>;
var LNGREF = <?php 
  passthru('python -c "import snapgraph; print snapgraph.LNGREF"'); ?>;
var LATSTEP = <?php 
  passthru('python -c "import snapgraph; print snapgraph.LATSTEP"'); ?>;
var LNGSTEP = <?php 
  passthru('python -c "import snapgraph; print snapgraph.LNGSTEP"'); ?>;

function initialize() {

	init_map();
	//init_street_polylines();

	g_map.setCenter(new google.maps.LatLng(43.6610036, -79.39));

	g_start_marker = new google.maps.Marker({
		position: new google.maps.LatLng(43.6610036, -79.3969135), 
		map: g_map,
		draggable: true, 
		icon: 'http://www.google.com/mapfiles/markerA.png', 
		zIndex: 5
		});

	g_dest_marker = new google.maps.Marker({
		position: new google.maps.LatLng(43.6683302, -79.3887810), 
		map: g_map,
		draggable: true, 
		icon: 'http://www.google.com/mapfiles/markerB.png', 
		zIndex: 5
		});

	google.maps.event.addListener(g_start_marker, 'dragend', on_drag_end);
	google.maps.event.addListener(g_dest_marker, 'dragend', on_drag_end);

	google.maps.event.addListener(g_map, 'dragstart', erase_grid);
	add_delayed_event_listener(g_map, 'bounds_changed', redraw_grid, 100);


}

function redraw_grid() {
	erase_grid();
	draw_grid();
}

function lat_to_gridlat(lat_) {
  return fdiv(lat_ - LATREF, LATSTEP);
}

function gridlat_to_lat(gridlat_) {
  return gridlat_*LATSTEP + LATREF;
}

function lng_to_gridlng(lng_) {
  return fdiv(lng_ - LNGREF, LNGSTEP);
}

function gridlng_to_lng(gridlng_) {
  return gridlng_*LNGSTEP + LNGREF;
}

function draw_grid() {
	draw_grid_lngs();
	draw_grid_lats();
}

// Same as the map bounds but a bit smaller on the north and east, so that the 
// grid lines don't overlap with the numbers that label those lines. 
function getGridBounds() {
	var orig_bounds = g_map.getBounds();
	var orig_sw = orig_bounds.getSouthWest(), orig_ne = orig_bounds.getNorthEast();
	var north_lat = (orig_ne.lat() - orig_sw.lat())*0.93 + orig_sw.lat();
	var east_lng = (orig_ne.lng() - orig_sw.lng())*0.97 + orig_sw.lng();
	return new google.maps.LatLngBounds(orig_sw, new google.maps.LatLng(north_lat, east_lng));
}

function draw_grid_lats() {
	var gridbounds = getGridBounds();
	for(var gridlat = lat_to_gridlat(gridbounds.getSouthWest().lat()); 
				gridlat <= lat_to_gridlat(gridbounds.getNorthEast().lat()); gridlat++) {
		var lat = gridlat_to_lat(gridlat);
		var pts = new Array();
		pts.push(new google.maps.LatLng(lat, gridbounds.getSouthWest().lng()));
		pts.push(new google.maps.LatLng(lat, gridbounds.getNorthEast().lng()));
		var line = new google.maps.Polyline({map: g_map, path: pts, strokeColor: 'rgb(0,0,255)', strokeWeight: (gridlat % 10 == 0 ? 1 : 0.5), 
			clickable: false});
		g_grid_objects.push(line);
		var marker = new RichMarker({
			position: new google.maps.LatLng(lat, g_map.getBounds().getNorthEast().lng()), 
			map: g_map,
			draggable: false,
			flat: true, 
			anchor: RichMarkerPosition.RIGHT, 
			content: get_number_label_svg(gridlat)
			});
		g_grid_objects.push(marker);
	}
}

function draw_grid_lngs() {
	var gridbounds = getGridBounds();
	for(var gridlng = lng_to_gridlng(gridbounds.getSouthWest().lng()); 
				gridlng <= lng_to_gridlng(gridbounds.getNorthEast().lng()); gridlng++) {
		var lng = gridlng_to_lng(gridlng);
		var pts = new Array();
		pts.push(new google.maps.LatLng(gridbounds.getSouthWest().lat(), lng));
		pts.push(new google.maps.LatLng(gridbounds.getNorthEast().lat(), lng));
		var line = new google.maps.Polyline({map: g_map, path: pts, strokeColor: 'rgb(0,0,255)', strokeWeight: (gridlng % 10 == 0 ? 1 : 0.5), 
			clickable: false});
		g_grid_objects.push(line);
		var marker = new RichMarker({
			position: new google.maps.LatLng(g_map.getBounds().getNorthEast().lat(), lng), 
			anchor: RichMarkerPosition.TOP, 
			map: g_map,
			draggable: false,
			flat: true, 
			content: get_number_label_svg(gridlng)
			});
		g_grid_objects.push(marker);
	}
}

function get_number_label_svg(num_) {
	return sprintf('<svg width="20" height="20" version="1.1">' +
			'<rect x="0" y="0" width="20" height="20" style="fill:white;stroke:blue;stroke-width:0.5;fill-opacity:1.0;stroke-opacity:1.0"/>' +
			'<text x="0" y="15" font-size="15" font-weight="bold" fill="rgb(0,0,255)">%d</text>' +
			'</svg>', 
			num_);
}

function erase_grid() {
	while(g_grid_objects.length > 0) {
		g_grid_objects.pop().setMap(null);
	}
}


function on_zoom_changed() {
	set_contents('p_zoom', sprintf('zoom: %d', g_map.getZoom()));
}

function on_drag_end() {
	//get_path_from_server();
	get_supercover();
}

function get_supercover() {
	while(g_supercover_objects.length > 0) {
		g_supercover_objects.pop().setMap(null);
	}
	callpy('t.get_supercover', g_start_marker.getPosition(), g_dest_marker.getPosition(), 
		{success: function(gridsquares_) {
			gridsquares_.forEach(function(gridsquare) {
				var bottomlat = gridlat_to_lat(gridsquare[0]);
				var toplat = gridlat_to_lat(gridsquare[0]+1);
				var leftlng = gridlng_to_lng(gridsquare[1]);
				var rightlng = gridlng_to_lng(gridsquare[1]+1);
				var sw = new google.maps.LatLng(bottomlat, leftlng);
				var ne = new google.maps.LatLng(toplat, rightlng);
				var nw = new google.maps.LatLng(toplat, leftlng);
				var se = new google.maps.LatLng(bottomlat, rightlng);
				g_supercover_objects.push(new google.maps.Polyline({map: g_map, path: [sw, ne]}));
				g_supercover_objects.push(new google.maps.Polyline({map: g_map, path: [nw, se]}));
			});
		}, 
		error: function() {
			console.log('error getting supercover');
		}}
		);
}

function init_street_polylines() {
	callpy('t.get_snapgraph_polylines', 
		{success: function(raw_polylines_) {
			var polylines = to_google_LatLng_polylines(raw_polylines_);
			polylines.forEach(function(polyline) {
				new google.maps.Polyline({map: g_map, path: polyline, 
						strokeColor: 'rgb(100,100,100)', zIndex: 4, strokeOpacity: 0.5});
			});
		}, 
		error: function() {
			console.log('error getting street polylines');
		}}
	);
}

function get_path_from_server() {
	set_contents('p_latlngs', sprintf('(%.8f,%.8f) &nbsp;&nbsp;&nbsp; (%.8f,%.8f)', 
			g_start_marker.getPosition().lat(), g_start_marker.getPosition().lng(), 
			g_dest_marker.getPosition().lat(), g_dest_marker.getPosition().lng()));

	callpy('t.get_path', g_start_marker.getPosition(), g_dest_marker.getPosition(), 
		{success: function(raw_path_pts_and_visited_vertexes_) {
			set_contents('p_error', '');
			var path_pts = [];
			raw_path_pts_and_visited_vertexes_[0].forEach(function(raw_path_pt) {
				path_pts.push(new google.maps.LatLng(raw_path_pt[0], raw_path_pt[1]));
			});
			if(g_path_polyline != null) {
				g_path_polyline.setMap(null);
				g_path_polyline = null;
			}
			g_path_polyline = new google.maps.Polyline({map: g_map, path: path_pts, strokeColor: 'rgb(255,0,0)', zIndex: 5});

			while(g_visited_vertex_markers.length > 0) {
				var marker = g_visited_vertex_markers.pop();
				marker.setMap(null);
			}
			google_LatLngs(raw_path_pts_and_visited_vertexes_[1]).forEach(function(visited_vertex) {
				g_visited_vertex_markers.push(new google.maps.Marker({map: g_map, position: visited_vertex, 
						icon: 'http://labs.google.com/ridefinder/images/mm_20_red.png'}));
			});
		}, 
		error: function() {
			set_contents('p_error', '>>>> ERROR <<<<');
		}}
	);
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
