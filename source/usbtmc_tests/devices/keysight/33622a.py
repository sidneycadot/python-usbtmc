#! /usr/bin/env -S python3 -B

"""Communicate with the Keysight 33622A waveform generator."""

import contextlib
import time
from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc.utilities import (usbtmc_query, parse_definite_length_binary_block, initialize_libusb_library_path_environment_variable,
                              make_definite_length_binary_block)


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"The device identifies itself as: {response!r}.")
    print()


def test_screendump(usbtmc_interface: UsbTmcInterface) -> None:
    """Test screendump functionality.

    Note: requesting a screenshot in PNG format is very slow, taking ~ 2.1 seconds!
    """
    for image_format in ["BMP", "PNG"]:
        usbtmc_interface.write_message(f"HCOPY:SDUMP:DATA:FORMAT {image_format}")
        usbtmc_interface.write_message("HCOPY:SDUMP:DATA?")
        t1 = time.monotonic()
        response = usbtmc_interface.read_binary_message()
        t2 = time.monotonic()
        image_data = parse_definite_length_binary_block(response)
        print(f"{image_format}: {len(image_data)} bytes in {t2 - t1:.3f} seconds.")
        with open(f"33622a_screendump.{image_format.lower()}", "wb") as fo:
            fo.write(image_data)
    print()


def test_waveform_upload(usbtmc_interface: UsbTmcInterface) -> None:
    waveform_name = "awg_test"
    num_samples = 1000000
    data = bytes(4 * num_samples)
    usbtmc_interface.write_message("DATA:VOLATILE:CLEAR")
    usbtmc_interface.write_message("DATA:ARBITRARY2:FORMAT ABAB")
    t1 = time.monotonic()
    usbtmc_interface.write_message(f"DATA:ARBITRARY2:DAC {waveform_name},", make_definite_length_binary_block(data))
    t2 = time.monotonic()
    print(f"Waveform upload: {len(data)} bytes in {t2 - t1:.3f} seconds.")
    print()


def run_tests(vid: int, pid: int, serial: Optional[str] = None) -> None:
    """Run USBTMC tests."""

    initialize_libusb_library_path_environment_variable()

    # We override the min_bulk_speed to be able to request PNG screenshots, which is VERY slow.
    usbtmc_interface = UsbTmcInterface(vid=vid, pid=pid, serial=serial, min_bulk_speed=5.0)
    usbtmc_interface.open()
    with contextlib.closing(usbtmc_interface):

        device_info = usbtmc_interface.get_device_info()
        device_model = device_info.manufacturer + " " + device_info.product

        print()
        print(f"Running tests on device model: '{device_model}' ...")
        print()

        test_identification(usbtmc_interface)

        test_screendump(usbtmc_interface)

        test_waveform_upload(usbtmc_interface)

    print()
    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x0957, 0x5707)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
