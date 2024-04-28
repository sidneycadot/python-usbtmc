"""The usbtmc package provides a cross-platform user-space USBTMC driver."""

import os
import struct
from enum import IntEnum
from typing import NamedTuple, Optional

from .libusb import LibUsbLibrary, LibUsbDeviceHandlePtr, DEFAULT_TIMEOUT


class ControlRequest(IntEnum):
    """Control-out endpoint requests of the USBTMC protocol and the USB488 sub-protocol."""
    # These are for the generic USBTMC protocol:
    INITIATE_ABORT_BULK_OUT     = 1
    CHECK_ABORT_BULK_OUT_STATUS = 2
    INITIATE_ABORT_BULK_IN      = 3
    CHECK_ABORT_BULK_IN_STATUS  = 4
    INITIATE_CLEAR              = 5
    CHECK_CLEAR_STATUS          = 6
    GET_CAPABILITIES            = 7
    INDICATOR_PULSE             = 64
    # These are specific to the USB488 sub-protocol:
    READ_STATUS_BYTE            = 128
    REN_CONTROL                 = 160
    GO_TO_LOCAL                 = 161
    LOCAL_LOCKOUT               = 162


class ControlStatus(IntEnum):
    """Control-in endpoint status of the USBTMC protocol and the USB488 sub-protocol."""
    # USBTMC
    SUCCESS                  = 0x01
    PENDING                  = 0x02
    FAILED                   = 0x80
    TRANSFER_NOT_IN_PROGRESS = 0x81
    SPLIT_NOT_IN_PROGRESS    = 0x82
    SPLIT_IN_PROGRESS        = 0x83
    # USB488
    INTERRUPT_IN_BUSY        = 0x20


class BulkMessageID(IntEnum):
    """Bulk-in and bulk-out endpoint message IDs of the USBTMC protocol and the USB488 sub-protocol."""
    # USBTMC
    DEV_DEP_MSG_OUT            = 1
    REQUEST_DEV_DEP_MSG_IN     = 2
    DEV_DEP_MSG_IN             = 2
    VENDOR_SPECIFIC_OUT        = 126
    REQUEST_VENDOR_SPECIFIC_IN = 127
    VENDOR_SPECIFIC_IN         = 127
    # USB488
    TRIGGER                    = 128


class UsbDeviceInfo(NamedTuple):
    """USB device info as human-readable strings."""
    vid_pid: str
    manufacturer: str
    product: str
    serial_number: Optional[str]


class UsbTmcInterfaceInfo(NamedTuple):
    """Interface info."""
    interface_number: int
    bulk_in_endpoint: int
    bulk_out_endpoint: int


class UsbTmcInterfaceCapabilities(NamedTuple):
    usbtmc_version: int
    usbtmc_indicator_pulse_supported: bool
    usbtmc_interface_is_talk_only: bool
    usbtmc_interface_is_listen_only: bool
    usbtmc_termchar_supported: bool
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


class LibUsbLibraryManager:
    """This class manages a LibUsbLibrary instance and a related LibUsbContextPtr.

    It is shared by all UsbTmcInterface instances to gain access to libusb functionality.
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
        if self._libusb is None:
            # Instantiating the libusb library.
            filename = None
            if "LIBUSB_LIBRARY_PATH" in os.environ:
                filename = os.environ["LIBUSB_LIBRARY_PATH"]
            if filename is None:
                raise UsbTmcError("Don't know where to find libusb. Set the LIBUSB_LIBRARY_PATH environment variable.")
            self._libusb = LibUsbLibrary(filename)
        return self._libusb

    def get_libusb_context(self):
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

                    return UsbTmcInterfaceInfo(altsetting.bInterfaceNumber, bulk_in_endpoint, bulk_out_endpoint)
        finally:
            libusb.free_config_descriptor(config_descriptor)

    return None  # No USBTMC interface was found.


class UsbTmcInterface:
    """This class represents the USBTMC interface of a specific USB device."""

    # All UsbTmcInterface instances will use the same managed instance of libusb and a libusb context.
    _usbtmc_libusb_manager = LibUsbLibraryManager()

    def __init__(self, *, vid: int, pid: int, serial: Optional[str] = None, timeout: Optional[int] = None):

        if timeout is None:
            timeout = DEFAULT_TIMEOUT

        self._vid = vid
        self._pid = pid
        self._serial = serial
        self._timeout = timeout

        self._libusb = None
        self._device_handle = None
        self._usbtmc_info = None
        self._bulk_out_btag = None
        self._rsb_btag = None

    def open(self, *, clear_interface: bool = True) -> None:
        """Find and open the device.

        Once opened, claim the interface, then clear the interface I/O (unless False is passed to clear_interface).
        """

        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        ctx = UsbTmcInterface._usbtmc_libusb_manager.get_libusb_context()

        device_handle = libusb.find_and_open_device(ctx, self._vid, self._pid, self._serial)
        if device_handle is None:
            raise UsbTmcError("Device not found. Make sure it is connected and the user has I/O permissions.")

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
            self.claim_interface()

            # By default, we also clear the interface, so we're ready to start afresh;
            # but this behavior can be overridden.
            if clear_interface:
                # Don't use clear_usbtmc_interface, as it ex
                self.clear_usbtmc_interface()

        except:
            # If any exception happened during the first uses of the newly opened device,
            # we immediately close the device and re-raise the exception.
            self.close()
            raise

    def close(self) -> None:
        """Close the device."""

        # Let the operating system know we're done with it.
        self.release_interface()

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

    def get_device_info(self, *, langid: Optional[int] = None) -> UsbDeviceInfo:
        """Convenience method for getting human-readable information on the currently open USBTMC device."""
        libusb = UsbTmcInterface._usbtmc_libusb_manager.get_libusb()
        device_handle = self._device_handle

        device = libusb.get_device(device_handle)

        device_descriptor = libusb.get_device_descriptor(device)

        vid_pid = "{:04x}:{:04x}".format(device_descriptor.idVendor, device_descriptor.idProduct)
        manufacturer = libusb.get_string_descriptor(device_handle, device_descriptor.iManufacturer, langid=langid)
        product = libusb.get_string_descriptor(device_handle, device_descriptor.iProduct, langid=langid)
        serial_number = libusb.get_string_descriptor(device_handle, device_descriptor.iSerialNumber, langid=langid)

        return UsbDeviceInfo(vid_pid, manufacturer, product, serial_number)

    def _get_next_bulk_out_btag(self) -> int:
        """Get next bTag value that identifies a BULK-OUT transfer.

        A transfer identifier. The Host must set bTag different than the bTag used in the previous Bulk-OUT Header.
        The Host should increment the bTag by 1 each time it sends a new Bulk-OUT Header.
        The Host must set bTag such that 1<=bTag<=255.
        """
        self._bulk_out_btag = self._bulk_out_btag % 255 + 1
        return self._bulk_out_btag

    def _get_next_rsb_btag(self) -> int:
        """Get next bTag value that identifies a READ_STATUS_BYTE control transfer.

        The bTag value (2 <= bTag <=127) for this request.
        The device must return this bTag value along with the Status Byte.
        The Host should increment the bTag by 1 for each new READ_STATUS_BYTE request to help identify when the
        response arrives on the Interrupt-IN endpoint.
        """
        self._rsb_btag = (self._rsb_btag - 1) % 126 + 2
        return self._rsb_btag

    def claim_interface(self) -> None:
        """Let the operating system know that we want to have exclusive access to the interface."""
        self._libusb.claim_interface(self._device_handle, self._usbtmc_info.interface_number)

    def release_interface(self) -> None:
        """Let the operating system know that we want to drop exclusive access to the interface."""
        self._libusb.release_interface(self._device_handle, self._usbtmc_info.interface_number)

    def write_usbtmc_message(self, *args: (str | bytes | bytearray), encoding: str = 'ascii', timeout: Optional[int] = None):
        """Write USBTMC message to the BULK-OUT endpoint.

        A USBTMC message is made up of one or more bulk transfers.

        A bulk transfer is made of one or more bus transactions. Chopping up the bulk transfer into multiple
        bus transactions is arranged by the OS or chipset.
        """

        if timeout is None:
            timeout = self._timeout

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

        header = struct.pack("<BBBBLL", BulkMessageID.DEV_DEP_MSG_OUT, btag, btag ^ 0xff, 0x00, transfer_size, end_of_message)
        padding = bytes(-len(data) % 4)
        message = header + data + padding

        self._libusb.bulk_transfer_out(self._device_handle, self._usbtmc_info.bulk_out_endpoint, message, timeout)

    def read_usbtmc_binary_message(self, *, remove_trailing_newline: bool = True, timeout: Optional[int] = None) -> bytes:
        """Read USBTMC message from BULK-IN endpoint.

        A USBTMC message is made up of one or more bulk transfers.

        A bulk transfer is made of one or more bus transactions. Chopping up the bulk transfer into multiple
        bus transactions is arranged by the OS or chipset.
        """

        if timeout is None:
            timeout = self._timeout

        # We will collect the data from the separate transfers in the usbtmc_message bytearray.
        usbtmc_message = bytearray()

        while True:

            btag = self._get_next_bulk_out_btag()
            transfer_size = 16384

            request = struct.pack("<BBBBLL", BulkMessageID.REQUEST_DEV_DEP_MSG_IN, btag, btag ^ 0xff, 0x00, transfer_size, 0)
            self._libusb.bulk_transfer_out(self._device_handle, self._usbtmc_info.bulk_out_endpoint, request, timeout)

            maxsize = transfer_size + 12
            transfer = self._libusb.bulk_transfer_in(
                self._device_handle, self._usbtmc_info.bulk_in_endpoint, maxsize, timeout)

            # print("bulk-in transfer: {} {} {}".format(transfer_size, maxsize, len(transfer)))

            if len(transfer) < 12:
                raise UsbTmcError("Bulk-in transfer is too short.")

            (message_id, btag_in, btag_in_inv, reserved) = struct.unpack_from("<BBBB", transfer, 0)

            if message_id != BulkMessageID.DEV_DEP_MSG_IN:
                raise UsbTmcError("Bulk-in transfer: bad message ID.")

            if (btag_in ^ btag_in_inv) != 0xff:
                raise UsbTmcError("Bulk0in transfer: bad btag/btag_inv pair.")

            (transfer_size_readback, attributes) = struct.unpack_from("<LB", transfer, 4)

            end_of_message = (attributes & 0x01) != 0

            usbtmc_message.extend(transfer[12:])

            if end_of_message:
                # End Of Message was set on the last transfer; the message is complete.
                break

        if remove_trailing_newline:
            if not usbtmc_message.endswith(b"\n"):
                raise UsbTmcError("The USBTMC message didn't end with a trailing newline.")
            # Remove the trailing newline.
            usbtmc_message.pop()

        return bytes(usbtmc_message)

    def read_usbtmc_message(self, *, remove_trailing_newline: bool = True, encoding: str = 'ascii', timeout: Optional[int] = None) -> str:
        """Read USBTMC message from BULK-IN endpoint, decoding it as a string."""

        usbtmc_message = self.read_usbtmc_binary_message(remove_trailing_newline=remove_trailing_newline, timeout=timeout)

        return usbtmc_message.decode(encoding)

    def trigger(self, *, timeout: Optional[int] = None):
        """Write TRIGGER request to the BULK-OUT endpoint."""

        if timeout is None:
            timeout = self._timeout

        btag = self._get_next_bulk_out_btag()

        transfer = struct.pack("<BBBBLL", BulkMessageID.TRIGGER, btag, btag ^ 0xff, 0x00, 0x00000000, 0x00000000)

        self._libusb.bulk_transfer_out(self._device_handle, self._usbtmc_info.bulk_out_endpoint, transfer, timeout)

    def clear_usbtmc_interface(self, *, timeout: Optional[int] = None) -> None:
        """Clear the USBTMC interface bulk I/O endpoints.

        The command sequence is described in 4.2.1.6 and 4.2.1.7 of the USBTMC spec."""

        if timeout is None:
            timeout = self._timeout

        # The sequence starts by sending an INITIATE_CLEAR request to the device.

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.INITIATE_CLEAR,       # bRequest
            0x0000,                              # wValue
            self._usbtmc_info.interface_number,  # wIndex
            1,                                   # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError()

        # The INITIATE_CLEAR request was acknowledged and the device is executing it.
        # We will read the clear status from the device until it is reports success.

        while True:
            response = self._libusb.control_transfer(
                self._device_handle,
                0xa1,                                # bmRequestType
                ControlRequest.CHECK_CLEAR_STATUS,   # bRequest
                0x0000,                              # wValue
                self._usbtmc_info.interface_number,  # wIndex
                2,                                   # wLength
                timeout
            )

            if response[0] == ControlStatus.SUCCESS:
                break

            elif response[0] == ControlStatus.PENDING:
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

    def get_capabilities(self, *, timeout: Optional[int] = None) -> UsbTmcInterfaceCapabilities:
        """Get device capabilities.

        This is a USBTMC request that USBTMC devices must handle.
        """
        if timeout is None:
            timeout = self._timeout

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.GET_CAPABILITIES,     # bRequest
            0x0000,                              # wValue
            self._usbtmc_info.interface_number,  # wIndex
            24,                                  # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError("GET_CAPABILITIES request failed.")

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

    def indicator_pulse(self, *, timeout: Optional[int] = None) -> None:
        """Show indicator pulse.

        This is a USBTMC request that USBTMC devices may or may not support.
        """

        if timeout is None:
            timeout = self._timeout

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.INDICATOR_PULSE,      # bRequest
            0x0000,                              # wValue
            self._usbtmc_info.interface_number,  # wIndex
            1,                                   # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError("INDICATOR_PULSE request failed.")

    def read_status_byte(self, *, timeout: Optional[int] = None) -> int:
        """Read device status byte.

        This is a USB488 request that USBTMC devices may or may not support.
        """

        if timeout is None:
            timeout = self._timeout

        btag = self._get_next_rsb_btag()

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.READ_STATUS_BYTE,     # bRequest
            btag,                                # wValue
            self._usbtmc_info.interface_number,  # wIndex
            3,                                   # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError("READ_STATUS_BYTE request failed.")

        if response[1] != btag:
            raise UsbTmcError("Bad btag value in READ_STATUS_BYTE response.")

        status_byte = response[2]

        return status_byte

    def ren_control(self, ren_flag: bool, *, timeout: Optional[int] = None) -> None:
        """Set REN CONTROL.

        This is a USB488 request that USBTMC devices may or may not support.
        """

        if timeout is None:
            timeout = self._timeout

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.REN_CONTROL,          # bRequest
            0x0001 if ren_flag else 0x0000,      # wValue
            self._usbtmc_info.interface_number,  # wIndex
            1,                                   # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError("REN_CONTROL request failed.")

    def go_to_local(self, *, timeout: Optional[int] = None) -> None:
        """Go to local control mode.

        This is a USB488 request that USBTMC devices may or may not support.
        """

        if timeout is None:
            timeout = self._timeout

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.GO_TO_LOCAL,          # bRequest
            0x0000,                              # wValue
            self._usbtmc_info.interface_number,  # wIndex
            1,                                   # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError("GO_TO_LOCAL request failed.")

    def local_lockout(self, *, timeout: Optional[int] = None) -> None:
        """Enable local lockout.

        This is a USB488 request that USBTMC devices may or may not support.
        """

        if timeout is None:
            timeout = self._timeout

        response = self._libusb.control_transfer(
            self._device_handle,
            0xa1,                                # bmRequestType
            ControlRequest.LOCAL_LOCKOUT,        # bRequest
            0x0000,                              # wValue
            self._usbtmc_info.interface_number,  # wIndex
            1,                                   # wLength
            timeout
        )

        if response[0] != ControlStatus.SUCCESS:
            raise UsbTmcError("LOCAL_LOCKOUT request failed.")
