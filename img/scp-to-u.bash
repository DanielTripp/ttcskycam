#!/usr/bin/env bash

tar zcf rendered_vehicles.tar.gz {bus,streetcar}-*.png 
#tar zcf rendered_vehicles.tar.gz streetcar-static-size-100-*.png # DEV 
#tar zcf rendered_vehicles.tar.gz bus-static-*315*.png # DEV 
scp rendered_vehicles.tar.gz $u:d/img
ssh $u tar zxf d/img/rendered_vehicles.tar.gz -C d/img
ssh $u rm d/img/rendered_vehicles.tar.gz
ssh $u chmod o+r 'd/img/bus-*.png'
ssh $u chmod o+r 'd/img/streetcar-*.png'
rm rendered_vehicles.tar.gz
