#! /usr/bin/env -S python3 -B

"""Communicate with the Rigol DHO 924S oscilloscope using USBTMC."""

import contextlib
import time
from typing import Optional

from usbtmc import UsbTmcInterface


def usbtmc_query(usbtmc_interface: UsbTmcInterface, command: str) -> str:
    usbtmc_interface.write_message(command)
    return usbtmc_interface.read_message()


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    print("** Test identification request (Bulk: *IDN?).")
    print("   Sending request ...")
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"   Received response: {response}")


def test_screendump(usbtmc_interface: UsbTmcInterface) -> None:
    for i in range(10):
        for image_format in ["PNG", "BMP", "JPG"]:
            usbtmc_interface.write_message(f"DISPLAY:DATA? {image_format}")
            t1 = time.monotonic()
            response = usbtmc_interface.read_binary_message()
            t2 = time.monotonic()
            image_data = parse_definite_length_binary_block(response)
            print(f"{image_format}: {len(image_data)} bytes in {t2 -  t1:.3f} seconds.")
            #with open("screendump.bmp", "wb") as fo:
            #    fo.write(image_data)


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

    print()
    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x1ab1, 0x044c)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
