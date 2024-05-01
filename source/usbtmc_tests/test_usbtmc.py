#! /usr/bin/env -S python3 -B

""""A basic test program for python-usbtmc."""

import contextlib
from io import BytesIO
import os
import sys
import time
from typing import Optional

from usbtmc import UsbTmcInterface, UsbTmcError
from usbtmc.libusb_library import LibUsbError


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


def usbtmc_query(usbtmc_interface: UsbTmcInterface, command: str) -> str:
    usbtmc_interface.write_message(command)
    return usbtmc_interface.read_message()


def test_identification(usbtmc_interface: UsbTmcInterface) -> None:
    print("** Test identification request (Bulk: *IDN?).")
    print("   Sending request ...")
    response = usbtmc_query(usbtmc_interface, "*IDN?")
    print(f"   Received response: {response}")


def test_capabilities(usbtmc_interface: UsbTmcInterface) -> None:
    print("** Test capabilities request (Control)")
    print("   Sending request ...")
    capabilities = usbtmc_interface.get_capabilities()
    print(f"   Received response: {capabilities}")


def test_indicator_pulse(usbtmc_interface: UsbTmcInterface) -> None:
    print("** Test indicator pulse (Control)")
    print("   Sending request ...")
    usbtmc_interface.indicator_pulse()
    print("   Done.")


def test_trigger(usbtmc_interface: UsbTmcInterface) -> None:
    print("** Test trigger (Bulk-Out)")
    print("   Sending request ...")
    usbtmc_interface.trigger()
    print("   Done.")


def test_max_message_length(usbtmc_interface: UsbTmcInterface, max_request_size: int) -> None:
    print("** Test max message length (Bulk)")
    num_spaces = 0
    best = None
    print(f"   Running test up to {max_request_size} characters ...")
    while True:
        # Make a long input message with two commands, separated by spaces.
        request = "*STB?;" + (" " * num_spaces) + "*STB?"
        if len(request) > max_request_size:
            break
        response = usbtmc_query(usbtmc_interface, request)
        num_parts = len(response.split(";"))
        if num_parts != 2:
            break
        best = len(request)
        num_spaces += 1
    print(f"   Done. Longest total message size that works: {best}.")


def test_multiple_queries(usbtmc_interface: UsbTmcInterface, max_query_count: int) -> None:
    print("** Test multiple queries in a single message (Bulk)")
    query_count = 1
    best = None
    print(f"   Running test up to {max_query_count} queries ...")
    while True:
        if query_count > max_query_count:
            break
        # Make a long input message with 'count'' commands, separated by semicolons.
        request = ";".join("*STB?" for i in range (query_count))
        try:
            response = usbtmc_query(usbtmc_interface, request)
        except LibUsbError:
            break
        num_parts = len(response.split(";"))
        if num_parts != query_count:
            break
        best = query_count
        query_count += 1
    print(f"   Done. Longest total query count that works: {best}.")


def test_status_behavior(usbtmc_interface: UsbTmcInterface) -> None:

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
        usbtmc_interface.write_message(query)
        response = usbtmc_interface.read_message()
        print(f"query: {query:20} response: {response:20}")

    for query in register_list:
        usbtmc_interface.write_message(query)
        response = usbtmc_interface.read_message()
        print(f"query: {query:20} response: {response:20}")

    usbtmc_interface.write_message("DATA:VOLATILE:CLEAR")
    usbtmc_interface.write_message("DATA:ARBITRARY2:FORMAT ABAB")
    usbtmc_interface.write_message("DATA:ARBITRARY2:FORMAT ABAB")
    usbtmc_interface.write_message("DATA:ARBITRARY2:DAC awg_test,", make_definite_length_binary_block(data))

    for i in range(20):
        stb = usbtmc_interface.read_status_byte()
        print("stb:", stb)
        time.sleep(0.200)

    # usbtmc_device.write_message("*STB?")
    # response = usbtmc_device.read_message()
    # print("STB response:", response)

    # usbtmc_device.write_message("*OPC?")
    # response = usbtmc_device.read_message()
    # print("response:", response)

    usbtmc_interface.write_message("*ESE 255; *SRE 191; *OPC")


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

    usbtmc_interface = UsbTmcInterface(vid=vid, pid=pid, serial=serial)
    usbtmc_interface.open()
    with contextlib.closing(usbtmc_interface):

        device_info = usbtmc_interface.get_device_info()
        device_model = device_info.manufacturer + " " + device_info.product

        print()
        print(f"Running tests on device model: '{device_model}' ...")
        print()

        # Define which tests to run.
        do_test_identification_start = True
        do_test_capabilities = True
        do_test_indicator_pulse = True
        do_test_trigger = True
        #
        do_test_max_message_length = True
        do_test_multiple_queries = True
        #
        do_test_screendump = False
        write_screendump = False
        #
        do_test_waveform_upload = False
        #
        do_test_identification_end = True
        #

        if do_test_identification_start:
            test_identification(usbtmc_interface)

        if do_test_capabilities:
            test_capabilities(usbtmc_interface)

        if do_test_indicator_pulse:
            test_indicator_pulse(usbtmc_interface)

        if do_test_trigger:
            test_trigger(usbtmc_interface)

        if do_test_max_message_length:
            test_max_message_length(usbtmc_interface, 100)

        if do_test_multiple_queries:
            test_multiple_queries(usbtmc_interface, 100)

        if do_test_screendump:
            if device_model in ("Keysight Technologies 33622A", "Keysight Technologies 52230A"):
                screendump_format = "bmp"
                usbtmc_interface.write_message("HCOPY:SDUMP:DATA:FORMAT {}".format(screendump_format.upper()))
                usbtmc_interface.write_message("HCOPY:SDUMP:DATA?")
                response = usbtmc_interface.read_binary_message()
                image = parse_definite_length_binary_block(response)
                if write_screendump:
                    with open("screendump.{}".format(screendump_format.lower()), "wb") as fo:
                        fo.write(image)
            # elif device_model == "Siglent SDS1204X-E":
            #    usbtmc_interface.write_message("SCDP")
            #    response = usbtmc_interface.read_binary_message()

        if do_test_waveform_upload:
            if device_model == "Keysight Technologies 33622A":
                num_samples = 100000
                data = bytes(4 * num_samples)
                usbtmc_interface.write_message("DATA:VOLATILE:CLEAR")
                usbtmc_interface.write_message("DATA:ARBITRARY2:FORMAT ABAB")
                usbtmc_interface.write_message("DATA:ARBITRARY2:DAC awg_test,", make_definite_length_binary_block(data))

        if do_test_identification_end:
            test_identification(usbtmc_interface)

    print()
    print("All done.")


def main():
    """Select device and run tests."""
    (vid, pid) = (0x0957, 0x5707)  # Keysight 33622A
    # (vid, pid) = (0x0957, 0x1907)  # Keysight 55230A
    # (vid, pid) = (0xf4ec, 0xee38)    # Siglent SDS 1204X-E
    # (vid, pid) = (0x1313, 0x8078)  # Thorlabs PM100D

    try:
        run_tests(vid, pid)
    except (LibUsbError, UsbTmcError) as exception:
        print("An exception occurred while executing tests:", exception)
        raise


if __name__ == "__main__":
    main()
