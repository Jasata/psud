#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# main.py - Jani Tammi <jasata@utu.fi>
#   0.1.0   2018.11.15  Initial version.
#
#
# Provide a combined lock/PID file for user space daemon.
#
import os
import sys
import time
import fcntl
import errno


class Lockfile:
    class AlreadyRunning(Exception):
        def __init__(self, pid = None, message = "Already running!"):
            super().__init__(message)
            self.message    = message
            self.pid        = pid
        def __str__(self):
            return self.message + " (PID: {})".format(self.pid or "unknown")

    def __init__(self, name: str):
        """Create a lock file and write current PID into it."""
        self.name = name
        try:
            try:
                self.fd = open(self.name, 'r+') # Open existing, do not tuncate
            except FileNotFoundError:
                self.fd = open(self.name, 'w+') # Create and truncate
            # Get an exclusive lock. Fails if another process has the files locked.
            fcntl.lockf(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Record the process id to pid and lock files.
            self.fd.write("{}".format(os.getpid()))
            self.fd.flush()
        except BlockingIOError as e:
            if e.errno == errno.EAGAIN:
                pid = self.fd.readline()
                raise Lockfile.AlreadyRunning(pid, "Another process already running!") from None
        except Exception as e:
            raise


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # raise if other than "no such file or directory" exception
        try:
            os.remove(self.name)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise





if __name__ == '__main__':

    try:
        with Lockfile("/tmp/locktest.lock"):
            time.sleep(10)
    except Lockfile.AlreadyRunning as e:
        print(str(e))



# EOF