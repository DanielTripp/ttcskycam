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
    <script type="text/javascript">

var POLYLINE_STROKEWEIGHT = 2;

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

var g_grid_objects = new Array();

var LATREF = <?php 
  passthru('python -c "import snaptogrid; print snaptogrid.LATREF"'); ?>;
var LNGREF = <?php 
  passthru('python -c "import snaptogrid; print snaptogrid.LNGREF"'); ?>;
var LATSTEP = <?php 
  passthru('python -c "import snaptogrid; print snaptogrid.LATSTEP"'); ?>;
var LNGSTEP = <?php 
  passthru('python -c "import snaptogrid; print snaptogrid.LATSTEP"'); ?>;

function initialize() {

	init_map();

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

  $('#filename_field').keydown(function (e){
      if(e.keyCode == 13) {
				refresh_from_file();
      }
    });

	if(false) { 
		set_value('filename_field', 'simp2');
		refresh_from_file();
	}
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
		var line = new google.maps.Polyline({map: g_map, path: pts, strokeColor: 'rgb(0,0,255)', strokeWeight: (gridlat % 10 == 0 ? 1 : 0.5)});
		g_grid_objects.push(line);
		var marker = new RichMarker({
			position: new google.maps.LatLng(lat, g_map.getBounds().getNorthEast().lng()), 
			map: g_map,
			draggable: false,
			flat: true, 
			anchor: RichMarkerPosition.RIGHT, 
			content: sprintf('<svg width="20" height="20" version="1.1">' +
					'<text x="0" y="15" font-size="15" font-weight="bold"  fill="rgb(0,0,255)">       %d</text>' +
					'</svg>', 
					gridlat)
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
		var line = new google.maps.Polyline({map: g_map, path: pts, strokeColor: 'rgb(0,0,255)', strokeWeight: (gridlng % 10 == 0 ? 1 : 0.5)});
		g_grid_objects.push(line);
		var marker = new RichMarker({
			position: new google.maps.LatLng(g_map.getBounds().getNorthEast().lat(), lng), 
			anchor: RichMarkerPosition.TOP, 
			map: g_map,
			draggable: false,
			flat: true, 
			content: sprintf('<svg width="20" height="20" version="1.1">' +
					'<text x="0" y="15" font-size="15" font-weight="bold" fill="rgb(0,0,255)">%d</text>' +
					'</svg>', 
					gridlng)
			});
		g_grid_objects.push(marker);
	}
}

function erase_grid() {
	while(g_grid_objects.length > 0) {
		g_grid_objects.pop().setMap(null);
	}
}


function on_zoom_changed() {
	set_contents('p_zoom', sprintf('zoom: %d', g_map.getZoom()));
}

function refresh_from_file() {
	forget_drawn_objects();
	get_latlngs_from_file();
	draw_objects();
}

function get_latlngs_from_file() {
	g_polyline_latlngs = [];
	var contents_str = get_sync(get_value('filename_field'), {cache: false});
	if(contents_str != null) {
		var raw_polylines = [];
		try {
			raw_polylines = $.parseJSON(contents_str);
		} catch(e) {
			// So it wasn't JSON.    Maybe it's XML: 
			try {
				var polyline = [];
				raw_polylines.push(polyline);
				var dom = $.parseXML(contents_str);
				$(dom).find('*').each(function() {
					var lat = $(this).attr('lat'), lng = $(this).attr('lon');
					if(lat != undefined && lng != undefined) {
						polyline.push([lat, lng]);
					}
				});
			} catch(err) {
				var polyline = [];
				raw_polylines.push(polyline);
				var filelines = contents_str.split('\n');
				for(var filelinei in filelines) {
					var fileline = filelines[filelinei];
					var regex = /([-]?\d+\.\d+)[ ,]*([-]?\d+\.\d+)/g;
					var match = regex.exec(fileline);
					if(match != null) {
					  var lat = parseFloat(match[1], 10);
						var lng = parseFloat(match[2], 10);
						polylines.push([lat, lng]);
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
				make_marker(latlng, sprintf('%d/%d', lineidx, ptidx));
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
			strokeOpacity: 0.5, strokeWeight: 1, fillOpacity: 0, zIndex: -10});

	if(is_selected('polyline_checkbox')) {
		draw_polylines();
	}
}

function draw_polylines() {
	g_polyline_latlngs.forEach(function(polyline_latlngs) {
		g_polylines.push(new google.maps.Polyline({path: polyline_latlngs, strokeWeight: POLYLINE_STROKEWEIGHT, strokeOpacity: g_opacity, map: g_map}));
	});
}

function make_marker(latlng_, label_) {
	var marker = new google.maps.Marker({position: latlng_, map: g_map, 
			icon: {path: google.maps.SymbolPath.CIRCLE, scale: 14, strokeWeight : 0, fillOpacity: g_opacity, fillColor: 'black'}
		});
	g_markers.push(marker);
	add_marker_mouseover_listener_for_infowin(marker, label_);
	add_marker_click_listener_for_show_dist(marker);
}

function add_marker_mouseover_listener_for_infowin(marker_, label_) {
	var latlng = marker_.getPosition();
	var infowin = new google.maps.InfoWindow({position: latlng, disableAutoPan: true, 
			content: sprintf('%s - %.8f, %.8f', label_, latlng.lat(), latlng.lng())});
	google.maps.event.addListener(marker_, 'mouseover', function() {
		infowin.open(g_map);
	});
	google.maps.event.addListener(marker_, 'mouseout', function() {
		infowin.close();
	});
}

function add_marker_click_listener_for_show_dist(marker_) {
	google.maps.event.addListener(marker_, 'click', function() {
		if(g_show_dist_pt1 != null  && g_show_dist_pt2 != null) {
			reset_show_dist_everything();
		}

		if(g_show_dist_pt1 == null) {
			assert(g_show_dist_pt2 == null);
			g_show_dist_pt1 = marker_.getPosition();
		} else if(g_show_dist_pt2 == null) {
			g_show_dist_pt2 = marker_.getPosition();
			g_show_dist_infowindow = new google.maps.InfoWindow({position: g_show_dist_pt2, disableAutoPan: true, 
					content: sprintf('distance: %.2f meters', dist_m(g_show_dist_pt1, g_show_dist_pt2))});
			google.maps.event.addListener(g_show_dist_infowindow, 'closeclick', reset_show_dist_everything);
			g_show_dist_infowindow.open(g_map);

			g_show_dist_polyline = new google.maps.Polyline({path: [g_show_dist_pt1, g_show_dist_pt2], strokeWeight: 4, 
					strokeColor: 'red', map: g_map});
		}
	});
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





    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:80%; height:100%"></div>
		<input type="text" size="130" name="filename_field" id="filename_field" />
		<input type="button" onclick="on_opacity_down_clicked()" value="Opacity DOWN" />
		<input type="button" onclick="on_opacity_up_clicked()" value="Opacity UP" />
		<label for="dots_checkbox">Dots:</label><input checked="checked" type="checkbox" id="dots_checkbox" name="dots_checkbox" onclick="redraw_objects()"/>
		<label for="polyline_checkbox">Polylines:</label><input type="checkbox" id="polyline_checkbox" name="polyline_checkbox" onclick="redraw_objects()"/>
		<p id="p_zoom"/>
  </body>
</html>