python-usbtmc
==============

This is python-usbtmc, a user-space Python module that uses *libusb* to communicate with
USBTMC-capable devices. It works in Linux, MacOS, and Windows.

It aims to be an improvement relative to the older USBTMC support implemented as part of
the Python-IVI project, as found here:

    https://github.com/python-ivi/python-usbtmc

This older module has several shortcomings, the most important one being that it seems
to be no longer actively maintained. Other than that, it has been very useful to us,
both in the lab (with a few patches here and there), and as a reference while developing
our own usbtmc driver.

What is USBTMC?
---------------

USBTMC is a protocol specification for controlling test- and measurement equipment over
USB. It is a so-called "USB class". Its specification can can be found at the USB
Implementers Forum (USB-IF).

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

Depends on the libusb-1.0 library to perform control- and bulk USB transfers as defined by the USBTMC standard.

Getting it to work in Microsoft Windows
---------------------------------------

In Windows things are more complicated than they could be.

* Libusb dependency
* WinUSB
* Registering a driver for your device. Use the "Zadig" program to bind your device to the WinUSB driver.

Device quirks
-------------

Supporting USBTMC on test- and measurement devices turns out to be not quite trivial.
Many devices out there claim to support USBTMC, but often they show behavior that is
not in full compliance with the specification.

This is especially true for lower-cost brands, but unfortunately even high-end devices
often shows such non-standard behavior.

This is unfortunately true to an extent that I would recommend not using USBTMC if
you can avoid it.  If your device supports Ethernet, and you just want to control
it using SCPI commands,  you're usually much better off just opening a TCP socket
to port 5025 (the standard  TCP port most modern lab devices implement for SCPI
access) and use that.

However, some devices don't have an Ethernet port; and on some devices the USBTMC
performance is (surprisingly) better than what can be achieved over TCP. As an
example, I have a  Keysight 33622A  waveform generator that I can upload arbitrary
waveforms to. Using USBTMC I can do that at a pretty dismal data rate of about
1.8 MB/s, but using Ethernet is somehow even worse, at 1.0 MB/sec.

Anyway, about those quirks:

This package was tested against any USBTMC devices that I could get my hands on;
see the example programs under source/usbtmc_tests/devices/ for the current list.

In the process, I uncovered a bunch of quirky behaviors where devices don't follow
the standard to the letter.

Wherever possible, I have tried to come up with a more-or-less generic workaround
for the quirky behavior, which overrides the default behavior. The known behavioral
quirks are collected, for each type of device, in the "usbtmc_interface_behavior.py"
source file. Whenever a device is opened this 'quirks database' is probed to find
a corresponding set of behavior hacks. This mechanism allows us to work around
many quirks. Unfortunately, this only works for devices I have been able to test.
