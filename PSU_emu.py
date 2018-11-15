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
import random

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
            if self.psu._power:
                return abs(random.uniform(
                    self.psu._voltage_setting - 0.07,
                    self.psu._voltage_setting + 0.07
                ))
            else:
                return random.uniform(0.0, 0.002)
            #self.psu.__send_message("MEASure:VOLTage")
            #return float(self.psu.__read_message())

        def current(self) -> float:
            """Read measured current from the device."""
            return self.voltage() / random.uniform(10.0, 20.0) # Ohm's law
            #self.psu.__send_message("MEASure:CURRent")
            #return float(self.psu.__read_message())


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        return self._power
        #return self.__read_message("Read power output value SCPI command...")
    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF. Setting is read back from the device
        and returned by this function (confirmation)."""
        self._power = value
        return self.power
        #self.__send_message("Toggle power output SCPI command...")
        #self.__read_message()
        #return self.power


    @property
    def voltage(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        return self._voltage_setting
        #self.__send_message("VOLTage:Get")
        #return float(self.__read_message())
    @voltage.setter
    def voltage(self, value: float) -> float:
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        self._voltage_setting = value
        return self.voltage
        #self.__send_message("VOLTage:Set:{}".format(value))
        #self.__read_message()
        #return self.voltage


    @property
    def current_limit(self) -> float:
        """Read PSU current limit setting."""
        return self._current_limit
        #self.__send_message("Get limit SCPI command...")
        #return float(self.__read_message("Get limit SCPI command..."))
    @current_limit.setter
    def current_limit(self, value: float) -> float:
        """Set SPU current limit value."""
        self._current_limit = value
        return self.current_limit
        #self.__send_message("Set limit SCPI command...")
        #self.__read_message()
        #return self.current_limit


    @property
    def state(self) -> str:
        """Read PSU Status (has/is current limit reached)."""
        return self._state
        #self.__send_message("Query current limit status...")
        #return ("OVER CURRENT", "OK")[(self.__read_message() == "<OK string response>")]


    @property
    def values(self) -> dict:
        """Returns a tuple for SQL INSERT."""
        return dict({
            "power"             : "ON" if self.power else "OFF",
            "voltage_setting"   : self.voltage,
            "current_limit"     : self.current_limit,
            "measured_current"  : self.measure.current(),
            "measured_voltage"  : self.measure.voltage(),
            "state"             : self.state
        })


    ###########################################################################
    #
    # Static method for finding the correct port
    #
    # NOTE: Completely untested.
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
                    timeout       = 0.1,
                    write_timeout = None
                )
                # Assuming 'yyyy.xx' return format
                response = transact(port, 'System:Version?')
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
        for p in serial.tools.list_ports.comports(include_links=False):
            if found_at(p):
                port = p
                break
        return port


    # testing __init__()
    def __init__(self, port):
        self.measure            = self.Measure(self) # <- must be here
        self._power             = False
        self._voltage_setting   = 0.0
        self._current_limit     = 0.4
        self._state             = "OK"

    ###########################################################################
    #
    # PSU "Private" methods
    #
    #   These may be freely changed. Client code will NOT access any of these
    #   methods.
    #
    #   NOTE: __init__() signature must remain as specified.
    #
    def __init__DISABLED(self, port = None):
        """Initialize object and test that we are connected to PSU by issuing a version query.
        If port argument is omitted, Config.PSU.Serial.port is used."""
        self.measure = self.Measure(self) # <- must be here
        # def __init__(self,serial_port1,read_timeout):
        """Copied from 'PSU_class_010.py', 09.11.2018."""
        #initialize and open serial port
        #raise SerialException if device cannot be configured
        #raise ValueException if parameters are out of range

        #serial interface
        port          = serial_port1
        #port          = "COM14"
        baudrate      = Config.PSU.baudrate
        bytesize      = Config.PSU.bytesize
        parity        = Config.PSU.parity
        stopbits      = Config.PSU.stopbits
        timeout       = read_timeout
        write_timeout = None
        xonxoff       = False
        rtscts        = False
        #note: port -parameter is needed to scan serial ports
        #note: port and timeout is not read from config.py -file
        #note: change to self ? reading directly from here       
        print('init port {0:s}..... '.format(serial_port1),end='')

        #print('init port',serial_port1,'..... ',end='')     #Python 3.0 or newer version required
        
        #open serial port
        try:
            self.serial_port = serial.Serial(port,baudrate,bytesize,parity,
                                        stopbits,timeout,xonxoff,rtscts,
                                        write_timeout)
        except:
            print('failed')
            raise
        else:
            print('OK')

        """
        except Exception as ex:
            print('other exception')
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            print ("exeption1:",message)
            raise"""

        #todo: add/check DTR control

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

        #todo: test if no exceptions
        print('send:',message_data_str_out)
        if common.debug_info==True:
        #if debug_info==True:
            print('bytes written:',bytes_written)
        return


    def __read_message(self):
        """read message from PSU
        Copied from 'PSU_class_010.py', 09.11.2018."""
        #read message from PSU
        #return bytestring
        #raises ValueError if message is not received

        print('read timeout:',self.serial_port.timeout)
        #received_message_bytes=self.serial_port.read(4) #read 4 bytes from serial
        received_message_bytes=self.serial_port.read_until(b'\r\n',10) #read max. 10 bytes from serial
        if received_message_bytes[-1:] != b'\n': 
            print ('timeout')
            raise ValueError("Serial read timeout! ({}s)".format(self.serial_port.timeout))
        else:
            print('received bytes (max 10):',received_message_bytes)
        return received_message_bytes       #return bytestring


    def __set_output_channel(self, channel='P6V'):
        """Copied from 'PSU_class_010.py', 09.11.2018."""
        #assert(channel in ['P6V', 'P25V','N25V'])
        output_message = 'Instrument:Select {0:s}'.format(channel)
        print('output message:',output_message)
        self.send_message(output_message)
        return


    def __check_SCPI_version(self,version='-'):
        """Copied from 'PSU_class_010.py', 09.11.2018."""
        #check if version is equal to SCPI version of the PSU
        #compare bytestrings
                        
        #Version format is YYYY.V
        correct_version="1995.0"
        print('Checking SCPI version ..... ',end='')
        #correct_version_byte=correct_version.encode('utf-8')
      
        #LF_str = "{0:1c}".format(LF_char)
        #if input_message_byte[0]==correct_version_byte[0]:
        if version[0] == correct_version[0]:
            print('ok')
            return True    
        else:
            print('failed') 
            return False
              
            #raise NameError('Version not found')
            #raise ValueError


    def __get_version(self):
        """Read SCPI -version from PSU
        Copied from 'PSU_class_010.py', 09.11.2018."""
        #read SCPI -version from PSU
        #returns SCPI -version of the PSU in string -format
        #raises ValueError if version is not found

        self.send_message("System:Version?")
        print()
        #read input message
        #raise exception if message is not received  (timeout)
        try:
            input_message_byte=self.read_message()  
             
        except ValueError:
            #timeout
            print('ValueError exception')
            raise
        
        else:
             #message received
            input_message=input_message_byte.decode('utf-8')    #convert to string 
            #print('SCPI version:',input_message)
            return input_message            



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
