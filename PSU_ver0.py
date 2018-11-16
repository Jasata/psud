#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PSU.py - Jarkko Pesonen <jarpeson@utu.fi>
#   0.1     2018.10.15  Initial version.
#   0.2     2018.11.11  Reviced interface.
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
            time.sleep(__SLEEP__)
            self.psu._PSU__send_message("Measure:Voltage?")
            input_message_byte=self.psu._PSU__read_message()  
             
            #message received
            input_message=input_message_byte.decode('utf-8')
            measured_voltage=float(input_message)

            return measured_voltage         

        def current(self) -> float:
            """Read measured current from the device."""
            time.sleep(__SLEEP__)
            self.psu._PSU__send_message("MEASure:CURRent?")
            return float(self.psu._PSU__read_message())


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        #return self.__read_message("Read power output value SCPI command...")
        return self._power
		
    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF. Setting is read back from the device
        and returned by this function (confirmation)."""  
        time.sleep(__SLEEP__)
        if value == True:
            self.__send_message('Output:State ON')
        if value == False: 
            self.__send_message('Output:State OFF')
        self._power = value
        return self._power


    @property
    def voltage(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        time.sleep(__SLEEP__)
        #send message
        output_message = 'Source:Voltage:Immediate?'
        self.__send_message(output_message)

        input_message_byte=self.__read_message()             
        input_message=input_message_byte.decode('utf-8')    #convert to string 
        voltage_set_value_from_PSU = float(input_message)
        return voltage_set_value_from_PSU
    @voltage.setter
    #def voltage(self, value: float) -> float:
    def voltage(self, voltage_set_value: float = None) -> float:
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        time.sleep(__SLEEP__)
        if voltage_set_value:
            output_message = 'Source:Voltage:Immediate {0:1.3f}'.format(voltage_set_value)      #output setting at 1 mV accuracy
            self.__send_message(output_message)
        return self.voltage
         

    @property
    def current_limit(self) -> float:
        """Read PSU current limit setting."""
        return self._current_limit
    @current_limit.setter
    def current_limit(self, value:float = None) -> float:
        """Set PSU current limit value."""
        self._current_limit = value
        return self.current_limit


    @property
    def state(self) -> str:
        """Read PSU state (has/is current limit reached)."""
        return self._state


    @property
    def values(self) -> dict:
        """Returns a tuple for SQL INSERT."""
        try:
            _ = self.power
        except:
            print("self.power")
        try:
            _ = self.voltage
        except:
            print("self.voltage")
        try:
            _ = self.current_limit
        except:
            print("self.current_limit")
        try:
            _ = self.measure.voltage()
        except:
            print("self.measure.voltage()")
        try:
            _ = self.measure.current()
        except:
            print("self.measure.current()")
        try:
            _ = self.state
        except:
            print("self.state")
        try:
            return dict({
                "power"               :"ON" if self.power else "OFF",
                "voltage_setting"     :self.voltage,
                "current_limit"       :self.current_limit,
                "measured_current"    :self.measure.current(),
                "measured_voltage"    :self.measure.voltage(),
                "state"               :self.state
            })
        except Exception as e:
            print("IT IS AWFUL", str(e))


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
        """Initialize object and test that we are connected to PSU by issuing a version query.
        If port argument is omitted, Config.PSU.Serial.port is used."""
        self.measure = self.Measure(self) # <- must be here
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
        self.__set_remote_mode()
        self.power = True
            

    def __send_message(self,message_data_str_out):
        """Copied from 'PSU_class_010.py', 09.11.2018."""
    
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
        Copied from 'PSU_class_010.py', 09.11.2018."""
        received_message_bytes=self.serial_port.read_until(b'\r\n',20) #read max. 20 bytes from serial
        if received_message_bytes[-1:] != b'\n': 
            raise ValueError("Serial read timeout! ({}s)".format(self.serial_port.timeout))
        return received_message_bytes       #return bytestring


    def set_output_channel(self,channel):
        """test purpose only"""
        self.__set_output_channel(channel)

    def __set_output_channel(self, channel='P6V'):
        """Copied from 'PSU_class_010.py', 09.11.2018."""
        #assert(channel in ['P6V', 'P25V','N25V'])
        output_message = 'Instrument:Select {0:s}'.format(channel)
        self.__send_message(output_message)

    
    def check_SCPI_version(self):
        """test purpose only"""
        self.__check_SCPI_version()

    def __check_SCPI_version(self,version='-'):
        """Copied from 'PSU_class_010.py', 09.11.2018."""
        #check if version is equal to SCPI version of the PSU
        #compare bytestrings
                        
        #Version format is YYYY.V
        correct_version="1995.0"
        #correct_version_byte=correct_version.encode('utf-8')
      
        #LF_str = "{0:1c}".format(LF_char)
        #if input_message_byte[0]==correct_version_byte[0]:
        if version[0] == correct_version[0]:
            return True    
        else:
            return False


    def set_remote_mode(self):
        self.__send_message("System:Remote")

    def __set_remote_mode(self):
        self.__send_message("System:Remote")

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
        version_number=version_number+0.002
            
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
