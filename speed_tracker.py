#!/usr/bin/python
import MySQLdb
from ET import et_lcd_clear_screen, et_lcd_message, measure_rpm, get_next_dataset, get_gps, measure_temp
import RPi.GPIO as GPIO
import os
from gps import *
from time import *
import threading
from string import find
from datetime import date, datetime,  timedelta, tzinfo
import math
from socket import socket, SOCK_DGRAM, AF_INET
from subprocess import Popen, PIPE


print "speed tracker started"

#determine the IP address of the ethernet and WIFI connections and show them on the screen for a few seconds on startup
command = "/sbin/ifconfig"
arg = "wlan0"
output = Popen([command, arg], stdout=PIPE)
output_string =  output.stdout.read()
if output_string.find('inet addr:') > 0:
    IP_ADDRESS1 = output_string[output_string.find('inet addr:')+10:output_string.find(' Bcast:')]
else:
    IP_ADDRESS1 = "none"
arg = "eth0"
output = Popen([command, arg], stdout=PIPE)
output_string =  output.stdout.read()
if output_string.find('inet addr:') > 0:
    IP_ADDRESS2 = output_string[output_string.find('inet addr:')+10:output_string.find(' Bcast:')]
else:
    IP_ADDRESS2 = "none"

line1 = "W%s" % IP_ADDRESS1
line2 = "E%s" % IP_ADDRESS2
#print line1
#print line2
et_lcd_clear_screen()
et_lcd_message(1,line1)
et_lcd_message(2,line2)
sleep(1)



dataset = 0
#use pin7 (GPIO4) as recording switch input
GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)



while 1:
    thermocouples = measure_temp()
    egt = thermocouples[0]
    cht = thermocouples[1]
    rpm = measure_rpm(11) 
    #rpm = 500
    gps_data = get_gps(-4) # get the latest GPS data from the GPS receiver. parameter is time offset from GMT
    #print gps_data
    speed = gps_data[3] 
    if GPIO.input(7):
        dataset = 0
        recording_status = "   "
    else:
        recording_status = "REC"
        if dataset == 0:
            dataset = get_next_dataset(gps_data[0])

    lcd_line1 = "%03dmph %04d  %s" % (speed, cht, gps_data[5])
    lcd_line2 = " %05d %04d  %s" % (rpm, egt, recording_status)
    et_lcd_message(1,lcd_line1)
    et_lcd_message(2,lcd_line2)
    #print lcd_line1
    #print lcd_line2
    #print
    
    #print "INSERT INTO datapoints (date_time, latitude, longitude, speed, altitude, gps_status, engine_rpm, egt, cht, dataset_num) VALUES  ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (gps_data[0], gps_data[1], gps_data[2], speed, gps_data[4], gps_data[5], rpm, egt, cht, dataset)
    
    if dataset != 0:
        try: # insert the data into the SQL server
    	  con=MySQLdb.connect(user="root",passwd="aviator",db="speed_tracker")
    	  cur = con.cursor()
    	  sql_string = "INSERT INTO datapoints (date_time, latitude, longitude, speed, altitude, gps_status, engine_rpm, egt, cht, dataset_num) VALUES  ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (gps_data[0], gps_data[1], gps_data[2], speed, gps_data[4], gps_data[5], rpm, egt, cht, dataset)
    	  cur.execute(sql_string)
    	  con.commit()
        except MySQLdb.Error, e:
    	  print "Error %d: %s" % (e.args[0], e.args[1])
        finally:
    	  if con:
    	    con.close()

