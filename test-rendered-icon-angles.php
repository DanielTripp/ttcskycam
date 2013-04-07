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

var g_trip_marker = null;
var g_trip_dest_marker = null;

function initialize() {

	init_map();

	var orig = new google.maps.LatLng(43.6494532, -79.4314174);
	var heading_latlngs = [
		[43.65932713, -79.43133163],
		[43.65920294, -79.42901420],
		[43.65895456, -79.42661094],
		[43.65845779, -79.42420768],
		[43.65752635, -79.42189025],
		[43.65678119, -79.41931533],
		[43.65572552, -79.41596794],
		[43.65423513, -79.41322136],
		[43.65206159, -79.41090393],
		[43.64932903, -79.41038894],
		[43.64690687, -79.41244888],
		[43.64473307, -79.41407966],
		[43.64274551, -79.41579628],
		[43.64175171, -79.41897201],
		[43.64013675, -79.42077446],
		[43.64187594, -79.42549514],
		[43.63783847, -79.42575264],
		[43.63659611, -79.42849922],
		[43.63721729, -79.43150329]];

	var heading_latlngs = [
		[43.65932713, -79.43133163],
		[43.66053985, -79.42991464], 
		[43.65920294, -79.42901420],
		[43.66035357, -79.42725389], 
		[43.65895456, -79.42661094],
		[43.66001205, -79.42450730],
		[43.65845779, -79.42420768],
		[43.65914273, -79.42193238],
		[43.65752635, -79.42189025],
		[43.65811815, -79.41931455],
		[43.65678119, -79.41931533],
		[43.65703146, -79.41618173],
		[43.65572552, -79.41596794],

[43.65513746, -79.41425054],
		[43.65423513, -79.41322136],
[43.65277765, -79.41377847],
		[43.65206159, -79.41090393],
[43.65047984, -79.41369264],
		[43.64932903, -79.41038894],
[43.64827511, -79.41347806],
		[43.64690687, -79.41244888],
[43.64625662, -79.41575257],
		[43.64473307, -79.41407966],
[43.64501444, -79.41828458],
		[43.64274551, -79.41579628],
[43.64414490, -79.42103116],
		[43.64175171, -79.41897201],
[43.64327535, -79.42304818],
		[43.64013675, -79.42077446],
[43.64280951, -79.42502229],
		[43.64187594, -79.42549514],
[43.64231261, -79.42699639],
		[43.63783847, -79.42575264],
[43.64200205, -79.42871301],
		[43.63659611, -79.42849922],
[43.64156726, -79.43060128],

		[43.63721729, -79.43150329],
	];

	for(var i=0; i<heading_latlngs.length; i++) {
		var latlng = google_LatLng(heading_latlngs[i]);
		console.log(latlng);
		var line = new google.maps.Polyline({map: g_map, path: [orig, latlng], strokeWeight: 7});

		var vehicle_lat = orig.lat()*0.2 + latlng.lat()*0.8;
		var vehicle_lng = orig.lng()*0.2 + latlng.lng()*0.8;
		//var heading = i*10;
		var heading = i*5;
		make_vehicle_marker('4000', 100, heading, vehicle_lat, vehicle_lng);
	}

	g_orig_marker = new google.maps.Marker({map: g_map, position: orig,
		draggable: false, icon: 'http://www.google.com/mapfiles/markerA.png'});
	g_dest_marker = new google.maps.Marker({map: g_map, position: new google.maps.LatLng(orig.lat() + 0.01, orig.lng() + 0.01),
		draggable: true, icon: 'http://www.google.com/mapfiles/markerB.png'});

	google.maps.event.addListener(g_orig_marker, 'dragend', on_marker_moved);
	google.maps.event.addListener(g_dest_marker, 'drag', on_marker_moved);


	var heading = 315;
	var sizes = [130, 100, 80, 70, 60, 50, 30, 17, 10];
	for(var i=0; i<sizes.length; i++) {
		var size = sizes[i];
		make_vehicle_marker('1000', size, heading, 43.6572158, -79.4489  - i*0.005);
	}



}

function make_vehicle_marker(vid_, size_, heading_, lat_, lon_) {
	var marker = new google.maps.Marker({
			position: new google.maps.LatLng(lat_, lon_),
			map: g_map,
			draggable: true,
			icon: new google.maps.MarkerImage(get_vehicle_url(vid_, size_, heading_, true), 
					null, null, new google.maps.Point(size_/2, size_/2)),
			visible: false, 
			title: ''+heading_, 
			clickable: false,
			zIndex: 5
		});
	marker.setVisible(true);
	return marker;
}

function get_vehicle_url(vid_, size_, heading_, static_aot_moving_) {
	var filename = '';
	if(true) {
		var vehicletype = (is_a_streetcar(vid_) ? 'streetcar' : 'bus');
		filename = sprintf('%s-%s-size-%d-heading-%d.png', vehicletype, (static_aot_moving_ ? 'static' : 'moving'), size_, heading_);
	} else {
		filename = sprintf('vehicle_arrow_%d_%d_%s.png', size_, heading_, (static_aot_moving_ ? 'static' : 'moving'));
	}
	return 'img/'+filename;
}

function on_marker_moved() {
	var heading = callpy_sync('geom.heading', g_orig_marker.getPosition(), g_dest_marker.getPosition());
	set_contents('p_heading', sprintf('heading: %d', heading));
	set_contents('p_dest_latlng', sprintf('dest latlng: %.8f, %.8f', g_dest_marker.getPosition().lat(), g_dest_marker.getPosition().lng()));
}

function on_add_button_clicked() {
	var new_latlng_str = sprintf('%.8f, %.8f', g_dest_marker.getPosition().lat(), g_dest_marker.getPosition().lng());
	set_contents('p_all', get_contents('p_all')+'<br>'+new_latlng_str);
	
}

function is_a_streetcar(vid_) {
	// At least, I think that starting w/ 4 means streetcar.  This logic is also implemented in vinfo.py. 
	return vid_.charAt(0) == '4';
}


    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<input type="button" onclick="on_add_button_clicked()" value="Add" />
		<p id="p_heading">...</p>
		<p id="p_dest_latlng">...</p>
		<p id="p_all"></p>
  </body>
</html>
