.. _network-install:

Install MSL-Network
===================

To install MSL-Network run:

.. code-block:: console

   pip install msl-network

Alternatively, using the `MSL Package Manager`_ run:

.. code-block:: console

   msl install network

Compatibility
-------------
The :class:`~msl.network.client.Client` and :class:`~msl.network.service.Service` classes can be
implemented in any programming language (and also in unsupported Python versions). See the
:ref:`json-formats` section for how the Network :class:`~msl.network.manager.Manager` exchanges
information between a :class:`~msl.network.client.Client` and a :class:`~msl.network.service.Service`.

Dependencies
------------
* Python 3.8+
* cryptography_
* paramiko_

Optional packages that can be used for (de)serializing JSON_ data:

* UltraJSON_
* RapidJSON_
* simplejson_
* orjson_

To use one of these external JSON_ packages, rather than Python's builtin :mod:`json` module,
read the documentation of :class:`msl.network.json.Package`.

.. _MSL Package Manager: https://msl-package-manager.readthedocs.io/en/stable/
.. _cryptography: https://cryptography.io/en/stable/
.. _JSON: https://www.json.org/
.. _UltraJSON: https://pypi.python.org/pypi/ujson/
.. _RapidJSON: https://pypi.python.org/pypi/python-rapidjson/
.. _simplejson: https://pypi.python.org/pypi/simplejson/
.. _orjson: https://pypi.org/project/orjson/
.. _paramiko: https://www.paramiko.org/
