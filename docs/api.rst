.. _network-api:

=============================
MSL-Network API Documentation
=============================

**MSL-Network** has very little functions or classes that need to be accessed in a user's application.

Typically, only the :class:`~msl.network.service.Service` class needs to be subclassed and the
:func:`~msl.network.client.connect` function will be called to connect to the Network
:class:`~msl.network.manager.Manager` for most applications using **MSL-Network**.

The :mod:`msl.network.ssh` module provides some functions for using `SSH <https://www.ssh.com/ssh/>`_
to connect to a remote computer. :ref:`ssh-example` shows an example package showing how to
automatically start a Network :class:`~msl.network.manager.Manager` and
:class:`~msl.network.service.Service` on a Raspberry Pi from another computer.

Package Structure
-----------------

.. toctree::

   msl.network <_api/msl.network>
   msl.network.cli <_api/msl.network.cli>
   msl.network.cli_argparse <_api/msl.network.cli_argparse>
   msl.network.cli_certdump <_api/msl.network.cli_certdump>
   msl.network.cli_certgen <_api/msl.network.cli_certgen>
   msl.network.cli_hostname <_api/msl.network.cli_hostname>
   msl.network.cli_keygen <_api/msl.network.cli_keygen>
   msl.network.cli_start <_api/msl.network.cli_start>
   msl.network.cli_user <_api/msl.network.cli_user>
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
