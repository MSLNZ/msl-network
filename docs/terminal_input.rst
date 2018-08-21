.. _terminal-input:

Connecting from a Terminal
==========================

One can connect to the Network :class:`~msl.network.manager.Manager` from a terminal,
e.g., using `openssl s_client`_, to manually send requests to the Network
:class:`~msl.network.manager.Manager`. So that you do not have to enter a request in the
*very-specific* :ref:`client-format` for the JSON_ string, the following syntax can be used.

Connecting from a terminal is only convenient when connecting as a
:class:`~msl.network.client.Client`. A :class:`~msl.network.service.Service` must enter the
:ref:`service-format` for the JSON_ string when it sends a reply. *Although, why would you connect*
*as a* :class:`~msl.network.service.Service` *and manually execute requests?*

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
       execute require that the request comes from an administrator of the Network
       :class:`~msl.network.manager.Manager`. Your login credentials will be checked
       (requested from you) before the Network :class:`~msl.network.manager.Manager`
       executes the request.

  * To request something from a :class:`~msl.network.service.Service` use the following format

    .. code-block:: console

       <service> <attribute> [<arguments>, [<keyword_arguments>]]

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
