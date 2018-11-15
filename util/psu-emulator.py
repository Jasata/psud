#! /usr/bin/env python3
#
# psu-emulator.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.11.12  Initial version.
#   0.2     2018.11.14  Enchanced with more replies.
#
#   Trivial Agilent PSU emulator.
#	This version replies only to version query.
#	Requires pyserial
#
#   # apt install python3-serial
#
#
#
import os
import sys
import time
import random
import serial
import platform
import argparse

__version__ = "0.2"
__fileName   = os.path.basename(__file__)


class Cfg:
    device        = "/dev/ttyUSB0"
    baudrate      = 9600
    bits          = serial.EIGHTBITS
    parity        = serial.PARITY_NONE
    stopbits      = serial.STOPBITS_TWO
    timeout       = None # 0.05
    write_timeout = None
    @staticmethod
    def serial_parameters():
        def bits(v):
            if v == serial.EIGHTBITS:
                return '8'
            elif v == serial.SEVENBITS:
                return '7'
            elif v == serial.SIXBITS:
                return '6'
            elif v == serial.FIVEBITS:
                return '5'
            else:
                return '?'
        def parity(v):
            if v == serial.PARITY_NONE:
                return 'N'
            elif v == serial.PARITY_EVEN:
                return 'E'
            elif v == serial.PARITY_ODD:
                return 'O'
            elif v == serial.PARITY_MARK:
                return 'M'
            elif v == serial.PARITY_SPACE:
                return 'S'
            else:
                return '?'
        def stopbits(v):
            if v == serial.STOPBITS_ONE:
                return '1'
            elif v == serial.STOPBITS_ONE_POINT_FIVE:
                return '1.5'
            elif v == serial.STOPBITS_TWO:
                return '2'
            else:
                return '?'
        return ",".join([
            str(Cfg.baudrate),
            bits(Cfg.bits),
            parity(Cfg.parity),
            stopbits(Cfg.stopbits)
        ])


class PSU:
    version = "1995.0"
    # Internal state values
    _power              = False
    _voltage            = 0.0
    _current_limit      = 0.0
    _over_current       = False
    # Circuit (R from _load_resistance() )
    _circuit_current    = 0.0
    _circuit_voltage    = 0.0

    # testing __init__()
    def __init__(self):
        self.measure            = self.Measure(self)
        self._power             = False
        self._voltage           = 0.0
        self._current_limit     = 4.4
        self._over_current      = False
        # self._run_circuit()

    def _run_circuit(self):
        """Applies U / R and sets overcurrent accordingly"""
        def inaccuracy(value: float) -> float:
            """ -1% ... +3%  """
            return random.uniform(value - (value * 0.01), value + (value * 0.03))
        r_now = self._load_resistance()
        if self._power:
            self._circuit_voltage = inaccuracy(self.voltage)
        else:
            self._circuit_voltage = inaccuracy(0.0)
        self._circuit_current = self._circuit_voltage / r_now
        # Overcurrent?
        if self._circuit_current > self._current_limit:
            self._circuit_voltage = inaccuracy(r_now * self._current_limit)
            self._circuit_current = self._circuit_voltage / r_now
            self._over_current = True
        else:
            self._over_current = False
        print("\r[{:>3}] {:1.3f}/{:1.3f} V, {:1.3f}/{:1.3f} A @ {:1.3} R".format(
            ("OFF", "ON")[self.power],
            self._circuit_voltage, self._voltage,
            self._circuit_current, self._current_limit,
            r_now
            ),
            end = "",
            flush = True
        )

    def _load_resistance(self) -> float:
        """R changes according to what the load does. This randomizes it."""
        return random.uniform(10.8, 13.3)

    class Measure:
        def __init__(self, psu):
            self.psu = psu
        def voltage(self):
            """Return voltage setting with +/-."""
            self.psu._run_circuit()
            return self.psu._circuit_voltage
        def current(self):
            """Current = Voltage divided by R={11.0 .. 22.0}."""
            self.psu._run_circuit()
            return self.psu._circuit_current


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        return self._power
    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF. Setting is read back from the device
        and returned by this function (confirmation)."""
        self._power = value
        return self.power


    @property
    def voltage(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        return self._voltage
    @voltage.setter
    def voltage(self, value: float) -> float:
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        self._voltage = value
        return self.voltage


    @property
    def current_limit(self) -> float:
        """Read PSU current limit setting."""
        return self._current_limit
    @current_limit.setter
    def current_limit(self, value: float) -> float:
        """Set SPU current limit value."""
        self._current_limit = value
        return self.current_limit


    @property
    def state(self) -> str:
        """Read PSU Status (has/is current limit reached)."""
        return self._over_current

#
# GLOBAL psu
#
psu = PSU()

###############################################################################
#
# SCPI command tree
#
###############################################################################
# SOURce:
def sour(cmdtree: list):
    return source(cmdtree)
def source(cmdtree: list):
    fnc = cmdtree.pop(0)
    if fnc in ("curr", "current"):
        # We don't do current settings
        return None
    elif fnc in ("volt", "voltage"):
        act = cmdtree.pop(0)
        if act in ("imm?", "immediate?"):
            return "{:1.3f}".format(psu.voltage)
        else:
            psu.voltage = float(act.split(' ')[1])
    else:
        print("Invalid subsection")
    return None
# elif cmd == "source:voltage:immediate?":


#INSTrument:
def inst(cmdtree: list):
    return instrument(cmdtree)
def instrument(cmdtree: list):
    fnc = cmdtree.pop(0)
    if fnc in ("sel?", "select?"):
        return "P6V"
    elif fnc in ("sel", "select"):
        return None

# MEASure:
def meas(cmdtree: list):
    return measure(cmdtree)
def measure(cmdtree: list):
    fnc = cmdtree.pop(0)
    if fnc in ("curr?", "current?"):
        return "{:1.3f}".format(psu.measure.current())
    elif fnc in ("volt?", "voltage?"):
        return "{:1.3f}".format(psu.measure.voltage())
    else:
        return None

# OUTput:
def out(cmdtree: list):
    return output(cmdtree)
def output(cmdtree: list):
    fnc = cmdtree.pop(0)
    if fnc[:len("stat?")] == "stat?" or fnc[:len("state?")] == "state?":
        return ("OFF", "ON")[psu.power]
    elif fnc[:len("stat")] == "stat" or fnc[:len("state")] == "state":
        psu.power = (fnc.split(' ')[1] == "on")
        return None
    else:
        return None

def syst(cmdtree: list):
    return system(cmdtree)
def system(cmdtree: list):
    fnc = cmdtree.pop(0)
    if fnc in ("vers?", "version?"):
        return psu.version
    elif fnc in ("rem", "remote"):
        return None
    else:
        return None


###############################################################################
#
# MAIN
#
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description = \
        "University of Turku, Department of Future Technologies\n" + \
        "Foresail-1 / Agilent PSU emulator\n" + \
        "Version {}, 2018 <jasata@utu.fi>\n".format(__version__)
    )
    parser.add_argument(
        '-p',
        '--port',
        help = "Set serial port device",
        nargs = '?',
        dest = "port",
        const = "PORT",
        default = Cfg.device,
        type = str
    )
    args = parser.parse_args()
    Cfg.device = args.port

    print("{} version {}".format(__fileName, __version__))
    print(
        "Running on Python ver.{} on {} {}" \
        .format(
            platform.python_version(),
            platform.system(),
            platform.release()
        )
    )
    print("pySerial ver.{}".format(serial.VERSION))
    print(
        "Opening {} ({})..."
        .format(
            Cfg.device,
            Cfg.serial_parameters()
        ),
        end = ''
    )
    bus = serial.Serial(
        port          = Cfg.device,
        baudrate      = Cfg.baudrate,
        bytesize      = Cfg.bits,
        parity        = Cfg.parity,
        stopbits      = Cfg.stopbits,
        timeout       = Cfg.timeout,
        write_timeout = Cfg.write_timeout,
        exclusive     = True
    )
    print(" '{}' OK".format(bus.name))

    # Create virtual Agilent power supply
    psu = PSU()

    #
    # Main loop
    #
    print("Waiting for commands... (CTRL-C to quit)")
    try:
        while True:
			# Slice two last characters ('\r\n')
            cmd = bus.readline().decode('ascii', 'ignore')[:-2].lower()
            # print("'{}'   ==> ".format(cmd), end = '')

            #
            # Command tree
            #
            reply = None
            try:
                cmdtree = cmd.split(":")
                fnc = cmdtree.pop(0)
                reply = eval(fnc + "(cmdtree)")
            except Exception as e:
                reply = str(e).replace('\n', '\\n')

            #
            # Send reply
            #
            if reply:
                reply = reply + "\r\n"
                bus.write(reply.encode('ascii'))
            # print(
            #     "'{}'"
            #     .format(
            #         reply.replace('\n', '\\n').replace('\r', '\\r') if reply else "None"
            #     ),
            #     flush=True
            # )
    except KeyboardInterrupt:
        print('interrupted!')
    finally:
        bus.close()

# EOF
