.. _ssh-example:

========================================
Starting a Service from another computer
========================================

Suppose that you wanted to start a :class:`~msl.network.service.Service` on a Raspberry Pi from
another computer that is on the same network as the Pi. Your package has the following structure::

    mypackage/
        mypackage/
            __init__.py
            rpi_service.py
            my_client.py
        setup.py

with ``setup.py`` as

.. code-block:: python

    from setuptools import setup

    setup(
        name='mypackage',
        version='0.1.0',
        packages=['mypackage'],
        install_requires=['msl-network', 'paramiko'],
        entry_points={
            'console_scripts': [
                'mypackage = mypackage:start_service_on_rpi',
            ],
        },
    )

``__init__.py`` as

.. code-block:: python

    from msl.network import manager, ssh

    from .rpi_service import RPiService
    from .my_client import MyClient

    def connect(*, hostname='raspberrypi', rpi_password=None, timeout=10, **kwargs):
        # if you installed mypackage in a virtual environment then you will
        # need to update the console_script_path value below
        console_script_path = '/home/pi/.local/bin/mypackage'
        ssh.start_manager(hostname, console_script_path, ssh_username='pi',
                          ssh_password=rpi_password, timeout=timeout, **kwargs)
        return MyClient(hostname, **kwargs)

    def start_service_on_rpi():
        kwargs = ssh.parse_console_script_kwargs()
        if kwargs.get('auth_login', False) and ('username' not in kwargs or 'password' not in kwargs):
            raise ValueError(
                'The Manager is using a login for authentication but RPiService '
                'does not know the username and password to use to connect to the Manager'
            )
        manager.run_services(RPiService(), **kwargs)

``rpi_service.py`` as

.. code-block:: python

    from msl.network import Service

    class RPiService(Service):

        def __init__(self):
            super(RPiService, self).__init__()

        def disconnect_service(self):
            # allows for RPiService to be shut down remotely by MyClient
            self._disconnect()

        def add_numbers(self, a, b, c, d):
            return a + b + c + d

        def power(self, a, n=2):
            return a ** n

and ``my_client.py`` as

.. code-block:: python

    from msl.network.client import parse_client_connect_kwargs
    from msl.network import (
        connect,
        MSLNetworkError,
    )

    class MyClient(object):

        def __init__(self, hostname, **kwargs):
            super(MyClient, self).__init__()

            self._link = None

            # connect to the Manager on the Raspberry Pi
            cxn = connect(host=hostname, **parse_client_connect_kwargs(**kwargs))

            # make a link to the Service on the Raspberry Pi
            self._link = cxn.link('RPiService')

        def __getattr__(self, item):
            def request(*args, **kwargs):
                try:
                    return getattr(self._link, item)(*args, **kwargs)
                except MSLNetworkError:
                    self.disconnect()
                    raise
            return request

        def disconnect(self):
            if self._link is not None:
                self._link.disconnect_service()
                self._link = None

        def __del__(self):
            self.disconnect()

To create a source distribution of ``mypackage`` run the following in the root
folder of your package

.. code-block:: console

   python setup.py sdist

This will create a file in ``dist/mypackage-0.1.0.tar.gz``. Copy this file to the Raspberry Pi.

Install ``mypackage-0.1.0.tar.gz`` on the Raspberry Pi using

.. code-block:: console

   sudo apt install libssl-dev
   pip3 install mypackage-0.1.0.tar.gz

*NOTE: the* ``libssl-dev`` *library is needed to build the cryptography package on the Pi.*
*It is also recommended to install the package in a virtual environment if you are familiar with them.*

In addition, install ``mypackage-0.1.0.tar.gz`` on another computer.

Finally, on the *'another'* computer you would perform the following. This would
start the Network :class:`~msl.network.manager.Manager` on the Raspberry Pi, start
the ``RPiService``, connect to the :class:`~msl.network.manager.Manager`
and :meth:`~msl.network.client.Client.link` with ``RPiService``

.. code-block:: pycon

    >>> from mypackage import connect
    >>> rpi = connect(hostname='192.168.1.65', assert_hostname=False)
    >>> rpi.add_numbers(1, 2, 3, 4)
    10
    >>> rpi.power(4)
    16
    >>> rpi.power(5, n=3)
    125

When you are done sending requests to ``RPiService`` you disconnect from the
:class:`~msl.network.service.Service` which will shut down the
Network :class:`~msl.network.manager.Manager` that is running on the Raspberry Pi

.. code-block:: pycon

    >>> rpi.disconnect()

.. tip::

   Suppose you get the following error

   .. code-block:: pycon

      >>> rpi = connect(hostname='192.168.1.65', assert_hostname=False)
      ...
      [Errno 98] error while attempting to bind on address ('::', 1875, 0, 0): address already in use

   This means that there is probably a :class:`~msl.network.manager.Manager` already running
   on the Pi at port 1875. You have three options.

   (1) Start another :class:`~msl.network.manager.Manager` on a different port

   .. code-block:: pycon

      >>> rpi = connect(hostname='192.168.1.65', assert_hostname=False, port=1876)

   (2) Connect to the :class:`~msl.network.manager.Manager` and shut it down gracefully;
       however, this requires that you are an administrator of that :class:`~msl.network.manager.Manager`.
       See the ``user`` command in :ref:`network-cli` for more details on how to create a user that
       is an administrator.

   .. code-block:: pycon

      >>> from msl.network import connect
      >>> cxn = connect(hostname='192.168.1.65', assert_hostname=False)
      >>> cxn.admin_request('shutdown_manager')

   (3) Kill the :class:`~msl.network.manager.Manager`

   .. code-block:: pycon

      >>> from msl.network import ssh
      >>> ssh_client = ssh.connect(hostname='pi@192.168.1.65')
      >>> out = ssh.exec_command(ssh_client, 'ps aux | grep mypackage')
      >>> print('\n'.join(out))
      pi  1367  0.1  2.2  63164 21380 pts/0  Sl+  12:21  0:01 /usr/bin/python3 .local/bin/mypackage
      pi  4341  0.0  0.2   4588  2512 ?      Ss   12:30  0:00 bash -c ps aux | grep mypackage
      pi  4343  0.0  0.0   4368   540 ?      S    12:30  0:00 grep mypackage
      >>> ssh.exec_command(ssh_client, 'sudo kill -9 1367')
      []
      >>> ssh_client.close()

