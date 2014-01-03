<!DOCTYPE html>
<html>
  <head>
		<title>show_points_file</title>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 70%; margin: 0; padding: 0 }
    </style>
    <script type="text/javascript"
		      src="http://maps.googleapis.com/maps/api/js?sensor=false&v=3">
					    </script>
		<script type="text/javascript" src="js/richmarker-compiled.js"></script>
		<script type="text/javascript" src="js/jquery-1.7.1.min.js"></script>
		<script type="text/javascript" src="common.js"></script>
		<script type="text/javascript" src="js/buckets-minified.js"></script>
		<script type="text/javascript" src="js/oms.min.js"></script>
    <script type="text/javascript">

var POLYLINE_STROKEWEIGHT = 3;

// array of array of google LatLngs. 
var g_polyline_latlngs = [];
// array of google Markers. 
var g_markers = []; 
var g_bounding_rect = null;
var g_opacity = 0.5;
// array of google polylines 
var g_polylines = [];

var g_show_dist_pt1 = null, g_show_dist_pt2 = null;
var g_show_dist_infowindow = null, g_show_dist_polyline = null;
var g_mouseovered_object_infowindow = null;
var g_mouseovered_object_infowindow_close_timer = null;

var g_grid_objects = new Array();

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

	init_spiderfying();

	// Using a delayed listener for the grid redraw because bounds_changed events can happen dozens of times a second while 
	// drag-scrolling the map, and redrawing on every one of those was making that dragging very choppy.  
	// And I see no utility in redrawing the map more than 10 times per second.  
	// Furthermore - the idea behind erasing the grid on dragstart is to make scrolling even smoother, because the fewer 
	// objects are on the map, the smoother the scrolling will be.   (I'm fairly sure that I noticed a difference in 
	// scrolling smoothness with this erasing but it's not as pronounced as the difference that the delayed listener makes.)
	google.maps.event.addListener(g_map, 'dragstart', erase_grid);
	add_delayed_event_listener(g_map, 'bounds_changed', redraw_grid, 100);

	google.maps.event.addListener(g_map, 'zoom_changed', on_zoom_changed);
	on_zoom_changed();

	google.maps.event.addListener(g_map, 'rightclick', function(mouseevent_) {
		on_mouse_click_for_show_dist(mouseevent_.latLng);
	});

  $('#filename_field').keydown(function (e){
      if(e.keyCode == 13) {
				refresh_from_file();
      }
    });

	if(true) { 
		//set_value('filename_field', 'simp2');
		//refresh_from_file();
		refresh_from_textarea();
	}

}

function init_spiderfying() {
	g_spiderfier = new OverlappingMarkerSpiderfier(g_map, {markersWontMove: true, markersWontHide: true});

	g_spiderfier.addListener('spiderfy', function(markers__) {
		if(g_mouseovered_object_infowindow != null) {
			g_mouseovered_object_infowindow.close();
			g_mouseovered_object_infowindow = null;
		}
		for(var i=0; i<markers__.length; i++) {
			markers__[i].setIcon(make_marker_icon('rgb(0,255,0)'));
		} 
	});
	g_spiderfier.addListener('unspiderfy', function(markers__) {
		if(g_mouseovered_object_infowindow != null) {
			g_mouseovered_object_infowindow.close();
			g_mouseovered_object_infowindow = null;
		}
		for(var i=0; i<markers__.length; i++) {
			markers__[i].setIcon(make_marker_icon());
		}
	});
}

function redraw_grid() {
	erase_grid();
	if(is_selected('grid_checkbox')) {
		draw_grid();
	}
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
			clickable: false, zIndex: 5});
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
			clickable: false, zIndex: 5});
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
	return sprintf('<svg width="30" height="20" version="1.1">' +
			'<rect x="0" y="0" width="30" height="20" style="fill:white;stroke:blue;stroke-width:0.5;fill-opacity:1.0;stroke-opacity:1.0"/>' +
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
	if(is_selected('arrows_checkbox')) {
		redraw_objects();
	}
}

function refresh_from_file() {
	forget_drawn_objects();
	get_latlngs_from_file();
	draw_objects();
}

function get_latlngs_from_file() {
	var contents_str = get_sync(get_value('filename_field'), {cache: false});
	get_latlngs_from_string(contents_str);
}

function refresh_from_textarea() {
	forget_drawn_objects();
	get_latlngs_from_textarea();
	draw_objects();
}

function get_latlngs_from_textarea() {
	var contents_str = get_value('contents_textarea');
	get_latlngs_from_string(contents_str);
}

function get_latlngs_from_string(str_) {
	g_polyline_latlngs = [];
	if(str_ != null) {
		var raw_polylines = [];
		try {
			var str = str_.replace(/\(/g, '[');
			str = str.replace(/\)/g, ']');
			try {
				raw_polylines = $.parseJSON(str);
				console.log('Slightly massaged JSON parse succeeded.');
			} catch(e) {
				while(str.length > 0 && str.match(/^-79\.\d\d\d+/) == null && str.charAt(0) !== '[') { // remove leading non-JSON: 
					str = str.substring(1, str.length);
				}
				while(str.length > 0 && str.match(/43\.\d\d\d+$/) == null && str.charAt(str.length-1) !== ']') { // remove trailing non-JSON: 
					str = str.substring(0, str.length-1);
				}
				console.log(sprintf('Trying massaged JSON: "%s"', str));
				raw_polylines = $.parseJSON('['+str+']');
				console.log('JSON parse succeeded.');
			}
			if(typeof raw_polylines[0][0] === 'number') { // file contains a polyline, not a list of polylines? 
				raw_polylines = [raw_polylines]; // now it's a list of polylines. 
			}
		} catch(e) {
			console.log('JSON parse failed.');
			// So it wasn't JSON.    Maybe it's XML: 
			try {
				var polyline = [];
				var dom = $.parseXML(str);
				$(dom).find('*').each(function() {
					var lat = $(this).attr('lat'), lng = $(this).attr('lon');
					if(lat != undefined && lng != undefined) {
						polyline.push([lat, lng]);
					}
				});
				raw_polylines.push(polyline);
			} catch(err) {
				var polyline = [];
				raw_polylines.push(polyline);
				var filelines = str_.split('\n');
				for(var filelinei in filelines) {
					var fileline = filelines[filelinei];
					var regex = /.*?(43\.\d+).*?(-79\.\d+).*/g;
					var match = regex.exec(fileline);
					if(match != null) {
					  var lat = parseFloat(match[1], 10);
						var lng = parseFloat(match[2], 10);
						polyline.push([lat, lng]);
					}
				}
			}
		}
		raw_polylines.forEach(function(raw_polyline) {
			var latlng_polyline = [];
			g_polyline_latlngs.push(latlng_polyline);
			raw_polyline.forEach(function(rawpt) {
				var latlng = new google.maps.LatLng(rawpt[0], rawpt[1]);
				latlng_polyline.push(latlng);
			});
		});
	}
}

function flatfile_get_fields_from_line(line_) {
	var line = line_;
	while(true) {
		var c = line.charAt(line.length-1);
		if(c == '\n' || c == '\r' || c == ' ') {
			line = line.substring(0, line.length-1);
		} else {
			break;
		}
	}
	var r = line.split(',');
	for(var i in r) {
		r[i] = cleanup_field(r[i]);
	}
	return r;
}

function cleanup_field(val_) {
  return val_.replace(/.*?([-]?\d+\.\d+).*/g, "$1");
}

function redraw_objects() {
	forget_drawn_objects();
	draw_objects();
}

function forget_drawn_objects() {
	g_markers.forEach(function(e) {
		e.setMap(null);
	});
	g_markers = [];

	if(g_bounding_rect != null) {
		g_bounding_rect.setMap(null);
		g_bounding_rect = null;
	}

	g_polylines.forEach(function(polyline) {
		polyline.setMap(null);
	});
	g_polylines = [];
}

function draw_objects() {
	var minlat=90, maxlat=0, minlng=0, maxlng=-180;

	var draw_dots = is_selected('dots_checkbox');

	var lineidx=0, ptidx=0;
	g_polyline_latlngs.forEach(function(line_latlngs) {
		line_latlngs.forEach(function(latlng) {

			if(draw_dots) {
				make_marker(latlng, sprintf('%d/%d -&nbsp;&nbsp;&nbsp;&nbsp;(%.8f,%.8f)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;', lineidx, ptidx, latlng.lat(), latlng.lng()));
			}

			minlat = Math.min(minlat, latlng.lat());
			maxlat = Math.max(maxlat, latlng.lat());
			minlng = Math.min(minlng, latlng.lng());
			maxlng = Math.max(maxlng, latlng.lng());

			ptidx += 1;
		});
		lineidx += 1;
		ptidx = 0;
	});

	var rect_bounds = new google.maps.LatLngBounds(
			new google.maps.LatLng(minlat, minlng), new google.maps.LatLng(maxlat, maxlng));
	g_bounding_rect = new google.maps.Rectangle({bounds: rect_bounds, map: g_map, strokeColor: 'rgb(0,0,0)', 
			strokeOpacity: 0.5, strokeWeight: 1, fillOpacity: 0, zIndex: -10, clickable: false});

	if(is_selected('polyline_checkbox')) {
		draw_polylines();
	}

	refresh_dists();
}

function refresh_dists() {
	var contents = '';
	var all_polylines_dist_m = 0;
	for(var i=0; i<g_polyline_latlngs.length; i++) {
		var pline_latlngs = g_polyline_latlngs[i];
		var polyline_dist_m = 0;
		for(var j=0; j<pline_latlngs.length-1; j++) {
			var pt1 = pline_latlngs[j]; pt2 = pline_latlngs[j+1];
			var lineseg_dist_m = dist_m(pt1, pt2);
			polyline_dist_m += lineseg_dist_m;
		}
		contents += sprintf('polyline [%d]: %d points, %.2f meters<br>', i, pline_latlngs.length, polyline_dist_m);
		all_polylines_dist_m += polyline_dist_m;
	}
	contents += sprintf('sum total of all polyline lengths: %.2f meters<br>', all_polylines_dist_m);
	set_contents('p_dists', contents);
}

function draw_polylines() {
	for(var i=0; i<g_polyline_latlngs.length; i++) {
		var polyline_latlngs = g_polyline_latlngs[i];
		var polylineOptions = {path: polyline_latlngs, strokeWeight: POLYLINE_STROKEWEIGHT, strokeOpacity: 0.7, 
				strokeColor: get_polyline_color(polyline_latlngs), clickable: false, 
				icons: (is_selected('arrows_checkbox') ? make_polyline_arrow_icons(g_map.getZoom(), polyline_latlngs) : null), 
				map: g_map};
		var polyline = new google.maps.Polyline(polylineOptions);
		add_marker_mouseover_listener_for_infowin(polyline, sprintf('line #%d', i));
		g_polylines.push(polyline);
	}
}

function get_polyline_color(polyline_latlngs_) {
	if(is_selected('colors_checkbox')) {
		var colors = [[0, 0, 0], [150, 150, 150], [255, 0, 0], [255, 0, 255], [0, 255, 255], [0, 127, 0], 
				[130, 127, 0], [127, 0, 0], [127, 0, 127], [0, 127, 127, ], [0, 255, 0], [0, 0, 255]];
		var r = colors[get_polyline_color_hash(polyline_latlngs_) % colors.length];
		return sprintf('rgb(%d,%d,%d)', r[0], r[1], r[2]);
	} else {
		return 'rgb(0,0,0)';
	}
}

function get_polyline_color_hash(polyline_latlngs_) {
	var r = 0;
	polyline_latlngs_.forEach(function(latlng) {
		r += latlng.lat()*100000 + latlng.lng()*100000;
	});
	return Math.round(Math.abs(r));
}

function make_marker_icon(color_) {
	return {path: google.maps.SymbolPath.CIRCLE, scale: 14, strokeWeight : 0, fillOpacity: g_opacity, 
			fillColor: (color_ === undefined ? 'black' : color_)};
}

function make_marker(latlng_, label_) {
	var marker = new google.maps.Marker({position: latlng_, map: g_map, icon: make_marker_icon()});
	g_markers.push(marker);
	add_marker_mouseover_listener_for_infowin(marker, label_);
	g_spiderfier.addMarker(marker);
	add_marker_click_listener_for_show_dist(marker);
}

function add_marker_mouseover_listener_for_infowin(mapobject_, label_) {
	var infowin = new google.maps.InfoWindow({disableAutoPan: true, content: label_});
	google.maps.event.addListener(mapobject_, 'mouseover', function(mouseevent_) {
		if(g_mouseovered_object_infowindow != null) {
			g_mouseovered_object_infowindow.close();
			g_mouseovered_object_infowindow = null;
		}
		if(g_mouseovered_object_infowindow_close_timer != null) {
			clearTimeout(g_mouseovered_object_infowindow_close_timer);
			g_mouseovered_object_infowindow_close_timer = null;
		}
		var pos = null;
		if(mapobject_.getPosition === 'function') { // marker probably. 
			pos = marker_.getPosition();
		} else {
			pos = mouseevent_.latLng;
		}
		var map_height_lat= g_map.getBounds().getNorthEast().lat() - g_map.getBounds().getSouthWest().lat(); 
		pos = new google.maps.LatLng(pos.lat() + map_height_lat*0.03, pos.lng());
		infowin.setPosition(pos);
		infowin.open(g_map);
		g_mouseovered_object_infowindow = infowin;
	});
	google.maps.event.addListener(mapobject_, 'mouseout', function() {
		if(g_mouseovered_object_infowindow_close_timer != null) {
			clearTimeout(g_mouseovered_object_infowindow_close_timer);
			g_mouseovered_object_infowindow_close_timer = null;
		}
		g_mouseovered_object_infowindow_close_timer = setTimeout(function() {
			infowin.close();
			g_mouseovered_object_infowindow_close_timer = null;
		}, 1000);
	});
}

function add_marker_click_listener_for_show_dist(marker_) {
	google.maps.event.addListener(marker_, 'rightclick', function() {
		on_mouse_click_for_show_dist(marker_.getPosition());
	});
}

function on_mouse_click_for_show_dist(latlng_) {
	if(g_show_dist_pt1 != null  && g_show_dist_pt2 != null) {
		reset_show_dist_everything();
	}

	if(g_show_dist_pt1 == null) {
		assert(g_show_dist_pt2 == null);
		g_show_dist_pt1 = latlng_;
	} else if(g_show_dist_pt2 == null) {
		g_show_dist_pt2 = latlng_;
		g_show_dist_infowindow = new google.maps.InfoWindow({position: g_show_dist_pt2, disableAutoPan: true, 
				content: sprintf('distance: %.2f meters', dist_m(g_show_dist_pt1, g_show_dist_pt2))});
		google.maps.event.addListener(g_show_dist_infowindow, 'closeclick', reset_show_dist_everything);
		g_show_dist_infowindow.open(g_map);

		g_show_dist_polyline = new google.maps.Polyline({path: [g_show_dist_pt1, g_show_dist_pt2], strokeWeight: 4, 
				strokeColor: 'red', clickable: false, map: g_map});
	}
}

function reset_show_dist_everything() {
	if(g_show_dist_infowindow != null) {
		g_show_dist_infowindow.close();
		g_show_dist_infowindow = null;
	}
	if(g_show_dist_polyline != null) {
		g_show_dist_polyline.setMap(null);
		g_show_dist_polyline = null;
	}
	g_show_dist_pt1 = null;
	g_show_dist_pt2 = null;
}

function on_opacity_down_clicked() {
	g_opacity = Math.max(g_opacity-0.1, 0.0);
	redraw_objects();
}

function on_opacity_up_clicked() {
	g_opacity = Math.min(g_opacity+0.1, 1.0);
	redraw_objects();
}

function on_grid_checkbox_clicked() {
	if(is_selected('grid_checkbox')) {
		draw_grid();
	} else {
		erase_grid();
	}
}

function on_submit_contents_clicked() {
}


    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:80%; height:100%"></div>
		Filename: <input type="text" size="80" name="filename_field" id="filename_field" /> <br>
		OR Contents:<br>
		<textarea id="contents_textarea" cols="80" rows="5">
		[(43.6585890,-79.3965331), (43.6579360,-79.3997590), (43.6587210,-79.3958810), (43.6592179,-79.3935154), (43.6598780,-79.3903730), (43.6592179,-79.3935154), (43.6601232,-79.3891835)]
		</textarea> 
		<input type="button" onclick="refresh_from_textarea()" value="Submit Contents" />
		<br>
		<input type="button" onclick="on_opacity_down_clicked()" value="Opacity DOWN" />
		<input type="button" onclick="on_opacity_up_clicked()" value="Opacity UP" />
		<input checked type="checkbox" id="dots_checkbox" name="dots_checkbox" onclick="redraw_objects()"/>
		<label for="dots_checkbox">Dots</label>

		<input type="checkbox" id="polyline_checkbox" name="polyline_checkbox" checked onclick="redraw_objects()"/>
		<label for="polyline_checkbox">Polylines</label>

		<input type="checkbox" id="grid_checkbox" name="grid_checkbox" onclick="on_grid_checkbox_clicked()"/>
		<label for="grid_checkbox">Grid</label>

		<input type="checkbox" id="colors_checkbox" name="colors_checkbox" onclick="redraw_objects()"/>
		<label for="colors_checkbox">Colors</label>

		<input type="checkbox" id="arrows_checkbox" name="arrows_checkbox" checked onclick="redraw_objects()"/>
		<label for="arrows_checkbox">Arrows</label>

		<p id="p_zoom"/>
		<p id="p_dists"/>
  </body>
</html>
