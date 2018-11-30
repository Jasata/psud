#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PSU.py -  Original work by Jarkko Pesonen <jarpeson@utu.fi>,
#           modified by Jani Tammi <jasata.utu.fi>
#   0.4.0   2018.11.30  Renamed as 'PSU.py'.
#   0.4.1   2018.11.30  Removed trailing whitespaces and couple of TABs.
#   0.4.2   2018.11.30  Changed import from 'Config_02W' to 'Config'.
#   0.4.3   2018.11.30  Removed debug print messages.
#   0.4.4   2018.11.30  Removed unnecessary try .. catch blocks.
#   0.4.5   2018.11.30  Removed unnecessary comments and commented-out blocks.
#   0.4.6   2018.11.30  Fixed static method .find()
#
#
# PSU_A017W.py - Jarkko Pesonen <jarpeson@utu.fi>
#   0.1     2018.10.15  Initial version.
#   0.2     2018.11.11  Reviced interface.
#   0.3     2018.11.30  First release.
#
# Version 0.3 (2018.11.30) ('PSU_A017W.py') incorporated from GitHub repository
# https://github.com/jarseson/pmpsu.git, and renamed to 'PSU.py'.
#
# This class interface uses typing (Python 3.5+) for public methods.
# https://docs.python.org/3/library/typing.html
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
    #       PSU().status                str             ["OVER CURRENT" | "OK"]
    #       PSU().port                  serial.Serial
    # PSU functions:
    #       PSU().values_tuple()        tuple
    #       PSU.find()                  str             ["/dev/.." | None]
    #
    # notes
    # PSU requires about 10 seconds for initial startup before using remote interface without handshake

    class Measure:
        """PSU.Measure - nested class providing beautified naming for measurement functions."""
        def __init__(self, psu):
            self.psu = psu

        def voltage(self) -> float:
            """Read measured voltage from the device."""
            #measure PSU output voltage from P25V channel
            output_message = 'Measure:Voltage:DC? P25V'
            self.psu._PSU__send_message(output_message)

            #read input message
            input_message_byte=self.psu._PSU__read_message()
            input_message=input_message_byte.decode('utf-8')
            measured_voltage = float(input_message)
            return measured_voltage


        def current(self) -> float:
            """Read measured current from the device."""
            #measure PSU output current from P25V channel
            output_message = 'Measure:Current:DC? P25V'
            self.psu._PSU__send_message(output_message)

            #read input message
            input_message_byte=self.psu._PSU__read_message()
            input_message=input_message_byte.decode('utf-8')
            measured_current = float(input_message)
            return measured_current


    @property
    def power(self) -> bool:
        """Read PSU power state ("ON" or "OFF")."""
        self.__send_message('Output:state?')
        #read input message
        input_message_byte=self.__read_message()  
        input_message=input_message_byte.decode('utf-8')
        PSU_on_off_status = int(input_message)
        if PSU_on_off_status == 1:
            PSU_power_ON = True
        elif PSU_on_off_status == 0:
            PSU_power_ON = False
        else:
            raise ValueError('value error')
        return PSU_power_ON

    @power.setter
    def power(self, value: bool) -> bool:
        """Toggle power output ON or OFF. Setting is read back from the device
        and returned by this function (confirmation)."""
        if value == True:
            self.__send_message('Output:State ON')
        if value == False: 
            self.__send_message('Output:State OFF')
        return self.power

    #for testing only, old version
    @property
    def voltage_set_value_test(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        time.sleep(0.3)
        #send message
        output_message = 'Source:Voltage:Immediate?'
        self.__send_message(output_message)

        #read input message
        input_message_byte=self.__read_message()
        input_message=input_message_byte.decode('utf-8')
        voltage_set_value_from_PSU = float(input_message)
        return voltage_set_value_from_PSU

    @property
    def voltage(self) -> float:
        """Read PSU voltage setting. NOT the same as measured voltage!"""
        #read voltage set value from PSU

        #send message
        output_message = 'Source:Voltage:Immediate?'
        self.__send_message(output_message)

        #read input message
        input_message_byte=self.__read_message()
        input_message=input_message_byte.decode('utf-8')
        voltage_set_value_from_PSU = float(input_message)
        return voltage_set_value_from_PSU


    @voltage.setter
    def voltage(self, voltage_set_value: float = None) -> float:
        """Set PSU voltage. After setting the value, the setting read back
        and returned. NOTE: This is NOT the measured actual output voltage!"""
        if voltage_set_value:
            output_message = 'Source:Voltage:Immediate {0:1.3f}'.format(voltage_set_value)
            self.__send_message(output_message)
            return self.voltage


    @property
    def current_limit(self) -> float:
        """Read PSU current limit setting."""
        output_message = 'Source:Current:Immediate?'
        self.__send_message(output_message)

        #read input message
        input_message_byte=self.__read_message()
        input_message=input_message_byte.decode('utf-8')
        current_limit_from_PSU = float(input_message)
        return current_limit_from_PSU

    @current_limit.setter
    def current_limit(self, current_set_value:float = None) -> float:
        """Set PSU current limit value."""
        if current_set_value:
            output_message = 'Source:Current:Immediate {0:1.3f}'.format(current_set_value)
            self.__send_message(output_message)
        return self.current_limit


    @property
    def status(self) -> str:
        """Read PSU Status (has/is current limit reached)."""
        self.__send_message("Query current limit status...")
        return ("OVER CURRENT", "OK")[(self.__read_message() == "<OK string response>")]

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
    # (This function written by Jani Tammi)
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
        self.measure = self.Measure(self)

        port          = port
        baudrate      = Config.PSU.baudrate
        bytesize      = Config.PSU.bytesize
        parity        = Config.PSU.parity
        stopbits      = Config.PSU.stopbits
        timeout       = Config.PSU.timeout
        write_timeout = None
        xonxoff       = False
        rtscts        = False
        dsrdtr        = True

        self.serial_port = serial.Serial(port,baudrate,bytesize,parity,
                                        stopbits,timeout,xonxoff,rtscts,
                                        write_timeout,dsrdtr)

        #set remote mode
        self.__set_remote_mode()

        #set power ON
        self.power = True
        #check ON/OFF status from PSU
        PSU_status = self.power
        #should be True during Init
        if PSU_status == False:
            raise ValueError('ON/OFF status not verified')

        #select +25 V channel
        self.__select_channel('P25V')
        #read and verify selected channel
        selected_channel_from_PSU=self.__read_selected_channel()
        if selected_channel_from_PSU[0:4] == 'P25V':

            #set default voltage
            self.voltage=Config.PSU.default_voltage
            #verify default voltage
            voltage_set_value_from_PSU = self.voltage
            if voltage_set_value_from_PSU == Config.PSU.default_voltage:

                self.current_limit=Config.PSU.default_current_limit
                #verify current limit
                current_limit_from_PSU = self.current_limit
                if current_limit_from_PSU == Config.PSU.default_current_limit:
                    pass
                else:
                    raise ValueError('Current limit setting not verified')
            else:
                raise ValueError('Output voltage setting not verified')
        else:
            raise ValueError('selected channel not verified')


    def __send_message(self,message_data_str_out):
        LF_char = 0x0A
        CR_char = 0x0D
        LF_str = "{0:1c}".format(LF_char)
        CR_str = "{0:1c}".format(CR_char)
        output_message = message_data_str_out+CR_str+LF_str
        output_message_byte=output_message.encode('utf-8')

        bytes_written=self.serial_port.write(output_message_byte)

        return


    def __read_message(self):
        """read message from PSU."""
        received_message_bytes=self.serial_port.read_until(b'\r\n',20)
        if received_message_bytes[-1:] != b'\n':
            raise ValueError("Serial read timeout! ({0:1.2f} s)".format(self.serial_port.timeout))

        return received_message_bytes

    def read_selected_channel(self):
        selected_channel_from_PSU=self.__read_selected_channel()
        return selected_channel_from_PSU

    def __read_selected_channel(self):
        output_message = 'Instrument:Select?'
        self.__send_message(output_message)
        input_message_byte=self.__read_message()
        input_message=input_message_byte.decode('utf-8')
        return input_message

    #test only
    def select_channel_long_msg(self,channel):
        """test purpose only"""
        self.__select_channel_long_msg(channel)

    #test only
    def select_channel(self,channel):
        """test purpose only"""
        self.__select_channel(channel)



    #long message 
    def __select_channel_long_msg(self, channel='P6V'):
        output_message = 'Instrument:Select {0:s}'.format(channel)
        self.__send_message(output_message)
        return

    #short message
    def __select_channel(self, channel='P6V'):
        #assert(channel in ['P6V', 'P25V','N25V'])
        output_message = 'INST:SEL {0:s}'.format(channel)
        self.__send_message(output_message)
        return

    
    def check_SCPI_version(self):
        """test purpose only"""
        self.__check_SCPI_version()

    #old version
    def __check_SCPI_version(self,version='-'):
        #Version format is YYYY.V
        correct_version="1995.0"
        if version[0] == correct_version[0]:
            return True
        else:
            return False


    def set_remote_mode(self):
        self.__send_message("System:Remote")

    def __set_remote_mode(self):
        #time.sleep(0.3)
        self.__send_message("System:Remote")

    def get_version(self):
        """test purpose only"""
        input_message=self.__get_version()
        return input_message

    def __get_version(self):
        """Read SCPI -version from PSU."""
        self.__send_message("System:Version?")
        input_message_byte=self.__read_message()  
        input_message=input_message_byte.decode('utf-8')

        #test only
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
        print(psu.values_tuple)


        psu.power = False
        psu.voltage = 3.3
        psu.current_limit = 0.3
        if psu.measure.voltage() > 0.02:
            raise ValueError("Unexpected voltage at terminal!")


        psu.power = True
        if abs(psu.measure.voltage() - psu.voltage) > 0.05:
            raise ValueError("Unexpected voltage difference between set and measured values!")


        print(psu.values_tuple)
        psu.power = False


# EOF
