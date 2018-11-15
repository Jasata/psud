#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU class client/tester
#
# IntervalScheduler.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.11.14  Initial version.
#
#
# Intervals for processing commands and for updating 'psu' table.
#
import time

class IntervalScheduler():
    # Event flags
    COMMAND = 0x01
    UPDATE  = 0x02

    class DotDict(dict):
        """dot.notation access to dictionary attributes"""
        __getattr__ = dict.get
        __setattr__ = dict.__setitem__
        __delattr__ = dict.__delitem__
        def __missing__(self, key):
            """Return None if non-existing key is accessed"""
            return None


    def __init__(
        self,
        command_interval    = 0.1,
        update_interval     = 0.5,
        time_window = 0.01
    ):
        now = time.time()
        self.Command                = self.DotDict()
        self.Command.INTERVAL       = command_interval
        self.Command.NEXTEVENT      = now + self.Command.INTERVAL
        self.Update                 = self.DotDict()
        self.Update.INTERVAL        = update_interval
        self.Update.NEXTEVENT       = now + self.Update.INTERVAL
        self.time_window            = time_window


    def restart(self):
        """Simply reset .NEXTEVENT timestamps"""
        now = time.time()
        self.Command.NEXTEVENT  = now + self.Command.INTERVAL
        self.Update.NEXTEVENT   = now + self.Update.INTERVAL


    def update(self, interval = None):
        """Give no arguments to 'get', give an argument to 'set'"""
        if interval is not None:
            self.Update.INTERVAL = interval
        return self.Update.INTERVAL


    def next(self):
        """Sleep until next event(s) and return them as flags"""
        now = time.time()
        # next event is the one with smallest triggering time
        next_event = min(
            self.Command.NEXTEVENT,
            self.Update.NEXTEVENT
        )
        # Sleep until next triggered event (skip negative duration)
        sleep_duration = next_event - now
        if sleep_duration > 0:
            time.sleep(sleep_duration)
        # trigger_time is the time *before* which events are triggered
        trigger_time = now + self.time_window
        events = 0x00
        # Compile fields and reschedule events that fired
        if self.Command.NEXTEVENT < trigger_time:
            events |= self.COMMAND
            self.Command.NEXTEVENT += self.Command.INTERVAL
        if self.Update.NEXTEVENT < trigger_time:
            events |= self.UPDATE
            self.Update.NEXTEVENT += self.Update.INTERVAL

        return events


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        pass


# EOF