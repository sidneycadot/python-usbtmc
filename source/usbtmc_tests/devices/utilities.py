
from io import BytesIO
import os
import sys

import usbtmc
from usbtmc import UsbTmcInterface


def initialize_libusb_library_path_environment_variable() -> bool:
    """Initialize the LIBUSB_LIBRARY_PATH environment variable, if needed.

    In Windows, we need to tell usbtmc where the libusb-1.0 DLL can be found. This is done by
    pointing the LIBUSB_LIBRARY_PATH environment variable to the libusb-1.0 DLL.

    If the LIBUSB_LIBRARY_PATH variable is already set, or on non-Windows platforms, this function is a no-op.
    """

    if ("LIBUSB_LIBRARY_PATH" in os.environ) or (sys.platform != "win32"):
        return False

    filename = os.path.abspath(os.path.join(os.path.dirname(usbtmc.__file__), "../../windows/libusb-1.0.dll"))
    if not os.path.exists(filename):
        raise RuntimeError(f"Cannot find the libusb-1.0 library at '{filename}'. Please make sure it's available.")

    os.environ["LIBUSB_LIBRARY_PATH"] = filename

    return True


def parse_definite_length_binary_block(data: bytes) -> bytes:
    """Parse an SCPI Definite Length Binary Block (DLBB)."""
    fi = BytesIO(data)
    header = fi.read(2)
    if len(header) != 2:
        raise ValueError()
    if not header.startswith(b'#'):
        raise ValueError()
    num_size_digits = int(header[1:2])
    if len(data) < 2 + num_size_digits:
        raise ValueError()
    size_digits = fi.read(num_size_digits)
    if len(size_digits) != num_size_digits:
        raise ValueError()
    size = int(size_digits)

    expected_size = 2 + num_size_digits + size
    if len(data) != expected_size:
        raise ValueError()

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
