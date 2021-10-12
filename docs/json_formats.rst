.. _json-formats:

JSON Formats
============

Information is exchanged between a :class:`~msl.network.manager.Manager`, a :class:`~msl.network.client.Client`
and a :class:`~msl.network.service.Service` using JSON_ as the data format. The information is
serialized_ to bytes and terminated with ``"\r\n"`` (a carriage return and a line feed).

A :class:`~msl.network.client.Client` or a :class:`~msl.network.service.Service` can be written in
any programming language, but the JSON_ data format must adhere to the specific requirements specified
below. The :class:`~msl.network.client.Client` and :class:`~msl.network.service.Service` must also
check for the ``"\r\n"`` (or just the ``"\n"``) byte sequence in each network packet that it receives
in order to ensure that all bytes have been received or to check if multiple requests/responses are
contained within the same network packet.

.. _client-format:

Client Format
-------------

A :class:`~msl.network.client.Client` must **send a request** with the following JSON_ representation:

.. code-block:: console

    {
      "args": array of objects (arguments to be passed to the method of the Manager or Service)
      "attribute": string (the name of a method or variable to access from the Manager or Service)
      "error": false
      "kwargs": name-value pairs (keyword arguments to be passed to the method of the Manager or Service)
      "service": string (the name of the Service, or "Manager" if the request is for the Manager)
      "uuid": string (a universally unique identifier of the request)
    }

The `uuid <https://en.wikipedia.org/wiki/Universally_unique_identifier>`_ is only used by the
:class:`~msl.network.client.Client`. The :class:`~msl.network.manager.Manager` simply forwards the unique id
to the :class:`~msl.network.service.Service` which just includes the unique id in its reply. Therefore, the value
can be anything that you want it to be (provided that it does not contain the ``"\r\n"`` sequence and it cannot
be equal to ``"notification"`` since this is a reserved uuid). The uuid is useful when keeping track of which
reply corresponds with which request when executing asynchronous requests.

A :class:`~msl.network.client.Client` will also have to **send a reply** to a :class:`~msl.network.manager.Manager`
during the connection procedure (i.e., when sending the :obj:`~msl.network.network.Network.identity` of the
:class:`~msl.network.client.Client` and possibly providing a username and/or password if requested by the
:class:`~msl.network.manager.Manager`).

To send a reply to the :class:`~msl.network.manager.Manager` use the following JSON_ representation

.. code-block:: console

    {
      "error": false (can be omitted)
      "requester": string (can be omitted)
      "result": object (the reply from the Client)
      "uuid": string (can be omitted)
    }

You only need to include the "result" name-value pair in the reply. The "error", "requester" and "uuid"
name-value pairs can be omitted, or anything you want, since they are not used by the
:class:`~msl.network.manager.Manager` to process the reply from a :class:`~msl.network.client.Client`.
However, including these additional name-value pairs provides symmetry with the way a
:class:`~msl.network.service.Service` sends a reply to a :class:`~msl.network.manager.Manager`
when there is no error.

A :class:`~msl.network.client.Client` will **receive a reply** that is in 1 of 3 JSON_ representations.

Before a :class:`~msl.network.client.Client` successfully connects to the :class:`~msl.network.manager.Manager`
the :class:`~msl.network.manager.Manager` will request information about the connecting device (such as the
:obj:`~msl.network.network.Network.identity` of the device and it may check the authorization details of the
connecting device).

If the bytes received represent a request from the Network :class:`~msl.network.manager.Manager` then the JSON_ object
will be:

.. code-block:: console

    {
      "args": array of objects (arguments to be passed to the method of the Client)
      "attribute": string (the name of a method to call from the Client)
      "error": false
      "kwargs": name-value pairs (keyword arguments to be passed to the method of the Client)
      "requester": string (the address of the Network Manager)
      "uuid": string (an empty string)
    }

If the bytes received represent a reply from a :class:`~msl.network.service.Service` then the JSON_ object will be:

.. code-block:: console

    {
      "error": false
      "requester": string (the address of the Client that made the request)
      "result": object (the reply from the Service)
      "uuid": string (the universally unique identifier of the request)
    }

If the bytes received represent an error then the JSON_ object will be:

.. code-block:: console

    {
      "error": true
      "message": string (a short description of the error)
      "requester": string (the address of the device that made the request)
      "result": null
      "traceback": array of strings (a detailed stack trace of the error)
      "uuid": string
    }

A :class:`~msl.network.service.Service` can also emit a notification to all
:class:`~msl.network.client.Client`\'s that are :class:`~msl.network.client.Link`\ed with the
:class:`~msl.network.service.Service`. Each :class:`~msl.network.client.Client` will
**receive a notification** that has the following JSON_ representation

.. code-block:: console

    {
      "error": false
      "result": array (a 2-element list of [args, kwargs], e.g., [[1, 2, 3], {"x": 4, "y": 5}])
      "service": string (the name of the Service that emitted the notification)
      "uuid": "notification"
    }

.. _service-format:

Service Format
--------------

A :class:`~msl.network.service.Service` will **receive** data in 1 of 2 JSON_ representations.

If the bytes received represent an error from the Network :class:`~msl.network.manager.Manager` then the JSON_
object will be:

.. code-block:: console

    {
      "error": true
      "message": string (a short description of the error)
      "requester": string (the address of the Manager)
      "result": null
      "traceback": array of strings (a detailed stack trace of the error)
      "uuid": string (an empty string)
    }

If the bytes received represent a request from the :class:`~msl.network.manager.Manager` or a
:class:`~msl.network.client.Client` then the JSON_ object will be:

.. code-block:: console

    {
      "args": array of objects (arguments to be passed to the method of the Service )
      "attribute": string (the name of a method or variable to access from the Service)
      "error": false
      "kwargs": name-value pairs (keyword arguments to be passed to the method of the Service)
      "requester": string (the address of the device that made the request)
      "uuid": string (the universally unique identifier of the request)
    }

A :class:`~msl.network.service.Service` will **send a response** in 1 of 2 JSON_ representations.

If the :class:`~msl.network.service.Service` raised an exception then the JSON_ object will be:

.. code-block:: console

    {
      "error": true
      "message": string (a short description of the error)
      "requester": string (the address of the device that made the request)
      "result": null
      "traceback": array of strings (a detailed stack trace of the error)
      "uuid": string (the universally unique identifier of the request)
    }

If the :class:`~msl.network.service.Service` successfully executed the request then the JSON_ object will be:

.. code-block:: console

    {
      "error": false
      "requester": string (the address of the device that made the request)
      "result": object (the reply from the Service)
      "uuid": string (the universally unique identifier of the request)
    }

A :class:`~msl.network.service.Service` can also emit a notification to all
:class:`~msl.network.client.Client`\'s that are :class:`~msl.network.client.Link`\ed with the
:class:`~msl.network.service.Service`. A :class:`~msl.network.service.Service` must
**emit a notification** that has the following JSON_ representation

.. code-block:: console

    {
      "error": false
      "result": array (a 2-element list of [args, kwargs], e.g., [[1, 2, 3], {"x": 4, "y": 5}])
      "service": string (the name of the Service that emitted the notification)
      "uuid": "notification"
    }

.. _JSON: https://www.json.org/
.. _serialized: https://en.wikipedia.org/wiki/Serialization
