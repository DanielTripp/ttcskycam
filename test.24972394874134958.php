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

function initialize() {

	init_map();
	init_street_polylines();

	g_map.setCenter(new google.maps.LatLng(43.6610036, -79.39));

	g_start_marker = new google.maps.Marker({
		position: new google.maps.LatLng(43.6610036, -79.3969135), 
		map: g_map,
		draggable: true, 
		icon: 'http://www.google.com/mapfiles/markerA.png'
		});

	g_dest_marker = new google.maps.Marker({
		position: new google.maps.LatLng(43.6683302, -79.3887810), 
		map: g_map,
		draggable: true, 
		icon: 'http://www.google.com/mapfiles/markerA.png'
		});

	google.maps.event.addListener(g_start_marker, 'dragend', get_path_from_server);
	google.maps.event.addListener(g_dest_marker, 'dragend', get_path_from_server);


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
			raw_path_pts_and_visited_vertexes_.forEach(function(raw_path_pt) {
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
