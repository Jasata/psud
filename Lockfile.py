#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# main.py - Jani Tammi <jasata@utu.fi>
#   0.1.0   2018.11.15  Initial version.
#   0.2.0   2018.11.18  Static status methods added.
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
                # Action failed due to locking
                pid = self.fd.readline()
                raise Lockfile.AlreadyRunning(
                    pid or "unknown",
                    "Another process already running!"
                ) from None
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


    @staticmethod
    def lockfilestatus(filename: str) -> tuple:
        """Checks if lock file exists and if the file is locked. (exists, locked). NOTE: Can also raise PermissionError (13), if the daemon has been started as another user (or super user). This condition is to be handled by the caller."""
        if not os.path.isfile(filename):
            return (False, False)
        # Exists - test for a lock
        try:
            fd = open(filename, 'a')
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            if e.errno == errno.EAGAIN:
                return (True, True)
        finally:
            try:
                fd.close()
            except:
                pass
        return (True, False)


    @staticmethod
    def lockfilestatusstring(filename: str) -> str:
        t = Lockfile.lockfilestatus(filename)
        if not t[0]:
            return "file does not exist!"
        if not t[1]:
            return "file not locked!"
        return "OK"



if __name__ == '__main__':

    filename = "/tmp/locktest.lock"
    def print_status(f):
        print(
            "{s:.<60} {p}".format(
                s=filename,
                p=Lockfile.lockfilestatusstring(filename)
            )
        )

    print("This WILL report 'Not locked!' because it is this same process that created the lock file and thus, for us, there will be no issues (re-)acquiring the same lock. Another process would report the lock correctly.")
    print_status(filename)
    try:
        with Lockfile(filename):
            print_status(filename)
            time.sleep(3)
    except Lockfile.AlreadyRunning as e:
        print(str(e))
    print_status(filename)



# EOF