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
		var img = document.getElementById('loading_img');
		if(img != null) {
			img.style.visibility = 'visible';
		}
		//set_contents('p_get_status', '...');
	}
}

function dec_loading_get_count() {
	g_loading_get_count--;
	if(g_loading_get_count == 0) {
		var img = document.getElementById('loading_img');
		if(img != null) {
			img.style.visibility = 'hidden';
		}
		//set_contents('p_get_status', '');
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
	
function init_map() {
	var myOptions = {
		center: new google.maps.LatLng(43.655, -79.425),
		zoom: 14,
		scaleControl: true, 
		mapTypeId: google.maps.MapTypeId.ROADMAP
	};
	g_map = new google.maps.Map(document.getElementById("map_canvas"),
			myOptions);
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
		paramstr += "&arg"+i+"="+encode_url_paramval(window.JSON.stringify(func_args_[i]));
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

eval(get_sync("js/json2.js"));

