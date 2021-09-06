"""
Base class for a :class:`~msl.network.manager.Manager`,
:class:`~msl.network.service.Service` and :class:`~msl.network.client.Client`.
"""
import socket
import asyncio
import traceback
from time import perf_counter

from .json import serialize
from .constants import (
    HOSTNAME,
    TERMINATION,
    ENCODING,
)
from .cryptography import get_ssl_context
from .utils import (
    logger,
    localhost_aliases,
)


class Network(object):

    termination = TERMINATION
    """:class:`bytes`: The sequence of bytes that signify the end of the data being sent."""

    encoding = ENCODING
    """:class:`str`: The encoding to use to convert :class:`str` to :class:`bytes`."""

    def __init__(self):
        """
        Base class for the Network :class:`~msl.network.manager.Manager`,
        :class:`~msl.network.service.Service` and :class:`~msl.network.client.Client`.
        """
        self._loop = None
        self._debug = False
        self._network_name = None  # helpful for debugging who is sending what to where
        self._max_print_size = 256  # the maximum number of characters to display when debugging
        self._connection_successful = False
        self._identity_successful = False

    def identity(self):
        """The identity of a device on the network.

        All devices on the network must be able to identify themselves to any
        other device that is connected to the network. There are 3 possible types
        of network devices -- a :class:`~msl.network.manager.Manager`,
        a :class:`~msl.network.service.Service` and a :class:`~msl.network.client.Client`.
        The member names and JSON_ datatype for each network device is described below.

        .. _JSON: https://www.json.org/

        * :class:`~msl.network.manager.Manager`

            hostname: string
                The name of the device that the Network :class:`~msl.network.manager.Manager`
                is running on.

            port: integer
                The port number that the Network :class:`~msl.network.manager.Manager`
                is running on.

            attributes: object
                An object (a Python :class:`dict`) of public attributes that the Network
                :class:`~msl.network.manager.Manager` provides. Users who are an administrator of
                the Network :class:`~msl.network.manager.Manager` can access private attributes.

            language: string
                The programming language that the Network :class:`~msl.network.manager.Manager`
                is running on.

            os: string
                The name of the operating system that the :class:`~msl.network.manager.Manager`
                is running on.

            clients: object
                An object (a Python :class:`dict`) of all :class:`~msl.network.client.Client` devices
                that are currently connected to the Network :class:`~msl.network.manager.Manager`.

            services: object
                An object (a Python :class:`dict`) of all :class:`~msl.network.service.Service` devices
                that are currently connected to the Network :class:`~msl.network.manager.Manager`.

        * :class:`~msl.network.service.Service`

            type: string
                This must be equal to ``'service'`` (case-insensitive).

            name: string
                The name to associate with the :class:`~msl.network.service.Service`
                (can contain spaces).

            attributes: object
                An object (a Python :class:`dict`) of the attributes that the
                :class:`~msl.network.service.Service` provides. The keys are
                the function names and the values are the function signatures
                (expressed as a string).

                The `attributes` get populated automatically when subclassing
                :class:`~msl.network.service.Service`. If you are creating a
                `Service` in another programming language then you can use the
                following as an example for how to define an `attributes` object::

                    {
                        'pi': '() -> float'
                        'add_integers': '(x:int, y:int) -> int'
                        'scalar_multiply': '(a:float, data:*float) -> *float'
                    }

                This `Service` would provide a function named ``pi`` that takes no
                inputs and returns a floating-point number, a function named
                ``add_integers`` that takes parameters named ``x`` and ``y`` as integer
                inputs and returns an integer, and a function named ``scalar_multiply``
                that takes parameters named ``a`` as a floating-point number and ``data``
                as an array of floating-point numbers as inputs and returns an array of
                floating-point numbers.

                The key **must** be equal to the name of the function that the
                `Service` provides, however, the value (the function signature) is only
                used as a helpful guide to let a :class:`~msl.network.client.Client` know
                what the function takes as inputs and what the function returns. How you
                express the function signature is up to you. The above example could
                also be expressed as::

                    {
                        'pi': '() -> 3.1415926...'
                        'add_integers': '(x:int32, y:int32) -> x+y'
                        'scalar_multiply': '(a:float, data:array of floats) -> array of floats'
                    }

            language: string, optional
                The programming language that the :class:`~msl.network.service.Service`
                is running on.

            os: string, optional
                The name of the operating system that the :class:`~msl.network.service.Service`
                is running on.

            max_clients: integer, optional
                The maximum number of :class:`~msl.network.client.Client`\\s that can be
                linked with the :class:`~msl.network.service.Service`. If the value is
                :math:`\\leq` 0 then that means that an unlimited number of
                :class:`~msl.network.client.Client`\\s can be linked
                *(this is the default setting if max_clients is not specified)*.

        * :class:`~msl.network.client.Client`

            type: string
                This must be equal to ``'client'`` (case-insensitive).

            name: string
                The name to associate with the :class:`~msl.network.client.Client`
                (can contain spaces).

            language: string, optional
                The programming language that the :class:`~msl.network.client.Client`
                is running on.

            os: string, optional
                The name of the operating system that the :class:`~msl.network.client.Client`
                is running on.

        Returns
        -------
        :class:`dict`
            The identity of the network device.
        """
        raise NotImplementedError

    def send_line(self, writer, line):
        """Send bytes through the network.

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer to use to send the bytes.
        line : :class:`bytes`
            The bytes to send (that already end with the :attr:`termination` bytes).
        """
        if writer is None:
            # could happen if the writer is for a Service and it was executing a
            # request when Manager.shutdown_manager() was called
            return

        n = len(line)

        if self._debug:
            logger.debug(self._network_name + ' is sending {} bytes...'.format(n))
            if n > self._max_print_size:
                logger.debug(line[:self._max_print_size//2] + b' ... ' + line[-self._max_print_size//2:])
            else:
                logger.debug(line)

        t0 = perf_counter()
        writer.write(line)

        if self._debug:
            dt = perf_counter() - t0
            if dt > 0:
                logger.debug('{} sent {} bytes in {:.3g} seconds [{:.3f} MB/s]'.format(
                    self._network_name, n, dt, n*1e-6/dt))
            else:
                logger.debug('{} sent {} bytes in {:.3f} useconds'.format(self._network_name, n, dt*1e6))

    def send_data(self, writer, data):
        """Serialize `data` as a JSON_ string then send.

        .. _JSON: https://www.json.org/

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer to use to send the data.
        data
            Any object that can be serialized into a JSON_ string.
        """
        try:
            self.send_line(writer, serialize(data).encode(ENCODING) + TERMINATION)
        except Exception as e:
            try:
                self.send_error(writer, e, data['requester'])
            except KeyError:
                # fixes Issue #5
                raise e from None

    def send_error(self, writer, error, requester, *, uuid=''):
        """Send an error through the network.

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        error : :class:`Exception`
            An exception object.
        requester : :class:`str`
            The address, ``host:port``, of the device that sent the request.
        uuid : :class:`str`, optional
            The universally unique identifier of the request.
        """
        tb = traceback.format_exc()
        message = error.__class__.__name__ + ': ' + str(error)
        self.send_data(writer, {
            'error': True,
            'message': message,
            'traceback': [] if tb.startswith('NoneType:') else tb.splitlines(),
            'result': None,
            'requester': requester,
            'uuid': uuid,
        })

    def send_reply(self, writer, reply, *, requester='', uuid=''):
        """Send a reply through the network.

        .. _JSON: https://www.json.org/

        Parameters
        ----------
        writer : :class:`asyncio.WriteTransport` or :class:`asyncio.StreamWriter`
            The writer.
        reply : :class:`object`
            Any object that can be serialized into a JSON_ string.
        requester : :class:`str`, optional
            The address, ``host:port``, of the device that sent the request.
            It is only mandatory to specify the address of the `requester` if a
            :class:`~msl.network.service.Service` is sending the reply.
        uuid : :class:`str`, optional
            The universally unique identifier of the request.
        """
        self.send_data(writer, {'result': reply, 'requester': requester, 'uuid': uuid, 'error': False})

    def _create_connection(self, **kwargs):
        # common to both Client and Service to connect to the Manager
        context = None
        is_localhost = kwargs['host'] in localhost_aliases()
        if not kwargs['disable_tls']:
            try:
                cert_file, context = get_ssl_context(
                    host=kwargs['host'], port=kwargs['port'],
                    cert_file=kwargs['cert_file'], auto_save=kwargs['auto_save']
                )
            except OSError as e:
                msg = str(e)
                if ('WRONG_VERSION_NUMBER' in msg) or ('UNKNOWN_PROTOCOL' in msg):
                    msg += '\nTry setting disable_tls=True'
                elif is_localhost:
                    msg += '\nMake sure a Network Manager is running on this computer'
                else:
                    msg += '\nCannot connect to {host}:{port} to get the certificate'.format(**kwargs)
                raise ConnectionError(msg) from None

            if not context:
                return False

            kwargs['cert_file'] = cert_file
            context.check_hostname = kwargs['assert_hostname']
            logger.debug('Loaded {}'.format(cert_file))

        try:
            self._loop.run_until_complete(
                asyncio.wait_for(
                    self._loop.create_connection(
                        lambda: self,
                        host=kwargs['host'],
                        port=kwargs['port'],
                        ssl=context,
                    ),
                    kwargs['timeout']
                )
            )
        except Exception as error:
            if isinstance(error, asyncio.TimeoutError):
                raise TimeoutError(
                    'Cannot connect to {host}:{port} within {timeout} seconds'.format(**kwargs)
                ) from None

            msg = str(error)
            if msg.startswith('Multiple exceptions'):  # comes from asyncio
                msg = 'Cannot connect to {host}:{port}'.format(**kwargs)
            elif isinstance(error, (ConnectionRefusedError, socket.gaierror)):
                msg += '\nCannot connect to {host}:{port}'.format(**kwargs)
            elif 'mismatch' in msg or "doesn't match" in msg:
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
                msg += '\nYou might need to add "{} {}" to /etc/hosts'.format(
                    kwargs['host'], HOSTNAME)
            raise ConnectionError(msg) from None

        # Make sure that the Manager registered this Client/Service by requesting its identity.
        # The following fixed the case where the Manager required TLS but the Client/Service was
        # started with ``disable_tls=True``. The connection_made() function was called
        # but the Manager never saw the connection request to register the Client/Service and the
        # Client/Service never raised an exception but just waited at run_forever().
        async def check_for_identity_request():
            t0 = perf_counter()
            timeout = kwargs['timeout']
            while True:
                await asyncio.sleep(0.01)
                if self._connection_successful or self._identity_successful:
                    break
                if timeout and perf_counter() - t0 > timeout:
                    err = 'The connection to {host}:{port} was not established.'.format(**kwargs)
                    if kwargs['disable_tls']:
                        err += '\nYou have TLS disabled. Perhaps the Manager is ' \
                               'using TLS for the connection.'
                    raise ConnectionError(err)
            while not self._identity_successful:
                await asyncio.sleep(0.01)

        try:
            self._loop.run_until_complete(check_for_identity_request())
        except RuntimeError:  # raised if the authentication step failed
            return False
        else:
            return True

    def _run_forever(self):
        # common to both Client and Service to connect to the Manager
        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            logger.debug('CTRL+C keyboard interrupt received')
            self._transport.close()
        except SystemExit:
            logger.debug('SystemExit was raised')
            self._transport.close()
        finally:
            logger.info('{!r} disconnected'.format(self._network_name))
            self._loop.close()
            logger.info('{!r} closed the event loop'.format(self._network_name))
