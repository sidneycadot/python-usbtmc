"""USBTMC interface device behaviors for a menagerie of different devices.

It is an unfortunate fact of life that many (perhaps most) devices that implement USBTMC support do not fully
follow the USBTMC standard.

This module defines device behaviors for different devices, as well as a default behavior that corresponds
to a fully compliant USBTMC device.
"""

from enum import Flag
from typing import NamedTuple


class ResetAtOpenPolicyFlag(Flag):
    """Right after opening the device, we may want to reset the interface."""
    NO_OPERATION      = 0  # Don't reset after opening the interface.
    SET_CONFIGURATION = 1  # Reset using a "set configuration" request.
    CLEAR_INTERFACE   = 2  # Reset using a "clear interface" request. This is the default.
    GOTO_REMOTE       = 4  # Perform a GOTO_REMOTE


class UsbTmcInterfaceBehavior(NamedTuple):
    """USBTMC interface behaviors and quirks."""
    # In-spec behaviors.
    max_bulk_in_transfer_size = 16384
    max_bulk_out_transfer_size = 16384
    # Out-of-spec behaviors (a.k.a. quirks).
    reset_at_open_policy: ResetAtOpenPolicyFlag = ResetAtOpenPolicyFlag.CLEAR_INTERFACE
    clear_usbtmc_interface_disabled: bool = False
    clear_usbtmc_interface_short_packet_read_request_disabled: bool = False
    clear_usbtmc_interface_resets_bulk_in: bool = False
    remove_bulk_padding_bytes: bool = False
    strip_trailing_string_nul_characters: bool = False
    bad_bulk_in_transfer_size: bool = False


def get_usbtmc_interface_behavior(vid: int, pid: int) -> UsbTmcInterfaceBehavior:
    """Generate a UsbTmcInterfaceBehavior instance from a (Vendor ID, Product ID) tuple.

    Unknown devices will return the UsbTmcInterfaceBehavior corresponding to a fully compliant
    USBTMC device, which is probably optimistic.
    """
    match (vid, pid):
        case (0x1313, 0x8076):  # Thorlabs PM101U powermeter.
            return UsbTmcInterfaceBehavior(
                reset_at_open_policy=ResetAtOpenPolicyFlag.CLEAR_INTERFACE,
                clear_usbtmc_interface_short_packet_read_request_disabled=True,
                clear_usbtmc_interface_resets_bulk_in=True
            )
        case (0x1313, 0x8078):  # Thorlabs PM100D powermeter.
            return UsbTmcInterfaceBehavior(
                reset_at_open_policy=ResetAtOpenPolicyFlag.CLEAR_INTERFACE,
                clear_usbtmc_interface_resets_bulk_in=True
            )
        case (0x1ab1, 0x0588):  # Rigol DS1102D oscilloscope.
            return UsbTmcInterfaceBehavior(
                strip_trailing_string_nul_characters=True
            )
        case (0xf4ec, 0xee38):  # Siglent SDS1204X-E oscilloscope.
            return UsbTmcInterfaceBehavior(
                clear_usbtmc_interface_disabled=True,
                remove_bulk_padding_bytes=True,
                bad_bulk_in_transfer_size=True
            )
        case _:  # Nominal USBTMC interface behavior.
            return UsbTmcInterfaceBehavior()
