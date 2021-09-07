import os
import sys
import time
import shutil
import logging
import asyncio
import tempfile
import subprocess
from socket import socket
from threading import Thread

# create MSL_NETWORK_HOME before importing msl.network
root_dir = os.path.join(tempfile.gettempdir(), '.msl')
if os.path.isdir(root_dir):
    shutil.rmtree(root_dir)
home = os.path.join(root_dir, 'network')
os.makedirs(home)
os.environ['MSL_NETWORK_HOME'] = home

from msl.network import (
    connect,
    constants,
    cryptography,
    UsersTable,
)

# suppress all logging message from being displayed
logging.basicConfig(level=logging.CRITICAL+10)

# For Python 3.8 on Windows the default event loop became ProactorEventLoop.
# This caused the tests to hang when calling loop.close() for a Client
# and a Service since the IocpProactor.close() method would get stuck
# in the "while self._cache:" block. Therefore, use the SelectorEventLoop
# if running the tests on Windows with Python 3.8+.
if constants.IS_WINDOWS and sys.version_info[:2] >= (3, 8):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Manager(object):

    key_file = cryptography.get_default_key_path()
    cert_file = cryptography.get_default_cert_path()
    database = os.path.join(home, 'testing.db')
    log_file = os.path.join(home, 'testing.log')

    def __init__(self, *service_classes, disable_tls=False, password_manager=None,
                 auth_login=True, auth_hostname=False, cert_common_name=None, **kwargs):
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
        cryptography.generate_key(path=self.key_file, password=key_pw, algorithm='ecc')
        cryptography.generate_certificate(
            path=self.cert_file, key_path=self.key_file, key_password=key_pw, name=cert_common_name
        )

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
            'cert_file': self.cert_file,
            'disable_tls': disable_tls,
            'password_manager': password_manager,
        }

        # start the Network Manager in a subprocess
        command = [sys.executable, '-c', 'from msl.network import cli; cli.main()', 'start',
                   '-p', str(self.port), '-c', self.cert_file, '-k', self.key_file, '-D', key_pw,
                   '-d', self.database, '-l', self.log_file]
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

        # start all Services
        self._service_threads = {}
        if service_classes:
            cxn = connect(**self.kwargs)
            for cls in service_classes:
                name = cls.__name__
                service = cls(**kwargs)
                thread = Thread(target=service.start, kwargs=self.kwargs, daemon=True)
                thread.start()
                t0 = time.time()
                while True:
                    time.sleep(0.1)
                    services = cxn.manager()['services']
                    if name in services:
                        break
                    if time.time() - t0 > 30:
                        in_use = self.is_port_in_use(service.port)
                        self.shutdown(cxn)
                        raise RuntimeError(
                            'Cannot start {} service.\n'
                            'Is Service port in use? {}\n'
                            'Services: {}'.format(name, in_use, services)
                        )
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
        while not Manager.is_port_in_use(port):
            if time.time() - start_time > 30:
                raise RuntimeError(message)
            time.sleep(0.1)

    @staticmethod
    def wait_shutdown(port, message):
        start_time = time.time()
        while Manager.is_port_in_use(port):
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
        out, _ = p.communicate()
        return out.find(b':%d ' % port) > 0

    @staticmethod
    def get_available_port():
        with socket() as sock:
            sock.bind(('', 0))  # get any available port
            return sock.getsockname()[1]

    @staticmethod
    def remove_files():
        files = (Manager.key_file, Manager.cert_file,
                 Manager.database, Manager.log_file)
        for file in files:
            try:
                os.remove(file)
            except OSError:
                pass
