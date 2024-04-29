"""The usbtmc package provides a cross-platform user-space USBTMC driver."""

import os
import struct
from typing import NamedTuple, Optional
import ctypes.util

from .better_int_enum import BetterIntEnum
from .libusb_library import LibUsbLibrary, LibUsbDeviceHandlePtr, LANGID_ENGLISH_US
from .quirks import get_usbtmc_interface_quirks


class ControlRequest(BetterIntEnum):
    """Control-out endpoint requests of the USBTMC protocol and the USB488 sub-protocol."""
    # Values defined for the generic USBTMC protocol:
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
    # Values defined for the generic USBTMC protocol:
    USBTMC_SUCCESS                  = 0x01
    USBTMC_PENDING                  = 0x02
    USBTMC_FAILED                   = 0x80
    USBTMC_TRANSFER_NOT_IN_PROGRESS = 0x81
    USBTMC_SPLIT_NOT_IN_PROGRESS    = 0x82
    USBTMC_SPLIT_IN_PROGRESS        = 0x83
    #  Values defined for the USB488 sub-protocol:
    USB488_INTERRUPT_IN_BUSY        = 0x20


class BulkMessageID(BetterIntEnum):
    """Bulk-in and bulk-out endpoint message IDs of the USBTMC protocol and the USB488 sub-protocol."""
    # Values defined for the generic USBTMC protocol:
    USBTMC_DEV_DEP_MSG_OUT            = 1
    USBTMC_REQUEST_DEV_DEP_MSG_IN     = 2
    USBTMC_DEV_DEP_MSG_IN             = 2
    USBTMC_VENDOR_SPECIFIC_OUT        = 126
    USBTMC_REQUEST_VENDOR_SPECIFIC_IN = 127
    USBTMC_VENDOR_SPECIFIC_IN         = 127
    #  Values defined for the USB488 sub-protocol:
    USBTMC_TRIGGER                    = 128


class UsbDeviceInfo(NamedTuple):
    """USB device info as human-readable strings."""
    vid_pid: str
    manufacturer: str
    product: str
    serial_number: Optional[str]


class UsbTmcInterfaceInfo(NamedTuple):
    """USBTMC interface info."""
    interface_number: int
    interface_protocol: int  # 0: USBTMC, 1: USB488.
    bulk_in_endpoint: int
    bulk_out_endpoint: int


class UsbTmcInterfaceCapabilities(NamedTuple):
    """USBTMC capabilities as read from the USBTMC interface."""
    # Version number and capabilities defined for the generic USBTMC protocol:
    usbtmc_version: int
    usbtmc_indicator_pulse_supported: bool
    usbtmc_interface_is_talk_only: bool
    usbtmc_interface_is_listen_only: bool
    usbtmc_termchar_supported: bool
    # Version number and capabilities defined for the USB488 sub-protocol:
    usb488_interface_version: int
    usb488_interface_is_488v2: bool
    usb488_interface_accepts_remote_local_commands: bool
    usb488_interface_accepts_trigger_command: bool
    usb488_device_supports_all_mandatory_scpi_commands: bool
    usb488_device_is_sr1_capable: bool
    usb488_device_is_rr1_capable: bool
    usb488_device_is_dt1_capable: bool


class UsbTmcError(Exception):
    """An error occurred at the USBTMC level."""


class UsbTmcControlResponseError(Exception):
    """An error occurred awhile doing a control transfer."""
    def __init__(self, request: ControlRequest, status: ControlStatus):
        self.request = request
        self.status = status

    def __str__(self):
        return f"UsbTmcControlResponseError(request=ControlRequest.{self.request.name}, status=ControlStatus.{self.status.name})"


class LibUsbLibraryManager:
    """This class manages a LibUsbLibrary instance and a LibUsbContextPtr.

    It is used by all UsbTmcInterface instances to gain access to libusb functionality.
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
        """Get the libusb library instance; instantiate if necessary."""
        if self._libusb is None:
            # Dynamically load the libusb library.
            if "LIBUSB_LIBRARY_PATH" in os.environ:
                filename = os.environ["LIBUSB_LIBRARY_PATH"]
            else:
                # This returns None if the library is not found.
                filename = ctypes.util.find_library("usb-1.0")
            if filename is None:
                raise UsbTmcError("Don't know where to find libusb. Set the LIBUSB_LIBRARY_PATH environment variable.")
            self._libusb = LibUsbLibrary(filename)
        return self._libusb

    def get_libusb_context(self):
        """Get the libusb context instance; initialize if necessary."""
        if self._ctx is None:
            # Initialize a libusb context.
            self._ctx = self.get_libusb().init()
        return self._ctx


def find_usbtmc_interface(libusb: LibUsbLibrary, device_handle: LibUsbDeviceHandlePtr) -> Optional[UsbTmcInterfaceInfo]:
    """Find the USBTMC interface of a given USB device."""

    device = libusb.get_device(device_handle)
    device_descriptor = libusb.get_device_descriptor(device)

    if device_descriptor.bNumConfigurations != 1:
        # Unable to deal with devices that have multiple configurations, yet.
        raise UsbTmcError("Unable to handle devices with multiple configurations.")

    for config_index in range(device_descriptor.bNumConfigurations):
        config_descriptor = libusb.get_config_descriptor(device, config_index)
        try:
            for interface_index in range(config_descriptor.contents.bNumInterfaces):
                interface = config_descriptor.contents.interface[interface_index]

                if interface.num_altsetting != 1:
                    # Unable to deal with interfaces that have multiple alt-settings, yet.
                    raise UsbTmcError("Unable to handle interfaces with multiple alt settings.")

                for altsetting_index in range(interface.num_altsetting):
                    altsetting = interface.altsetting[altsetting_index]

                    found_usbtmc_interface = ((altsetting.bInterfaceClass == 0xfe) and
                                              (altsetting.bInterfaceSubClass == 0x03))
                    if not found_usbtmc_interface:
                        continue

                    bulk_in_endpoint = None
                    bulk_out_endpoint = None

                    for endpoint_index in range(altsetting.bNumEndpoints):

                        endpoint = altsetting.endpoint[endpoint_index]

                        endpoint_address = endpoint.bEndpointAddress
                        endpoint_direction = (endpoint.bEndpointAddress & 0x80)
                        endpoint_type = endpoint.bmAttributes & 0x0f

                        match (endpoint_type, endpoint_direction):
                            case (0x02, 0x80):  # BULK-IN endpoint
                                bulk_in_endpoint = endpoint_address
                            case (0x02, 0x00):  # BULK-OUT endpoint
                                bulk_out_endpoint = endpoint_address

                    return UsbTmcInterfaceInfo(altsetting.bInterfaceNumber, altsetting.bInterfaceProtocol, bulk_in_endpoint, bulk_out_endpoint)
        finally:
            libusb.free_config_descriptor(config_descriptor)

    return None  # No USBTMC interface was found.


class UsbTmcInterface:
    """This class represents the USBTMC interface of a specific USB device."""

    # All UsbTmcInterface instances will use the same managed instance of libusb and a libusb context.
    _usbtmc_libusb_manager = LibUsbLibraryManager()

    def __init__(self, *, vid: int, pid: int, serial: Optional[str] = None, short_timeout: Optional[float] = None, min_bulk_speed: Optional[float] = None):

        if short_timeout is None:
            # 100 milliseconds. Used for control transfers and small bulk transfers.
            short_timeout = 100.0

        if min_bulk_speed is None:
            # Default value: 100.0 bytes/ms, or, equivalently, 100 kilobytes/second.
            # This is conservative, leading to long timeout values on large bulk transfers.
            min_bulk_speed = 100.0

        self._vid = vid
        self._pid = pid
        self._serial = serial
        self._short_timeout = round(short_timeout)  # Short timeout, in [ms]. Used for control transfers and short bulk transfers.
        self._min_bulk_speed = min_bulk_speed       # Minimum bulk speed, in [bytes/ms] or, equivalently, [kB/s].

        self._quirks = get_usbtmc_interface_quirks(vid, pid)

        self._libusb = None
        self._device_handle = None
        self._usbtmc_info = None
        self._bulk_out_btag = None
        self._rsb_btag = None

    def open(self) -> None:
        """Find and open the device.

        Once opened, claim the interface, then clear the interface I/O (unless False is passed to clear_interface).
        """

        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        ctx = UsbTmcInterface._usbtmc_libusb_manager.get_libusb_context()

        device_handle = libusb.find_and_open_device(ctx, self._vid, self._pid, self._serial, self._short_timeout)
        if device_handle is None:
            raise UsbTmcError(f"Device {self._vid:04x}:{self._pid:04x} not found."
                              " Make sure the device is connected and user permissions allow I/O access to the device.")

        # We found the device and opened it. See if it provides a USBTMC interface.
        # If not, we close the device handle and raise an exception.

        usbtmc_info = find_usbtmc_interface(libusb, device_handle)
        if usbtmc_info is None:
            libusb.close(device_handle)
            raise UsbTmcError("The device doesn't have a USBTMC interface.")

        # Declare the device open, but prepare to close it when a subsequent operation fails.

        self._libusb = libusb
        self._device_handle = device_handle
        self._usbtmc_info = usbtmc_info
        self._bulk_out_btag = 0  # Will be incremented to 1 at first invocation _get_next_bulk_out_btag.
        self._rsb_btag = 1  # Will be incremented to 2 at first invocation of _get_next_rsb_btag.

        try:
            # Claim the interface.
            self._claim_interface()

            match self._quirks.open_reset_method:
                case 0:
                    pass  # no-op
                case 1:
                    self.clear_usbtmc_interface()

        except:
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

        # Set all device-specific fields to None. They will need to be re-initialized when the device
        # is reopened.
        self._libusb = None
        self._device_handle = None
        self._usbtmc_info = None
        self._bulk_out_btag = None
        self._rsb_btag = None

    def _control_transfer(self, request: ControlRequest, w_value: int, w_length: int) -> bytes:
        """Perform a control transfer to the USBTMC interface."""

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
        self._bulk_out_btag = self._bulk_out_btag % 255 + 1
        return self._bulk_out_btag

    def _get_next_rsb_btag(self) -> int:
        """Get next bTag value that identifies a READ_STATUS_BYTE control transfer.

        The bTag value (2 <= bTag <= 127) for this request.
        The device must return this bTag value along with the Status Byte.
        The Host should increment the bTag by 1 for each new READ_STATUS_BYTE request to help identify when the
        response arrives at the Interrupt-IN endpoint.
        """
        self._rsb_btag = (self._rsb_btag - 1) % 126 + 2
        return self._rsb_btag

    def _claim_interface(self) -> None:
        """Let the operating system know that we want to have exclusive access to the interface."""
        self._libusb.claim_interface(self._device_handle, self._usbtmc_info.interface_number)

    def _release_interface(self) -> None:
        """Let the operating system know that we want to drop exclusive access to the interface."""
        self._libusb.release_interface(self._device_handle, self._usbtmc_info.interface_number)

    def _calculate_bulk_timeout(self, num_octets: int) -> int:
        """Return a pessimistic estimate for the time a bulk transfer can take, in milliseconds."""
        return self._short_timeout + round(num_octets / self._min_bulk_speed)

    def _bulk_transfer_in(self, maxsize: int) -> bytes:
        """Perform a single BULK-IN transfer."""
        timeout = self._calculate_bulk_timeout(maxsize)
        return self._libusb.bulk_transfer_in(self._device_handle, self._usbtmc_info.bulk_in_endpoint, maxsize, timeout)

    def _bulk_transfer_out(self, transfer: bytes) -> None:
        """Perform a single BULK-OUT transfer."""
        timeout = self._calculate_bulk_timeout(len(transfer))
        self._libusb.bulk_transfer_out(self._device_handle, self._usbtmc_info.bulk_out_endpoint, transfer, timeout)

    def _get_string_descriptor(self, descriptor_index: int, langid: Optional[int]) -> str:
        """Get string descriptor from device."""
        if langid is None:
            # All USBTMC devices are required to support English (US).
            langid = LANGID_ENGLISH_US

        return self._libusb.get_string_descriptor(self._device_handle, descriptor_index, self._short_timeout, langid)

    def get_device_info(self, *, langid: Optional[int] = None) -> UsbDeviceInfo:
        """Convenience method for getting human-readable information on the currently open USBTMC device."""
        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        device_handle = self._device_handle

        device = libusb.get_device(device_handle)

        device_descriptor = libusb.get_device_descriptor(device)

        vid_pid = "{:04x}:{:04x}".format(device_descriptor.idVendor, device_descriptor.idProduct)
        manufacturer = self._get_string_descriptor(device_descriptor.iManufacturer, langid=langid)
        product = self._get_string_descriptor(device_descriptor.iProduct, langid=langid)
        serial_number = self._get_string_descriptor(device_descriptor.iSerialNumber, langid=langid)

        return UsbDeviceInfo(vid_pid, manufacturer, product, serial_number)

    def write_usbtmc_message(self, *args: (str | bytes | bytearray), encoding: str = 'ascii'):
        """Write USBTMC message to the BULK-OUT endpoint.

        For now, we write the entire message in a single transfer.
        TODO: split up the message in multiple transfers.
        """

        # Collect all arguments into a single byte array.
        data = bytearray()
        for arg in args:
            if isinstance(arg, str):
                arg = arg.encode(encoding)
            if not isinstance(arg, (bytes, bytearray)):
                raise UsbTmcError("Bad argument (expected only strings, bytes, and bytearray)")
            data.extend(arg)

        btag = self._get_next_bulk_out_btag()
        transfer_size = len(data)
        end_of_message = 1

        header = struct.pack("<BBBBLL", BulkMessageID.USBTMC_DEV_DEP_MSG_OUT, btag, btag ^ 0xff, 0x00, transfer_size, end_of_message)
        padding = bytes(-len(data) % 4)
        message = header + data + padding

        self._bulk_transfer_out(message)

    def read_usbtmc_binary_message(self, *, remove_trailing_newline: bool = True) -> bytes:
        """Read a complete USBTMC message from the USBTMC interface's BULK-IN endpoint as a 'bytes' instance."""

        # We will collect the data from the separate transfers in the usbtmc_message buffer.
        usbtmc_message = bytearray()

        while True:

            btag = self._get_next_bulk_out_btag()

            transfer_size = 16384

            request = struct.pack("<BBBBLL", BulkMessageID.USBTMC_REQUEST_DEV_DEP_MSG_IN, btag, btag ^ 0xff, 0x00, transfer_size, 0)

            self._bulk_transfer_out(request)

            maxsize = transfer_size + 12
            transfer = self._bulk_transfer_in(maxsize)

            print("bulk-in transfer: {} {} {}".format(transfer_size, maxsize, len(transfer)))

            if len(transfer) < 12:
                raise UsbTmcError("Bulk-in transfer is too short.")

            (message_id, btag_in, btag_in_inv, reserved) = struct.unpack_from("<BBBB", transfer, 0)

            if message_id != BulkMessageID.USBTMC_DEV_DEP_MSG_IN:
                raise UsbTmcError("Bulk-in transfer: bad message ID.")

            if (btag_in ^ btag_in_inv) != 0xff:
                raise UsbTmcError("Bulk0in transfer: bad btag/btag_inv pair.")

            (transfer_size_readback, attributes) = struct.unpack_from("<LB", transfer, 4)

            end_of_message = (attributes & 0x01) != 0

            usbtmc_message.extend(transfer[12:])

            if end_of_message:
                # End Of Message was set on the last transfer; the message is complete.
                break

        if self._quirks.remove_bulk_padding_bytes:
            # The interface erroneously reports the transfer size including any padding bytes.
            # This means that the transfer size will always be divisible by four.
            if not len(usbtmc_message) % 4 == 0:
                raise UsbTmcError("Transfer size is not a multiple of 4.")
            # We can have outer 0, 1, 2, or 3 padding bytes; and we don't really know
            # how many we have.
            # We *assume* that the 'real' message (without padding) ends in a '\n'.
            #
            # This leaves the following cases:
            #     padding == 0: message ends with "\x0a"
            #     padding == 1: message ends with "\x0a\x00"
            #     padding == 2: message ends with "\x0a\x00\x00"
            #     padding == 3: message ends with "\x0a\x00\x00\x00"

            if usbtmc_message.endswith(b"\x0a\x00"):
                del usbtmc_message[-1]
            elif usbtmc_message.endswith(b"\x0a\x00\x00"):
                del usbtmc_message[-2:]
            elif usbtmc_message.endswith(b"\x0a\x00\x00\x00"):
                del usbtmc_message[-3:]

        if remove_trailing_newline:
            if not usbtmc_message.endswith(b"\n"):
                raise UsbTmcError("The USBTMC message didn't end with a trailing newline.")
            #  Remove the trailing newline.
            del usbtmc_message[-1]

        return bytes(usbtmc_message)

    def read_usbtmc_message(self, *, remove_trailing_newline: bool = True, encoding: str = 'ascii') -> str:
        """Read a complete USBTMC message from the USBTMC interface's BULK-IN endpoint, decoding it as a string."""

        usbtmc_message = self.read_usbtmc_binary_message(remove_trailing_newline=remove_trailing_newline)

        return usbtmc_message.decode(encoding)

    def trigger(self):
        """Write TRIGGER request to the BULK-OUT endpoint."""

        btag = self._get_next_bulk_out_btag()

        message = struct.pack("<BBBBLL", BulkMessageID.USBTMC_TRIGGER, btag, btag ^ 0xff, 0x00, 0x00000000, 0x00000000)

        self._bulk_transfer_out(message)

    def clear_usbtmc_interface(self) -> None:
        """Clear the USBTMC interface bulk I/O endpoints.

        The command sequence is described in 4.2.1.6 and 4.2.1.7 of the USBTMC spec."""

        if self._quirks.clear_usbtmc_interface_disabled:
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

            elif response[0] == ControlStatus.USBTMC_PENDING:
                if (response[1] & 0x01) != 0:
                    # If bmClear.D0 = 1, the Host should read from the Bulk-IN endpoint until a short packet is
                    # received. The Host must send CHECK_CLEAR_STATUS at a later time.
                    #
                    # We have never encountered this behavior even though it is specified in the spec.
                    # We don't implement it unless we can test it.
                    #
                    # If you have a device the behavior of which can reproducibly trigger this exception,
                    # let us know.
                    raise UsbTmcError("Short packet read during clear is not yet implemented.")

        # Out of the CHECK_CLEAR_STATUS loop; the CLEAR has been confirmed.

        # Clear the bulk-out endpoint, as prescribed by the standard.
        self._libusb.clear_halt(self._device_handle, self._usbtmc_info.bulk_out_endpoint)

        # QUIRK: Clear the bulk-in endpoint. This is needed by some devices.
        if self._quirks.usbtmc_clear_sequence_resets_bulk_in:
            # This is NOT prescribed by the standard.
            self._libusb.clear_halt(self._device_handle, self._usbtmc_info.bulk_in_endpoint)

    def get_capabilities(self) -> UsbTmcInterfaceCapabilities:
        """Get device capabilities.

        This is a USBTMC request that USBTMC devices must support.
        """
        response = self._control_transfer(ControlRequest.USBTMC_GET_CAPABILITIES, 0x0000, 24)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USBTMC_GET_CAPABILITIES, ControlStatus(response[0]))

        capabilities = UsbTmcInterfaceCapabilities(
            usbtmc_version                                     = response[4] + response[5] * 0x100,
            usbtmc_indicator_pulse_supported                   = ((response[4] >> 2) & 1) != 0,
            usbtmc_interface_is_talk_only                      = ((response[4] >> 1) & 1) != 0,
            usbtmc_interface_is_listen_only                    = ((response[4] >> 0) & 1) != 0,
            usbtmc_termchar_supported                          = ((response[5] >> 0) & 1) != 0,
            usb488_interface_version                           = response[12] + response[13] * 0x100,
            usb488_interface_is_488v2                          = ((response[14] >> 2) & 1) != 0,
            usb488_interface_accepts_remote_local_commands     = ((response[14] >> 1) & 1) != 0,
            usb488_interface_accepts_trigger_command           = ((response[14] >> 0) & 1) != 0,
            usb488_device_supports_all_mandatory_scpi_commands = ((response[15] >> 3) & 1) != 0,
            usb488_device_is_sr1_capable                       = ((response[15] >> 2) & 1) != 0,
            usb488_device_is_rr1_capable                       = ((response[15] >> 1) & 1) != 0,
            usb488_device_is_dt1_capable                       = ((response[15] >> 0) & 1) != 0
        )

        return capabilities

    def indicator_pulse(self) -> None:
        """Show indicator pulse.

        If the device supports the request, the device then turns on an implementation-dependent
        activity indicator for a human detectable length of time (recommend time is >= 500 milliseconds
        and <= 1 second). The activity indicator then automatically turns off.

        This is a USBTMC request that USBTMC interfaces may or may not support.
        """

        response = self._control_transfer(ControlRequest.USBTMC_INDICATOR_PULSE, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USBTMC_INDICATOR_PULSE, ControlStatus(response[0]))

    def read_status_byte(self) -> int:
        """Read device status byte.

        This is a USB488 request that USBTMC interfaces may or may not support.
        """

        btag = self._get_next_rsb_btag()

        response = self._control_transfer(ControlRequest.USB488_READ_STATUS_BYTE, 0x0000, 3)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_READ_STATUS_BYTE, ControlStatus(response[0]))

        if response[1] != btag:
            raise UsbTmcError("Bad btag value in READ_STATUS_BYTE response.")

        status_byte = response[2]

        return status_byte

    def remote_enable_control(self, remote_enable_flag: bool) -> None:
        """Set remote enable control to True or False.

        This is a USB488 request that USBTMC interfaces may or may not support.
        """

        response = self._control_transfer(ControlRequest.USB488_REN_CONTROL, int(remote_enable_flag), 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_REN_CONTROL, ControlStatus(response[0]))

    def go_to_local(self) -> None:
        """Go to local control mode.

        This is a USB488 request that USBTMC interfaces may or may not support.
        """

        response = self._control_transfer(ControlRequest.USB488_GO_TO_LOCAL, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_GO_TO_LOCAL, ControlStatus(response[0]))

    def local_lockout(self) -> None:
        """Enable local lockout.

        This is a USB488 request that USBTMC interfaces may or may not support.
        """

        response = self._control_transfer(ControlRequest.USB488_LOCAL_LOCKOUT, 0x0000, 1)
        if response[0] != ControlStatus.USBTMC_SUCCESS:
            raise UsbTmcControlResponseError(ControlRequest.USB488_LOCAL_LOCKOUT, ControlStatus(response[0]))
