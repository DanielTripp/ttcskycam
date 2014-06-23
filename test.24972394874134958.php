<!DOCTYPE html>
<html>
  <head>
		<title>test</title>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 70%; margin: 0; padding: 0 }
    </style>
    <script type="text/javascript"
		      src="http://maps.googleapis.com/maps/api/js?sensor=false">
					    </script>
		<script type="text/javascript" src="js/richmarker-compiled.js"></script>
		<script type="text/javascript" src="js/jquery-1.7.1.min.js"></script>
		<script type="text/javascript" src="js/buckets-minified.js"></script>
		<script type="text/javascript" src="common.js"></script>
		<script type="text/javascript" src="js/infobox_packed.js"></script>
		<script type="text/javascript" src="snaptogrid.js"></script>
    <script type="text/javascript">


function initialize() {

	init_map();
	google.maps.event.addListenerOnce(g_map, 'bounds_changed', function() {
		init_map_sync('map_sync_checkbox', true);

		var sc = new SnapToGridCache([[ [43.653497, -79.465184], [43.656338, -79.452353] ], 
				[ [43.652286, -79.458983], [43.657564, -79.461215] ]]);
	});

}

    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<br>
		<label><input id="map_sync_checkbox" type="checkbox" checked />Map Sync</label>
		<p id="p_error"/>
		<p id="p_latlngs"/>
		<p id="p_loading_urls"/>
  </body>
</html>
