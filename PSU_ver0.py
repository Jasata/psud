#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PSU.py - Jarkko Pesonen <jarpeson@utu.fi>
#   0.1     2018.10.15  Initial version.
#   0.2     2018.11.11  Reviced interface.
#   0.3     2018.11.24  Raise serial.SerialTimeoutException on read timeouts.
#                       Setter returns discarded.
#                       PSU.port honored.
#                       On __init__(), port is flushed.
#                       short-hand SCPI command strings used.
#
#
# This class interface uses typing (Python 3.5+) for public methods.
# https://docs.python.org/3/library/typing.html
#
import serial
import time

from Config import Config



# HACK
__SLEEP__ = 0.0

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
            self.psu._PSU__send_message("MEAS:VOLT?") # "Measure:Voltage?"
            return float(self.psu._PSU__read_message())

        def current(self) -> float:
            """Read measured current from the device."""
            self.psu._PSU__send_message("MEAS:CURR?") # "MEASure:CURRent?"
            return float(self.psu._PSU__read_message())


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        self.__send_message("OUTP:STAT?") # "Output:State?"
        return ("ON" in self.__read_message())
    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF. Setting is read back from the device and returned by this function (confirmation)."""
         # "Output:State ON"
        self.__send_message("OUTP:STAT {}".format(("OFF", "ON")[value]))


    @property
    def voltage(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        self.__send_message("SOUR:VOLT:IMM?") # "Source:Voltage:Immediate?"
        return float(self.__read_message())
    @voltage.setter
    def voltage(self, value: float) -> float:
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        # "Source:Voltage:Immediate {0:1.3f}"
        self.__send_message(
            "SOUR:VOLT:IMM {0:1.3f}".format(
                value
            )
        )

    @property
    def current_limit(self) -> float:
        """Read PSU current limit setting."""
        return self._current_limit
    @current_limit.setter
    def current_limit(self, value:float = None) -> float:
        """Set PSU current limit value."""
        self._current_limit = value


    @property
    def state(self) -> str:
        """Read PSU state (current limit is/has been reached)."""
        return self._state


    @property
    def values(self) -> dict:
        """Returns a dict for SQL INSERT."""
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
    # NOTE: Tested on 12.11.2018 / JTa.
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
    #   These may be freely changed. Client code will NOT access any of these
    #   methods.
    #
    #   NOTE: __init__() signature must remain as specified.
    #
    def __init__(self, port = None):
        """Initialize object and test that we are connected to PSU by issuing a version query. If port argument is omitted, Config.PSU.Serial.port is used. Modified 24.11.2018."""
        self.measure = self.Measure(self) # <- must be here
        # Testing "hacks"
        self._power             = False
        self._voltage_setting   = 0.0
        self._current_limit     = 0.4
        self._state             = "OK"


        #serial interface
        port          = port
        #port          = "COM14"
        baudrate      = Config.PSU.baudrate
        bytesize      = Config.PSU.bytesize
        parity        = Config.PSU.parity
        stopbits      = Config.PSU.stopbits
        timeout       = Config.PSU.timeout
        write_timeout = None
        xonxoff       = False
        rtscts        = False
        self.serial_port = serial.Serial(port,baudrate,bytesize,parity,
                                        stopbits,timeout,xonxoff,rtscts,
                                        write_timeout)
        # It was supposed to be PSU.port!
        self.port = self.serial_port

        # Delay 100 ms, send line termination, flush
        time.sleep(0.1)
        self.port.write("\r\n".encode("utf-8"))
        self.port.flushOutput()
        self.port.flushInput()

        # Set remote mode
        self.__send_message("SYST:REM") # "System:Remote"
        # PSU apparently does not respond (which is shitty design)

        # Query version
        self.__send_message("SYST:VERS?") # "System:Version?"
        reply = self.__read_message()
        try:
            if len(reply) < len("yyyy.x"):
                raise ValueError()
            if reply[4:5] != '.':
                raise ValueError()
            int(reply[0:4])
            int(reply[5:6])
        except:
            raise ValueError("Device is not Agilent E3631?")

        # Select output terminal
        self.__send_message("Instrument:Select P25V")
        # Apparently again, no reply



    def __send_message(self,message_data_str_out):
        """Copied from 'PSU_class_010.py', 09.11.2018. Modified 24.11.2018."""
    
        #add LF and CR characters to the end of message 
        LF_char = 0x0A      #integer, Line feed
        CR_char = 0x0D      #integer, Carriage return
        LF_str = "{0:1c}".format(LF_char)
        CR_str = "{0:1c}".format(CR_char)            
        output_message = message_data_str_out+CR_str+LF_str
        output_message_byte=output_message.encode('utf-8')

        #write data to serial port
        bytes_written=self.serial_port.write(output_message_byte)



    def __read_message(self):
        """read message from PSU
        Copied from 'PSU_class_010.py', 09.11.2018. Modified 24.11.2018."""
        received_message_bytes=self.serial_port.read_until(b'\r\n',20) #read max. 20 bytes from serial
        if received_message_bytes[-1:] != b'\n': 
            raise serial.SerialTimeoutException(
                "Serial read timeout! ({}s)".format(
                    self.serial_port.timeout
                )
            )
        return received_message_bytes.decode('utf-8')[:-2]



    
    def get_version(self):
        """test purpose only"""
        input_message=self.__get_version()
        return input_message

    def __get_version(self):
        """Read SCPI -version from PSU
        Copied from 'PSU_class_010.py', 09.11.2018."""

        self.__send_message("System:Version?")
        input_message_byte=self.__read_message()  
        input_message=input_message_byte.decode('utf-8')    #convert to string 
            
        version_number=float(input_message)
        version_number=version_number+0.002 # What the ... ???
            
        return input_message            



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

# EOF
