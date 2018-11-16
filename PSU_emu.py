#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PSU_emulator.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.10.16  Initial version.
#
#
# Emulates PSU at class level. No real serial connections made.
#
# This class interface uses typing (Python 3.5+) for public methods.
# https://docs.python.org/3/library/typing.html
#
import serial
import random

from Config import Config

class PSU:
    ###########################################################################
    #
    # Public interface
    #
    # Available via nested class as functions:
    #       PSU().measure.voltage()     float
    #       PSU().measure.current()     float
    # PSU properties:
    #       PSU().power                 bool
    #       PSU().voltage               float
    #       PSU().current_limit         float
    #       PSU().state                 str             ["OVER CURRENT" | "OK"]
    #       PSU().port                  serial.Serial
    # PSU functions:
    #       PSU().values_tuple()        tuple
    #       PSU.find()                  str             ["/dev/.." | None]
    #

    #
    # Object properties
    #
    # instance of serial.Serial
    port    = None

    version = "1995.0"
    # Internal state values
    _power              = False
    _voltage            = 0.0
    _current_limit      = 0.0
    _over_current       = False
    # Circuit (R from _load_resistance() )
    _circuit_current    = 0.0
    _circuit_voltage    = 0.0

    #
    # Public methods
    #
    def __init__(self, port = None):
        self.measure            = self.Measure(self)
        self._power             = False
        self._voltage           = 0.0
        self._current_limit     = 4.4
        self._over_current      = False


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


    @property
    def values(self) -> dict:
        """Returns a tuple for SQL INSERT."""
        return dict({
            "power"             : "ON" if self.power else "OFF",
            "voltage_setting"   : self.voltage,
            "current_limit"     : self.current_limit,
            "measured_current"  : self.measure.current(),
            "measured_voltage"  : self.measure.voltage(),
            "state"             : ("OK", "OVER CURRENT")[self.state]
        })


    #
    # Static method for finding the correct port
    # Emulator implementation returns '/dev/null'.
    #
    @staticmethod
    def find() -> str:
        return '/dev/null'


    ###########################################################################
    #
    # PSU "Private" methods
    #
    #   These may be freely changed. Client code will NOT access any of these
    #   methods.
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
        # print("\r[{:>3}] {:1.3f}/{:1.3f} V, {:1.3f}/{:1.3f} A @ {:1.3} R".format(
        #     ("OFF", "ON")[self.power],
        #     self._circuit_voltage, self._voltage,
        #     self._circuit_current, self._current_limit,
        #     r_now
        #     ),
        #     end = "",
        #     flush = True
        # )

    def _load_resistance(self) -> float:
        """R changes according to what the load does. This randomizes it."""
        return random.uniform(10.8, 13.3)


    #
    # Support for 'with' -statement. These should be left unmodified.
    #
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.port.close()


###############################################################################
#
# Unit testing
#
###############################################################################

if __name__ == "__main__":

    import os


    print("Finding PSU...", end="", flush=True)
    try:
        port = PSU.find()
        if not port:
            print("not found!")
            os._exit(-1)
    except:
        print("\nAbnormal termination!")
        raise


    with PSU(port) as psu:
        print(psu.values)


        psu.power = False
        psu.voltage = 3.3
        psu.current_limit = 0.3
        if psu.measure.voltage() > 0.02:
            raise ValueError("Unexpected voltage at terminal!")


        psu.power = True
        if abs(psu.measure.voltage() - psu.voltage) > 0.05:
            raise ValueError("Unexpected voltage difference between set and measured values!")


        print(psu.values)
        psu.power = False


        print(psu.values)
        psu.power = False

# EOF
