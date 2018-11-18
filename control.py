#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Turku University (2018) Department of Future Technologies
# Foresail-1 / PATE Monitor / Middleware (PMAPI)
# PSU controller daemon
#
# control.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.11.14  Initial version.
#   0.2     2018.11.18  Added status 
#
#
# Loop that processess 'command' table rows into SCPI commands
# and keeps updating the 'psu' table.
#
# NOTE: print()'s seem to crash the deamon, although stdout is /dev/null
#
import os
import sys
import time
import logging

# Application specific
from Config             import Config
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



def psu():
    """PSU controller main loop."""
    try:
        log = logging.getLogger(Config.PSU.Daemon.name)
        psu = PSU(Config.PSU.port)
        with \
            Database(Config.database_file) as db, \
            IntervalScheduler(
                command_interval = Config.PSU.Daemon.Interval.command,
                update_interval  = Config.PSU.Daemon.Interval.update
            ) as event:
            log.info("Entering main loop...")
            lastupdate = time.time()
            while True:
                if not Config.PSU.Daemon.run_as_daemon:
                    ticker()
                events = event.next()
                #
                # 'command' table read event
                #
                if events & IntervalScheduler.COMMAND:
                    # (id, command, value)
                    cmd = db.command.next()
                    if cmd:
                        now = time.time()
                        log.info(cmd)
                        if cmd[1] == "SET VOLTAGE":
                            try:
                                psu.voltage = float(cmd[2])
                            except Exception as e:
                                log.exception("PSU:SET VOLTAGE failed!")
                                db.command.close(
                                    cmd[0],
                                    str(e).replace('\n', '\\n')
                                )
                            else:
                                db.command.close(
                                    cmd[0],
                                    str(psu.voltage)
                                )
                                log.debug(
                                    "PSU:command '{}' took {:1.3f} ms".format(
                                        cmd[1], (time.time() - now)  * 1000
                                    )
                                )
                        elif cmd[1] == "SET CURRENT LIMIT":
                            try:
                                psu.current_limit = float(cmd[2])
                            except Exception as e:
                                log.exception("PSU:SET CURRENT LIMIT failed!")
                                db.command.close(
                                    cmd[0],
                                    str(e).replace('\n', '\\n')
                                )
                            else:
                                db.command.close(
                                    cmd[0],
                                    str(psu.current_limit)
                                )
                                log.debug(
                                    "PSU:command '{}' took {:1.3f} ms".format(
                                        cmd[1], (time.time() - now)  * 1000
                                    )
                                )
                        elif cmd[1] == "SET POWER":
                            try:
                                psu.power = (cmd[2] == "ON")
                            except Exception as e:
                                log.exception("PSU:SET POWER failed!")
                                db.command.close(
                                    cmd[0],
                                    str(e).replace('\n', '\\n')
                                )
                            else:
                                db.command.close(
                                    cmd[0],
                                    ("OFF", "ON")[psu.power]
                                )
                                log.debug(
                                    "PSU:command '{}' took {:1.3f} ms".format(
                                        cmd[1], (time.time() - now)  * 1000
                                    )
                                )
                #
                # 'psu' table update event
                #
                if events & IntervalScheduler.UPDATE:
                    now = time.time()
                    try:
                        db.psu.update(psu.values)
                    except:
                        log.exception("PSU:update failed!")
                    else:
                        log.debug(
                            "PSU:update took {:1.3f} ms, previous {:1.1f} ms ago".format(
                                (time.time() - now)  * 1000,
                                (now - lastupdate) * 1000
                            )
                        )
                        lastupdate = now
    except KeyboardInterrupt:
        # print() would be OK here, because daemon code
        # can never receive KeyboardInterrupt
        log.info("Terminated with CTRL-C")
        pass


# EOF
