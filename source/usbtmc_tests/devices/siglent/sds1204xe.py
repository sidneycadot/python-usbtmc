#! /usr/bin/env -S python3 -B

"""Communicate with the Siglent SDS1204X-E oscilloscope."""

import contextlib
import time
import struct
from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc.utilities import initialize_libusb_library_path_environment_variable, usbtmc_query


def fix_screenshot_data(image_data: bytes) -> bytes:
    """Fix screenshot image as returned by the DISPLAY:DATA? command."""

    expected_image_data_size = 1 + 14 + 40 + 272 * 480 * 3

    if len(image_data) != expected_image_data_size:
        raise ValueError("Bad image data.")

    # Turn data into a bytearray, discarding the first stray byte, the value of which is non-deterministic.
    image_data = bytearray(image_data[1:])

    # An (almost) BMP format image remains. Fix it.

    # Fix file length (the BMP header is not included in the value of the length field, so its value is too low by 14 bytes).
    struct.pack_into("<L", image_data, 2, len(image_data))

    # Mirror image horizontally and rearrange pixel color ordering: (B/R/G) -> (B/G/R).
    for y in range(272):
        for x in range(240):
            offset1 = 54 + 3 * (y * 480 + x)
            offset2 = 54 + 3 * (y * 480 + (479 - x))

            (b1, r1, g1) = struct.unpack_from("BBB", image_data, offset1)
            (b2, r2, g2) = struct.unpack_from("BBB", image_data, offset2)

            struct.pack_into("BBB", image_data, offset1, b2, g2, r2)
            struct.pack_into("BBB", image_data, offset2, b1, g1, r1)

    # We now have a valid BMP file.
    return bytes(image_data)


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
    (vid, pid) = (0xf4ec, 0xee38)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
