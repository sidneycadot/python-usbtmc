"""This module provides the UsbTmcInterface class."""

import os
import struct
from typing import NamedTuple, Optional
import ctypes.util

from .better_int_enum import BetterIntEnum
from .libusb_library import LibUsbLibrary, LibUsbDeviceHandlePtr, LANGID_ENGLISH_US
from .usbtmc_interface_behavior import get_usbtmc_interface_behavior, UsbTmcInterfaceBehavior, ResetAtOpenPolicyFlag

BULK_TRANSFER_HEADER_SIZE = 12  # All Bulk-In and Bulk-Out transfers have a 12-byte header describing the transfer.


class ControlRequest(BetterIntEnum):
    """Control-out endpoint requests of the USBTMC protocol and the USB488 sub-protocol."""
    # Values defined for the USBTMC protocol:
    USBTMC_INITIATE_ABORT_BULK_OUT     = 1
    USBTMC_CHECK_ABORT_BULK_OUT_STATUS = 2
    USBTMC_INITIATE_ABORT_BULK_IN      = 3
    USBTMC_CHECK_ABORT_BULK_IN_STATUS  = 4
    USBTMC_INITIATE_CLEAR              = 5
    USBTMC_CHECK_CLEAR_STATUS          = 6
    USBTMC_GET_CAPABILITIES            = 7
    USBTMC_INDICATOR_PULSE             = 64
    # Values defined for the USB488 sub-protocol:
    USB488_READ_STATUS_BYTE            = 128
    USB488_REN_CONTROL                 = 160
    USB488_GO_TO_LOCAL                 = 161
    USB488_LOCAL_LOCKOUT               = 162


class ControlStatus(BetterIntEnum):
    """Control-in endpoint status of the USBTMC protocol and the USB488 sub-protocol."""
    # Values defined for the USBTMC protocol:
    USBTMC_SUCCESS                  = 0x01
    USBTMC_PENDING                  = 0x02
    USBTMC_FAILED                   = 0x80
    USBTMC_TRANSFER_NOT_IN_PROGRESS = 0x81
    USBTMC_SPLIT_NOT_IN_PROGRESS    = 0x82
    USBTMC_SPLIT_IN_PROGRESS        = 0x83
    # Values defined for the USB488 sub-protocol:
    USB488_INTERRUPT_IN_BUSY        = 0x20


class BulkMessageID(BetterIntEnum):
    """Bulk-in and bulk-out endpoint message IDs of the USBTMC protocol and the USB488 sub-protocol."""
    # Values defined for the USBTMC protocol:
    USBTMC_DEV_DEP_MSG_OUT            = 1
    USBTMC_REQUEST_DEV_DEP_MSG_IN     = 2
    USBTMC_DEV_DEP_MSG_IN             = 2
    USBTMC_VENDOR_SPECIFIC_OUT        = 126
    USBTMC_REQUEST_VENDOR_SPECIFIC_IN = 127
    USBTMC_VENDOR_SPECIFIC_IN         = 127
    # Values defined for the USB488 sub-protocol:
    USB488_TRIGGER                    = 128


class UsbDeviceInfo(NamedTuple):
    """USB device info as human-readable strings."""
    vid_pid: str                  # vid:pid in xxxx:yyyy format, with xxxx and yyyy being four-digit hexadecimal values.
    manufacturer: str             # Manufacturer name, as read from the device descriptor.
    product: str                  # Product name, as read from the device descriptor.
    serial_number: Optional[str]  # Serial number, as read from the device descriptor. May be absent.


class UsbTmcInterfaceInfo(NamedTuple):
    """USBTMC interface info."""
    configuration_number: int
    interface_number: int
    interface_protocol: int  # 0: USBTMC, 1: USB488.
    bulk_in_endpoint: int
    bulk_in_endpoint_max_packet_size: int
    bulk_out_endpoint: int
    bulk_out_endpoint_max_packet_size: int


class UsbTmcInterfaceCapabilities(NamedTuple):
    """USBTMC capabilities as read from the USBTMC interface."""
    # Version number and capabilities defined for the generic USBTMC protocol:
    usbtmc_interface_version: tuple[int, int]
    usbtmc_interface_supports_indicator_pulse: bool
    usbtmc_interface_is_talk_only: bool
    usbtmc_interface_is_listen_only: bool
    usbtmc_interface_supports_termchar_feature: bool
    # Version number and capabilities defined for the USB488 sub-protocol:
    usb488_interface_version: tuple[int, int]
    usb488_interface_is_488v2: bool
    usb488_interface_accepts_remote_local_commands: bool
    usb488_interface_accepts_trigger_command: bool
    usb488_interface_supports_all_mandatory_scpi_commands: bool
    usb488_interface_device_is_sr1_capable: bool
    usb488_interface_device_is_rl1_capable: bool
    usb488_interface_device_is_dt1_capable: bool


class UsbTmcError(Exception):
    """Base class for all errors that are caught at the UsbTmcInterface level."""


class UsbTmcGenericError(UsbTmcError):
    """A generic error occurred at the UsbTmcInterface level."""
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"UsbTmcGenericError(message={self.message!r})"


class UsbTmcControlResponseError(UsbTmcError):
    """An error occurred awhile doing a control transfer."""
    def __init__(self, request: ControlRequest, status: ControlStatus):
        self.request = request
        self.status = status

    def __str__(self):
        return f"UsbTmcControlResponseError(request={self.request}, status={self.status})"


class LibUsbLibraryManager:
    """This class manages a LibUsbLibrary instance and a LibUsbContextPtr obtained from it.

    An instance is shared by all UsbTmcInterface instances to gain access to libusb functionality.
    """
    def __init__(self):
        self._libusb = None
        self._ctx = None

    def __del__(self):
        if self._ctx is not None:
            # Discard libusb context.
            self.get_libusb().exit(self._ctx)
        if self._libusb is not None:
            # The ctypes module provides no way to unload a library.
            pass

    def get_libusb(self):
        """Get the libusb library instance; instantiate it if necessary."""
        if self._libusb is None:
            # Dynamically load the libusb library.
            if "LIBUSB_LIBRARY_PATH" in os.environ:
                filename = os.environ["LIBUSB_LIBRARY_PATH"]
            else:
                # This returns None if the library is not found.
                filename = ctypes.util.find_library("usb-1.0")
            if filename is None:
                raise UsbTmcGenericError("Don't know where to find libusb. Set the LIBUSB_LIBRARY_PATH environment variable.")
            self._libusb = LibUsbLibrary(filename)
        return self._libusb

    def get_libusb_context(self):
        """Get the libusb context instance; initialize one if necessary."""
        if self._ctx is None:
            # Initialize a libusb context.
            self._ctx = self.get_libusb().init()
        return self._ctx


def _find_usbtmc_interface(libusb: LibUsbLibrary, device_handle: LibUsbDeviceHandlePtr) -> Optional[UsbTmcInterfaceInfo]:
    """Find the USBTMC interface of a given USB device."""

    device = libusb.get_device(device_handle)
    device_descriptor = libusb.get_device_descriptor(device)

    if device_descriptor.bNumConfigurations != 1:
        # Unable to deal with devices that have multiple configurations, yet.
        raise UsbTmcGenericError("Unable to handle devices with multiple configurations.")

    for config_index in range(device_descriptor.bNumConfigurations):
        config_descriptor = libusb.get_config_descriptor(device, config_index)
        try:
            for interface_index in range(config_descriptor.contents.bNumInterfaces):
                interface = config_descriptor.contents.interface[interface_index]

                if interface.num_altsetting != 1:
                    # Unable to deal with interfaces that have multiple alt-settings, yet.
                    raise UsbTmcGenericError("Unable to handle interfaces with multiple alt settings.")

                for altsetting_index in range(interface.num_altsetting):
                    altsetting = interface.altsetting[altsetting_index]

                    found_usbtmc_interface = ((altsetting.bInterfaceClass == 0xfe) and
                                              (altsetting.bInterfaceSubClass == 0x03))
                    if not found_usbtmc_interface:
                        continue

                    bulk_in_endpoint = None
                    bulk_out_endpoint = None
                    bulk_in_endpoint_max_packet_size = None
                    bulk_out_endpoint_max_packet_size = None

                    for endpoint_index in range(altsetting.bNumEndpoints):

                        endpoint = altsetting.endpoint[endpoint_index]

                        endpoint_address = endpoint.bEndpointAddress
                        endpoint_direction = (endpoint.bEndpointAddress & 0x80)
                        endpoint_type = endpoint.bmAttributes & 0x0f
                        endpoint_max_packet_size = endpoint.wMaxPacketSize

                        match (endpoint_type, endpoint_direction):
                            case (0x02, 0x80):  # BULK-IN endpoint
                                bulk_in_endpoint = endpoint_address
                                bulk_in_endpoint_max_packet_size = endpoint_max_packet_size
                            case (0x02, 0x00):  # BULK-OUT endpoint
                                bulk_out_endpoint = endpoint_address
                                bulk_out_endpoint_max_packet_size = endpoint_max_packet_size

                    ok = (bulk_in_endpoint is not None) 
                    if not ok:
                        continue

                    return UsbTmcInterfaceInfo(
                        config_descriptor.contents.bConfigurationValue,
                        altsetting.bInterfaceNumber,
                        altsetting.bInterfaceProtocol,
                        bulk_in_endpoint, bulk_in_endpoint_max_packet_size,
                        bulk_out_endpoint, bulk_out_endpoint_max_packet_size
                    )
        finally:
            libusb.free_config_descriptor(config_descriptor)

    return None  # No USBTMC interface was found.


def _from_bcd(octet: int) -> int:
    # Interpret an octet as a BCD number (range 0.. 99).
    hi = octet // 16
    lo = octet % 16
    ok = (0 <= hi <= 9) and (0 <= lo <= 9)
    if not ok:
        raise ValueError(f"Bad BCD octet value: 0x{octet:04x}")

    return hi * 10 + lo


class UsbTmcInterface:
    """This class represents the USBTMC interface of a specific USB device."""

    # All UsbTmcInterface instances will use the same managed instance of libusb and a libusb context.
    _usbtmc_libusb_manager = LibUsbLibraryManager()

    def __init__(self, *, vid: int, pid: int, serial: Optional[str] = None,
                 behavior: Optional[UsbTmcInterfaceBehavior] = None,
                 short_timeout: float = 500.0,
                 min_bulk_speed: float = 500.0):

        self._vid = vid
        self._pid = pid
        self._serial = serial
        self._short_timeout = round(short_timeout)  # Short timeout, in [ms]. Used for control transfers and short bulk transfers.
        self._min_bulk_speed = min_bulk_speed       # Minimum bulk speed, in [bytes/ms] or, equivalently, [kB/s].

        self._behavior = get_usbtmc_interface_behavior(vid, pid) if behavior is None else behavior

        self._libusb = None
        self._device_handle = None
        self._usbtmc_info = None
        self._bulk_out_btag: Optional[int] = None
        self._rsb_btag: Optional[int] = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _exception_type, _exception_value, _exception_traceback):
        self.close()

    def open(self) -> None:
        """Find and open the device.

        Once opened, claim the interface, then clear the interface I/O (unless False is passed to clear_interface).
        """

        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        ctx = UsbTmcInterface._usbtmc_libusb_manager.get_libusb_context()

        device_handle = libusb.find_and_open_device(ctx, self._vid, self._pid, self._serial, self._short_timeout, LANGID_ENGLISH_US)
        if device_handle is None:
            raise UsbTmcGenericError(f"Device {self._vid:04x}:{self._pid:04x} not found."
                                     " Make sure the device is connected and user permissions allow I/O access to the device.")

        # We found the device and opened it. See if it provides a USBTMC interface.
        # If not, we close the device handle and raise an exception.

        usbtmc_info = _find_usbtmc_interface(libusb, device_handle)
        if usbtmc_info is None:
            libusb.close(device_handle)
            raise UsbTmcGenericError("The device doesn't have a USBTMC interface.")

        # Let libusb take care of attaching/detaching the kernel driver.
        libusb.set_auto_detach_kernel_driver(device_handle, True)

        #if libusb.kernel_driver_active(device_handle, usbtmc_info.interface_number):
        #    libusb.detach_kernel_driver(device_handle, usbtmc_info.interface_number)

        # Declare the device open, but prepare to close it when a subsequent initialization operation fails.

        self._libusb = libusb
        self._device_handle = device_handle
        self._usbtmc_info = usbtmc_info
        self._bulk_out_btag = 0  # Will be incremented to 1 at first invocation _get_next_bulk_out_btag.
        self._rsb_btag = 1  # Will be incremented to 2 at first invocation of _get_next_rsb_btag.

        try:
            # We reset the interface using the method specified by the device behavior's reset-at-open policy.

            if ResetAtOpenPolicyFlag.SET_CONFIGURATION in self._behavior.reset_at_open_policy:
                libusb.set_configuration(device_handle, usbtmc_info.configuration_number)

            # Claim the interface. This needs to happen *after* the set-configuration operation.
            self._claim_interface()

            if ResetAtOpenPolicyFlag.CLEAR_INTERFACE in self._behavior.reset_at_open_policy:
                self.clear_usbtmc_interface()

            if ResetAtOpenPolicyFlag.GOTO_REMOTE in self._behavior.reset_at_open_policy:
                self.remote_enable_control(True)

        except Exception:
            # If any exception happened during the first uses of the newly opened device,
            # we immediately close the device and re-raise the exception.
            self.close()
            raise

    def close(self) -> None:
        """Close the device."""

        # Let the operating system know we're done with it.
        self._release_interface()

        # Close the device handle.
        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        libusb.close(self._device_handle)

        # Set all device-specific fields to None. They will need to be re-initialized when the device is reopened.
        self._libusb = None
        self._device_handle = None
        self._usbtmc_info = None
        self._bulk_out_btag = None
        self._rsb_btag = None

    def _control_transfer(self, request: ControlRequest, w_value: int, w_length: int) -> bytes:
        """Perform a control transfer to the USBTMC interface."""

        if self._libusb is None:
            raise UsbTmcGenericError("The interface is not open.")

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            request,                             # bRequest
            w_value,                             # wValue
            self._usbtmc_info.interface_number,  # wIndex
            w_length,                            # wLength: the expected number of response bytes.
            self._short_timeout
        )

        return response

    def _get_next_bulk_out_btag(self) -> int:
        """Get next bTag value that identifies a BULK-OUT transfer.

        A transfer identifier. The Host must set bTag different from the bTag used in the previous Bulk-OUT Header.
        The Host should increment the bTag by 1 each time it sends a new Bulk-OUT Header.
        The Host must set bTag such that 1 <= bTag <= 255.
        """

        if self._bulk_out_btag is None:
            raise UsbTmcGenericError("The interface is not open.")

        self._bulk_out_btag = self._bulk_out_btag % 255 + 1
        return self._bulk_out_btag

    def _get_next_rsb_btag(self) -> int:
        """Get next bTag value that identifies a READ_STATUS_BYTE control transfer.

        The bTag value (2 <= bTag <= 127) for this request.
        The device must return this bTag value along with the Status Byte.
        The Host should increment the bTag by 1 for each new READ_STATUS_BYTE request to help identify when the
        response arrives at the Interrupt-IN endpoint.
        """

        if self._rsb_btag is None:
            raise UsbTmcGenericError("The interface is not open.")

        self._rsb_btag = (self._rsb_btag - 1) % 126 + 2
        return self._rsb_btag

    def _claim_interface(self) -> None:
        """Let the operating system know that we want to have exclusive access to the interface."""

        if self._libusb is None:
            raise UsbTmcGenericError("The interface is not open.")

        self._libusb.claim_interface(self._device_handle, self._usbtmc_info.interface_number)

    def _release_interface(self) -> None:
        """Let the operating system know that we want to drop exclusive access to the interface."""

        if self._libusb is None:
            raise UsbTmcGenericError("The interface is not open.")

        self._libusb.release_interface(self._device_handle, self._usbtmc_info.interface_number)

    def _calculate_bulk_timeout(self, num_octets: int) -> int:
        """Return a pessimistic estimate for the time a bulk transfer can take, in milliseconds."""
        return self._short_timeout + round(num_octets / self._min_bulk_speed)

    def _bulk_transfer_in(self, max_size: int) -> bytes:
        """Perform a single BULK-IN transfer."""

        if self._libusb is None:
            raise UsbTmcGenericError("The interface is not open.")

        timeout = self._calculate_bulk_timeout(max_size)
        return self._libusb.bulk_transfer_in(self._device_handle, self._usbtmc_info.bulk_in_endpoint, max_size, timeout)

    def _bulk_transfer_out(self, transfer: bytes) -> None:
        """Perform a single BULK-OUT transfer."""

        if self._libusb is None:
            raise UsbTmcGenericError("The interface is not open.")

        timeout = self._calculate_bulk_timeout(len(transfer))
        self._libusb.bulk_transfer_out(self._device_handle, self._usbtmc_info.bulk_out_endpoint, transfer, timeout)

    def get_string_descriptor_languages(self) -> list[int]:
        """Get supported string descriptor languages."""

        if self._device_handle is None:
            raise UsbTmcGenericError("The interface is not open.")

        return self._libusb.get_string_descriptor_languages(self._device_handle, self._short_timeout)

    def get_string_descriptor(self, descriptor_index: int, langid: int = LANGID_ENGLISH_US) -> str:
        """Get string descriptor from device."""

        if self._libusb is None:
            raise UsbTmcGenericError("The interface is not open.")

        response = self._libusb.get_string_descriptor(self._device_handle, descriptor_index, self._short_timeout, langid)

        if self._behavior.strip_trailing_string_nul_characters:
            while response.endswith("\x00"):
                response = response[:-1]

        return response

    def get_device_info(self, *, langid: int = LANGID_ENGLISH_US) -> UsbDeviceInfo:
        """Convenience method for getting human-readable information about the currently open USBTMC device."""
        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        device_handle = self._device_handle

        device = libusb.get_device(device_handle)

        device_descriptor = libusb.get_device_descriptor(device)

        vid_pid = f"{device_descriptor.idVendor:04x}:{device_descriptor.idProduct:04x}"
        manufacturer = self.get_string_descriptor(device_descriptor.iManufacturer, langid=langid)
        product = self.get_string_descriptor(device_descriptor.iProduct, langid=langid)
        serial_number = self.get_string_descriptor(device_descriptor.iSerialNumber, langid=langid)

        return UsbDeviceInfo(vid_pid, manufacturer, product, serial_number)

    def get_usbtmc_interface_info(self) -> Optional[UsbTmcInterfaceInfo]:
        """Get the USBTMC interface info as read when the device was opened."""
        return self._usbtmc_info

    def write_message(self, *args: (str | bytes), encoding: str = 'ascii'):
        """Write USBTMC message to the BULK-OUT endpoint."""

        # Collect all arguments into a single byte array.
        message = bytearray()
        for arg in args:
            if isinstance(arg, str):
                arg = arg.encode(encoding)
            if not isinstance(arg, (bytes, bytearray)):
                raise UsbTmcGenericError("Bad argument (expected only strings, bytes, and bytearray).")
            message.extend(arg)

        if len(message) == 0:
            # The USBTMC standard forbids Host-to-Device bulk transfers without payload,
            # meaning we have no way to handle zero-byte messages.
            raise UsbTmcGenericError("Unable to send a zero-length message.")

        max_payload_size = self._behavior.max_bulk_out_transfer_size - BULK_TRANSFER_HEADER_SIZE

        offset = 0
        while offset != len(message):
            btag = self._get_next_bulk_out_btag()
            payload_size = min(max_payload_size, len(message) - offset)
            if offset + payload_size == len(message):
                transfer_attributes = 0x01  # End-Of-Message
            else:
                transfer_attributes = 0x00  # Not End-Of-Message

            header = struct.pack("<BBBxLB3x", BulkMessageID.USBTMC_DEV_DEP_MSG_OUT, btag, btag ^ 0xff, payload_size, transfer_attributes)
            padding = bytes(-payload_size % 4)
            transfer = header + message[offset:offset + payload_size] + padding

            self._bulk_transfer_out(transfer)

            offset += payload_size

    def read_binary_message(self, *, remove_trailing_newline: bool = True) -> bytes:
        """Read a complete USBTMC message from the USBTMC interface's BULK-IN endpoint as a 'bytes' instance."""

        if self._usbtmc_info is None:
            raise UsbTmcGenericError("The interface is not open.")

        # We will collect the data from the separate transfers in the usbtmc_message buffer.
        message = bytearray()

        while True:

            btag = self._get_next_bulk_out_btag()

            max_payload_size = self._behavior.max_bulk_in_transfer_size - BULK_TRANSFER_HEADER_SIZE

            request = struct.pack("<BBBxL4x", BulkMessageID.USBTMC_REQUEST_DEV_DEP_MSG_IN, btag, btag ^ 0xff, max_payload_size)

            self._bulk_transfer_out(request)

            transfer = self._bulk_transfer_in(self._behavior.max_bulk_in_transfer_size)

            # print("bulk-in transfer: max_transfer_size {} max_payload_size {} actual {}".format(max_transfer_size, max_payload_size, len(transfer)))

            if len(transfer) < BULK_TRANSFER_HEADER_SIZE:
                raise UsbTmcGenericError(f"Bulk-in transfer is too short ({len(transfer)} bytes).")

            if len(transfer) % self._usbtmc_info.bulk_in_endpoint_max_packet_size == 0:

                # From to the USBTMC specification:
                #
                # "The device must always terminate a Bulk-IN transfer by sending a short packet. The short packet
                #  may be zero-length or non zero-length. The device may send extra alignment bytes (up to
                #  wMaxPacketSize – 1) to avoid sending a zero-length packet. The alignment bytes should be 0x00-
                #  valued, but this is not required. A device is not required to send any alignment bytes."
                #
                # In accordance with this, we expect to see a short packet here.

                max_dummy_size = self._usbtmc_info.bulk_in_endpoint_max_packet_size
                dummy_transfer = self._bulk_transfer_in(max_dummy_size)
                if len(dummy_transfer) >= self._usbtmc_info.bulk_in_endpoint_max_packet_size:
                    raise UsbTmcGenericError("Bad dummy packet received.")

            (message_id, btag_in, btag_in_inv, payload_size, transfer_attributes) = struct.unpack_from("<BBBxLB3x", transfer)

            if message_id != BulkMessageID.USBTMC_DEV_DEP_MSG_IN:
                raise UsbTmcGenericError("Bulk-in transfer: bad message ID.")

            if (btag_in ^ btag_in_inv) != 0xff:
                raise UsbTmcGenericError("Bulk-in transfer: bad btag/btag_inv pair.")

            if self._behavior.bad_bulk_in_transfer_size:
                # QUIRK:
                # Header + payload sizes should add up to the transfer length, but some devices mess this up.
                pass
            else:
                # Normal behavior, compliant with the specification.
                if payload_size != len(transfer) - BULK_TRANSFER_HEADER_SIZE:
                    raise UsbTmcGenericError("Bulk-in transfer: bad payload size.")

            if payload_size == 0:
                # The USBTMC standard forbids this.
                raise UsbTmcGenericError("Device sent a Bulk-In message without payload.")

            end_of_message = (transfer_attributes & 0x01) != 0

            message.extend(transfer[BULK_TRANSFER_HEADER_SIZE:])

            if end_of_message:
                # End Of Message was set on the last transfer; the message is complete.
                break

        # The message is now complete. We handle some situations where we want to
        # drop bytes from the end of the received message.

        if self._behavior.remove_bulk_padding_bytes:

            # QUIRK:
            #
            # The USB standard mandates that bulk messages must be a multiple of four bytes. To ensure this, both the Host and the Device add 0..3
            # padding bytes to the last transfer of a message. Padding bytes are recommended to be 0x00, although this is not required. If padding
            # bytes are added, the transfer_size reported in the bulk transfer header should reflect the original (pre-padding) byte count.
            #
            # Unfortunately, the interface of some devices erroneously reports the transfer size *including* any padding bytes.
            #
            # For such devices, we attempt here to restore the original message by removing the padding bytes using a heuristic.

            # For devices where we implement the behavior, we expect the message length to be a multiple of four bytes.
            if not len(message) % 4 == 0:
                raise UsbTmcGenericError("Incoming message size is not a multiple of 4 bytes for a device that incorrectly handles padding.")

            # We can have either 0, 1, 2, or 3 padding bytes; and we don't have a fully robust way to figure out how many are really there.
            #
            # However, if we *assume* that the 'real' message (without padding) ends in a
            # newline, we can make a good guess, by considering the following cases:
            #
            #    number of padding bytes    end-of-message        action
            #    -----------------------    ------------------    ---------------------
            #               0               "\x0a"                leaves message as-is
            #               1               "\x0a\x00"            drop last byte
            #               2               "\x0a\x00\x00"        drop last two bytes
            #               3               "\x0a\x00\x00\x00"    drop last three bytes
            #
            # In all other cases, we leave the message as-is.

            if message.endswith(b"\x0a\x00"):
                del message[-1]
            elif message.endswith(b"\x0a\x00\x00"):
                del message[-2:]
            elif message.endswith(b"\x0a\x00\x00\x00"):
                del message[-3:]

        if remove_trailing_newline:

            # More often than not, it is useful to drop a terminating newline character from the end of an incoming message.
            # We do that here if it was requested, and the message indeed ends with a newline; otherwise, we leave the message as-is.

            if message.endswith(b"\n"):
                del message[-1]

        return bytes(message)

    def read_message(self, *, remove_trailing_newline: bool = True, encoding: str = 'ascii') -> str:
        """Read a complete USBTMC message from the USBTMC interface's BULK-IN endpoint, decoding it as a string."""

        message = self.read_binary_message(remove_trailing_newline=remove_trailing_newline)

        return message.decode(encoding)

    def trigger(self) -> None:
        """Send trigger request to device.

        The trigger request is sent by the Host via the BULK-OUT endpoint.
        The Device will not send a response message.

        This message is described in the USBTMC-USB488 sub-protocol standard, section 3.2.1.1.
        """

        btag = self._get_next_bulk_out_btag()

        message = struct.pack("<BBB9x", BulkMessageID.USB488_TRIGGER, btag, btag ^ 0xff)

        self._bulk_transfer_out(message)

    def clear_usbtmc_interface(self) -> None:
        """Clear the USBTMC interface.

        The command sequence is described in 4.2.1.6 and 4.2.1.7 of the USBTMC specification.
        """

        if self._usbtmc_info is None:
            raise UsbTmcGenericError("The interface is not open.")

        if self._behavior.clear_usbtmc_interface_disabled:
            return

        # The sequence starts by sending an INITIATE_CLEAR request to the device.

        response = self._control_transfer(ControlRequest.USBTMC_INITIATE_CLEAR, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USBTMC_INITIATE_CLEAR, ControlStatus(response[0]))

        # The INITIATE_CLEAR request was acknowledged and the device is executing it.
        # We will read the clear status from the device until it is reports success.

        while True:
            response = self._control_transfer(ControlRequest.USBTMC_CHECK_CLEAR_STATUS, 0x0000, 2)

            if response[0] == ControlStatus.USBTMC_SUCCESS:
                break

            if response[0] == ControlStatus.USBTMC_PENDING:
                if (not self._behavior.clear_usbtmc_interface_short_packet_read_request_disabled) and (response[1] & 0x01) != 0:
                    # If bmClear.D0 = 1, the Host should read from the Bulk-IN endpoint until a short
                    # packet is received. The Host must send CHECK_CLEAR_STATUS at a later time.
                    max_dummy_size = self._usbtmc_info.bulk_in_endpoint_max_packet_size
                    print("doing dummy transfer ...")
                    while True:
                        dummy_transfer = self._bulk_transfer_in(max_dummy_size)
                        print("dummy transfer completed:", len(dummy_transfer))
                        if len(dummy_transfer) < self._usbtmc_info.bulk_in_endpoint_max_packet_size:
                            break

        # Out of the CHECK_CLEAR_STATUS loop; the CLEAR has been confirmed.

        # Clear the bulk-out endpoint, as prescribed by the standard.
        self._libusb.clear_halt(self._device_handle, self._usbtmc_info.bulk_out_endpoint)

        # (QUIRK) Clear the bulk-in endpoint if the device requires it.
        if self._behavior.clear_usbtmc_interface_resets_bulk_in:
            # This is NOT prescribed by the standard.
            self._libusb.clear_halt(self._device_handle, self._usbtmc_info.bulk_in_endpoint)

    def get_capabilities(self) -> UsbTmcInterfaceCapabilities:
        """Get USBTMC interface capabilities.

        This is a USBTMC request that USBTMC devices must support.

        This request is described in the USBTMC protocol standard, section 4.2.1.8.
        Extended capabilities for the USB488 sub-protocol are described in the USBTMC-USB488 sub-protocol standard, section 4.2.2.
        """
        response = self._control_transfer(ControlRequest.USBTMC_GET_CAPABILITIES, 0x0000, 24)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USBTMC_GET_CAPABILITIES, ControlStatus(response[0]))

        capabilities = UsbTmcInterfaceCapabilities(
            usbtmc_interface_version                              = (_from_bcd(response[5]), _from_bcd(response[4])),
            usbtmc_interface_supports_indicator_pulse             = ((response[4] >> 2) & 1) != 0,
            usbtmc_interface_is_talk_only                         = ((response[4] >> 1) & 1) != 0,
            usbtmc_interface_is_listen_only                       = ((response[4] >> 0) & 1) != 0,
            usbtmc_interface_supports_termchar_feature            = ((response[5] >> 0) & 1) != 0,
            usb488_interface_version                              = (_from_bcd(response[13]), _from_bcd(response[12])),
            usb488_interface_is_488v2                             = ((response[14] >> 2) & 1) != 0,
            usb488_interface_accepts_remote_local_commands        = ((response[14] >> 1) & 1) != 0,
            usb488_interface_accepts_trigger_command              = ((response[14] >> 0) & 1) != 0,
            usb488_interface_supports_all_mandatory_scpi_commands = ((response[15] >> 3) & 1) != 0,
            usb488_interface_device_is_sr1_capable                = ((response[15] >> 2) & 1) != 0,
            usb488_interface_device_is_rl1_capable                = ((response[15] >> 1) & 1) != 0,
            usb488_interface_device_is_dt1_capable                = ((response[15] >> 0) & 1) != 0
        )

        return capabilities

    def indicator_pulse(self) -> None:
        """Show indicator pulse.

        If the device supports the request, the device then turns on an implementation-dependent
        activity indicator for a human detectable length of time (recommend time is >= 500 milliseconds
        and <= 1 second). The activity indicator then automatically turns off.

        This is a USBTMC request that USBTMC interfaces may or may not support.

        This request is described in the USBTMC protocol standard, section 4.2.1.9.
        """

        response = self._control_transfer(ControlRequest.USBTMC_INDICATOR_PULSE, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USBTMC_INDICATOR_PULSE, ControlStatus(response[0]))

    def read_status_byte(self) -> int:
        """Read device status byte.

        This is a USB488 request that USBTMC interfaces may or may not support.

        This request is described in the USBTMC-USB488 sub-protocol standard, section 4.3.1.
        """

        btag = self._get_next_rsb_btag()

        response = self._control_transfer(ControlRequest.USB488_READ_STATUS_BYTE, btag, 3)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_READ_STATUS_BYTE, ControlStatus(response[0]))

        if response[1] != btag:
            raise UsbTmcGenericError(f"Unexpected btag value in READ_STATUS_BYTE response (expected 0x{btag:02x}, got 0x{response[1]:02x}).")

        status_byte = response[2]

        return status_byte

    def remote_enable_control(self, remote_enable_flag: bool) -> None:
        """Enable or disable remote control.

        This is a USB488 request that USBTMC interfaces may or may not support.

        This request is described in the USBTMC-USB488 sub-protocol standard, section 4.3.2.
        """

        response = self._control_transfer(ControlRequest.USB488_REN_CONTROL, int(remote_enable_flag), 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_REN_CONTROL, ControlStatus(response[0]))

    def goto_local_control(self) -> None:
        """Go to local control mode.

        This is a USB488 request that USBTMC interfaces may or may not support.

        This request is described in the USBTMC-USB488 sub-protocol standard, section 4.3.3.
        """

        response = self._control_transfer(ControlRequest.USB488_GO_TO_LOCAL, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_GO_TO_LOCAL, ControlStatus(response[0]))

    def local_lockout(self) -> None:
        """Enable local lockout.

        This is a USB488 request that USBTMC interfaces may or may not support.

        This request is described in the USBTMC-USB488 sub-protocol standard, section 4.3.4.
        """

        response = self._control_transfer(ControlRequest.USB488_LOCAL_LOCKOUT, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_LOCAL_LOCKOUT, ControlStatus(response[0]))
