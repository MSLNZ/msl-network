=============
Release Notes
=============

Version 0.2.0 (2018.08.24)
==========================

- Added

  * a ``wakeup()`` Task in debug mode on Windows (see: https://bugs.python.org/issue23057)
  * the ``version_info`` named tuple now includes a *releaselevel*
  * example for creating a Client and a Service in LabVIEW
  * the ability to establish a connection to the Network Manager without using TLS
  * a ``timeout`` kwarg to Service.start()
  * an Echo Service to the examples

- Changed

  * rename 'async' kwarg to be 'asynchronous' (for Python 3.7 support) in Client.send_request()
  * the termination bytes were changed from ``\n`` to ``\r\n``

Version 0.1.0 (2017.12.14)
==========================
- Initial release
