"""
Common functions.
"""
import re
import os
import ast

from .constants import HOSTNAME

_key_value_regex = re.compile(r'(\w+)[\s]*=[\s]*((?:[^\"\s]+)|\"(?:[^\"]*)\")')


def ensure_root_path(path):
    """Ensure that the root directory of the file path exists.
        
    Parameters
    ----------
    path : :obj:`str`
        The file path.
        
        For example, if `path` is ``/the/path/to/my/test/file.txt`` then
        this function would ensure that the ``/the/path/to/my/test`` directory
        exists creating the intermediate directories if necessary.
    """
    root = os.path.dirname(path)
    if root and not os.path.isdir(root):
        os.makedirs(root)


def parse_terminal_input(line):
    """Parse text from a terminal connection.

    This is a convenience method if someone connects through a terminal, e.g. Putty,
    to manually send requests to the Network :class:`~msl.network.manager.Manager`.
    so that they do not have to enter the request as very-specific JSON_ strings.

    This function is really only convenient for connecting as a :class:`~msl.network.client.Client`
    since a :class:`~msl.network.service.Service` must format the
    :obj:`~msl.network.network.Network.identity` and the
    :class:`replies <msl.network.service.Service.data_received>` to be a properly-formatted
    JSON_ string. Although, why would you manually connect as a :class:`~msl.network.service.Service`?

    Some tips for connecting as a :class:`~msl.network.client.Client`:

        * To identify as a :class:`~msl.network.client.Client` enter ``client``.

        * To identify as a :class:`~msl.network.client.Client` with a the name ``My Name``
          enter ``client My Name``.

        * To request the identity of the Network :class:`~msl.network.manager.Manager`
          enter ``identity``

        * You **MUST** request to link the :class:`~msl.network.client.Client` with a
          :class:`~msl.network.service.Service` so that the response from the
          :class:`~msl.network.service.Service` can be routed back to the
          :class:`~msl.network.client.Client`. For example, to link with a
          :class:`~msl.network.service.Service` that is called ``BasicMath`` or ``String Editor``
          enter ``link BasicMath`` and ``link String Editor`` respectively.

        * To request something from a :class:`~msl.network.service.Service` use the following
          format ``service_name attribute_name key_value_parameters``

          For example,

          To request the addition of two numbers from a ``BasicMath.add(x, y)``
          :class:`~msl.network.service.Service` enter ``BasicMath add x=4 y=10``

          To request concatenating two strings from a ``ModifyString.concat(s1, s2)``
          :class:`~msl.network.service.Service`, but with the :class:`~msl.network.service.Service`
          being named ``String Editor`` on the Network :class:`~msl.network.manager.Manager`
          then enter ``"String Editor" concat s1="first string" s2="second string"``

        * To exit from the terminal session enter ``disconnect`` or ``exit``.

    .. _JSON: http://www.json.org/

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
            'service': None,
            'attribute': 'identity',
            'parameters': {},
            'error': False,
        }
    elif line_lower.startswith('client'):
        values = line.split()  # can also specify a name for the Client, e.g., client Me and Myself
        name = 'Client' if len(values) == 1 else ' '.join(values[1:])
        return {
            'type': 'client',
            'name': name.replace('"', ''),
            'error': False,
        }
    elif line_lower == '__disconnect__' or line_lower == 'disconnect' or line_lower == 'exit':
        return {
            'service': 'self',
            'attribute': '__disconnect__',
            'parameters': {},
            'error': False,
        }
    elif line_lower.startswith('link'):
        return {
            'service': None,
            'attribute': 'link',
            'parameters': {'service': line[4:].strip().replace('"', '')},
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
                'parameters': {},
                'error': False,
            }
        else:
            params = dict()
            for m in re.finditer(_key_value_regex, items[2]):
                key, value = m.groups()
                params[key] = convert_value(value)
            return {
                'service': service,
                'attribute': attribute,
                'parameters': params,
                'error': False,
            }


def localhost_aliases():
    """:obj:`tuple` of :obj:`str`: Aliases for ``localhost``."""
    return HOSTNAME, 'localhost', '127.0.0.1', '::1'
