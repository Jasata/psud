#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PATE Monitor / Development Utility 2018
# Post-git-clone script
# Setup Agilent PSU controller daemon
#
# setup.py - Jani Tammi <jasata@utu.fi>
#   0.1.0   2019.06.13  Initial version.
#
import os
import getpass
import sqlite3
import pathlib
import logging
import argparse
import subprocess

# PEP 396 -- Module Version Numbers https://www.python.org/dev/peps/pep-0396/
__version__ = "0.1.0"
__author__  = "Jani Tammi <jasata@utu.fi>"
VERSION = __version__
HEADER  = """
=============================================================================
University of Turku, Department of Future Technologies
ForeSail-1 / PATE Monitor PSU daemon setup script
Version {}, 2019 {}
""".format(__version__, __author__)

from Config import Config


__service_file_content = """
[Unit]
Description=Pate Monitor / PSU Control Daemon
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User={}
ExecStart={}

[Install]
WantedBy=multi-user.target
""".format(
    Config.PSU.Daemon.process_owner,
    os.path.dirname(os.path.realpath(__file__)) + "/psud --systemd"
)



def do_or_die(cmd: list):
    prc = subprocess.run(cmd.split(" "))
    if prc.returncode:
        print("Command '{}' failed!".format(cmd))
        os._exit(-1)


def get_daemon_pid():
    """Get a LIST of PIDs that run 'python3 ./psud'"""
    pass

if __name__ == '__main__':

    #
    # MUST be executed as root!
    #
    if os.geteuid() != 0:
        print("This script MUST be executed as 'root'!")
        os._exit(-1)


    #
    # Commandline arguments
    #
    parser = argparse.ArgumentParser(
        description     = HEADER,
        formatter_class = argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-l',
        '--log',
        help    = "Set logging level. Default: '{}'".format(Config.logging_level),
        choices = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        nargs   = '?',
        dest    = "logging_level",
        const   = "INFO",
        default = Config.logging_level,
        type    = str.upper,
        metavar = "LEVEL"
    )
    parser.add_argument(
        '--force',
        help    = 'Delete existing database file and recreate.',
        action  = 'store_true'
    )
    parser.add_argument(
        '--dev',
        help    = 'Generate development content.',
        action  = 'store_true'
    )
    args = parser.parse_args()
    Config.logging_level = getattr(logging, args.logging_level)


    #
    # Set up logging
    #
    logging.basicConfig(
        level       = Config.logging_level,
        filename    = "setup.log",
        format      = "%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
        datefmt     = "%H:%M:%S"
    )
    log = logging.getLogger()


    #
    # Prerequisites for setting up the daemon
    #
    # 1. Not running currently
    print("TODO: Check that no processes of this script are executing")
    # cat /proc/[pid]/cmdline => "python3./psud" ...it seems...
    if args.force:
        print("TODO: Kill all psud script executing python3 processes")

    #
    # 2. Create systemd service file
    #
    try:
        with open("/etc/systemd/system/psud.service", "w+") as service_file:
            service_file.write(__service_file_content)
    except Exception as e:
        print("Systemd service file creation failed!")
        print(str(e))
        os._exit(-1)
    # Enable to the service
    do_or_die("systemctl enable psud")
    # ...and start it
    do_or_die("systemctl start psud")


# EOF