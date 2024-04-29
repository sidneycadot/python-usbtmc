#! /usr/bin/env -S python3 -B

""""A basic test program for python-usbtmc."""

import contextlib
from io import BytesIO
import os
import sys
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
        test_multiple_queries = True
        test_trigger_request = False
        #
        test_screendump = False
        write_screendump = False
        #
        test_waveform_upload = False
        #
        test_identification_end = True
        #
        usbtmc_device.clear_usbtmc_interface()

        if test_identification_start:
            usbtmc_device.write_usbtmc_message("*IDN?")
            response = usbtmc_device.read_usbtmc_message()
            print("Device identification:", response)

        if test_capabilities_request:
            capabilities = usbtmc_device.get_capabilities()
            print("USBTMC capabilities:", capabilities)

        if test_screendump:
            if device_model in ("Keysight 33622A", "Keysight 52230A"):
                screendump_format = "bmp"
                usbtmc_device.write_usbtmc_message("HCOPY:SDUMP:DATA:FORMAT {}".format(screendump_format.upper()))
                usbtmc_device.write_usbtmc_message("HCOPY:SDUMP:DATA?")
                response = usbtmc_device.read_usbtmc_binary_message()
                image = parse_definite_length_binary_block(response)
                if write_screendump:
                    with open("screendump.{}".format(screendump_format.lower()), "wb") as fo:
                        fo.write(image)
            elif device_model == "Siglent SDS1204X-E":
                usbtmc_device.write_usbtmc_message("SCDP")
                response = usbtmc_device.read_usbtmc_binary_message()
                print("@@@", len(response))

        if test_waveform_upload:
            num_samples = 20000
            data = bytes(4 * num_samples)
            usbtmc_device.write_usbtmc_message("DATA:VOLATILE:CLEAR")
            usbtmc_device.write_usbtmc_message("DATA:ARBITRARY2:FORMAT ABAB")
            usbtmc_device.write_usbtmc_message("DATA:ARBITRARY2:DAC henk,", make_definite_length_binary_block(data))

        if test_multiple_queries:
            num_queries = 10
            query = ";".join(["*STB?"] * num_queries) + "\n"
            usbtmc_device.write_usbtmc_message(query)
            response = usbtmc_device.read_usbtmc_message()
            print("Multiple queries response:", response)
            response = response.split(";")
            print("Number of response values:", len(response))

        if test_indicator_pulse_request:
            usbtmc_device.indicator_pulse()

        if test_trigger_request:
            usbtmc_device.trigger()

        if test_identification_end:
            usbtmc_device.write_usbtmc_message("*IDN?")
            response = usbtmc_device.read_usbtmc_message()
            print("Device identification:", response)

    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x0957, 0x5707)  # Keysight 33622A
    #(vid, pid) = (0x0957, 0x1907)  # Keysight 55230A
    #(vid, pid) = (0xf4ec, 0xee38)   # Siglent SDS 1204X-E
    #(vid, pid) = (0x1313, 0x8078)  # Thorlabs PM100D

    try:
        run_tests(vid, pid)
    except UsbTmcError as exception:
        print("An exception occurred while executing tests:", exception)
        raise


if __name__ == "__main__":
    main()
