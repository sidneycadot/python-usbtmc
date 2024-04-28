#! /usr/bin/env -S python3 -B

import contextlib
from io import BytesIO
import os
import sys

from usbtmc import UsbTmcInterface

if sys.platform == "win32":
    # In Windows, we need to point to the libusb-1.0 DLL explicitly.
    filename = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "windows", "libusb-1.0.dll"))
    if not os.path.exists(filename):
        raise RuntimeError("Cannot find the library.")
    print("Setting libusb filename as:", filename)
    os.environ["LIBUSB_LIBRARY_PATH"] = filename
    del filename


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


def main():

    """Run USBTMC tests."""

    print("Running tests ...")

    usbtmc_device = UsbTmcInterface(vid=0x0957, pid=0x5707)
    usbtmc_device.open()
    with contextlib.closing(usbtmc_device):

        device_info = usbtmc_device.get_device_info()
        print(device_info)

        test_identification_start = True
        if test_identification_start:
            usbtmc_device.write_usbtmc_message("*IDN?")
            response = usbtmc_device.read_usbtmc_message()
            print(response)

        screendump = True
        if screendump:
            usbtmc_device.write_usbtmc_message("HCOPY:SDUMP:DATA:FORMAT BMP")
            usbtmc_device.write_usbtmc_message("HCOPY:SDUMP:DATA?")
            response = usbtmc_device.read_usbtmc_binary_message()
            image = parse_definite_length_binary_block(response)
            write_screendump = False
            if write_screendump:
                with open("H:\\vm_shared\\pythontest.bmp", "wb") as fo:
                    fo.write(image)

        make_wave = True
        if make_wave:
            num_samples = 20000
            data = bytes(4 * num_samples)
            usbtmc_device.write_usbtmc_message("DATA:VOLATILE:CLEAR")
            usbtmc_device.write_usbtmc_message("DATA:ARBITRARY2:FORMAT ABAB")
            usbtmc_device.write_usbtmc_message("DATA:ARBITRARY2:DAC henk,", make_definite_length_binary_block(data))

        multiple_commands = True
        if multiple_commands:
            usbtmc_device.write_usbtmc_message("FREQ?;FREQ?;FREQ?;FREQ?;FREQ?;FREQ?;FREQ?;FREQ?")
            response = usbtmc_device.read_usbtmc_message()
            print("multiple_commands response:", response)

        test_capabilities_request = True
        if test_capabilities_request:
            capabilities = usbtmc_device.get_capabilities()
            print("Capabilities:", capabilities)

        test_indicator_pulse_request = True
        if test_indicator_pulse_request:
            usbtmc_device.indicator_pulse()

        test_trigger_request = False
        if test_trigger_request:
            usbtmc_device.trigger()

        test_identification_end = True
        if test_identification_end:
            usbtmc_device.write_usbtmc_message("*IDN?")
            response = usbtmc_device.read_usbtmc_message()
            print(response)

    print("All done.")


if __name__ == "__main__":
    main()
