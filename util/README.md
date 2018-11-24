# Utilities for psud

psu-emulator.py emulates Agilent E3631 minimally (only for those commands that are actually used by the psud). Connect to psud either via USB-RSR232 adapters or by using socat.

    usage: psu-emulator.py [-h] [-p [PORT]] [--show-command-replies]

    University of Turku, Department of Future Technologies Foresail-1 / Agilent
    PSU emulator Version 0.3, 2018 <jasata@utu.fi>

    optional arguments:
    -h, --help                show this help message and exit
    -p [PORT], --port [PORT]  Set serial port device
    --show-command-replies    Show received commands and replies instead of PSU internal state

Does not implement DTR (which is characteristic of E3631). Probably never will...
