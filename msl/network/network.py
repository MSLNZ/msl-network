"""
Base classes for a :class:`~msl.network.manager.Manager`,
:class:`~msl.network.service.Service` and :class:`~msl.network.client.Client`.
"""
import asyncio
import getpass
import socket
import sys
import threading
import traceback
from typing import Union

from .constants import HOSTNAME
from .constants import LOCALHOST_ALIASES
from .cryptography import get_ssl_context
from .json import deserialize
from .json import serialize
from .utils import _is_manager_regex
from .utils import logger


class Network(object):

    def __init__(self):
        """Base class for the :class:`~msl.network.manager.Manager`,
        :class:`~msl.network.service.Service` and
        :class:`~msl.network.client.Client`.
        """
        self._loop = None
        self._reader = None
        self._writer = None
        self._identity = None
        self._network_name = '<UNKNOWN>'  # name[host:port]
        self._max_debug_length = 256

    def __str__(self):
        return self._network_name

    def identity(self) -> dict:
        """The identity of a device on the network.

        All devices on the network must be able to identify themselves to any
        other device that is connected to the network. There are 3 possible
        types of network devices -- a :class:`~msl.network.manager.Manager`,
        a :class:`~msl.network.service.Service` and a
        :class:`~msl.network.client.Client`. The member names and JSON_ datatype
        for each network device is described below.

        .. _JSON: https://www.json.org/

        * :class:`~msl.network.manager.Manager`

            hostname: string
                The name of the computer that the Network
                :class:`~msl.network.manager.Manager` is running on.

            port: integer
                The port number that the Network
                :class:`~msl.network.manager.Manager` is running on.

            attributes: object
                An object (a Python :class:`dict`) of public attributes that the
                Network :class:`~msl.network.manager.Manager` provides. Users
                who are an administrator of the Network
                :class:`~msl.network.manager.Manager` can request private
                attributes, see :meth:`~msl.network.client.Client.admin_request`.

            language: string
                The programming language that the Network
                :class:`~msl.network.manager.Manager` is running on.

            os: string
                The name of the operating system that the Network
                :class:`~msl.network.manager.Manager` is running on.

            clients: object
                An object (a Python :class:`dict`) of all
                :class:`~msl.network.client.Client` devices that are currently
                connected to the Network :class:`~msl.network.manager.Manager`.

            services: object
                An object (a Python :class:`dict`) of all
                :class:`~msl.network.service.Service` devices that are currently
                connected to the Network :class:`~msl.network.manager.Manager`.

        * :class:`~msl.network.service.Service`

            type: string
                This must be equal to ``'service'`` (case-insensitive).

            name: string
                The name to associate with the
                :class:`~msl.network.service.Service` (can contain spaces).

            attributes: object
                An object (a Python :class:`dict`) of the attributes that the
                :class:`~msl.network.service.Service` provides. The keys are
                the method names and the values are the method signatures
                (expressed as a string).

                The `attributes` get populated automatically when subclassing
                :class:`~msl.network.service.Service`. If you are creating a
                `Service` in another programming language then you can use the
                following as an example for how to define an `attributes` object::

                    {
                      "pi": "() -> float",
                      "add_integers": "(x:int, y:int) -> int",
                      "scalar_multiply": "(a:float, data:List[floats]) -> List[floats]"
                    }

                This `Service` would provide a method named ``pi`` that takes
                no inputs and returns a floating-point number, a method named
                ``add_integers`` that takes parameters named ``x`` and ``y`` as
                integer inputs and returns an integer, and a method named
                ``scalar_multiply`` that takes parameters named ``a`` as a
                floating-point number and ``data`` as an array of floating-point
                numbers as inputs and returns an array of floating-point numbers.

                The key **must** be equal to the name of the method that the
                `Service` provides; however, the value (the method signature)
                is only used as a helpful guide to let a
                :class:`~msl.network.client.Client` know what the method takes
                as inputs and what the method returns. How you express the
                method signature is up to you. The above example could also
                be expressed as::

                    {
                      "pi": "() -> 3.1415926...",
                      "add_integers": "(int32 x, int32 y) -> x+y",
                      "scalar_multiply": "(double a, *double data) -> *double"
                    }

            language: string, optional
                The programming language that the
                :class:`~msl.network.service.Service` is running on.

            os: string, optional
                The name of the operating system that the
                :class:`~msl.network.service.Service` is running on.

            max_clients: integer, optional
                The maximum number of :class:`~msl.network.client.Client`\\s
                that can be linked with the :class:`~msl.network.service.Service`.
                If the value is :math:`\\leq` 0 then that means that an unlimited
                number of :class:`~msl.network.client.Client`\\s can be linked
                *(this is the default setting if max_clients is not specified)*.

        * :class:`~msl.network.client.Client`

            type: string
                This must be equal to ``'client'`` (case-insensitive).

            name: string
                The name to associate with the
                :class:`~msl.network.client.Client` (can contain spaces).

            language: string, optional
                The programming language that the
                :class:`~msl.network.client.Client` is running on.

            os: string, optional
                The name of the operating system that the
                :class:`~msl.network.client.Client` is running on.

        Returns
        -------
        :class:`dict`
            The identity of the network device.
        """
        return self._identity

    @staticmethod
    def set_logging_level(level: Union[str, int]) -> bool:
        """Set the :ref:`logging level <levels>`.

        Parameters
        ----------
        level : :class:`int` or :class:`str`
            The logging level of the ``msl.network`` logger.

        Returns
        -------
        :class:`bool`
            Whether setting the logging level was successful.
        """
        if isinstance(level, str):
            try:
                level = int(level)  # allow for "20" (as a string)
            except ValueError:
                level = level.upper()

        try:
            logger.setLevel(level)
        except (ValueError, TypeError):
            logger.error('invalid logging level %r', level)
            return False
        else:
            return True

    async def _write(self, message, *, writer=None):
        """Serialize, append the termination and write it to the stream.

        Parameters
        ----------
        message : :class:`dict`
            A request or a response.
        writer : :class:`asyncio.StreamWriter`, optional
            The writer to use to write the data. If not specified then uses
            the writer of this class.
        """
        if writer is None:
            writer = self._writer
        writer.write(f'{serialize(message)}\r\n'.encode('utf-8'))
        await writer.drain()

    async def _write_result(self, result, *, requester=None, uid='', writer=None,
                            **ignored):  # noqa
        """Write a result message to the stream.

        Parameters
        ----------
        result
            The result of a request. Must be a JSON-serializable object, or
            have a to_json() method.
        requester : :class:`str`, optional
            The name of the device that sent the request.
        uid : :class:`str`, optional
            The unique identifier of the request.
        writer : :class:`asyncio.StreamWriter`, optional
            The writer to use to write the data. If not specified then uses
            the writer of this class.
        """
        data = {
            'error': False,
            'requester': requester,
            'result': result,
            'uid': uid
        }
        await self._write(data, writer=writer)

    async def _write_error(self, error, *, requester=None, uid='', writer=None,
                           **ignored):  # noqa
        """Write an error message to the stream.

        Parameters
        ----------
        error : :class:`Exception`
            An exception object.
        requester : :class:`str`, optional
            The name of the device that sent the request.
        uid : :class:`str`, optional
            The unique identifier of the request.
        writer : :class:`asyncio.StreamWriter`, optional
            The writer to use to write the data. If not specified then uses
            the writer of this class.
        """
        e = traceback.format_exc()
        data = {
            'error': True,
            'message': f'{error.__class__.__name__}: {error}',
            'requester': requester,
            'result': None,
            'traceback': [] if e.startswith('NoneType:') else e.splitlines(),
            'uid': uid
        }
        await self._write(data, writer=writer)


class Device(Network):

    def __init__(self, name=None):
        """Base class for a :class:`~msl.network.service.Service` and
        :class:`~msl.network.client.Client`.

        .. versionadded:: 1.0

        Parameters
        ----------
        name : :class:`str`, optional
            The name of the device as it will appear on the Network
            :class:`~msl.network.manager.Manager`. If not specified
            then the class name is used.
        """
        super(Device, self).__init__()
        self._address_manager = None
        self._name = self.__class__.__name__ if name is None else name
        self._password = None
        self._password_manager = None
        self._port = None
        self._queue = None
        self._tasks = []
        self._username = None
        self._loop_thread_id = None

    @property
    def address_manager(self):
        """:class:`str`: The address of the :class:`~msl.network.manager.Manager`
        that this device is connected to."""
        return self._address_manager

    @property
    def loop_thread_id(self):
        """Identifier of the thread running the event loop.

        Returns :data:`None` if the event loop is not running.

        .. versionadded:: 1.0
        """
        return self._loop_thread_id

    @property
    def name(self):
        """:class:`str`: The name of the device on the
        :class:`~msl.network.manager.Manager`."""
        return self._name

    @property
    def port(self):
        """:class:`int`: The port number of this device that is being used for
        the connection to the :class:`~msl.network.manager.Manager`."""
        return self._port

    def add_tasks(self, *coros_or_futures):
        """Additional tasks to run in the event loop.

        .. versionadded:: 1.0

        Parameters
        ----------
        coros_or_futures
            Coroutines or futures that will be passed to
            :func:`asyncio.gather` when the event loop runs.
        """
        self._tasks.extend(coros_or_futures)

    def shutdown_handler(self):
        """Called after the connection to the Network
        :class:`~msl.network.manager.Manager` has been lost but before
        the event loop stops.

        Override this method to do any necessary cleanup.

        .. versionadded:: 1.0
        """
        pass

    def _create_connection(self, **kwargs):
        self._address_manager = '{host}:{port}'.format(**kwargs)
        self._username = kwargs['username']
        self._password = kwargs['password']
        self._password_manager = kwargs['password_manager']

        # get SSL context
        context = None
        if not kwargs['disable_tls']:
            # In Python 3.10, ssl.get_server_certificate() accepts a timeout parameter
            kws = {'timeout': kwargs['timeout']} if sys.version_info[:2] >= (3, 10) else {}
            try:
                cert_file, context = get_ssl_context(
                    cert_file=kwargs['cert_file'],
                    host=kwargs['host'],
                    port=kwargs['port'],
                    auto_save=kwargs['auto_save'],
                    **kws
                )
            except OSError as error:
                e = str(error)
                if ('WRONG_VERSION_NUMBER' in e) or ('UNKNOWN_PROTOCOL' in e):
                    e += '\nTry setting disable_tls=True'
                elif kwargs['host'] in LOCALHOST_ALIASES:
                    e += '\nMake sure a Manager is running on this computer'
                else:
                    e += '\nCannot connect to {host}:{port} to get the ' \
                         'certificate'.format(**kwargs)
                raise ConnectionError(e) from None

            if context is None:
                # then the user chose to not accept the SSL certificate
                return

            context.check_hostname = kwargs['assert_hostname']
            logger.debug('loaded %s', cert_file)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if kwargs['read_limit'] is None:
            kwargs['read_limit'] = sys.maxsize

        # connect
        try:
            self._reader, self._writer = loop.run_until_complete(
                asyncio.wait_for(
                    asyncio.open_connection(
                        host=kwargs['host'],
                        port=kwargs['port'],
                        ssl=context,
                        limit=kwargs['read_limit'],
                    ),
                    kwargs['timeout']
                )
            )
        except Exception as error:
            if isinstance(error, asyncio.TimeoutError):
                raise TimeoutError(
                    'Cannot connect to {host}:{port} within '
                    '{timeout} seconds'.format(**kwargs)
                ) from None

            msg = str(error)
            if msg.startswith('Multiple exceptions'):  # comes from asyncio
                msg = 'Cannot connect to {host}:{port}'.format(**kwargs)
            elif isinstance(error, (ConnectionRefusedError, socket.gaierror)):
                msg += '\nCannot connect to {host}:{port}'.format(**kwargs)
            elif ('name mismatch' in msg) or ('address mismatch' in msg):
                msg += '\nTo disable hostname checking set assert_hostname=False\n' \
                       'Make sure you trust the connection to {host}:{port} ' \
                       'if you decide to do this.'.format(**kwargs)
            elif 'CERTIFICATE_VERIFY_FAILED' in msg:
                msg += '\nPerhaps the Network Manager is using a new certificate.\n' \
                       'If you trust the connection to {host}:{port}, you can delete ' \
                       'the certificate at\n  {cert_file}\nand then re-connect to ' \
                       'create a new trusted certificate.'.format(**kwargs)
            elif ('WRONG_VERSION_NUMBER' in msg) or ('UNKNOWN_PROTOCOL' in msg):
                msg += '\nTry setting disable_tls=True'
            elif 'nodename nor servname provided' in msg:
                host = kwargs['host']
                msg += f'\nYou might need to add "{host} {HOSTNAME}" to /etc/hosts'
            raise ConnectionError(msg) from None

        # authenticate
        try:
            line = loop.run_until_complete(
                asyncio.wait_for(self._reader.readline(), kwargs['timeout']))
        except asyncio.TimeoutError:
            msg = 'The connection to {host}:{port} was not established after ' \
                  '{timeout} second(s)'.format(**kwargs)
            if kwargs['disable_tls']:
                msg += '\nYou have TLS disabled. Perhaps the Manager is ' \
                       'using TLS for the connection.'
            raise ConnectionError(msg) from None
        else:
            loop.run_until_complete(self._authenticate(line))

        return loop

    def _run_until_complete(self):
        # Run all tasks until complete

        # must instantiate the Queue after the connection has been established
        # since self._create_connection creates a new event loop
        self._queue = asyncio.Queue()

        self._loop_thread_id = threading.get_ident()

        try:
            self._loop.run_until_complete(self._gather())
        except KeyboardInterrupt:
            logger.debug('CTRL+C keyboard interrupt')
        except SystemExit:
            logger.debug('SystemExit raised')
        except Exception as e:
            logger.exception(e)
        finally:
            self._reader.feed_eof()
            self._loop.run_until_complete(self._queue.join())
            self._writer.close()
            self._loop.run_until_complete(self._writer.wait_closed())
            self._loop.close()
            self._loop_thread_id = None
            try:
                logger.info('disconnected from Manager[%s]', self._address_manager)
            except (NameError, ValueError):
                # These errors could occur when Python is exiting
                #   ValueError: I/O operation on closed file
                #   NameError: name 'open' is not defined
                pass

    async def _authenticate(self, line):
        # The Manager may ask for a username/password and will always request
        # the identity of the connecting device
        logger.debug('start authentication')
        while True:
            request = deserialize(line)
            if request['error']:
                raise ValueError(request['message'])
            identified = await self._handle_manager_request(request)
            if identified:
                break
            line = await self._reader.readline()
        logger.debug('finish authentication')

    async def _gather(self):
        # Gather all tasks
        await asyncio.gather(*self._tasks)

    async def _handle_manager_request(self, request):
        # Handle a request from a Manager
        logger.debug('Manager[%s] requested %r', self._address_manager,
                     request['attribute'])

        if request['attribute'] == 'identity':
            await self._write_result(self._identity)
            self._port = int(self._writer.get_extra_info('sockname')[1])
            self._network_name = f'{self._name}[{HOSTNAME}:{self._port}]'
            logger.info('connected to Manager[%s] as %s',
                        self._address_manager, self._network_name)
            return True
        elif request['attribute'] == 'username':
            if self._username is None:
                name = request['args'][0]
                self._username = input(f'Enter a username for {name} > ')
            await self._write_result(self._username, **request)
        elif request['attribute'] == 'password':
            def get():
                return getpass.getpass(f'Enter the password for {name} > ')

            name = request['args'][0]
            if _is_manager_regex.search(name) is not None:
                if self._password_manager is None:
                    self._password_manager = get()
                password = self._password_manager
            else:
                if self._password is None:
                    self._password = get()
                password = self._password

            await self._write_result(password, **request)
        else:
            assert False, 'should not get here!'
