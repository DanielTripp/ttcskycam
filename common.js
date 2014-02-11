var g_map;

// From http://stackoverflow.com/questions/7616461/generate-a-hash-from-string-in-javascript-jquery 
function hashCode(str_) {
    var r = 0;
    if (str_.length == 0) return r;
    for (i = 0; i < str_.length; i++) {
        char = str_.charCodeAt(i);
        r = ((r<<5)-r)+char;
        r = r & r; // Convert to 32bit integer
    }
    return r;
}

eval(get_sync("sprintf.js"));
eval(get_sync("js/buckets-minified.js"));

var g_loading_urls = null;

function add_to_loading_urls(url_) {
	if(g_loading_urls == null) {
		g_loading_urls = new buckets.LinkedList();
		// Caching this error image in advance so that if the user, on their phone, loads the page while they have reception 
		// (which will usually be the case) then they lose reception, our error icon will appear.  Otherwise a browser-specific 
		// broken image icon would probably appear. 
		(new Image(25, 25)).src = 'error.png';
	}
	g_loading_urls.add(url_)
	if(g_loading_urls.size() == 1) {
		var img = document.getElementById('loading_img');
		if(img != null) {
			img.src = 'loading.gif';
			img.style.visibility = 'visible';
		}
	}
	update_p_loading_urls();
}

function update_p_loading_urls() {
	var p_loading_urls = document.getElementById('p_loading_urls');
	if(p_loading_urls != null) {
		var html = "";
		if(g_loading_urls != null) {
			g_loading_urls.forEach(function(url) {
				html += url+"<br>";
			});
		}
		p_loading_urls.innerHTML = html;
	}
}

function remove_from_loading_urls(url_, success_) {
	var was_removed = g_loading_urls.remove(url_);
	assert(was_removed, "url "+url_+" not found in list.");
	if(g_loading_urls.size() == 0) {
		var img = document.getElementById('loading_img');
		if(img != null) {
			if(success_) {
				img.style.visibility = 'hidden';
			} else {
				img.src = 'error.png';
			}
		}
	}
	update_p_loading_urls();
}

g_page_is_unloading = false;
$(window).unload(function() { g_page_is_unloading = true; });

// funcs_arg_ can be a single callable (success function) or an object with 'success' and/or 'error' members. 
function get(url_, funcs_arg_) {
	add_to_loading_urls(url_);
	var success_func = funcs_arg_.success, error_func = funcs_arg_.error;
	if(success_func == undefined && error_func == undefined) {
		success_func = funcs_arg_;
	}
	$.ajax({url:url_, async:true, 
		error: function(jqXHR_, textStatus_, errorThrown_) {
			if(g_page_is_unloading) {
				return;
			}
			remove_from_loading_urls(url_, false);
			if(error_func != undefined) {
				error_func();
			}
		}, 
		success: function(data_, textStatus_, jqXHR_) {
			remove_from_loading_urls(url_, true);
			success_func($.parseJSON(data_));
		}
	});
}

function dict_union(dict1_, dict2_) {
	r = {}
	for(var i in dict1_) {
		r[i] = dict1_[i];
	}
	for(var i in dict2_) {
		r[i] = dict2_[i];
	}
	return r;
}

function get_sync(url_, additional_options_) {
	var error = false;
	var options = {url:url_, async:false, 
			error: function(jqXHR_, textStatus_, errorThrown_) {
				if(g_page_is_unloading) {
					return;
				}
				alert("get_sync('"+url_+"') error - "+errorThrown_);
				error = true;
			}
		};
	if(additional_options_ != undefined) {
		options = dict_union(options, additional_options_);
	}
	var jqXHR = $.ajax(options);
	if(error) {
		return null;
	} else {
		return jqXHR.responseText;
	}
}

function get_v1(url_) {
	var xmlhttp = new XMLHttpRequest();
	xmlhttp.open("GET", url_, false);
	xmlhttp.send();
	return xmlhttp.responseText;
}

function int_to_rgbstr(int_) {
	var n = int_ % 6;
	var r = '(0,0,0)';
	if(n == 0) {
		r = '255,0,0';
	} else if(n == 1) {
		r = '0,255,0';
	} else if(n == 2) {
		r = '0,0,255';
	} else if(n == 3) {
		r = '255,255,0';
	} else if(n == 4) {
		r = '0,255,255';
	} else if(n == 5) {
		r = '255,0,255';
	}
	return 'rgb('+r+')';
}
	
function init_map() {
	var myOptions = {
		center: new google.maps.LatLng(43.65431690357294, -79.40920715332034),
		zoom: 14,
		scaleControl: true, 
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};
	g_map = new google.maps.Map(document.getElementById("map_canvas"),
			myOptions);
	var bounds = new google.maps.LatLngBounds(new google.maps.LatLng(43.64280759826894, -79.47029872139592), 
			new google.maps.LatLng(43.666964279902764, -79.34704585274358));
	// The line below seemed not to work on iPhone and even worse, it broke everything too (no data, routes, or 
	// start / destination markers shown).   
	//g_map.fitBounds(bounds);
}

function set_contents(id_, contents_) {
	var dom_elem = document.getElementById(id_);
	assert(dom_elem!=null, 'dom elem "'+id_+'" is null');
	dom_elem.innerHTML = contents_;
}

function get_contents(id_) {
	var dom_elem = document.getElementById(id_);
	return dom_elem.innerHTML;
}

function radio_val(groupname_) {
	return $('input[name='+groupname_+']:checked').val();
}

function get_value(textfieldname_) {
	return $("#"+textfieldname_).val();
}

function set_value(textfieldname_, value_) {
	return $("#"+textfieldname_).val(value_);
}

function is_selected(checkboxname_) {
	return $('#'+checkboxname_).is(":checked");
}

function set_selected(checkboxname_, selected_) {
	return $('#'+checkboxname_).prop('checked', selected_);
}

function set_visible(objectid_, visible_) {
	document.getElementById(objectid_).style.visibility = (visible_ ? 'visible' : 'hidden');
}

function ord(char_) {
	return char_.charCodeAt(0);
}

function chr(intval_) {
	return String.fromCharCode(intval_);
}

function get_range_val(x1_, y1_, x2_, y2_, domain_val_) {
	return (y2_ - y1_)*(domain_val_ - x1_)/(x2_ - x1_) + y1_;
}

function google_LatLng(latlon_) {
	return new google.maps.LatLng(latlon_[0], latlon_[1]);
}

function from_google_LatLng(glatlng_) {
	return [glatlng_.lat(), glatlng_.lng()];
}

// arg: array of float pairs representing latlngs. 
function google_LatLngs(latlngs_) {
	var r = [];
	latlngs_.forEach(function(latlng) {
		r.push(google_LatLng(latlng));
	});
	return r;
}

function to_google_LatLng_polylines(raw_polylines_) {
	var r = [];
	raw_polylines_.forEach(function(raw_polyline) {
		r.push(google_LatLngs(raw_polyline));
	});
	return r;
}

function callpy(module_and_funcname_) {
	var func_args = new Array();
	for(var i=1; i<arguments.length-1; i++) {
		func_args.push(arguments[i]);
	}
	var url = callpy_url(module_and_funcname_, func_args);
	var funcs_arg = arguments[arguments.length-1];
	get(url, funcs_arg);
}

function callpy_sync(module_and_funcname_) {
	var func_args = new Array();
	for(var i=1; i<arguments.length; i++) {
		func_args.push(arguments[i]);
	}
	var url = callpy_url(module_and_funcname_, func_args);
	return $.parseJSON(get_sync(url));
}

function callpy_url(module_and_funcname_, func_args_) {
	var paramstr = "module_and_funcname="+module_and_funcname_;
	for(var i=0; i<func_args_.length; i++) {
		var argval = func_args_[i];
		if(argval instanceof google.maps.LatLng) {
			argval = [argval.lat(), argval.lng()];
		} else if(argval instanceof buckets.LinkedList) {
			new_argval = [];
			argval.forEach(function(e) {
				new_argval.push(e);
			});
			argval = new_argval;
		} else if($.isArray(argval) && argval.length > 0 && argval[0] instanceof google.maps.LatLng) {
			argval = argval.map(function(e) { return [e.lat(), e.lng()]; });
		}
		var argval_json = window.JSON.stringify(argval);
		paramstr += "&arg"+i+"="+encode_url_paramval(argval_json);
	}
	return "callpy.wsgi?"+paramstr;
}

function toJsonString(obj_, indent_) {
	return window.JSON.stringify(obj_, undefined, (indent_ ? 2 : 0));
}

function cgi_url(cgi_path_, func_args_) {
	var paramstr = "";
	for(var i=0; i<func_args_.length; i++) {
		paramstr += (i==0 ? "?" : "&") + "arg"+i+"="+func_args_[i];
	}
	return cgi_path_+paramstr;
}

function AssertException(message) { this.message = message; }
AssertException.prototype.toString = function () {
	if(this.message != undefined) {
  	return 'AssertException: ' + this.message;
	} else {
  	return 'AssertException';
	}
}

function assert(exp, message) {
  if (!exp) {
    throw new AssertException(message);
  }
}

// For scrambling strings so that they don't look to apache ModSecurity like SQL injection attacks.  
// See counterpart at misc.py - decode_sql_str().  
function encode_url_paramval(str_) {
  var r = '';
  for(var i=0; i<str_.length; i++) {
    var ordval = ord(str_.charAt(i));
    var group = Math.floor(ordval / 10);
    var sub = ordval - (group*10);
    var groupchar = chr(ord('a') + group);
    r += groupchar + sub;
  }
  return r;
}

function vi_to_str(vi_) {
	var dir_tag;
	if(vi_.dir_tag == null) {
		dir_tag = '(null)';
	} else if(vi_.dir_tag.length == 0) {
		dir_tag = '(blank)';
	} else {
		dir_tag = "'"+vi_.dir_tag+"'";
	}
	return sprintf('%s  route: %4s, vehicle: %s, dir: %-12s, (  %2.5f, %2.5f  ) , mofr: %d, heading: %3d %s', 
			vi_.timestr, vi_.route_tag, vi_.vehicle_id, dir_tag, vi_.lat, vi_.lon, vi_.mofr, vi_.heading, 
				(vi_.predictable ? '' : 'UNPREDICTABLE'));
}

function avg(lo_, hi_, ratio_) {
  return (lo_ + (hi_ - lo_)*ratio_);
}

var g_temp_infowin = null;

function show_temp_infowin(text_) {
	close_temp_infowin();
	var top = g_map.getBounds().getNorthEast().lat(), bottom = g_map.getBounds().getSouthWest().lat();
	var pos = new google.maps.LatLng(avg(bottom, top, 0.1), g_map.getCenter().lng());
	g_temp_infowin = new google.maps.InfoWindow({content: text_, position: pos, disableAutoPan: true});
	g_temp_infowin.open(g_map);
	setTimeout("close_temp_infowin()", 3000);
}

function close_temp_infowin() {
	if(g_temp_infowin != null) {
		g_temp_infowin.close();
		g_temp_infowin = null;
	}
}

function add_all(dest_list_, src_list_) {
	src_list_.forEach(function(e) {
		dest_list_.add(e);
	});
}

function to_buckets_list(array_, reverse_) {
	var reverse = false;
	if(reverse_ != undefined) {
		reverse = reverse_;
	}
	var r = new buckets.LinkedList();
	if(reverse) {
		for(var i=array_.length-1; i>=0; i--) {
			r.add(array_[i]);
		}
	} else {
		for(var i=0; i<array_.length; i++) {
			r.add(array_[i]);
		}
	}
	return r;
}

function to_buckets_set(array_) {
	var r = new buckets.Set();
	array_.forEach(function(e) {
		r.add(e);
	});
	return r;
}

function to_buckets_dict(dict_) {
	var r = new buckets.Dictionary();
	for(var key in dict_) {
		var value = dict_[key];
		r.set(key, value);
	}
	return r;
}

function buckets_set_to_string(s_) {
	var r = "(";
	s_.forEach(function(e) {
		r += sprintf("%s", e);
		r += ", ";
	});
	r += ")";
	return r;
}

function buckets_list_to_string(l_) {
	var r = "[";
	for(var i=0; i<l_.size(); i++) {
		r += sprintf("%s", l_.elementAtIndex(i));
		if(i != l_.size()-1) {
			r += ", ";
		}
	}
	r += "]";
	return r;
}

function buckets_set_to_list(set_) {
	var r = new buckets.LinkedList();
	set_.forEach(function(e) {
		r.add(e);
	});
	return r;
}

function sort_buckets_list(l_) {
	var temp = [];
	l_.forEach(function(e) {
		temp.push(e);
	});
	l_.clear();
	temp.sort();
	temp.forEach(function(e) {
		l_.add(e);
	});
}

function add_delayed_event_listener(listenee_, eventname_, real_listener_func_, delay_millis_) {
	var timeout = null;

	function delaying_listener() {
		if(timeout != null) {
			clearTimeout(timeout);
			timeout = null;
		}
		timeout = setTimeout(real_listener_func_, delay_millis_);
	}

	return google.maps.event.addListener(listenee_, eventname_, delaying_listener);
}

var g_hover_listener_listenee_objectid_to_mapobjects = new buckets.Dictionary();

// listener_func_ can return something that we can all close() or setMap(null) on, or an array of same. 
// delay_millis_ - we will use this for the delay in both calling listener_func_, and calling close() on the
// 		object that it returns.
function add_hover_listener(listenee_, listener_func_, delay_millis_) {
	google.maps.event.addListener(listenee_, 'mouseover', function(mouseevent__) { 
		hover_listener_close_objects(listenee_);
		g_hover_listener_listenee_objectid_to_mapobjects.set(object_id(listenee_), null);
		setTimeout(function() {
			if(g_hover_listener_listenee_objectid_to_mapobjects.containsKey(object_id(listenee_))) {
				var mapobject_or_mapobjects = listener_func_(mouseevent__.latLng);
				if(mapobject_or_mapobjects != null) {
					var mapobjects = [];
					if(mapobject_or_mapobjects.close != undefined || mapobject_or_mapobjects.setMap != undefined) {
						mapobjects.push(mapobject_or_mapobjects);
					} else {
						mapobjects = mapobject_or_mapobjects;
					}
					g_hover_listener_listenee_objectid_to_mapobjects.set(object_id(listenee_), mapobjects);
				}
			}
		}, delay_millis_);
	});
	google.maps.event.addListener(listenee_, 'mouseout', function() { 
		setTimeout(function() { hover_listener_close_objects(listenee_); }, delay_millis_);
	});
}

function hover_listener_close_objects(listenee_) {
	var mapobjects = g_hover_listener_listenee_objectid_to_mapobjects.get(object_id(listenee_));
	g_hover_listener_listenee_objectid_to_mapobjects.remove(object_id(listenee_));
	if(mapobjects != null) {
		mapobjects.forEach(function(mapobject) {
			if(mapobject.close != undefined) {
				mapobject.close();
			} else {
				mapobject.setMap(null);
			}
		});
	}
}

var g_next_objid = 1;

// adapted from http://stackoverflow.com/questions/2020670/javascript-object-id 
function object_id(obj_) {
    if(obj_==null) {
			return null;
		}
    if(obj_.__obj_id==undefined) {
			obj_.__obj_id = g_next_objid++;
		}
    return obj_.__obj_id;
}

// adapted from http://ejohn.org/blog/javascript-array-remove/ 
function array_remove(array_, from_, to_) {
	var rest = array_.slice((to_ || from_) + 1 || array_.length);
	array_.length = from_ < 0 ? array_.length + from_ : from_;
	return array_.push.apply(array_, rest);
};

function array_indexof_identity(array_, object_) {
	for(var i=0; i<array_.length; i++) {
		if(array_[i] === object_) {
			return i;
		}
	}
	return -1;
}

function sorted_keys(dict_) {
    var keys = [];
    for(var key in dict_) {
        if(dict_.hasOwnProperty(key)) {
            keys.push(key);
        }
    }
    return keys.sort();
}

function draw_polygon(filename_) {
	var glatlngs = [];
	var raw_latlngs = $.parseJSON(get_sync(filename_));
	raw_latlngs.forEach(function(raw_latlng) {
		glatlngs.push(google_LatLng(raw_latlng));
	});
	glatlngs.push(google_LatLng(raw_latlngs[0]));
	new google.maps.Polyline({map: g_map, path: glatlngs, strokeColor: 'rgb(255,0,0)'});
}

function shallow_clone_set(set_) {
	var r = new buckets.Set();
	set_.forEach(function(e) {
		r.add(e);
	});
	return r;
}

// buckets.Set's own intersection method modified the 'this' object.  This method doesn't. 
function intersection(set1_, set2_) {
	var set1_clone = shallow_clone_set(set1_);
	set1_clone.intersection(set2_);
	return set1_clone;
}


function radians(degrees_) {
	return degrees_*Math.PI/180.0;
}

// Both arguments need to be a google.maps.LatLng, or anything with 'lat' and 'lng' members (either callable or not). 
function dist_m(pt1_, pt2_) {
	var RADIUS_OF_EARTH = 6367.44465;
	var pt1, pt2;
	if(typeof(pt1_.lat) === 'function') {
		pt1 = [pt1_.lat(), pt1_.lng()];
		pt2 = [pt2_.lat(), pt2_.lng()];
	} else {
		pt1 = [pt1_.lat, pt1_.lng];
		pt2 = [pt2_.lat, pt2_.lng];
	}
	var lat1 = radians(pt1[0]), lng1 = radians(pt1[1]);
	var lat2 = radians(pt2[0]), lng2 = radians(pt2[1]);
	// 'Haversine formula' from http://en.wikipedia.org/wiki/Great-circle_distance
	var dlat = lat2 - lat1;
	var dlng = lng2 - lng1;
	var central_angle = 2*Math.asin(Math.sqrt(Math.pow(Math.sin(dlat/2), 2) + Math.cos(lat1)*Math.cos(lat2)*(Math.pow(Math.sin(dlng/2), 2))));
	return central_angle*RADIUS_OF_EARTH*1000.0;
}

function dist_m_polyline(pts_) {
	var r = 0.0;
	for(var i=0; i<pts_.length-1; i++) {
		r += dist_m(pts_[i], pts_[i+1]);
	}
	return r;
}

function fdiv(x_, y_) {
	return Math.floor(x_/y_);
}

// Thanks to http://stackoverflow.com/questions/3885817/how-to-check-if-a-number-is-float-or-integer 
function isInt(n) {
	return typeof n === 'number' && n % 1 == 0;
}

function inii(lower_, x_, upper_) {
	return (lower_ <= x_ && x_ <= upper_);
}

function inie(lower_, x_, upper_) {
	return (lower_ <= x_ && x_ < upper_);
}

// Returns a list like python's 'range' except this will return something regardless of the order the arguments are in. 
function intervalii(a_, b_) {
	var r = [];
  if(a_ < b_) {
		for(var i=a_; i<=b_; i++) {
			r.push(i);
		}
  } else {
		for(var i=a_; i>=b_; i--) {
			r.push(i);
		}
	}
	return r;
}

function arrayMin(array_) {
	return Math.min.apply(Math, array_);
}

function arrayMax(array_) {
	return Math.max.apply(Math, array_);
}

function roundDown(x_, step_, ref_) {
	var ref = (typeof ref_ === 'undefined' ? 0 : ref_);
	return fdiv(x_-ref, step_)*step_ + ref;
}

function roundUp(x_, step_, ref_) {
	var r = roundDown(x_, step_, ref_);
	return (r == x_ ? r : r+step_);
}

function make_polyline_arrow_icons(zoom_, latlngs_) {
	var arrowSymbol = { path: google.maps.SymbolPath.FORWARD_OPEN_ARROW };
	var metersPerArrow = 10*Math.pow(1.8, 21-zoom_);
	var plineLengthMeters = dist_m_polyline(latlngs_);
	var percentBetweenArrows = 100.0*metersPerArrow/plineLengthMeters;
	var r = [];
	var curPercent = percentBetweenArrows/4;
	while(curPercent <= 100.0) {
		r.push({icon: arrowSymbol, offset: sprintf('%f%%', curPercent)});
		curPercent += percentBetweenArrows;
	}
	return r;
}

var g_map_sync_bounds_changed_listener = null;

function init_map_sync(checkbox_id_, enabled_initially_) {
	set_selected(checkbox_id_, enabled_initially_);

	map_sync_add_bounds_changed_listener(checkbox_id_);

	window.addEventListener('storage', function(event__) {
		if((event__.key == 'dev-map-sync') && is_selected(checkbox_id_)) {
			map_sync_set_map_bounds_from_localstorage_value(checkbox_id_);
		}
	}, false);

	$('#'+checkbox_id_).click(function() {
		if(is_selected(checkbox_id_)) {
			map_sync_set_map_bounds_from_localstorage_value(checkbox_id_);
		}
	});

	if(enabled_initially_) {
		map_sync_set_map_bounds_from_localstorage_value(checkbox_id_);
	}
}

function map_sync_set_map_bounds_from_localstorage_value(checkbox_id_) {
	var new_params = get_map_sync_params_from_str(localStorage.getItem('dev-map-sync'));
	var latlng = new_params[0], zoom = new_params[1];
	map_sync_remove_bounds_changed_listener();
	g_map.setZoom(zoom);
	set_map_bounds_northwest(latlng);
	map_sync_add_bounds_changed_listener(checkbox_id_);
}

function set_map_bounds_northwest(latlng_) {
	for(var i=0; i<10; i++) {
		var northwest = get_map_bounds_northwest();
		var latdiff = latlng_.lat() - northwest.lat(), lngdiff = latlng_.lng() - northwest.lng();
		var cur_center = g_map.getCenter();
		var new_center = new google.maps.LatLng(cur_center.lat() + latdiff, cur_center.lng() + lngdiff);
		g_map.setCenter(new_center);
	}
}

function get_map_bounds_northwest() {
	var bounds = g_map.getBounds();
	return new google.maps.LatLng(bounds.getNorthEast().lat(), west = bounds.getSouthWest().lng());
}

function map_sync_add_bounds_changed_listener(checkbox_id_) {
	map_sync_remove_bounds_changed_listener();
	g_map_sync_bounds_changed_listener = add_delayed_event_listener(g_map, 'bounds_changed', function() {
		if(is_selected(checkbox_id_)) {
			localStorage.setItem('dev-map-sync', get_map_sync_params_str_from_map());
		}
	}, 500);
}

function map_sync_remove_bounds_changed_listener() {
	if(g_map_sync_bounds_changed_listener != null) {
		google.maps.event.removeListener(g_map_sync_bounds_changed_listener);
		g_map_sync_bounds_changed_listener = null;
	}
}

function get_map_sync_params_str_from_map() {
	var northwest = get_map_bounds_northwest();
	var zoom = g_map.getZoom();
	return toJsonString([[northwest.lat(), northwest.lng()], zoom]);
}

function get_map_sync_params_from_str(str_) {
	var raw_params = $.parseJSON(str_);
	var raw_latlng = raw_params[0], zoom = raw_params[1];
	var latlng = google_LatLng(raw_latlng);
	return [latlng, zoom];
}

eval(get_sync("js/json2.js"));


