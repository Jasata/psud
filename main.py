#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# main.py - Jani Tammi <jasata@utu.fi>
#   0.1.0   2018.11.14  Initial version.
#
#
# Execute this script to start the daemon.
#
#       'main.py' will parse commandline and update Config accordingly.
#       This script will then invoke 'deamonify.py', which will transform
#       the process into a daemon (unless '--nodaemon' was specified).
#       'daemonify.py' will finally enter the program's main loop, which
#       is located in 'control.py'.
#
#       main.py -> daemonify.py -> control.py
#
#       Class files (names starting with capital letter) are used by the
#       'control.py' main loop to execute the tasks periodically.
#
__version__ = "0.1.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION     = __version__
HEADER      = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / PATE Monitor
OBC Emulator Daemon version {}, 2018 {}
""".format(__version__, __author__)

import os
import sys
import errno
import fcntl
import serial
import logging
import sqlite3
import platform
import argparse

from Config         import Config, display_config
from pathlib        import Path
from control        import *                # Most importantly: control.psu()




def start_regular_process(function, config=Config):
    """Change directory, create lock file, run."""

    try:
        os.chdir(config.PSU.Daemon.working_directory)
    except Exception as e:
        print(
            "Unable to change directory to '{}'!\n".format(
                config.PSU.Daemon.working_directory
            )
        )
        print(str(e))
        os._exit(-1)

    #
    # Execute main loop
    #
    try:
        from Lockfile import Lockfile
        with Lockfile("/tmp/{}.lock".format(Config.PSU.Daemon.name)):
            function(config)
    except Lockfile.AlreadyRunning as e:
        print(str(e))
    except Exception as e:
        print("Main loop ended with an exception!\n", str(e))
    else:
        print("Normal termination.")






######################################################################
#
# Start-up routines
#
if __name__ == "__main__":

    # Print header with additional info
    print(HEADER)
    print(
        "Running on Python ver.{} on {} {}" \
        .format(
            platform.python_version(),
            platform.system(),
            platform.release()
        )
    )
    print(
        "SQLite ver.{} (pySQLite ver.{})" \
        .format(
            sqlite3.sqlite_version,
            sqlite3.version
        )
    )
    print("pySerial ver.{}".format(serial.VERSION))
    # If the number of cores cannot be determined, multiprocessing.cpu_count()
    # raises NotImplementedError, but os.cpu_count() returns None.
    print(
        "{} cores are available ({} cores in current OS)\n" \
        .format(
            os.cpu_count() or "Unknown number of",
            platform.architecture()[0]
        )
    )



    #
    # Commandline arguments
    #
    parser = argparse.ArgumentParser(
        description     = HEADER,
        formatter_class = argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-d',
        '--datafile',
        help    = "PATE Monitor SQLite3 database file path and name",
        nargs   = '?',
        dest    = "database_file",
        default = Config.database_file,
        type    = str,
        metavar = "FILE"
    )
    parser.add_argument(
        '-l',
        '--log',
        help    = "Set logging level",
        choices = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        nargs   = '?',
        dest    = "logging_level",
        const   = "INFO",
        default = Config.logging_level,
        type    = str.upper,
        metavar = "LEVEL"
    )
    parser.add_argument(
        '-p',
        '--port',
        help = "Set serial port device. Default: '{}'".format(Config.PSU.port),
        nargs = '?',
        dest = "serial_port",
        const = "DEVICE",
        default = Config.PSU.port,
        type = str
    )
    parser.add_argument(
        '--nodaemon',
        help = 'Do not execute as a daemon',
        action = 'store_true'
    )
    args = parser.parse_args()

    #
    # Create instance of Config and update according to commandline.
    #
    Config.logging_level = getattr(logging, args.logging_level)
    Config.database_file = args.database_file
    Config.PSU.port      = args.serial_port

    if Config.logging_level == logging.DEBUG:
        display_config(Config)
        print("\n\n")


    #
    # Test-open serial port
    #
    print("Opening {}...".format(Config.PSU.port), end = '', flush = True)
    try:
        port = serial.Serial(
            port            = Config.PSU.port,
            baudrate        = Config.PSU.baudrate,
            parity          = Config.PSU.parity,
            stopbits        = Config.PSU.stopbits,
            bytesize        = Config.PSU.bytesize,
            timeout         = Config.PSU.timeout,
            write_timeout   = Config.PSU.write_timeout
        )
    except Exception as e:
        print("FAILED!")
        print(str(e))
        os._exit(-1)
    else:
        print("OK")
        port.close()


    #
    # database file open/create
    #
    # dbfile = Path(Config.database_file)
    # if not dbfile.is_file():
    #     print(Config.database_file, "not found!")
    #     os._exit(-1)

    if not os.path.isfile(Config.database_file):
        print("Database file '{}' does NOT exist".format(Config.database_file))
        os._exit(-1)


    #
    # Start-up routines completed, deamonify
    #
    from control import psu
    if args.nodaemon:
        start_regular_process(psu, Config)
    else:
        import daemonify
        daemonify.process(psu, Config)



# EOF
