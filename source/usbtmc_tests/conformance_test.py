#! /usr/bin/env python3

"""This is a conformance testing tool for devices that claim to support USBTMC."""

import os
import sys
import re
import argparse
from contextlib import closing
from enum import Enum

from usbtmc import UsbTmcInterface
from usbtmc.libusb_library import LibUsbLibraryFunctionCallError
from usbtmc.usbtmc_interface_behavior import UsbTmcInterfaceBehavior

languages = {
    0x1404: "Chinese (Macau SAR)",
    0x041a: "Croatian",
    0x0405: "Czech",
    0x0406: "Danish",
    0x0413: "Dutch (Netherlands)",
    0x0813: "Dutch (Belgium)",
    0x0409: "English (United States)",
    0x0809: "English (United Kingdom)",
    0x0c09: "English (Australian)",
    0x1009: "English (Canadian)",
    0x1409: "English (New Zealand)",
    0x1809: "English (Ireland)",
    0x1c09: "English (South Africa)",
    0x2009: "English (Jamaica)",
    0x2409: "English (Caribbean)",
    0x2809: "English (Belize)",
    0x2c09: "English (Trinidad)",
    0x3009: "English (Zimbabwe)",
    0x3409: "English (Philippines)",
    0x0425: "Estonian",
    0x0438: "Faeroese",
    0x0429: "Farsi",
    0x040b: "Finnish",
    0x040c: "French (Standard)",
    0x080c: "French (Belgian)",
    0x0c0c: "French (Canadian)",
    0x100c: "French (Switzerland)",
    0x140c: "French (Luxembourg)",
    0x180c: "French (Monaco)",
    0x0437: "Georgian",
    0x0407: "German (Standard)",
    0x0807: "German (Switzerland)",
    0x0c07: "German (Austria)",
    0x1007: "German (Luxembourg)",
    0x1407: "German (Liechtenstein)",
    0x0408: "Greek",
    0x0447: "Gujarati",
    0x040d: "Hebrew",
    0x0439: "Hindi",
    0x040e: "Hungarian",
    0x040f: "Icelandic",
    0x0421: "Indonesian",
    0x0410: "Italian (Standard)",
    0x0810: "Italian (Switzerland)",
    0x0411: "Japanese",
    0x044b: "Kannada",
    0x0860: "Kashmiri (India)",
    0x043f: "Kazakh",
    0x0457: "Konkani",
    0x0412: "Korean",
    0x0812: "Korean (Johab)",
    0x0426: "Latvian",
    0x0427: "Lithuanian",
    0x0827: "Lithuanian (Classic)",
    0x042f: "Macedonian",
    0x043e: "Malay (Malaysian)",
    0x083e: "Malay (Brunei Darussalam)",
    0x044c: "Malayalam",
    0x0458: "Manipuri",
    0x044e: "Marathi",
    0x0861: "Nepali (India)",
    0x0414: "Norwegian (Bokmal)",
    0x0814: "Norwegian (Nynorsk)",
    0x0448: "Oriya",
    0x0415: "Polish",
    0x0416: "Portuguese (Brazil)",
    0x0816: "Portuguese (Standard)",
    0x0446: "Punjabi.",
    0x0418: "Romanian",
    0x0419: "Russian",
    0x044f: "Sanskrit",
    0x0c1a: "Serbian (Cyrillic)",
    0x081a: "Serbian (Latin)",
    0x0459: "Sindhi",
    0x041b: "Slovak",
    0x0424: "Slovenian",
    0x040a: "Spanish (Traditional Sort)",
    0x080a: "Spanish (Mexican)",
    0x0c0a: "Spanish (Modern Sort)",
    0x100a: "Spanish (Guatemala)",
    0x140a: "Spanish (Costa Rica)",
    0x180a: "Spanish (Panama)",
    0x1c0a: "Spanish (Dominican Republic)",
    0x200a: "Spanish (Venezuela)",
    0x240a: "Spanish (Colombia)",
    0x280a: "Spanish (Peru)",
    0x2c0a: "Spanish (Argentina)",
    0x300a: "Spanish (Ecuador)",
    0x340a: "Spanish (Chile)",
    0x380a: "Spanish (Uruguay)",
    0x3c0a: "Spanish (Paraguay)",
    0x400a: "Spanish (Bolivia)",
    0x440a: "Spanish (El Salvador)",
    0x480a: "Spanish (Honduras)",
    0x4c0a: "Spanish (Nicaragua)",
    0x500a: "Spanish (Puerto Rico)",
    0x0430: "Sutu",
    0x0441: "Swahili (Kenya)",
    0x041d: "Swedish",
    0x081d: "Swedish (Finland)",
    0x0449: "Tamil",
    0x0444: "Tatar (Tatarstan)",
    0x044a: "Telugu",
    0x041e: "Thai",
    0x041f: "Turkish",
    0x0422: "Ukrainian",
    0x0420: "Urdu (Pakistan)",
    0x0820: "Urdu (India)",
    0x0443: "Uzbek (Latin)",
    0x0843: "Uzbek (Cyrillic)",
    0x042a: "Vietnamese",
    0x04ff: "HID (Usage Data Descriptor)",
    0xf0ff: "HID (Vendor Defined 1)",
    0xf4ff: "HID (Vendor Defined 2)",
    0xf8ff: "HID (Vendor Defined 3)",
    0xfcff: "HID (Vendor Defined 4)"
}


def initialize_libusb_library_path_environment_variable() -> bool:
    """Initialize the LIBUSB_LIBRARY_PATH environment variable, if needed.

    In Windows, we need to tell usbtmc where the libusb-1.0 DLL can be found. This is done by
    pointing the LIBUSB_LIBRARY_PATH environment variable to the libusb-1.0 DLL.

    If the LIBUSB_LIBRARY_PATH variable is already set, or on non-Windows platforms, this function is a no-op.
    """

    if ("LIBUSB_LIBRARY_PATH" in os.environ) or (sys.platform != "win32"):
        return False

    filename = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../windows/libusb-1.0.dll"))
    if not os.path.exists(filename):
        raise RuntimeError(f"Cannot find the libusb-1.0 library at '{filename}'. Please make sure it's available.")
    os.environ["LIBUSB_LIBRARY_PATH"] = filename
    return True


def conformance_test_indicator_pulse(usbtmc_interface: UsbTmcInterface, is_capability: bool) -> None:

    print()
    print("Conformity test: indicator pulse")
    print("================================")
    print()

    print("USBTMC devices may support INDICATOR PULSE requests. Such a request asks the device to")
    print("show a blinking light (or something similar), to help the user to identify the correct")
    print("device in a lab setting.")
    print()

    if is_capability:
        print("The device claims that it handles indicator pulse requests.")
    else:
        print("The device claims that it DOES NOT handle indicator pulse requests.")

    print()
    print("We will now check the actual behavior of the device when an indicator pulse request")
    print("is sent. To do this, you are prompted to press Enter. Each time you press enter,")
    print("an indicator request is sent. This loop stops when you type 'q', followed by enter.")
    print()

    class ObservedBehavior(Enum):
        REQUEST_REJECTED = 101
        REQUEST_ACCEPTED_INDICATOR_PRESENT = 102
        REQUEST_ACCEPTED_INDICATOR_NOT_PRESENT = 103

    input("Press enter to send the request ... ").lower()
    while True:
        print("Requesting indicator pulse ...")
        # The following line raises an exception if the device indicates it does not support the
        # request.
        try:
            usbtmc_interface.indicator_pulse()
        except Exception as exception:
            # Note: the Siglent raises a LibUsbFunctionCallError: LIBUSB_ERROR_PIPE here.
            print("The device refused the request:", exception)
            behavior = ObservedBehavior.REQUEST_REJECTED  # Request was rejected.
            break

        print("The device acknowledged request.")

        user_input = input("Type 'y' if you see the indicator, 'n' if you don't see it, or just Enter to retry.").lower()
        if user_input in ("y", "yes"):
            behavior = ObservedBehavior.REQUEST_ACCEPTED_INDICATOR_PRESENT
            break

        if user_input in ("n", "no"):
            behavior = ObservedBehavior.REQUEST_ACCEPTED_INDICATOR_NOT_PRESENT
            break

    match (is_capability, behavior):
        case (True, ObservedBehavior.REQUEST_REJECTED):
            print("NON-CONFORMANT BEHAVIOR: device claims it can do it, but rejects the request. The request should be accepted.")
        case (True, ObservedBehavior.REQUEST_ACCEPTED_INDICATOR_PRESENT):
            print("CONFORMANT BEHAVIOR: device claims it can do it, accepted the request, and an indicator pulse is seen.")
        case (True, ObservedBehavior.REQUEST_ACCEPTED_INDICATOR_NOT_PRESENT):
            print("NON-CONFORMANT BEHAVIOR: device claims it can do it, accepted the pulse, but no pulse seen. The device should shown a visible pulse indicator.")
        case (False, ObservedBehavior.REQUEST_REJECTED):
            print("CONFORMANT BEHAVIOR: device claims it cannot do it and rejected the request.")
        case (False, ObservedBehavior.REQUEST_ACCEPTED_INDICATOR_PRESENT):
            print("NON-CONFORMANT BEHAVIOR: device claims it cannot do it but accepted the request and shows an indicator. The capability should be 'indicator pulse supported'.")
        case (False, ObservedBehavior.REQUEST_ACCEPTED_INDICATOR_NOT_PRESENT):
            print("NON-CONFORMANT BEHAVIOR: device claims it cannot do it but then accepted the request, showing no indicator. The request should have been rejected.")


def conformance_test_scpi(usbtmc_interface: UsbTmcInterface) -> None:

    print()
    print("Conformity test: SCPI")
    print("=====================")
    print()

    usbtmc_interface.write_message("*IDN?\n")
    response = usbtmc_interface.read_message()

    print(f"Response: {response!r}")


def yesno(flag: bool) -> str:
    return "yes" if flag else "no"


def test_device(vid: int, pid: int) -> None:

    #behavior = None
    behavior = UsbTmcInterfaceBehavior(
        open_reset_method=0
    )

    usbtmc_interface = UsbTmcInterface(vid=vid, pid=pid, behavior=behavior)
    usbtmc_interface.open()
    with closing(usbtmc_interface):

        print()
        print(f"Device info for USBTMC device {vid:04x}:{pid:04x}")
        print("=======================================")
        print()

        device_info = usbtmc_interface.get_device_info()

        print(f"Manufacturer ....... : {device_info.manufacturer!r}")
        print(f"Product ............ : {device_info.product!r}")
        print(f"Serial Number ...... : {device_info.serial_number!r}")

        print()
        print("Interface info")
        print("--------------")
        print()

        usbtmc_interface_info = usbtmc_interface.get_usbtmc_interface_info()

        match usbtmc_interface_info.interface_protocol:
            case 0:
                interface_protocol_name = "USBTMC basic"
            case 1:
                interface_protocol_name = "USBTMC + USB488"
            case _:
                interface_protocol_name = "unknown"

        print(f"usbtmc interface number  ...................... : {usbtmc_interface_info.interface_number}")
        print(f"usbtmc interface protocol  .................... : {usbtmc_interface_info.interface_protocol} ({interface_protocol_name})")
        print(f"usbtmc bulk-in endpoint ....................... : 0x{usbtmc_interface_info.bulk_in_endpoint:02x} ; maximum packet size = {usbtmc_interface_info.bulk_in_endpoint_max_packet_size}")
        print(f"usbtmc bulk-out endpoint ...................... : 0x{usbtmc_interface_info.bulk_out_endpoint:02x} ; maximum packet size = {usbtmc_interface_info.bulk_out_endpoint_max_packet_size}")

        print()
        print("Supported languages")
        print("-------------------")
        print()

        supported_languages = usbtmc_interface.get_string_descriptor_languages()

        for langid in supported_languages:
            if langid in languages:
                language_name = languages[langid]
            else:
                language_name = f"Unknown language: 0x{langid:04x}"
            print(f"0x{langid:04x}: {language_name}")

        print()
        print("String descriptors")
        print("------------------")
        print()

        for langid in supported_languages:
            if langid in languages:
                language_name = languages[langid]
            else:
                language_name = "Unknown language"

            print(f"String descriptors defined for langid 0x{langid:04x}: {language_name}")

            for descriptor_index in range(1, 256):
                try:
                    descriptor_string = usbtmc_interface.get_string_descriptor(descriptor_index)
                except LibUsbLibraryFunctionCallError:
                    descriptor_string = None

                if descriptor_string is not None:
                    print(f"    {descriptor_index:3d} {descriptor_string!r}")

        print()
        print("Interface capabilities")
        print("----------------------")
        print()

        capabilities = usbtmc_interface.get_capabilities()

        print(f"usbtmc interface version ................................... : {capabilities.usbtmc_interface_version[0]}.{capabilities.usbtmc_interface_version[1]}")
        print(f"usbtmc interface supports indicator pulse .................. : {yesno(capabilities.usbtmc_interface_supports_indicator_pulse)}")
        print(f"usbtmc interface is talk-only .............................. : {yesno(capabilities.usbtmc_interface_is_talk_only)}")
        print(f"usbtmc interface is listen-only ............................ : {yesno(capabilities.usbtmc_interface_is_listen_only)}")
        print(f"usbtmc interface supports termchar feature ................. : {yesno(capabilities.usbtmc_interface_supports_termchar_feature)}")
        print()
        print(f"usb488 interface version ................................... : {capabilities.usb488_interface_version[0]}.{capabilities.usb488_interface_version[1]}")
        print(f"usb488 interface is USB488.2 ............................... : {yesno(capabilities.usb488_interface_is_488v2)}")
        print(f"usb488 interface accepts remote/local commands ............. : {yesno(capabilities.usb488_interface_accepts_remote_local_commands)}")
        print(f"usb488 interface accepts trigger command ................... : {yesno(capabilities.usb488_interface_accepts_trigger_command)}")
        print(f"usb488 interface supports all mandatory SCPI commands ...... : {yesno(capabilities.usb488_interface_supports_all_mandatory_scpi_commands)}")
        print(f"usb488 interface is SR1 capable ............................ : {yesno(capabilities.usb488_interface_device_is_sr1_capable)}")
        print(f"usb488 interface is RL1 capable ............................ : {yesno(capabilities.usb488_interface_device_is_rl1_capable)}")
        print(f"usb488 interface is DT1 capable ............................ : {yesno(capabilities.usb488_interface_device_is_dt1_capable)}")

        conformance_test_indicator_pulse(usbtmc_interface, capabilities.usbtmc_interface_supports_indicator_pulse)

        conformance_test_scpi(usbtmc_interface)


def main():

    device_vid_pid_pattern = re.compile("([0-9a-fA-F]{4}):([0-9a-fA-F]{4})")

    parser = argparse.ArgumentParser()
    parser.add_argument("devices", nargs="+")

    args = parser.parse_args()

    initialize_libusb_library_path_environment_variable()

    for device in args.devices:

        match = device_vid_pid_pattern.match(device)
        if match is None:
            print(f"Skipping bad device: {device!r}.")
            continue

        vid = int(match.group(1), 16)
        pid = int(match.group(2), 16)

        test_device(vid, pid)

        break  # TODO: Remove. With this break present, we only test the first device.


if __name__ == "__main__":
    main()
