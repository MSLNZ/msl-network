"""
Common functions.
"""
import os
import ssl


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


def get_ssl_context(host=None, port=None, certificate=None):
    """Get the SSL context to connect to a server.

    Gets the context either from a remote server or from a file.

    To get the context from a remote server you must specify both
    `host` and `port`.

    Parameters
    ----------
    host : :obj:`str`, optional
        The hostname of the remote server to get the certificate of.
    port : :obj:`int`, optional
        The port number of the remote server to get the certificate of.
    certificate : :obj:`str`, optional
        The path to the certificate file.

    Returns
    -------
    :class:`ssl.SSLContext`
        The SSL context.
    """
    if certificate is None:

        if host in ('localhost', '127.0.0.1', '::1'):
            host = HOSTNAME

        # check that the default certificate exists
        # if it does not exist then fetch it
        certificate = os.path.join(CERT_DIR, host + '.crt')
        if not os.path.isfile(certificate):
            cert = load_certificate(ssl.get_server_certificate((host, port)).encode())
            fingerprint = get_fingerprint(cert)
            name = cert.signature_algorithm_oid._name

            print(f'The certificate for {host} is not cached in the registry.\n'
                  f'You have no guarantee that the server is the computer that you think it is.\n\n'
                  f'The server\'s {name} key fingerprint is\n{fingerprint}\n\n'
                  f'If you trust this host you can save the certificate in the registry\n'
                  f'and continue to connect, otherwise this is your final chance to abort.\n')
            while True:
                r = input('Continue? y/n: ').lower()
                if r.startswith('n'):
                    return
                elif r.startswith('y'):
                    break

            ensure_root_path(certificate)
            with open(certificate, 'wb') as f:
                f.write(cert.encode())

    elif not os.path.isfile(certificate):
        raise IOError('Cannot find certificate ' + certificate)

    return ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=certificate)


# import these here to avoid circular import errors (for the crypto module)

from .constants import CERT_DIR, HOSTNAME
from .crypto import get_fingerprint, load_certificate
