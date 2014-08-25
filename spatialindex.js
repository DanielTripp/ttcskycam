
// Makes for about a 200m x 200m square. 
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

LatLng.prototype.toString = function() {
	return sprintf('LatLng(%.6f,%.6f)', this.lat, this.lng);
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
	assert(isLatLng(other_), other_.toString());
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

LatLng.prototype.google = function() {
	return new google.maps.LatLng(this.lat, this.lng);
}

LatLng.prototype.to_other_latlng_type = function(reference_obj_) {
	if(reference_obj_ instanceof LatLng) {
		return this;
	} else if(reference_obj_ instanceof google.maps.LatLng) {
		return new google.maps.LatLng(this.lat, this.lng);
	} else if(obj_.length == 2 && typeof obj_[0] == 'number' && obj_[1] == 'number') {
		return [this.lat, this.lng];
	} else {
		throw new Exception();
	}
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
	if(standpt_.dist_m(forept_) < 0.001) {
		return 0.0;
	} else {
		var ang = angle(post_, standpt_, forept_);
		var hypot = standpt_.dist_m(post_);
		var adjacent = hypot*Math.cos(ang);
		return adjacent/forept_.dist_m(standpt_);
	}
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
	if(isInt(arg_[0]) && isInt(arg_[1])) {
		this.gridlat = arg_[0];
		this.gridlng = arg_[1];
	} else {
		var latlng = to_our_LatLng(arg_);
		this.gridlat = lat_to_gridlat(latlng.lat);
		this.gridlng = lng_to_gridlng(latlng.lng);
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

function LineSegAddr(plinename_, startptidx_) {
	this.plinename = plinename_;
	this.startptidx = startptidx_;
}

LineSegAddr.prototype.eq = function(other) {
	return (this.plinename === other_.plinename) && (this.startptidx == other_.startptidx);
}

// I believe that this is used by buckets.Set.
LineSegAddr.prototype.toString = function() {
	return sprintf('LineSegAddr(%s,%d)', this.plinename, this.startptidx);
}

// arg polylines_: a list of a list of LatLng objects OR a list of a list of 2-element arrays (lat and lng). 
function SpatialIndex(objects_, plines_or_points_) {
	assert(plines_or_points_ == 'plines' || plines_or_points_ == 'points');
	this.latstep = LATSTEP; this.lngstep = LNGSTEP;
	if(plines_or_points_ == 'plines') {
		this.init_from_polylines(objects_);
	} else {
		this.init_from_points(objects_);
	}
}

SpatialIndex.prototype.init_from_points = function(points_) {
	this.plines_aot_points = false;
	// key : GridSquare.  value : set of points (point = element of points_).
	this.gridsquare_to_points = new buckets.Dictionary(); 
	var thiss = this;
	points_.forEach(function(point) {
		assert(point.pos != undefined);
		point.pos = to_our_LatLng(point.pos);
		var gridsquare = new GridSquare(point.pos);
		if(!thiss.gridsquare_to_points.containsKey(gridsquare)) {
			thiss.gridsquare_to_points.set(gridsquare, []);
		}
		thiss.gridsquare_to_points.get(gridsquare).push(point);
	});
}

SpatialIndex.prototype.init_from_polylines = function(polylines_) {
	this.plines_aot_points = true;
	this.plinename2pts = massage_polylines_to_LatLngs(polylines_);
	this.gridsquare_to_linesegaddrs = new buckets.Dictionary(); // key : GridSquare.  value : set of LineSegAddr.
	var thiss = this;
	for(var plinename in polylines_) {
		var polyline = polylines_[plinename];
		for(var startptidx=0; startptidx<polyline.length-1; startptidx+=1) {
			var linesegstartgridsquare = new GridSquare(polyline[startptidx]);
			var linesegendgridsquare = new GridSquare(polyline[startptidx+1]);
			var linesegaddr = new LineSegAddr(plinename, startptidx);
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
	}
}

function massage_polylines_to_LatLngs(in_polylines_) {
	var out_polylines = {};
	for(var plinename in in_polylines_) {
		var in_polyline = in_polylines_[plinename];
		var out_polyline = [];
		in_polyline.forEach(function(in_pt) {
			out_polyline.push(to_our_LatLng(in_pt));
		});
		out_polylines[plinename] = out_polyline;
	}
	return out_polylines;
}

function to_our_LatLng(point_) {
	if(isLatLng(point_)) {
		return point_;
	} else if(point_.length == 2 && typeof(point_[0]) == 'number' && typeof(point_[1]) == 'number') {
		return new LatLng(point_[0], point_[1]);
	} else {
		throw sprintf("Don't understand point: %s '%s'", typeof(point_), point_);
	}
}

SpatialIndex.prototype.get_lineseg = function(linesegaddr_) {
	assert(this.plines_aot_points);
	var polyline = this.plinename2pts[linesegaddr_.plinename];
	return new LineSeg(polyline[linesegaddr_.startptidx], polyline[linesegaddr_.startptidx+1]);
}

SpatialIndex.prototype.get_pline_point = function(linesegaddr_) {
	assert(this.plines_aot_points);
	return this.plinename2pts[linesegaddr_.plinename][linesegaddr_.startptidx];
}

// arg target_ can be a google.maps.LatLng, our LatLng, or a two-element float array containing lat and lng. 
// arg searchradius_ is in metres.
//
// if this.plines_aot_points: 
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
// if !this.plines_aot_points: 
// returns null, or a point. 
SpatialIndex.prototype.snap = function(target_, searchradius_) {
	if(this.plines_aot_points) {
		return this.plines_snap(target_, searchradius_);
	} else {
		return this.points_snap(target_, searchradius_);
	}
}

SpatialIndex.prototype.multisnap = function(target_, searchradius_) {
	if(this.plines_aot_points) {
		return this.plines_multisnap(target_, searchradius_);
	} else {
		return this.points_multisnap(target_, searchradius_);
	}
}

SpatialIndex.prototype.points_snap = function(target_, searchradius_) {
	assert(!this.plines_aot_points);
	var target = to_our_latlng(target_);
	assert(isInt(searchradius_));
	var target_gridsquare = new GridSquare(target);
	var closest_point_yet = null, closest_dist_yet = 0;
	var thiss = this;
	this.get_nearby_points(target_gridsquare, searchradius_).forEach(function(point) {
		var dist_target_to_point = point.pos.dist_m(target);
		if(dist_target_to_point < searchradius_ && closest_point_yet == null || closest_dist_yet > dist_target_to_point) {
			closest_dist_yet = dist_target_to_point;
			closest_point_yet = point;
		}
	});
	return closest_point_yet;
}

SpatialIndex.prototype.points_multisnap = function(target_, searchradius_) {
	assert(!this.plines_aot_points);
	var target = to_our_latlng(target_);
	assert(isInt(searchradius_));
	var target_gridsquare = new GridSquare(target);
	var pointndists = [];
	var thiss = this;
	this.get_nearby_points(target_gridsquare, searchradius_).forEach(function(point) {
		var dist_target_to_point = point.pos.dist_m(target);
		if(dist_target_to_point <= searchradius_) {
			pointndists.push([point, dist_target_to_point]);
		}
	});
	pointndists.sort(function(a, b) {return a[1] - b[1]});
	var points = [];
	pointndists.forEach(function(pointndist) {
		points.push(pointndist[0]);
	});
	return points;
}

SpatialIndex.prototype.plines_snap = function(target_, searchradius_) {
	assert(this.plines_aot_points);
	var target = to_our_latlng(target_);
	assert(isInt(searchradius_));
	var target_gridsquare = new GridSquare(target);
	var best_yet_snapresult = null, best_yet_linesegaddr = null;
	var thiss = this;
	this.get_nearby_linesegaddrs(target_gridsquare, searchradius_).forEach(function(linesegaddr) {
		var lineseg = thiss.get_lineseg(linesegaddr);
		var cur_snapresult = target.snap_to_lineseg(lineseg);
		if(best_yet_snapresult==null || cur_snapresult[2]<best_yet_snapresult[2]) {
			best_yet_snapresult = cur_snapresult;
			best_yet_linesegaddr = linesegaddr;
		}
	});
	if(best_yet_snapresult == null || best_yet_snapresult[2] > searchradius_) {
		return null;
	} else {
		if(best_yet_snapresult[1] == null) {
			return [best_yet_snapresult[0].to_other_latlng_type(target_), best_yet_linesegaddr, true];
		} else {
			var reference_point_addr = null;
			if(best_yet_snapresult[1] == 0) {
				reference_point_addr = best_yet_linesegaddr;
			} else {
				reference_point_addr = new LineSegAddr(best_yet_linesegaddr.plinename, best_yet_linesegaddr.startptidx+1);
			}
			return [this.get_pline_point(reference_point_addr).clone(), reference_point_addr, false];
		}
	}
}

SpatialIndex.prototype.plines_multisnap = function(target_, searchradius_) {
	assert(this.plines_aot_points);
	var target = to_our_latlng(target_);
	assert(isInt(searchradius_));
	var target_gridsquare = new GridSquare(target);
	var linesegaddr_n_lssrs = [];
	var thiss = this;
	this.get_nearby_linesegaddrs(target_gridsquare, searchradius_).forEach(function(linesegaddr) {
		var lineseg = thiss.get_lineseg(linesegaddr);
		var lssr = target.snap_to_lineseg(lineseg); // lssr = Line Seg Snap Result 
		if(lssr[2] <= searchradius_) {
			linesegaddr_n_lssrs.push([linesegaddr, lssr]);
		}
	});
	linesegaddr_n_lssrs.sort(function(a, b) {
		var adist = a[1][2], bdist = b[1][2];
		return adist - bdist;
	});
	var r = [];
	for(var i in linesegaddr_n_lssrs) {
		var e = linesegaddr_n_lssrs[i];
		var linesegaddr = e[0], lssr = e[1];
		if(lssr[1] == null) {
			r.push([lssr[0].to_other_latlng_type(target_), linesegaddr, true]);
		} else {
			var reference_point_addr = null;
			if(lssr[1] == 0) {
				reference_point_addr = linesegaddr;
			} else {
				reference_point_addr = new LineSegAddr(linesegaddr.plinename, linesegaddr.startptidx+1);
			}
			r.push([this.get_pline_point(reference_point_addr).clone(), reference_point_addr, false]);
		}
	}
	return r;
}

SpatialIndex.prototype.heading = function(linesegaddr_, referencing_lineseg_aot_point_) {
	assert(this.plines_aot_points);
	assert(isLineSegAddr(linesegaddr_));
	// TODO: do something fancier on corners i.e. when referencing_lineseg_aot_point_ is false.
	assert(inie(0, linesegaddr_.plinename, this.plinename2pts.length));
	if(referencing_lineseg_aot_point_) {
		assert(inie(0, linesegaddr_.startptidx, this.plinename2pts[linesegaddr_.plinename].length-1));
	} else {
		assert(inie(0, linesegaddr_.startptidx, this.plinename2pts[linesegaddr_.plinename].length));
	}
	var startptidx = linesegaddr_.startptidx;
	if(linesegaddr_.startptidx == this.plinename2pts[linesegaddr_.plinename].length-1) {
		assert(!referencing_lineseg_aot_point_);
		startptidx -= 1;
	}
	var linesegaddr = new LineSegAddr(linesegaddr_.plinename, startptidx);
	var lineseg = this.get_lineseg(linesegaddr);
	return lineseg.start.heading(lineseg.end);
}

SpatialIndex.prototype.get_nearby_linesegaddrs = function(gridsquare_, searchradius_) {
	assert(this.plines_aot_points);
	assert(isGridSquare(gridsquare_));
	var r = new buckets.Set();
	var thiss = this;
	get_gridsquare_spiral_by_geom_vals(gridsquare_, searchradius_).forEach(function(gridsquare) {
		if(thiss.gridsquare_to_linesegaddrs.containsKey(gridsquare)) {
			thiss.gridsquare_to_linesegaddrs.get(gridsquare).forEach(function(linesegaddr) {
				r.add(linesegaddr);
			});
		}
	});
	return r;
}

SpatialIndex.prototype.get_nearby_points = function(gridsquare_, searchradius_) {
	assert(!this.plines_aot_points);
	assert(isGridSquare(gridsquare_));
	var r = [];
	var thiss = this;
	get_gridsquare_spiral_by_geom_vals(gridsquare_, searchradius_).forEach(function(gridsquare) {
		if(thiss.gridsquare_to_points.containsKey(gridsquare)) {
			thiss.gridsquare_to_points.get(gridsquare).forEach(function(point) {
				r.push(point);
			});
		}
	});
	return r;
}

function to_our_latlng(obj_) {
	if(obj_ instanceof LatLng) {
		return obj_;
	} else if(obj_ instanceof google.maps.LatLng) {
		return new LatLng(obj_.lat(), obj_.lng());
	} else if(obj_.length == 2 && typeof obj_[0] == 'number' && obj_[1] == 'number') {
		return new LatLng(obj_[0], obj_[1]);
	} else {
		throw new Exception();
	}
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


