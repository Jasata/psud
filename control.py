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

# Device class 'PSU' raises serial.SerialTimeoutException on BOTH
# read and write timeouts. They need to be caught specially.
from serial import SerialTimeoutException, SerialException

# Number of consecutive Exceptions allowed before exiting
_retry_count = 3

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
        psu = PSU(Config.PSU.Serial.port)
        with \
            Database(Config.database_file) as db, \
            IntervalScheduler(
                command_interval = Config.PSU.Daemon.Interval.command,
                update_interval  = Config.PSU.Daemon.Interval.update
            ) as event:
            log.info("Entering main loop...")
            log.debug("PSU at port '{}'".format(psu.port.name))
            consecutive_error_count = 0
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
                        # cmd_receipt is a tuple of (success: boolean, value)
                        # command interface will be modified to support this...
                        try:
                            now = time.time()

                            if cmd[1] == "SET VOLTAGE":
                                psu.voltage = float(cmd[2])
                                cmd_receipt = (True, str(psu.voltage))

                            elif cmd[1] == "SET CURRENT LIMIT":
                                psu.current_limit = float(cmd[2])
                                cmd_receipt = (True, str(psu.current_limit))

                            elif cmd[1] == "SET POWER":
                                psu.power = (cmd[2] == "ON")
                                cmd_receipt = (True, ("OFF", "ON")[psu.power])

                        except KeyboardInterrupt:
                            # re-raise to exit
                            cmd_receipt = (False, "CTRL-C Keyboard Interrupt!")
                            raise
                        except SerialTimeoutException:
                            cmd_receipt = (False, "Serial Timeout!")
                            if consecutive_error_count > _retry_count:
                                raise
                            # Retry count not exceeded, increment
                            consecutive_error_count += 1
                        except Exception as e:
                            cmd_receipt = (False, str(e).replace('\n', '\\n'))
                            if consecutive_error_count > _retry_count:
                                raise
                            # Retry count not exceeded, increment
                            consecutive_error_count += 1
                        else:
                            # On success, reset error count
                            consecutive_error_count = 0
                        finally:
                            # TODO: Add success: boolean to Database.close()
                            db.command.close(cmd[0], cmd_receipt[1])
                            if cmd_receipt[0]:
                                log.debug(
                                    "PSU:{} took {:1.3f} ms".format(
                                        cmd[1], (time.time() - now)  * 1000
                                    )
                                )
                            else:
                                log.error(
                                    "PSU:{} failed! (error count: {}/{})".format(
                                        cmd[1],
                                        consecutive_error_count,
                                        _retry_count
                                    )
                                )

                #
                # 'psu' table update event
                #
                if events & IntervalScheduler.UPDATE:
                    now = time.time()
                    try:
                        db.psu.update(psu.values)
                    except KeyboardInterrupt:
                        # re-raise to exit
                        raise
                    except:
                        consecutive_error_count += 1
                        log.error(
                            "PSU:update failed! (error count: {}/{})".format(
                                consecutive_error_count, _retry_count
                            )
                        )
                        if consecutive_error_count >= _retry_count:
                            raise
                    else:
                        consecutive_error_count = 0
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
    except SerialTimeoutException as e:
        # Case 1: USB-serial adapter has disconnected
        if not os.path.exists(psu.port.name):
            log.error(
                "USB Serial Adapter '{}' disconnected!".format(
                    psu.port.name
                )
            )
        # Case (all others): Unknown reason
        else:
            log.error("Repeated serial timeouts!")
            #raise
    except SerialException as e:
        # Case 1: USB-serial adapter has disconnected
        if not os.path.exists(psu.port.name):
            log.error(
                "USB Serial Adapter '{}' disconnected!".format(
                    psu.port.name
                )
            )
        # Case (all others): Unknown reason
        else:
            log.error("Unusual SerialException!")
            raise
    except Exception as e:
        # Terminating due to exception
        log.error("Abnormal termination!")
        raise

# EOF
