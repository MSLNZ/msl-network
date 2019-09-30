"""
This is module contains a helper class to allow one to
easily start multiple Services that are used for testing purposes.
"""
import os
import time
import tempfile
import logging
from socket import socket
from threading import Thread

from msl.network import manager, cryptography, UsersTable

# suppress all logging message from being displayed
logging.basicConfig(level=logging.CRITICAL+10)


class ServiceStarter(object):

    def __init__(self, service_classes, sleep=1, ignore_attrs=None, **kwargs):
        """Starts the Network Manager and all specified Services to use for testing.

        Parameters
        ----------
        service_classes : tuple of msl.network.service.Service
            The Service sub-classes to start (they have NOT been instantiated).
        sleep : float, optional
            The number of second to wait after starting the Manager and each Service.
        ignore_attrs : list of str
            Passed to Service.ignore_attributes
        **kwargs
            These are all sent to Service.__init__ for all `service_classes`.
        """
        with socket() as sock:
            sock.bind(('', 0))  # get any available port
            port = sock.getsockname()[1]

        # the args in cli_start.execute(args) requires that the following CLI arguments are available:
        # port, auth_password, auth_hostname, auth_login, certfile, keyfile, keyfile_password, database, debug

        self.port = port
        self.auth_password = None
        self.auth_hostname = False
        self.auth_login = True
        self.debug = False
        self.disable_tls = False

        filename = 'msl-network-testing'
        self.keyfile = tempfile.gettempdir() + '/' + filename + '.key'
        self.certfile = tempfile.gettempdir() + '/' + filename + '.crt'
        self.database = tempfile.gettempdir() + '/' + filename + '.db'

        self.cleanup()

        key_pw = 'dummy pw!'  # use a password for the key.. just for fun
        cryptography.generate_key(path=self.keyfile, password=key_pw, algorithm='ecc')
        cryptography.generate_certificate(path=self.certfile, key_path=self.keyfile, key_password=key_pw)

        # need a UsersTable with an administrator to be able to shutdown the Manager
        ut = UsersTable(database=self.database)
        self.admin_username, self.admin_password = 'admin', 'whatever'
        ut.insert(self.admin_username, self.admin_password, True)
        ut.close()

        # a convenience dictionary for connecting to the Manager as a Service or a Client
        self.kwargs = {
            'username': self.admin_username,
            'password': self.admin_password,
            'port': self.port,
            'certfile': self.certfile,
        }

        # start the Network Manager
        self._manager_thread = Thread(
            target=manager.run_forever,
            kwargs={'port': port, 'certfile': self.certfile, 'keyfile': self.keyfile,
                    'keyfile_password': key_pw, 'database': self.database, 'auth_login': True},
            daemon=True
        )
        self._manager_thread.start()
        time.sleep(sleep)  # wait for the Manager to be running

        # start all Service's
        self._service_threads = []
        for cls in service_classes:
            service = cls(**kwargs)
            if ignore_attrs:
                service.ignore_attributes(ignore_attrs)
            self._service_threads.append(Thread(target=service.start, kwargs=self.kwargs, daemon=True))
            self._service_threads[-1].start()
            time.sleep(sleep)  # wait for the Service to be running

    def cleanup(self):
        time.sleep(0.5)
        for item in (self.keyfile, self.certfile, self.database):
            if os.path.isfile(item):
                os.remove(item)

    def shutdown(self, connection):
        # shutdown the Manager and delete the dummy files that were created
        connection.admin_request('shutdown_manager')
        connection.disconnect()
        for t in self._service_threads:
            t.join()
        self._manager_thread.join()
        self.cleanup()
