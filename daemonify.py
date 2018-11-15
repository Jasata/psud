#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# deamonify.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.11.14  Initial version.
#
#
# Module that implements minimal Linux daemonification.
#
import os
import sys
import time
import errno
import fcntl


__daemon_name__ = "psud"

def terminate():
    #syslog.critical('OBCED terminating...')
    sys.exit(0)

def sigusr1():
    #syslog.info("Unimplemented SIGUSR1 caught")
    pass

def silentremove(filename):
    try:
        os.remove(filename)
    except OSError as e:
        # raise if other than "no such file or directory" exception
        if e.errno != errno.ENOENT:
            raise


#
# Daemonify the process
#
def process(function, config):
    """Requires a 'function' that accepts one argument, the 'config' class."""

    #
    # Spawn daemon process with fork()
    #
    process_id = os.fork()
    if process_id < 0:
        # fork() failed
        print("os.fork() failure! Cannot deamonify!")
        os._exit(-1)
    elif process_id != 0:
        # fork() success. This is parent. Report and close.
        print("Daemon process launched. Exiting.")
        os._exit(0)



    ###########################################################################
    #
    # Daemon process
    #

    #
    # TODO: syslog
    #

    # Stop listening for signals that the parent process receives.
    # This is done by getting a new process id.
    # setpgrp() is an alternative to setsid().
    # setsid puts the process in a new parent group and detaches its
    # controlling terminal.
    process_id = os.setsid()
    if process_id == -1:
        # Uh oh, there was a problem.
        # syslog.report()
        os._exit(-1) # sys.exit(1)


    #
    # Close file descriptors
    #
    devnull = '/dev/null'
    if hasattr(os, "devnull"):
        # Python has set os.devnull on this system, use it instead 
        # as it might be different than /dev/null.
        devnull = os.devnull
    null_descriptor = open(devnull, 'rw')
    for descriptor in (sys.stdin, sys.stdout, sys.stderr):
        descriptor.close()
        descriptor = null_descriptor


    #
    # Set umask to default to safe file permissions when running
    # as a root daemon. 027 is an octal number.
    os.umask(0o027)


    #
    # Normally, daemons change working directory to '/', in order to avoid
    # blocking directory removal operations.
    #
    # WE ARE DIFFERENT
    # We MUST block such delete attempts, because we are dependent on the
    # database file.
    os.chdir(config.PSU.Daemon.directory)


    #
    # Lock and PID files
    #
    # Debian policy dictates that lock files go to '/var/lock/{name}.lock'
    # and PID files go to '/var/run/{name}.pid'.
    #
    try:
        lockfile = open("/var/lock/{}.lock".format(__daemon_name__), 'w')
        pidfile  = open("/var/run/{}.pid".format(__daemon_name__), "w")
        # Get an exclusive lock on files. Fails if another process has
        # the files locked.
        fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.lockf(pidfile,  fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Record the process id to pid and lock files.
        lockfile.write('%s' %(os.getpid()))
        lockfile.flush()
        pidfile.write('%s' %(os.getpid()))
        pidfile.flush()
    except Exception as e:
        # TODO: log exception
        try:
            silentremove(lockfile)
            silentremove(pidfile)
        except:
            pass
        os._exit(-1)



    # PID file TODO

    # Logging.  Current thoughts are:
    # 1. Attempt to use the Python logger (this won't work Python < 2.3)
    # 2. Offer the ability to log to syslog
    # 3. If logging fails, log stdout & stderr to a file
    # 4. If logging to file fails, log stdout & stderr to stdout.

    #
    # Enter main loop
    #
    function(config)


    #
    # Returned from main loop
    #

    # Remove pid and lock files
    # TODO rm lockfile
    # TODO rm pidfile

    # Close logging



# EOF