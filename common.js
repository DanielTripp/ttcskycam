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

g_loading_urls = new buckets.LinkedList();

function add_to_loading_urls(url_) {
	g_loading_urls.add(url_)
	if(g_loading_urls.size() == 1) {
		if(g_loading_gif_marker!=null) {
			g_loading_gif_marker.setVisible(true);
		}
		var img = document.getElementById('loading_img');
		if(img != null) {
			img.style.visibility = 'visible';
		}
	}
	update_p_loading_urls();
}

function update_p_loading_urls() {
	var p_loading_urls = document.getElementById('p_loading_urls');
	if(p_loading_urls != null) {
		var html = "";
		g_loading_urls.forEach(function(url) {
			html += url+"<br>";
		});
		p_loading_urls.innerHTML = html;
	}
}

function remove_from_loading_urls(url_) {
	var was_removed = g_loading_urls.remove(url_);
	assert(was_removed, "url "+url_+" not found in list.");
	if(g_loading_urls.size() == 0) {
		if(g_loading_gif_marker!=null) {
			g_loading_gif_marker.setVisible(false);
		}
		var img = document.getElementById('loading_img');
		if(img != null) {
			img.style.visibility = 'hidden';
		}
	}
	update_p_loading_urls();
}

// funcs_arg_ can be a single callable (success function) or an object with 'success' and/or 'error' members. 
function get(url_, funcs_arg_) {
	add_to_loading_urls(url_);
	var success_func = funcs_arg_.success, error_func = funcs_arg_.error;
	if(success_func == undefined && error_func == undefined) {
		success_func = funcs_arg_;
	}
	$.ajax({url:url_, async:true, 
		error: function(jqXHR_, textStatus_, errorThrown_) {
			remove_from_loading_urls(url_);
			if(error_func != undefined) {
				error_func();
			}
			alert(sprintf("Error %s %s %s", jqXHR_, textStatus_, errorThrown_));
		}, 
		success: function(data_, textStatus_, jqXHR_) {
			remove_from_loading_urls(url_);
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
	
var g_loading_gif_marker = null;

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

  g_loading_gif_marker = new google.maps.Marker({
      position: new google.maps.LatLng(43.652868888096386, -79.41064639290471),
      map: g_map,
      optimized: false,
      draggable: false,
      icon: new google.maps.MarkerImage('loading.gif',
          null, null, new google.maps.Point(-10, 70)),
      visible: false
    });

	google.maps.event.addListener(g_map, 'bounds_changed', reposition_loading_gif_marker);
}

function reposition_loading_gif_marker() {
	g_loading_gif_marker.setPosition(g_map.getBounds().getSouthWest());
}


function set_contents(id_, contents_) {
	var dom_elem = document.getElementById(id_);
	assert(dom_elem!=null, 'dom elem "'+id_+'" is null');
	dom_elem.innerHTML = contents_;
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
	for(var i in latlngs_) {
		r.push(google_LatLng(latlngs_[i]));
	}
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
		}
		var argval_json = window.JSON.stringify(argval);
		paramstr += "&arg"+i+"="+encode_url_paramval(argval_json);
	}
	return "callpy.cgi?"+paramstr;
}

function toJsonString(obj_) {
	return window.JSON.stringify(obj_);
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
  return 'AssertException: ' + this.message;
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

function to_buckets_list(array_) {
	var r = new buckets.LinkedList();
	for(var i in array_) {
		var e = array_[i];
		r.add(e);
	}
	return r;
}

function to_buckets_set(array_) {
	var r = new buckets.Set();
	for(var i in array_) {
		var e = array_[i];
		r.add(e);
	}
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
	for(var i in temp) {
		var e = temp[i];
		l_.add(e);
	}
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

	google.maps.event.addListener(listenee_, eventname_, delaying_listener);
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
	for(var i in raw_latlngs) {
		var raw_latlng = raw_latlngs[i];
		glatlngs.push(google_LatLng(raw_latlng));
	}
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


eval(get_sync("js/json2.js"));

