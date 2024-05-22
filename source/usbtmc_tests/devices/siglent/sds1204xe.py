#! /usr/bin/env -S python3 -B

"""Communicate with the Siglent SDS1204X-E oscilloscope."""

import contextlib
import time
from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc.utilities import initialize_libusb_library_path_environment_variable, usbtmc_query


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"The device identifies itself as: {response!r}.")
    print()


def test_screendump(usbtmc_interface: UsbTmcInterface) -> None:
    """test screendump functionality.

    The screendump is returned as a message, and is a bastardized BMP format."""

    usbtmc_interface.write_message("SCDP")
    t1 = time.monotonic()
    image_data = usbtmc_interface.read_binary_message()
    t2 = time.monotonic()
    print(f"Retrieved {len(image_data)} image data bytes in {t2 - t1:.3f} seconds.")
    with open("sds1204xe_screendump.bmp", "wb") as fo:
        fo.write(image_data)
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

        test_screendump(usbtmc_interface)

    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0xf4ec, 0xee38)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
