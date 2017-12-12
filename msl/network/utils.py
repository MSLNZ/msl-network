"""
Common functions.
"""
import re
import os
import ast

from .constants import HOSTNAME

_args_regex = re.compile(r'[\s]*((?:[^\"\s]+)|\"(?:[^\"]*)\")')

_kwargs_regex = re.compile(r'(\w+)[\s]*=[\s]*((?:[^\"\s]+)|\"(?:[^\"]*)\")')


def ensure_root_path(path):
    """Ensure that the root directory of the file path exists.
        
    Parameters
    ----------
    path : :obj:`str`
        The file path.
        
        For example, if `path` is ``/the/path/to/my/test/file.txt`` then
        this function would ensure that ``/the/path/to/my/test`` directory
        exists (creating the intermediate directories if necessary).
    """
    if path is not None:
        root = os.path.dirname(path)
        if root and not os.path.isdir(root):
            os.makedirs(root)


def parse_terminal_input(line):
    """Parse text from a terminal connection.

    This is a convenience function if someone wants to connect to the Network
    :class:`~msl.network.manager.Manager` through a terminal, e.g. using `openssl s_client`_,
    to manually send requests to the Network :class:`~msl.network.manager.Manager` so that
    they do not have to enter a request in the very-specific :ref:`client-format` for the
    JSON_ string.

    This function is only convenient for connecting as a :class:`~msl.network.client.Client`.
    A :class:`~msl.network.service.Service` must enter the :ref:`service-format`
    for the JSON_ string when it sends a reply. *Although, why would you connect*
    *as a* :class:`~msl.network.service.Service` *and manually execute requests?*

    Some tips for connecting as a :class:`~msl.network.client.Client`:

        * To identify as a :class:`~msl.network.client.Client` enter ``client``.

        * To identify as a :class:`~msl.network.client.Client` with the name ``My Name``
          enter ``client My Name``.

        * To request something from the Network :class:`~msl.network.manager.Manager` use
          the following format ``Manager <attribute> [<arguments>, [<keyword_arguments>]]``

          For example,

          To request the :obj:`~msl.network.network.Network.identity` of the
          Network :class:`~msl.network.manager.Manager` enter ``Manager identity``.

          To check if a user with the name ``n.bohr`` exists in the database of users enter

          ``Manager users_table.is_user_registered n.bohr``.

          .. note::

              Most requests that are for the Network :class:`~msl.network.manager.Manager` to
              execute require that the request comes from an administrator of the Network
              :class:`~msl.network.manager.Manager`. Your login credentials will be checked
              (requested from you) before the Network :class:`~msl.network.manager.Manager`
              executes the request.

        * To request something from a :class:`~msl.network.service.Service` use the following
          format ``<service> <attribute> [<arguments>, [<keyword_arguments>]]``

          For example,

          To request the addition of two numbers from the :ref:`basic-math-service` enter

          ``BasicMath add 4 10`` or ``BasicMath add x=4 y=10``

          To request the concatenation of two strings from a ``ModifyString.concat(s1, s2)``
          :class:`~msl.network.service.Service`, but with the ``ModifyString``
          :class:`~msl.network.service.Service` being named ``String Editor`` on the Network
          :class:`~msl.network.manager.Manager` then enter

          ``"String Editor" concat s1="first string" s2="second string"``

        * To exit from the terminal session enter ``disconnect`` or ``exit``.

    .. _JSON: http://www.json.org/
    .. _openssl s_client: https://www.openssl.org/docs/manmaster/man1/s_client.html

    Parameters
    ----------
    line : :obj:`str`
        The input text from the terminal.

    Returns
    -------
    :obj:`dict`
        The JSON_ object.
    """
    def convert_value(val):
        val_ = val.lower()
        if val_ == 'false':
            return False
        elif val_ == 'true':
            return True
        elif val_ == 'null' or val_ == 'none':
            return None
        else:
            try:
                return ast.literal_eval(val)
            except:
                return val

    line = line.strip()
    line_lower = line.lower()
    if line_lower == 'identity':
        return {
            'service': 'Manager',
            'attribute': 'identity',
            'args': [],
            'kwargs': {},
            'uuid': '',
            'error': False,
        }
    elif line_lower.startswith('client'):
        values = line.split()  # can also specify a name for the Client, e.g., client Me and Myself
        name = 'Client' if len(values) == 1 else ' '.join(values[1:])
        return {
            'type': 'client',
            'name': name.replace('"', ''),
            'language': 'unknown',
            'os': 'unknown',
            'error': False,
        }
    elif line_lower == '__disconnect__' or line_lower == 'disconnect' or line_lower == 'exit':
        return {
            'service': 'self',
            'attribute': '__disconnect__',
            'args': [],
            'kwargs': {},
            'uuid': '',
            'error': False,
        }
    elif line_lower.startswith('link'):
        return {
            'service': 'Manager',
            'attribute': 'link',
            'args': [line[4:].strip().replace('"', '')],
            'kwargs': {},
            'uuid': '',
            'error': False,
        }
    else:
        line = line.replace("'", '"')
        if line.startswith('"'):
            line = line.split('"', maxsplit=2)
            items = [item.strip() for item in line if item.strip()]
            if len(items) > 1:
                items = [items[0]] + items[1].split(None, maxsplit=1)
        else:
            items = line.split(None, maxsplit=2)

        if len(items) < 2:  # then the name of the service and/or attribute was not set
            return None

        service = convert_value(items[0])
        attribute = convert_value(items[1]).replace('"', '')
        if len(items) == 2:  # no parameters
            return {
                'service': service,
                'attribute': attribute,
                'args': [],
                'kwargs': {},
                'uuid': '',
                'error': False,
            }
        else:
            args = [convert_value(m.groups()[0]) for m in re.finditer(_args_regex, items[2])]
            kwargs = dict()
            for i, m in enumerate(re.finditer(_kwargs_regex, items[2])):
                key, value = m.groups()
                if i == 0:
                    args = [convert_value(m.groups()[0]) for m in re.finditer(_args_regex, items[2].split(key)[0])]
                kwargs[key] = convert_value(value)
            return {
                'service': service,
                'attribute': attribute,
                'args': args,
                'kwargs': kwargs,
                'uuid': '',
                'error': False,
            }


def localhost_aliases():
    """:obj:`tuple` of :obj:`str`: Aliases for ``localhost``."""
    return HOSTNAME, 'localhost', '127.0.0.1', '::1'
