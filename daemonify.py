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
import syslog

from Lockfile       import Lockfile


__daemon_name__ = "patemon.psud"

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

    try:
        syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_DAEMON)
        syslog.syslog(syslog.LOG_ERR, "Daemon initializing...")

        # Stop listening for signals that the parent process receives.
        # This is done by getting a new process id.
        # setpgrp() is an alternative to setsid().
        # setsid puts the process in a new parent group and detaches its
        # controlling terminal.
        process_id = os.setsid()
        if process_id == -1:
            syslog.syslog(syslog.LOG_ERR, "Unable to set session ID!")
            os._exit(-1) # sys.exit(1)


        #
        # Close stdio,stdout and stderr file descriptors
        #
        null_descriptor = open('/dev/null', 'w+')
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
        os.chdir(config.PSU.Daemon.run_directory)


        #
        # Lock and PID files
        #
        # Debian policy dictates that lock files go to '/var/lock/{name}.lock'
        # and PID files go to '/var/run/{name}.pid' ... BUT this applied to
        # daemons that start/run as 'root'. We are using configured directory.
        #
        try:
            lockfilepath = "{}/{}.lock".format(
                config.PSU.Daemon.lock_directory,
                __daemon_name__
            )
            lockfile = open(lockfilepath, 'w')
            # Get an exclusive lock on files. Fails if another process has
            # the files locked.
            fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Record the process id to pid and lock files.
            lockfile.write('%s' %(os.getpid()))
            lockfile.flush()
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Unable to create lock file!")
            try:
                silentremove(lockfile)
            except:
                pass
            os._exit(-1)

    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Daemon initialization failed!")
        syslog.syslog(syslog.LOG_ERR, str(e))
        os._exit(-1)


    #
    # Enter main loop
    #
    try:
        with Lockfile("/tmp/{}.lock".format(config.PSU.Daemon.name))
            function(config)
    except Lockfile.AlreadyRunning as e:
        syslog.syslog(syslog_LOG_ERR, str(e))
        os._exit(-1)
    except Exceptionas as e:
        syslog.syslog(
            syslog.LOG_ERR,
            "Daemon routine exits with an exception! " + str(e)
        )
        # ...hoping it will be logged...
        raise


    #
    # Returned from main loop
    #
    syslog.syslog(syslog.LOG_DAEMON, "Exiting...")



# EOF