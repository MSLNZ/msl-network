.. _json-formats:

JSON Formats
============

Information is exchanged between the :class:`~msl.network.manager.Manager`, a :class:`~msl.network.client.Client`
and a :class:`~msl.network.service.Service` using JSON_ as the data format. The information is
`serialized <https://en.wikipedia.org/wiki/Serialization>`_ to bytes and terminated with the line-feed character,
``\n``. Therefore, a :class:`~msl.network.client.Client` and a :class:`~msl.network.service.Service` must
not use the ``\n`` character within in the request or the reply since the ``\n`` character is used to signify the
end of the byte stream.

A :class:`~msl.network.client.Client` or a :class:`~msl.network.service.Service` can be written in any programming
language but the JSON_ data format must adhere to specific requirements. The :class:`~msl.network.client.Client` and
:class:`~msl.network.service.Service` must check for the ``\n`` character to ensure that all bytes have been received.

.. _client-format:

Client Format
-------------

A :class:`~msl.network.client.Client` must **send** data with the following JSON_ representation::

    {
      'error': false
      'service': string (the name of the Service, or "Manager" if the request is for the Manager)
      'attribute': string (the name of a method or variable to access from the Manager or Service)
      'args': array of objects (arguments to be passed to the method of the Manager or Service)
      'kwargs': key-value pairs (keyword arguments to be passed to the method of the Manager or Service)
      'uuid': string (a universally unique identifier of the request)
    }

The `uuid <https://en.wikipedia.org/wiki/Universally_unique_identifier>`_ is only used by the
:class:`~msl.network.client.Client` when it receives the reply from the :class:`~msl.network.manager.Manager`.
Therefore, the value can be anything that you want it to be (provided that it does not contain the ``\n`` character).
It is a useful value to use when keeping track of which reply belongs with which request when executing asynchronous
requests.

A :class:`~msl.network.client.Client` will **receive** data that is in 1 of 3 JSON_ representations.

Before a :class:`~msl.network.client.Client` successfully connects to the :class:`~msl.network.manager.Manager`
the :class:`~msl.network.manager.Manager` will request information about the connecting device (such as the
:obj:`~msl.network.network.Network.identity` of the device and it may check the authorization details of the
connecting device).

If the input data represents a request from the Network :class:`~msl.network.manager.Manager` then the JSON_ object
will be::

    {
      'error': false
      'attribute': string (the name of a method to call from the Client)
      'args': array of objects (arguments to be passed to the method of the Client)
      'kwargs': key-value pairs (keyword arguments to be passed to the method of the Client)
      'requester': string (the address of the Network Manager)
      'uuid': string (an empty string)
    }

If the input data represent a reply from a :class:`~msl.network.service.Service` then the JSON_ object will be::

    {
      'error' : false
      'result': object (the reply from the Service)
      'requester': string (the address of the Client that made the request)
      'uuid': string (the universally unique identifier of the request)
    }

If the input data represents an error then the JSON_ object will be::

    {
      'error': true
      'message': string (a short description of the error)
      'traceback': array of strings (a detailed stack trace of the error)
      'result': null
      'requester': string (the address of the device that made the request)
      'uuid': string (can be an empty string)
    }

.. _service-format:

Service Format
--------------

A :class:`~msl.network.service.Service` will **receive** data in 1 of 2 JSON_ representations.

If the input data represents an error from the Network :class:`~msl.network.manager.Manager` then the JSON_
object will be::

    {
      'error': true
      'message': string (a short description of the error)
      'traceback': array of strings (a detailed stack trace of the error)
      'result': null
      'requester': string (the address of the Manager)
      'uuid': string (an empty string)
    }

If the input data represents a request from the :class:`~msl.network.manager.Manager` or a
:class:`~msl.network.client.Client` then the JSON_ object will be::

    {
      'error': false
      'attribute': string (the name of a method or variable to access from the Service)
      'args': array of objects (arguments to be passed to the method of the Service )
      'kwargs': key-value pairs (keyword arguments to be passed to the method of the Service)
      'requester': string (the address of the device that made the request)
      'uuid': string (the universally unique identifier of the request)
    }

A :class:`~msl.network.service.Service` will **send** data in 1 of 2 JSON_ representations.

If the :class:`~msl.network.service.Service` raised an exception then the JSON_ object will be::

    {
      'error': true
      'message': string (a short description of the error)
      'traceback': array of strings (a detailed stack trace of the error)
      'result': null
      'requester': string (the address of the device that made the request)
      'uuid': string (the universally unique identifier of the request)
    }

If the :class:`~msl.network.service.Service` successfully executed the request then the JSON_ object will be::

    {
      'error': false
      'result': object (the reply from the Service)
      'requester': string (the address of the device that made the request)
      'uuid': string (the universally unique identifier of the request)
    }

.. _JSON: http://www.json.org/
