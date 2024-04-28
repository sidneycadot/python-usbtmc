python-usbtmc
==============

This is python-usbtmc, a user-space driver for USBTMC devices in Python.

What is USBTMC?
---------------

USBTMC is a protocol specification for controlling test- and measurement equipment over
USB. It is a so-called "USB class", and its specification was written, and is currently maintained,
by the USB Implementers Forum (USB-IF).

Applicable documents
--------------------

[1] USB 2.0 specification
[2] USBTMC_1_00.pdf (40 pages)
[3] USBTMC_usb488_subclass_1_00.pdf (30 pages)
[4] SCPI specification
[5] IEC 60488.1 specification
[6] IEC 60488.2 specification

Documents [2] and [3] can be downloaded from https://www.usb.org/sites/default/files/USBTMC_1_006a.zip.

How does python-usbtmc work?
----------------------------

Written in Python.

Depends on the libusb-1.0 library. 

Getting it to work in Microsoft Windows
---------------------------------------

* Libusb dependency
* WinUSB
* Registering a driver for your device. The "Zadig" software.

Device quirks
-------------

Supporting USBTMC on test- and measurement devices turns out to be not quite trivial.
Many devices out there claim to support USBTMC, but often they show behavior that is
not in compliance with the specification.

This is especially true for lower-cost brands, but unfortunately even high-end devices
often shows such non-standard behavior.

This is true to an extent that I would recommend not using USBTMC if you can avoid it.
If your device supports Ethernet, and you just want to control it using SCPI commands,
you're usually much better off just opening a TCP socket to port 5025 (the standard
TCP port most modern lab devices implement for SCPI access) and use that.

However, some devices don't have an Ethernet port; and on some devices the USBTMC
performance  is better than what can be achieved over TCP. As an example, I have a
Keysight 33622A  waveform generator that I can upload arbitrary waveforms to. Using
USBTMC I can do that  with a pretty dismal data rate of about 1.8 MB/s, but using
Ethernet is even worse, at 1.0 MB/sec.
 
We will try to document and handle device quirks in the library.
