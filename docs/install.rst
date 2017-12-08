.. _install:

Install MSL-Network
===================

To install **MSL-Network** run::

   pip install https://github.com/MSLNZ/msl-network/archive/master.zip

Alternatively, using the `MSL Package Manager`_ run::

   msl install network

Compatibility
-------------
**MSL-Network** uses coroutines with the ``async`` and ``await`` syntax that were added in
Python 3.5 (PEP492_) and the *f-string* syntax for literal string interpolation that was added
in Python 3.6 (PEP498_). Therefore **MSL-Network** is only compatible with Python versions >= 3.6.

Dependencies
------------
* Python 3.6+
* cryptography_

Optional packages that can be used for (de)serializing JSON_ data:

* UltraJSON_ (see here_ for a pre-built wheel for Windows)
* RapidJSON_
* simplejson_
* yajl_

.. _MSL Package Manager: http://msl-package-manager.readthedocs.io/en/latest/?badge=latest
.. _PEP492: https://www.python.org/dev/peps/pep-0492/
.. _PEP498: https://www.python.org/dev/peps/pep-0498/
.. _cryptography: https://pypi.python.org/pypi/cryptography
.. _JSON: http://www.json.org/
.. _UltraJSON: https://pypi.python.org/pypi/ujson
.. _here: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ujson
.. _RapidJSON: https://pypi.python.org/pypi/python-rapidjson
.. _simplejson: https://pypi.python.org/pypi/simplejson/
.. _yajl: https://pypi.python.org/pypi/yajl
