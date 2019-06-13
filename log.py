#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# PATE Monitor / Agilent PSU Controller
#
# log.py - Jani Tammi <jasata@utu.fi>
#
#   0.1.0   2019.06.13  Initial version.
#
#
# Global logging solution. Depends on Config.py, initializes on first import.
# Alternations to Config.py:Config MUST BE MADE PRIOR TO IMPORTING THIS MODULE!
# Usage:
#
# import log
#
# log.debug("blah blah")
# log.info("Herring is a fish")
# log.error("Does not work!")
#
import sys
import logging

from Config import Config

# Module private
__log           = logging.getLogger(Config.PSU.Daemon.name)

#
# Initialization (daemon or not-a-daemon)
#
def init():
    global __handlerSyslog
    global __handlerStdout

    __log.setLevel(Config.logging_level)
    if Config.PSU.Daemon.run_as_daemon:
        __handlerSyslog = logging.handlers.SysLogHandler(
            address='/dev/log',
            facility=logging.handlers.SysLogHandler.LOG_DAEMON
        )
        formatter = logging.Formatter(
            '%(asctime)s %(name)s[%(process)d]: %(message)s',
            '%b %e %H:%M:%S'
        )
        __handlerSyslog.setFormatter(formatter)
        __log.addHandler(__handlerSyslog)

    # By default, have stdout hander
    # Daemonification will dispose stdout messages
    __handlerStdout = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s.%(msecs)03d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    __handlerStdout.setFormatter(formatter)
    __log.addHandler(__handlerStdout)


def remove_std_handler():
    """Remove STDOUT stream handler from logger."""
    __log.removeHandler(__handlerStdout)

#
# Wrappers
#
def debug(msg, *args, **kwargs):
    __log.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    __log.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    __log.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    __log.error(msg, *args, **kwargs)

def exception(msg, *args, **kwargs):
    __log.exception(msg, *args, **kwargs)


# EOF