.. _network-install:

Install MSL-Network
===================

To install **MSL-Network** run:

.. code-block:: console

   pip install msl-network

Alternatively, using the `MSL Package Manager`_ run:

.. code-block:: console

   msl install network

Compatibility
-------------
**MSL-Network** uses coroutines with the ``async`` and ``await`` syntax that were added in
Python 3.5 (PEP492_). Therefore, the Network :class:`~msl.network.manager.Manager` class is
only compatible with Python 3.5+.

The :class:`~msl.network.client.Client` and :class:`~msl.network.service.Service` classes can be
implemented in any programming language (and also in previous versions of Python). See the
:ref:`json-formats` section for how the Network :class:`~msl.network.manager.Manager` exchanges
information between a :class:`~msl.network.client.Client` and a :class:`~msl.network.service.Service`.

Dependencies
------------
* Python 3.5+
* cryptography_
* paramiko_

Optional packages that can be used for (de)serializing JSON_ data:

* UltraJSON_ (see `this link <https://www.lfd.uci.edu/~gohlke/pythonlibs/#ujson>`_ for a pre-built wheel for Windows)
* RapidJSON_
* simplejson_
* yajl_

To use one of these external JSON_ packages, rather than Python's builtin :mod:`json` module, you must
specify a ``MSL_NETWORK_JSON`` environment variable. See
`here <https://msl-network.readthedocs.io/en/latest/_api/msl.network.constants.html#msl.network.constants.JSON>`_
for more details.

.. _MSL Package Manager: https://msl-package-manager.readthedocs.io/en/latest/
.. _PEP492: https://www.python.org/dev/peps/pep-0492/
.. _PEP498: https://www.python.org/dev/peps/pep-0498/
.. _cryptography: https://cryptography.io/en/latest/
.. _JSON: https://www.json.org/
.. _UltraJSON: https://pypi.python.org/pypi/ujson
.. _RapidJSON: https://pypi.python.org/pypi/python-rapidjson
.. _simplejson: https://pypi.python.org/pypi/simplejson/
.. _yajl: https://pypi.python.org/pypi/yajl
.. _paramiko: http://www.paramiko.org/
