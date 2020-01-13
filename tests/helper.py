"""
This is module contains a helper class to allow one to
easily start multiple Services that are used for testing purposes.
"""
import os
import sys
import time
import tempfile
import logging
import subprocess
from socket import socket
from threading import Thread

try:
    from msl.network import cryptography, UsersTable, connect
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
    from msl.network import cryptography, UsersTable, connect

# suppress all logging message from being displayed
logging.basicConfig(level=logging.CRITICAL+10)


class ServiceStarter(object):

    keyfile = tempfile.gettempdir() + '/msl-network-testing.key'
    certfile = tempfile.gettempdir() + '/msl-network-testing.crt'
    database = tempfile.gettempdir() + '/msl-network-testing.db'
    logfile = tempfile.gettempdir() + '/msl-network-testing.log'

    def __init__(self, *service_classes, disable_tls=False, password_manager=None,
                 auth_login=True, auth_hostname=False, **kwargs):
        """Starts the Network Manager and all specified Services to use for testing.

        Parameters
        ----------
        service_classes
            The Service sub-classes to start (they have NOT been instantiated).
        **kwargs
            These are all sent to Service.__init__ for all `service_classes`.
        """
        self.port = self.get_available_port()
        self.auth_hostname = auth_hostname
        self.auth_login = auth_login
        self.debug = False
        self.disable_tls = disable_tls
        self._manager_proc = None

        self.remove_files()

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
            'disable_tls': disable_tls,
            'password_manager': password_manager,
        }

        # start the Network Manager in a subprocess
        command = [sys.executable, '-c', 'from msl.network import cli; cli.main()', 'start',
                   '-p', str(self.port), '-c', self.certfile, '-k', self.keyfile, '-D', key_pw,
                   '-d', self.database, '-l', self.logfile]
        if disable_tls:
            command.append('--disable-tls')
        if password_manager:
            command.extend(['-P', password_manager])
        elif auth_hostname:
            command.append('--auth-hostname')
        elif auth_login:
            command.append('--auth-login')

        # start the Network Manager
        self._manager_proc = subprocess.Popen(command)
        self.wait_start(self.port, 'Cannot start Manager')

        # start all Service's
        cxn = connect(**self.kwargs)  # checks that the Service is running
        self._service_threads = {}
        for cls in service_classes:
            service = cls(**kwargs)
            thread = Thread(target=service.start, kwargs=self.kwargs, daemon=True)
            thread.start()
            start_time = time.time()
            while service._name not in cxn.manager()['services']:
                time.sleep(0.1)
                if time.time() - start_time > 30:
                    self.shutdown(cxn)
                    raise RuntimeError('Cannot start {}'.format(service))
            self._service_threads[service] = thread
        cxn.disconnect()

    def shutdown(self, connection=None):
        # shutdown the Manager and delete the dummy files that were created
        if connection is None:
            connection = connect(**self.kwargs)

        connection.admin_request('shutdown_manager')
        self._manager_proc.communicate(timeout=5)

        self.wait_shutdown(connection.port, '{} will not shutdown'.format(connection))
        for service, thread in self._service_threads.items():
            self.wait_shutdown(service.port, '{} will not shutdown'.format(service))

        self.remove_files()

    def __del__(self):
        if self._manager_proc is not None:
            self._manager_proc.terminate()
            self._manager_proc = None

    @staticmethod
    def wait_start(port, message):
        start_time = time.time()
        while not ServiceStarter.is_port_in_use(port):
            if time.time() - start_time > 30:
                raise RuntimeError(message)
            time.sleep(0.1)

    @staticmethod
    def wait_shutdown(port, message):
        start_time = time.time()
        while ServiceStarter.is_port_in_use(port):
            if time.time() - start_time > 30:
                raise RuntimeError(message)
            time.sleep(0.1)

    @staticmethod
    def is_port_in_use(port):
        if port is None:
            return False
        if sys.platform == 'darwin':
            cmd = ['lsof', '-nP', '-iTCP:%d' % port]
        else:
            cmd = ['netstat', '-an']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.communicate()[0]
        return out.find(b':%d ' % port) > 0

    @staticmethod
    def get_available_port():
        with socket() as sock:
            sock.bind(('', 0))  # get any available port
            return sock.getsockname()[1]

    @staticmethod
    def remove_files():
        files = (ServiceStarter.keyfile, ServiceStarter.certfile, ServiceStarter.database, ServiceStarter.logfile)
        for file in files:
            if os.path.isfile(file):
                # the logging file might not have closed yet
                if file == ServiceStarter.logfile:
                    try:
                        os.remove(file)
                    except PermissionError:
                        pass
                else:
                    os.remove(file)
