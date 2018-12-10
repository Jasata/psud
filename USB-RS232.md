# USB / RS-232 Serial Adapter
10.12.2018

A RS-232 serial line is needed to run Agilent E3631A in a remote mode. Given that very few computers have serial hardware in them anymore, the most common way to accomplish this is to acquire an USB / RS-232 serial adapter.

The E3631A serial communications are based on **DSR/DTR hardware flow control**. Unfortunately, these lines are not always broken out from USB serial adapters. Especially, the cheapest serial adapters generally lack these lines.

A DSR/DTR capable serial adapter was ordered from verkkokauppa.com and it was used for two months by our extra resource. When the work received, it was based on hardcoded delays. This was understandable, as the "promised" DSR/DTR flow control was in fact a "lie" - rising DTR turned out to mean **only** that the MCU responsible for serial communications was ready - the instrument made no such promises from it's part!

The hardcoded delays meant that the performance was just barely in the acceptable range, but we could have left it as-is.. however, with superficial testing, even with the lengthy delays, the implementation still suffered from timeouts.

A rather big surprise soon followed, as it turned out that the PySerial DSR/DTR flow control apparently ... did nothing at all! Or perhaps we completely misunderstood what it was promising to do. Be as it may, it was most definately **not** waiting for the DTR line to come up before blasting the next command down the line. Small matter of just writing a handler that explicitly observes the DTR and that issue was dealth with. However, it did nothing to the occasional timeouts...

Previously, the hardcoded delays were given to all commands, but with little poking around, it turned out that apparently only those commands that changed the operation of the PSU, needed additional "recovery time". However, this discovery did not solve the occasional timeouts, although it did improve the overall performance nicely.

Next, a retry scheme was implemented, which would repeat sending the command and retry reading the response (adjustable, but in this implementation, three times) before giving up. This seemed to deal with some issues, such as becoming able to read the version string `CTRL-C` output buffer flush command (always seems to take at least two tries). But some errors still persisted.

At this point, verbose output of the communications was implemented, which revealed something unexpected. The PySerial would return obviously wrong replies! More specifically, the last reply. While the very first SCPI command that produced a reply, would succeed (version query, which receives a reply string "1995.0"), the next one ("INST?" expecting to see the terminal name "P25V") would also return "1995.0"!

Writing a Serial().flushInput() into the serial transaction method (meaning, the port input would be flushed every single time) let the "INST?" query to receive correct reply, but the third command ("APPL? P25V") would now receive the same response as "INST?" received... even though, the input was flushed just as the same each time.

With the recommendation of Jarno Tuominen, a different adapter was borrowed from local IT staff. With this new adapter, all remaining problems vanished.

I cannot understand how the USB/RS-232 implementation can malfunction like that .. without becoming unusable to, well, virtually any use at all. But as long as we have a functioning solution, I will not dive into this matter any further.

# Example output from tests

    jani@fs-debian:/srv/psud$ ./PSU.py /dev/ttyUSB0
    [   0.162] Using port '/dev/ttyUSB0'
    [   1.542] DTR wait after PSU.flush(): 0.40 ms
    [   1.593] self._last_read set to None ('None')
    [   2.045] __write('SYST:VERS?') waited DTR for 0.41 ms
    [ 216.419] Retry #3
    [ 351.554] __write('SYST:VERS?') waited DTR for 135.07 ms
    [ 366.117] __transact('SYST:VERS?') -> '1995.0'
    [ 428.804] __write('SYST:REM') waited DTR for 62.61 ms
    [ 429.428] __write('INST P25V') waited DTR for 0.53 ms
    [ 429.513] self._last_read set to None ('None')
    [ 430.082] __write('INST?') waited DTR for 0.52 ms
    [ 440.830] __transact('INST?') -> '1995.0'
    Traceback (most recent call last):
      File "./PSU.py", line 585, in <module>
        with PSU(port) as psu:
      File "./PSU.py", line 399, in __init__
        self._last_read
    ValueError: Unable to select output terminal! Returned: '1995.0'


    jani@fs-debian:/srv/psud$ ./PSU.py /dev/ttyUSB0
    [   0.153] Using port '/dev/ttyUSB0'
    [   1.611] DTR wait after PSU.flush(): 0.53 ms
    [   1.664] self._last_read set to None ('None')
    [   2.362] __write('SYST:VERS?') waited DTR for 0.51 ms
    [  63.393] __transact('SYST:VERS?') -> '1995.0'
    [  64.009] __write('SYST:REM') waited DTR for 0.54 ms
    [  64.640] __write('INST P25V') waited DTR for 0.53 ms
    [  64.731] self._last_read set to None ('None')
    [ 140.391] __write('INST?') waited DTR for 52.38 ms
    [ 348.930] Retry #3
    [ 349.743] __write('INST?') waited DTR for 0.48 ms
    [ 558.340] Retry #2
    [ 665.629] __write('INST?') waited DTR for 107.04 ms
    [ 674.366] __transact('INST?') -> 'P25V'
    [ 736.633] __write('APPL P25V,7.400,0.500') waited DTR for 62.20 ms
    [ 736.721] self._last_read set to None ('None')
    [ 760.507] __write('APPL? P25V') waited DTR for 0.50 ms
    [ 763.619] __transact('APPL? P25V') -> 'P25V'
    Traceback (most recent call last):
      File "./PSU.py", line 588, in <module>
        with PSU(port) as psu:
      File "./PSU.py", line 420, in __init__
        )[1:][:-1].split(",")
    ValueError: not enough values to unpack (expected 2, got 1)

With working USB/RS-232 adapter:

    jani@fs-debian:/srv/psud$ ./PSU.py /dev/ttyUSB1
    [   0.184] Using port '/dev/ttyUSB1'
    [ 202.840] DTR wait after PSU.flush(): 0.54 ms
    [ 202.893] self._last_read set to None ('None')
    [ 203.589] __write('SYST:VERS?') waited DTR for 0.51 ms
    [ 275.352] __transact('SYST:VERS?') -> '1995.0'
    [ 275.836] __write('SYST:REM') waited DTR for 0.40 ms
    [ 276.364] __write('INST P25V') waited DTR for 0.43 ms
    [ 276.492] self._last_read set to None ('None')
    [ 342.493] __write('INST?') waited DTR for 42.00 ms
    [ 851.504] Retry #3
    [ 852.228] __write('INST?') waited DTR for 0.51 ms
    [1159.695] __transact('INST?') -> 'P25V'
    [1160.256] __write('APPL P25V,7.400,0.500') waited DTR for 0.49 ms
    [1160.345] self._last_read set to None ('None')
    [1306.865] __write('APPL? P25V') waited DTR for 114.50 ms
    [1411.561] __transact('APPL? P25V') -> '"7.400000,0.500000"'
    [1411.624] self._last_read set to None ('None')
    [1412.486] __write('MEAS?') waited DTR for 0.47 ms
    [1675.105] __transact('MEAS?') -> '+5.89410700E-03'
    [1675.158] Volts: 0.005
    [1675.195] self._last_read set to None ('None')
    [1675.993] __write('OUTP?') waited DTR for 0.50 ms
    [1734.765] __transact('OUTP?') -> '0'
    [1734.816] self._last_read set to None ('None')
    [1735.617] __write('SOUR:VOLT:IMM?') waited DTR for 0.47 ms
    [1838.535] __transact('SOUR:VOLT:IMM?') -> '+7.40000000E+00'
    [1838.586] self._last_read set to None ('None')
    [1839.368] __write('CURR?') waited DTR for 0.48 ms
    [1922.701] __transact('CURR?') -> '+5.00000000E-01'
    [1922.752] self._last_read set to None ('None')
    [1923.495] __write('MEAS:CURR?') waited DTR for 0.50 ms
    [2157.443] __transact('MEAS:CURR?') -> '-4.61115500E-04'
    [2157.492] self._last_read set to None ('None')
    [2158.249] __write('MEAS?') waited DTR for 0.50 ms
    [2389.488] __transact('MEAS?') -> '+5.89410700E-03'
    [2389.536] {'measured_voltage': Decimal('0.00589410700'), 'current_limit': Decimal('0.500000000'), 'measured_current': Decimal('-0.000461115500'), 'power': 'ON', 'voltage_setting': Decimal('7.40000000')}
    [2390.127] __write('OUTP OFF') waited DTR for 0.51 ms
    [2390.260] self._last_read set to None ('None')
    [2456.761] __write('OUTP?') waited DTR for 52.35 ms
    [2529.896] __transact('OUTP?') -> '0'
    [2530.383] __write('VOLT 3.3') waited DTR for 0.41 ms
    [2531.058] __write('CURR 0.3') waited DTR for 0.56 ms
    [2531.658] __write('OUTP ON') waited DTR for 0.49 ms
    [2531.756] self._last_read set to None ('None')
    [2661.513] __write('OUTP?') waited DTR for 96.88 ms
    [3170.522] Retry #3
    [3171.267] __write('OUTP?') waited DTR for 0.50 ms
    [3481.162] __transact('OUTP?') -> '1'
    [3481.210] self._last_read set to None ('None')
    [3481.897] __write('MEAS?') waited DTR for 0.50 ms
    [3759.486] __transact('MEAS?') -> '+3.30649800E+00'
    [3759.536] self._last_read set to None ('None')
    [3760.279] __write('SOUR:VOLT:IMM?') waited DTR for 0.50 ms
    [3844.369] __transact('SOUR:VOLT:IMM?') -> '+3.30000000E+00'
    [3844.419] Set: 3.30000000, Measured: 3.30649800
    [3844.445] self._last_read set to None ('None')
    [3845.191] __write('SOUR:VOLT:IMM?') waited DTR for 0.54 ms
    [3929.124] __transact('SOUR:VOLT:IMM?') -> '+3.30000000E+00'
    [3929.658] __write('OUTP ON') waited DTR for 0.44 ms
    [3929.746] self._last_read set to None ('None')
    [4100.113] __write('OUTP?') waited DTR for 155.70 ms
    [4175.680] __transact('OUTP?') -> '1'
    [4175.727] self._last_read set to None ('None')
    [4176.535] __write('MEAS?') waited DTR for 0.50 ms
    [4417.793] __transact('MEAS?') -> '+3.30659400E+00'
    [4417.842] self._last_read set to None ('None')
    [4418.545] __write('SOUR:VOLT:IMM?') waited DTR for 0.50 ms
    [4503.779] __transact('SOUR:VOLT:IMM?') -> '+3.30000000E+00'
    [4503.846] self._last_read set to None ('None')
    [4504.549] __write('OUTP?') waited DTR for 0.51 ms
    [4560.681] __transact('OUTP?') -> '1'
    [4560.725] self._last_read set to None ('None')
    [4561.542] __write('SOUR:VOLT:IMM?') waited DTR for 0.50 ms
    [4661.921] __transact('SOUR:VOLT:IMM?') -> '+3.30000000E+00'
    [4661.971] self._last_read set to None ('None')
    [4662.669] __write('CURR?') waited DTR for 0.50 ms
    [4743.801] __transact('CURR?') -> '+3.00000000E-01'
    [4743.850] self._last_read set to None ('None')
    [4744.542] __write('MEAS:CURR?') waited DTR for 0.51 ms
    [4973.013] __transact('MEAS:CURR?') -> '-4.16898900E-04'
    [4973.060] self._last_read set to None ('None')
    [4973.799] __write('MEAS?') waited DTR for 0.50 ms
    [5198.944] __transact('MEAS?') -> '+3.30646600E+00'
    [5198.991] {'measured_voltage': Decimal('3.30646600'), 'current_limit': Decimal('0.300000000'), 'measured_current': Decimal('-0.000416898900'), 'power': 'ON', 'voltage_setting': Decimal('3.30000000')}
    [5199.553] __write('OUTP OFF') waited DTR for 0.49 ms
    [5199.642] self._last_read set to None ('None')
    [5264.680] __write('OUTP?') waited DTR for 52.22 ms
    [5333.464] __transact('OUTP?') -> '0'
