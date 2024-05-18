"""Minimalistic ctypes-based libusb-1.0 binding for implementing USBTMC support."""

from typing import Optional
import ctypes
import sys

# libusb constants.

LIBUSB_SUCCESS = 0
LIBUSB_ERROR_NOT_SUPPORTED = -12

LIBUSB_ENDPOINT_IN = 0x80
LIBUSB_ENDPOINT_OUT = 0x00

LIBUSB_REQUEST_GET_DESCRIPTOR = 0x06

LIBUSB_DT_STRING = 0x03

# Alignment for structs used by libusb. The value 8 works on 64-bit Microsoft Windows.
C_STRUCT_ALIGNMENT = 8

LANGID_ENGLISH_US = 0x0409  # USBTMC devices are required to support at least this language for string descriptors.


# libusb types.

class LibUsbContext(ctypes.Structure):
    """Opaque type representing a libusb context."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = []


LibUsbContextPtr = ctypes.POINTER(LibUsbContext)


class LibUsbDevice(ctypes.Structure):
    """Opaque type representing a libusb device."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = []


LibUsbDevicePtr = ctypes.POINTER(LibUsbDevice)


class LibUsbDeviceHandle(ctypes.Structure):
    """Opaque type representing a libusb device handle (i.e., a USB device that has been opened)."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = []


LibUsbDeviceHandlePtr = ctypes.POINTER(LibUsbDeviceHandle)


class LibUsbEndpointDescriptor(ctypes.Structure):
    """A libusb endpoint descriptor."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = [
        ("bLength", ctypes.c_uint8),
        ("bDescriptorType", ctypes.c_uint8),
        ("bEndpointAddress", ctypes.c_uint8),
        ("bmAttributes", ctypes.c_uint8),
        ("wMaxPacketSize", ctypes.c_uint16),
        ("bInterval", ctypes.c_uint8),
        ("bRefresh", ctypes.c_uint8),
        ("bSynchAddress", ctypes.c_uint8),
        ("extra", ctypes.POINTER(ctypes.c_ubyte)),
        ("extra_length", ctypes.c_int)
    ]


LibUsbEndpointDescriptorPtr = ctypes.POINTER(LibUsbEndpointDescriptor)


class LibUsbInterfaceDescriptor(ctypes.Structure):
    """A libusb interface descriptor."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = [
        ("bLength", ctypes.c_uint8),
        ("bDescriptorType", ctypes.c_uint8),
        ("bInterfaceNumber", ctypes.c_uint8),
        ("bAlternateSetting", ctypes.c_uint8),
        ("bNumEndpoints", ctypes.c_uint8),
        ("bInterfaceClass", ctypes.c_uint8),
        ("bInterfaceSubClass", ctypes.c_uint8),
        ("bInterfaceProtocol", ctypes.c_uint8),
        ("iInterface", ctypes.c_uint8),
        ("endpoint", LibUsbEndpointDescriptorPtr),
        ("extra", ctypes.POINTER(ctypes.c_ubyte)),
        ("extra_length", ctypes.c_int)
    ]


LibUsbInterfaceDescriptorPtr = ctypes.POINTER(LibUsbInterfaceDescriptor)


class LibUsbInterface(ctypes.Structure):
    """A libusb interface."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = [
        ("altsetting", LibUsbInterfaceDescriptorPtr),
        ("num_altsetting", ctypes.c_int)
    ]


LibUsbInterfacePtr = ctypes.POINTER(LibUsbInterface)


class LibUsbConfigDescriptor(ctypes.Structure):
    """A libusb configuration descriptor."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = [
        ("bLength", ctypes.c_uint8),
        ("bDescriptorType", ctypes.c_uint8),
        ("wTotalLength", ctypes.c_uint16),
        ("bNumInterfaces", ctypes.c_uint8),
        ("bConfigurationValue", ctypes.c_uint8),
        ("iConfiguration", ctypes.c_uint8),
        ("bmAttributes", ctypes.c_uint8),
        ("MaxPower", ctypes.c_uint8),
        ("interface", LibUsbInterfacePtr),
        ("extra", ctypes.POINTER(ctypes.c_ubyte)),
        ("extra_length", ctypes.c_int)
    ]


LibUsbConfigDescriptorPtr = ctypes.POINTER(LibUsbConfigDescriptor)


class LibUsbDeviceDescriptor(ctypes.Structure):
    """A libusb device descriptor."""
    _pack_ = C_STRUCT_ALIGNMENT
    _fields_ = [
        ("bLength", ctypes.c_uint8),
        ("bDescriptorType", ctypes.c_uint8),
        ("bcdUSB", ctypes.c_uint16),
        ("bDeviceClass", ctypes.c_uint8),
        ("bDeviceSubClass", ctypes.c_uint8),
        ("bDeviceProtocol", ctypes.c_uint8),
        ("bMaxPacketSize0", ctypes.c_uint8),
        ("idVendor", ctypes.c_uint16),
        ("idProduct", ctypes.c_uint16),
        ("bcdDevice", ctypes.c_uint16),
        ("iManufacturer", ctypes.c_uint8),
        ("iProduct", ctypes.c_uint8),
        ("iSerialNumber", ctypes.c_uint8),
        ("bNumConfigurations", ctypes.c_uint8)
    ]


LibUsbDeviceDescriptorPtr = ctypes.POINTER(LibUsbDeviceDescriptor)


class LibUsbLibraryError(Exception):
    """Base class for errors reported by the LibUsbLibrary methods."""


class LibUsbLibraryFunctionCallError(LibUsbLibraryError):
    """An error was reported by a libusb function."""
    def __init__(self, error_code: int, error_message: str):
        self.error_code = error_code
        self.error_message = error_message


class LibUsbLibraryMiscellaneousError(LibUsbLibraryError):
    """Any error in a LibUsbLibrary method that is not reported by a function call the libusb library."""
    def __init__(self, message: str):
        self.message = message


class LibUsbLibrary:
    """This class encapsulates a dynamically loaded libusb instance."""

    def __init__(self, filename: str):

        if sys.platform == "win32":
            # The Windows version of libusb uses the 'stdcall' calling convention.
            lib = ctypes.WinDLL(filename)
        else:
            lib = ctypes.CDLL(filename)

        # Annotate the library functions.
        LibUsbLibrary._annotate_library_functions(lib)

        self._lib = lib

    @staticmethod
    def _annotate_library_functions(lib):
        """Add ctype-compliant type annotations to the libusb functions we'll be using."""

        lib.libusb_init.argtypes = [ctypes.POINTER(LibUsbContextPtr)]
        lib.libusb_init.restype = ctypes.c_int

        lib.libusb_exit.argtypes = [LibUsbContextPtr]
        lib.libusb_exit.restype = None

        lib.libusb_get_device_list.argtypes = [LibUsbContextPtr, ctypes.POINTER(ctypes.POINTER(LibUsbDevicePtr))]
        lib.libusb_get_device_list.restype = ctypes.c_ssize_t

        lib.libusb_free_device_list.argtypes = [ctypes.POINTER(LibUsbDevicePtr), ctypes.c_int]
        lib.libusb_free_device_list.restype = None

        lib.libusb_get_device_descriptor.argtypes = [LibUsbDevicePtr, LibUsbDeviceDescriptorPtr]
        lib.libusb_get_device_descriptor.restype = ctypes.c_int

        lib.libusb_get_config_descriptor.argtypes = [LibUsbDevicePtr, ctypes.c_uint8,
                                                     ctypes.POINTER(LibUsbConfigDescriptorPtr)]
        lib.libusb_get_config_descriptor.restype = ctypes.c_int

        lib.libusb_free_config_descriptor.argtypes = [LibUsbConfigDescriptorPtr]
        lib.libusb_free_config_descriptor.restype = None

        lib.libusb_open.argtypes = [LibUsbDevicePtr, ctypes.POINTER(LibUsbDeviceHandlePtr)]
        lib.libusb_open.restype = ctypes.c_int

        lib.libusb_close.argtypes = [LibUsbDeviceHandlePtr]
        lib.libusb_close.restype = None

        lib.libusb_control_transfer.argtypes = [
            LibUsbDeviceHandlePtr, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint16, ctypes.c_uint]
        lib.libusb_control_transfer.restype = ctypes.c_int

        lib.libusb_bulk_transfer.argtypes = [
            LibUsbDeviceHandlePtr, ctypes.c_ubyte, ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
        lib.libusb_bulk_transfer.restype = ctypes.c_int

        lib.libusb_error_name.argtypes = [ctypes.c_int]
        lib.libusb_error_name.restype = ctypes.c_char_p

        lib.libusb_get_device.argtypes = [LibUsbDeviceHandlePtr]
        lib.libusb_get_device.restype = LibUsbDevicePtr

        lib.libusb_claim_interface.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_claim_interface.restype = ctypes.c_int

        lib.libusb_release_interface.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_release_interface.restype = ctypes.c_int

        lib.libusb_clear_halt.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_ubyte]
        lib.libusb_clear_halt.restype = ctypes.c_int

        lib.libusb_get_configuration.argtypes = [LibUsbDeviceHandlePtr, ctypes.POINTER(ctypes.c_int)]
        lib.libusb_get_configuration.restype = ctypes.c_int

        lib.libusb_set_configuration.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_set_configuration.restype = ctypes.c_int

        lib.libusb_kernel_driver_active.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_kernel_driver_active.restype = ctypes.c_int

        lib.libusb_detach_kernel_driver.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_detach_kernel_driver.restype = ctypes.c_int

        lib.libusb_attach_kernel_driver.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_attach_kernel_driver.restype = ctypes.c_int

        lib.libusb_set_auto_detach_kernel_driver.argtypes = [LibUsbDeviceHandlePtr, ctypes.c_int]
        lib.libusb_set_auto_detach_kernel_driver.restype = ctypes.c_int

    def _libusb_exception(self, error_code: int) -> LibUsbLibraryFunctionCallError:
        """Look up the description of the error and return a LibUsbError exception."""
        error_message = self.get_error_name(error_code)
        return LibUsbLibraryFunctionCallError(error_code, error_message)

    def init(self) -> LibUsbContextPtr:
        """Initialize a libusb context."""
        ctx = LibUsbContextPtr()
        result = self._lib.libusb_init(ctx)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)
        return ctx

    def exit(self, ctx: LibUsbContextPtr) -> None:
        """Discard a libusb context."""
        self._lib.libusb_exit(ctx)

    def get_device_descriptor(self, device: LibUsbDevicePtr) -> LibUsbDeviceDescriptor:
        """Get a USB device descriptor."""
        device_descriptor = LibUsbDeviceDescriptor()

        result = self._lib.libusb_get_device_descriptor(device, device_descriptor)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

        return device_descriptor

    def get_config_descriptor(self, device: LibUsbDevicePtr, config_index: int) -> LibUsbConfigDescriptorPtr:
        """Get a configuration descriptor.

        Note: the configuration descriptor should at some point be freed by calling `free_config_descriptor`.
        """
        config_descriptor = LibUsbConfigDescriptorPtr()

        result = self._lib.libusb_get_config_descriptor(device, config_index, config_descriptor)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

        return config_descriptor

    def free_config_descriptor(self, config_descriptor: LibUsbConfigDescriptorPtr) -> None:
        """Free a configuration descriptor."""
        self._lib.libusb_free_config_descriptor(config_descriptor)

    def get_device(self, device_handle: LibUsbDeviceHandlePtr) -> LibUsbDevicePtr:
        """Get a Device from a Device Handle."""
        return self._lib.libusb_get_device(device_handle)

    def get_error_name(self, error_code: int) -> str:
        """Find the error name associated with the given error code."""
        result = self._lib.libusb_error_name(error_code)
        return result.decode('ascii')

    def control_transfer(self, device_handle: LibUsbDeviceHandlePtr, request_type: int, request: int, value: int,
                         index: int, length: int, timeout: int) -> bytes:
        """Execute a control request and return the response."""
        data = ctypes.create_string_buffer(length)

        result = self._lib.libusb_control_transfer(
            device_handle,
            request_type,  # mwRequestType
            request,       # bRequest
            value,         # wValue
            index,         # wIndex
            ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte)),
            length,        # wLength
            timeout
        )
        if result < 0:
            raise self._libusb_exception(result)

        # Return a bytes instance.
        return bytes(data[:result])

    def bulk_transfer_out(self, device_handle: LibUsbDeviceHandlePtr, endpoint: int, data: bytes, timeout: int) -> None:
        """Execute a bulk-out transfer."""
        transferred = ctypes.c_int()
        result = self._lib.libusb_bulk_transfer(
            device_handle, endpoint, ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte)), len(data), transferred, timeout)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

        if transferred.value != len(data):
            raise LibUsbLibraryMiscellaneousError("Expected the value of transferred to be equal to the number of bytes received.")

    def bulk_transfer_in(self, device_handle: LibUsbDeviceHandlePtr, endpoint: int, maxsize: int, timeout: int) -> bytes:
        """Execute a bulk-in transfer."""

        data = ctypes.create_string_buffer(maxsize)

        transferred = ctypes.c_int()

        result = self._lib.libusb_bulk_transfer(
            device_handle, endpoint, ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte)), maxsize, transferred, timeout)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

        return data[:transferred.value]

    def get_string_descriptor_languages(self, device_handle: LibUsbDeviceHandlePtr, timeout: int) -> list[int]:
        """Request languages supported by the device as LANGID values.

        These are stored in the special string descriptor 0.
        """
        maxsize = 256
        descriptor_index = 0
        response = self.control_transfer(
            device_handle,
            LIBUSB_ENDPOINT_IN,
            LIBUSB_REQUEST_GET_DESCRIPTOR,
            (LIBUSB_DT_STRING << 8) | descriptor_index,
            0,
            maxsize,
            timeout
        )

        if len(response) < 2:
            raise LibUsbLibraryMiscellaneousError("Response too short.")

        if response[0] != len(response):
            raise LibUsbLibraryMiscellaneousError("Bad response length.")

        if response[1] != LIBUSB_DT_STRING:
            raise LibUsbLibraryMiscellaneousError("Bad descriptor type.")

        if len(response) % 2 != 0:
            raise LibUsbLibraryMiscellaneousError("Response length not even.")

        num_languages = (len(response) - 2) // 2

        languages = [response[2 * k + 2] + response[2 * k + 3] * 256 for k in range(num_languages)]

        return languages

    def get_string_descriptor(self, device_handle: LibUsbDeviceHandlePtr, descriptor_index: int, timeout: int, langid: int) -> Optional[str]:
        """Get a string descriptor value from a device."""

        # String descriptor 0 contains LANGID information. The string descriptor value 0 is
        # used to indicate absense of a string descriptor, hence we return None.
        if descriptor_index == 0:
            return None

        maxsize = 256
        response = self.control_transfer(
            device_handle,
            LIBUSB_ENDPOINT_IN,
            LIBUSB_REQUEST_GET_DESCRIPTOR,
            (LIBUSB_DT_STRING << 8) | descriptor_index,
            langid,
            maxsize,
            timeout
        )

        if response[0] != len(response):
            raise LibUsbLibraryMiscellaneousError("Expected first byte to be equal to the length of the response.")

        if response[1] != LIBUSB_DT_STRING:
            raise LibUsbLibraryMiscellaneousError("Expected string descriptor.")

        return response[2:].decode('utf_16_le')

    def open(self, device: LibUsbDevicePtr) -> LibUsbDeviceHandlePtr:
        """Open the libusb device, yielding a device handle that we can use for I/O.

        This operation increments the libusb-level reference count of the device.
        """
        device_handle = LibUsbDeviceHandlePtr()
        result = self._lib.libusb_open(device, device_handle)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)
        return device_handle

    def close(self, device_handle: LibUsbDeviceHandlePtr) -> None:
        """Close the libusb device, making it unavailable for I/O.

        This operation decrements the libusb-level reference count of the device.
        """
        self._lib.libusb_close(device_handle)

    def claim_interface(self, device_handle: LibUsbDeviceHandlePtr, interface_number: int) -> None:
        """Let the OS know we want to take exclusive control of the interface."""
        result = self._lib.libusb_claim_interface(device_handle, interface_number)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

    def release_interface(self, device_handle: LibUsbDeviceHandlePtr, interface_number: int) -> None:
        """Let the OS know we want to drop exclusive control of the interface."""
        result = self._lib.libusb_release_interface(device_handle, interface_number)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

    def clear_halt(self, device_handle: LibUsbDeviceHandlePtr, endpoint: int) -> None:
        """Clear the Halt condition on the given endpoint."""
        result = self._lib.libusb_clear_halt(device_handle, endpoint)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

    def get_configuration(self, device_handle: LibUsbDeviceHandlePtr) -> int:
        """Get device configuration."""
        c_configuration = ctypes.c_int()
        result = self._lib.libusb_get_configuration(device_handle, c_configuration)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)
        configuration = c_configuration.value
        return configuration

    def set_configuration(self, device_handle: LibUsbDeviceHandlePtr, configuration: int) -> None:
        """Set device configuration."""
        result = self._lib.libusb_set_configuration(device_handle, configuration)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

    def kernel_driver_active(self, device_handle: LibUsbDeviceHandlePtr, interface_number: int) -> bool:
        """Determine if a kernel driver is active on an interface. """
        result = self._lib.libusb_kernel_driver_active(device_handle, interface_number)
        if result == LIBUSB_ERROR_NOT_SUPPORTED:
            # In operating systems where the "kernel driver active" concept does not exist,
            # report False.
            return False
        if result < 0:
            raise self._libusb_exception(result)
        return bool(result)

    def detach_kernel_driver(self, device_handle: LibUsbDeviceHandlePtr, interface_number: int) -> None:
        """CDetach a kernel driver from an interface."""
        result = self._lib.libusb_detach_kernel_driver(device_handle, interface_number)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

    def attach_kernel_driver(self, device_handle: LibUsbDeviceHandlePtr, interface_number: int) -> None:
        """Re-attach an interface's kernel driver."""
        result = self._lib.libusb_attach_kernel_driver(device_handle, interface_number)
        if result != LIBUSB_SUCCESS:
            raise self._libusb_exception(result)

    def set_auto_detach_kernel_driver(self, device_handle: LibUsbDeviceHandlePtr, enable: bool) -> None:
        """Enable/disable automatic kernel driver detachment by libusb."""
        result = self._lib.libusb_set_auto_detach_kernel_driver(device_handle, enable)
        if result not in (LIBUSB_SUCCESS, LIBUSB_ERROR_NOT_SUPPORTED):
            raise self._libusb_exception(result)

    def find_and_open_device(self, ctx: LibUsbContextPtr, vid: int, pid: int,
                             serial: Optional[str], timeout: int, langid: int) -> Optional[LibUsbDeviceHandlePtr]:
        """Enumerate USB devices and open the first one that matches the given parameters.

        A device matches the parameters if the following conditions are all true:

        (1) The Vendor and Product ID of the device match the values given in the parameters.

        (2) The device can actually be opened (i.e., that is allowed by permissions).

        (3) Either the `serial` parameter is None, or, it precisely matches the serial number as
            read from the device.

        The enumeration and selection process is rather elaborate and does not reflect a basic operation provided
        by the libusb library.

        The reason we still implement it as a method of the LibUsbLibrary class is because of the way libusb
        organizes the management of a device list. It is initialized as an array of devices and represented by
        a pointer to its first element. When done with the list, a client must free the device list by passing
        that pointer back to libusb.

        This way of memory management means that there is no clean way to represent a device list in Python,
        since simply copying the devices to a list would lose the pointer that we need to discard the device
        list using libusb.

        One way to deal with this would be to discard the device list and to rely on the reference counting
        memory management in the libusb-level devices. However, getting this to work correctly and reliably
        with the garbage collection at the Python level is quite complex.

        For this reason, we opted to combine the device enumeration and device opening functionality in this
        single function. It's not super elegant, but it works reliably.
        """

        device_list = ctypes.POINTER(LibUsbDevicePtr)()

        result = self._lib.libusb_get_device_list(ctx, device_list)
        if result < 0:
            raise self._libusb_exception(result)

        device_count = result

        device_handle = None

        for device_index in range(device_count):
            device = device_list[device_index]

            device_descriptor = self.get_device_descriptor(device)

            # print(f"Located device:  {device_descriptor.idVendor:04x}:{device_descriptor.idProduct:04x}")

            if (device_descriptor.idVendor != vid) or (device_descriptor.idProduct != pid):
                # VID or PID mismatch -- reject.
                continue

            try:
                device_handle = self.open(device)
            except LibUsbLibraryFunctionCallError:
                # Cannot open the device -- reject.
                continue

            if serial is None:
                # No check on the serial number was requested. Accept the device.
                break

            if device_descriptor.iSerialNumber == 0:
                # A serial number check was requested, but the device doesn't have one. Close device, reject.
                self.close(device_handle)
                device_handle = None
                continue

            try:
                serial_from_device = self.get_string_descriptor(device_handle, device_descriptor.iSerialNumber, timeout, langid)
            except LibUsbLibraryFunctionCallError:
                # Error while retrieving the serial number. Close device, reject.
                self.close(device_handle)
                device_handle = None
                continue

            if serial != serial_from_device:
                # Serial number mismatch. Close device, reject.
                self.close(device_handle)
                device_handle = None
                continue

        # Discard the list of devices and decrement their reference counts.
        # This will bring all reference counts to zero, except for the currently opened device (if any).
        self._lib.libusb_free_device_list(device_list, 1)

        return device_handle
