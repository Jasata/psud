#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# control.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.11.14  Initial version.
#
#
# Loop that processess 'command' table rows into SCPI commands
# and keeps updating the 'psu' table.
#
# NOTE: print()'s seem to crash the deamon, although stdout is /dev/null
#
import os
import sys
import logging

from IntervalScheduler  import IntervalScheduler
from Database           import Database
from PSU                import PSU



def ticker():
    """Rotating character. Used only on non-daemon case."""
    try:
        c = ('|', '/', '-', '\\')[ticker.value]
        ticker.value += 1
    except:
        ticker.value = 0
        ticker()
    else:
        print("\r[{}]".format(c), end="", flush=True)


    # def display_psu(row: tuple):
    #     print(
    #         "\r{:>3} {:0.03f}/{:0.03f} V {:0.03f}/{:0.03f} A "
    #         .format(
    #             row[1],
    #             row[5],
    #             row[2],
    #             row[4],
    #             row[3]
    #         ),
    #         end="",
    #         flush=True
    #     )
def psu(config):
    try:
        psu = PSU(config.PSU.port)
        with \
            Database(config.database_file) as db, \
            IntervalScheduler(
                command_interval    = config.PSU.Daemon.Interval.command,
                update_interval     = config.PSU.Daemon.Interval.update
            ) as event:
            while True:
                #ticker()
                events = event.next()
                if events & IntervalScheduler.COMMAND:
                    # (id, command, value)
                    cmd = db.command.next()
                    if cmd:
                        #print(cmd)
                        if cmd[1] == "SET VOLTAGE":
                            try:
                                psu.voltage = float(cmd[2])
                            except Exception as e:
                                db.command.close(
                                    cmd[0],
                                    str(e).replace('\n', '\\n')
                                )
                            else:
                                db.command.close(
                                    cmd[0],
                                    str(psu.voltage)
                                )
                        elif cmd[1] == "SET CURRENT LIMIT":
                            try:
                                psu.current_limit = float(cmd[2])
                            except Exception as e:
                                db.command.close(
                                    cmd[0],
                                    str(e).replace('\n', '\\n')
                                )
                            else:
                                db.command.close(
                                    cmd[0],
                                    str(psu.current_limit)
                                )
                        elif cmd[1] == "SET POWER":
                            try:
                                psu.power = (cmd[2] == "ON")
                            except Exception as e:
                                db.command.close(
                                    cmd[0],
                                    str(e).replace('\n', '\\n')
                                )
                            else:
                                db.command.close(
                                    cmd[0],
                                    ("OFF", "ON")[psu.power]
                                )
                if events & IntervalScheduler.UPDATE:
                    db.psu.update(psu.values)
    except KeyboardInterrupt:
        # print() is OK here, because daemon code can never receive KeyboardInterrup
        print("\nTerminated with CTRL-C")
        pass


# EOF
