.. _concurrent-asynchronous:

Concurrency and Asynchronous Programming
========================================

This section describes what is meant by :ref:`concurrency` and :ref:`asynchronous-programming`.
The `presentation <https://youtu.be/M-UcUs7IMIM>`_ by Robert Smallshire provides a nice overview of
concurrent programming and Python's :mod:`asyncio` module.

.. _concurrency:

Concurrency
-----------
*Concurrent programming* uses a single thread to execute multiple tasks in an interleaved fashion. This is
different from *parallel programming* where multiple tasks can be executed at the same time.

.. image:: _static/concurrency_vs_parallelism.png
   :scale: 60%
   :align: center
   :target: https://raw.githubusercontent.com/MSLNZ/msl-network/main/docs/_static/concurrency_vs_parallelism.png

The Network :class:`~msl.network.manager.Manager` uses *concurrent programming*. It runs in a single event loop
but it can handle multiple :class:`~msl.network.client.Client`\s and :class:`~msl.network.service.Service`\s
connected to it simultaneously.

When a :class:`~msl.network.client.Client` sends a request, the :class:`~msl.network.manager.Manager`
forwards the request to the appropriate :class:`~msl.network.service.Service` and then the
:class:`~msl.network.manager.Manager` waits for another event to occur. Whether the event is a reply from a
:class:`~msl.network.service.Service`, another request from a :class:`~msl.network.client.Client` or a new device
wanting to connect to the :class:`~msl.network.manager.Manager`, the :class:`~msl.network.manager.Manager` simply
waits for I/O events and forwards an event to the appropriate network device when an event becomes available.

Since the :class:`~msl.network.manager.Manager` is running in a single thread it can only process one event at a
single instance in time. In typical use cases, this does not inhibit the performance of the
:class:`~msl.network.manager.Manager` since the :class:`~msl.network.manager.Manager` has the sole responsibility
of routing requests and replies through the network and it does not actually execute a request. *There are*
*rare situations when an administrator is making a request for the* :class:`~msl.network.manager.Manager`
*to execute and in these situations the* :class:`~msl.network.manager.Manager` *would be executing the request, see*
:meth:`~msl.network.client.Client.admin_request` *for more details*.

The :class:`~msl.network.manager.Manager` can become slow if it is (de)serializing a large
`JSON <https://www.json.org/>`_ object or sending a large amount of bytes through the network. For example,
if a reply from a :class:`~msl.network.service.Service` is 1 GB in size and the network speed is 1 Gbps
(125 MB/s) then it will take at least 8 seconds for the data to be transmitted. During these 8 seconds the
:class:`~msl.network.manager.Manager` will be unresponsive to other events until it finishes sending all 1 GB of
data.

If the request for, or reply from, a :class:`~msl.network.service.Service` consumes a lot of the processing time
of the :class:`~msl.network.manager.Manager` it is best to start another instance of the
:class:`~msl.network.manager.Manager` on another port to host the :class:`~msl.network.service.Service`.

.. _asynchronous-programming:

Asynchronous Programming
------------------------

A :class:`~msl.network.client.Client` can send requests either *synchronously* or *asynchronously*. Synchronous
requests are sent sequentially and the :class:`~msl.network.client.Client` must wait to receive the reply before
proceeding to send the next request. These are blocking requests where the total execution time to receive all
replies is the combined sum of executing each request individually. Asynchronous requests do not wait for the
reply but immediately return a :class:`~concurrent.futures.Future` instance, which is an object that is a
*promise* that a result (or exception) will be available later. These are non-blocking requests where the total
execution time to receive all replies is equal to the time it takes to execute the longest-running request.

.. image:: _static/sync_vs_async.png
   :scale: 60%
   :align: center
   :target: https://raw.githubusercontent.com/MSLNZ/msl-network/main/docs/_static/sync_vs_async.png

.. _synchronous:

Synchronous Example
+++++++++++++++++++

The following code illustrates how to send requests *synchronously*. Before you can run this example on your own
computer make sure to :ref:`start-manager` and start the :ref:`basic-math-service`.

.. code-block:: python

    # synchronous.py
    #
    # This script takes about 21 seconds to run.

    import time
    from msl.network import connect

    # Connect to the Manager (that is running on the same computer)
    cxn = connect()

    # Establish a link to the BasicMath Service
    bm = cxn.link('BasicMath')

    # Get the start time before sending the requests
    t0 = time.perf_counter()

    # Send all requests synchronously
    # The returned object is the result of each request
    add = bm.add(1, 2)
    subtract = bm.subtract(1, 2)
    multiply = bm.multiply(1, 2)
    divide = bm.divide(1, 2)
    is_positive = bm.ensure_positive(1)
    power = bm.power(2, 4)

    # Print the results
    print(f'1+2= {add}')
    print(f'1-2= {subtract}')
    print(f'1*2= {multiply}')
    print(f'1/2= {divide}')
    print(f'is positive? {is_positive}')
    print(f'2**4= {power}')

    # The total time that passed to receive all results
    dt = time.perf_counter() - t0
    print(f'Total execution time: {dt:.2f} seconds')

    # Disconnect from the Manager
    cxn.disconnect()

The output of the ``synchronous.py`` program will be::

    1+2= 3
    1-2= -1
    1*2= 2
    1/2= 0.5
    is positive? True
    2**4= 16
    Total execution time: 21.06 seconds

The *Total execution time* value will be slightly different for you, but the important thing to notice is that
executing all requests took about 21 seconds (i.e., 1+2+3+4+5+6=21 for the :func:`time.sleep` functions in the
:ref:`basic-math-service`) and that the returned object from each request was the value of the result.

.. _asynchronous:

Asynchronous Example
++++++++++++++++++++

The following code illustrates how to send requests *asynchronously*. Before you can run this example on your own
computer make sure to :ref:`start-manager` and start the :ref:`basic-math-service`.

.. code-block:: python

    # asynchronous.py
    #
    # This script takes about 6 seconds to run.

    import time
    from msl.network import connect

    # Connect to the Manager (that is running on the same computer)
    cxn = connect()

    # Establish a link to the BasicMath Service
    bm = cxn.link('BasicMath')

    # Get the start time before sending the requests
    t0 = time.perf_counter()

    # Create asynchronous requests by using the asynchronous=True keyword argument
    # The returned object is a Future object (not the result of each request)
    add = bm.add(1, 2, asynchronous=True)
    subtract = bm.subtract(1, 2, asynchronous=True)
    multiply = bm.multiply(1, 2, asynchronous=True)
    divide = bm.divide(1, 2, asynchronous=True)
    is_positive = bm.ensure_positive(1, asynchronous=True)
    power = bm.power(2, 4, asynchronous=True)

    # There are different ways to gather the results of the Future objects.
    # Calling result() on the Future will block until the result becomes
    # available (or until the request raised an exception). Note, the
    # result() method also supports a timeout argument. You can also
    # register callbacks to be called when a Future is done.

    # Print the results
    print(f'1+2= {add.result()}')
    print(f'1-2= {subtract.result()}')
    print(f'1*2= {multiply.result()}')
    print(f'1/2= {divide.result()}')
    print(f'is positive? {is_positive.result()}')
    print(f'2**4= {power.result()}')

    # The total time that passed to receive all results
    dt = time.perf_counter() - t0
    print(f'Total execution time: {dt:.2f} seconds')

    # Disconnect from the Manager
    cxn.disconnect()

The output of the ``asynchronous.py`` program will be::

    1+2= 3
    1-2= -1
    1*2= 2
    1/2= 0.5
    is positive? True
    2**4= 16
    Total execution time: 6.02 seconds

The *Total execution time* value will be slightly different for you, but the important thing to notice is that
executing all requests took about 6 seconds (i.e., max(1, 2, 3, 4, 5, 6) for the :func:`time.sleep` functions in the
:ref:`basic-math-service`) and that the returned object from each request was a :class:`~concurrent.futures.Future`
instance which we needed to get the :meth:`~concurrent.futures.Future.result` of.

Synchronous vs Asynchronous comparison
++++++++++++++++++++++++++++++++++++++

Comparing the total execution time for the :ref:`synchronous` and the :ref:`asynchronous` we see that the asynchronous
program is 3.5 times faster. Choosing whether to send a request synchronously or asynchronously is performed by passing
in an ``asynchronous=False`` or ``asynchronous=True`` keyword argument, respectively. Also, in the synchronous example
when a request is sent the object that is returned is the result of the method from the :ref:`basic-math-service`,
whereas in the asynchronous example the returned value is a :class:`~concurrent.futures.Future` object that
provides the result later.

+-----------------------------+------------------------------+----------------------------------------------+
|                             |   Synchronous                |   Asynchronous                               |
+=============================+==============================+==============================================+
| Total execution time        |    21 seconds                |     6 seconds                                |
+-----------------------------+------------------------------+----------------------------------------------+
| Keyword argument to invoke  | asynchronous=False (default) |  asynchronous=True                           |
+-----------------------------+------------------------------+----------------------------------------------+
| Returned value from request |    the result                | a :class:`~concurrent.futures.Future` object |
+-----------------------------+------------------------------+----------------------------------------------+
