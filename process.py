#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# process.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.11.14  Initial version.
#   0.2     2018.11.17  Renamed from 'daemonify' to 'process'.
#   0.3     2018.11.18  Added status methods.
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
import logging
import logging.handlers

# Config module was loaded by 'psud.py' and not unloaded.
# For this purpose, the changes made to the class persist
# when 'Config.py' is loaded again by this module.
from Config         import Config
from Lockfile       import Lockfile



def pid():
    """Returns psud pid, if lock file exists and a process (identified by the PID in the lock file) exists, or otherwise 'None'."""
    try:
        with open(Config.PSU.Daemon.lockfile, "r") as lockfile:
            return int(lockfile.readline())
    except:
        return None


def is_running(pid):
    try:
        os.kill(pid, 0)
    except:
        return False
    else:
        return True


def kill():
    """Reads PID from a lockfile, kills pid and removed lockfile."""
    def rm(filename):
        try:
            os.remove(filename)
        except OSError:
            pass
    lockfilename = Config.PSU.Daemon.lockfile
    try:
        with open(lockfilename, "r") as lockfile:
            pid = int(lockfile.readline())
            #
            # Check for stale lockfile
            #
            try:
                os.kill(pid, 0)
            except OSError:
                print(
                    "Stale lockfile. Daemon (pid: {}) does not exist.".format(
                        pid
                    )
                )
                print(
                    "Removing stale lockfile '{}'".format(
                        lockfilename
                    )
                )
                rm(lockfilename)
                os._exit(0)
            #
            # PID is running, proceed in killing it
            #
            print("Terminating pid {}...".format(pid))
            os.kill(pid, signal.SIGTERM)
            # Try to verify kill (not sure if os.kill() returns immediately)
            for _ in range(50):
                try:
                    os.kill(pid, 0)
                except OSError:
                    rm(lockfilename)
                    print("Daemon killed.")
                    os._exit(0)
                else:
                    time.sleep(0.05)
            # Strange - process seems to be still alive
            print("ERROR: Process ({}) seems to be still alive!".format(pid))
    except FileNotFoundError:
        print("ERROR: No lock file ('{}') for the daemon!".format(
            lockfilename
            )
        )
        os._exit(-1)
    except ValueError:
        print("ERROR: Content of the lock file is not a valid process id!")
        os._exit(-1)
    except OSError:
        print(
            "ERROR: pid ({}) does not respond to SIGTERM.".format(
                pid or "unknown"
            )
        )
        os._exit(-1)


def status():
    """Display daemon status'es for database, lockfile and process."""
    def display_time(seconds, granularity = 2):
        """Human readable time span."""
        intervals = (
            ('weeks',   604800),  # 60 * 60 * 24 * 7
            ('days',    86400),   # 60 * 60 * 24
            ('hours',   3600),    # 60 * 60
            ('minutes', 60),
            ('seconds', 1),
        )
        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(value, name))
            else:
                # Add a blank if we're in the middle of other values
                if len(result) > 0:
                    result.append(None)
        return ', '.join([x for x in result[:granularity] if x is not None])


    from Database import Database
    width = 60
    print("PSU Daemon Status:")
    # database file
    print(
        "{s:.<{w}} {p}".format(
            w=width,
            s="Database file '{}'".format(
                Config.database_file
            ),
            p=Database.filestatusstring(Config.database_file)
        )
    )
    # psu -table status
    print(
        "{s:.<{w}} {p}".format(
            w=width,
            s="PSU table",
            p=Database.psutablestatusstring(Config.database_file)
        )
    )
    # psu -table content age
    # if over 10 seconds older than update interval, NOT OK
    update_age  = Database.lastupdate(Config.database_file)
    allowed_age = Config.PSU.Daemon.Interval.update + 10
    if not update_age:
        status_msg = "no data!"
    elif update_age > allowed_age:
        status_msg = "Old data! (" + display_time(update_age) + ")"
    else:
        status_msg = "OK"
    print(
        "{s:.<{w}} {p}".format(
            w=width,
            s="PSU data age",
            p=status_msg
        )
    )
    # lockfile
    try:
        status_msg = Lockfile.lockfilestatusstring(Config.PSU.Daemon.lockfile)
    except PermissionError as e:
        if e.errno == errno.EACCES:
            status_msg = "no access - daemon started by different user!"
        else:
            raise
    print(
        "{s:.<{w}} {p}".format(
            w=width,
            s="Lock file '{}'".format(
                Config.PSU.Daemon.lockfile
            ),
            p=status_msg
        )
    )
    # process
    process_id = pid()
    print(
        "{s:.<{w}} {p}".format(
            w=width,
            s="Process (PID: {})".format(
                process_id or "unknown"
            ),
            p="OK" if is_running(process_id) else "not running!"
        )
    )




#
# Signal handler functions
#
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

###############################################################################
#
# Start main loop - as a daemon or within this process
#
###############################################################################

#
# Run the main loop in this process
#
def start_regular_process(function):
    """Change directory, create lock file, run."""

    try:
        os.chdir(Config.PSU.Daemon.working_directory)
    except Exception as e:
        print(
            "Unable to change directory to '{}'!\n".format(
                Config.PSU.Daemon.working_directory
            )
        )
        print(str(e))
        os._exit(-1)


    #
    # Set up logging
    #
    log = logging.getLogger(Config.PSU.Daemon.name)
    log.setLevel(Config.logging_level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='%(asctime)s.%(msecs)03d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    log.addHandler(handler)


    #
    # Execute main loop
    #
    try:
        from Lockfile import Lockfile
        with Lockfile(Config.PSU.Daemon.lockfile):
            function()
    except Lockfile.AlreadyRunning as e:
        log.error(str(e))
    except Exception as e:
        log.exception("Main loop ended with an exception!")
    else:
        log.info("Normal termination.")



#
# Daemonify the process
#
def daemonify(function):
    """Requires a 'function' that takes no arguments."""

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
        log = logging.getLogger(Config.PSU.Daemon.name)
        log.setLevel(Config.logging_level)
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
        os.chdir(Config.PSU.Daemon.working_directory)

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
        with Lockfile(Config.PSU.Daemon.lockfile):
            function()
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