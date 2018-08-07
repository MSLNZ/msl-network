.. _usage:

Usage
=====

Using **MSL-Network** requires a sequence of 3 steps:

1. :ref:`start-manager`
2. :ref:`start-service`
3. :ref:`connect-client`

.. _start-manager:

Start the Network Manager
-------------------------

The first thing to do is to start the Network :class:`~msl.network.manager.Manager`. Open a
command prompt (Windows) or a terminal (\*nix) and run:

.. code-block:: console

   msl-network start

Running this command will automatically perform the following default actions:

* create a private 2048-bit, RSA_ key
* create a self-signed certificate using the private key
* create a SQLite_ database to store information that is needed by the Network :class:`~msl.network.manager.Manager`
* start the Network :class:`~msl.network.manager.Manager` on the default port using the TLS_ protocol

You can override the default actions, for example, use `Elliptic-Curve Cryptography`_ rather than
RSA_. For more details refer to the help that is available from the command line, for example:

.. code-block:: console

   msl-network --help
   msl-network certgen --help

.. _start-service:

Start a Service on the Network Manager
--------------------------------------

Below is a simple, *and terribly inefficient*, :class:`~msl.network.service.Service` that performs some basic
math operations. In order to create a new :class:`~msl.network.service.Service` just create a class that
is a subclass of :class:`~msl.network.service.Service` and call the :meth:`~msl.network.service.Service.start`
method.

.. note::
   The reason for adding the :func:`time.sleep` functions in the :ref:`basic-math-service` will become evident
   when discussing :ref:`asynchronous-programming`.

.. _basic-math-service:

BasicMath Service
+++++++++++++++++

.. literalinclude:: ../msl/examples/network/basic_math.py

To start the :ref:`basic-math-service` run the following command in a command prompt (Windows):

.. code-block:: console

   python -c "from msl.examples.network import BasicMath; BasicMath().start()"

or, in a terminal (\*nix):

.. code-block:: console

   python3 -c "from msl.examples.network import BasicMath; BasicMath().start()"

This will start the :ref:`basic-math-service` on the Network :class:`~msl.network.manager.Manager`
that is running on the same computer.

.. _connect-client:

Connect to the Network Manager as a Client
------------------------------------------

Now that there is a :ref:`basic-math-service` running on the Network :class:`~msl.network.manager.Manager`
(which are both running on the same computer that the :class:`~msl.network.client.Client` will be), we can
:func:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`:

.. code-block:: pycon

   >>> from msl.network import connect
   >>> cxn = connect()

establish a link with the :ref:`basic-math-service`:

.. code-block:: pycon

   >>> bm = cxn.link('BasicMath')

and send a request to the :ref:`basic-math-service`:

.. code-block:: pycon

   >>> bm.add(1, 2)
   3

*See the* :ref:`asynchronous-programming` *section for an example on how to send requests asynchronously.*

We can find out what devices are currently connected to the :class:`~msl.network.manager.Manager`:

.. code-block:: pycon

   >>> print(cxn.manager(as_yaml=True))
   Manager[localhost:1875]
       attributes:
           identity: () -> dict
           link: (service:str) -> bool
       language: Python 3.6.2
       os: Windows 10 AMD64
   Clients [1]:
       Client[localhost:51065]
           language: Python 3.6.5
           os: Windows 10 AMD64
   Services [1]:
       BasicMath[localhost:51042]
           attributes:
               add: (x:Union[int, float], y:Union[int, float]) -> Union[int, float]
               divide: (x:Union[int, float], y:Union[int, float]) -> Union[int, float]
               ensure_positive: (x:Union[int, float]) -> bool
               euler: 2.718281828459045
               multiply: (x:Union[int, float], y:Union[int, float]) -> Union[int, float]
               pi: 3.141592653589793
               power: (x:Union[int, float], n=2) -> Union[int, float]
               subtract: (x:Union[int, float], y:Union[int, float]) -> Union[int, float]
           language: Python 3.6.2
           os: Windows 10 AMD64

If ``as_yaml=False``, which is the default boolean value, then the returned value would be a
:class:`dict`, rather than a :class:`str`, containing the same information.

To disconnect from the :class:`~msl.network.manager.Manager`, enter:

.. code-block:: pycon

  >>> cxn.disconnect()

.. _RSA: https://en.wikipedia.org/wiki/RSA_(cryptosystem)
.. _TLS: https://en.wikipedia.org/wiki/Transport_Layer_Security
.. _Elliptic-Curve Cryptography: https://en.wikipedia.org/wiki/Elliptic-curve_cryptography
.. _SQLite: https://www.sqlite.org/
