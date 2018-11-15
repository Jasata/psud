# psud - Agilent PSU controller daemon for PATE Monitor

This solution implements minimal RS-232 remote control of Agilent E3631 powersupply.

psud runs as a daemon (unless '--nodaemon' is specified) and connects to PATE Monitor SQLite database to monitor and process "PSU" commands.
