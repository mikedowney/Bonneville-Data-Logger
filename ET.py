#!/usr/bin/python

from Adafruit_I2C import Adafruit_I2C
from time import sleep, strftime, localtime
import gps
from string import find
from datetime import date, datetime, time, timedelta, tzinfo
import MySQLdb



# ===========================================================================
# Display driver for eagle tree power panel LCD. This display is a 2x16
# LCD driven over an I2C bus. Note that level shifters should be used before
# interfacing to the Raspberry Pi
# pinout
# 1. +5V (red wire)
# 2. Ground
# 3. SDA (5V)
# 4. SCK (5V)
#
# default address should be 0x3B
#
# To Initialize display 
# 00 34 0C 06 01
#
# 00 - Control Byte,Function Set
# 34 - 2-Line display
# 0C - Display Control, Display on, Cursor Off, Cursor blink Off
# 06 - Entry Mode, auto increment address 1 and shift cursor to the right on each write
# 01 - Return Home
#
# To position cursor
# 00 YY
# 00 - Control Byte,Function Set
# YY - Cursor position. For line 1 add 0x80 to character position, for line 2 add 0xC0
#
# Write Character (up to 16 characters)
# 40 xx xx xx xx xx xx
# 40 - Control byte - Write data
# YY - ASCII character to print. Multiple characters can be strung together because of Entry Mode
# must set MSB first. for example, to print a space (ascii 0x20) would be 0x40 0xA0
# ===========================================================================

def et_lcd_clear_screen(): # initialize and clear the display
    et_lcd_address = 0x3B
    et_lcd = Adafruit_I2C(et_lcd_address)
    lcd_init = [0x34, 0x0C, 0x06, 0x01]
    lcd_goto_line1 = [0x80]
    lcd_goto_line2 = [0xC0]
    lcd_clear_line = [0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0, 0xA0]
    
    et_lcd.writeList(0x00,lcd_init) 
    et_lcd.writeList(0x00,lcd_goto_line1)
    et_lcd.writeList(0x40,lcd_clear_line)
    et_lcd.writeList(0x00,lcd_goto_line2)
    et_lcd.writeList(0x40,lcd_clear_line)
    et_lcd.writeList(0x00,lcd_goto_line1)



def et_lcd_message(line, message_given): # print a message on the screen on line x
    et_lcd_address = 0x3B
    et_lcd = Adafruit_I2C(et_lcd_address)
    line_bytes = []
    if line == 1:
        line_bytes.append(0x80)
    if line == 2:
        line_bytes.append(0xC0)
    et_lcd.writeList(0x00, line_bytes)
    message_data = []
    i=0
    while i < len(message_given):
        message_data.append(ord(message_given[i])+128)
        i+=1
    et_lcd.writeList(0x40,message_data)
    
    
# ===========================================================================
# measure RPM from a pulse train on a GPIO pin. measure the number of 
# transitions on a GPIO pin during a 500ms time frame and calculate
# Engine RPM from this value
# note that pin_number is the actual pin number on the connector, not the 
# port GPIO number. For example, if you want to read GPIO4, you would pass
# 7 to the function (pin 7 on the connector)
# ===========================================================================
import RPi.GPIO as GPIO  
from datetime import datetime

def measure_rpm_old(pin_number): #pass the pin number to the function. 
    #set the pin direction on the GPIO pin
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(pin_number, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    #wait for the pin to get to a known state (high)
    pin_state = GPIO.input(pin_number)
    change_start = datetime.now()
    change_ms=0
    while pin_state == 1 and change_ms < 100: #make sure the pin is actually changing. Tineout if not. 
        change = datetime.now() - change_start
        change_ms = ((change.days * 24 * 60 * 60 + change.seconds) * 1000 + change.microseconds / 1000.0)        
        pin_state = GPIO.input(pin_number)
    
    #take 500ms worth of data. count how many times the pin changes state
    t1 = datetime.now()
    samples = 0
    ms = 0
    while ms < 500:
        
        pin_state = GPIO.input(pin_number)
        change_start = datetime.now()
        change_ms=0
        while pin_state == 0 and change_ms < 501: #if pin doesnt change in 501 ms, then bail out. 
            change = datetime.now() - change_start
            change_ms = ((change.days * 24 * 60 * 60 + change.seconds) * 1000 + change.microseconds / 1000.0)
            pin_state = GPIO.input(pin_number)
        
        change_start = datetime.now()
        change_ms=0
        while pin_state == 1 and change_ms < 501: #if pin doesnt change in 501 ms, then bail out. 
            change = datetime.now() - change_start
            change_ms = ((change.days * 24 * 60 * 60 + change.seconds) * 1000 + change.microseconds / 1000.0)
            pin_state = GPIO.input(pin_number)

        #calculate the time elapsed since we started taking samples
        dt = datetime.now() - t1
        ms = ((dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0)
        samples = samples + 1

    if samples == 1:
        samples = samples - 1 #if the pin is not changing, RPM should be zero
    rpm = 60 * 2 * samples 
    return rpm
    

# ===========================================================================
# measure RPM using an LM2907 frequency to voltage converter and then meansure  
# voltage using an ADS1115 A/D
# 
# Frequency of engine is 6297rpm/V
# 
# ===========================================================================
from Adafruit_ADS1x15 import ADS1x15

def measure_rpm(pin_number): #pass the pin number to the function. 
    ADS1015 = 0x00    # 12-bit ADC
    ADS1115 = 0x01	# 16-bit ADC
    ADS_Current = ADS1115    
    adc = ADS1x15(ic=ADS_Current)
    # Read channel 0 in single-ended mode 
    result = adc.readADCSingleEnded(0)
    # For ADS1115 at max range (+/-6.144V) 1-bit = 0.1875mV (16-bit values)
    #print "Channel 0 = %.3f V" % (result * 0.0001875)
    result = (result * 0.0001875)
    #print result
    rpm = 6496.3 * result - 88.159
    if rpm < 0:
        rpm = 0
    return rpm


# ===========================================================================
# used the GPSd daemon to parse the NMEA messages from a GPS receiver
# currently using an Adafruit Ultimate GPS, but almost any UART based GPS should work
# note that the UART port settings are set in the daemon and not in this function. 
# 
# get the latest report from GPS and return 
# time[0], latitude[1], longtitude[2], speed[3], altitude[4], status[5]
#
# GPS will report back all times using GMT time zone, so we will apply an offset
# to calculate local time
# ===========================================================================
def get_gps(time_offset):
    session = gps.gps("localhost", "2947") #start a new session with the GPS daemon
    session.stream(gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
    report_received = 0
    while report_received == 0:
        #print "waiting"
        report = session.next() # wait for the next status message from the GPS receiver
        #print "finished"
        #print report
        if report['class'] == 'TPV': # Wait for a 'TPV' report and display the current time
            if hasattr(report, 'time'):
                report_received = 1
                s = report.time
                s = s[:find(s, "T")] + " " + s[find(s, "T")+1:]
                s = s[:find(s, ".")]  
                dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
                dt = dt + timedelta(hours=time_offset) # apply an offset for the local time zone
                gps_time = dt.strftime('%Y-%m-%d %H:%M:%S') #convert time string into a format we can use
                mode = report.mode # get status from the GPS receiver. either no lock, 2d lock or 3d lock
                if mode == 1:
                    mode_string = "NO"
                if mode == 2:
                    mode_string = "2D"
                if mode == 3:
                    mode_string = "3D"
                lat = report.lat
                longatude = report.lon
                speed = 2.236936*report.speed # convert meters per second to mph
                alt = report.alt
            else:
                if hasattr(report, 'mode'):
                    report_received = 1
                    lat = 0
                    longatude = 0
                    speed = 0
                    alt = 0
                    mode = report.mode # get status from the GPS receiver. either no lock, 2d lock or 3d lock
                    if mode == 1:
                        mode_string = "NO"
                    if mode == 2:
                        mode_string = "2D"
                    if mode == 3:
                        mode_string = "3D"
                    gps_time = strftime('%Y-%m-%d %H:%M:%S', localtime())
    return gps_time, lat, longatude, speed, alt, mode_string;  #return data back from the receiver. 
 
    
    
    
def get_next_dataset(starttime):
    con=MySQLdb.connect(user="root",passwd="aviator",db="speed_tracker")
    cur = con.cursor()
    sql_string = "INSERT INTO dataset (starttime) VALUES  ('%s')" % (starttime)
    cur.execute(sql_string)
    con.commit()

    db2=MySQLdb.connect(user="root",passwd="aviator",db="speed_tracker")
    c2=db2.cursor(MySQLdb.cursors.DictCursor)
    sql_string = "SELECT id FROM dataset order by id desc limit 1"
    c2.execute(sql_string)
    for row in c2.fetchall() :
        dataset = row["id"]
    db2.close()
    c2.close()
    
    return dataset



# ===========================================================================
# read temperatures from 2 thermocouples and return their values
# temperatures are read from 2 MAX6675 thermocouple transducers read over an SPI bus
# ===========================================================================
import RPi.GPIO as GPIO  
import time      
        
def measure_temp():
    timedelay=0.001
    # to use Raspberry Pi board pin numbers  
    GPIO.setmode(GPIO.BOARD)  
    GPIO.setwarnings(False)
    # set up GPIO output channel - use pin number, not port number. example, pin 26 is actually GPIO7
    SPI_CE = 24
    SPI_CE2 = 26
    
    SPI_SCLK = 23
    SPI_MISO = 21
    GPIO.setup(SPI_CE, GPIO.OUT)  
    GPIO.setup(SPI_CE2, GPIO.OUT)  
    GPIO.setup(SPI_SCLK, GPIO.OUT)  
    GPIO.setup(SPI_MISO, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
    
    #set intial state of SPI bus
    GPIO.output(SPI_CE,GPIO.HIGH)  
    GPIO.output(SPI_CE2,GPIO.HIGH)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(100*timedelay)  
    
    #read Thermocouple1
    GPIO.output(SPI_CE,GPIO.LOW) 
    time.sleep(timedelay)  
    
    #read dummy sign bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    if GPIO.input(SPI_MISO):
        print "sign error"
    #read temp values
    value = 0
    i = 15
    while i>3:
        i -= 1
        GPIO.output(SPI_SCLK,GPIO.HIGH)  
        time.sleep(timedelay)  
        GPIO.output(SPI_SCLK,GPIO.LOW)  
        time.sleep(timedelay)  
        if GPIO.input(SPI_MISO):
            value = value + 2**(i-3)
    
    #read thermocouple_input bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    if GPIO.input(SPI_MISO):
        print "thermocouple 1 not detected"
    
    #read device_id bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    
    #read thermocouple_state bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    
    #print value
    temperature = 0.25*value-37


    #read Thermocouple2
    GPIO.output(SPI_CE,GPIO.HIGH) 
    GPIO.output(SPI_CE2,GPIO.HIGH) 
    time.sleep(100*timedelay)
    GPIO.output(SPI_CE2,GPIO.LOW) 
    time.sleep(timedelay)  
    
    #read dummy sign bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    if GPIO.input(SPI_MISO):
        print "sign error"
    #read temp values
    value = 0
    i = 15
    while i>3:
        i -= 1
        GPIO.output(SPI_SCLK,GPIO.HIGH)  
        time.sleep(timedelay)  
        GPIO.output(SPI_SCLK,GPIO.LOW)  
        time.sleep(timedelay)  
        if GPIO.input(SPI_MISO):
            value = value + 2**(i-3)
    
    #read thermocouple_input bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    if GPIO.input(SPI_MISO):
        print "thermocouple 2 not detected"
    
    #read device_id bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    
    #read thermocouple_state bit
    GPIO.output(SPI_SCLK,GPIO.HIGH)  
    time.sleep(timedelay)  
    GPIO.output(SPI_SCLK,GPIO.LOW)  
    time.sleep(timedelay)  
    
    #print value
    temperature2 = 0.25*value -37
    
    
    GPIO.output(SPI_CE,GPIO.HIGH) 
    GPIO.output(SPI_CE2,GPIO.HIGH) 
    time.sleep(100*timedelay)  
    return temperature, temperature2
