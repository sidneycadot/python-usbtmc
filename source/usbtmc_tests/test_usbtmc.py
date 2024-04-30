#! /usr/bin/env -S python3 -B

""""A basic test program for python-usbtmc."""

import contextlib
from io import BytesIO
import os
import sys
import time
from typing import Optional

from usbtmc import UsbTmcInterface, UsbTmcError


def parse_definite_length_binary_block(data: bytes) -> bytes:
    """Parse an SCPI Definite Length Binary Block (DLBB)."""
    fi = BytesIO(data)
    header = fi.read(2)
    if len(header) != 2:
        raise RuntimeError()
    if not header.startswith(b'#'):
        raise RuntimeError()
    num_size_digits = int(header[1:2])
    if len(data) < 2 + num_size_digits:
        raise RuntimeError()
    size_digits = fi.read(num_size_digits)
    if len(size_digits) != num_size_digits:
        raise RuntimeError()
    size = int(size_digits)

    expected_size = 2 + num_size_digits + size
    if len(data) != expected_size:
        raise RuntimeError()

    block = fi.read(size)
    return block


def make_definite_length_binary_block(data: bytes) -> bytes:
    """Make an SCPI Definite Length Binary Block (DLBB)."""
    fo = BytesIO()

    size = len(data)
    size_digits = str(size).encode('ascii')
    size_digits_size_digit = str(len(size_digits)).encode('ascii')

    fo.write(b'#')
    fo.write(size_digits_size_digit)
    fo.write(size_digits)
    fo.write(data)

    return fo.getvalue()


def run_tests(vid: int, pid: int, serial: Optional[str] = None) -> None:
    """Run USBTMC tests."""

    if sys.platform == "win32" and "LIBUSB_LIBRARY_PATH" not in os.environ:
        # In Windows, we need to explain to usbtmc where the libusb-1.0 DLL can be found.
        # Point to a location relative to where this test's source file can be found.

        filename = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../windows/libusb-1.0.dll"))
        if not os.path.exists(filename):
            raise RuntimeError("Cannot find the libusb library.")
        print("Setting libusb filename to '{}'.".format(filename))
        os.environ["LIBUSB_LIBRARY_PATH"] = filename
        del filename

    print("Running tests ...")

    usbtmc_device = UsbTmcInterface(vid=vid, pid=pid, serial=serial)
    usbtmc_device.open()
    with contextlib.closing(usbtmc_device):

        device_info = usbtmc_device.get_device_info()
        device_model = device_info.manufacturer + " " + device_info.product

        print("Testing device model:", device_model)

        # Define which tests to run.
        test_identification_start = True
        #
        test_capabilities_request = True
        test_indicator_pulse_request = False
        test_two_queries = False
        test_multiple_queries = False
        test_trigger_request = False
        #
        test_screendump = False
        write_screendump = False
        #
        test_waveform_upload = True
        #
        test_identification_end = True
        #
        usbtmc_device.clear_usbtmc_interface()

        if test_identification_start:
            usbtmc_device.write_message("*IDN?")
            response = usbtmc_device.read_message()
            print("Device identification:", response)

        if test_capabilities_request:
            capabilities = usbtmc_device.get_capabilities()
            print("USBTMC capabilities:", capabilities)

        if test_two_queries:
            for interval in range(0, 1000, 17):
                query = "*STB?;" + (" " * interval) + "*STB?"
                usbtmc_device.write_message(query)
                response = usbtmc_device.read_message()
                response = response.split(";")
                if len(response) == 2:
                    print(f"two queries, total size {len(query)} works")
                else:
                    print(f"two queries, total size {len(query)} DOES NOT work")
                    break

        if test_multiple_queries:
            for num_queries in range(50, 100, 50):
                query = ";".join(["*STB?"] * num_queries) + "\n"
                usbtmc_device.write_message(query)
                response = usbtmc_device.read_message()
                response = response.split(";")
                if len(response) == num_queries:
                    print(f"num_queries = {num_queries} works")
                else:
                    print(f"num_queries = {num_queries} DOES NOT work.")
                    break

        if test_indicator_pulse_request:
            usbtmc_device.indicator_pulse()

        if test_trigger_request:
            usbtmc_device.trigger()

        if test_screendump:
            if device_model in ("Keysight Technologies 33622A", "Keysight Technologies 52230A"):
                screendump_format = "bmp"
                usbtmc_device.write_message("HCOPY:SDUMP:DATA:FORMAT {}".format(screendump_format.upper()))
                usbtmc_device.write_message("HCOPY:SDUMP:DATA?")
                response = usbtmc_device.read_binary_message()
                image = parse_definite_length_binary_block(response)
                if write_screendump:
                    with open("screendump.{}".format(screendump_format.lower()), "wb") as fo:
                        fo.write(image)
            elif device_model == "Siglent SDS1204X-E":
                usbtmc_device.write_message("SCDP")
                response = usbtmc_device.read_binary_message()

        if test_waveform_upload:
            if device_model == "Keysight Technologies 33622A":
                num_samples = 100000
                data = bytes(4 * num_samples)

                usbtmc_device.write_message("*ESE 255; *SRE 191; *OPC")

                register_list = [
                    "STAT:QUES:COND?",
                    "STAT:QUES:EVEN?",
                    "STAT:QUES:ENAB?",
                    "STAT:OPER:COND?",
                    "STAT:OPER:EVEN?",
                    "STAT:OPER:ENAB?",
                    "*ESR?",
                    "*ESE?",
                    "*STB?",
                    "*SRE?"
                ]

                for query in register_list:
                    usbtmc_device.write_message(query)
                    response = usbtmc_device.read_message()
                    print(f"query: {query:20} response: {response:20}")

                for query in register_list:
                    usbtmc_device.write_message(query)
                    response = usbtmc_device.read_message()
                    print(f"query: {query:20} response: {response:20}")

                usbtmc_device.write_message("DATA:VOLATILE:CLEAR")
                usbtmc_device.write_message("DATA:ARBITRARY2:FORMAT ABAB")
                usbtmc_device.write_message("DATA:ARBITRARY2:FORMAT ABAB")
                usbtmc_device.write_message("DATA:ARBITRARY2:DAC awg_test,", make_definite_length_binary_block(data))

                for i in range(20):
                    stb = usbtmc_device.read_status_byte()
                    print("stb:", stb)
                    time.sleep(0.200)

                #usbtmc_device.write_message("*STB?")
                #response = usbtmc_device.read_message()
                #print("STB response:", response)

                #usbtmc_device.write_message("*OPC?")
                #response = usbtmc_device.read_message()
                #print("response:", response)

        if test_identification_end:
            usbtmc_device.write_message("*IDN?")
            response = usbtmc_device.read_message()
            print("Device identification:", response)

    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x0957, 0x5707)  # Keysight 33622A
    # (vid, pid) = (0x0957, 0x1907)  # Keysight 55230A
    # (vid, pid) = (0xf4ec, 0xee38)    # Siglent SDS 1204X-E
    # (vid, pid) = (0x1313, 0x8078)  # Thorlabs PM100D

    try:
        run_tests(vid, pid)
    except UsbTmcError as exception:
        print("An exception occurred while executing tests:", exception)
        raise


if __name__ == "__main__":
    main()
