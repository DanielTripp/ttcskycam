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

g_loading_get_count = 0;

function inc_loading_get_count() {
	g_loading_get_count++;
	if(g_loading_get_count == 1) {
		if(g_loading_gif_marker!=null) {
			g_loading_gif_marker.setVisible(true);
		}
        var img = document.getElementById('loading_img');
        if(img != null) {
            img.style.visibility = 'visible';
        }
	}
}

function dec_loading_get_count() {
	g_loading_get_count--;
	if(g_loading_get_count == 0) {
		if(g_loading_gif_marker!=null) {
			g_loading_gif_marker.setVisible(false);
		}
        var img = document.getElementById('loading_img');
        if(img != null) {
            img.style.visibility = 'hidden';
        }
	}
}

function get(url_, success_) {
	inc_loading_get_count();
	$.ajax({url:url_, async:true, 
		error: function(jqXHR_, textStatus_, errorThrown_) {
			dec_loading_get_count();
			alert(sprintf("Error %s %s %s", jqXHR_, textStatus_, errorThrown_));
		}, 
		success: function(data_, textStatus_, jqXHR_) {
			dec_loading_get_count();
			success_($.parseJSON(data_));
		}
	});
}

function get_sync(url_) {
	r = $.ajax({url:url_, async:false, 
		error: function(jqXHR_, textStatus_, errorThrown_) {
			alert("Error");
		}
	}).responseText;
	return r;
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
	document.getElementById(id_).innerHTML = contents_;
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

function callpy(module_and_funcname_) {
	var func_args = new Array();
	for(var i=1; i<arguments.length-1; i++) {
		func_args.push(arguments[i]);
	}
	var url = callpy_url(module_and_funcname_, func_args);
	var success_func = arguments[arguments.length-1];
	get(url, success_func);
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
		}
		var argval_json = window.JSON.stringify(argval);
		paramstr += "&arg"+i+"="+encode_url_paramval(argval_json);
	}
	return "callpy.cgi?"+paramstr;
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

eval(get_sync("js/json2.js"));

