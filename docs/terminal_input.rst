.. _terminal-input:

Connecting from a Terminal
==========================

One can connect to the Network :class:`~msl.network.manager.Manager` from a terminal,
e.g., using `openssl s_client`_, to manually send requests to the Network
:class:`~msl.network.manager.Manager`. So that you do not have to enter a request in the
*very-specific* JSON_ representation of the :ref:`client-format`, the following syntax
can be used instead.

Connecting from a terminal is only convenient when connecting as a
:class:`~msl.network.client.Client`. A :class:`~msl.network.service.Service` must enter
the full JSON_ representation of the :ref:`service-format` when it sends a response.

Some tips for connecting as a :class:`~msl.network.client.Client`:

  * To identify as a :class:`~msl.network.client.Client` enter

    .. code-block:: console

       client

  * To identify as a :class:`~msl.network.client.Client` with the name ``My Name`` enter

    .. code-block:: console

       client My Name

  * To request something from the Network :class:`~msl.network.manager.Manager` use the following format

    .. code-block:: console

       Manager <attribute> [<arguments>, [<keyword_arguments>]]

    For example, to request the :obj:`~msl.network.network.Network.identity` of the Network
    :class:`~msl.network.manager.Manager` enter

    .. code-block:: console

       Manager identity

    or, as a shortcut for requesting the :obj:`~msl.network.network.Network.identity` of
    the :class:`~msl.network.manager.Manager`, you only need to enter

    .. code-block:: console

       identity

    To check if a user with the name ``n.bohr`` exists in the database of registered users enter

    .. code-block:: console

       Manager users_table.is_user_registered n.bohr

    .. note::

       Most requests that are for the Network :class:`~msl.network.manager.Manager` to
       execute require that the request comes from a :class:`~msl.network.client.Client`
       that is connected to the Network :class:`~msl.network.manager.Manager` as an administrator.
       Your login credentials will be checked (requested from you) before the Network
       :class:`~msl.network.manager.Manager` executes the request. See the ``user`` command in
       :ref:`network-cli` for more details on how to become an administrator.

  * To request something from a :class:`~msl.network.service.Service` use the following format

    .. code-block:: console

       <service> <attribute> [<arguments>, [<keyword_arguments>]]

    .. attention::

       Although you can send requests to a :class:`~msl.network.service.Service` in the following manner
       there is no way to block the request if the :class:`~msl.network.service.Service` has already met the
       restriction for the maximum number of :class:`~msl.network.client.Client`\'s that can be linked with
       the :class:`~msl.network.service.Service` to send requests to it. Therefore, you should only do the
       following if you are certain that the :class:`~msl.network.service.Service` has not reached its maximum
       :class:`~msl.network.client.Client` limit. To test if this :class:`~msl.network.client.Client`
       limit has been reached enter ``link <service>``, for example, ``link BasicMath`` and see if you get
       a ``PermissionError`` in the response before you proceed to send requests to the
       :class:`~msl.network.service.Service`.

    For example, to request the addition of two numbers from the :ref:`basic-math-service` enter

    .. code-block:: console

       BasicMath add 4 10

    or

    .. code-block:: console

       BasicMath add x=4 y=10

  To request the concatenation of two strings from a ``ModifyString.concat(s1, s2)``
  :class:`~msl.network.service.Service`, but with the ``ModifyString``
  :class:`~msl.network.service.Service` being named ``String Editor`` on the Network
  :class:`~msl.network.manager.Manager` enter

    .. code-block:: console

       "String Editor" concat s1="first string" s2="second string"

  * To disconnect from the Network :class:`~msl.network.manager.Manager` enter

    .. code-block:: console

       disconnect

    or

    .. code-block:: console

       exit

.. _JSON: https://www.json.org/
.. _openssl s_client: https://www.openssl.org/docs/manmaster/man1/s_client.html
