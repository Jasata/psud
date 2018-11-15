#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / OBC Emulator
# Configuration values from PATE Monitor's backend
#
import serial

class Config:
    class PSU:
        port          = '/dev/ttyUSB0'
        baudrate      = 9600
        parity        = serial.PARITY_NONE
        stopbits      = serial.STOPBITS_TWO
        bytesize      = serial.EIGHTBITS
        timeout       = 0.500    #seconds, timeout has to be > 300 ms
        write_timeout = None
        default_voltage = 2.5         #[V]
        default_current_limit = 0.100 #[A]
        class Daemon:
            run_directory       = '/srv/nginx-root'
            lock_directory      = '/tmp'
            class Interval:
                command         = 0.2   # seconds between polls
                update          = 0.5   # seconds between updates
    class PATE:
        class Bus:
            port                = '/dev/ttyUSB1'
            baudrate            = 115200
            parity              = serial.PARITY_NONE
            stopbits            = serial.STOPBITS_ONE
            bytesize            = serial.EIGHTBITS
            timeout             = 0.05
            write_timeout       = None
        class Interval:
            status_check        = 10    # seconds between status check message
            housekeeping        = 60    # seconds between housekeeping retrieval
    # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    logging_level               = "DEBUG"
    database_file               = '/srv/nginx-root/pmapi.sqlite3'
    command_poll                = 0.1   # seconds





def display_config(obj=Config, indent_level=0):
    """Created for class'es (might work for objects)."""
    def get_name(x):
        if hasattr(x, '__name__'):
            return x.__name__           # class
        else:
            return type(x).__name__     # object
    indent = 4
    print("{}[{}]".format(" " * indent * indent_level, get_name(obj)))
    for k, v in vars(obj).items():
        # Disregard double-underscore members
        if k[:2] != '__':
            if type(v).__name__ in ('float', 'int', 'str', 'long', 'complex', 'NoneType'):
                print("{}{} = {}".format(" " * indent * (indent_level + 1), k, str(v) or "None"))
            elif type(v).__name__ == 'type':
                # it's a class
                display_config(v, indent_level + 1)
            elif hasattr(v, '__class__') and hasattr(v, '__dict__'):
                # It's an object (instance of some class)
                display_config(v, indent_level + 1)
            else:
                print("ERROR: Unhandled type: '{}'".format(str(type(v))))

# EOF