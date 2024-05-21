#! /usr/bin/env -S python3 -B

"""A basic test program for python-usbtmc."""

import contextlib
import time
from typing import Optional

from usbtmc import UsbTmcInterface
from usbtmc.libusb_library import LibUsbLibraryError
from usbtmc.utilities import usbtmc_query, initialize_libusb_library_path_environment_variable, parse_definite_length_binary_block, \
    make_definite_length_binary_block


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
    print(f"   Done. Longest total message size that works as expected: {best}.")


def test_multiple_queries(usbtmc_interface: UsbTmcInterface, max_query_count: int) -> None:
    print("** Test multiple queries in a single message (Bulk)")
    query_count = 1
    best = None
    print(f"   Running test up to {max_query_count} queries ...")
    while True:
        if query_count > max_query_count:
            break
        # Make a long input message with 'count' commands, separated by semicolons.
        request = ";".join(["*STB?"] * query_count)
        try:
            response = usbtmc_query(usbtmc_interface, request)
        except LibUsbLibraryError:
            break
        num_parts = len(response.split(";"))
        if num_parts != query_count:
            break
        best = query_count
        query_count += 1
    print(f"   Done. Longest total query count that works as expected: {best}.")


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

    initialize_libusb_library_path_environment_variable()

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
    # (vid, pid) = (0xf4ec, 0xee38)  # Siglent SDS 1204X-E
    # (vid, pid) = (0x1313, 0x8078)  # Thorlabs PM100D

    run_tests(vid, pid)


if __name__ == "__main__":
    main()
