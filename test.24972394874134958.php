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
    <script type="text/javascript">


function initialize() {

	init_map();


var marker = new google.maps.Marker({
    position: new google.maps.LatLng( 43.6507574, -79.4138221),
		    icon: {
				        path: google.maps.SymbolPath.CIRCLE,
								        scale: 14, 
												strokeWeight : 0, 
												fillOpacity: 0.5, 
												fillColor: 'black'
												    },
														    draggable: true,
																    map: g_map
																		});

}


    </script>
  </head>
  <body onload="initialize()" >
		<div id="map_canvas" style="width:100%; height:100%"></div>
		<div style="float: left;">a<br>a2<br>a3<br></div>
		<div style="float: right;">b<br>b2<br>b3<br>b4</div>
		<br>
		<div style="clear: both;">
		x
		</div>
		y
		<p id="p1">p1</p>
		<p id="p2">p2</p>
  </body>
</html>
