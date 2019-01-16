.. _network-examples:

Python Examples
===============

The following examples illustrate some ideas on how one could use **MSL-Network**.

1. :ref:`digital-multimeter`
2. :ref:`additional-examples`

.. _digital-multimeter:

Digital Multimeter
------------------

This example shows how a digital multimeter that has a non-Ethernet interface, e.g., GPIB or RS232, can be
controlled from any computer that is on the network. It uses the MSL-Equipment_ package to connect to the digital
multimeter and **MSL-Network** to enable the digital multimeter as a :class:`~msl.network.service.Service` on the
network. This example is included with **MSL-Network** when it is installed, but since it requires additional hardware
(a digital multimeter) it can only be run if the hardware is attached to the computer.

The first task to do is to :ref:`start-manager` on the same computer that the digital multimeter is
physically connected to (via a GPIB cable or a DB9 cable). Next, on the same computer, copy and paste the
following script to a file and run the script to start the digital multimeter :class:`~msl.network.service.Service`.

.. literalinclude:: ../msl/examples/network/dmm.py

With the ``DigitalMultimeter`` :class:`~msl.network.service.Service` running you can execute the following
commands on another computer that is on the same network as the :class:`~msl.network.manager.Manager`
in order to interact with the digital multimeter from the remote computer.

Connect to the :class:`~msl.network.manager.Manager` by specifying the hostname of the computer that the
:class:`~msl.network.manager.Manager` is running on

.. code-block:: pycon

   >>> from msl.network import connect
   >>> cxn = connect(host='change to be the hostname of the computer that is running the Manager')

Since the name of the ``DigitalMultimeter`` :class:`~msl.network.service.Service` was specified to be
``'Hewlett Packard 34401A'``, we must link with the correct name of the :class:`~msl.network.service.Service`

.. code-block:: pycon

   >>> dmm = cxn.link('Hewlett Packard 34401A')

Now we can send ``write``, ``read`` or ``query`` commands to the digital multimeter

.. code-block:: pycon

   >>> dmm.query('MEASURE:VOLTAGE:DC?')
   '-6.23954727E-02'

When you are finished sending requests to the :class:`~msl.network.manager.Manager` you should disconnect
from the :class:`~msl.network.manager.Manager`. This will allow other :class:`~msl.network.client.Client`\'s
to be able to control the digital multimeter.

.. code-block:: pycon

   >>> cxn.disconnect()

.. _additional-examples:

Additional (Runnable) Examples
------------------------------
The following :class:`~msl.network.service.Service`\'s are included with **MSL-Network**. To start
any of these :class:`~msl.network.service.Service`\'s, first make sure that you :ref:`start-manager`,
and then run the following command in a `command prompt`_ (Windows) or in a terminal (\*nix, replace *python*
with *python3*). For this example, the ``Echo`` :class:`~msl.network.service.Service` is started

.. code-block:: console

   python -c "from msl.examples.network import Echo; Echo().start()"

You can then send requests to the ``Echo`` :class:`~msl.network.service.Service`

.. code-block:: pycon

   >>> from msl.network import connect
   >>> cxn = connect()
   >>> e = cxn.link('Echo')
   >>> e.echo('hello')
   [['hello'], {}]
   >>> e.echo('world!', x=7, array=list(range(10)))
   [['world!'], {'x': 7, 'array': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}]
   >>> cxn.disconnect()

.. _echo-service:

Echo Service
++++++++++++

.. literalinclude:: ../msl/examples/network/echo.py

.. _basicmath-service:

BasicMath Service
+++++++++++++++++

.. literalinclude:: ../msl/examples/network/basic_math.py

.. _myarray-service:

MyArray Service
++++++++++++++++

.. literalinclude:: ../msl/examples/network/array.py


.. _MSL-Equipment: https://msl-equipment.readthedocs.io/en/latest/
.. _command prompt: https://en.wikipedia.org/wiki/Cmd.exe
