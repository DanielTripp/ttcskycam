
var LATSTEP = 0.00175, LNGSTEP = 0.0025;

// Grid squares are offset from a point that has no large importance, it just makes for more easily
// readable values during debugging {
var LATREF = 43.62696696859263, LNGREF = -79.4579391022553

function lat_to_gridlat(lat_) {
	return fdiv(lat_ - LATREF, LATSTEP);
}

function gridlat_to_lat(gridlat_) {
	return gridlat_*LATSTEP + LATREF;
}

function lng_to_gridlng(lng_) {
	return fdiv(lng_ - LNGREF, LNGSTEP)
}

function gridlng_to_lng(gridlng_) {
	return gridlng_*LNGSTEP + LNGREF;
}

function LatLng(lat_, lng_) {
	assert(typeof(lat_) === 'number' && typeof(lng_) === 'number');
	this.lat = lat_;
	this.lng = lng_;
}

// I don't know of a way to test if x_ is really an "instance" of LatLng (defined elsewhere), with all the prototype 
// function of it.  But I can test for the data fields. 
function isLatLng(x_) {
	return x_ != undefined && x_.lat != undefined && x_.lng != undefined && inii(-90, x_.lat, 90) && inii(-180, x_.lng, 180);
}

LatLng.prototype.avg = function(other_) {
	assert(isLatLng(other_));
	return new LatLng((this.lat + other_.lat)/2.0, (this.lng + other_.lng)/2.0);
}

LatLng.prototype.clone = function() {
	return new LatLng(this.lat, this.lng);
}

// returns a tuple - (snapped point, 0|1|null, dist in meters)
// elem 1 - 0 if the first point of the line is the snapped-to point, 1 if the second, None if neither.
LatLng.prototype.snap_to_lineseg = function(lineseg_) {
	assert(isLineSeg(lineseg_));
	var ang1 = angle(lineseg_.end, lineseg_.start, this);
	var ang2 = angle(lineseg_.start, lineseg_.end, this);
	if(ang1 < Math.PI/2 && ang2 < Math.PI/2) {
		var snappedpt = get_pass_point(lineseg_.start, lineseg_.end, this)
		return [snappedpt, null, this.dist_m(snappedpt)];
	} else {
		var dist0 = this.dist_m(lineseg_.start), dist1 = this.dist_m(lineseg_.end);
		if(dist0 < dist1) {
			return [lineseg_.start, 0, dist0];
		} else {
			return [lineseg_.end, 1, dist1];
		}
	}
}

// Returns 'absolute angle' between two points (measured counter-clockwise from the positive X axis)
// Returns between -pi and +pi.
LatLng.prototype.abs_angle = function(fore_) {
	assert(isLatLng(fore_));
	var opposite = (new LatLng(this.lat, fore_.lng)).dist_m(new LatLng(fore_.lat, fore_.lng));
	var adjacent = (new LatLng(this.lat, fore_.lng)).dist_m(this);
	var r = Math.atan2(opposite, adjacent);
	var latdiff = fore_.lat - this.lat, londiff = fore_.lng - this.lng;
	if(londiff > 0 && latdiff > 0) { // first quadrant 
		// do nothing 
	} else if(londiff <= 0 && latdiff > 0) { // second quadrant 
		r = Math.PI - r;
	} else if(londiff <= 0 && latdiff <= 0) { // third quadrant 
		r = -Math.PI + r;
	} else { // fourth quadrant 
		r = -r;
	}
	return r;
}

LatLng.prototype.dist_m = function(other_) {
	return dist_m(this, other_);
}

LatLng.prototype.add = function(other_) {
	assert(isLatLng(other_));
	return new LatLng(this.lat+other_.lat, this.lng+other_.lng);
}

LatLng.prototype.subtract = function(other_) {
	assert(isLatLng(other_));
	return new LatLng(this.lat-other_.lat, this.lng-other_.lng);
}

LatLng.prototype.scale = function(factor_) {
	assert(typeof(factor_) === 'number');
	return new LatLng(this.lat*factor_, this.lng*factor_);
}

function angle(arm1_, origin_, arm2_) {
	assert(isLatLng(arm1_) && isLatLng(origin_) && isLatLng(arm2_));
	var abs_ang1 = origin_.abs_angle(arm1_);
	var abs_ang2 = origin_.abs_angle(arm2_);
	var r = Math.abs(abs_ang2 - abs_ang1);
	if(r > Math.PI) {
		r = Math.abs(r - 2*Math.PI);
	} else if(r < -Math.PI) {
		r = r + 2*Math.PI;
	}
	return r;
}

function get_pass_point(standpt_, forept_, post_) {
	assert(isLatLng(standpt_) && isLatLng(forept_) && isLatLng(post_));
	var ratio = get_pass_ratio(standpt_, forept_, post_);
	var r = standpt_.add(forept_.subtract(standpt_).scale(ratio));
	return r;
}

function get_pass_ratio(standpt_, forept_, post_) {
	assert(isLatLng(standpt_) && isLatLng(forept_) && isLatLng(post_));
	var ang = angle(post_, standpt_, forept_);
	var hypot = standpt_.dist_m(post_);
	var adjacent = hypot*Math.cos(ang);
	return adjacent/forept_.dist_m(standpt_);
}

function LineSeg(start_, end_) {
	assert(isLatLng(start_) && isLatLng(end_));
	this.start = start_;
	this.end = end_;
}

LineSeg.prototype.toString = function() {
	return sprintf('[%s -> %s]', this.start, this.end);
}

LineSeg.prototype.heading = function() {
	return this.start.heading(this.end);
}

function isLineSeg(x_) {
	return (x_.start != undefined && x_.end != undefined);
}

function GridSquare(arg_) {
	if(isLatLng(arg_)) {
		this.gridlat = lat_to_gridlat(arg_.lat);
		this.gridlng = lng_to_gridlng(arg_.lng);
	} else if(isInt(arg_[0]) && isInt(arg_[1])) {
		this.gridlat = arg_[0];
		this.gridlng = arg_[1];
	} else {
		throw "Don't recognize GridSquare constructor arguments.";
	}
}

function isGridSquare(x_) {
	return (x_.gridlat != undefined && x_.gridlng != undefined);
}

GridSquare.prototype.eq = function(other_) {
	return (this.gridlat == other_.gridlat) && (this.gridlng == other.gridlng);
}

// This is important because buckets.Dictionary uses it instead of a hash function, as far as I can tell. 
GridSquare.prototype.toString = function() {
	return sprintf('GridSquare(%d,%d)', this.gridlat, this.gridlng);
}

GridSquare.prototype.latlng = function() {
	return new LatLng(gridlat_to_lat(this.gridlat), gridlng_to_lng(this.gridlng));
}

GridSquare.prototype.corner_latlngs = function() {
	var r = [];
	r.push(new LatLng(gridlat_to_lat(this.gridlat+1), gridlng_to_lng(this.gridlng+1)));
	r.push(new LatLng(gridlat_to_lat(this.gridlat+1), gridlng_to_lng(this.gridlng)));
	r.push(new LatLng(gridlat_to_lat(this.gridlat), gridlng_to_lng(this.gridlng)));
	r.push(new LatLng(gridlat_to_lat(this.gridlat), gridlng_to_lng(this.gridlng+1)));
	return r;
}

GridSquare.prototype.center_latlng = function() {
	var sw = new LatLng(gridlat_to_lat(this.gridlat), gridlng_to_lng(this.gridlng));
	var ne = new LatLng(gridlat_to_lat(this.gridlat+1), gridlng_to_lng(this.gridlng+1));
	return sw.avg(ne);
}

GridSquare.prototype.diagonal_dist_m = function() {
	var sw = new LatLng(gridlat_to_lat(this.gridlat), gridlng_to_lng(this.gridlng));
	var ne = new LatLng(gridlat_to_lat(this.gridlat+1), gridlng_to_lng(this.gridlng+1));
	return sw.dist_m(ne);
}

function LineSegAddr(polylineidx_, startptidx_) {
	this.polylineidx = polylineidx_;
	this.startptidx = startptidx_;
}

LineSegAddr.prototype.eq = function(other) {
	return (this.polylineidx == other_.polylineidx) && (this.startptidx == other_.startptidx);
}

// I believe that this is used by buckets.Set.
LineSegAddr.prototype.toString = function() {
	return sprintf('LineSegAddr(%d,%d)', this.polylineidx, this.startptidx);
}

// arg polylines_: a list of a list of LatLng objects OR a list of a list of 2-element arrays (lat and lng). 
function SnapToGridCache(polylines_) {
	this.latstep = LATSTEP; this.lngstep = LNGSTEP;
	this.polylines = massage_polylines_to_LatLngs(polylines_);
	this.gridsquare_to_linesegaddrs = new buckets.Dictionary(); // key : GridSquare.  value : set of LineSegAddr.
	var polylineidx = 0;
	var thiss = this;
	this.polylines.forEach(function(polyline) {
		for(var startptidx=0; startptidx<polyline.length-1; startptidx+=1) {
			var linesegstartgridsquare = new GridSquare(polyline[startptidx]);
			var linesegendgridsquare = new GridSquare(polyline[startptidx+1]);
			var linesegaddr = new LineSegAddr(polylineidx, startptidx);
			// TODO: be more specific in the grid squares considered touched by a line.  We are covering a whole bounding box.
			// we could narrow down that set of squares a lot.
			intervalii(linesegstartgridsquare.gridlat, linesegendgridsquare.gridlat).forEach(function(gridlat) {
				intervalii(linesegstartgridsquare.gridlng, linesegendgridsquare.gridlng).forEach(function(gridlng) {
					var gridsquare = new GridSquare([gridlat, gridlng]);
					if(!thiss.gridsquare_to_linesegaddrs.containsKey(gridsquare)) {
						thiss.gridsquare_to_linesegaddrs.set(gridsquare, new buckets.Set());
					}
					thiss.gridsquare_to_linesegaddrs.get(gridsquare).add(linesegaddr);
				});
			});
		}
		polylineidx+=1;
	});
}

function massage_polylines_to_LatLngs(in_polylines_) {
	var out_polylines = [];
	in_polylines_.forEach(function(in_polyline) {
		var out_polyline = [];
		in_polyline.forEach(function(in_pt) {
			if(isLatLng(in_pt)) {
				out_polyline.push(in_pt);
			} else if(in_pt.length == 2 && typeof(in_pt[0]) == 'number' && typeof(in_pt[1]) == 'number') {
				out_polyline.push(new LatLng(in_pt[0], in_pt[1]));
			} else {
				throw "Don't understand polyline point.";
			}
		});
		out_polylines.push(out_polyline);
	});
	return out_polylines;
}

SnapToGridCache.prototype.get_lineseg = function(linesegaddr_) {
	var polyline = this.polylines[linesegaddr_.polylineidx];
	return new LineSeg(polyline[linesegaddr_.startptidx], polyline[linesegaddr_.startptidx+1]);
}

SnapToGridCache.prototype.get_point = function(linesegaddr_) {
	return this.polylines[linesegaddr_.polylineidx][linesegaddr_.startptidx];
}

// arg searchradius_ is in metres.
//
// returns null, or an array - (geom.LatLng, LineSegAddr, bool)
// if null: no line was found within the search radius.;
// if array:
//	elem 0: snapped-to point.  geom.LatLng.
// 	elem 1: reference line segment address (or point address) that the snapped-to point is on.
//	elem 2: 'snapped-to point is along a line' flag.
//			if true: then interpret elem 1 as the address of a line segment (not a point).  The snapped-to point 
// 				(i.e. elem 0) is somewhere along that line segment.
// 			if false: then intepret elem 1 as the address of a point (not a line) - && the snapped-to point (elem 0) 
// 				is exactly the point referenced by elem 1.
SnapToGridCache.prototype.snap = function(target_, searchradius_) {
	assert(isLatLng(target_) && isInt(searchradius_));
	var target_gridsquare = new GridSquare(target_);
	var a_nearby_linesegaddr = this.get_a_nearby_linesegaddr(target_gridsquare, searchradius_);
	if(a_nearby_linesegaddr == null) {
		return null;
	}
	var a_nearby_lineseg = this.get_lineseg(a_nearby_linesegaddr);
	var endgame_search_radius = this._snap_get_endgame_search_radius(a_nearby_lineseg, target_gridsquare);
	var best_yet_snapresult = null, best_yet_linesegaddr = null;
	var thiss = this;
	this.snap_get_endgame_linesegaddrs(target_gridsquare, endgame_search_radius).forEach(function(linesegaddr) {
		var lineseg = thiss.get_lineseg(linesegaddr);
		var cur_snapresult = target_.snap_to_lineseg(lineseg);
		if(best_yet_snapresult==null || cur_snapresult[2]<best_yet_snapresult[2]) {
			best_yet_snapresult = cur_snapresult;
			best_yet_linesegaddr = linesegaddr;
		}
	});
	if(best_yet_snapresult == null || best_yet_snapresult[2] > searchradius_) {
		return null;
	} else {
		if(best_yet_snapresult[1] == null) {
			return [best_yet_snapresult[0], best_yet_linesegaddr, true];
		} else {
			var reference_point_addr = null;
			if(best_yet_snapresult[1] == 0) {
				reference_point_addr = best_yet_linesegaddr;
			} else {
				reference_point_addr = new LineSegAddr(best_yet_linesegaddr.polylineidx, best_yet_linesegaddr.startptidx+1);
			}
			return [this.get_point(reference_point_addr).clone(), reference_point_addr, false];
		}
	}
}

SnapToGridCache.prototype.snap_get_endgame_linesegaddrs = function(target_gridsquare_, search_radius_) {
	assert(isGridSquare(target_gridsquare_) && search_radius_ > 0);
	var r = new buckets.Set();
	this.get_nearby_linesegaddrs(target_gridsquare_, search_radius_).forEach(function(linesegaddr) {
		r.add(linesegaddr);
	});
	return r;
}

SnapToGridCache.prototype._snap_get_endgame_search_radius = function(a_nearby_lineseg_, target_gridsquare_) {
	assert(isLineSeg(a_nearby_lineseg_) && isGridSquare(target_gridsquare_));
	var snap_to_distances = [];
	target_gridsquare_.corner_latlngs().forEach(function(latlng) {
		var gridsquare_corner_to_lineseg_snapresult = latlng.snap_to_lineseg(a_nearby_lineseg_);
		snap_to_distances.push(gridsquare_corner_to_lineseg_snapresult[2]);
	});
	return Math.round(arrayMax(snap_to_distances));
}

SnapToGridCache.prototype.heading = function(linesegaddr_, referencing_lineseg_aot_point_) {
	assert(isLineSegAddr(linesegaddr_));
	// TODO: do something fancier on corners i.e. when referencing_lineseg_aot_point_ is false.
	assert(inie(0, linesegaddr_.polylineidx, this.polylines.length));
	if(referencing_lineseg_aot_point_) {
		assert(inie(0, linesegaddr_.startptidx, this.polylines[linesegaddr_.polylineidx].length-1));
	} else {
		assert(inie(0, linesegaddr_.startptidx, this.polylines[linesegaddr_.polylineidx].length));
	}
	var startptidx = linesegaddr_.startptidx;
	if(linesegaddr_.startptidx == this.polylines[linesegaddr_.polylineidx].length-1) {
		assert(!referencing_lineseg_aot_point_);
		startptidx -= 1;
	}
	var linesegaddr = new LineSegAddr(linesegaddr_.polylineidx, startptidx);
	var lineseg = this.get_lineseg(linesegaddr);
	return lineseg.start.heading(lineseg.end);
}

// Return a linesegaddr, any linesegaddr.  It will probably be one nearby, but definitely not guaranteed to be the closest. 
SnapToGridCache.prototype.get_a_nearby_linesegaddr = function(gridsquare_, searchradius_) {
	var nearbys = this.get_nearby_linesegaddrs(gridsquare_, searchradius_);
	if(nearbys.length > 0) {
		return nearbys[0];
	} else {
		return null;
	}
}

SnapToGridCache.prototype.get_nearby_linesegaddrs = function(gridsquare_, searchradius_) {
	assert(isGridSquare(gridsquare_));
	var r = [];
	var thiss = this;
	get_gridsquare_spiral_by_geom_vals(gridsquare_, searchradius_).forEach(function(gridsquare) {
		if(thiss.gridsquare_to_linesegaddrs.containsKey(gridsquare)) {
			thiss.gridsquare_to_linesegaddrs.get(gridsquare).forEach(function(linesegaddr) {
				r.push(linesegaddr);
			});
		}
	});
	return r;
}

function get_reach(target_gridsquare_, searchradius_) {
	assert(isGridSquare(target_gridsquare_) && isInt(searchradius_));
	var lat_reach = get_reach_single(target_gridsquare_, searchradius_, true);
	var lon_reach_top = get_reach_single(new GridSquare([target_gridsquare_.gridlat+lat_reach+1, target_gridsquare_.gridlng]), searchradius_, false);
	var lon_reach_bottom = get_reach_single(new GridSquare([target_gridsquare_.gridlat-lat_reach, target_gridsquare_.gridlng]), searchradius_, false);
	return [lat_reach, Math.max(lon_reach_top, lon_reach_bottom)];
}

function get_reach_single(reference_gridsquare_, searchradius_, lat_aot_lng_) {
	assert(isGridSquare(reference_gridsquare_) && isInt(searchradius_) && (lat_aot_lng_ == true || lat_aot_lng_ == false));
	var reference_gridsquare_latlng = reference_gridsquare_.latlng();
	var r = 1;
	while(true) {
		var cur_latlng = null;
		if(lat_aot_lng_) {
			cur_latlng = new LatLng(reference_gridsquare_latlng.lat + r*LATSTEP, reference_gridsquare_latlng.lng);
		} else {
			cur_latlng = new LatLng(reference_gridsquare_latlng.lat, reference_gridsquare_latlng.lng + r*LNGSTEP);
		}
		if(cur_latlng.dist_m(reference_gridsquare_latlng) >= searchradius_) {
			return r;
		}
		r += 1;
	}
}

// yields a 2-element array of integer offsets - that is, lat/lng offsets eg. [0,0], [1,0], [1,1], [-1, 1], etc.
function get_gridsquare_offset_spiral(latreach_, lngreach_) {
	assert(isInt(latreach_) && isInt(lngreach_));

	var r = [];
	var cur = [0, 0];
	function yieldmaybe() {
		if(Math.abs(cur[0]) <= latreach_ && Math.abs(cur[1]) <= lngreach_) {
			r.push(cur.slice(0));
		}
	}
	yieldmaybe();
	var square_reach = Math.max(latreach_, lngreach_);
	for(var spiralidx=0; spiralidx<square_reach+2; spiralidx++) {
		for(var i=0; i<spiralidx*2 + 1; i++) { // north 
			cur[0] += 1;
			yieldmaybe();
		}
		for(var i=0; i<spiralidx*2 + 1; i++) { // east 
			cur[1] += 1;
			yieldmaybe();
		}
		for(var i=0; i<spiralidx*2 + 2; i++) { // south
			cur[0] -= 1;
			yieldmaybe();
		}
		for(var i=0; i<spiralidx*2 + 2; i++) { // west
			cur[1] -= 1;
			yieldmaybe();
		}
	}
	return r;
}

function get_gridsquare_spiral_by_grid_vals(center_gridsquare_, latreach_, lngreach_) {
	assert(isGridSquare(center_gridsquare_));
	var r = [];
	get_gridsquare_offset_spiral(latreach_, lngreach_).forEach(function(offset) {
		r.push(new GridSquare([center_gridsquare_.gridlat + offset[0], center_gridsquare_.gridlng + offset[1]]));
	});
	return r;
}

function get_gridsquare_spiral_by_geom_vals(center_gridsquare_, searchradius_) {
	var reach = get_reach(center_gridsquare_, searchradius_);
	return get_gridsquare_spiral_by_grid_vals(center_gridsquare_, reach[0], reach[1]);
}


