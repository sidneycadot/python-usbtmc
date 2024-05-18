"""The usbtmc package provides a cross-platform user-space driver for USBTMC-capable devices.

This package implements the USBTMC protocol and the USBTMC-USB488 sub-protocol as described in [1] and [2].

The API presented does not support protocol features that are not very useful in most use-cases. Specifically:

* For Bulk I/O, only device-dependent messages are supported. Support for vendor-specific messages is not implemented.
* For Bulk I/O, the "TermChar" feature is not supported. This feature allows the Host to request a specific termination
  character to end responses from the Device.
* Functionality related to the Interrupt-IN endpoint is not supported.
* The ABORT_BULK_OUT and ABORT_BULK_IN control sequences are not supported. (The INITIATE_CLEAR / CHECK_CLEAR_STATUS sequence is, though).

[1] Universal Serial Bus Test and Measurement Class Specification (USBTMC), Revision 1.0, April 14, 2003
[2] Universal Serial Bus Test and Measurement Class, Subclass USB488 Specification (USBTMC-USB488), Revision 1.0, April 14, 2003

[1] and [2] can be downloaded from here: https://www.usb.org/sites/default/files/USBTMC_1_006a.zip.

The functionality of this package is implemented in the UsbTmcInterface class, which we import here to
make it available for import directly from the usbtmc package.
"""

from .usbtmc_interface import UsbTmcInterface
