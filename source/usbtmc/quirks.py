"""A menagerie of USBTMC interface quirks of different devices."""

from typing import NamedTuple


class UsbTmcInterfaceQuirks(NamedTuple):
    """Interface quirks and behaviors."""
    open_reset_method: int = 1  # 0==no reset; 1 == USBTMC clear request after open.
    usbtmc_clear_sequence_resets_bulk_in: bool = False
    clear_usbtmc_interface_disabled: bool = False
    remove_bulk_padding_bytes: bool = False


def get_usbtmc_interface_quirks(vid: int, pid: int) -> UsbTmcInterfaceQuirks:
    match (vid, pid):
        case (0x1313, 0x8078):
            """Thorlabs PM100D powermeter."""
            return UsbTmcInterfaceQuirks(
                usbtmc_clear_sequence_resets_bulk_in=True
            )
        case (0xf4ec, 0xee38):
            """Siglent SDS1204X-E oscilloscope."""
            return UsbTmcInterfaceQuirks(
                open_reset_method=0,
                clear_usbtmc_interface_disabled=True,
                remove_bulk_padding_bytes=True
            )
        case _:
            """Nominal USBTMC interface behavior."""
            return UsbTmcInterfaceQuirks()
