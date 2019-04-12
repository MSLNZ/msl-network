"""
Common functions used by **MSL-Network**.
"""
import re
import os
import ast

from .constants import (
    HOSTNAME,
    DISCONNECT_REQUEST,
)

_args_regex = re.compile(r'[\s]*((?:[^\"\s]+)|\"(?:[^\"]*)\")')

_kwargs_regex = re.compile(r'(\w+)[\s]*=[\s]*((?:[^\"\s]+)|\"(?:[^\"]*)\")')

_is_manager_regex = re.compile(r':\d+$')

_ipv4_regex = re.compile(r'\d+\.\d+\.\d+\.\d+')

_oid_regex = re.compile(r'oid=(.+), name=(.+)\)')


def ensure_root_path(path):
    """Ensure that the root directory of the file path exists.
        
    Parameters
    ----------
    path : :class:`str`
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

    See, :ref:`terminal-input` for more details.

    .. _JSON: https://www.json.org/

    Parameters
    ----------
    line : :class:`str`
        The input text from the terminal.

    Returns
    -------
    :class:`dict`
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
    elif line_lower == DISCONNECT_REQUEST or line_lower == 'disconnect' or line_lower == 'exit':
        return {
            'service': 'self',
            'attribute': DISCONNECT_REQUEST,
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

        service = items[0].replace('"', '')
        attribute = items[1].replace('"', '')
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
    """:class:`tuple` of :class:`str`: Aliases for ``localhost``."""
    return HOSTNAME, 'localhost', '127.0.0.1', '::1'
