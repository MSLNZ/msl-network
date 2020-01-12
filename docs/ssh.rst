.. _ssh-example:

========================================
Starting a Service from another computer
========================================

Suppose that you wanted to start a :class:`~msl.network.service.Service` on a remote computer,
for example, a Raspberry Pi, from another computer that is on the same network as the Pi.

Your package has the following structure::

    mypackage/
        mypackage/
            __init__.py
            my_client.py
            rpi_service.py
        setup.py

with ``setup.py`` as

.. code-block:: python

    from setuptools import setup

    setup(
        name='mypackage',
        version='0.1.0',
        packages=['mypackage'],
        install_requires=['msl-network'],
        entry_points={
            'console_scripts': [
                'mypackage = mypackage:start_service_on_rpi',
            ],
        },
    )

``__init__.py`` as

.. code-block:: python

    from msl.network import run_services, ssh, LinkedClient

    from .rpi_service import RPiService
    from .my_client import MyClient

    def connect(*, host='raspberrypi', rpi_password=None, timeout=10, **kwargs):
        # you will need to update the `console_script_path` value below
        # when you implement the code in your own program since this is a unique path
        # that is defined as the path where the mypackage executable is located on the Pi
        console_script_path = '/home/pi/.local/bin/mypackage'
        ssh.start_manager(host, console_script_path, ssh_username='pi',
                          ssh_password=rpi_password, timeout=timeout, **kwargs)

        # create a Client that is linked with a Service of your choice
        # in this case it is the RPiService
        kwargs['host'] = host
        return MyClient('RPiService', **kwargs)

    def start_service_on_rpi():
        # this function gets called from your `console_scripts` definition in setup.py
        kwargs = ssh.parse_console_script_kwargs()
        if kwargs.get('auth_login', False) and ('username' not in kwargs or 'password' not in kwargs):
            raise ValueError(
                'The Manager is using a login for authentication but RPiService '
                'does not know the username and password to use to connect to the Manager'
            )
        run_services(RPiService(), **kwargs)

``rpi_service.py`` as

.. code-block:: python

    from msl.network import Service

    class RPiService(Service):

        def __init__(self):
            super(RPiService, self).__init__()

        def shutdown_service(self, *args, **kwargs):
            # Implementing this method allows for the RPiService to be
            # shut down remotely by MyClient. MyClient can also include
            # *args and **kwargs to the shutdown_service() method.
            # If there is nothing that needs to be performed before the
            # RPiService shuts down then just return None.
            # After the shutdown_service() method returns, the RPiService
            # will automatically wait for all Futures that it is currently
            # executing to either finish or to be cancelled before the
            # RPiService disconnects from the Network Manager.

        def add_numbers(self, a, b, c, d):
            return a + b + c + d

        def power(self, a, n=2):
            return a ** n

and ``my_client.py`` as

.. code-block:: python

    from msl.network import LinkedClient

    class MyClient(LinkedClient):

        def __init__(self, service_name, **kwargs):
            super(MyClient, self).__init__(service_name, **kwargs)

        def disconnect(self):
            # We override the `disconnect` method because we want to shut
            # down the RPiService and the Network Manager when MyClient
            # disconnects from the Raspberry Pi. You don't always want to
            # shut down a Service and the Manager when a Client disconnects
            # from the Manager and so we wouldn't override this method. The
            # Manager might have other Services running on it that other
            # Clients are using. Also, not every Service will allow a Client
            # to shut it down. However, we have decided to design mypackage
            # in a particular way that MyClient is intended to be the only
            # Client connected to the Manager and when MyClient is done
            # communicating with the RPiService then everything shuts down.
            # The Client can also include *args and **kwargs in the
            # shutdown_service() request, but we don't use them in this example.
            self.shutdown_service()
            super(MyClient, self).disconnect()

        def service_error_handler(self):
            # We override this method to shut down the RPiService and the
            # Manager if there was an error on the RPiService. In general,
            # if a Service raises an exception you wouldn't want it to shut
            # down because you would have to manually restart it. Especially
            # if other Clients in other peoples code are requesting information
            # from that Service it can become frustrating. However, for
            # mypackage we want everything to shut down (RPiService, MyClient
            # and the Manager) when any one of them raises an exception.
            self.disconnect()

To create a source distribution of ``mypackage`` run the following in the root folder of your
package directory

.. code-block:: console

   python setup.py sdist

This will create a file ``dist/mypackage-0.1.0.tar.gz``. Copy this file to the Raspberry Pi.

.. note::

   The ``libssl-dev`` and ``libffi-dev`` libraries that are specified below are needed to build
   the cryptography_ package from source on the Raspberry Pi. It is also recommended to install
   ``mypackage`` in a `virtual environment`_ if you are familiar with them. However, in what
   follows we show how to install ``mypackage`` without using a `virtual environment`_ for
   simplicity.

   Sometimes running the ``pip3 install mypackage-0.1.0.tar.gz`` command can raise an error.
   Try running the command a few times since it might just be a temporary network issue on the Pi.

Install ``mypackage-0.1.0.tar.gz`` on the Raspberry Pi using

.. code-block:: console

   sudo apt install libssl-dev libffi-dev
   pip3 install mypackage-0.1.0.tar.gz

In addition, install ``mypackage-0.1.0.tar.gz`` on another computer.

Finally, on the *'another'* computer you would perform the following. This would
start the Network :class:`~msl.network.manager.Manager` on the Raspberry Pi, start
the ``RPiService``, connect to the :class:`~msl.network.manager.Manager`
and :meth:`~msl.network.client.Client.link` with ``RPiService``.

You will have to change the value of *host* below for your Raspberry Pi. The reason for including
``assert_hostname=False`` is because we specify an IP address for the value of `host` instead of its
hostname. The hostname of the Raspberry Pi is (most likely) ``'raspberrypi'`` and so ``'192.168.1.65'``
does not equal ``'raspberrypi'`` when the security of the connection is checked behind the scenes.
If you specify the hostname of the Raspberry Pi then you can do hostname verification and not include
the ``assert_hostname`` keyword argument. In general, use ``assert_hostname=False`` at your own risk
if there is a possibility of a man-in-the-middle hijack in your connection to the Pi.

.. code-block:: pycon

    >>> from mypackage import connect
    >>> rpi = connect(host='192.168.1.65', assert_hostname=False)
    >>> rpi.add_numbers(1, 2, 3, 4)
    10
    >>> rpi.power(4)
    16
    >>> rpi.power(5, n=3)
    125

When you are done sending requests to ``RPiService`` you call the ``disconnect`` method which
will shut down the ``RPiService`` and the Network :class:`~msl.network.manager.Manager` that are
running on the Raspberry Pi and disconnect ``MyClient`` from the Pi.

.. code-block:: pycon

    >>> rpi.disconnect()

.. tip::

   Suppose that you get the following error

   .. code-block:: pycon

      >>> rpi = connect(host='192.168.1.65', assert_hostname=False)
      ...
      [Errno 98] error while attempting to bind on address ('::', 1875, 0, 0): address already in use

   This means that there is probably a :class:`~msl.network.manager.Manager` already running
   on the Raspberry Pi at port 1875. You have four options to solve this problem using **MSL-Network**.

   (1) Start another :class:`~msl.network.manager.Manager` on a different port

   .. code-block:: pycon

      >>> rpi = connect(host='192.168.1.65', assert_hostname=False, port=1876)

   (2) Connect to the :class:`~msl.network.manager.Manager` and shut it down gracefully;
       however, this requires that you are an administrator of that :class:`~msl.network.manager.Manager`.
       See the ``user`` command in :ref:`network-cli` for more details on how to create a user that
       is an administrator.

   .. code-block:: pycon

      >>> from msl.network import connect
      >>> cxn = connect(host='192.168.1.65', assert_hostname=False)
      >>> cxn.admin_request('shutdown_manager')

   (3) Kill the :class:`~msl.network.manager.Manager`

   .. code-block:: pycon

      >>> from msl.network import ssh
      >>> ssh_client = ssh.connect('pi@192.168.1.65')
      >>> out = ssh.exec_command(ssh_client, 'ps aux | grep mypackage')
      >>> print('\n'.join(out))
      pi  1367  0.1  2.2  63164 21380 pts/0  Sl+  12:21  0:01 /usr/bin/python3 .local/bin/mypackage
      pi  4341  0.0  0.2   4588  2512 ?      Ss   12:30  0:00 bash -c ps aux | grep mypackage
      pi  4343  0.0  0.0   4368   540 ?      S    12:30  0:00 grep mypackage
      >>> ssh.exec_command(ssh_client, 'sudo kill -9 1367')
      []
      >>> ssh_client.close()

   (4) Reboot the remote computer

   .. code-block:: pycon

      >>> from msl.network import ssh
      >>> ssh_client = ssh.connect('pi@192.168.1.65')
      >>> ssh.exec_command(ssh_client, 'sudo reboot')
      []
      >>> ssh_client.close()

.. _cryptography: https://cryptography.io/en/latest/
.. _virtual environment: https://docs.python.org/3/tutorial/venv.html
