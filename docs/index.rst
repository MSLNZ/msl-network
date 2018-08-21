.. _msl-network-welcome:

===========
MSL-Network
===========

**MSL-Network** is used to send information across a network and it is composed of three objects -- a
Network :class:`~msl.network.manager.Manager`, :class:`~msl.network.client.Client`\s and
:class:`~msl.network.service.Service`\s.

The Network :class:`~msl.network.manager.Manager` allows for multiple :class:`~msl.network.client.Client`\s
and :class:`~msl.network.service.Service`\s to connect to it and it links a :class:`~msl.network.client.Client`\'s
request to the appropriate :class:`~msl.network.service.Service` to execute the request and then the Network
:class:`~msl.network.manager.Manager` sends the response from the :class:`~msl.network.service.Service` back
to the :class:`~msl.network.client.Client`.

The Network :class:`~msl.network.manager.Manager` uses concurrency to handle requests from multiple
:class:`~msl.network.client.Client`\s such that multiple requests start, run and complete in overlapping time
periods and in no specific order. A :class:`~msl.network.client.Client` can send requests synchronously or
asynchronously to the Network :class:`~msl.network.manager.Manager` for a :class:`~msl.network.service.Service`
to execute. See :ref:`concurrent-asynchronous` for more details.

`JSON <https://www.json.org/>`_ is used as the data format to exchange information between a
:class:`~msl.network.client.Client` and a :class:`~msl.network.service.Service`. As such, it is possible to
implement a :class:`~msl.network.client.Client` or a :class:`~msl.network.service.Service` in any programming
language to connect to the Network :class:`~msl.network.manager.Manager`. See the :ref:`json-formats` section
for an overview of the data format. One can even connect to the Network :class:`~msl.network.manager.Manager`
from a terminal to send requests, see :ref:`terminal-input` for more details.

========
Contents
========

.. toctree::
   :maxdepth: 1

   Install <install>
   Usage <usage>
   Concurrency & Asynchronous Programming <concurrency_async>
   JSON Formats <json_formats>
   Connecting from a Terminal <terminal_input>
   Python Examples <examples>
   Non-Python Examples <nonpython>
   API <api>
   License <license>
   Authors <authors>
   Release Notes <changelog>

=====
Index
=====

* :ref:`modindex`
