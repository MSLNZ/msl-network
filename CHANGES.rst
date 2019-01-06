=============
Release Notes
=============

Version 0.3.1.dev0
==================

Version 0.3.0 (2019.01.06)
==========================

- Added

  * every request from a `Client` can now specify a timeout value
  * the docs now include an example for how to send requests to the ``Echo`` `Service`

- Changed

  * the default `timeout` value for connecting to the `Manager` is now 10 seconds
  * the `__repr__` method for a `Client` no longer includes the id as a hex number

- Fixed

  * issue `#5 <https://github.com/MSLNZ/msl-network/issues/5>`_
  * issue `#4 <https://github.com/MSLNZ/msl-network/issues/4>`_
  * issue `#3 <https://github.com/MSLNZ/msl-network/issues/3>`_
  * issue `#2 <https://github.com/MSLNZ/msl-network/issues/2>`_
  * issue `#1 <https://github.com/MSLNZ/msl-network/issues/1>`_

- Removed

  * the `__repr__` method for a `Service`

Version 0.2.0 (2018.08.24)
==========================

- Added

  * a ``wakeup()`` Task in debug mode on Windows (see: https://bugs.python.org/issue23057)
  * the ``version_info`` named tuple now includes a *releaselevel*
  * example for creating a `Client` and a `Service` in LabVIEW
  * the ability to establish a connection to the Network `Manager` without using TLS
  * a ``timeout`` kwarg to `Service.start()`
  * an ``Echo`` `Service` to the examples

- Changed

  * rename 'async' kwarg to be 'asynchronous' (for Python 3.7 support)
  * the termination bytes were changed from ``\n`` to ``\r\n``

Version 0.1.0 (2017.12.14)
==========================
- Initial release
