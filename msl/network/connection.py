"""
Create a new connection to the Manager.
"""
from threading import Thread

from .client import Client
from .constants import PORT


def connect(host='localhost', port=PORT, password=None, certificate=None, debug=False):
    """Create a new connection to the Manager.

    Parameters
    ----------
    host : :obj:`str`
        The hostname of the :class:`Manager` that the :class:`Client`
        should connect to.
    port : :obj:`int`, optional
        The port number of the :class:`Manager` that the :class:`Client`
        should connect to.
    password : :obj:`str`, optional
        The password that is required to connect to the Manager.
        If not specified then you will be asked for the password (only if
        the Manager requires a password to be able to connect to it).
    certificate : :obj:`str`, optional
        The path to the certificate file to use for the TLS connection
        with the Manager.
    debug : :obj:`bool`, optional
        Whether to log debug messages for the :class:`Client`.
    """
    client = Client()
    t1 = Thread(target=client.start, args=(host, port, password, certificate, debug))
    t1.start()
    return client
