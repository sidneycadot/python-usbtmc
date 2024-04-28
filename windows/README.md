Getting libusb for Microsoft Windows
------------------------------------

The Windows version of libusb-1.0 can be downloaded from https://libusb.info/. Go to the "Downloads" section,
and click "Latest Windows Binaries". This will download a compressed file containing no less than 12 (!)
versions of the libusb v1.0 DLL: compiled by six different compilers, for both 32-bits and 64-bits targets.

We'll be using the 64-bit version compiled with MinGW64:

* filename: mingw_libusb-1.0.dll
* file size: 228945 bytes
* md5sum: 37360951c9ecea62d4c5e2a094127aca

Telling python-usbtmc about the file location
---------------------------------------------

The python-usbtmc package depends on ctypes to load the file "libusb-1.0.dll" as a shared library.
To be able to do that, we need to tell python-usbtmc module where that file is.

Use the environment variable LIBUSB_LIBRARY_PATH for that.
