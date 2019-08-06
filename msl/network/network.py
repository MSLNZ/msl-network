"""
Base class for a :class:`~msl.network.manager.Manager`,
:class:`~msl.network.service.Service` and :class:`~msl.network.client.Client`.
"""
import asyncio
import logging
import traceback
from time import perf_counter

from .json import serialize
from .constants import HOSTNAME
from .cryptography import get_ssl_context
from .exceptions import MSLNetworkError

log = logging.getLogger(__name__)


class Network(object):

    termination = b'\r\n'
    """:class:`bytes`: The sequence of bytes that signify the end of the data being sent."""

    encoding = 'utf-8'
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
        self._connection_established = False
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
            log.debug(self._network_name + ' is sending {} bytes...'.format(n))
            if n > self._max_print_size:
                log.debug(line[:self._max_print_size//2] + b' ... ' + line[-self._max_print_size//2:])
            else:
                log.debug(line)

        t0 = perf_counter()
        writer.write(line)

        if self._debug:
            dt = perf_counter() - t0
            if dt > 0:
                log.debug('{} sent {} bytes in {:.3g} seconds [{:.3f} MB/s]'.format(
                    self._network_name, n, dt, n*1e-6/dt))
            else:
                log.debug('{} sent {} bytes in {:.3f} useconds'.format(self._network_name, n, dt*1e6))

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
            self.send_line(writer, serialize(data).encode(Network.encoding) + Network.termination)
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

    def _create_connection(self, host, port, certfile, disable_tls, assert_hostname, timeout):
        # common to both Client and Service to connect to the Manager

        context = None
        if not disable_tls:
            certfile, context = get_ssl_context(host=host, port=port, certfile=certfile)
            if not context:
                return False

            if not assert_hostname:
                context.check_hostname = False
            else:
                context.check_hostname = host != HOSTNAME

        try:
            self._loop.run_until_complete(
                self._loop.create_connection(
                    lambda: self,
                    host=host,
                    port=port,
                    ssl=context,
                ),
            )
        except Exception as e:
            err = str(e)
            if 'match' in err:
                err += '\nTo disable hostname checking set assert_hostname=False\n' \
                       'Make sure that you trust the connection if you do this'
            elif 'CERTIFICATE_VERIFY_FAILED' in err:
                err += '\nPerhaps the Network Manager is using a new certificate...\n' \
                       'If you trust the network connection then you can delete ' \
                       'the certificate at\n{}\nand then re-connect to the Network Manager ' \
                       'to create a new trusted certificate'.format(certfile)
            elif ('WRONG_VERSION_NUMBER' in err) or ('UNKNOWN_PROTOCOL' in err):
                err += '\nTry setting disable_tls=True'
            elif 'Errno 10061' in err:
                err += '\nMake sure that a Network Manager is running at {}:{}'.format(host, port)
            raise MSLNetworkError(err) from None

        # Make sure that the Manager registered this Client/Service by requesting its identity.
        # The following fixed the case where the Manager required TLS but the Client/Service was
        # started with ``disable_tls=True``. The connection_made() function was called
        # but the Manager never saw the connection request to register the Client/Service and the
        # Client/Service never raised an exception but just waited at run_forever().
        async def check_for_identity_request():
            t0 = perf_counter()
            while True:
                await asyncio.sleep(0.01)
                if self._connection_established or self._identity_successful:
                    break
                if timeout and perf_counter() - t0 > timeout:
                    msg = 'The connection to the Network Manager was not established.'
                    if disable_tls:
                        msg += '\nYou have TLS disabled. Perhaps the Manager is using TLS for the connection.'
                    raise TimeoutError(msg)
            while not self._identity_successful:
                await asyncio.sleep(0.01)

        try:
            self._loop.run_until_complete(check_for_identity_request())
        except RuntimeError:  # raised if the authentication step failed
            return False
        else:
            return True
