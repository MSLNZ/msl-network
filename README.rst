Welcome to MSL-Network
======================

|docs|

Purpose
-------
**MSL-Network** uses concurrency and asynchronous programming to transfer data across a network. The network
is composed of three objects -- a Network Manager_, Client_\s and Service_\s.

The Network Manager_ allows for multiple Client_\s and Service_\s to connect to it and it links a Client_'s
request to the appropriate Service_ to execute the request and then the Network Manager_ sends the response
from the Service_ back to the Client_.

The Network Manager_ uses concurrency to handle requests from multiple Client_\s such that multiple requests
start, run and complete in overlapping time periods and in no specific order. A Client_ can send requests
synchronously or asynchronously to the Network Manager_ for a Service_ to execute. See
`Concurrency and Asynchronous Programming`_ for more details.

JSON_ is used as the data format to exchange information between a Client_ and a Service_. As such, it is
possible to implement a Client_ or a Service_ in any programming language to connect to the Network Manager_.
See the `JSON Formats`_ section for an overview of the data format. One can even connect to the Network
Manager_ from a terminal to send requests, see `Connecting from a Terminal`_ for more details.

Documentation
-------------

The documentation for **MSL-Network** can be found `here <http://msl-network.readthedocs.io/en/latest/index.html>`_.

Install
-------

To install **MSL-Network** run::

   pip install https://github.com/MSLNZ/msl-network/archive/master.zip

Alternatively, using the `MSL Package Manager`_ run::

   msl install network

Dependencies
++++++++++++
* Python 3.5+
* cryptography_

.. |docs| image:: https://readthedocs.org/projects/msl-network/badge/?version=latest
   :target: http://msl-network.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. _Manager: http://msl-network.readthedocs.io/en/latest/_api/msl.network.manager.html
.. _Client: http://msl-network.readthedocs.io/en/latest/_api/msl.network.client.html#msl.network.client.Client
.. _Service: http://msl-network.readthedocs.io/en/latest/_api/msl.network.service.html
.. _Concurrency and Asynchronous Programming: http://msl-network.readthedocs.io/en/latest/concurrency_async.html#concurrent-asynchronous
.. _JSON: http://www.json.org/
.. _JSON Formats: http://msl-network.readthedocs.io/en/latest/json_formats.html#json-formats
.. _Connecting from a Terminal: http://msl-network.readthedocs.io/en/latest/terminal_input.html#terminal-input
.. _MSL Package Manager: http://msl-package-manager.readthedocs.io/en/latest/?badge=latest
.. _cryptography: https://pypi.python.org/pypi/cryptography
