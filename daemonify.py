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
import signal
import syslog           # for 1st child
import logging          # for 2nd child (the daemon proper)
import logging.handlers

from Lockfile       import Lockfile


__daemon_name__ = "patemon.psud"

def sigterm(signum, frame):
    from Config import Config
    log = logging.getLogger(Config.PSU.Daemon.name).info("Terminating...")
    # To-do : remove psu row + commit
    sys.exit(0)

def sighup(signum, frame):
    from Config import Config
    log = logging.getLogger(Config.PSU.Daemon.name).info("SIGHUP...")
    pass

# def silentremove(filename):
#     try:
#         os.remove(filename)
#     except OSError as e:
#         # raise if other than "no such file or directory" exception
#         if e.errno != errno.ENOENT:
#             raise


#
# Daemonify the process
#
def process(function, config):
    """Requires a 'function' that accepts one argument, the 'config' class."""

    #
    # Spawn first child process
    #
    process_id = os.fork()
    if process_id < 0:
        print("os.fork() failure! Cannot deamonify!")
        os._exit(-1)
    elif process_id != 0:
        # NOTE: None of this makes any sense with double-forking.
        # print("Daemon process launched (PID: {}).".format(process_id))
        # #
        # # Wait to see if the child pid is still alive after awhile.
        # # This "trick" works because we cannot be in a position where we
        # # would lack the privileges to send a signal to our own child.
        # #
        # time.sleep(1.0)
        # try:
        #     os.kill(process_id, 0)
        # except OSError:
        #     print("Daemon process has died! Check logs!")
        # else:
        #     print("Daemon appears to run normally. Exiting...")
        os._exit(0)


    ###########################################################################
    #
    # First child process
    #
    try:
        #
        # Set up logging
        #
        log = logging.getLogger(config.PSU.Daemon.name)
        log.setLevel(logging.INFO)
        sysloghandler = logging.handlers.SysLogHandler(
            address='/dev/log',
            facility=logging.handlers.SysLogHandler.LOG_DAEMON
        )
        formatter = logging.Formatter(
            '%(asctime)s %(name)s[%(process)d]: %(message)s', '%b %e %H:%M:%S'
        )
        sysloghandler.setFormatter(formatter)
        log.addHandler(sysloghandler)


        # Dissociate from (parent's) controlling terminal. Signals from
        # dissociated terminal will not reach this new session - which does not
        # /yet/ have a controlling terminal of it's own.
        if os.setsid() == -1:
            log.error("Unable to create a new session!")
            os._exit(-1)
        # Because session leader (we, after the os.setsid() above) can acquire
        # a new controlling terminal simply by opening a tty device, we want to
        # create another child process that is quaranteed not to be a session
        # leader (because we are the leader now), and which will NOT get a
        # controlling terminal (accidentally) just by opening tty devices (such
        # as serial ports, perhaps...).
        # All this is related to zombie processes. Read more at:
        # http://www.microhowto.info/howto/cause_a_process_to_become_a_daemon.html
        process_id = os.fork()
        if process_id < 0:
            log.error("os.fork() failure! Cannot deamonify!")
            os._exit(-1)
        elif process_id != 0:
            # As a group and session leader, this exit WILL send SIGHUP, which
            # must be ignored by the child (at least, this first time).
            os._exit(0)


    except Exception as e:
        log.exception("Daemonization failure! " + str(e))
        os._exit(-1)


    ###########################################################################
    #
    # Daemon process (second child process)
    #
    try:
        log.info("PATE Monitor PSU Daemon initializing...")

        #
        # Normally, daemons change working directory to '/', in order to avoid
        # blocking directory removal operations.
        #
        # We actually WANT TO block operations directed at the location of our
        # database file and thus set a (Config.py) working directory accordinly.
        #
        os.chdir(config.PSU.Daemon.working_directory)

        #
        # Set umask
        #
        os.umask(0o027)

        #
        # Close stdio,stdout and stderr file descriptors
        #
        null_descriptor = open('/dev/null', 'w+')
        for descriptor in (sys.stdin, sys.stdout, sys.stderr):
            descriptor.close()
            descriptor = null_descriptor

        #
        # Basic signal handler(s)
        #
        signal.signal(signal.SIGTERM, sigterm)
        signal.signal(signal.SIGHUP,  sighup)

    except Exception as e:
        log.error("Initialization failure! " + str(e))
        os._exit(-1)


    #
    # Enter main loop with lock file
    #
    # Debian policy dictates that lock files go to '/var/lock/{name}.lock'
    # and PID files go to '/var/run/{name}.pid' ... BUT this applied to
    # daemons that start/run as 'root'.
    #
    # We are using configured directory and only a lock file, with PID in it.
    #
    try:
        with Lockfile("/tmp/{}.lock".format(config.PSU.Daemon.name)):
            function(config)
    except Lockfile.AlreadyRunning as e:
        log.error(str(e) + " Exiting!")
        os._exit(-1)
    except Exception as e:
        log.exception("Daemon routine exits with an exception!")
        os._exit(-1)


    #
    # Returned from main loop
    #
    log.error("Daemon exited main loop! Should never happen!")



# EOF