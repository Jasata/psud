# psud - Agilent PSU controller daemon for PATE Monitor

This solution implements minimal RS-232 remote control of Agilent E3631 power supply.

psud runs as a daemon (unless '--nodaemon' is specified) and connects to PATE Monitor SQLite database to monitor and process "PSU" commands and to periodically update the `psu` table with settings and measured voltage and current values.

All code, with the exception of `PSU.py`, are written by Jani Tammi and copyrighted under MIT license. The interface class `PSU.py` is written by NAME and is copyrighted under LICENSE. The project repository for this this file is REPOSITORY.

## Usage

This daemon is intended to be managed by PATE Monitor's System Daemon, but can be managed separately, if necessary.

    usage: psud [-h] [-d [FILE]] [-l [LEVEL]] [-p [SERIAL_PORT]] [--nodaemon] [--kill]

    optional arguments:
      -h, --help                    show this help message and exit
      -d [FILE], --datafile [FILE]  PATE Monitor SQLite3 database. Default: '/srv/nginx-root/pmapi.sqlite3'
      -l [LEVEL], --log [LEVEL]     Set logging level. Default: DEBUG
      -p [PORT], --port [PORT]      Set serial port device. Default: '/dev/ttyUSB0'
      --nodaemon                    Do not execute as a daemon
      --kill                        Kill daemon

Default values come from `Config.py`.

Option `-p` has one special value; `auto`. If specified, the daemon will attempt to detect which of the system's serial ports has the Agilent power supply connected to. Otherwise, `-p` option expects to receive a valid serial device as an argument.

## Single Instance Execution

This implementation uses a lock file scheme to avoid multiple instances from starting up. Because this daemon is expected to be executed with non-root privileges, the lock file cannot be located in the system default location. Instead, the lock file is placed into `/tmp` directory.

It is to be noted that if the user so wishes, he can remove a lock file and start up another copy of the daemon, but the implementation itself respects the lock file.

## Update Intervals

Because the Agilent E3631 power supply only supports up to 9600 baud serial speed, the command-response cycles can be relatively long (can exceed 40 ms), the query and command intervals cannot be very short.

Agilent E3631 has serial configuration; `9600,8,N,2`.

    payload characters x bits per character / bits per second
    15 characters x (8 bits/Byte + 1 start bit + 2 stop bits) / 9600 bits per second
    = 15 x 11 / 9600 = 17,2 ms

    (approximately: 1,146 ms / character)

*Status Query*

The 2 characters added in each command are the line terminator characters (`\r\n`).

 - Qeury power status (`X` ? + 2 characters)
 - Query voltage setting (`Source:Voltage:Immediate?` 25 + 2 characters)
 - Query current limit (`Source:Current:Immediate?` 25 + 2 characters)
 - Query measured voltage (`Measure:Voltage?` 16 + 2 characters)
 - Query measured current (`Measure:Current?` 16 + 2 characters)
 - Query state (`X` ? + 2 characters)

The query commands alone are 94 characters plus the query lengths for power status and state queries, which can be assumed to be on overage at least 16 characters each. Total being 126 characters or more. This equals around 144,5 ms. Responses are string representations of voltages or states:

 - Response power status (`d` 1 + 2 characters)
 - Response voltage setting (`dd.dddd` 7 + 2 characters)
 - Response current limit (`dd.dddd` 7 + 2 characters)
 - Response measured voltage (`dd.dddd` 7 + 2 characters)
 - Response measured current (`dd.dddd` 7 + 2 characters)
 - Response state (`X` 1 + 2 characters)

Responses equal to at least 42 characters, totaling around 48,2 ms.

Total transmission time is around 192,7 ms or more - same assumption is 200 ms.

*Commands*

The daemon is built to process one command each interval, which means that we are interested in the longest commmand-reply sequence. This is (most likely) the voltage setting command:

    Source:Voltage:Immediate dd.ddd

31 + 2 characters, with no reply at all, giving us around 37,9 ms. Safe time allocation would be 40 ms.

*Interval values*

A full cycle of populating the `psu` table and processing one command requires around 240 ms. This means that "update" events should not schedule more often than every 250 ms or more. This value is increased 40 ms for each "command" event that fired (or begins to lapse) during "update" interval.

For example, "command" intervals trigger every 100 ms, meaning that "update" interval needs to be at least 200 ms + all the "command" intervals during the total time.

    200 ms / 100 ms = 2 "command" cycles
    new "update" interval = 200 ms + 40 ms x 2 = 280 ms
    280 ms / 100 ms = 3 "command" cycles => 200 ms + 40 ms x 3 = 320 ms
    320 ms / 100 ms = 4 "command" cycles => 200 ms + 40 ms x 4 = 360 ms
    360 ms / 100 ms = 4 "command" cycles (!)

Usable interval values are thus; `psu` table updates every 360 ms and command processing every 100 ms. With these values, the should never be any skew. Event triggering window (allow early event triggering for the other event, if it would follow withing set time window) should be half of the command processing time (40 ms / 2 = 20 ms).

(shorthands)

