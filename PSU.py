#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PSU.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.10.15  Initial version (call interface only).
#   0.2     2018.12.03  Full implementation.
#
#
# This class interface uses typing (Python 3.5+) for public methods.
# https://docs.python.org/3/library/typing.html
#
# python3 -m serial.tools.miniterm --parity N --dtr 0 --eol CRLF
#
# DTR - Data Terminal Ready     PSU is ready to receive
#                               ->False : Stop within 10 characters
#                               read: port.getDSR()
# DSR - Data Set Ready          PSU monitors for bus controller's readiness
#                               PSU pauses immediately when false
#                               set: port.setDTR(1|0)
#
# Agilent E3631 User Guide:
#   (page 58): The DTR line must be TRUE before the power supply will accept
#   data from the interface. When the power supply sets the DTR line FALSE,
#   the data must cease within 10 characters.
#
#   To disable the DTR/DSR handshake, do not connect the DTR line and tie the
#   DSR line to logic TRUE. If you disable the DTR/DSR handshake, also select a
#   slower baud rate to ensure that the data is transmitted correctly.
#
#   (page 59): A form of interface deadlock exists until the bus controller
#   asserts the DSR line TRUE to allow the power supply to complete the
#   transmission. You can break the interface deadlock by sending the <Ctrl-C> 
#   character, which clears the operation in progress and discards pending 
#   output (this is equivalent to the IEEE-488 device clear action).
#
#   For the <Ctrl-C> character to be recognized reliably by the power supply
#   while it holds DTR FALSE, the bus controller must first set DSR FALSE.
#
import serial
import time

from Config import Config

class PSU:

    #
    # Object properties
    #
    # instance of serial.Serial
    port    = None

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
    class Measure:
        """PSU.Measure - nested class providing beautified naming for measurement functions."""
        def __init__(self, psu):
            self.psu = psu


        def voltage(self) -> float:
            """Read measured voltage from the device."""
            # "SOUR:VOLT:IMM?" vs "MEAS:VOLT? P6V"
            return float(self.psu._PSU__transact("MEAS:VOLT?"))


        def current(self) -> float:
            """Read measured current from the device."""
            # "MEAS:CURR? P6V"
            return float(self.psu._PSU__transact("MEAS:CURR?"))


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        #return self.__read_message("Read power output value SCPI command...")
        return ("OFF", "ON")[self.__transact("OUTP:STAT?") == "ON"]


    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF."""  
        self.__write("OUTP:STAT " + ("OFF", "ON")[value])
        if self.power != ("OFF", "ON")[value]:
            raise ValueError("Failed to toggle output ON/OFF!")


    @property
    def voltage(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        return float(self.__transact("SOUR:VOLT:IMM?"))


    @voltage.setter
    def voltage(self, value: float) -> float:
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        self.__write("SOUR:VOLT:IMM {0:1.3f}".format(value))


    @property
    def current_limit(self) -> float:
        """Read PSU current limit setting."""
        return float(self.__transact("SOUR:CURR:IMM?"))


    @current_limit.setter
    def current_limit(self, value: float) -> float:
        """Set PSU current limit value."""
        self.__write("SOUR:CURR:IMM {:1.3f}".format(value))
        # Skip verification for now: float comparison is a bad idea and
        # the unit returns exponent format strings ("+3.00000000E-01")


    @property
    def state(self) -> str:
        """Read PSU state (has/is current limit reached)."""
        # TODO
        return "TODO"


    @property
    def values(self) -> dict:
        """Returns a tuple for SQL INSERT."""
        return dict({
            "power"               :"ON" if self.power else "OFF",
            "voltage_setting"     :self.voltage,
            "current_limit"       :self.current_limit,
            "measured_current"    :self.measure.current(),
            "measured_voltage"    :self.measure.voltage(),
            "state"               :self.state
        })


    ###########################################################################
    #
    # Static method for finding the correct port
    #
    @staticmethod
    def find() -> str:
        """Finds Agilent PSU from available serial devices.
        Return device file name or None if not found."""
        def transact(port, command: str) -> str:
            """Argument 'command' of type str. Returns type str"""
            port.write(command.encode('utf-8'))
            line = port.readline()
            # If the last character is not '\n', we had a timeout
            if line[-1:] != b'\n':
                raise ValueError(
                    "Serial read timeout! ({}s)".format(port.timeout)
                )
            return line.decode('utf-8')
        def found_at(port: str) -> bool:
            """Guaranteed to return True or False, depending on if the PSU is
            detected at the provided port."""
            def valid_firmware_string(firmware: str) -> bool:
                """Validate 'yyyy.x' version string.
                Returns True is meets criteria, False if not."""
                try:
                    if len(firmware) < len("yyyy.x"):
                        raise ValueError()
                    if firmware[4:5] != '.':
                        raise ValueError()
                    int(firmware[0:4])
                    int(firmware[5:6])
                except:
                    return False
                return True
            result = None
            try:
                port = serial.Serial(
                    port          = port,
                    baudrate      = Config.PSU.baudrate,
                    parity        = Config.PSU.parity,
                    stopbits      = Config.PSU.stopbits,
                    bytesize      = Config.PSU.bytesize,
                    timeout       = 0.3,
                    write_timeout = None
                )
                # Agilent uses CRLF line termination
                response = transact(port, 'System:Version?\r\n')
                result = valid_firmware_string(response)
            except:
                result = False
            finally:
                try:
                    port.close()
                except:
                    pass
            return result or False
        #
        # PSU.find() block begins
        #
        import serial.tools.list_ports
        port = None
        for sysfsobj in serial.tools.list_ports.comports():
            if found_at(sysfsobj.device):
                port = sysfsobj.device
                break
        return port


    ###########################################################################
    #
    # PSU "Private" methods
    #
    #   We know that the unit responds to "SYST:VERS?" without remove mode,
    #   but beyond that, we should first set "SYST:REM".
    #
    def __init__(self, port = None):
        """Connect and initialize PSU. If port argument is omitted, Config.PSU.Serial.port is used."""
        self.measure = self.Measure(self)

        # If port == 'auto', try to .find() it.
        if not port and Config.PSU.port.lower() == 'auto':
            Config.PSU.port = PSU.find()
            if Config.PSU.port is None:
                raise ValueError("Unable to find power supply!")

        self.port = serial.Serial(
            port            = port or Config.PSU.port,
            baudrate        = Config.PSU.baudrate,
            bytesize        = Config.PSU.bytesize,
            parity          = Config.PSU.parity,
            stopbits        = Config.PSU.stopbits,
            timeout         = Config.PSU.timeout,
            xonxoff         = False,
            rtscts          = False,
            write_timeout   = None,
            dsrdtr          = True
        )

        # "Clear line". User's Guide p. 59 tells us that sending CTRL-C to the
        # unit will cause it to discard any pending output.
        # "^C" ETX ("End of Text") 0x03
        # "For the <Ctrl-C> character to be recognized reliably by the power
        # supply while it holds DTR FALSE, the bus controller must first set
        # DSR FALSE."
        self.port.flushOutput()
        self.port.flushInput()
        time.sleep(0.1)
        self.port.dtr = 0
        self.port.write(b'\x03')
        while not self.port.dsr:
            pass
        # Let the PSU "recover"
        time.sleep(0.5)


        # Check that it's a PSU ('yyyy.xx' return format)
        try:
            response = self.__transact("SYST:VERS?")
            if response[4:5] != '.':
                raise ValueError()
            int(response[0:4])
            int(response[5:7])
        except Exception as e:
            raise ValueError("Serial device does not appear to be Agilent E3631\n" + str(e)) from None



        # TODO: Try to determine if the PSU is already initialized
        # Setting remote does not return anything
        self.__write("SYST:REM")
        # If PySerial DSR/DTR control works, the above call should have not
        # returned until the PSU DTR line is high.
        if not self.port.dsr:
            raise ValueError("PSU DTR is low!")

        # Select terminal ("channel")
        self.__write("INST:SEL P25V")
        if not self.port.dsr:
            raise ValueError("PSU DTR is low!")
        if self.__transact("INST:SEL?") != "P25V":
            raise ValueError("Unable to select output terminal!")




    def __write(self, command: str) -> None:
        """Send SCPI command string to serial adapter."""
        self.port.write((command + "\r\n").encode('utf-8'))


    def __transact(self, command: str) -> str:
        """Read SCPI command response from serial adapter."""
        self.__write(command)
        line = self.port.readline()
        # If the last character is not '\n', we had a timeout.
        # Agilent E3631 returns '\r\n' line terminators, but '\n' is fine.
        if line[-1:] != b'\n':
            raise serial.SerialException("Serial read timeout!")
        return line.decode('utf-8')[:-2]


    #
    # Support for 'with' -statement. These should be left unmodified.
    #
    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.port.close()






if __name__ == "__main__":
    """Basic test"""
    import os
    import sys

    # If port not specified in commandline
    if len(sys.argv) < 2:
        port = PSU.find()
        if not port:
            print("Cannot find Agilent PSU!")
            os._exit(-1)
    else:
        port = sys.argv[1]


    # Do some stuff
    print("Using port '{}'".format(port))
    with PSU(port) as psu:

        print("Volts: {:1.3f}".format(psu.measure.voltage()))
        # print(psu.values)

        # psu.power = False
        # psu.voltage = 3.3
        # psu.current_limit = 0.3
        # if psu.measure.voltage() > 0.02:
        #     raise ValueError("Unexpected voltage at terminal!")


        # psu.power = True
        # if abs(psu.measure.voltage() - psu.voltage) > 0.05:
        #     raise ValueError("Unexpected voltage difference between set and measured values!")


        # print(psu.values)
        # psu.power = False

# EOF
