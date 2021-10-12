.. _network-examples:

Python Examples
===============

The following examples illustrate some ideas on how one could use MSL-Network.

1. :ref:`digital-multimeter`
2. :ref:`additional-examples`
3. RPi-SmartGadget_ -- Uses a Raspberry Pi to communicate with a Sensirion SHTxx sensor.

.. _digital-multimeter:

Digital Multimeter
------------------

This example shows how a digital multimeter that has a non-Ethernet interface, e.g., GPIB or RS232, can be
controlled from any computer that is on the network. It uses the MSL-Equipment_ package to connect to the digital
multimeter and MSL-Network to enable the digital multimeter as a :class:`~msl.network.service.Service` on the
network. This example is included with MSL-Network when it is installed, but since it requires additional hardware
(a digital multimeter) it can only be run if the hardware is attached to the computer.

The first task to do is to :ref:`start-manager` on the same computer that the digital multimeter is
physically connected to (via a GPIB cable or a DB9 cable). Next, on the same computer, copy and paste the
following script to a file, edit the equipment record used by MSL-Equipment_ for the information relevant
to your DMM (e.g., the COM#, GPIB address) and then run the script to start the digital multimeter
:class:`~msl.network.service.Service`.

.. literalinclude:: ../msl/examples/network/dmm.py

With the ``DigitalMultimeter`` :class:`~msl.network.service.Service` running you can execute the following
commands on another computer that is on the same network as the :class:`~msl.network.manager.Manager`
in order to interact with the digital multimeter from the remote computer.

Connect to the :class:`~msl.network.manager.Manager` by specifying the hostname (or IP address) of the computer
that the :class:`~msl.network.manager.Manager` is running on

.. code-block:: pycon

   >>> from msl.network import connect
   >>> cxn = connect(host='the hostname or IP address of the computer that the Manager is running on')

Since the name of the ``DigitalMultimeter`` :class:`~msl.network.service.Service` was specified to be
``'Hewlett Packard 34401A'``, we must link with the correct name of the :class:`~msl.network.service.Service`

.. code-block:: pycon

   >>> dmm = cxn.link('Hewlett Packard 34401A')

.. tip::

   The process of establishing a connection to a :class:`~msl.network.manager.Manager`
   and linking with a :class:`~msl.network.service.Service` can also be done in a single
   line. A :class:`~msl.network.client.LinkedClient` exists for this purpose. This can be
   useful if you only want to link with a single :class:`~msl.network.service.Service`.

   .. code-block:: pycon

      >>> from msl.network import LinkedClient
      >>> dmm = LinkedClient('Hewlett Packard 34401A', host='hostname or IP address of the Manager')

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
The following :class:`~msl.network.service.Service`\'s are included with MSL-Network. To start
any of these :class:`~msl.network.service.Service`\'s, first make sure that you :ref:`start-manager`,
and then run the following command in a terminal. For this example, the :ref:`echo-service-source`
is running

.. code-block:: console

   python -c "from msl.examples.network import Echo; Echo().start()"

You can then send requests to the :ref:`echo-service-source`

.. code-block:: pycon

   >>> from msl.network import connect
   >>> cxn = connect()
   >>> e = cxn.link('Echo')
   >>> e.echo('hello')
   [['hello'], {}]
   >>> e.echo('world!', x=7, array=list(range(10)))
   [['world!'], {'x': 7, 'array': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}]
   >>> cxn.disconnect()

.. _echo-service-source:

Echo Service
++++++++++++

.. literalinclude:: ../msl/examples/network/echo.py

.. _basicmath-service-source:

BasicMath Service
+++++++++++++++++

.. literalinclude:: ../msl/examples/network/basic_math.py

.. _myarray-service-source:

MyArray Service
++++++++++++++++

.. literalinclude:: ../msl/examples/network/array.py

.. _heartbeat-service-source:

Heartbeat Service
+++++++++++++++++

.. literalinclude:: ../msl/examples/network/heartbeat.py

.. _MSL-Equipment: https://msl-equipment.readthedocs.io/en/latest/
.. _RPi-SmartGadget: https://github.com/MSLNZ/rpi-smartgadget
