.. _network-api:

=============================
MSL-Network API Documentation
=============================

**MSL-Network** has very little functions or classes that need to be accessed in a user's application.

Typically, only the :class:`~msl.network.service.Service` class needs to be subclassed and the
:func:`~msl.network.client.connect` function will be called to connect to the Network
:class:`~msl.network.manager.Manager` for most applications using **MSL-Network**.

The :mod:`msl.network.ssh` module provides some functions for using `SSH <https://www.ssh.com/ssh/>`_
to connect to a remote computer. :ref:`ssh-example` shows an example Python package that can
automatically start a Network :class:`~msl.network.manager.Manager` and a
:class:`~msl.network.service.Service` on a Raspberry Pi from another computer.

The process of establishing a connection to a :class:`~msl.network.manager.Manager` and linking
with a particular :class:`~msl.network.service.Service` can be achieved by creating a
:class:`~msl.network.client.LinkedClient`. This can be useful if you only want to link with a
single :class:`~msl.network.service.Service` on a :class:`~msl.network.manager.Manager`.

Package Structure
-----------------

.. toctree::

   msl.network <_api/msl.network>
   msl.network.client <_api/msl.network.client>
   msl.network.constants <_api/msl.network.constants>
   msl.network.cryptography <_api/msl.network.cryptography>
   msl.network.database <_api/msl.network.database>
   msl.network.exceptions <_api/msl.network.exceptions>
   msl.network.json <_api/msl.network.json>
   msl.network.manager <_api/msl.network.manager>
   msl.network.network <_api/msl.network.network>
   msl.network.service <_api/msl.network.service>
   msl.network.ssh <_api/msl.network.ssh>
   msl.network.utils <_api/msl.network.utils>
