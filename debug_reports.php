<!DOCTYPE html>
<html>
  <head>
		<title>debug_reports</title>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 70%; margin: 0; padding: 0 }
    </style>
		<script type="text/javascript" src="js/buckets-minified.js"></script>
		<link type="text/css" href="css/ui-lightness/jquery-ui-1.8.17.custom.css" rel="stylesheet" />
    <script type="text/javascript"
      src="http://maps.googleapis.com/maps/api/js?sensor=false&v=3.14">
    </script>
		<script type="text/javascript" src="js/jquery-1.7.1.min.js"></script>
		<script type="text/javascript" src="js/richmarker-compiled.js"></script>
		<script type="text/javascript" src="js/jquery-ui-1.8.17.custom.min.js"></script>
		<script type="text/javascript" src="common.js"></script>
		<script type="text/javascript" src="spatialindex.js"></script>
    <script type="text/javascript">

var g_pline = null;
var g_markers = new buckets.LinkedList();

var g_model = null;
var g_editing_viidx = -1;

function initialize() {
	init_map();

	bind_text_control_to_localstorage('raw_textarea');
	bind_text_control_to_localstorage('filename_textfield');

	init_edit_dialog();
	init_message_dialog();

	google.maps.event.addListenerOnce(g_map, 'bounds_changed', function() {
		google.maps.event.addListener(g_map, 'click', function(e) {
			g_model.vis.push({time_secs: 60.0, latlng: e.latLng});
			write_model_to_localstorage();
			redraw_pline();
			update_model_text_view();
		});

		// To redraw pline arrows with spacing appropriate to the current zoom: 
		google.maps.event.addListener(g_map, 'zoom_changed', function(e) {
			redraw_pline();
		});

		google.maps.event.addListener(g_map, 'rightclick', function(e) {
			array_insert(g_model.vis, 0, {time_secs: 0.0, latlng: e.latLng});
			g_model.vis[1].time_secs = 60.0;
			write_model_to_localstorage();
			redraw_pline();
			update_model_text_view();
		});

		init_map_sync('map_sync_checkbox', true);

		read_model_from_localstorage();
	});

}

function read_model_from_localstorage() {
	var json_str = localStorage.getItem(get_model_localstorage_key());
	set_model($.parseJSON(json_str));
}

function write_model_to_localstorage() {
	localStorage.setItem(get_model_localstorage_key(), get_model_as_json_str());
}

function get_model_localstorage_key() {
	return document.URL+' - model';
}

function init_edit_dialog() {
	$("#div_edit_dialog").dialog({resizable: true, autoOpen: false, modal: true,
		buttons: { 'Ok': function() { 
			var new_time_secs = parseFloat(get_value('edit_dialog_textfield'), 10);
			if(isNaN(new_time_secs)) {
				alert('parseFloat error');
			} else {
				g_model.vis[g_editing_viidx].time_secs = new_time_secs;
				write_model_to_localstorage();
				update_model_text_view();
				$(this).dialog('close'); 
			}
		}}
	});
}

function init_message_dialog() {
	$("#div_message_dialog").dialog({resizable: true, autoOpen: false, modal: true, width: 500});
}

function show_message_dialog(msg_) {
	$('#div_message_dialog').html(msg_);
	$('#div_message_dialog').dialog('open');
	setTimeout(function() { $('#div_message_dialog').dialog('close'); }, 1000);
}

function open_edit_dialog(viidx_) {
	set_contents('p_edit_dialog_desc', sprintf('[%d]', viidx_));
	set_value('edit_dialog_textfield', g_model.vis[viidx_].time_secs.toString());
	select_line('model_text_view_textarea', viidx_);
	scroll_to_line('model_text_view_textarea', viidx_);
	setTimeout(function() { 
		g_editing_viidx = viidx_;
		$('#div_edit_dialog').dialog('open'); 
	}, 500);
}

function remove_pline() {
	if(g_pline != null) {
		g_pline.setMap(null);
		g_pline = null;
	}
}

function draw_pline() {
	if(g_model == null) {
		return;
	}
	var path = [];
	for(var i=0; i<g_model.vis.length; i++) {
		path.push(g_model.vis[i].latlng);
	}
	g_pline = new google.maps.Polyline({clickable: true, editable: true, draggable: true, map: g_map, 
		path: path, strokeColor: 'rgb(255,0,0)', strokeWeight: 5, 
		icons: make_polyline_arrow_icons(g_map.getZoom(), false, path)
	});
	google.maps.event.addListener(g_pline, 'click', function(polymouseevent__) {
		if(polymouseevent__.vertex != undefined) {
			open_edit_dialog(polymouseevent__.vertex);
		} else if(polymouseevent__.edge == undefined) {
			var si = new SpatialIndex([g_pline.getPath().getArray()], 'plines');
			var snap_result = si.snap(polymouseevent__.latLng, 50);
			if(snap_result != null) {
				var startptidx = snap_result[1].startptidx;
				var lineseg_startpt = g_pline.getPath().getAt(startptidx);
				var snapped_pt = snap_result[0];
				var dist_ref_to_snap_pt = dist_m(snapped_pt, lineseg_startpt);
				var lineseg_endpt = g_pline.getPath().getAt(startptidx+1);
				var lineseg_len = dist_m(lineseg_startpt, lineseg_endpt);
				var ratio = dist_ref_to_snap_pt/lineseg_len;
				if(ratio > 0.005 && ratio < 0.995) {
					var old_endpt_time_secs = g_model.vis[startptidx+1].time_secs;
					var new_endpt_time_secs = roundByDigits(old_endpt_time_secs*(1.0 - ratio), 3);
					g_model.vis[startptidx+1].time_secs = new_endpt_time_secs;
					var new_vi_time_secs = roundByDigits(old_endpt_time_secs*ratio, 3);
					var new_vi = {time_secs: new_vi_time_secs, latlng: google_LatLng(snapped_pt)}
					array_insert(g_model.vis, startptidx+1, new_vi);
					write_model_to_localstorage();
					redraw_pline();
					update_model_text_view();
				}
			}
		}
	});
	google.maps.event.addListener(g_pline, 'rightclick', function(polymouseevent__) {
		if(polymouseevent__.vertex != undefined) {
			g_pline.getPath().removeAt(polymouseevent__.vertex); // triggers remove_at listener, below.
		}
	});
	google.maps.event.addListener(g_pline.getPath(), 'insert_at', function(idx__) {
		var new_latlng = g_pline.getPath().getAt(idx__);
		if(idx__ == 0) {
			g_model.vis[1].time_secs = 60.0;
			array_insert(g_model.vis, 0, {time_secs: 0.0, latlng: new_latlng});
		} else {
			var next_time_secs = g_model.vis[idx__].time_secs;
			g_model.vis[idx__].time_secs = roundByDigits(g_model.vis[idx__].time_secs/2.0, 3);
			array_insert(g_model.vis, idx__, {time_secs: roundByDigits(next_time_secs/2.0, 3), latlng: new_latlng});
		}
		write_model_to_localstorage();
		update_model_text_view();
	});
	google.maps.event.addListener(g_pline.getPath(), 'remove_at', function(idx__, value__) {
		if(idx__ > 0 && idx__ < g_model.vis.length-1) {
			var old_time_secs = g_model.vis[idx__].time_secs;
			g_model.vis[idx__+1].time_secs += old_time_secs;
		}
		array_remove(g_model.vis, idx__);
		write_model_to_localstorage();
		update_model_text_view();
	});
	google.maps.event.addListener(g_pline.getPath(), 'set_at', function(idx__, prev_value__) {
		var new_val = g_pline.getPath().getAt(idx__);
		g_model.vis[idx__].latlng = new_val;
		write_model_to_localstorage();
		update_model_text_view();
	});
}

function redraw_pline() {
	remove_pline();
	draw_pline();
}

function refresh_from_raw_textarea() {
	var textarea_contents = get_value('raw_textarea');
	callpy_post('debug_reports.get_model_from_raw_string', textarea_contents, 
		{success: function(r__) {
			show_message_dialog('Got parsed model from server OK.');
			set_model(r__);
		}});
}

function set_model(model_) {
	g_model = model_;
	var old_vis = g_model.vis;
	var new_vis = [];
	for(var i=0; i<old_vis.length; i++) {
		var e = old_vis[i];
		new_vis.push({time_secs: e.time_secs, latlng: google_LatLng(e.latlng)});
	}
	g_model.vis = new_vis;

	write_model_to_localstorage();
	redraw_pline();
	update_model_text_view();
}

function write_model_to_file() {
	callpy_post('debug_reports.write_to_file', get_value('filename_textfield'), get_model_as_json_str(), 
		{success: function(r__) {
			show_message_dialog('File written OK.');
		}});
}

function read_model_from_file() {
	callpy_post('debug_reports.read_from_file', get_value('filename_textfield'), 
		{success: function(r__) {
			show_message_dialog('File read OK.');
			set_model(r__);
		}});
}

function get_model_as_json_str() {
	var replacer = function(key__, value__) {
		if(value__ instanceof google.maps.LatLng) {
			return [value__.lat(), value__.lng()];
		} else {
			return value__;
		}
	}
	return window.JSON.stringify(g_model, replacer, '\t');
}

function update_model_text_view() {
	update_model_text_view_desc();
	update_model_text_view_textarea();
}

function update_model_text_view_textarea() {
	var contents = '';
	for(var i=0; i<g_model.vis.length; i++) {
		var vi = g_model.vis[i];
		contents += sprintf('[%d] %.3f - (%.7f,%.7f)\n', 
				i, vi.time_secs, vi.latlng.lat(), vi.latlng.lng());
	}
	set_contents('model_text_view_textarea', contents);
}

function update_model_text_view_desc() {
	if(g_model.vis.length == 0) {
		set_contents('div_model_text_view_desc', '0 vis');
	} else {
		var time_span_secs = 0.0;
		for(var i=1; i<g_model.vis.length; i++) {
			var vi = g_model.vis[i];
			time_span_secs += vi.time_secs;
		}
		var start_time_secs = g_model.vis[0].time_secs;
		var end_time_secs = start_time_secs + time_span_secs;
		set_contents('div_model_text_view_desc', sprintf('%d vis, %s, %s, %s to %s', 
				g_model.vis.length, g_model.fudgeroute, g_model.vehicle_type, 
				get_minutes_fraction_html(start_time_secs), get_minutes_fraction_html(end_time_secs)));
	}
}

function get_minutes_fraction_html(secs_) {
	var mins = Math.floor(secs_/60.0);
	var secs = secs_ - mins*60;
	return sprintf('%d<sup>%d</sup>&frasl;<sub>60</sub>', mins, secs);
}

function write_model_to_db() {
	callpy('debug_reports.restart_memcache_and_wsgi', 
		{success: function(r__) {
			callpy_post('debug_reports.write_to_db', get_model_as_json_str(), 
				{success: function(r__) {
					show_message_dialog('Wrote to database OK.');
				}});
		}});
}


    </script>
  </head>
  <body onload="initialize()">
		<div id="map_canvas" style="width:80%; height:90%"></div>
    <div id="div_model_text_view" style="position:absolute; top:0; right:0; width:20%; height:90%;">
			<!--
			<textarea id="model_text_view_textarea" rows="20" style="font-family: Arial; width: 100%; -webkit-box-sizing: border-box; -moz-box-sizing: border-box; box-sizing: border-box;"></textarea>
			-->
			<div id="div_model_text_view_desc"></div>
			<textarea id="model_text_view_textarea" readonly rows="22" style="
				/* Thanks to http://stackoverflow.com/questions/3165083/how-to-make-textarea-to-fill-div-block */
				font-family: Times; font-size: 11pt; width: 100%; padding: 5px; 
				-webkit-box-sizing: border-box; /* Safari/Chrome, other WebKit */
				-moz-box-sizing: border-box;    /* Firefox, other Gecko */
				box-sizing: border-box;         /* IE 8+ */
			"></textarea>
    </div>
		<div id="div_loading_img" style="position: absolute; background-color: transparent; top: 0px; left: 0px; z-index: 99;">
			<img id="loading_img" src="loading_small.gif" style="visibility:hidden"/>
		</div>
		Filename: <input type="text" size="50" id="filename_textfield" value="" />
		<input type="button" onclick="write_model_to_file()" value="Write To File" />
		<input type="button" onclick="read_model_from_file()" value="Read From File" />
		///
		<input type="button" onclick="write_model_to_db()" value="Write To Database" />
		///
		<label><input id="map_sync_checkbox" type="checkbox"/>Map Sync</label><br>
		<br>
		<textarea id="raw_textarea" cols="135" rows="10" wrap="off"></textarea>
		<input type="button" onclick="refresh_from_raw_textarea()" value="Parse" />
		<div id="div_edit_dialog"><p id="p_edit_dialog_desc"></p><input type="text" size="15" id="edit_dialog_textfield"/></div>
		<div id="div_message_dialog"></div>
  </body>
</html>
