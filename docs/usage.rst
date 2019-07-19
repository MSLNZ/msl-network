.. _network-usage:

Usage
=====

Using **MSL-Network** requires a sequence of 3 steps:

1. :ref:`start-manager`
2. :ref:`start-service`
3. :ref:`connect-client`

.. _start-manager:

Start the Network Manager
-------------------------

The first thing to do is to start the Network :class:`~msl.network.manager.Manager`. There are 3 ways
to do this.

1. From a `command prompt`_ (Windows) or a terminal (\*nix) by running:

    .. code-block:: console

       msl-network start

    Running this command will automatically perform the following default actions:

        * create a private 2048-bit, RSA_ key
        * create a self-signed certificate using the private key
        * create a SQLite_ database to store information that is used by the Network
          :class:`~msl.network.manager.Manager`
        * start the Network :class:`~msl.network.manager.Manager` on the default port using the TLS_ protocol
        * no authentication is required for :class:`~msl.network.client.Client`\'s and
          :class:`~msl.network.service.Service`\'s to connect to the :class:`~msl.network.manager.Manager`

    You can override the default actions, for example, use `Elliptic-Curve Cryptography`_ rather than
    RSA_ or only allow certain users to be able to connect to the :class:`~msl.network.manager.Manager`.
    For more details refer to the help that is available from the command line

    .. code-block:: console

       msl-network --help
       msl-network start --help

2. Call :func:`~msl.network.manager.run_forever` in a script.

3. Call :func:`~msl.network.manager.run_services` in a script. This method also starts the
   :class:`~msl.network.service.Service`\'s immediately after the :class:`~msl.network.manager.Manager` starts.

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

The :ref:`basic-math-service` is included with **MSL-Network**. To start the service run the following
command in a `command prompt`_ (Windows) or in a terminal (\*nix, replace *python* with *python3*)

.. code-block:: console

   python -c "from msl.examples.network import BasicMath; BasicMath().start()"

This will start the :ref:`basic-math-service` on the Network :class:`~msl.network.manager.Manager`
that is running on the same computer.

.. _connect-client:

Connect to the Network Manager as a Client
------------------------------------------

Now that there is a :ref:`basic-math-service` running on the Network :class:`~msl.network.manager.Manager`
(which are both running on the same computer that the :class:`~msl.network.client.Client` will be), we can
:func:`~msl.network.client.connect` to the Network :class:`~msl.network.manager.Manager`

.. code-block:: pycon

   >>> from msl.network import connect
   >>> cxn = connect()

establish a link with the :ref:`basic-math-service`

.. code-block:: pycon

   >>> bm = cxn.link('BasicMath')

and send a request to the :ref:`basic-math-service`

.. code-block:: pycon

   >>> bm.add(1, 2)
   3

*See the* :ref:`asynchronous-programming` *section for an example on how to send requests asynchronously.*

To find out what devices are currently connected to the :class:`~msl.network.manager.Manager`, execute

.. code-block:: pycon

   >>> print(cxn.manager(as_string=True))
   Manager[localhost:1875]
     attributes:
       identity() -> dict
       link(service: str) -> bool
     language: Python 3.7.3
     os: Windows 10 AMD64
   Clients [1]:
     Client[localhost:63818]
       language: Python 3.7.3
       os: Windows 10 AMD64
   Services [1]:
     BasicMath[localhost:63815]
       attributes:
         add(x: Union[int, float], y: Union[int, float]) -> Union[int, float]
         divide(x: Union[int, float], y: Union[int, float]) -> Union[int, float]
         ensure_positive(x: Union[int, float]) -> bool
         euler() -> 2.718281828459045
         multiply(x: Union[int, float], y: Union[int, float]) -> Union[int, float]
         pi() -> 3.141592653589793
         power(x: Union[int, float], n=2) -> Union[int, float]
         subtract(x: Union[int, float], y: Union[int, float]) -> Union[int, float]
       language: Python 3.7.3
       max_clients: -1
       os: Windows 10 AMD64

If ``as_string=False``, which is the default boolean value, then the returned value would be a
:class:`dict`, rather than a :class:`str`, containing the same information.

To disconnect from the :class:`~msl.network.manager.Manager`, execute

.. code-block:: pycon

  >>> cxn.disconnect()

If you only wanted to connect to the :ref:`basic-math-service` (and no other
:class:`~msl.network.service.Service`\s on the :class:`~msl.network.manager.Manager`)
then you could create a :class:`~msl.network.client.LinkedClient`

.. code-block:: pycon

   >>> from msl.network import LinkedClient
   >>> bm = LinkedClient('BasicMath')
   >>> bm.add(1, 2)
   3
   >>> bm.disconnect()

.. _RSA: https://en.wikipedia.org/wiki/RSA_(cryptosystem)
.. _TLS: https://en.wikipedia.org/wiki/Transport_Layer_Security
.. _Elliptic-Curve Cryptography: https://en.wikipedia.org/wiki/Elliptic-curve_cryptography
.. _SQLite: https://www.sqlite.org/
.. _command prompt: https://en.wikipedia.org/wiki/Cmd.exe
