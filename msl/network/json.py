"""
This module is used as the `JSON <https://www.json.org/>`_ (de)serializer.
"""
import time

from .utils import logger
from .constants import (
    JSON,
    JSONPackage,
)


if JSON == JSONPackage.BUILTIN:
    import json
    _PKG = 'json'
    kwargs_loads = {}
    kwargs_dumps = {'ensure_ascii': False}
elif JSON == JSONPackage.ULTRA:
    import ujson as json
    _PKG = 'ujson'
    kwargs_loads = {'precise_float': False}
    kwargs_dumps = {'ensure_ascii': False}
elif JSON == JSONPackage.SIMPLE:
    import simplejson as json
    _PKG = 'simplejson'
    kwargs_loads = {}
    kwargs_dumps = {'ensure_ascii': False}
elif JSON == JSONPackage.RAPID:
    import rapidjson as json
    _PKG = 'rapidjson'
    kwargs_loads = {'number_mode': json.NM_NATIVE}
    kwargs_dumps = {'ensure_ascii': False, 'number_mode': json.NM_NATIVE}
elif JSON == JSONPackage.YAJL:
    import yajl as json
    _PKG = 'yajl'
    kwargs_loads = {}
    kwargs_dumps = {}
else:
    raise ValueError('{} is not a supported JSON Package'.format(JSON))


def serialize(obj):
    """Serialize `obj` to a JSON-formatted :class:`str`."""
    t0 = time.perf_counter()
    data = json.dumps(obj, **kwargs_dumps)
    logger.debug('{}.dumps took {:.3g} seconds'.format(_PKG, time.perf_counter() - t0))
    return data


def deserialize(s):
    """Deserialize `s` to a Python object."""
    t0 = time.perf_counter()
    if isinstance(s, (bytes, bytearray)):
        s = s.decode('utf-8', 'surrogatepass')
    data = json.loads(s, **kwargs_loads)
    logger.debug('{}.loads took {:.3g} seconds'.format(_PKG, time.perf_counter() - t0))
    return data
