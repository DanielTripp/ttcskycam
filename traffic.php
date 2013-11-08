<!DOCTYPE html>
<html>
  <head>
		<title>The Unofficial TTC Traffic Report</title>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 70%; margin: 0; padding: 0 }
    </style>
		<link type="text/css" href="css/ui-lightness/jquery-ui-1.8.17.custom.css" rel="stylesheet" />
    <script type="text/javascript"
      src="http://maps.googleapis.com/maps/api/js?sensor=true&v=3.13">
			<!-- ^^ using v3 stable b/c at one point the unstable release had our infowindows apearing too small, 
			and with a vertical scroll bar.  Same as http://stackoverflow.com/questions/18271220/google-maps-info-window-is-smaller-since-last-night 
			Hope that this issue goes away and that I can then go to a newer google maps version ('visual refresh' version I guess). --> 
    </script>
		<script type="text/javascript" src="js/jquery-1.7.1.min.js"></script>
		<script type="text/javascript" src="js/infobox_packed.js"></script>
		<script type="text/javascript" src="js/richmarker-compiled.js"></script>
		<script type="text/javascript" src="js/jquery-ui-1.8.17.custom.min.js"></script>
		<script type="text/javascript" src="js/jquery-ui-timepicker-addon.js"></script>
		<script type="text/javascript" src="js/buckets-minified.js"></script>
		<script type="text/javascript" src="common.js"></script>
		<script type="text/javascript" src="snaptogrid.js"></script>
    <script type="text/javascript">

var DONT_SHOW_INSTRUCTIONS = false;
var TEST_INVISIBLE = false;
var DISABLE_OVERTIME = false;
var SHOW_FRAMERATE = false;

var SHOW_DEV_CONTROLS = false;
var SHOW_HISTORICAL_ON_LOAD = false;
var HISTORICAL_TIME_DEFAULT = '2013-02-17 12:35';
var SHOW_ZOOM = false;

var SHOW_PATHS_TEXT = false;
var SHOW_PATH_GRID_SQUARES = false;
var SHOW_LOADING_URLS = false;
var DISABLE_GEOLOCATION = true;

var HARDCODE_DISPLAY_SET = false;
var HARDCODED_DISPLAY_SET = [['dundas', 0]];

init_dev_option_values();

// Thanks to http://stackoverflow.com/questions/654112/how-do-you-detect-support-for-vml-or-svg-in-a-browser 
var BROWSER_SUPPORTS_SVG = document.implementation.hasFeature("http://www.w3.org/TR/SVG11/feature#BasicStructure", "1.1"); 

init_javascript_array_functions_old_browser_fallbacks();

function new_fudgeroute_data() {
	return {
		// The key sets of datazoom_to_traffic_mofr2speed and datazoom_to_traffic_linedefs are supposed to always be the same. 
		datazoom_to_traffic_mofr2speed: new buckets.Dictionary(), 
		datazoom_to_traffic_linedefs: new buckets.Dictionary(), 
		traffic_lines: new buckets.LinkedList(),  // if this is a subway, these aren't really traffic lines - rather, plain old route lines. 
		traffic_datazoom: -1, // -1 implies no such data has been received yet and hence rendering is impossible.  Once it's non-zero, 
				// will never be zero again. 

		datazoom_to_time_to_vid_to_vi: new buckets.Dictionary(), // key: date/time string.  value: dictionary (key: vid string, value: VehicleInfo object) 
		vid_to_static_vehicle_marker: new buckets.Dictionary(), 
		vid_to_heading_to_moving_vehicle_marker: new buckets.Dictionary(), 
		vehicles_datazoom: -1, // Works the same as traffic_datazoom above.

		dir: null, // will be 0 or 1 or a pair a latlngs (orig and dest).   latlngs will be in a plain format: [float, float] array. 
		traffic_request_pending: false, 
		vehicles_request_pending: false,
		streetlabel_markers: new buckets.LinkedList(),
		traffic_last_returned_timestr: null, 
		locations_last_returned_timestr: null
	};
}

var g_show_static_vehicles = true, g_show_moving_vehicles = true, g_show_traffic_lines = true;

// End of this list = highest zindex i.e. most visible.  
var g_froute_zindexes = ['ossington', 'lansdowne', 'spadina', 'bathurst', 'dufferin', 'dupont', 'carlton', 'dundas', 'king', 'queen'];

 // complete list of all froutes, whether they are shown or not.  
// This will be filled in later (but soon, on page load), then after that will remain unchanged.  
var g_all_froutes = [];

var g_subway_froutes = to_buckets_set(['bloor_danforth', 'yonge_university_spadina']);

var g_framerate_period_times = new buckets.LinkedList();
for(var i=0; i<15; i++) {
	g_framerate_period_times.add(0);
}
var g_framerate_last_epochtime = (new Date()).getTime();

var LOG = false;

var g_fudgeroute_data = new buckets.Dictionary();
var g_play_timer = null;
/* current time location (index into g_times) of the animation. */
var g_cur_minute_idx = 0;
/* Contains date/time strings.  Each element is a minute. */
var g_times = new buckets.LinkedList();
var g_refresh_data_from_server_timer = null;
var g_hidden_vids = new buckets.Set();
var g_playing = true;

var g_mouseover_infowin = null;
var g_mouseover_infowin_timer = null;

var g_browser_is_desktop = <?php
function is_desktop($user_agent_) {
  $mobile_regex = '/iphone|ipod|blackberry|android|palm|windows\s+ce/i';
  $desktop_regex = '/windows|linux|os\s+[x9]|solaris|bsd/i';
  return (preg_match($mobile_regex, $user_agent_) == 0) && (preg_match($desktop_regex, $user_agent_) == 1);
}
echo (is_desktop(getenv('HTTP_USER_AGENT')) ? 'true' : 'false');
?>;

var g_num_extra_routes_to_show = (g_browser_is_desktop ? 3 : 0);
var g_trip_orig_marker = null, g_trip_dest_marker = null;
var g_num_trip_marker_moves_so_far = 0;
var g_instructions_orig_infowin = null, g_instructions_dest_infowin = null, g_instructions_also_infobox = null;
var g_route_options_dialog_froute = null;
var g_force_show_froutes = new buckets.Set(), g_force_hide_froutes = new buckets.Set();
var g_force_dir0_froutes = new buckets.Set(), g_force_dir1_froutes = new buckets.Set();
var g_main_path = [], g_extra_path_froutendirs = [];
var g_use_rendered_aot_arrow_vehicle_icons = g_browser_is_desktop;
var g_froute_to_snaptogridcache = null;

var HEADING_ROUNDING_DEGREES = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	readfile('HEADING_ROUNDING'); ?>;
var MIN_GUIZOOM = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	readfile('MIN_GUIZOOM'); ?>;
var MAX_GUIZOOM = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	readfile('MAX_GUIZOOM'); ?>;
var MIN_DATAZOOM = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	passthru('python -c "import c; print c.MIN_DATAZOOM"'); ?>;
var MAX_DATAZOOM = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	passthru('python -c "import c; print c.MAX_DATAZOOM"'); ?>;
var REFRESH_INTERVAL_MS = 10*1000;
var MOVING_VEHICLES_OVERTIME_FLASH_INTERVAL_MS = 500;
var MOVING_VEHICLES_ANIM_INTERVAL_MS = 100;
var FROUTE_TO_INTDIR_TO_ENGLISHDESC = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	passthru('python -c "import routes; print routes.get_fudgeroute_to_intdir_to_englishdesc()"'); ?>;
var FROUTE_TO_ENGLISH = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	passthru('python -c "import routes; print routes.get_froute_to_english()"'); ?>;
// Arrived at by visual trial and error.  Not very accurate.  Specific to Toronto. 
var GUIZOOM_TO_METERSPERPIXEL = {10: 102.4, 11: 51.2, 12: 25.6, 13: 12.8, 14: 6.4, 15: 3.2, 16: 1.6, 17: 0.8, 18: 0.4, 19: 0.2};
var MAX_RSDT = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	passthru('python -c "import c; print max(c.DATAZOOM_TO_RSDT.values())"'); ?>;
var SUBWAY_FROUTE_TO_DATAZOOM_TO_ROUTEPTS = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	passthru('python -c "import routes; print routes.get_subway_froute_to_datazoom_to_routepts()"'); ?>;
var GUIZOOM_TO_DATAZOOM = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	passthru('python -c "import c; print c.GUIZOOM_TO_DATAZOOM"'); ?>;

var g_guizoom_to_vehicle_rendered_img_size = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	readfile('zoom_to_vehicle_rendered_img_size.json'); ?>;
var g_guizoom_to_vehicle_arrow_img_size = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
	readfile('zoom_to_vehicle_arrow_img_size.json'); ?>;
var g_guizoom_to_traffic_line_width = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 7, 8, 8, 10, 13, 16, 22, 42, 42];

function init_dev_option_values() {
	<?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	if(file_exists('dev-options-for-traffic-php.txt')) {
		foreach(explode("\n", file_get_contents('dev-options-for-traffic-php.txt')) as $line) {
			if($line != "") {
				$line_splits = preg_split("/[\s]+/", $line, 2);
				$varname = $line_splits[0];
				echo $varname, ";\n"; // This is to make sure that the variable name in the .txt file has already been declared in 
					// this html files.  A line of javascript of the form "VARNAME;" will do nothing, but it will cause an show-stopping 
					// error in the javascript interpreter (a ReferenceError I believe) if that variable hasn't been defined already.  
					// We want only variables that have already been defined in this php file to be defined in the .txt, so this 
					// is how we do it. 
				echo $line, "\n"; // <-- This is the more important part - setting the overridden value. 
			}
		}
	}
	?>
}

<?php echo "\n"; /* fudging number of lines so that line numbers are the same pre- and post-PHP. */ ?>  

function get_vehicle_size_by_guizoom(guizoom_) {
	var arr = (g_use_rendered_aot_arrow_vehicle_icons ? g_guizoom_to_vehicle_rendered_img_size : g_guizoom_to_vehicle_arrow_img_size);
	if(0 <= guizoom_ && guizoom_ < arr.length) {
		return arr[guizoom_];
	} else {
		return arr[arr.length-1];
	}
}

function get_vehicle_size() {
	return get_vehicle_size_by_guizoom(g_map.getZoom());
}

function kmph_to_color(kmph_) {
	var r = kmph_to_color_ints(kmph_);
	return sprintf('rgb(%d,%d,%d)', r[0], r[1], r[2]);
}

function kmph_to_color_ints(kmph_) {
	if(kmph_==null) {
		return [255, 255, 255];
	}
	var red = [150, 0, 0], yellow = [250, 250, 0], green = [0, 255, 0];
	var red_kmph = 5, yellow_kmph = 15, green_kmph = 25;
	if(kmph_ <= red_kmph) {
		return [0, 0, 0];
	} else if(red_kmph < kmph_ && kmph_ <= yellow_kmph) {
		return interp_color(red, yellow, (kmph_ - red_kmph)/(yellow_kmph - red_kmph));
	} else if(yellow_kmph < kmph_ && kmph_ <= green_kmph) {
		return interp_color(yellow, green, (kmph_ - yellow_kmph)/(green_kmph - yellow_kmph));
	} else {
		return green;
	}
}

function interp_color(c1_, c2_, percent_) {
	var r = [0, 0, 0];
	r.forEach(function(e, i) {
		r[i] = get_range_val(0, c1_[i], 1.0, c2_[i], percent_);
	});
	return r;
}

// note [1]: This is dealing with three facts: 
// - We get these linedefs from the server in increasing mofr order, starting from 0.  
// - We draw them all with the same zIndex, so the last one drawn is displayed on top.  
// - Google Maps Polylines, at considerable thicknesses (which our traffic lines usually are), are drawn with rounded 
// (circular) ends.  
// So straightforwardly drawing these linedefs will result in the rounded polyline ends pointing their convex sides towards 
// mofr == 0, whether the direction we're displaying is 0 or 1.  I think that these rounded ends don't look very good anyway, 
// but they look even worse when the convex ends are pointing in the opposite direction that the vehicle location markers are 
// moving.  I think that the direction that the convex ends are pointing tends to suggest to the typical person the direction 
// of travel.  So here I am ensuring that the convex ends are pointing that way.  
function refresh_traffic_from_server(fudgeroute_) {
	var data = g_fudgeroute_data.get(fudgeroute_);
	var dir_to_request = data.dir;
	var datazoom = GUIZOOM_TO_DATAZOOM[g_map.getZoom()];
	if(!data.traffic_request_pending) {
		data.traffic_request_pending = true;
		callpy('reports.get_traffic_report', fudgeroute_, dir_to_request, datazoom, get_datetime_from_gui(), 
				(data.datazoom_to_traffic_mofr2speed.containsKey(datazoom) ? data.traffic_last_returned_timestr : null), 
			{success: function(r_) {
				var data = g_fudgeroute_data.get(fudgeroute_);
				if(data == undefined || !dir_equals(data.dir, dir_to_request)) {
					return;
				}
				data.traffic_request_pending = false;
				var returned_timestr = r_[0];
				if((returned_timestr == data.traffic_last_returned_timestr) && data.datazoom_to_traffic_mofr2speed.containsKey(datazoom)) {
					return;
				}
				var time_was_updated = (returned_timestr != data.traffic_last_returned_timestr);
				if(time_was_updated) {
					data.datazoom_to_traffic_mofr2speed.clear();
					data.datazoom_to_traffic_linedefs.clear();
					data.traffic_last_returned_timestr = returned_timestr;
					assert(r_[1] != null, "traffic data is null even though timestamp has been updated.");
				}
				var dir_returned = r_[2];
				data.datazoom_to_traffic_linedefs.set(datazoom, to_buckets_list(r_[1][0], (dir_returned==0))); // see note [1] above. 
				data.datazoom_to_traffic_mofr2speed.set(datazoom, to_buckets_dict(r_[1][1]));
				if(update_traffic_datazoom(fudgeroute_) || time_was_updated) {
					remake_traffic_lines_singleroute(fudgeroute_); 
				}
			}, 
			error: function() {
				var data = g_fudgeroute_data.get(fudgeroute_);
				if(data == undefined || !dir_equals(data.dir, dir_to_request)) {
					return;
				}
				data.traffic_request_pending = false;
			}}
		);
	}
}

// Both arguments can be 0, 1, or a pair of latlngs (i.e. orig and dest).  Here we are simple. 
function dir_equals(dir1_, dir2_) {
	if(dir1_ == 0 || dir1_ == 1) {
		return (dir1_ == dir2_);
	} else if(dir2_ == 0 || dir2_ == 1) {
		return false;
	} else {
		assert(dir1_.length == 2 && dir2_.length == 2);
		assert(dir1_[0].length == 2 && dir1_[1].length == 2);
		assert(dir2_[0].length == 2 && dir2_[1].length == 2);
		return (dir1_[0][0] == dir2_[0][0] && dir1_[0][1] == dir2_[0][1] && dir1_[1][0] == dir2_[1][0] && dir1_[1][1] == dir2_[1][1]);
	}
}

function update_traffic_datazoom(froute_) {
	return update_datazoom(froute_, true);
}

function update_vehicles_datazoom(froute_) {
	return update_datazoom(froute_, false);
}

// true iff the datazoom field for the route in question was updated.
function update_datazoom(froute_, traffic_aot_vehicles_) {
	var data = g_fudgeroute_data.get(froute_);
	var old_datazoom = (traffic_aot_vehicles_ ? data.traffic_datazoom : data.vehicles_datazoom);
	var datazooms_map = (traffic_aot_vehicles_ ? data.datazoom_to_traffic_mofr2speed : data.datazoom_to_time_to_vid_to_vi);
	var guis_datazoom = GUIZOOM_TO_DATAZOOM[g_map.getZoom()], new_datazoom = old_datazoom;
	if(datazooms_map.containsKey(guis_datazoom)) {
		new_datazoom = guis_datazoom;
	} else {
		for(var offset=0; offset<MAX_DATAZOOM-MIN_DATAZOOM; offset++) {
			if(datazooms_map.containsKey(guis_datazoom-offset)) {
				new_datazoom = guis_datazoom-offset;
				break;
			}
			if(datazooms_map.containsKey(guis_datazoom+offset)) {
				new_datazoom = guis_datazoom+offset;
				break;
			}
		}
	}
	if(traffic_aot_vehicles_) {
		data.traffic_datazoom = new_datazoom;
	} else {
		data.vehicles_datazoom = new_datazoom;
	}
	return (new_datazoom != old_datazoom);
}

// note 237896: We need to remake static vehicles for _all_ routes here b/c we may have just 
// updated g_times like so: eg. 12:30 used to be the last time visible for this route (route X), but now 12:31 is, 
// (i.e. we had data up to 12:31 for route Y all along, but route X had only up to 12:30 -- until this present call returned.) 
// So starting now, without us doing anything, the animation is going to go to 12:31 with the moving vehicles, because all 
// of those markers exist already.  But for static vehicles, here we need to make sure that they are in compliance. 
function refresh_vehicles_from_server(fudgeroute_) {
	var data = g_fudgeroute_data.get(fudgeroute_);
	var dir_to_request = data.dir;
	var datazoom = GUIZOOM_TO_DATAZOOM[g_map.getZoom()];
	if(!data.vehicles_request_pending) {
		data.vehicles_request_pending = true;
		callpy('reports.get_locations_report', fudgeroute_, dir_to_request, datazoom, get_datetime_from_gui(), 
				(data.datazoom_to_time_to_vid_to_vi.containsKey(datazoom) ? data.locations_last_returned_timestr : null), 
			{success: function(r_) {
				var data = g_fudgeroute_data.get(fudgeroute_);
				if(data == undefined || !dir_equals(data.dir, dir_to_request)) {
					return;
				}
				data.vehicles_request_pending = false;
				var returned_timestr = r_[0];
				var time_was_updated = (returned_timestr != data.locations_last_returned_timestr);
				if(!time_was_updated && data.datazoom_to_time_to_vid_to_vi.containsKey(datazoom)) {
					return;
				}
				if(time_was_updated) {
					data.datazoom_to_time_to_vid_to_vi.clear();
					data.locations_last_returned_timestr = returned_timestr;
					assert(r_[1] != null, "locations data is null even though timestamp has been updated.");
				}
				appropriate_vehicle_locations(fudgeroute_, datazoom, r_[1]);
				var datazoom_was_updated = update_vehicles_datazoom(fudgeroute_);
				if(time_was_updated) {
					update_g_times(); 
				}
				if(time_was_updated || datazoom_was_updated) {
					remake_static_vehicles_allroutes();  // see note 237896.
					remake_moving_vehicles_singleroute(fudgeroute_);
				}
				if(time_was_updated) {
					refresh_vid_checkboxes_html();
					if(g_cur_minute_idx >= g_times.size()) { // want to keep animation going smoothly if possible - but if for some reason 
							// (what reason I don't know) the server returned fewer timeslices on this refresh and thus g_times shrunk, 
							// then here we handle that.  Not worth it to fuss about overtime here. 
						g_cur_minute_idx = 0;
					}
					update_clock_show_cur_minute();
				}
				if(time_was_updated || datazoom_was_updated) {
					show_cur_minute_vehicles_singleroute(fudgeroute_);
					// This will deal with hidden VIDs: 
					all_froutes().forEach(function(froute) {
						set_all_static_vehicle_markers_visible_singleroute(froute, g_show_static_vehicles);
					});
				}
			}, 
			error: function() {
				var data = g_fudgeroute_data.get(fudgeroute_);
				if(data == undefined || !dir_equals(data.dir, dir_to_request)) {
					return;
				}
				data.vehicles_request_pending = false;
			}}
		);
	}
}

function all_froutes() {
	return g_fudgeroute_data.keys();
}

function refresh_vid_checkboxes_html() {
	if(!SHOW_DEV_CONTROLS) {
		return;
	}
	var html = 'Showing vehicle IDs:<br>';
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		html += fudgeroute+': ';
		var vids = buckets_set_to_list(all_vids_singleroute(fudgeroute));
		sort_buckets_list(vids);
		vids.forEach(function(vid) {
			html += sprintf('%s <span onclick="%s" ondblclick="set_solo_vid(%s)">%s</span>&nbsp;&nbsp;', 
				make_vid_checkbox_html(fudgeroute, vid), 
				"$('#"+vid_checkbox_id(fudgeroute, vid)+"').trigger('click')", 
				vid, vid);
		});
		html += '<br>';
	});
	set_contents('p_vid_checkboxes', html);
}

function make_vid_checkbox_html(fudgeroute_, vid_) {
	return sprintf('<input type="checkbox" id="'+vid_checkbox_id(fudgeroute_, vid_)+'" onclick="on_vid_checkbox_clicked(\''+vid_+'\')" %s/>', 
			(g_hidden_vids.contains(vid_) ? '' : 'checked="checked"'));
}

function vid_checkbox_id(fudgeroute_, vid_) {
	return 'vid-checkbox-'+fudgeroute_+'-'+vid_;
}

function on_vid_checkbox_clicked(vid_) {
	if(g_hidden_vids.contains(vid_)) {
		g_hidden_vids.remove(vid_);
	} else {
		g_hidden_vids.add(vid_);
	}

	refresh_vid_checkboxes_selectedness();

	show_cur_minute_vehicles_allroutes();
}

function refresh_vid_checkboxes_selectedness() {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		var vids = all_vids_singleroute(fudgeroute);
		vids.forEach(function(vid) {
			var checkbox_domid = vid_checkbox_id(fudgeroute, vid);
			set_selected(checkbox_domid, !g_hidden_vids.contains(vid));
		});
	});
}

function all_vids_allroutes() {
	var r = new buckets.Set();
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		add_all(r, all_vids_singleroute(fudgeroute));
	});
	return r;
}

function all_vids_singleroute(fudgeroute_) {
	var r = new buckets.Set();
	var data = g_fudgeroute_data.get(fudgeroute_);
	if(data.datazoom_to_time_to_vid_to_vi.containsKey(data.vehicles_datazoom)) {
		data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom).forEach(function(time, vid_to_vi) {
			vid_to_vi.forEach(function(vid, vi) {
				r.add(vid);
			});
		});
	} // else: that'll happen if it's a subway or if the route was just added to our list and we don't have any vehicle data for it yet. 
	return r;
}

function appropriate_vehicle_locations(fudgeroute_, datazoom_, raw_) {
	var data = g_fudgeroute_data.get(fudgeroute_);
	data.datazoom_to_time_to_vid_to_vi.set(datazoom_, new buckets.Dictionary()); // will discard old data for this datazoom, if there is any. 
	var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(datazoom_);
	time_to_vid_to_vi.clear();
	raw_.forEach(function(timeslice) {
		var timestr = timeslice.shift();
		var vid_to_vi = new buckets.Dictionary();
		time_to_vid_to_vi.set(timestr, vid_to_vi);
		timeslice.forEach(function(vi) {
			vid_to_vi.set(vi.vehicle_id, vi);
		});
	});
}

// make g_times the intersection of all times present in all routes. 
function update_g_times() {
	var new_times_set = null;
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom);
		if(time_to_vid_to_vi != undefined && time_to_vid_to_vi.size() > 0) {
			if(new_times_set==null) {
				new_times_set = array_to_set(time_to_vid_to_vi.keys());
			} else {
				var oldsize = new_times_set.size();
				if(time_to_vid_to_vi.size() > 0) { // don't let empty ones influence this.  presumably we haven't 
						// received any data from the server yet for routes with an empty one of these. 
					new_times_set.intersection(array_to_set(time_to_vid_to_vi.keys()));
				}
			}
		}
	});
	if(new_times_set == null) {
		new_times_set = new buckets.Set();
	}

	var cur_time = g_times.elementAtIndex(Math.min(g_cur_minute_idx, g_times.size()-1));

	// Go through some contortions to turn new_times_set into a sorted list: 
	var new_times_sortedtree = new buckets.BSTree();
	new_times_set.forEach(function(e) {
		new_times_sortedtree.add(e);
	});
	g_times = new buckets.LinkedList();
	new_times_sortedtree.forEach(function(e) {
		g_times.add(e);
	});

	// This is to try to stay showing the same minute (moving vehicles) even if g_times changes due to an update from the server: 
	g_cur_minute_idx = g_times.indexOf(cur_time);
	if(g_cur_minute_idx == -1) { // ... but sometimes that doesn't work out (like if it's 1:31, and we were showing 1:00, 
		g_cur_minute_idx = 0; // but now we don't have that 1:00 data any more (earliest being 1:01 now.) 
	}
}

function array_to_set(a_) {
	var r = new buckets.Set();
	a_.forEach(function(e) {
		r.add(e);
	});
	return r;
}

function remake_moving_vehicles_allroutes(fudgeroute_) {
	g_fudgeroute_data.forEach(function(fudgeroute, data)  {
		remake_moving_vehicles_singleroute(fudgeroute);
	});
}

function remake_moving_vehicles_singleroute(fudgeroute_) {
	forget_moving_vehicles(fudgeroute_);
	var data = g_fudgeroute_data.get(fudgeroute_);
	var new_vid_to_heading_to_moving_vehicle_marker = new buckets.Dictionary();
	if(data.vehicles_datazoom == -1) {
		return;
	}
	data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom).forEach(function(timestr, vid_to_vi) {
		vid_to_vi.forEach(function(vid, vi) {
			var heading_to_moving_vehicle_marker = new_vid_to_heading_to_moving_vehicle_marker.get(vid);
			if(heading_to_moving_vehicle_marker == undefined) {
				heading_to_moving_vehicle_marker = new buckets.Dictionary();
				new_vid_to_heading_to_moving_vehicle_marker.set(vid, heading_to_moving_vehicle_marker);
			}
			var rounded_heading = round_heading(vi.heading);
			if(!heading_to_moving_vehicle_marker.containsKey(rounded_heading)) {
				var marker = make_vehicle_marker(vid, rounded_heading, 43, 79, false);
				heading_to_moving_vehicle_marker.set(rounded_heading, marker);
			}
		});
	});
	data.vid_to_heading_to_moving_vehicle_marker = new_vid_to_heading_to_moving_vehicle_marker;
}

function round_heading(heading_) {
	var r = round(heading_, HEADING_ROUNDING_DEGREES);
	if(r == 360) {
		r = 0;
	}
	return r;
}

function refresh_data_from_server_timer_func() {
	refresh_data_from_server_allroutes();
	schedule_refresh_data_from_server();
}

function refresh_data_from_server_allroutes() {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		if(!is_subway(fudgeroute)) {
			refresh_data_from_server_singleroute(fudgeroute);
		}
	});
}

function refresh_data_from_server_singleroute(fudgeroute_) {
	refresh_traffic_from_server(fudgeroute_);
	refresh_vehicles_from_server(fudgeroute_);
}

function remake_static_vehicles_allroutes() {
	g_fudgeroute_data.forEach(function(fudgeroute, data)  {
		remake_static_vehicles_singleroute(fudgeroute);
	});
}

function remake_static_vehicles_singleroute(fudgeroute_) {
	forget_static_vehicles(fudgeroute_);
	if(g_times.size() > 0) {
		var data = g_fudgeroute_data.get(fudgeroute_);
		if(data.vehicles_datazoom != -1) {
			var last_time = g_times.elementAtIndex(g_times.size()-1);
			var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom);
			if(time_to_vid_to_vi != undefined) {
				var vid_to_vi = time_to_vid_to_vi.get(last_time);
				if(vid_to_vi != undefined) {
					vid_to_vi.forEach(function(vid, vi) {
						var marker = make_vehicle_marker(vid, round_heading(vi.heading), vi.lat, vi.lon, true);
						data.vid_to_static_vehicle_marker.set(vid, marker);
					});
				}
			}
		}
	}
}

function moving_vehicles_timer_func() {
	var method_start_epochtime = (new Date()).getTime();

	if(!g_playing || !g_show_moving_vehicles) {
		g_play_timer = setTimeout('moving_vehicles_timer_func()', MOVING_VEHICLES_ANIM_INTERVAL_MS);
		return;
	} else {
		g_cur_minute_idx = (g_cur_minute_idx + 1) % (g_times.size() + 4);
		if(DISABLE_OVERTIME) {
			g_cur_minute_idx = g_cur_minute_idx % g_times.size();
		}

		var timeout = (g_cur_minute_idx >= g_times.size()-1 
				? MOVING_VEHICLES_OVERTIME_FLASH_INTERVAL_MS : MOVING_VEHICLES_ANIM_INTERVAL_MS);
		if(DISABLE_OVERTIME) {
			timeout = MOVING_VEHICLES_ANIM_INTERVAL_MS;
		}
		g_play_timer = setTimeout('moving_vehicles_timer_func()', timeout);
	}

	update_clock_show_cur_minute();
	move_vehicles_forward_one_minute();

	if(SHOW_FRAMERATE) {
		var cur_epochtime = (new Date()).getTime();
		if(g_cur_minute_idx > 0 && g_cur_minute_idx <= g_times.size()-2) {
			var cur_period_time = cur_epochtime - g_framerate_last_epochtime;

			var our_work_time = (cur_epochtime - method_start_epochtime);
			set_contents('p_worktime', sprintf('Our work time: %d ms', our_work_time));

			g_framerate_period_times.add(cur_period_time);
			g_framerate_period_times.removeElementAtIndex(0);
			var tally_time = 0;
			g_framerate_period_times.forEach(function(e) {
				tally_time += e;
			});
			var avg_millis_per_frame = tally_time/g_framerate_period_times.size();
			var frames_per_sec = 1000/avg_millis_per_frame;
			set_contents('p_framerate', sprintf('%.1f frames per second', frames_per_sec));
		}
		g_framerate_last_epochtime = cur_epochtime;
	}
}

function in_overtime() {
	return (g_cur_minute_idx >= g_times.size());
}

function in_overtime_flash_on() {
	return ((g_cur_minute_idx - g_times.size()) % 2 == 1);
}

function set_all_static_vehicle_markers_visible_allroutes(visible_) {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		set_all_static_vehicle_markers_visible_singleroute(fudgeroute, visible_);
	});
}

// Not 'all' really.  This function respects the hidden vid checkboxes. 
function set_all_static_vehicle_markers_visible_singleroute(fudgeroute_, visible_) {
	var data = g_fudgeroute_data.get(fudgeroute_);
	data.vid_to_static_vehicle_marker.forEach(function(vid, marker) {
		marker.setVisible(visible_ && !g_hidden_vids.contains(vid));
	});
}

function move_vehicles_forward_one_minute() {
	if(g_cur_minute_idx < g_times.size()-1) {
		move_vehicles_forward_one_minute_normal();
	} else {
		move_vehicles_forward_one_minute_overtime();
	}
}

function move_vehicles_forward_one_minute_overtime() {
	if(g_times.size() == 0) {
		return;
	}
	if(g_cur_minute_idx == g_times.size()-1) { // special case, going into overtime: 
		g_fudgeroute_data.forEach(function(fudgeroute, data) {
			var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom);
			if(time_to_vid_to_vi != undefined && time_to_vid_to_vi.size() > 0) {
				var prev_minute_vid_to_vi = time_to_vid_to_vi.get(g_times.elementAtIndex(g_times.size()-2));
				prev_minute_vid_to_vi.forEach(function(vid, prev_minute_vi) {
					var prev_heading = round_heading(prev_minute_vi.heading);
					if(!TEST_INVISIBLE) data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(prev_heading).setVisible(false);
				});
			}
		});
	} else { // somewhere in overtime, either flash on or flash off: 
		g_fudgeroute_data.forEach(function(fudgeroute, data) {
			var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom);
			if(time_to_vid_to_vi != undefined && time_to_vid_to_vi.size() > 0) {
				var last_time = g_times.elementAtIndex(g_times.size()-1);
				time_to_vid_to_vi.get(last_time).forEach(function(vid, vi) {
					var heading = round_heading(vi.heading);
					var marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(heading);
					if(g_cur_minute_idx == g_times.size()) {
						marker.setPosition(new google.maps.LatLng(vi.lat, vi.lon));
					}
					if(!TEST_INVISIBLE) {
						marker.setVisible(g_show_moving_vehicles && !in_overtime_flash_on() && !g_hidden_vids.contains(vid));
					}
				});
			}
		});
		set_all_static_vehicle_markers_visible_allroutes(in_overtime_flash_on() && g_show_static_vehicles);
	} 
}

function move_vehicles_forward_one_minute_normal() {
	if(g_times.size() == 0) {
		return;
	}
	var prev_minute_idx = g_cur_minute_idx-1;
	if(prev_minute_idx < 0) {
		prev_minute_idx = g_times.size()-1;
	}
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom);
		if(time_to_vid_to_vi != undefined && time_to_vid_to_vi.size() > 0) {
			var prev_minute_vid_to_vi = time_to_vid_to_vi.get(g_times.elementAtIndex(prev_minute_idx));
			var cur_minute_vid_to_vi = time_to_vid_to_vi.get(g_times.elementAtIndex(g_cur_minute_idx));
			cur_minute_vid_to_vi.forEach(function(vid, cur_minute_vi) {
				if(g_hidden_vids.contains(vid)) {
					return;
				}
				var cur_within_bounds = within_map_bounds(cur_minute_vi);
				var prev_minute_vi = prev_minute_vid_to_vi.get(vid);
				var cur_heading = round_heading(cur_minute_vi.heading);
				if(prev_minute_vi == undefined) {
					if(cur_within_bounds) {
						var marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(cur_heading);
						marker.setPosition(new google.maps.LatLng(cur_minute_vi.lat, cur_minute_vi.lon));
						if(!TEST_INVISIBLE) {
							marker.setVisible(g_show_moving_vehicles);
						}
					}
				} else {
					var prev_within_bounds = within_map_bounds(prev_minute_vi);
					var prev_heading = round_heading(prev_minute_vi.heading);
					if(cur_heading == prev_heading) {
						if((prev_within_bounds && cur_within_bounds) || (!prev_within_bounds && cur_within_bounds)) {
							var marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(cur_heading);
							marker.setPosition(new google.maps.LatLng(cur_minute_vi.lat, cur_minute_vi.lon));
							marker.setVisible(g_show_moving_vehicles);
						} else if(prev_within_bounds && !cur_within_bounds) {
							var marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(cur_heading);
							marker.setVisible(false);
						} 
					} else {
						if(prev_within_bounds && cur_within_bounds) {
							var prev_marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(prev_heading);
							var cur_marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(cur_heading);
							prev_marker.setVisible(false);
							cur_marker.setPosition(new google.maps.LatLng(cur_minute_vi.lat, cur_minute_vi.lon));
							cur_marker.setVisible(g_show_moving_vehicles);
						} else if(prev_within_bounds && !cur_within_bounds) {
							var prev_marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(prev_heading);
							prev_marker.setVisible(false);
						} else if(!prev_within_bounds && cur_within_bounds) {
							var cur_marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(cur_heading);
							cur_marker.setPosition(new google.maps.LatLng(cur_minute_vi.lat, cur_minute_vi.lon));
							cur_marker.setVisible(g_show_moving_vehicles);
						}
					}
				}
			});
			prev_minute_vid_to_vi.forEach(function(vid, prev_minute_vi) {
				if(!cur_minute_vid_to_vi.containsKey(vid) || g_hidden_vids.contains(vid)) {
					var prev_within_bounds = within_map_bounds(prev_minute_vi);
					var prev_heading = round_heading(prev_minute_vi.heading);
					if(prev_within_bounds) {
						if(!TEST_INVISIBLE) data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(prev_heading).setVisible(false);
					}
				}
			});
		}
	});
}

function within_map_bounds(vi_) {
	var map_bounds = g_map.getBounds();
	var sw = map_bounds.getSouthWest(), ne = map_bounds.getNorthEast();
	return (sw.lat() <= vi_.lat && vi_.lat <= ne.lat()) && (sw.lng() <= vi_.lon && vi_.lon <= ne.lng());
}

// show cur minute unless we are not showing moving vehicles, in which case show the last time in g_times. 
function update_clock_show_cur_minute() {
	if(g_times.size() > 0) {
		var time_idx = (g_show_moving_vehicles ? Math.min(g_cur_minute_idx, g_times.size()-1) : g_times.size()-1);
		var timestr = g_times.elementAtIndex(time_idx);
		update_clock(timestr);
	} else {
		update_clock(null);
	}
}

function update_clock(timestr_) {
	if(timestr_ == null) {
		set_clock_hour_minute(0, 0);
	} else {
		set_clock_timestr(timestr_);
		var cur_time_html = timestr_.substr(0, 16);
		if((g_cur_minute_idx == g_times.size()-1) || (in_overtime() && in_overtime_flash_on())) {
			cur_time_html = '<b>'+cur_time_html+'</b>';
		}
	}
}

function set_clock_timestr(timestr_) {
	// We want a timestamp in the format: 2012-10-30 01:14:00 
	assert((new RegExp('\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}')).test(timestr_), "date/time does not match");

	var hour = parseInt(timestr_.substr(11, 2), 10), minute = parseInt(timestr_.substr(14, 2), 10);
	set_clock_hour_minute(hour, minute);
}

function set_clock_hour_minute(hour_, minute_) {
	if(BROWSER_SUPPORTS_SVG) {
		var hourangle = ((hour_ % 12) + minute_/60)*30;
		var minangle = minute_*6;

		// Get SVG elements for the hands of the clock
		//var sechand = document.getElementById('secondhand');
		var minhand = document.getElementById("minutehand");
		var hourhand = document.getElementById("hourhand");

		// Set an SVG attribute on them to move them around the clock face
		//sechand.setAttribute("transform", "rotate(" + secangle + ",50,50)");
		minhand.setAttribute("transform", "rotate(" + minangle + ",50,50)");
		hourhand.setAttribute("transform", "rotate(" + hourangle + ",50,50)");
	} else {
		set_contents('div_clock', sprintf('<b>%02d:%02d </b>', hour_, minute_));
	}
}

function make_vehicle_marker(vid_, heading_, lat_, lon_, static_aot_moving_) {
	var size = get_vehicle_size();
	var marker = new google.maps.Marker({
			position: new google.maps.LatLng(lat_, lon_),
			map: g_map,
			draggable: false,
			icon: new google.maps.MarkerImage(get_vehicle_url(vid_, size, heading_, static_aot_moving_), 
					null, null, new google.maps.Point(size/2, size/2)),
			visible: false, 
			clickable: false,
			zIndex: 5
		});
	if(!TEST_INVISIBLE) {
		if((static_aot_moving_ && g_show_static_vehicles) || (!static_aot_moving_ && g_show_moving_vehicles)) {
			marker.setVisible(true);
		}
	}
	add_vid_mouseover_infowin(marker, size, vid_);
	//add_solo_vid_click_listener(marker, vid_);
	return marker;
}

function get_vehicle_url(vid_, size_, heading_, static_aot_moving_) {
	var filename = '';
	if(g_use_rendered_aot_arrow_vehicle_icons) {
		var vehicletype = (is_a_streetcar(vid_) ? 'streetcar' : 'bus');
		filename = sprintf('%s-%s-size-%d-heading-%d.png', vehicletype, (static_aot_moving_ ? 'static' : 'moving'), size_, heading_);
	} else {
		filename = sprintf('vehicle_arrow_%d_%d_%s.png', size_, heading_, (static_aot_moving_ ? 'static' : 'moving'));
	}
	return 'img/'+filename;
}

function add_solo_vid_click_listener(vehicle_marker_, vid_) {
	google.maps.event.addListener(vehicle_marker_, 'click', function() { set_solo_vid(vid_); });
}

function set_solo_vid(vid_) {
	var was_solo = is_solo_already();
	g_fudgeroute_data.forEach(function(froute, data) {
		all_vids_singleroute(froute).forEach(function(vid) {
			var checkbox = document.getElementById(vid_checkbox_id(froute, vid));
			if(was_solo) {
				if(!checkbox.checked) {
					checkbox.checked = true;
					on_vid_checkbox_clicked(vid);
				}
			} else {
				if(vid == vid_) {
					if(!checkbox.checked) {
						checkbox.checked = true;
						on_vid_checkbox_clicked(vid);
					}
				} else {
					if(checkbox.checked) {
						checkbox.checked = false;
						on_vid_checkbox_clicked(vid);
					}
				}
			}
		});
	});
}

function is_solo_already() {
	return (all_vids_allroutes().size() == g_hidden_vids.size()+1);
}

function add_vid_mouseover_infowin(vehicle_marker_, vehicle_marker_size_, vid_) {
	add_hover_listener(vehicle_marker_, function() {
		var infowin = new google.maps.InfoWindow({content: sprintf('Vehicle ID %s', vid_), 
			position: vehicle_marker_.getPosition()});
		infowin.open(g_map);
		return infowin;
	}, 1000);

}

function add_mouseover_infowin(map_object_, offset_, text_) {
	google.maps.event.addListener(map_object_, 'mouseover', function() {
		clear_mouseover_infowin();
		if(g_mouseover_infowin_timer != null) {
			clearTimeout(g_mouseover_infowin_timer);
			g_mouseover_infowin_timer = null;
		}
		var pos = null;
		if(map_object_ instanceof google.maps.Marker) {
			pos = map_object_.getPosition();
		} else if(map_object_ instanceof google.maps.Polyline) {
			pos = map_object_.getPath().getAt(0);
		} else {
			assert(false, "add_mouseover_infowin unknown object type");
		}
		g_mouseover_infowin = new google.maps.InfoWindow({content: text_, disableAutoPan: true, 
				position: pos, pixelOffset: new google.maps.Size(offset_, -offset_) 
			});
		g_mouseover_infowin.open(g_map);
	});
	google.maps.event.addListener(map_object_, 'mouseout', function() {
		g_mouseover_infowin_timer = setTimeout('clear_mouseover_infowin()', 1000);
	});
}

function clear_mouseover_infowin() {
	if(g_mouseover_infowin != null) {
		g_mouseover_infowin.close();
		g_mouseover_infowin = null;
	}
}

function forget_vehicles_allroutes() {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		forget_vehicles(fudgeroute);
	});
}

function forget_vehicles(fudgeroute_) {
	forget_moving_vehicles(fudgeroute_);
	forget_static_vehicles(fudgeroute_);
}

function forget_moving_vehicles(fudgeroute_) {
	if(g_fudgeroute_data.containsKey(fudgeroute_)) {
		var m = g_fudgeroute_data.get(fudgeroute_).vid_to_heading_to_moving_vehicle_marker;
		m.forEach(function(vid, heading_to_moving_vehicle_marker) {
			hide_vehicles(heading_to_moving_vehicle_marker.values());
		});
		m.clear();
	}
}

function forget_static_vehicles(fudgeroute_) {
	if(g_fudgeroute_data.containsKey(fudgeroute_)) {
		var m = g_fudgeroute_data.get(fudgeroute_).vid_to_static_vehicle_marker;
		hide_vehicles(m.values());
		m.clear();
	}
}

function hide_vehicles(list_) {
	list_.forEach(function(m) {
		m.setMap(null);
	});
}

function remake_all_vehicle_markers() {
	forget_vehicles_allroutes();
	remake_static_vehicles_allroutes();
	remake_moving_vehicles_allroutes();
	show_cur_minute_vehicles_allroutes();
}

function remake_traffic_lines_allroutes() {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		remake_traffic_lines_singleroute(fudgeroute);
	});
}

function remake_traffic_lines_singleroute(fudgeroute_) {
	forget_traffic_lines(fudgeroute_);

	var data = g_fudgeroute_data.get(fudgeroute_);
	if(data != undefined) {
		if(is_subway(fudgeroute_)) {
			make_subway_lines(fudgeroute_);
		} else if(data.traffic_datazoom != -1) {
			data.datazoom_to_traffic_linedefs.get(data.traffic_datazoom).forEach(function(linedef) {
				var traf = data.datazoom_to_traffic_mofr2speed.get(data.traffic_datazoom).get(linedef.mofr);
				var new_lines = make_traffic_line(fudgeroute_, linedef.start_latlon, linedef.end_latlon, (traf!=null ? traf.kmph : null), 
						linedef.mofr);
				add_all(data.traffic_lines, new_lines);
			});
		}
	}
}

function forget_traffic_lines(fudgeroute_) {
	var data = g_fudgeroute_data.get(fudgeroute_);
	if(data != undefined) {
		data.traffic_lines.forEach(function(e) {
			e.setMap(null);
		});
		data.traffic_lines.clear();
	}
}

function initialize() {

	init_map();

	init_everything_that_doesnt_depend_on_map();

	// Some things that we do depend on g_map.getBounds(), which will be undefined until the map has had time to load a bit. 
	google.maps.event.addListenerOnce(g_map, 'bounds_changed', init_everything_that_depends_on_map);
}

function init_everything_that_doesnt_depend_on_map() {

	if(SHOW_DEV_CONTROLS) {
		init_datetimepicker();
	} else {
		$('#div_dev_controls').remove();
	}
	if(!SHOW_PATHS_TEXT) {
		$('#p_paths_text').remove();
	}
	if(!SHOW_LOADING_URLS) {
		$('#p_loading_urls').remove();
	}
	if(!SHOW_ZOOM) {
		$('#p_zoom').remove();
	}

	set_play_buttons_appropriately();

	if(!SHOW_FRAMERATE) {
		$('#div_framerate').remove();
	}

	init_num_extra_routes_controls();

	init_message_dialog();
	init_route_options_dialog();
	init_route_select_dialog();

	init_rendered_aot_arrow_vehicle_icons_buttons();

	$(window).bind("resize", on_browser_window_resized);
	on_browser_window_resized();

	if(!BROWSER_SUPPORTS_SVG) {
		$('#svg_clock').remove();
	}
}

function on_browser_window_resized() {
	var window_height = $(window).height();
	var map_height = Math.round(window_height*3/4);
	$('#map_canvas').css('height', sprintf('%dpx', map_height));
	$('#div_clock').css('top', sprintf('%dpx', map_height-70));
	$('#div_loading_img').css('top', sprintf('%dpx', map_height-35));
}

// For IE8 etc.  
function init_javascript_array_functions_old_browser_fallbacks() {

	// From https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Array/IndexOf
	if (!Array.prototype.indexOf) {
			Array.prototype.indexOf = function (searchElement /*, fromIndex */ ) {
					"use strict";
					if (this == null) {
							throw new TypeError();
					}
					var t = Object(this);
					var len = t.length >>> 0;
					if (len === 0) {
							return -1;
					}
					var n = 0;
					if (arguments.length > 1) {
							n = Number(arguments[1]);
							if (n != n) { // shortcut for verifying if it's NaN
									n = 0;
							} else if (n != 0 && n != Infinity && n != -Infinity) {
									n = (n > 0 || -1) * Math.floor(Math.abs(n));
							}
					}
					if (n >= len) {
							return -1;
					}
					var k = n >= 0 ? n : Math.max(len - Math.abs(n), 0);
					for (; k < len; k++) {
							if (k in t && t[k] === searchElement) {
									return k;
							}
					}
					return -1;
			}
	}

	// From https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Array/forEach
	// Production steps of ECMA-262, Edition 5, 15.4.4.18
	// Reference: http://es5.github.com/#x15.4.4.18
	if ( !Array.prototype.forEach ) {
	 
		Array.prototype.forEach = function forEach( callback, thisArg ) {
	 
			var T, k;
	 
			if ( this == null ) {
				throw new TypeError( "this is null or not defined" );
			}
	 
			// 1. Let O be the result of calling ToObject passing the |this| value as the argument.
			var O = Object(this);
	 
			// 2. Let lenValue be the result of calling the Get internal method of O with the argument "length".
			// 3. Let len be ToUint32(lenValue).
			var len = O.length >>> 0; // Hack to convert O.length to a UInt32
	 
			// 4. If IsCallable(callback) is false, throw a TypeError exception.
			// See: http://es5.github.com/#x9.11
			if ( {}.toString.call(callback) !== "[object Function]" ) {
				throw new TypeError( callback + " is not a function" );
			}
	 
			// 5. If thisArg was supplied, let T be thisArg; else let T be undefined.
			if ( thisArg ) {
				T = thisArg;
			}
	 
			// 6. Let k be 0
			k = 0;
	 
			// 7. Repeat, while k < len
			while( k < len ) {
	 
				var kValue;
	 
				// a. Let Pk be ToString(k).
				//   This is implicit for LHS operands of the in operator
				// b. Let kPresent be the result of calling the HasProperty internal method of O with argument Pk.
				//   This step can be combined with c
				// c. If kPresent is true, then
				if ( Object.prototype.hasOwnProperty.call(O, k) ) {
	 
					// i. Let kValue be the result of calling the Get internal method of O with argument Pk.
					kValue = O[ k ];
	 
					// ii. Call the Call internal method of callback with T as the this value and
					// argument list containing kValue, k, and O.
					callback.call( T, kValue, k, O );
				}
				// d. Increase k by 1.
				k++;
			}
			// 8. return undefined
		};
	}



}

function init_everything_that_depends_on_map() {
	google.maps.event.addListener(g_map, 'zoom_changed', on_guizoom_changed);

	g_play_timer = setTimeout('moving_vehicles_timer_func()', 0);

	init_trip_markers();
	init_geolocation();

	// The first 'get' of data from the server will happen due to the get_paths_from_server() call below.  
	schedule_refresh_data_from_server(); // But this call here will cause a periodic refresh of all routes.  The first refresh 
			// caused by this will happen not right away, but in a few seconds. 

	create_invisible_clickable_route_grid();

	if(SHOW_PATH_GRID_SQUARES) {
		show_pathgridsquares();
	}

	add_delayed_event_listener(g_map, 'bounds_changed', refresh_streetlabels_allroutes, 500);

	if(SHOW_HISTORICAL_ON_LOAD) {
		set_selected('historical_button', true);
		on_traffictype_changed();
	}

	if(!HARDCODE_DISPLAY_SET) {
		get_paths_from_server();
	} else {
		show_hardcoded_display_set();
	}

	google.maps.event.addListener(g_map, 'click', on_map_click);
}

function on_map_click(mouseevent_) {
	var latlng = new LatLng(mouseevent_.latLng.lat(), mouseevent_.latLng.lng());
	var nearby_froutes = [];
	var search_radius = get_map_click_route_search_radius_for_cur_guizoom();
	g_froute_to_snaptogridcache.forEach(function(froute, snaptogridcache) {
		if(snaptogridcache.snap(latlng, search_radius) != null) {
			nearby_froutes.push(froute);
		}
	});
	if(nearby_froutes.length == 0) {
		show_message_dialog('', 'You clicked in a place where we don\'t know of any routes.  Either there is no TTC route here, or we haven\'t gotten around to supporting that route yet.');
	} else if(nearby_froutes.length == 1) {
		show_route_options_dialog(nearby_froutes[0]);
	} else {
		nearby_froutes.sort();
		show_route_select_dialog(nearby_froutes);
	}
}

function get_map_click_route_search_radius_for_cur_guizoom() {
	var meters_per_pixel = get_meters_per_pixel_for_cur_guizoom();
	var pixels = 30; // Seems like a clickable area. 
	var r = Math.round(meters_per_pixel*pixels);

	// Doing this because we are using route pts at min datazoom (which will have max rsdt) for the invisble clickable grid, 
	// so when the user is at a high zoom, that invisible route polyline could be quite far (in pixels) from 
	// where the street is on the map.  By our definition of what an RSDT is, the farthest distance from a real route to 
	// a simplified version is the RSDT.  (For the purposes of this comment, assume that the street as it appears on the 
	// google map coincides exactly with the real route AKA the unsimplified route AKA the route at RSDT of 0.)  
	// So eg. our east-west route could, in a certain area, be such that the the max-rsdt simplified version of it 
	// runs MAX_RSDT meters below or above it.  So that means that our search radius should always be at least RSDT, 
	// or else the user could click right on the street and we would not count that as a hit.  Going further - in that case 
	// it would not be very useful if we made the clickable area end eg. one pixel north of the street on the map. 
	// So that is why we use MAX_RSDT*2. 
	r = Math.max(r, MAX_RSDT*2);

	return r;
}

function get_meters_per_pixel_for_cur_guizoom() {
	var zoom = g_map.getZoom();
	if(!(zoom in GUIZOOM_TO_METERSPERPIXEL)) {
		// Top answer in http://stackoverflow.com/questions/4946287/finding-out-if-console-is-available/4946373#4946373 
		// for testing for the existence of 'console.log'.  I feel like there is a better way.  Oh well. 
		if(typeof console == "object") { 
			console.log(sprintf("zoom %d not present in map.", zoom));
		}
		var zoom_keys = sorted_keys(GUIZOOM_TO_METERSPERPIXEL);
		var min_zoom_key = arrayMin(zoom_keys), max_zoom_key = arrayMax(zoom_keys);
		if(zoom < min_zoom_key) { 
			zoom = min_zoom_key;
		} else if(zoom > max_zoom_key) {
			zoom = max_zoom_key;
		} else {
			throw sprintf("Don't know what to do for route search radius in zoom %d.", zoom);
		}
	}
	return GUIZOOM_TO_METERSPERPIXEL[zoom];
}

function on_guizoom_changed() {
	if(SHOW_ZOOM) {
		set_contents('p_zoom', "Zoom: "+(g_map.getZoom())); 
	}

	if(g_map.getZoom() < MIN_GUIZOOM) {
		g_map.setZoom(MIN_GUIZOOM);
	} else if(g_map.getZoom() > MAX_GUIZOOM) {
		g_map.setZoom(MAX_GUIZOOM);
	} else {
		var guizoom = g_map.getZoom();
		g_fudgeroute_data.forEach(function(froute, data) {
			if(!is_subway(froute)) {
				update_traffic_datazoom(froute);
				if(data.traffic_datazoom != guizoom) {
					refresh_traffic_from_server(froute);
				}

				update_vehicles_datazoom(froute);
				if(data.vehicles_datazoom != guizoom) {
					refresh_vehicles_from_server(froute);
				}
			}
		});
		remake_traffic_lines_allroutes();
		remake_all_vehicle_markers();
	}
}

function show_hardcoded_display_set() {
	HARDCODED_DISPLAY_SET.forEach(function(froutendir) {
		var froute = froutendir[0];
		var dir = froutendir[1];
		g_force_show_froutes.add(froute);
		(dir == 0 ? g_force_dir0_froutes : g_force_dir1_froutes).add(froute);
	});
	calc_display_set_and_deal_with_it();
	g_trip_orig_marker.setVisible(false);
	g_trip_dest_marker.setVisible(false);
}

function init_geolocation() {
	if(!DISABLE_GEOLOCATION) {
		if(navigator.geolocation) {
			var on_success = function(position) {
				var latlng = new google.maps.LatLng(position.coords.latitude, position.coords.longitude);
				g_trip_orig_marker.setPosition(latlng);
				g_map.panTo(latlng);
				get_paths_from_server();
			};
			navigator.geolocation.getCurrentPosition(on_success, null, {timeout: 10000});
		}
	}
}

function map_fit_bounds_to_trip_markers() {
	var p1 = g_trip_orig_marker.getPosition(), p2 = g_trip_dest_marker.getPosition();
	var sw = new google.maps.LatLng(Math.min(p1.lat(), p2.lat()), Math.min(p1.lng(), p2.lng()));
	var ne = new google.maps.LatLng(Math.max(p1.lat(), p2.lat()), Math.max(p1.lng(), p2.lng()));
	g_map.fitBounds(new google.maps.LatLngBounds(sw, ne));
	if(g_browser_is_desktop) {
		g_map.setZoom(g_map.getZoom()-2);
	}
}

function refresh_streetlabels_allroutes() {
	g_fudgeroute_data.forEach(function(froute, data) {
		refresh_streetlabels_singleroute(froute);
	});
}

function refresh_streetlabels_singleroute(froute_) {
	if(is_subway(froute_)) {
		return;
	}
	var guizoom = g_map.getZoom();
	var direction = g_fudgeroute_data.get(froute_).dir;
	if(!do_streetlabels_for_guizoom(guizoom) || !g_show_traffic_lines) {
		forget_streetlabels_singleroute(froute_);
	} else {
		callpy('streetlabels.get_labels', froute_, direction, guizoom, g_map.getBounds().getSouthWest(), g_map.getBounds().getNorthEast(), 
			function(labels) {
				// This is a callback, so since we started the call, this route could have been hidden or the guizoom could have been changed, 
				// or all traffic lines hidden.  
				// The map bounds could have changed too but I don't care as much about them right now for some reason. 
				if(!g_fudgeroute_data.containsKey(froute_) || (g_map.getZoom() != guizoom) || !g_show_traffic_lines 
						|| !dir_equals(g_fudgeroute_data.get(froute_).dir, direction)) {
					return;
				}
				forget_streetlabels_singleroute(froute_);
				labels.forEach(function(label) {
					var marker = new google.maps.Marker({position: google_LatLng(label.latlng), 
						map: g_map, draggable: false, flat: true, clickable: false, zIndex: 4,
						icon: new google.maps.MarkerImage(get_streetlabel_url(label.text, label.rotation, guizoom), 
								null, null, new google.maps.Point(150, 150))
						});
					g_fudgeroute_data.get(froute_).streetlabel_markers.add(marker);
				});
			});
	}
}

function get_streetlabel_url(text_, rotation_, guizoom_) {
	var filename = sprintf('streetlabel_%s_%d_%d.png', text_.replace(/ /g, '_'), rotation_, guizoom_);
	return 'img/'+filename;
}

/* The whole reason we do our own street labels is because our traffic polylines, to show up reasonably well, have to be 
thick enough that they obscure google map's own street labels.  I've set up the widths of our traffic polylines so 
that for (gui)zooms 13 to 21 inclusive, our lines are thick enough that they cover the entire google maps label (most of the time) 
so the user won't see both ours and google map's labels.  For zooms less than 13 I've made our lines thin enough that google's 
labels are readable, and hence ours aren't necessary.  This range 13 to 21 is also hard-coded in streetlabels.py.  Here we check 
on the client side, to maybe save a server call that would return an empty list anyway.   
Note that 21 is the maximum zoom of a google map. 
*/
function do_streetlabels_for_guizoom(zoom_) {
	return (13 <= zoom_ && zoom_ <= 21);
}

function forget_streetlabels_allroutes() {
	g_fudgeroute_data.forEach(function(froute, data) {
		forget_streetlabels_singleroute(froute);
	});
}

function forget_streetlabels_singleroute(froute_) {
	g_fudgeroute_data.get(froute_).streetlabel_markers.forEach(function(e) {
		e.setMap(null);
	});
	g_fudgeroute_data.get(froute_).streetlabel_markers.clear();
}

function init_message_dialog() {
	$("#message-dialog").dialog({
		resizable: false,
		autoOpen: false,
		modal: true,
		buttons: { 'Ok': function() { $(this).dialog('close'); } }
	});
}

function init_route_options_dialog() {
	$("#route-options-dialog").dialog({
		resizable: false,
		autoOpen: false,
		//height:340,
		modal: true,
		buttons: {
			'Ok': function() { on_route_options_dialog_ok_clicked(); $(this).dialog('close'); },
			'Cancel': function() { $(this).dialog('close'); }
		}
	});
}

function init_route_select_dialog() {
	$("#route-select-dialog").dialog({
		resizable: false,
		autoOpen: false,
		modal: true,
	});
}

function on_route_options_dialog_ok_clicked() {
	update_force_sets_from_dialog_gui();
	calc_display_set_and_deal_with_it();
}

function update_force_sets_from_dialog_gui() {
	assert_force_sets_consistent();
	var show = radio_val('show');

	var was_solo = showing_route_solo(g_route_options_dialog_froute);
	if(was_solo && show != 'solo') {
		g_force_show_froutes.clear();
		g_force_hide_froutes.clear();
	}

	if(show == 'show') {
		g_force_show_froutes.add(g_route_options_dialog_froute);
		g_force_hide_froutes.remove(g_route_options_dialog_froute);
	} else if(show == 'hide') {
		g_force_show_froutes.remove(g_route_options_dialog_froute);
		g_force_hide_froutes.add(g_route_options_dialog_froute);
	} else if(show == 'solo') {
		g_force_show_froutes.clear();
		g_force_show_froutes.add(g_route_options_dialog_froute);
		g_force_hide_froutes.clear();
		g_all_froutes.forEach(function(froute) {
			if(froute != g_route_options_dialog_froute) {
				g_force_hide_froutes.add(froute);
			}
		});
	} else {
		g_force_show_froutes.remove(g_route_options_dialog_froute);
		g_force_hide_froutes.remove(g_route_options_dialog_froute);
	}

	var dir = radio_val('dir');
	if(dir == 'dir0') {
		g_force_dir0_froutes.add(g_route_options_dialog_froute);
		g_force_dir1_froutes.remove(g_route_options_dialog_froute);
	} else if(dir == 'dir1') {
		g_force_dir0_froutes.remove(g_route_options_dialog_froute);
		g_force_dir1_froutes.add(g_route_options_dialog_froute);
	} else {
		g_force_dir0_froutes.remove(g_route_options_dialog_froute);
		g_force_dir1_froutes.remove(g_route_options_dialog_froute);
	}

	assert_force_sets_consistent();
}

function is_subway(froute_) {
	return g_subway_froutes.contains(froute_);
}

function create_invisible_clickable_route_grid() {
	var froute_to_routepts = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION 
				passthru('python -c "import routes; print routes.get_froute_to_routepts_min_datazoom_json_str()"'); ?>;
	g_froute_to_snaptogridcache = new buckets.Dictionary();
	for(var froute in froute_to_routepts) {
		var routepts = froute_to_routepts[froute];
		g_all_froutes.push(froute); // using this opportunity to build a complete list of froute names on the client side here. 
		g_froute_to_snaptogridcache.set(froute, new SnapToGridCache(routepts));
	}
}

function assert_force_sets_consistent() {
	if(!((intersection(g_force_show_froutes, g_force_hide_froutes).size() == 0) 
			&& intersection(g_force_dir0_froutes, g_force_dir1_froutes).size() == 0)) {
		throw sprintf('force sets inconsistent - %s %s %s %s', 
				buckets_set_to_string(g_force_show_froutes), buckets_set_to_string(g_force_hide_froutes), 
				buckets_set_to_string(g_force_dir0_froutes), buckets_set_to_string(g_force_dir1_froutes));
	}
}

function show_message_dialog(title_, message_) {
	$('#message-dialog').dialog('option', 'title', title_);
	$('#message-dialog').html(message_);
	$('#message-dialog').dialog('open');
}

function show_route_options_dialog(froute_) {
	g_route_options_dialog_froute = froute_;
	assert_force_sets_consistent();
	function s(bool_) {
		return (bool_ ? ' checked="checked" ' : ' ');
	}
	var show = 'auto';
	if(showing_route_solo(froute_)) {
		show = 'solo';
	} else if(g_force_show_froutes.contains(froute_)) {
		show = 'show';
	} else if(g_force_hide_froutes.contains(froute_)) {
		show = 'hide';
	}
	var html = sprintf(
		  'Show this route?<br>'
		+ '<input id="showshowbutton" type="radio" name="show" value="show" onclick="" %(showchecked)s />'
		+ '<label for="showshowbutton" onclick="">Show it</label><br>'
		+ '<input id="showsolobutton" type="radio" name="show" value="solo" onclick="" %(solochecked)s />'
		+ '<label for="showsolobutton" onclick="">Show this route only</label><br>'
		+ '<input id="showhidebutton" type="radio" name="show" value="hide" onclick="" %(hidechecked)s />'
		+ '<label for="showhidebutton" onclick="">Hide it</label><br>'
		+ '<input id="showautobutton" type="radio" name="show" value="auto" onclick="" %(autochecked)s />'
		+ '<label for="showautobutton" onclick="">Auto</label><br>'
		, 
		{showchecked: s(show == 'show'), hidechecked: s(show == 'hide'), 
			autochecked: s(show == 'auto'), solochecked: s(show == 'solo')});
	if(!is_subway(froute_)) {
		var dir = 'auto';
		if(g_force_dir0_froutes.contains(froute_)) {
			dir = '0';
		} else if(g_force_dir1_froutes.contains(froute_)) {
			dir = '1';
		}
		html += sprintf('Direction to show:<br>'
			+ '<input id="dir0button" type="radio" name="dir" value="dir0" onclick="" %(dir0checked)s />'
			+ '<label for="dir0button" onclick="">%(dir0text)s</label><br>'
			+ '<input id="dir1button" type="radio" name="dir" value="dir1" onclick="" %(dir1checked)s />'
			+ '<label for="dir1button" onclick="">%(dir1text)s</label><br>'
			+ '<input id="dirautobutton" type="radio" name="dir" value="dirauto" onclick="" %(dirautochecked)s />'
			+ '<label for="dirautobutton" onclick="">Auto</label><br>', 
			{dir0text: FROUTE_TO_INTDIR_TO_ENGLISHDESC[froute_][0], dir1text: FROUTE_TO_INTDIR_TO_ENGLISHDESC[froute_][1], 
			dir0checked: s(dir == '0'), dir1checked: s(dir == '1'), dirautochecked: s(dir == 'auto')});
	}
	$('#route-options-dialog').dialog('option', 'title', FROUTE_TO_ENGLISH[froute_]);
	$('#route-options-dialog').html(html);
	$('#route-options-dialog').dialog('open');
}

function showing_route_solo(froute_) {
	assert_force_sets_consistent();
	assert(g_all_froutes.indexOf(froute_) != -1, "unknown froute '"+froute_+"'");
	return (g_force_show_froutes.size() == 1 && g_force_show_froutes.contains(froute_) 
			&& g_force_hide_froutes.size() == g_all_froutes.length-1);
}

function show_route_select_dialog(froutes_) {
	assert(froutes_.length > 0);
	var html = '';
	froutes_.forEach(function(froute) {
		html += sprintf('<input type="button" id="%(fr)s_button" onclick="on_route_select_button_clicked(\'%(fr)s\')" value="%(eng)s" /><br>', 
			{fr: froute, eng: FROUTE_TO_ENGLISH[froute]});
	});
	$('#route-select-dialog').dialog('option', 'title', 'Did you mean...');
	$('#route-select-dialog').html(html);
	$('#route-select-dialog').dialog('open');
}

function on_route_select_button_clicked(froute_) {
	$("#route-select-dialog").dialog('close');
	show_route_options_dialog(froute_);
}

function show_pathgridsquares() {
	show_pathgridsquares_draw_grid();
	show_pathgridsquares_add_rightclick_listener();
}

function show_pathgridsquares_add_rightclick_listener() {
	google.maps.event.addListener(g_map, 'rightclick', function(mouse_event) {	
		var click_latlng = mouse_event.latLng;
		callpy('paths.get_pathgridsquare', click_latlng, 
			function(r_) {
				var infowin = new google.maps.InfoWindow({content: r_, position: click_latlng});
				infowin.open(g_map);
			});
	});
}

function show_pathgridsquares_draw_grid() {
	var LATSTEP = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	  passthru('python -c "import paths; print paths.LATSTEP"'); ?>;
	var LNGSTEP = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	  passthru('python -c "import paths; print paths.LNGSTEP"'); ?>;
	var LATREF = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	  passthru('python -c "import paths; print paths.LATREF"'); ?>;
	var LNGREF = <?php # RUN_THIS_PHP_BLOCK_IN_MANGLE_TO_PRODUCTION
	  passthru('python -c "import paths; print paths.LNGREF"'); ?>;

	var minlat = LATREF-30*LATSTEP, maxlat = LATREF+60*LATSTEP;
	var minlng = LNGREF-40*LNGSTEP, maxlng = LNGREF+60*LNGSTEP;

	for(var lat=minlat; lat<=maxlat; lat+=LATSTEP) {
		new google.maps.Polyline({map: g_map, path: [google_LatLng([lat, minlng]), google_LatLng([lat, maxlng])], 
				strokeColor: 'rgb(0,0,0)', strokeWeight: 0.6, zIndex: -100});
		new google.maps.Polyline({map: g_map, path: [google_LatLng([lat+LATSTEP/2, minlng]), google_LatLng([lat+LATSTEP/2, maxlng])], 
				strokeColor: 'rgb(0,0,0)', strokeWeight: 0.2, zIndex: -100});
	}
	for(var lat=LATREF; lat<=LATREF+100*LATSTEP; lat+=10*LATSTEP) {
		new google.maps.Polyline({map: g_map, path: [google_LatLng([lat, minlng]), google_LatLng([lat, maxlng])], 
				strokeColor: 'rgb(0,255,0)', strokeWeight: 3, zIndex: -100});
	}
	for(var lng=minlng; lng<=maxlng; lng+=LNGSTEP) {
		new google.maps.Polyline({map: g_map, path: [google_LatLng([minlat, lng]), google_LatLng([maxlat, lng])], 
				strokeColor: 'rgb(0,0,0)', strokeWeight: 0.6, zIndex: -100});
		new google.maps.Polyline({map: g_map, path: [google_LatLng([minlat, lng+LNGSTEP/2]), google_LatLng([maxlat, lng+LNGSTEP/2])], 
				strokeColor: 'rgb(0,0,0)', strokeWeight: 0.2, zIndex: -100});
	}
	for(var lng=LNGREF; lng<=LNGREF+100*LNGSTEP; lng+=10*LNGSTEP) {
		new google.maps.Polyline({map: g_map, path: [google_LatLng([minlat, lng]), google_LatLng([maxlat, lng])], 
				strokeColor: 'rgb(0,255,0)', strokeWeight: 3, zIndex: -100});
	}

	draw_polygon('paths_db_hires_bounding_polygon.json');
}

function init_trip_markers() {
	g_trip_orig_marker = new google.maps.Marker({map: g_map, position: new google.maps.LatLng(43.6494532, -79.4314174), 
		draggable: true, icon: 'http://www.google.com/mapfiles/markerA.png', zIndex: 6});
	g_trip_dest_marker = new google.maps.Marker({map: g_map, position: new google.maps.LatLng(43.6523100, -79.4063549), 
		draggable: true, icon: 'http://www.google.com/mapfiles/markerB.png', zIndex: 6});

	google.maps.event.addListener(g_trip_orig_marker, 'dragend', on_trip_orig_marker_moved);
	google.maps.event.addListener(g_trip_dest_marker, 'dragend', on_trip_dest_marker_moved);

	map_fit_bounds_to_trip_markers();

	if(show_instructions()) {
		g_instructions_orig_infowin = new google.maps.InfoWindow({content: 'Move this marker to where<br>you are starting from.', zIndex: 2});
		g_instructions_orig_infowin.open(g_map, g_trip_orig_marker);
		g_instructions_dest_infowin = new google.maps.InfoWindow({content: '... and this one to where<br>you want to go.', zIndex: 1});
		g_instructions_dest_infowin.open(g_map, g_trip_dest_marker);
	}
}

function show_instructions() {
	return !DONT_SHOW_INSTRUCTIONS && g_browser_is_desktop;
}

function on_trip_orig_marker_moved() {
	on_trip_marker_moved(true);
}

function on_trip_dest_marker_moved() {
	on_trip_marker_moved(false);
}

function on_trip_marker_moved(orig_aot_dest_) {
	if(show_instructions()) {
		if(g_num_trip_marker_moves_so_far == 0) {
			g_num_trip_marker_moves_so_far += 1;
			g_instructions_orig_infowin.close();
			g_instructions_dest_infowin.close();
			var boxText = document.createElement("div");
			boxText.style.cssText = "border: 1px solid black; margin-top: 8px; background: white; padding: 5px; width: 175px";
			boxText.innerHTML = "Also, you can click on certain streets for more options.";
			g_instructions_also_infobox = new InfoBox({content: boxText, pixelOffset: new google.maps.Size(-70, 0), closeBoxMargin: "10px 2px 2px 2px"});
			g_instructions_also_infobox.open(g_map, (orig_aot_dest_ ? g_trip_orig_marker : g_trip_dest_marker));
		} else if(g_num_trip_marker_moves_so_far == 1) {
			g_num_trip_marker_moves_so_far += 1;
			g_instructions_also_infobox.close();
		}
	}
	get_paths_from_server();
}

function kmph_to_mps(kmph_) {
	return kmph_*1000.0/(60*60);
}

// 'off step' means 'steps shifted in phase by half the period, if you will'  
function round_up_off_step(x_, step_) {
	var r = round_down_off_step(x_, step_);
	return (r == x_ ? r : r+step_);
}

function round_down_off_step(x_, step_) {
	// assert type(x_) == int and type(step_) == int
	return Math.floor((x_-step_/2)/step_)*step_ + step_/2;
}

function round_up(x_, step_) {
	var r = round_down(x_, step_);
	return (r == x_ ? r : r+step_);
}

function round_down(x_, step_) {
	// assert type(x_) == int and type(step_) == int
	return (Math.floor(x_/step_)*step_);
}

function round(x_, step_) {
	var rd = round_down(x_, step_)
	var ru = round_up(x_, step_)
	return (x_ - rd < ru - x_ ? rd : ru);
}

function get_paths_from_server() {
	var orig = g_trip_orig_marker.getPosition(), dest = g_trip_dest_marker.getPosition();
	callpy('paths.get_paths_by_latlngs', orig, dest, 
		function(r_) {
			if(SHOW_PATHS_TEXT) {
				set_contents('p_paths_text', sprintf('%.5f, %.5f -> %.5f, %.5f&nbsp;&nbsp;&nbsp;&nbsp;%s', 
					orig.lat(), orig.lng(), dest.lat(), dest.lng(), toJsonString(r_)));
			}
			g_main_path = r_[0];
			g_extra_path_froutendirs = r_[1];
			calc_display_set_and_deal_with_it();
		});
}

// Combines the paths indicated by the trip orig and dest markers with the per-route override settings, 
// and maxroutes/num-extra-routes-to-show. 
// return list of (froute, dir) pairs.  dir will be 0 or 1 except for when we need the server to figure it out, 
// then it will be a pair of latlngs representing orig and dest points (latlngs in raw 2-element array format.) 
function calc_display_set() {
	assert_force_sets_consistent();
	var r = [];

	g_main_path.forEach(function(froutendir) {
		var froute = froutendir[0], dir = froutendir[1];
		if(!g_force_hide_froutes.contains(froute)) {
			if(g_force_dir0_froutes.contains(froute)) {
				dir = 0;
			} else if(g_force_dir1_froutes.contains(froute)) {
				dir = 1;
			}
			r.push([froute, dir]);
		}
	});

	function in_r(froute__) {
		for(var i=0; i<r.length; i++) {
			var froutendir = r[i];
			if(froutendir[0] == froute__) {
				return true;
			}
		}
		return false;
	}

	var extras_added = 0;
	for(var i=0; i<g_extra_path_froutendirs.length; i++) {
		var froutendir = g_extra_path_froutendirs[i];
		var froute = froutendir[0], dir = froutendir[1];
		if(extras_added >= g_num_extra_routes_to_show) {
			break;
		}
		if(!in_r(froute) && !g_force_hide_froutes.contains(froute)) {
			if(g_force_dir0_froutes.contains(froute)) {
				dir = 0;
			} else if(g_force_dir1_froutes.contains(froute)) {
				dir = 1;
			}
			r.push([froute, dir]);
			extras_added += 1;
		}
	}

	g_force_show_froutes.forEach(function(froute) {
		if(!in_r(froute)) {
			var dir = null;
			if(g_force_dir0_froutes.contains(froute)) {
				dir = 0;
			} else if(g_force_dir1_froutes.contains(froute)) {
				dir = 1;
			} else {
				dir = [from_google_LatLng(g_trip_orig_marker.getPosition()), from_google_LatLng(g_trip_dest_marker.getPosition())];
			}
			r.push([froute, dir]);
		}
	});
	return r;
}

function init_num_extra_routes_controls() {
	set_contents('span_num_extra_routes', ''+g_num_extra_routes_to_show);

	$('#down_img').on({'click': on_num_extra_routes_down_clicked});
	$('#up_img').on({'click': on_num_extra_routes_up_clicked});
}

function on_num_extra_routes_down_clicked() {
	if(g_num_extra_routes_to_show > 0) {
		g_num_extra_routes_to_show -= 1;
		set_contents('span_num_extra_routes', ''+g_num_extra_routes_to_show);
		calc_display_set_and_deal_with_it();
	}
}

function on_num_extra_routes_up_clicked() {
	if(g_num_extra_routes_to_show < 99) {
		g_num_extra_routes_to_show += 1;
		set_contents('span_num_extra_routes', ''+g_num_extra_routes_to_show);
		calc_display_set_and_deal_with_it();
	}
}

function calc_display_set_and_deal_with_it() {
	var new_froutendirs = calc_display_set();

	var new_routes = new buckets.LinkedList();
	new_froutendirs.forEach(function(froutendir) {
		new_routes.add(froutendir[0]);
	});

	g_fudgeroute_data.forEach(function(froute, data) {
		if(!new_routes.contains(froute)) {
			forget_data_singleroute(froute);
		}
	});

	new_froutendirs.forEach(function(froutendir) {
		var froute = froutendir[0], dir = froutendir[1];
		if(g_fudgeroute_data.get(froute) == undefined || !dir_equals(g_fudgeroute_data.get(froute).dir, dir)) {
			forget_data_singleroute(froute);
			var data = new_fudgeroute_data();
			data.dir = dir;
			g_fudgeroute_data.set(froute, data);
			if(is_subway(froute)) {
				make_subway_lines(froute);
			} else {
				refresh_data_from_server_singleroute(froute);
				refresh_streetlabels_singleroute(froute);
			}
		}
	});

	refresh_vid_checkboxes_html();
}

function make_subway_lines(froute_) {
	assert(is_subway(froute_), ""+froute_+" is not a subway");

	var data = g_fudgeroute_data.get(froute_);
	var latlngs = SUBWAY_FROUTE_TO_DATAZOOM_TO_ROUTEPTS[froute_][GUIZOOM_TO_DATAZOOM[g_map.getZoom()]];
	var width = get_traffic_line_width()*1.5;
	var line = new google.maps.Polyline({map: g_map, path: google_LatLngs(latlngs), strokeWeight: width, strokeOpacity: 0.5, 
			strokeColor: 'rgb(0,0,255)', zIndex: -30, visible: g_show_traffic_lines, clickable: false}); 
	data.traffic_lines.add(line);
}

function set_play_buttons_appropriately() {
	$('#playpause_button').prop('value', (g_playing ? 'Pause' : 'Play'));
	$('#back_button').prop('disabled', g_playing);
	$('#forward_button').prop('disabled', g_playing);
}

function on_playpause_clicked() {
	g_playing = !g_playing;
	set_play_buttons_appropriately();
	if(g_playing) { // go from paused to playing: 
		schedule_refresh_data_from_server();
	} else { // go from playing to paused: 
		if(g_times.size() > 0) {
			if(g_cur_minute_idx > g_times.size()-1) {
				g_cur_minute_idx = g_times.size()-1;
			}
			show_cur_minute_vehicles_allroutes();
			update_clock_show_cur_minute();
		}
	}
}

function show_cur_minute_vehicles_allroutes() {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		show_cur_minute_vehicles_singleroute(fudgeroute);
	});
}

function show_cur_minute_vehicles_singleroute(fudgeroute_) {
	set_all_static_vehicle_markers_visible_singleroute(fudgeroute_, g_show_static_vehicles);

	var data = g_fudgeroute_data.get(fudgeroute_);
	// TODO: could optimize this I think - hide only previous frame. 
	data.vid_to_heading_to_moving_vehicle_marker.forEach(function(vid, heading_to_marker) {
		heading_to_marker.forEach(function(heading, marker) {
			if(!TEST_INVISIBLE) {
				marker.setVisible(false);
			}
		});
	});
	var time_to_vid_to_vi = data.datazoom_to_time_to_vid_to_vi.get(data.vehicles_datazoom);
	if(time_to_vid_to_vi != undefined) {
		var vid_to_vi = time_to_vid_to_vi.get(g_times.elementAtIndex(g_cur_minute_idx));
		if(vid_to_vi != undefined) {
			vid_to_vi.forEach(function(vid, vi) {
				if(!g_hidden_vids.contains(vid)) {
					var marker = data.vid_to_heading_to_moving_vehicle_marker.get(vid).get(round_heading(vi.heading));
					marker.setPosition(google_LatLng([vi.lat, vi.lon]));
					if(!TEST_INVISIBLE) {
						if(g_show_moving_vehicles) {
							marker.setVisible(true);
						}
					}
				}
			});
		}
	}
}

function on_forward_clicked() {
	if(g_times.size() == 0) {
		return;
	}
	g_cur_minute_idx = Math.min(g_cur_minute_idx+1, g_times.size()-1);
	update_clock_show_cur_minute();
	show_cur_minute_vehicles_allroutes();
}

function on_back_clicked() {
	if(g_times.size() == 0) {
		return;
	}
	g_cur_minute_idx = Math.max(g_cur_minute_idx-1, 0);
	update_clock_show_cur_minute();
	show_cur_minute_vehicles_allroutes();
}

function is_traffictype_current() {
	return (radio_val('traffictype') == 'current');
}

function is_traffictype_historical() {
	return !is_traffictype_current();
}

function init_datetimepicker() {
	set_value('datetimepicker_textfield', HISTORICAL_TIME_DEFAULT);
	$('#datetimepicker_textfield').datetimepicker({
		dateFormat: 'yy-mm-dd', 
		onSelect: function(dateText, inst) { 
			on_datetime_changed();
		}
	});
	update_datetimepicker_enabledness();
}

function on_traffictype_changed() {
	update_datetimepicker_enabledness();
	stop_refresh_data_from_server_timer();
	forget_data_allroutes();
	update_g_times();
	calc_display_set_and_deal_with_it();
	if(is_traffictype_current()) {
		schedule_refresh_data_from_server();
	}
}

function schedule_refresh_data_from_server() {
	g_refresh_data_from_server_timer = setTimeout('refresh_data_from_server_timer_func()', REFRESH_INTERVAL_MS);
}

function update_datetimepicker_enabledness() {
	if(SHOW_DEV_CONTROLS) {
		$('#datetimepicker_textfield').prop('disabled', is_traffictype_current());
	}
}

function substr_int(str_, startidx_, len_) {
	return parseInt(str_.substr(startidx_, len_), 10);
}

// Returns either 0 (an integer) or a string (in yyyy-MM-dd HH:MM format).   Our server functions can handle both. 
function get_datetime_from_gui() {
	if(SHOW_DEV_CONTROLS) {
		return (is_traffictype_current() ? 0 : get_value('datetimepicker_textfield'));
	} else {
		return 0;
	}
}

function stop_refresh_data_from_server_timer() {
	if(g_refresh_data_from_server_timer != null) {
		clearTimeout(g_refresh_data_from_server_timer);
		g_refresh_data_from_server_timer = null;
	}
}

function forget_data_allroutes() {
	g_fudgeroute_data.forEach(function(fudgeroute, data) {
		forget_data_singleroute(fudgeroute);
	});
}

function forget_data_singleroute(fudgeroute_) {
	var data = g_fudgeroute_data.get(fudgeroute_);
	if(data != undefined) {
		if(data.traffic_lines != null) {
			data.traffic_lines.forEach(function(line) {
				line.setMap(null);
			});
		}
		if(data.vid_to_static_vehicle_marker != null) {
			data.vid_to_static_vehicle_marker.forEach(function(vid, marker) {
				marker.setMap(null);
			});
		}
		if(data.vid_to_heading_to_moving_vehicle_marker != null) {
			data.vid_to_heading_to_moving_vehicle_marker.forEach(function(vid, heading_to_moving_vehicle_marker) {
				heading_to_moving_vehicle_marker.forEach(function(heading, marker) {
					marker.setMap(null);
				});
			});
		}
		data.streetlabel_markers.forEach(function(e) {
			e.setMap(null);
		});
		g_fudgeroute_data.remove(fudgeroute_);
	}
}

function on_datetime_changed() {
	on_traffictype_changed();
}

function get_traffic_line_width() {
	return get_traffic_line_width_by_guizoom(g_map.getZoom());
}

function get_traffic_line_width_by_guizoom(zoom_) {
	if(0 <= zoom_ && zoom_ < g_guizoom_to_traffic_line_width.length) {
		return g_guizoom_to_traffic_line_width[zoom_];
	} else {
		return g_guizoom_to_traffic_line_width[g_guizoom_to_traffic_line_width.length];
	}
}

// kmph_ == null ==> no data available. 
// return: Either one or two two-point Polylines.  second one, if present, will be a background line, for the purpose of outlining.
// 		both lines will have the same start- and end-position. 
function make_traffic_line(froute_, start_latlon_, end_latlon_, kmph_, mofr_) {
	var r = new buckets.LinkedList();
	var draw_outline = traffic_line_warrants_outline(kmph_);
	var line = new google.maps.Polyline({
		path: [google_LatLng(start_latlon_), google_LatLng(end_latlon_)], 
		map: g_map, 
		strokeColor: kmph_to_color(kmph_), 
		strokeWeight: (draw_outline ? get_traffic_line_width()-1 : get_traffic_line_width()),  
		zIndex: get_traffic_line_zindex(froute_, false), 
		visible: g_show_traffic_lines, 
		clickable: false
	});
	r.add(line);
	if(draw_outline) {
		var line_behind = new google.maps.Polyline({
			path: [google_LatLng(start_latlon_), google_LatLng(end_latlon_)], 
			map: g_map, 
			strokeColor: get_outline_color(kmph_), 
			strokeWeight: get_traffic_line_width(), 
			zIndex: get_traffic_line_zindex(froute_, true),
			visible: g_show_traffic_lines, 
			clickable: false
		});
		r.add(line_behind);
	}

	/*
	var infowin_text = sprintf("The average speed here, in this direction, is %s.", 
			(kmph_==null ? 'not available' : sprintf('%.1f kmph', kmph_)));
	add_mouseover_infowin(line, 0, infowin_text);
	*/

	return r;
}

function get_outline_color(kmph_) {
	if(kmph_==null) {
		return 'rgb(150,150,150)';
	} else {
		var main_line_color = kmph_to_color_ints(kmph_);
		var ratio = 0.75;
		var r = [0, 0, 0];
		r[0] = avg(0, main_line_color[0], ratio);
		r[1] = avg(0, main_line_color[1], ratio);
		r[2] = avg(0, main_line_color[2], ratio);
		return sprintf('rgb(%d,%d,%d)', r[0], r[1], r[2]);
	}
}

function traffic_line_warrants_outline(kmph_) {
	return (kmph_==null) || (13 <= kmph_ && kmph_ <= 17);
}

function get_traffic_line_zindex(froute_, outline_) {
	// Here we give foreground outlines (i.e. coloured lines) even zindexes eg. 
	// queen = -2, lansdowne = -4, or something like that, and 
	// outlines odd zindexes one less eg. queen = -3, lansdowne = -4.  
	var idx = g_froute_zindexes.indexOf(froute_);
	idx -= g_froute_zindexes.length;
	idx *= 2;
	if(outline_) {
		idx -= 1;
	}
	return idx;
}

function on_show_static_vehicles_checkbox_clicked() {
	g_show_static_vehicles = is_selected('show_static_vehicles_checkbox');
	g_fudgeroute_data.forEach(function(froute, data) {
		data.vid_to_static_vehicle_marker.forEach(function(vid, marker) {
			marker.setVisible(g_show_static_vehicles);
		});
	});
}

function on_show_moving_vehicles_checkbox_clicked() {
	g_show_moving_vehicles = is_selected('show_moving_vehicles_checkbox');
	set_visible('animation_controls_div', g_show_moving_vehicles);
	update_clock_show_cur_minute();
	show_cur_minute_vehicles_allroutes();
}

function on_show_traffic_lines_checkbox_clicked() {
	g_show_traffic_lines = is_selected('show_traffic_lines_checkbox');
	g_fudgeroute_data.forEach(function(froute, data) {
		data.traffic_lines.forEach(function(line) {
			line.setVisible(g_show_traffic_lines);
		});
		data.streetlabel_markers.forEach(function(line) {
			line.setVisible(g_show_traffic_lines);
		});
	});
}

function is_a_streetcar(vid_) {
	// At least, I think that starting w/ 4 means streetcar.  This logic is also implemented in vinfo.py. 
	return vid_.charAt(0) == '4';
}

function set_vehicle_checkbox_imgs_appropriately() {
	var icontypestr = (g_use_rendered_aot_arrow_vehicle_icons ? 'rendered' : 'arrow');
	$("#static_vehicle_legend_img").attr('src', sprintf('static-vehicle-%s-for-legend.png', icontypestr));
	$("#moving_vehicle_legend_img").attr('src', sprintf('moving-vehicle-%s-for-legend.png', icontypestr));
}

function on_rendered_aot_arrow_vehicle_icons_button_clicked() {
	g_use_rendered_aot_arrow_vehicle_icons = (radio_val('vehicleicontype') == 'rendered');
	set_vehicle_checkbox_imgs_appropriately();
	remake_all_vehicle_markers();
}

function init_rendered_aot_arrow_vehicle_icons_buttons() {
	set_selected((g_use_rendered_aot_arrow_vehicle_icons ? 'rendered_button' : 'arrow_button'), true);
	set_vehicle_checkbox_imgs_appropriately();
}



$(document).ready(initialize);

    </script>

		<!-- SVG clock from https://gist.github.com/1188550 --> 
    <style>
      /* These CSS styles all apply to the SVG elements defined below */
      #svg_clock {
        /* styles for everything in the clock */
        stroke: black;
        /* black lines */
        stroke-linecap: round;
        /* with rounded ends */
        fill: #eef;
        /* on a light blue gray background */
      }
      #face { stroke-width: 3px;}
      /* clock face outline */
      #ticks { stroke-width: 2; }
      /* lines that mark each hour */
      #hourhand {stroke-width: 5px;}
      /* wide hour hand */
      #minutehand {stroke-width: 3px;} /* narrow minute hand */
      #secondhand {stroke-width: 1px;}
      #numbers {
        /* how to draw the numbers */
        font-family: sans-serif; font-size: 7pt; font-weight: bold;
        text-anchor: middle; stroke: none; fill: black;
      }
    </style>
  </head>
  <body>
		<div id="map_wrapper">
			<div id="map_canvas" style="width:100%; height:100%"></div>
			<div id="div_clock" style="position: absolute; background-color: transparent; top: 30px; right: 2px; z-index: 99; ">
				<svg id="svg_clock" viewBox="0 0 100 100" width="50" height="50">
					<!-- SVG clock from https://gist.github.com/1188550 --> 
					<circle id="face" cx="50" cy="50" r="45"/> <!-- the clock face -->
					<g id="ticks">
						<!-- 12 hour tick marks -->
						<line x1='50' y1='5.000' x2='50.00' y2='10.00'/> <line x1='72.50' y1='11.03' x2='70.00' y2='15.36'/> <line x1='88.97' y1='27.50' x2='84.64' y2='30.00'/> <line x1='95.00' y1='50.00' x2='90.00' y2='50.00'/> <line x1='88.97' y1='72.50' x2='84.64' y2='70.00'/> <line x1='72.50' y1='88.97' x2='70.00' y2='84.64'/> <line x1='50.00' y1='95.00' x2='50.00' y2='90.00'/> <line x1='27.50' y1='88.97' x2='30.00' y2='84.64'/> <line x1='11.03' y1='72.50' x2='15.36' y2='70.00'/> <line x1='5.000' y1='50.00' x2='10.00' y2='50.00'/> <line x1='11.03' y1='27.50' x2='15.36' y2='30.00'/> <line x1='27.50' y1='11.03' x2='30.00' y2='15.36'/>
					</g>
					<g id="numbers">
						<!-- Number the cardinal directions-->
						<text x="50" y="18">12</text><text x="85" y="53">3</text> <text x="50" y="88">6</text><text x="15" y="53">9</text>
					</g>
					<!-- Draw hands pointing straight up. We rotate them in the code. -->
					<g id="hands"> <!-- Add shadows to the hands -->
						<line id="hourhand" x1="50" y1="50" x2="50" y2="24"/> <line id="minutehand" x1="50" y1="50" x2="50" y2="20"/>
						<!--<line id="secondhand" x1="50" y1="50" x2="50" y2="16"/>-->
					</g>
				</svg> <br/>
			</div>
			<div id="div_loading_img" style="position: absolute; background-color: transparent; top: 0px; left: 0px; z-index: 99;">
				<img id="loading_img" src="loading.gif" style="visibility:hidden"/>
			</div>
		</div>
		<div>
			<p id="p_zoom"/>
			<p id="p_paths_text"/>
			<p id="p_loading_urls"/>
			<div id="div_framerate">
				<br/><p id='p_framerate'/>
				<br/><p id='p_worktime'/>
			</div>
			<!-- Layers: -->
			<input type="checkbox" id="show_static_vehicles_checkbox" checked="checked" 
				onclick="on_show_static_vehicles_checkbox_clicked()"                  title="Show/Hide layer: current vehicle locations (stationary icons)"/>
			<label for="show_static_vehicles_checkbox" onclick=""> 
			<img id="static_vehicle_legend_img" src="static-vehicle-arrow-for-legend.png" title="Show/Hide layer: current vehicle locations (stationary icons)"/> 
			</label> 
&nbsp;&nbsp;
			<input type="checkbox" id="show_moving_vehicles_checkbox" checked="checked" 
				onclick="on_show_moving_vehicles_checkbox_clicked()"                  title="Show/Hide layer: past 30 minutes of vehicle locations (animated icons)"/>
			<label for="show_moving_vehicles_checkbox" onclick=""> 
			<img id="moving_vehicle_legend_img" src="moving-vehicle-arrow-for-legend.png" title="Show/Hide layer: past 30 minutes of vehicle locations (animated icons)"/> 
			</label> 
&nbsp;&nbsp;
			<input type="checkbox" id="show_traffic_lines_checkbox" checked="checked" 
				onclick="on_show_traffic_lines_checkbox_clicked()"       title="Show/Hide layer: recent traffic speed (coloured lines)"/>
			<label for="show_traffic_lines_checkbox" onclick=""> 
			<img src="traffic-color-legend.gif" style="float: bottom;" title="Show/Hide layer: recent traffic speed (coloured lines)"/>
			                                    <!-- ^^^ I don't know why that style/float is there. -->
			</label> 
			<hr style="border-top:1px solid #ccc" />

			<!-- Rendered vs. arrow icons: -->
			<input id="rendered_button" type="radio" name="vehicleicontype" value="rendered" 
				onclick="on_rendered_aot_arrow_vehicle_icons_button_clicked()" 
																	 title="Use streetcar and bus icons" />
			<label for="rendered_button" title="Use streetcar and bus icons"><img src="static-vehicle-rendered-for-legend.png"/></label>
&nbsp;/
			<input id="arrow_button" type="radio" name="vehicleicontype" value="arrow" 
				onclick="on_rendered_aot_arrow_vehicle_icons_button_clicked()" 
																title="Use arrow icons" />
			<label for="arrow_button" title="Use arrow icons"><img src="static-vehicle-arrow-for-legend.png"/></label>
			<hr style="border-top:1px solid #ccc" />

			<!-- Num extra routes: -->
			Max. extra routes to show: <font size="+1"><span id="span_num_extra_routes"></span></font>  
			<img id="down_img" src="down.png"/> <img id="up_img" src="up.png"/> <br/>
			<hr style="border-top:1px solid #ccc" />

			<!-- Play / pause: -->
			<div id="animation_controls_div">
				Vehicle animation: 
				<input type="button" id="playpause_button" onclick="on_playpause_clicked()" value="" />
				<input type="button" id="back_button" onclick="on_back_clicked()" value="<" />
				<input type="button" id="forward_button" onclick="on_forward_clicked()" value=">" />
			</div>

			<div id="div_dev_controls">
				<hr style="border-top:1px solid #ccc" />
				<div>
					<font size="-1">
					<p>Details:</p>
					<p id="p_vid_checkboxes">&nbsp;</p>
					</font>

					<input id="current_button" type="radio" name="traffictype" value="current"    onclick="on_traffictype_changed()"  checked="checked"  />
					<label for="current_button">Now</label>
					<input id="historical_button" type="radio" name="traffictype" value="historical" onclick="on_traffictype_changed()" />
					<label for="historical_button">Past</label>
					<input id="datetimepicker_textfield" type="text" name="datetimepicker_textfield" value="" />
				</div>
			</div>
		<div style="clear: both">
			<hr style="border-top:1px solid #ccc" />
			<p><a href="about.html">About this website.</a></p>
			<p></p>
		</div>
		<div id="route-options-dialog"><div>
		<div id="route-select-dialog"><div>
		<div id="message-dialog"><div>
  </body>
</html>
