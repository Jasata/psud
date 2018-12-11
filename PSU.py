#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PSU.py - Jani Tammi <jasata@utu.fi>
#   0.1     2018.10.15  Initial version (call interface only).
#   0.2     2018.12.03  Full implementation.
#   0.3.    2018.12.05  DTR seems to be a lie in case of certain commands.
#                       Added hardcoded long delays after such commands.
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
# =============================================================================
#
# Serial Cable ----------------------------------------------------------------
#   (page 57): "You must use a DTE-to-DTE interface cable. These cables are
#   also called null-modem, modem-eliminator, or crossover cables."
#
#   NOTE: D9 male connectors on both ends.
#
# PSU DTR/DSR Handshake Protocol ----------------------------------------------
#   (page 58): The DTR line must be TRUE before the power supply will accept
#   data from the interface. When the power supply sets the DTR line FALSE,
#   the data must cease within 10 characters.
#
#   NOTE: For us, using PySerial, this is read from serial.Serial().dsr!
#
#   (page 59): "When the power supply wants to “talk” over the interface
#   (which means that it has processed a query) and has received a <new line>
#   message terminator, it will set the DTR line FALSE."
#
#   "After the response has been output, the power supply sets the DTR line
#   TRUE again."
#
# Discard output buffer -------------------------------------------------------
#   (page 59): A form of interface deadlock exists until the bus controller
#   asserts the DSR line TRUE to allow the power supply to complete the
#   transmission. You can break the interface deadlock by sending the <Ctrl-C> 
#   character, which clears the operation in progress and discards pending 
#   output (this is equivalent to the IEEE-488 device clear action).
#
#   For the <Ctrl-C> character to be recognized reliably by the power supply
#   while it holds DTR FALSE, the bus controller must first set DSR FALSE.
#
# Terminal OFF ----------------------------------------------------------------
#   (page 79): The state of the disabled outputs is a condition of less than
#   0.6 volts of opposite polarity with no load and less than 60 mA of opposite
#   direction with a short circuit. At *RST, the output state is off.
#
# Triggered Value Setting -----------------------------------------------------
#   (page 73):  "INST P6V"          Select +6V terminal
#               "VOLT:TRIG 3.0"     Set the triggered voltage level to 3.0 V
#               "CURR:TRIG 1.0"     Set the triggered current level to 1.0 A
#               "TRIG:SOUR IMM"     Select immediate trigger as a source
#               "INIT"              Cause the trigger system to initiate
#
#   Good so far, BUT - the whole point of using this in our application boils
#   down to an ability to READ BACK those values, to verify that they ARE
#   correct, before we trigger them.
#   THIS NEEDS TO BE LOOKED INTO, IF WE WANT THIS TO BE USED.
#
###############################################################################
#
# ISSUE WITH SCPI COMMUNICATIONS
#
#       It has become clear that the the DTR signal does not indicate the
#       readiness of the device to handle commands or queries. It seems to be
#       limited to the readiness of the MCU that handles the serial comms.
#
#       In practise, this manifests itself as a failure to respond to a SCPI
#       command, if it is issued "too soon" after a command that is still being
#       handled internally. These /seem/ to be all the commands that modify the
#       operation of the device, such as set voltage, select terminal, set
#       terminal ON/OFF...
#
#       NO AMOUNT OF READ TIMEOUT / WAITING CAN SOLVE THIS ISSUE!!
#       (if another command is sent too soon, the reply will never come)
#
#       Two strategies are seen to handle this:
#       1. hard code "recovery delay" sleep() calls for each method that issues
#          a known "troublemaker" SCPI command.
#       2. Implement a retry count into the serial handler methods.
#
#   Testing Results:
#
#       GitHub USB-RS232.md should be read for details.
#       TLDR; our first USB/RS-232 adapter caused the remaining issues.
#       A borrowed unit solved the issues.
#
import time
import serial
import decimal

from typing import Union
from Config import Config


# FOR DEBUG LOGGING.
__log_start__ = time.monotonic()

def log(msg):
    print(
        "[{: >8.3f}] {}".format(
            (time.monotonic() - __log_start__) * 1000,
            msg or ""
        )
    )

#__RECOVERY_DELAY__ = 0.3    # 300 ms recovery time
#                            # necessary after certain commands;
#                            # OUTP, CURR, INST, APPL, etc.

class PSU:

    _loops = 0
    _last_read = ""
    _transaction_log = []
    #
    # Object properties
    #
    # instance of serial.Serial (public)
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
    #       PSU().port                  serial.Serial
    # PSU functions:
    #       PSU().values_tuple()        tuple
    #       PSU.find()                  str             ["/dev/.." | None]
    #
    class Measure:
        """PSU.Measure - nested class providing beautified naming for measurement functions."""
        def __init__(self, psu):
            self.psu = psu


        def voltage(self) -> decimal.Decimal:
            """Read measured voltage from the device."""
            # "SOUR:VOLT:IMM?" vs "MEAS:VOLT? P6V" <- use this! ("MEAS?" is OK!)
            return decimal.Decimal(self.psu._PSU__transact("MEAS?"))


        def current(self) -> decimal.Decimal:
            """Read measured current from the device."""
            # "MEAS:CURR? P6V"
            return decimal.Decimal(self.psu._PSU__transact("MEAS:CURR?"))


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        # "OUTP:STAT?" == "OUTP?", return value is string "0" or "1"
        return ("OFF", "ON")[self.__transact("OUTP?") == "1"]


    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF."""
        # "OUTP:STAT ON|OFF" == "OUTP ON|OFF"
        self.__write("OUTP " + ("OFF", "ON")[value])
        # After setting output state, PSU needs recovery time
        # (the DTR signal is a lie! Try it!)
        #time.sleep(__RECOVERY_DELAY__)
        if self.power != ("OFF", "ON")[value]:
            raise ValueError("Failed to toggle output ON/OFF!")


    @property
    def voltage(self) -> decimal.Decimal:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        return decimal.Decimal(self.__transact("SOUR:VOLT:IMM?"))


    @voltage.setter
    def voltage(self, value: Union[float, decimal.Decimal]):
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        # "SOUR:VOLT:IMM" == "VOLT"
        self.__write("VOLT {}".format(str(round(value, 3))))


    @property
    def current_limit(self) -> decimal.Decimal:
        """Read PSU current limit setting."""
        # "SOUR:CURR:IMM?" == "CURR?"
        return decimal.Decimal(self.__transact("CURR?"))


    @current_limit.setter
    def current_limit(self, value: Union[float, decimal.Decimal]):
        """Set PSU current limit value."""
        # "SOUR:CURR:IMM" == "CURR"
        self.__write("CURR {}".format(str(round(value, 3))))
        # After setting current limit, PSU needs recovery time
        #time.sleep(__RECOVERY_DELAY__)
        # Skip verification for now...


    @property
    def values(self) -> dict:
        """Returns a tuple for SQL INSERT."""
        return dict({
            "power"               :"ON" if self.power else "OFF",
            "voltage_setting"     :self.voltage,
            "current_limit"       :self.current_limit,
            "measured_current"    :self.measure.current(),
            "measured_voltage"    :self.measure.voltage()
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
                    baudrate      = Config.PSU.Serial.baudrate,
                    parity        = Config.PSU.Serial.parity,
                    stopbits      = Config.PSU.Serial.stopbits,
                    bytesize      = Config.PSU.Serial.bytesize,
                    timeout       = 0.3,
                    write_timeout = None
                )
                PSU.flush(port)
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
            print("DEV:", sysfsobj.device)
            if found_at(sysfsobj.device):
                port = sysfsobj.device
                break
        return port

    @staticmethod
    def flush(port: serial.Serial):
        """Clear serial line/buffers from artefacts. Agilent E3631 User's Guide (p. 59) tells us that sending CTRL-C to the unit will cause it to discard any pending output. ("^C" ETX; "End of Text", 0x03 or b'\x03'). Quite: "For the <Ctrl-C> character to be recognized reliably by the power supply while it holds DTR FALSE, the bus controller must first set DSR FALSE. (NOTE: for us, in PySerial, this means setting _our_ DTR low)."""
        discard_timeout = 0.1
        log("#1 {} {}".format(port.dsr, port.dtr))
        port.flushOutput()
        log("#2 {} {}".format(port.dsr, port.dtr))
        port.flushInput()
        log("#3 {} {}".format(port.dsr, port.dtr))
        time.sleep(0.1)
        log("#4 {} {}".format(port.dsr, port.dtr))
        port.dtr = 0
        log("#5 {} {}".format(port.dsr, port.dtr))
        port.write(b'\x03')
        log("#6 {} {}".format(port.dsr, port.dtr))
        port.dtr = 1
        log("#7 {} {}".format(port.dsr, port.dtr))
        # wait until unit raises DTR
        start = time.monotonic()
        while not port.dsr and time.monotonic() - start < discard_timeout:
            time.sleep(0.01)
        log("#8 {} {}".format(port.dsr, port.dtr))
        if not port.dsr:
            raise serial.SerialTimeoutException(
                "Device did not raise DTR within {:1.2f} ms".format(
                    discard_timeout * 1000
                )
            )
        # DTR has come up, but its a lie - PSU is not ready!
        # Wait for magical period
        #time.sleep(__RECOVERY_DELAY__)
        # print("#7", port.dsr, port.dtr)


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
        if not port and Config.PSU.Serial.port.lower() == 'auto':
            port = PSU.find()
            if port is None:
                raise ValueError("Unable to find power supply!")

        # Read and convert Config.py's float values into decimal.Decimal
        # TODO: Try to make sure we get the exact value read in
        decimal.getcontext().rounding = decimal.ROUND_FLOOR
        default_voltage = round(decimal.Decimal(Config.PSU.Default.voltage), 3)
        default_climit  = round(decimal.Decimal(Config.PSU.Default.current_limit), 3)

        self.port = serial.Serial(
            port            = port or Config.PSU.Serial.port,
            baudrate        = Config.PSU.Serial.baudrate,
            bytesize        = Config.PSU.Serial.bytesize,
            parity          = Config.PSU.Serial.parity,
            stopbits        = Config.PSU.Serial.stopbits,
            timeout         = Config.PSU.Serial.timeout,
            xonxoff         = False,
            rtscts          = False,
            write_timeout   = None,
            dsrdtr          = True
        )
        # PySerial has bad habbits. See:
        # https://stackoverflow.com/questions/7266558/pyserial-buffer-wont-flush
        # Recommended approach is to wait after opening a port
        time.sleep(0.2)

        # Try to clean the line and buffers
        PSU.flush(self.port)
        log(
            "DTR wait after PSU.flush(): {:1.2f} ms".format(
                self.__waitDTR() * 1000
            )
        )

        # Check that it's a PSU ('yyyy.xx' return format)
        try:
            response = self.__transact("SYST:VERS?")
            if response[4:5] != '.':
                raise ValueError()
            int(response[0:4])
            int(response[5:7])
        except Exception as e:
            raise ValueError(
                "Serial device does not appear to be Agilent E3631\n" + str(e)
            ) from None

        # TODO: Try to determine if the PSU is already initialized
        # Setting remote does not return anything
        self.__write("SYST:REM")
        # If PySerial DSR/DTR control works, the above call should have not
        # returned until the PSU DTR line is high. But we already know that
        # it doesn't work...
        # if not self.port.dsr:
        #     raise ValueError("PSU DTR is low!")

        # Select terminal ("channel")
        # Seems to work for "MEAS:..." commands, but "SOUR:VOLT:IMM " could
        # not care less ("INST:SEL" == "INST")
        self.__write("INST {}".format(Config.PSU.Default.terminal))
        # DTR comes up, but the PSU IS NOT READY! If you now issue some other
        # command, the last replay is sent again ("SYST:VERS?" -> "1995.0")!!
        # time.sleep(0.3)
        if self.__transact("INST?") != Config.PSU.Default.terminal:
            raise ValueError(
                "Unable to select output terminal! Returned: '{}'".format(
                    self._last_read
                )
            )

        #
        # Set default values
        #
        self.__write(
            "APPL {},{},{}".format(
                Config.PSU.Default.terminal,
                str(round(default_voltage, 3)),
                str(round(default_climit, 3))
            )
        )
        # AGAIN, DTR comes up, but the PSU is not ready
        #time.sleep(__RECOVERY_DELAY__)
        setv, setcl = self.__transact(
            "APPL? {}".format(
                Config.PSU.Default.terminal
            )
        )[1:][:-1].split(",")
        setv = decimal.Decimal(setv)
        setcl = decimal.Decimal(setcl)
        if setv != default_voltage:
            raise ValueError(
                "Default voltage setting error! '{}' != '{}'".format(
                    setv, default_voltage
                )
            )
        if setcl !=  default_climit:
            raise ValueError(
                "Default current limit setting error! '{}' != '{}'".format(
                    setcl, default_climit
                )
            )


    def __waitDTR(self):
        """Use to determine when it is OK to send to PSU. This method wait for the unit to raise DTR (for us, in PySerial, port.dsr), or raises a serial.SerialTimeoutException after 500ms. For debug/testing purposes, returns the time spent waiting.
        NOTE: DTR will NOT raise if the PSU has data to be read! The SCPI protocol interactions are YOUR responsibility!"""
        start = time.monotonic()
        while not self.port.dsr and time.monotonic() - start < 0.5:
            time.sleep(0.005)
        if not self.port.dsr:
            raise serial.SerialTimeoutException(
                "PSU DTR did not go high within 100ms!"
            )
        return time.monotonic() - start


    def __write(self, command: str, ignore_dtr = False) -> None:
        """Send SCPI command string to serial adapter."""
        start = time.monotonic()
        try:
            if not ignore_dtr:
                log(
                    "__write('{}') waited DTR for {:1.2f} ms".format(
                        command,
                        self.__waitDTR() * 1000
                    )
                )
            self.port.write((command + "\r\n").encode('utf-8'))
        except Exception as e:
            raise Exception(str(e) + " Command: '{}'".format(command)) from None
        self._transaction_log.append(
            ((time.monotonic() - start) * 1000, command, None)
        )

    def __transact(self, command: str, ignore_dtr = False) -> str:
        """Read SCPI command response from serial adapter."""
        start = time.monotonic()
        self._last_read = None
        log("self._last_read set to None ('{}')".format(self._last_read))
        retry = 3
        while retry:
            retry -= 1
            # Flush is VERY IMPORTANT! You WILL get the last read otherwise
            self.port.flush()
            try:
                self.__write(command, ignore_dtr)
            except Exception as e:
                log("__write() returned with an exception!")
                log(str(e).replace('\n', ' '))
                raise
            # "Surprise", PySerial's DSR/DTR hardware flow control doesn't seem
            # to do anything at all.
            # PSU DTR *must* become low! It indicates PSU has data to be read.
            # Blindy going into a read before this has proven to be a bad idea.
            # So we do this now...
            self._loops = 0
            while self.port.dsr:
                # In tests, usually less than 100 loops
                if self._loops > 1000:
                    raise ValueError("PSU DTR does not go down!")
                self._loops += 1

            self._last_read = None
            self._last_read = self.port.read_until(b'\r\n')
            if self._last_read[-1:] != b'\n':
                if retry == 0:
                    raise serial.SerialTimeoutException(
                        "Serial readline() timeout for '{}'! ('{}')".format(
                            command,
                            self._last_read or "None"
                        )
                    )
                else:
                    log("Retry #{}".format(retry + 1))
            else:
                break
        self._last_read = self._last_read.decode('utf-8')[:-2]
        log("__transact('{}') -> '{}'".format(command, self._last_read))
        self._transaction_log.append(
            ((time.monotonic() - start) * 1000, command, self._last_read)
        )
        return self._last_read


    def next_error(self):
        code, msg = self.__transact("SYST:ERR?").split(",")
        return msg


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
    log("Using port '{}'".format(port))
    with PSU(port) as psu:

        log("Volts: {:1.3f}".format(psu.measure.voltage()))
        log(psu.values)

        psu.power = False
        psu.voltage = 3.3
        psu.current_limit = 0.3
        psu.power = True
        reading = psu.measure.voltage()
        log("Set: {}, Measured: {}".format(psu.voltage, reading))
        if abs(psu.voltage - reading)  > 0.02:
            raise ValueError("Unexpected voltage differential!")


        psu.power = True
        if abs(psu.measure.voltage() - psu.voltage) > 0.05:
            raise ValueError("Unexpected voltage difference between set and measured values!")


        log(psu.values)
        psu.power = False

    #print(psu._)

# EOF
