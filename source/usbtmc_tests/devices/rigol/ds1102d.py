#! /usr/bin/env -S python3 -B

"""Communicate with the Rigol DS1102D oscilloscope using USBTMC."""

from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc.utilities import usbtmc_query, initialize_libusb_library_path_environment_variable


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    """Test device identification."""
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"The device identifies itself as: {response!r}.")
    print()


def run_tests(vid: int, pid: int, serial: Optional[str] = None) -> None:
    """Run USBTMC tests."""

    initialize_libusb_library_path_environment_variable()

    with UsbTmcInterface(vid=vid, pid=pid, serial=serial) as usbtmc_interface:

        device_info = usbtmc_interface.get_device_info()
        device_model = device_info.manufacturer + " " + device_info.product

        print()
        print(f"Running tests on device model: '{device_model}' ...")
        print()

        test_identification(usbtmc_interface)

    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x1ab1, 0x0588)
    run_tests(vid, pid)


if __name__ == "__main__":
    main()
