#! /usr/bin/env -S python3 -B

"""Communicate with the Thorlabs PM100D powermeter."""

import contextlib
import time
import struct
from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc_tests.devices.utilities import initialize_libusb_library_path_environment_variable, usbtmc_query


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    """Test *IDN? command."""
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"Device identifies as follows: {response}")


def check_status(usbtmc_interface: UsbTmcInterface) -> None:
    """Test several device query commands."""
    commands = [
        ":SYSTEM:LFREQUENCY?",
        ":SYSTEM:VERSION?",
        ":SYSTEM:DATE?",
        ":SYSTEM:TIME?",
        ":CALIBRATION:STRING?",
        ":CORRECTION:WAVELENGTH?",
        ":CORRECTION:BEAMDIAMETER?",
        "*STB?"
    ]

    print("Query commands:")
    for command in commands:
        response = usbtmc_query(usbtmc_interface, command)
        print(f"  {command!r} -> {response!r}")


def test_screendump(usbtmc_interface: UsbTmcInterface) -> None:
    """The screendump is returned as a message, and is a bastardized BMP format."""

    usbtmc_interface.write_message(f"DISPLAY:DATA?")
    t1 = time.monotonic()
    image_data = usbtmc_interface.read_binary_message()
    t2 = time.monotonic()
    print(f"Retrieved {len(image_data)} image data bytes in {t2 - t1:.3f} seconds.")

    image_data = fix_screenshot_data(image_data)

    with open("screendump.bmp", "wb") as fo:
        fo.write(image_data)


def run_tests(vid: int, pid: int, serial: Optional[str] = None) -> None:
    """Run USBTMC tests."""

    initialize_libusb_library_path_environment_variable()

    usbtmc_interface = UsbTmcInterface(vid=vid, pid=pid, serial=serial)
    usbtmc_interface.open()
    with contextlib.closing(usbtmc_interface):

        device_info = usbtmc_interface.get_device_info()
        device_model = device_info.manufacturer + " " + device_info.product

        print()
        print(f"Running tests on device model: '{device_model}' ...")
        print()

        test_identification(usbtmc_interface)

        check_status(usbtmc_interface)

    print()
    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x1313, 0x8078)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
