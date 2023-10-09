"""
Base class for all Services.
"""
import inspect
import platform
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from .constants import DISCONNECT_REQUEST
from .constants import NOTIFICATION_UID
from .constants import PORT
from .constants import SHUTDOWN_SERVICE
from .json import deserialize
from .json import serialize
from .network import Device
from .utils import logger


class Service(Device):

    def __init__(self, *, name=None, max_clients=None, ignore_attributes=None):
        """Base class for all Services.

        .. versionadded:: 0.4
            The `name` and `max_clients` keyword argument.

        .. versionadded:: 0.5
            The `ignore_attributes` keyword argument.

        .. versionadded:: 1.0
            If a method of the Service returns an object that is not natively
            JSON serializable, then the returned object can have a callable
            ``to_json()`` method and the value returned by ``to_json()`` will be
            used in the response to the :class:`~msl.network.client.Client`.

        Parameters
        ----------
        name : :class:`str`, optional
            The name of the Service as it will appear on the Network
            :class:`~msl.network.manager.Manager`. If not specified
            then the class name is used. You can also specify the `name`
            in the :meth:`.start` method.
        max_clients : :class:`int`, optional
            The maximum number of :class:`~msl.network.client.Client`\\s
            that can be linked with this Service. A value :math:`\\leq` 0
            or :data:`None` means that there is no limit.
        ignore_attributes : :class:`str` or :class:`list` of :class:`str`, optional
            The names of the attributes to not include in the
            :obj:`~msl.network.network.Network.identity` of the Service.
            See :meth:`.ignore_attributes` for more details.
        """
        super(Service, self).__init__(name=name)
        self._futures = []
        self._request = {}

        if max_clients is None or max_clients <= 0:
            self._max_clients = -1
        else:
            self._max_clients = int(max_clients)

        self._ignore_attributes = [
            'add_tasks', 'address_manager', 'emit_notification',
            'emit_notification_threadsafe', 'identity', 'ignore_attributes',
            'loop_thread_id', 'max_clients', 'name', 'port',
            'shutdown_handler', 'start', 'request',
        ]

        if ignore_attributes is not None:
            if isinstance(ignore_attributes, str):
                self.ignore_attributes(ignore_attributes)
            else:
                self.ignore_attributes(*ignore_attributes)

        self._executor = ThreadPoolExecutor(thread_name_prefix=f'{self.name}')

    @property
    def max_clients(self):
        """:class:`int`: The maximum number of :class:`~msl.network.client.Client`\\s
        that can be linked with this :class:`Service`. A value :math:`\\leq` 0 means an
        unlimited number of :class:`~msl.network.client.Client`\\s can be linked."""
        return self._max_clients

    def emit_notification(self, *args, **kwargs):
        """Emit a notification to all :class:`~msl.network.client.Client`\\s that
        are :class:`~msl.network.client.Link`\\ed with this :class:`Service`.

        .. versionadded:: 0.5

        Parameters
        ----------
        args
            The arguments to emit.
        kwargs
            The keyword arguments to emit.

        See Also
        --------
        :meth:`.emit_notification_threadsafe`
        :meth:`~msl.network.client.Link.notification_handler`
        """
        notification = {
            'error': False,
            'result': [args, kwargs],
            'service': self._name,
            'uid': NOTIFICATION_UID
        }
        self._queue.put_nowait((NOTIFICATION_UID, notification))

    def emit_notification_threadsafe(self, *args, **kwargs):
        """A thread-safe implementation of :meth:`.emit_notification`.

        When a :class:`Service` handles a request, it does so in a separate
        thread than the event loop is running in. Therefore, if a method of
        the :class:`Service` class wants to emit a notification while it is
        handling a request then it must emit the notification in a
        thread-safe manner.

        .. versionadded:: 1.0

        Parameters
        ----------
        args
            The arguments to emit.
        kwargs
            The keyword arguments to emit.

        See Also
        --------
        :meth:`.emit_notification`
        :meth:`~msl.network.client.Link.notification_handler`
        """
        self._loop.call_soon_threadsafe(partial(self.emit_notification, *args, **kwargs))

    def ignore_attributes(self, *names):
        """Ignore attributes from being added to the
        :obj:`~msl.network.network.Network.identity` of the :class:`Service`.

        There are a few reasons why you may want to call this method:

        * If you see warnings that an object is not JSON serializable or that
          the signature of an attribute cannot be found when starting the
          :class:`Service` and you prefer not to see the warnings.
        * If you do not want an attribute to be made publicly known that it
          exists. However, a :class:`~msl.network.client.Client` can still
          access the ignored attributes.

        Private attributes (i.e., attributes that start with an underscore)
        are automatically ignored and cannot be accessed from a
        :class:`~msl.network.client.Client` on the network.

        If you want to ignore any attributes then you must call
        :meth:`.ignore_attributes` before calling :meth:`.start`.

        .. versionadded:: 0.5

        Parameters
        ----------
        names
            The names of the attributes to not include in the
            :obj:`~msl.network.network.Network.identity` of the :class:`Service`.
        """
        self._ignore_attributes.extend(names)

    def start(self, *, name=None, host='localhost', port=PORT, timeout=10,
              username=None, password=None, password_manager=None,
              read_limit=None, disable_tls=False, cert_file=None,
              assert_hostname=True, auto_save=False, ):
        """Start the :class:`Service`.

        See :func:`~msl.network.client.connect` for the description
        of each parameter.
        """
        kwargs = {k: v for k, v in locals().items() if k != 'self'}

        if name is not None:
            self._name = name

        if kwargs['password'] and kwargs['password_manager']:
            raise ValueError(
                'Specify either "password" or "password_manager" but not both.\n'
                'A Manager cannot be started using multiple authentication methods.'
            )

        self._identity = self._generate_identity()
        self._loop = self._create_connection(**kwargs)
        if self._loop is None:
            # then the user chose to not accept the SSL certificate
            return

        self._tasks.append(self._handle_requests())
        self._tasks.append(self._send_responses())
        self._run_until_complete()

    @property
    def request(self):
        """:class:`dict`: Returns the latest request.

        This property is meant to be used by a subclass that may want to know
        the information about the request while processing it.

        Since a request is executed in a separate thread and this property
        returns the *latest* request, the subclass should immediately extract
        the necessary information from the request before the :class:`Service`
        receives a new request.

        The key-value pairs in the request are::

            {
              'args': list,
              'attribute': str,
              'kwargs': dict,
              'service': str (the name of this Service),
              'uid': str,
              'requester': str,
            }

        .. versionadded:: 1.1
        """
        return self._request

    def _execute_request(self, attr, request):
        # Executes a request in a separate thread
        try:
            response = attr(*request['args'], **request['kwargs'])
        except Exception as e:
            logger.error('%s: %s', e.__class__.__name__, e)
            response = e
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (request, response))

    def _generate_identity(self):
        # Generate the identity dict of this Service
        attributes = dict()
        for name in dir(self):
            if name.startswith('_') or name in self._ignore_attributes:
                continue

            try:
                attrib = getattr(self, name)
            except Exception as e:
                # This can happen if the Service is also a subclass of
                # another class (e.g., the PiCamera class) and the other
                # class defines some of its attributes using the builtin
                # property function, e.g., property(fget, fset, fdel, doc),
                # and defines fget=None or if the getattr() function
                # executes code, like PiCamera.frame does, which raises
                # a custom exception if the camera is not running.
                logger.warning('%s [attribute=%r]', e, name)
                continue

            try:
                value = str(inspect.signature(attrib))
            except TypeError:
                # Then the attribute is not a callable object
                value = attrib
            except ValueError as e:
                # Cannot get the signature of the callable object.
                # This can happen if the Service is also a subclass of
                # some other object, for example a Qt class.
                logger.warning('%s [attribute=%r]', e, name)
                continue

            try:
                # This object must be JSON serializable
                serialize(value)
            except TypeError as e:
                logger.warning('%s [attribute=%r]', e, name)
                continue

            attributes[name] = value

        return {
            'type': 'service',
            'name': self._name,
            'attributes': attributes,
            'max_clients': self._max_clients,
            'language': f'Python {platform.python_version()}',
            'os': f'{platform.system()} {platform.release()} {platform.machine()}'
        }

    def _remove_future(self, future):
        self._futures.remove(future)

    async def _handle_requests(self):
        # Handle requests until EOF
        logger.debug('start requests loop (producer)')
        num_requests = 0
        while True:
            try:
                line = await self._reader.readline()
            except Exception as e:
                logger.error('%s: %s', e.__class__.__name__, e)
                continue

            if not line:
                logger.debug('received EOF')
                self._queue.put_nowait((None, None))
                self.shutdown_handler()
                break

            num_requests += 1

            if len(line) > self._max_debug_length:
                half = self._max_debug_length // 2
                logger.debug('request: %s ... %s', line[:half], line[-half:])
            else:
                logger.debug('request: %s', line)

            try:
                request = deserialize(line)
            except ValueError as e:
                # The Manager should be the only device sending requests
                # to this Service so this error should never occur
                self._queue.put_nowait(({}, e))
                logger.critical('%s: %s', e.__class__.__name__, e)
                continue

            if request.pop('error', False):
                # Not sure who would send an error, but we'll just log it
                default = 'UnknownError: No error message has been provided'
                msg = '\n'.join(request['traceback'])
                if not msg:
                    msg = request['message'] or default
                logger.error('%s sent an error: %s', request['requester'], msg)
                continue

            attribute = request['attribute']
            if attribute.startswith('_'):
                error = PermissionError('Cannot request a private attribute')
                self._queue.put_nowait((request, error))
                logger.warning('%s requested private attribute %r',
                               request['requester'], attribute)
                continue

            try:
                attr = getattr(self, attribute)
            except AttributeError as e:
                self._queue.put_nowait((request, e))
                logger.error('%s: %s', e.__class__.__name__, e)
                continue

            self._request = request

            if attribute == SHUTDOWN_SERVICE:
                response = attr(*request['args'], **request['kwargs'])
                self._queue.put_nowait((request, response))
                await self._queue.join()
                # Notify the Manager and let it shut down the Service
                # since the Manager also needs to notify all Clients that
                # are linked with the Service
                await self._write({
                    'service': self._network_name,
                    'attribute': DISCONNECT_REQUEST
                })
                continue

            if callable(attr):
                # execute the request in a separate thread
                future = self._loop.run_in_executor(
                    self._executor, self._execute_request, attr, request)
                self._futures.append(future)
                future.add_done_callback(self._remove_future)
            else:
                self._queue.put_nowait((request, attr))

            logger.info('%s requested %r [%d running, %d total]',
                        request['requester'], request['attribute'],
                        len(self._futures), num_requests)

        logger.debug('finish requests loop (producer)')

    async def _send_responses(self):
        # FIFO queue to send responses to a Manager
        logger.debug('start responses loop (consumer)')
        notification = NOTIFICATION_UID
        while True:
            request, response = await self._queue.get()
            if request is None:
                self._queue.task_done()
                break
            try:
                if isinstance(response, Exception):
                    await self._write_error(response, **request)
                elif request == notification:
                    await self._write(response)
                else:
                    await self._write_result(response, **request)
            except Exception as e:
                logger.error('%s: %s', e.__class__.__name__, e)
                try:
                    await self._write_error(e, **request)
                except Exception as e:
                    logger.exception(e)
            finally:
                self._queue.task_done()
        logger.debug('finish responses loop (consumer)')


def filter_service_start_kwargs(**kwargs):
    """From the specified keyword arguments only return those that are valid
    for :meth:`~msl.network.service.Service.start`.

    .. versionadded:: 0.4

    Parameters
    ----------
    kwargs
        All keyword arguments that are not part of the method signature for
        :meth:`~msl.network.service.Service.start` are silently ignored and
        are not included in the output.

    Returns
    -------
    :class:`dict`
        Valid keyword arguments that can be passed to
        :meth:`~msl.network.service.Service.start`.
    """
    kws = {}
    for item in inspect.getfullargspec(Service.start).kwonlyargs:
        if item in kwargs:
            kws[item] = kwargs[item]

    # the manager uses an `auth_password` kwarg but a service uses a
    # `password_manager` kwarg, however, these kwargs represent the same thing
    if 'auth_password' in kwargs and 'password_manager' not in kws:
        kws['password_manager'] = kwargs['auth_password']

    return kws
