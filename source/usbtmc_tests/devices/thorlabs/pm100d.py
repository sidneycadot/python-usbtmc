#! /usr/bin/env -S python3 -B

"""Communicate with the Thorlabs PM100D powermeter."""

import contextlib
from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc.utilities import initialize_libusb_library_path_environment_variable, usbtmc_query


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"The device identifies itself as: {response!r}.")
    print()


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
    print()


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

    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x1313, 0x8078)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
