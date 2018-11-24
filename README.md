# psud - Agilent PSU controller daemon for PATE Monitor

This solution implements minimal RS-232 remote control of Agilent E3631 power supply.

psud runs as a daemon (unless `--nodaemon` is specified) and connects to PATE Monitor SQLite database to monitor and process "PSU" commands and to periodically update the `psu` table with settings and measured voltage and current values.

All code, with the exception of `PSU.py`, are written by Jani Tammi and copyrighted under MIT license. The interface class `PSU.py` is written by *NAME* and is copyrighted under *LICENSE*. The project repository for this this file is *REPOSITORY*. (to be updated once PSU interface class is completed by the assigned programmer).

## Why not PEP 3143? (Standard daemon process library)

This implementation does not use standard python [daemon module](https://pypi.org/project/python-daemon/) (as specified by [PEP 3143](https://www.python.org/dev/peps/pep-3143/) because it is not part of the [standard library](https://docs.python.org/3/library/) of Python version 3.5.3 (the target platform for this solution and default Python version for Debian 9 based systems). It was supposed to be. PEP 3143 was released already on January 26, 2009, but apparently no one took up the task of implementing the reference module for the PEP into acceptable version. As a result, no Python installation has a daemon module in its standard library. Possible reason for this can be read at [this blog post](https://dpbl.wordpress.com/2017/02/12/a-tutorial-on-python-daemon/).

The above means that the module that carries that mantle of PEP 3143 (or any other module that would implement daemonification) is automatically a dependency (and extra installable). The PATE Monitor project tries to keep the number of dependencies and separate installables to minimum reasonable number, and since the implementation of a daemon is relatively simple, the design decision has been to just write the daemonization code by my self, instead of adding another dependency and installable.

This implementation is also somewhat different to *most* daemons, as it is not supposed to be executed or started with super user privileges. Thus, for example, it has no access to `/var/run` (-> `/run`) or `/var/lock` (-> `/run/lock`). This might be configurable with the *python-daemon* module, but with this design approach we have full control of the implementation specifics and none of the potential pitfalls can compromise the outcome.

## Usage

This daemon is intended to be managed by PATE Monitor's System Daemon, but can be started/stopped manually, if necessary.

    usage: psud [-h] [-d [FILE]] [-l [LEVEL]] [-p [PORT]] [--nodaemon] [--kill] [--status]

    optional arguments:
      -h, --help                    show this help message and exit
      -d [FILE], --datafile [FILE]  PATE Monitor SQLite3 database. Default: '/srv/nginx-root/pmapi.sqlite3'
      -l [LEVEL], --log [LEVEL]     Set logging level. Default: INFO
      -p [PORT], --port [PORT]      Set serial port device. Default: 'auto'
      --nodaemon                    Do not execute as a daemon
      --kill                        Kill daemon
      --status                      Get status report about the daemon

Default values come from `Config.py`. There are no mandatory options.

**Option `-d`** specifies the SQLite3 database file that contains PATE Monitor data. Database must be readable and writable to `psud` daemon.

**Option `-l`** setting allows defining logging level (as used by module `logging`). Allowed values are; `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Recommended value is `INFO`, because `DEBUG` generates vast volumes of syslog content.

**Option `-p`** takes either a serial device (`/dev/ttyUSB0`, ...) or `auto`. If `auto` specified, the daemon will attempt to detect which of the system's serial ports has the Agilent power supply connected to. This is done by opening each port in the system with configured (`Config.py`) port parameters and issueing a SCPI command for firmware version query. In this implementation, Agilent E3631 is identified by known version number (`1995.0`). This strategy works for this specific use case, but should not be copied to other implementations as-is.

**Option `--nodaemon`** runs the program in the current terminal (and can be terminated with CTRL-C).

**Option `--kill`** reads a PID from lock file and attempts to issue SIGTERM to that process. *Due to pySerial specifics, this command may need to be repeated, in case the first happens exactly during serial read call.*

**Option `--status`** reports on the daemon process and the contents of `psu` table in the database.

## Single Instance Execution

This implementation uses a lock file scheme to avoid multiple instances from starting up. Because this daemon is expected to be executed with non-root privileges, the lock file cannot be located in the system default location. Instead, the lock file is placed into `/tmp` directory.

It is to be noted that if the user so wishes, he can remove a lock file and start up another copy of the daemon, but the implementation itself respects the lock file. Another running copy of the deamon is also unlikely to find another connected Agilent device...

## Update Intervals

Because the Agilent E3631 power supply only supports up to 9600 baud serial speed, the command-response cycles can be relatively long (can exceed 40 ms), the query and command intervals cannot be very short.

Agilent E3631 has serial configuration; `9600,8,N,2`.

    payload characters x bits per character / bits per second
    15 characters x (8 bits/Byte + 1 start bit + 2 stop bits) / 9600 bits per second
    = 15 x 11 / 9600 = 17,2 ms

    (approximately: 1,146 ms / character)

### Queries (for psu-table updates)

The `psu` table contains six fields that need to be updated each time. This means sending out 6 query commands and receiving 6 responses.

**Query Commands**

 - Qeury power status (`X` ? + 2 characters)
 - Query voltage setting (`Source:Voltage:Immediate?` 25 + 2 characters)
 - Query current limit (`Source:Current:Immediate?` 25 + 2 characters)
 - Query measured voltage (`Measure:Voltage?` 16 + 2 characters)
 - Query measured current (`Measure:Current?` 16 + 2 characters)
 - Query state (`X` ? + 2 characters)

*The 2 characters added in each command are the line terminator characters (`\r\n`).*

The query commands alone are 94 characters plus the query lengths for power status and state queries, which can be assumed to be on overage at least 16 characters each. Total being 126 characters or more. (This equals around 144,5 ms).

**Query Replies**

Responses are string representations of settings, measured values or device states:

 - Response power status (`d` 1 + 2 characters)
 - Response voltage setting (`dd.dddd` 7 + 2 characters)
 - Response current limit (`dd.dddd` 7 + 2 characters)
 - Response measured voltage (`dd.dddd` 7 + 2 characters)
 - Response measured current (`dd.dddd` 7 + 2 characters)
 - Response state (`X` 1 + 2 characters)

Responses equal to at least 42 characters, totaling around 48,2 ms.

**Total transmission time is around 192,7 ms or more - a safe assumption would be 200 ms.**

### Commands

The daemon is built to process one command (set voltage, set current limit, set power) each interval, which means that we are interested in the longest commmand-reply sequence. This is (most likely) the voltage setting command:

    Source:Voltage:Immediate dd.ddd

31 + 2 characters, with no reply at all, giving us around 37,9 ms. **Safe time allocation would be 40 ms.**

## Interval Values

A full cycle of populating the `psu` table and processing one command requires around 240 ms. This means that "update" events should not schedule more often than every 250 ms or more. This value is increased 40 ms for each "command" event that fired (or begins to lapse) during "update" interval.

For example, "command" intervals trigger every 100 ms, meaning that "update" interval needs to be at least 200 ms + all the "command" intervals during the total time.

    200 ms / 100 ms = 2 "command" cycles
    new "update" interval = 200 ms + 40 ms x 2 = 280 ms
    280 ms / 100 ms = 3 "command" cycles => 200 ms + 40 ms x 3 = 320 ms
    320 ms / 100 ms = 4 "command" cycles => 200 ms + 40 ms x 4 = 360 ms
    360 ms / 100 ms = 4 "command" cycles (!)

Usable interval values are thus; `psu` table updates every 360 ms and command processing every 100 ms. With these values, the should never be any skew. Event triggering window (allow early event triggering for the other event, if it would follow withing set time window) should be half of the command processing time (40 ms / 2 = 20 ms).

## Version 0.4.0 Testing Results

    Nov 18 16:52:04 nuc patemon.psud[3793]: PATE Monitor PSU Daemon initializing...
    Nov 18 16:52:04 nuc patemon.psud[3793]: Entering main loop...
    Nov 18 16:52:05 nuc patemon.psud[3793]: PSU:update took 216.449 ms, previous 500.3 ms ago
    Nov 18 16:52:06 nuc patemon.psud[3793]: PSU:update took 215.375 ms, previous 500.4 ms ago
    Nov 18 16:52:06 nuc patemon.psud[3793]: PSU:update took 218.895 ms, previous 499.6 ms ago
    Nov 18 16:52:07 nuc patemon.psud[3793]: PSU:update took 214.198 ms, previous 500.4 ms ago
    Nov 18 16:52:07 nuc patemon.psud[3793]: PSU:update took 214.786 ms, previous 499.6 ms ago
    Nov 18 16:52:08 nuc patemon.psud[3793]: PSU:update took 214.805 ms, previous 500.4 ms ago
    Nov 18 16:52:08 nuc patemon.psud[3793]: PSU:update took 215.326 ms, previous 499.6 ms ago
    Nov 18 16:52:08 nuc patemon.psud[3793]: Terminating...

    Nov 18 17:09:22 nuc patemon.psud[3830]: PSU:command 'SET VOLTAGE' took 128.585 ms
    Nov 18 17:09:29 nuc patemon.psud[3830]: PSU:command 'SET POWER' took 5.467 ms

Update took about 10% more than calculated, which is not too bad. However, `SET VOLTAGE` taking almost 130 ms is a concern (was supposed to take no more than 40 ms).

Shorthands should be used for general performance improvement and command processing needs to be examined in detail.

## Version 0.4.2 Testing Results

    Nov 25 00:04:11 nuc patemon.psud[27598]: PSU:update took 112.512 ms, previous 200.0 ms ago
    Nov 25 00:04:11 nuc patemon.psud[27598]: PSU:update took 113.231 ms, previous 200.0 ms ago
    Nov 25 00:04:11 nuc patemon.psud[27598]: PSU:update took 112.143 ms, previous 199.9 ms ago
    Nov 25 00:04:12 nuc patemon.psud[27598]: PSU:update took 112.470 ms, previous 200.1 ms ago
    Nov 25 00:04:12 nuc patemon.psud[27598]: PSU:update took 112.396 ms, previous 199.9 ms ago
    Nov 25 00:04:12 nuc patemon.psud[27598]: PSU:update took 113.131 ms, previous 200.1 ms ago
    Nov 25 00:04:12 nuc patemon.psud[27598]: PSU:update took 113.005 ms, previous 200.0 ms ago
    Nov 25 00:04:12 nuc patemon.psud[27598]: PSU:update took 112.515 ms, previous 199.8 ms ago

Updates are now as good as they need to be. This version also received a serial timeout handling features, along with retry count:

    Nov 25 00:26:57 nuc patemon.psud[28810]: PSU:update took 112.991 ms, previous 6000.0 ms ago
    Nov 25 00:27:03 nuc patemon.psud[28810]: PSU:update took 111.136 ms, previous 6000.0 ms ago
    Nov 25 00:27:09 nuc patemon.psud[28810]: PSU:update failed! (error count: 1/3)
    Nov 25 00:27:15 nuc patemon.psud[28810]: PSU:update took 115.180 ms, previous 12000.0 ms ago
    Nov 25 00:27:21 nuc patemon.psud[28810]: PSU:update took 115.622 ms, previous 6000.0 ms ago
    Nov 25 00:27:27 nuc patemon.psud[28810]: PSU:update took 114.805 ms, previous 6000.0 ms ago
    Nov 25 00:27:33 nuc patemon.psud[28810]: PSU:update took 115.262 ms, previous 6000.0 ms ago
    Nov 25 00:27:39 nuc patemon.psud[28810]: PSU:update failed! (error count: 1/3)
    Nov 25 00:27:45 nuc patemon.psud[28810]: PSU:update failed! (error count: 2/3)
    Nov 25 00:27:51 nuc patemon.psud[28810]: PSU:update failed! (error count: 3/3)
    Nov 25 00:27:51 nuc patemon.psud[28810]: Repeated serial timeouts!
    Nov 25 00:27:51 nuc patemon.psud[28810]: Abnormal, but clean, daemon exit!

Commands are also reasonably fast:

    Nov 25 00:20:29 nuc patemon.psud[28782]: PSU:SET VOLTAGE took 58.667 ms

Results are likely to become worse with actual Agilent PSU (as opposed to emulated unit) and once this is moved to target platform (Raspberry Pi 3 B+).
