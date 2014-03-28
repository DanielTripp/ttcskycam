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

var g_lines = new buckets.LinkedList();
var g_pt_markers = new buckets.LinkedList();
var g_path_pline = null;

function initialize() {

	init_map();

	google.maps.event.addListenerOnce(g_map, 'tilesloaded', function() {
		google.maps.event.addListener(g_map, 'click', function(e) {
			add_pt_marker(e.latLng);
		});
		init_map_sync('map_sync_checkbox', true);
	});

}

function remove_pt_markers() {
	remove_objects(g_pt_markers);
}

function remove_lines() {
	remove_objects(g_lines);
}

function forget_path_pline() {
	if(g_path_pline!=null) {
		g_path_pline.setMap(null);
		g_path_pline = null;
	}
}

function remove_objects(list_) {
	list_.forEach(function(marker) {
		marker.setMap(null);
	});
	list_.clear();
}

function add_lines_based_on_pt_markers() {
	for(var i=0; i<g_pt_markers.size()-1; i++) {
		add_line(i);
	}
}

function add_line(i_) {
	var latlng1 = g_pt_markers.elementAtIndex(i_).getPosition();
	var latlng2 = g_pt_markers.elementAtIndex(i_+1).getPosition();
	var line = new google.maps.Polyline({ clickable: true, map: g_map, path: [latlng1, latlng2], 
		strokeColor: 'rgb(255,0,0)', strokeWeight: 5, zIndex: 5
	});
	google.maps.event.addListener(line, 'click', function(e__) {
		split_line(i_, e__.latLng);
	});
	g_lines.add(line);
}

function split_line(lo_marker_ptaddr_, new_latlng_) {
	var marker_latlngs = new buckets.LinkedList();
	for(var i=0; i<g_pt_markers.size(); i++) {
		var marker = g_pt_markers.elementAtIndex(i);
		marker_latlngs.add(marker.getPosition());
		if(i == lo_marker_ptaddr_) {
			marker_latlngs.add(new_latlng_);
		}
	}

	remove_lines();
	remove_pt_markers();

	marker_latlngs.forEach(function(latlng) {
		add_pt_marker(latlng);
	});
}

function add_pt_marker(glatlon_) {
	var glatlon = glatlon_;

	var marker_ptaddr = g_pt_markers.size();

	var marker = new google.maps.Marker({position: glatlon, map: g_map, title:''+(marker_ptaddr), draggable: true, zIndex: -10, 
		icon: 'http://www.google.com/mapfiles/marker.png'});

	g_pt_markers.add(marker);

	google.maps.event.addListener(marker, 'drag', function() {
		redraw_pt_pline();
	});

	google.maps.event.addListener(marker, 'dragend', function() {
		get_path_from_server();
	});

	google.maps.event.addListener(marker, 'click', function() {
		delete_marker(marker_ptaddr);
		get_path_from_server();
	});

	redraw_pt_pline();
	get_path_from_server();
}

function get_path_from_server() {
	forget_path_pline();
	if(g_pt_markers.size() < 2) {
		return;
	}
	var latlngs = [];
	g_pt_markers.forEach(function(marker) {
		latlngs.push(marker.getPosition());
	});
	callpy('osrm.get_path', latlngs, 
		{success: function(r_) {
			forget_path_pline();
			var pts = [];
			r_.forEach(function(pathpt) {
				pts.push(new google.maps.LatLng(pathpt[0], pathpt[1]));
			});
			g_path_pline = new google.maps.Polyline({map: g_map, strokeColor: 'rgb(0,255,0)', path: pts, zIndex: 10});
		}}
	);
}

function delete_marker(marker_ptaddr_) {
	var marker_latlngs = new buckets.LinkedList();
	for(var i=0; i<g_pt_markers.size(); i++) {
		var marker = g_pt_markers.elementAtIndex(i);
		if(i == marker_ptaddr_) {
			continue;
		}
		marker_latlngs.add(marker.getPosition());
	}

	remove_lines();
	remove_pt_markers();

	marker_latlngs.forEach(function(latlng) {
		add_pt_marker(latlng);
	});
}

function redraw_pt_pline() {
	remove_lines();

	add_lines_based_on_pt_markers();

	var str_repr = '[<br/>';
	for(var i=0; i<g_pt_markers.size(); i++) {
		var m = g_pt_markers.elementAtIndex(i);
		str_repr += sprintf('[ %.6f,%.6f ]%s <br/>', m.getPosition().lat(), m.getPosition().lng(), 
			(i<g_pt_markers.size()-1 ? ',' : ''));
	}
	str_repr += ']<br/>';
	set_contents('p_latlngs', str_repr);

}

    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<br>
		<label><input id="map_sync_checkbox" type="checkbox"/>Map Sync</label><br>
		<p id="p_latlngs">latlngs will go here.</p>
		<p id="p_loading_urls"/>
  </body>
</html>
