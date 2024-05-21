"""USBTMC interface device behaviors for a menagerie of different devices.

This module defines device behaviors for a different devices, as well as a generic behavior that a compliant
USBTMC device should be able to handle.

It is an unfortunate fact of life that many (perhaps most) devices that implement USBTMC support do not fully
follow the USB standard.

In this module we make accommodations for that fact by listing quirks for devices that we have come across. Ou
host-side implementation of USBTMC can use the behaviors and quirks to adapt its behavior.
"""

from typing import NamedTuple


class UsbTmcInterfaceBehavior(NamedTuple):
    """USBTMC interface behaviors and quirks."""
    # In-spec behaviors.
    max_bulk_in_transfer_size = 16384
    max_bulk_out_transfer_size = 16384
    # Out-of-spec behaviors (a.k.a. quirks).
    open_reset_method: int = 1  # 0==no reset; 1 == USBTMC clear request after open.
    usbtmc_clear_sequence_resets_bulk_in: bool = False
    clear_usbtmc_interface_disabled: bool = False
    remove_bulk_padding_bytes: bool = False
    strip_trailing_string_nul_characters: bool = False
    bad_bulk_in_transfer_size: bool = False


def get_usbtmc_interface_behavior(vid: int, pid: int) -> UsbTmcInterfaceBehavior:
    """Map a (Vendor ID, Product ID) tuple to a UsbTmcInterfaceBehavior instance."""
    match (vid, pid):
        case (0x1313, 0x8078):  # Thorlabs PM100D powermeter.
            return UsbTmcInterfaceBehavior(
                usbtmc_clear_sequence_resets_bulk_in=True
            )
        case (0xf4ec, 0xee38):  # Siglent SDS1204X-E oscilloscope.
            return UsbTmcInterfaceBehavior(
                open_reset_method=0,
                clear_usbtmc_interface_disabled=True,
                remove_bulk_padding_bytes=True,
                bad_bulk_in_transfer_size=True
            )
        case (0x1ab1, 0x0588):  # Rigol DS1102D oscilloscope.
            return UsbTmcInterfaceBehavior(
                strip_trailing_string_nul_characters=True
            )
        case _:  # Nominal USBTMC interface behavior.
            return UsbTmcInterfaceBehavior()
