<!DOCTYPE html>
<html>
  <head>
		<title>browse_snapgraph</title>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 70%; margin: 0; padding: 0 }
    </style>
		<link type="text/css" href="css/ui-lightness/jquery-ui-1.8.17.custom.css" rel="stylesheet" />
    <script type="text/javascript"
		      src="http://maps.googleapis.com/maps/api/js?sensor=false&v=3.14">
					    </script>
		<script type="text/javascript" src="js/richmarker-compiled.js"></script>
		<script type="text/javascript" src="js/jquery-1.7.1.min.js"></script>
		<script type="text/javascript" src="js/jquery-ui-1.8.17.custom.min.js"></script>
		<script type="text/javascript" src="js/buckets-minified.js"></script>
		<script type="text/javascript" src="common.js"></script>
		<script type="text/javascript" src="spatialindex.js"></script>
		<script type="text/javascript" src="js/infobox_packed.js"></script>
    <script type="text/javascript">

//var DEFAULT_SNAP_RADIUS = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
//	passthru('python -c "import c; print c.GRAPH_SNAP_RADIUS"'); ?>;
var DEFAULT_SNAP_RADIUS = 200;
var RADIUS_OF_EARTH_METERS = 6367.44465*1000;

var g_static_graph_objects = [];
var g_path_objects = [];
var g_path_markers = [];
var g_path_latlngs = null, g_visited_vertex_latlngs = null;
var g_multisnap_objects = [];
var g_found_polyline = null, g_found_vertex_map_objects = null, g_found_posaddr = null;

/** b/c if you doubleclick the map, both 'click' and 'dblclick' events will happen. 
Thanks to http://stackoverflow.com/questions/13859918/google-map-api-v3-how-to-prevent-mouse-click-event-for-a-marker-when-user-actu */
var g_map_doubleclicked = false;
var g_map_click_mouseevent = null;

var g_plines_spatialindex = null, g_plinepts_spatialindex = null, g_vertexes_spatialindex = null;

var g_nearby_plinepts = [], g_nearby_verts = [];
var g_shown_nearby_object = null;

function initialize() {

	init_map();

	set_value('snap_radius_textfield', DEFAULT_SNAP_RADIUS.toString());

	google.maps.event.addListenerOnce(g_map, 'bounds_changed', function() {
		g_map.setZoom(17);

		google.maps.event.addListener(g_map, 'click', function(mouseevent_) { 
				g_map_click_mouseevent = mouseevent_;
				g_map_doubleclicked = false;
				setTimeout(handle_map_single_or_doubleclick, 250);
			});
		google.maps.event.addListener(g_map, 'dblclick', function(mouseevent_) { 
			g_map_doubleclicked=true;
		});
		google.maps.event.addListener(g_map, 'rightclick', function(mouseevent_) { 
				add_path_marker(mouseevent_.latLng); 
				get_paths_from_server();
			});
		add_delayed_event_listener(g_map, 'bounds_changed', refresh_graph_visuals, 300);

		google.maps.event.addListener(g_map, 'zoom_changed', function() {
			draw_paths();
		});

		// Hack because around January 15 2013, Chrome sometimes stopped displaying the graph visuals until we jog the 
		// map a little, or alt-tab, or zoom, or something like that.   Oddly enough, it looks like changing the delay 
		// above from 500 to 300 fixes it too.  Well this fixes it again. 
		//setTimeout("g_map.panTo(new google.maps.LatLng(g_map.getCenter().lat(), g_map.getCenter().lng()+0.00001));", 1000);

		$('#plinename_field').keydown(function (e) {
			if(e.keyCode == 13) {
				$('#plinename_button').trigger('click');
			}
		});
		$('#vertname_field').keydown(function (e) {
			if(e.keyCode == 13) {
				$('#vertname_button').trigger('click');
			}
		});
		$('#vertidx_field').keydown(function (e) {
			if(e.keyCode == 13) {
				$('#vertidx_button').trigger('click');
			}
		});

		init_map_sync('map_sync_checkbox', true);

		init_path_markers();

		init_nearby_objects_dialog();
	});
}

function init_path_markers() {
	var bounds = g_map.getBounds();
	var toplat = bounds.getNorthEast().lat(), bottomlat = bounds.getSouthWest().lat();
	var middlelat = avg(toplat, bottomlat);
	var leftlng = bounds.getSouthWest().lng(), rightlng = bounds.getNorthEast().lng();
	var centerlng = g_map.getCenter().lng();
	var left_of_center_lng = avg(leftlng, centerlng), right_of_center_lng = avg(rightlng, centerlng);
	add_path_marker(new google.maps.LatLng(middlelat, left_of_center_lng));
	add_path_marker(new google.maps.LatLng(middlelat, right_of_center_lng));
}

function init_nearby_objects_dialog() {
	$("#nearby-objects-dialog").dialog({width: 500, height: 500, resizable: true, autoOpen: false, modal: true});
}

function handle_map_single_or_doubleclick() {
	if(g_map_doubleclicked) {
		handle_map_doubleclick(g_map_click_mouseevent.latLng);
	} else {
		handle_map_singleclick(g_map_click_mouseevent.latLng);
	}
}

function handle_map_doubleclick(latlng_) {
	snap(latlng_);
}

function handle_map_singleclick(latlng_) {
	show_nearby_objects_dialog(latlng_);
}

function get_nearby_object_search_radius_from_cur_zoom() {
	var zoom2radius = {12: 175, 13: 135, 14: 70, 15: 40, 16: 25, 17: 15, 18: 8, 19: 5, 20: 3};
	var zoomkey = g_map.getZoom();
	var sortedkeys = sorted_keys(zoom2radius);
	var minkey = sortedkeys[0], maxkey = sortedkeys[sortedkeys.length-1];
	if(zoomkey < minkey) {
		zoomkey = minkey;
	} else if(zoomkey > maxkey) {
		zoomkey = maxkey;
	}
	return zoom2radius[zoomkey];
}

function show_nearby_objects_dialog(latlng_) {
	var radius = get_nearby_object_search_radius_from_cur_zoom();
	var nearby_plinenames = get_nearby_plinenames(latlng_, radius);
	g_nearby_plinepts = get_nearby_plinepts(latlng_, radius);
	g_nearby_vertinfos = get_nearby_vertinfos(latlng_, radius);
	if(Math.max(nearby_plinenames.length, g_nearby_plinepts.length, g_nearby_verts.length) == 0) {
		forget_shown_nearby_object();
	} else if(nearby_plinenames.length + g_nearby_plinepts.length + g_nearby_verts.length == 1) {
		if(nearby_plinenames.length == 1) {
			on_nearby_pline_button_clicked(nearby_plinenames[0]);
		} else if(g_nearby_plinepts.length == 1) {
			on_nearby_plinept_button_clicked(g_nearby_plinepts[0]);
		} else {
			on_nearby_vertex_button_clicked(g_nearby_vertinfos[0]);
		}
	} else {
		var html = '';
		for(var i=0; i<g_nearby_vertinfos.length; i++) {
			var vertinfo = g_nearby_vertinfos[i];
			html += sprintf('<input type="button" onclick="on_nearby_vertex_button_clicked(%d)" value="vertex [%d] %s" /><br>', 
					i, vertinfo.idx, vertinfo.name);
		}
		html += '----<br>';
		for(var i=0; i<nearby_plinenames.length; i++) {
			var plinename = nearby_plinenames[i];
			html += sprintf('<input type="button" onclick="on_nearby_pline_button_clicked(\'%s\')" value="pline %s" /><br>', 
					plinename, plinename);
		}
		html += '----<br>';
		for(var i=0; i<g_nearby_plinepts.length; i++) {
			var plinept = g_nearby_plinepts[i];
			html += sprintf('<input type="button" onclick="on_nearby_plinept_button_clicked(%d)" value="%s" /><br>', 
					i, plinept.name);
		}
		$('#nearby-objects-dialog').html(html);
		$('#nearby-objects-dialog').dialog('open');
	}
}

function on_nearby_vertex_button_clicked(i_) {
	$("#nearby-objects-dialog").dialog('close');
	forget_shown_nearby_object();
	var vertinfo = g_nearby_vertinfos[i_];

	var vertpos = vertinfo.pos.google();
	var infowin_content = sprintf('Vertex [%d] - %s - (%.8f,%.8f)<br>', vertinfo.idx, vertinfo.name, vertpos.lat(), vertpos.lng());
	infowin_content += 'ptaddrs: ';
	vertinfo.ptaddrs.forEach(function(ptaddr) {
		infowin_content += sprintf('(%s, %d), ', ptaddr[0], ptaddr[1]);
	});
	infowin_content = infowin_content.substring(0, infowin_content.length-2) + '<br>';
	infowin_content += sprintf('Connected to %d verts: %s', 
			vertinfo.connectedvertnamesandidxes.length, toJsonString(vertinfo.connectedvertnamesandidxes));
	var mapheightlat = g_map.getBounds().getNorthEast().lat() - g_map.getBounds().getSouthWest().lat();
	var mapwidthlng = g_map.getBounds().getNorthEast().lng() - g_map.getBounds().getSouthWest().lng();
	var infowinpos = new google.maps.LatLng(vertpos.lat() + mapheightlat/8, vertpos.lng() + mapwidthlng/16);
	var infowin = new google.maps.InfoWindow({content: infowin_content, position: infowinpos, zIndex: 2});
	infowin.open(g_map);
	var color = 'rgb(75,75,75)';
	var infowin_to_vert_polyine = new google.maps.Polyline({map: g_map, path: [vertpos, infowinpos], 
			strokeOpacity: 0, zIndex: 3, strokeColor: color, 
			icons: [{icon: {path: 'M 0,-1 0,1', strokeWeight: 6, strokeOpacity: 0.6, scale: 2}, offset: '0', repeat: '14px'}]});
	var map_objects = [];
	map_objects.push(infowin_to_vert_polyine);

	function hide() {
		infowin.close();
		for(var i=0; i<map_objects.length; i++) {
			map_objects[i].setMap(null);
		}
	}

	vertinfo.connectedvertlatlngs.forEach(function(latlng) {
		map_objects.push(new google.maps.Circle({map: g_map, center: google_LatLng(latlng), radius: 30, 
				fillColor: color, fillOpacity: 0.6, strokeWeight: 0, zIndex: 3}));
		map_objects.push(new google.maps.Polyline({map: g_map, path: [google_LatLng(latlng), vertpos], 
				strokeColor: color, strokeWeight: 15, zIndex: 3, strokeOpacity: 0.6}));
	});

	for(var i=0; i<map_objects.length; i++) {
		google.maps.event.addListener(map_objects[i], 'click', hide);
	}

	google.maps.event.addListener(infowin, 'closeclick', hide);

	g_shown_nearby_object = {hide: hide};

}

function on_nearby_pline_button_clicked(plinename_) {
	$("#nearby-objects-dialog").dialog('close');
	forget_shown_nearby_object();
	var latlngs = g_plines_spatialindex.plinename2pts[plinename_];
	var gpolyline = make_highlighted_polyline(latlngs);

	var infobox_div = document.createElement("div");
	infobox_div.style.cssText = "border: 1px solid black; margin-top: 8px; background: white; padding: 5px";
	infobox_div.innerHTML = sprintf('<h2>%s</h2>', plinename_);
	var infobox = new InfoBox({content: infobox_div, 
		pixelOffset: new google.maps.Size(-90, 0), 
		closeBoxMargin: "10px 2px 2px 2px", 
		position: g_map.getCenter()});
	infobox.open(g_map);
	g_shown_nearby_object = {hide: function() {
			infobox.close();
			gpolyline.setMap(null);
		}
	};

	google.maps.event.addListener(gpolyline, 'click', function() {
			infobox.close();
		});
	google.maps.event.addListener(infobox, 'closeclick', function() {
			gpolyline.setMap(null);
		});
}

function on_nearby_plinept_button_clicked(i_) {
	$("#nearby-objects-dialog").dialog('close');
	forget_shown_nearby_object();
	var point = g_nearby_plinepts[i_];
	var infowin = new google.maps.InfoWindow({position: point.pos.google(),  
			content: sprintf('%s (%.6f,%.6f)', point.name, point.pos.lat, point.pos.lng)});
	infowin.open(g_map);
	g_shown_nearby_object = {hide: function() {
			infowin.close();
		}};
}

function forget_shown_nearby_object() {
	if(g_shown_nearby_object != null) {
		g_shown_nearby_object.hide();
		g_shown_nearby_object = null;
	}
}

function get_nearby_vertinfos(latlng_, radius_) {
	if(g_vertexes_spatialindex != null) {
		return g_vertexes_spatialindex.multisnap(latlng_, radius_);
	} else {
		return [];
	}
}

function get_nearby_plinepts(latlng_, radius_) {
	if(g_plinepts_spatialindex != null) {
		return g_plinepts_spatialindex.multisnap(latlng_, radius_).sort(function(a, b) {
				return pline_ish_name_sort(a.name, b.name);
			});
	} else {
		return [];
	}
}

function pline_ish_name_sort(a_, b_) {
	var r = 0;
	var aHasExclamation = a_.indexOf('!') != -1, bHasExclamation = b_.indexOf('!') != -1;
	if(aHasExclamation && !bHasExclamation) {
		r = 1;
	} else if(!aHasExclamation && bHasExclamation) {
		r = -1;
	} else {
		if(a_ < b_) {
			r = -1;
		} else if(a_ > b_) {
			r = 1;
		} else {
			r = 0;
		}
	}
	return r;
}

function get_nearby_plinenames(latlng_, radius_) {
	var r = new buckets.Set();
	if(g_plines_spatialindex != null) {
		var snap_results = g_plines_spatialindex.multisnap(latlng_, radius_);
		snap_results.forEach(function(snap_result) {
			var plinename = snap_result[1].plinename;
			r.add(plinename);
		});
	}
	return r.toArray().sort(pline_ish_name_sort);
}

function get_path_marker_icon_url(i_) {
	return sprintf('http://www.google.com/mapfiles/marker_grey%s.png', 
			String.fromCharCode('A'.charCodeAt(0) + i_));
}

function add_path_marker(latlng_) {
	var marker = new google.maps.Marker({map: g_map, position: latlng_, 
			icon: get_path_marker_icon_url(g_path_markers.length), draggable: true});
	google.maps.event.addListener(marker, 'click', clear_or_reget_path);
	google.maps.event.addListener(marker, 'dragend', get_paths_from_server);
	google.maps.event.addListener(marker, 'rightclick', function() {
			for(var i=0; i<g_path_markers.length; i++) {
				if(g_path_markers[i] == marker) {
					g_path_markers.splice(i, 1);
					marker.setMap(null);
					break;
				}
			}
			for(var i=0; i<g_path_markers.length; i++) {
				g_path_markers[i].setIcon(get_path_marker_icon_url(i))
			}
			get_paths_from_server();
		});
	g_path_markers.push(marker);
}

function clear_or_reget_path() {
	if(g_path_objects.length > 0) {
		forget_drawn_path_objects();
	} else {
		get_paths_from_server();
	}
}

function get_sgname() {
	return radio_val('sgname');
}

function snap(target_) {
	forget_multisnap_objects();
	set_contents('p_multisnap_info', 'Multisnap: ...');
	var snap_radius = get_snap_radius_from_gui();
	callpy('browse_snapgraph.multisnap', get_sgname(), target_, snap_radius, 
		{success: function(latlng_n_posaddrstrs__) {
			var infostr = sprintf('Multisnap: arg: geom.LatLng(%.8f,%.8f) <br>%d result(s):', 
					target_.lat(), target_.lng(), latlng_n_posaddrstrs__.length);
			latlng_n_posaddrstrs__.forEach(function(latlng_n_posaddrstr) {
				var latlng = latlng_n_posaddrstr[0], posaddrstr = latlng_n_posaddrstr[1];
				var marker = new google.maps.Marker({map: g_map, position: google_LatLng(latlng), zIndex: 1, draggable: false});
				g_multisnap_objects.push(marker);
				if(is_selected('multisnap_show_infowindows')) {
					var infowin = new google.maps.InfoWindow({content: posaddrstr, disableAutoPan: true});
					infowin.open(g_map, marker);
					g_multisnap_objects.push(infowin);
				}
				infostr += sprintf('<br>(%.8f,%.8f) %s', latlng[0], latlng[1], posaddrstr);
			});
			set_contents('p_multisnap_info', infostr);
			g_multisnap_objects.push(new google.maps.Marker({map: g_map, position: target_, draggable: false, 
					icon: 'http://labs.google.com/ridefinder/images/mm_20_red.png', clickable: false}));
			g_multisnap_objects.push(new google.maps.Circle({map: g_map, center: target_, 
					radius: snap_radius, fillOpacity: 0, zIndex: 1, clickable: false}));

			g_multisnap_objects.forEach(function(marker) {
				google.maps.event.addListener(marker, 'click', forget_multisnap_objects);
			});
		}
	});
}

function get_snap_radius_from_gui() {
	var rstr = get_value('snap_radius_textfield');
	return parseInt(rstr, 10);
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

function get_paths_from_server() {
	forget_path_objects_backing_data();
	forget_drawn_path_objects();
	if(!is_selected('path_checkbox')) {
		set_contents('p_marker_latlngs', 'Paths: disabled.');
	} else if(g_path_markers.length < 2) {
		set_contents('p_marker_latlngs', 'Paths: need at least two markers.');
	} else {
		set_path_text_display();
		var latlngs = g_path_markers.map(function(marker) { return marker.getPosition(); } );
		if(latlngs.length < 2) {
			console.log('Less than two markers.  Can\'t do path.');
		} else if(latlngs.length == 2) {
			callpy('browse_snapgraph.find_paths', get_sgname(), latlngs[0], latlngs[1], 
						get_snap_arg(), get_snap_radius_from_gui(), 
						get_pathkfactor_from_gui(), is_selected('show_visited_vertexes_checkbox'), 
					{success: function(r__) {
						g_path_latlngs = r__['path_latlngs'];
						show_path_text_and_controls();
						draw_paths();
						g_visited_vertex_latlngs = r__['visited_vertex_latlngs'];
						draw_visited_vertexes();
					} 
				});
		} else { // ==> > 2 
			if(get_pathkfactor_from_gui() > 1) {
				console.log('More than two markers exist AND more than one path requested.  Can only do one or the other.  Will do a single multipath for these markers.');
			}
			callpy('browse_snapgraph.find_multipath', get_sgname(), latlngs, 
					{success: function(path__) {
						g_path_latlngs = (path__ == null ? [] : [path__]);
						draw_paths();
					} 
				});
		}
	}
}

function get_snap_arg() {
	return radio_val('snap_style');
}

function show_path_text_and_controls() {
	var CHECKBOX_STYLE = 'style="width: 20px; height: 20px""';

	var contents = '';
	if(g_path_latlngs != null) {
		for(var i=0; i<g_path_latlngs.length; i++) {
			contents += sprintf(
				'<label><input type="checkbox" onclick="on_path_solo_checkbox_clicked(%d)" id="%s" %s/>[%d]&nbsp;&nbsp;&nbsp;</label>', 
					i, get_path_solo_checkbox_id(i), CHECKBOX_STYLE, i);
		}
	} else {
		contents = '...';
	}
	set_contents('p_path_controls', contents);
}

function on_path_solo_checkbox_clicked(pathidx_) {
	for(var pathidx=0; pathidx<g_path_latlngs.length; pathidx++) {
		if(pathidx != pathidx_) {
			set_selected(get_path_solo_checkbox_id(pathidx), false);
		}
	}
	forget_drawn_path_objects();
	draw_paths();
}

function get_path_solo_checkbox_id(pathidx_) {
	return sprintf('path_%d_solo_checkbox', pathidx_);
}
function draw_visited_vertexes() {
	if(g_visited_vertex_latlngs != null) {
		g_visited_vertex_latlngs.forEach(function(latlng) {
			var circle = new google.maps.Circle({map: g_map, center: google_LatLng(latlng), radius: 60, 
					fillOpacity: 0, strokeOpacity: 0.5, strokeWeight: 1.5, zIndex: 20});
			g_path_objects.push(circle);
		});
	}
}

function get_pathkfactor_from_gui() {
	var rstr = get_value('pathskarg_textfield');
	if(rstr == '') {
		return null;
	} else if(rstr.indexOf(',') != -1) {
		var splits = rstr.split(',');
		var intpart = parseInt(splits[0], 10), floatpart = parseFloat(splits[1], 10);
		if(isInt(floatpart)) {
			if(floatpart == 1.0) {
				floatpart += 0.00001;
			} else {
				floatpart -= 0.00001;
			}
		}
		return [intpart, floatpart];
	} else {
		// Passing an int or a float for this 'k' arg mean very different things.  
		// Javascript doesn't have different int and float types, but due to the encoding that 
		// happens via callpy / window.JSON.stringify(), an int in the GUI will show up on the server 
		// side as an int, and a float as a float. 
		var r = parseFloat(rstr, 10);
		if(r < 1.0) {
			throw "path k factor should be >= 1.0";
		}
		return r;
	}
}

function get_solo_pathidx_from_gui() {
	if(g_path_latlngs != null) {
		for(var i=0; i<g_path_latlngs.length; i++) {
			if(is_selected(get_path_solo_checkbox_id(i))) {
				return i;
			}
		}
	}
	return -1;
}

function draw_paths() {
	var solo_pathidx = get_solo_pathidx_from_gui();
	if(g_path_latlngs == null || g_path_latlngs.length == 0) {
		set_contents('p_marker_latlngs', get_contents('p_marker_latlngs')+' - <b>NO PATH POSSIBLE</b>');
	} else {
		for(var i=0; i<g_path_latlngs.length; i++) {
			if(solo_pathidx != -1 && solo_pathidx != i) {
				continue;
			}
			var path = g_path_latlngs[i];
			var path_latlngs = google_LatLngs(path);
			var greylevel = get_range_val(0, 100, g_path_latlngs.length, 220, i);
			var color = sprintf('rgb(%d,%d,%d)', greylevel, greylevel, greylevel);
			var path_pline = new google.maps.Polyline({map: g_map, path: path_latlngs, zIndex: 100-i, 
					strokeColor: color, strokeWeight: 6, clickable: false, strokeOpacity: 1, 
					icons: (is_selected('arrows_checkbox') ? make_polyline_arrow_icons(g_map.getZoom(), false, path_latlngs) : null)});
			g_path_objects.push(path_pline);
		}
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
	if(g_found_vertex_map_objects != null) {
		g_found_vertex_map_objects.forEach(function(e) {
			e.setMap(null);
		});
		g_found_vertex_map_objects = null;
	}
}

function refresh_graph_visuals() {
	if((get_sgname() == 'streets' && g_map.getZoom() < 16) || (get_sgname() == 'tracks' && g_map.getZoom() < 13)) {
		console.log('Zoom in more.');
		forget_static_graph_objects();
		return;
	}
	var map_sw = g_map.getBounds().getSouthWest(), map_ne = g_map.getBounds().getNorthEast();
	var box_sw=null, box_ne=null;
	if(dist_m(map_sw, map_ne) < 6000) {
		box_sw = get_range_val_latlng(0, map_ne, 1, map_sw, 1.5);
		box_ne = get_range_val_latlng(0, map_sw, 1, map_ne, 1.5);
	} else {
		box_sw = map_sw;
		box_ne = map_ne;
	}
	callpy('browse_snapgraph.get_infos_for_box', get_sgname(), box_sw, box_ne, 
		{success: function(r_) {
			forget_static_graph_objects();
			var plinename_to_pts = {};
			var plinename_to_ptidx_to_pt = r_['plinename_to_ptidx_to_pt'], vertname_to_info = r_['vertname_to_info'], 
					plinename_to_ptidx_to_hasvertex = r_['plinename_to_ptidx_to_hasvertex'];
			for(var plinename in plinename_to_ptidx_to_pt) {
				var ptidx_to_pt = plinename_to_ptidx_to_pt[plinename];
				make_pline(plinename, ptidx_to_pt, plinename_to_ptidx_to_hasvertex);
				plinename_to_pts[plinename] = values(ptidx_to_pt);
			}
			g_plines_spatialindex = new SpatialIndex(plinename_to_pts, 'plines');
			if(is_selected('show_points_and_vertexes_checkbox')) {
				var pt_points = [];
				for(var plinename in plinename_to_ptidx_to_pt) {
					var ptidx_to_pt = plinename_to_ptidx_to_pt[plinename];
					for(var ptidx in ptidx_to_pt) {
						var ptidx = parseInt(ptidx, 10);
						var pt = ptidx_to_pt[ptidx];
						pt_points.push({pos: pt, name: sprintf('pline %s pt %d', plinename, ptidx)}); 
					}
				}
				g_plinepts_spatialindex = new SpatialIndex(pt_points, 'points');

				var vert_points = [];
				for(var vertname in vertname_to_info) {
					var vertinfo = vertname_to_info[vertname];
					make_vert_circle(vertinfo);
					vert_points.push(vertinfo);
				}
				g_vertexes_spatialindex = new SpatialIndex(vert_points, 'points');
			}
			g_static_graph_objects.push(new google.maps.Rectangle({map: g_map, bounds: g_map.getBounds(), fillOpacity: 0, 
					clickable: false, strokeWeight: 0.5}));
		}, 
		error: function() {
			console.log('error');
		}}
		);
}

function make_vert_circle(vertinfo_) {
	//if(false) { // tdr 
	if(get_sgname() == 'system' && !vertinfo_.name.startsWith('(s)')) {
		return;
	}
	var vertpos = google_LatLng(vertinfo_.pos);
	var circle = new google.maps.Circle({map: g_map, center: vertpos, radius: 30, 
			fillOpacity: 0.4, strokeOpacity: 0, zIndex: 10});
	add_click_handler(circle);
	g_static_graph_objects.push(circle);
}

function add_click_handler(map_object_) {
	google.maps.event.addListener(map_object_, 'click', function(mouseevent__) { 
			handle_map_singleclick(mouseevent__.latLng);
		});
}

function make_pline(plinename_, ptidx_to_pt_, plinename_to_ptidx_to_hasvertex_) {
	var glatlngs = google_LatLngs(values(ptidx_to_pt_));
	var pline = new google.maps.Polyline({map: g_map, path: glatlngs, strokeColor: get_polyline_color(plinename_), 
			strokeWeight: 6, zIndex: 2, strokeOpacity: 0.6});
	add_click_handler(pline);
	g_static_graph_objects.push(pline);

	if(is_selected('show_points_and_vertexes_checkbox')) {
		for(var ptidx in ptidx_to_pt_) {
			var ptidx = parseInt(ptidx, 10);
			if(!plinename_to_ptidx_to_hasvertex_[plinename_][ptidx]) {
				var pt = ptidx_to_pt_[ptidx];
				make_pline_pt_circle(plinename_, ptidx, pt);
			}
		}
	}
}

function make_pline_pt_circle(plinename_, ptidx_, pt_) {
	var circle_pos = google_LatLng(pt_);
	var circle = new google.maps.Circle({map: g_map, center: circle_pos, radius: 10, 
			fillOpacity: 0.4, strokeOpacity: 0, zIndex: 9});
	add_click_handler(circle);
	g_static_graph_objects.push(circle);
}

function forget_static_graph_objects() {
	g_static_graph_objects.forEach(function(obj) {
		obj.setMap(null);
	});
	g_static_graph_objects = [];
	
	g_plines_spatialindex = null;
	g_plinepts_spatialindex = null;
	g_vertexes_spatialindex = null;
}

function forget_path_objects_backing_data() {
	g_path_latlngs = null;
	g_visited_vertex_latlngs = null;
}

function forget_drawn_path_objects() {
	g_path_objects.forEach(function(obj) {
		obj.setMap(null);
	});
	g_path_objects = [];
}

function get_polyline_color(plinename_) {
	var colors = [[255, 0, 0], [255, 0, 255], [0, 255, 255], [0, 127, 0], 
			[127, 0, 0], [127, 0, 127], [0, 127, 127, ], [0, 255, 0], [0, 0, 255]];
	var hashval = Math.abs(hashCode(plinename_));
	var base_color = colors[hashval % colors.length];
	var num_gradients = 11;
	var gradient_num = hashval % num_gradients;
	var percent_shift_to_white = (gradient_num/num_gradients)*0.75;
	var r = [avg(base_color[0], 255, percent_shift_to_white), 
					avg(base_color[1], 255, percent_shift_to_white), 
					avg(base_color[2], 255, percent_shift_to_white)];
	return sprintf('rgb(%d,%d,%d)', r[0], r[1], r[2]);
}

function find_pline(plinename_, pan_to_) {
	forget_found_polyline();
	callpy('browse_snapgraph.get_pline_latlngs', get_sgname(), plinename_, 
		{success: function(latlngs__) {
			if(latlngs__ === null) {
				alert('Polyline not found.');
			} else {
				g_found_polyline = make_highlighted_polyline(latlngs__);
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

function make_highlighted_polyline(latlngs_) {
	var glatlngs = google_LatLngs(latlngs_);
	if(glatlngs.length == 2 && glatlngs[0].equals(glatlngs[1])) {
		// google maps won't draw the polyline unless the points are slightly unequal. 
		glatlngs[0] = new google.maps.LatLng(glatlngs[0].lat()+0.00005, glatlngs[0].lng());
	}
	var r = new google.maps.Polyline({map: g_map, path: glatlngs, zIndex: 100, 
			strokeWeight: 100, strokeColor: 'rgb(150,150,150)', strokeOpacity: 0.6}); // max strokeWeight might be 32. 
	google.maps.event.addListener(r, 'click', function() {
			r.setMap(null);
		});
	return r;
}

function on_sgname_changed() {
	refresh_graph_visuals();
	forget_drawn_path_objects();
	forget_shown_nearby_object();
	forget_multisnap_objects();
	forget_found_polyline();
	forget_found_vertex();
}

function on_vertname_button_clicked() {
	forget_found_vertex();
	var vertname = get_value('vertname_field');
	get_vert_pos_from_server(vertname);
}

function on_vertidx_button_clicked() {
	forget_found_vertex();
	var vertidx = parseInt(get_value('vertidx_field'), 10);
	get_vert_pos_from_server(vertidx);
}

function get_vert_pos_from_server(vertname_or_idx_) {
	callpy('browse_snapgraph.get_vert_pos', get_sgname(), vertname_or_idx_, 
		{success: function(latlng__) {
			if(latlng__ === null) {
				alert('Vertex not found.');
			} else {
				var latlng = google_LatLng(latlng__);
				g_found_vertex_map_objects = [];
				[50, 100, 200].forEach(function(radius) {
					var circle = new google.maps.Circle({map: g_map, center: latlng, zIndex: 1, 
							radius: radius, fillColor: 'rgb(255,230,0)', fillOpacity: 0.3, strokeOpacity: 0});
					google.maps.event.addListener(circle, 'click', forget_found_vertex);
					g_found_vertex_map_objects.push(circle);
				});
				g_map.panTo(latlng);
			}
		}
	});
}

function forget_found_posaddr() {
	if(g_found_posaddr != null) {
		g_found_posaddr.setMap(null);
		g_found_posaddr = null;
	}
}

function on_posaddr_button_clicked() {
	forget_found_posaddr();
	var posaddr_str = get_value('posaddr_field');
	get_posaddr_latlng_from_server(posaddr_str);
}

function get_posaddr_latlng_from_server(posaddr_str_) {
	callpy('browse_snapgraph.get_posaddr_latlng', get_sgname(), posaddr_str_, 
		{success: function(latlng__) {
			if(latlng__ === null) {
				alert('PosAddr either not parsed or not found.');
			} else {
				var latlng = google_LatLng(latlng__);
				g_found_posaddr = new google.maps.Marker({map: g_map, position: latlng, zIndex: 2, 
						icon: 'http://maps.google.com/mapfiles/dir_60.png', draggable: false});
				google.maps.event.addListener(g_found_posaddr, 'click', forget_found_posaddr);
				g_map.panTo(latlng);
			}
		}, 
		error: function() {
			alert('PosAddr either not parsed or not found.');
		}
	});
}

    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<br>
		Find pline by name:<input type="text" size="10" name="plinename_field" id="plinename_field" value="790"/> <input type="button" id="plinename_button" onclick="find_pline(get_value('plinename_field'), true)" value="Ok" /> 
		| Find vert ... by name:<input type="text" size="10" name="vertname_field" id="vertname_field" value="0"/> <input type="button" id="vertname_button" onclick="on_vertname_button_clicked()" value="Ok" /> 
		... by idx:<input type="text" size="5" name="vertidx_field" id="vertidx_field" value="0"/> <input type="button" id="vertidx_button" onclick="on_vertidx_button_clicked()" value="Ok" /> 
		| Find PosAddr: <input type="text" size="40" id="posaddr_field" value="PosAddr('bathurst', 35, 0.436)"/> <input type="button" id="posaddr_button" onclick="on_posaddr_button_clicked()" value="Ok" />
		<br>
		Snap radius: <input id="snap_radius_textfield" size="5" /> | 
		<input id="streets_button" type="radio" name="sgname" value="streets" onclick="on_sgname_changed()"  />
		<label for="streets_button">streets</label>
		<input id="tracks_button" type="radio" name="sgname" value="tracks" onclick="on_sgname_changed()" />
		<label for="tracks_button">tracks</label>
		<input id="system_button" type="radio" name="sgname" value="system" onclick="on_sgname_changed()" checked />
		<label for="system_button">system</label> 
		<input id="testgraph_button" type="radio" name="sgname" value="testgraph" onclick="on_sgname_changed()" />
		<label for="system_button">testgraph</label> | 
		<input type="checkbox" id="show_points_and_vertexes_checkbox" checked="checked" onclick="refresh_graph_visuals()" />
		<label for="show_points_and_vertexes_checkbox">Show points and vertexes</label> 
		<br>
		<input type="checkbox" id="path_checkbox" checked onclick="get_paths_from_server()" />
		<label for="path_checkbox">Do path</label> |
		Yen k: <input id="pathskarg_textfield" name="value" size="5" value="10,2.0"/> |
		<label><input id="show_visited_vertexes_checkbox" type="checkbox" checked onclick="get_paths_from_server()"/>
				Show visited vertexes</label> 
		<label><input type="checkbox" id="arrows_checkbox" name="arrows_checkbox" checked onclick="get_paths_from_server()"/>
				Show arrows on path</label> 

		//// Snap style for paths: 
		<label><input type="radio" name="snap_style" value="1" onclick="get_paths_from_server()" />Single</label>
		<label><input type="radio" name="snap_style" value="m" onclick="get_paths_from_server()" checked />Multi</label>
		<label><input type="radio" name="snap_style" value="pcp" onclick="get_paths_from_server()" />PCP</label>

		<br>
		<input type="checkbox" id="multisnap_show_infowindows" />
		<label for="multisnap_show_infowindows">Multisnap: show infowindows</label> |
		<label><input id="map_sync_checkbox" type="checkbox"/>Map Sync</label> 

		<p id="p_error"/>
		<p id="p_path_controls">Path controls...</p>
		<p id="p_marker_latlngs">Path markers: ...</p>
		<p id="p_multisnap_info"/>
		<p id="p_loading_urls"/>
		<div id="nearby-objects-dialog"><div>
  </body>
</html>
