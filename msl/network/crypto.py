"""
Functions to create a self-signed certificate for the secure SSL/TLS protocol.
"""
import os
import ssl
import socket
import datetime
import logging
import inspect

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

from .constants import KEY_DIR, CERT_DIR

log = logging.getLogger(__name__)


def generate_key(path, algorithm='RSA', password=None, size=2048, curve='SECP384R1'):
    """Generate a new private key.

    Parameters
    ----------
    path : :obj:`str`
        The path to where to save the private key. Example, ``path/to/store/key.pem``.
    algorithm : :obj:`str`, optional
        The encryption algorithm to use to generate the private key. Options are:

        * ``RSA`` - Rivest, Shamir, and Adleman algorithm.
        * ``DSA`` - Digital Signature Algorithm.
        * ``ECC`` - Elliptic Curve Cryptography.

    password : :obj:`str`, optional
        The password to use to encrypt the key.
    size : :obj:`int`, optional
        The size (number of bits) of the key. Only used if `algorithm` is ``RSA`` or ``DSA``.
    curve : :obj:`str`, optional
        The name of the elliptic curve to use. Only used if `algorithm` is ``ECC``.
        See `here <https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ec/#elliptic-curves>`_
        for example elliptic-curve names.

    Returns
    -------
    :obj:`str`
        The path to the private key.
    """
    algorithm_u = algorithm.upper()
    if algorithm_u == 'RSA':
        key = rsa.generate_private_key(65537, size, default_backend())
    elif algorithm_u == 'DSA':
        key = dsa.generate_private_key(size, default_backend())
    elif algorithm_u == 'ECC':
        try:
            curve_class = ec._CURVE_TYPES[curve.lower()]  # yeah, access the private variable...
        except KeyError:
            names = [key.upper() for key in ec._CURVE_TYPES]
            msg = 'Unknown curve name "{}". Allowed names are {}'.format(
                curve.upper(), ', '.join(sorted(names)))
            raise ValueError(msg) from None
        key = ec.generate_private_key(curve_class, default_backend())
    else:
        raise ValueError('The encryption algorithm must be RSA, DSA or ECC. Got ' + algorithm_u)

    if path is None:
        path = get_default_key_path()
    _ensure_root_path(path)

    if password is None:
        encryption = serialization.NoEncryption()
    else:
        encryption = serialization.BestAvailableEncryption(bytes(str(password).encode()))

    with open(path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        ))

    log.debug('created private {} key {}'.format(algorithm_u, path))
    return path


def load_key(path, password=None):
    """Load a private key from a file.

    Parameters
    ----------
    path : :obj:`str`
        The path to the key file.
    password : :obj:`str`, optional
        The password to use to decrypt the private key.

    Returns
    -------
    :class:`~cryptography.hazmat.primitives.asymmetric.rsa.RSAPrivateKey`, :class:`~cryptography.hazmat.primitives.asymmetric.dsa.DSAPrivateKey` or :class:`~cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePrivateKey`
        The private key.
    """
    with open(path, 'rb') as f:
        data = f.read()
    pw = None if password is None else bytes(str(password).encode())
    log.debug('load private key ' + path)
    return serialization.load_pem_private_key(data=data, password=pw, backend=default_backend())


def generate_certificate(path, key_path=None, key_password=None, algorithm='SHA256', years_valid=100):
    """Generate a self-signed certificate.

    Parameters
    ----------
    path : :obj:`str`, optional
        The path to where to save the certificate. Example, ``path/to/store/certificate.pem``.
    key_path : :obj:`str`, optional
        The path to where the private key is saved which will be used to digitally sign the
        certificate. If :obj:`None` then automatically generates a new private key (overwriting
        the default private key if one already exists).
    key_password : :obj:`str`, optional
        The password to use to decrypt the private key.
    algorithm : :obj:`str`, optional
        The hash algorithm to use. Default is ``SHA256``. See
        `this <https://cryptography.io/en/latest/hazmat/primitives/cryptographic-hashes/#cryptographic-hash-algorithms>`_
        link for example hash-algorithm names.

    years_valid : :obj:`int`, optional
        The number of years that the certificate is valid for. Default is ``100`` years.

    Returns
    -------
    :obj:`str`
        The path to the self-signed certificate.
    """
    hash_map = {}
    for item in dir(hashes):
        obj = getattr(hashes, item)
        item_upper = item.upper()
        if item.startswith('_') or not inspect.isclass(obj) or item_upper == 'HASHALGORITHM':
            continue
        if issubclass(obj, hashes.HashAlgorithm):
            hash_map[item_upper] = obj

    try:
        hash_class = hash_map[algorithm.upper()]()
    except KeyError:
        allowed = ', '.join(hash_map.keys())
        msg = 'Invalid hash algorithm "{}". Allowed algorithms are {}'.format(algorithm.upper(), allowed)
        raise ValueError(msg) from None

    if key_path is None:
        key_path = get_default_key_path()
        if not os.path.isfile(key_path):
            generate_key(key_path)
    key = load_key(key_path, key_password)

    if path is None:
        path = get_default_cert_path()
    _ensure_root_path(path)

    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'NZ'),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Wellington'),
        x509.NameAttribute(NameOID.LOCALITY_NAME, 'Lower Hutt'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Measurement Standards Laboratory of New Zealand'),
        x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname()),
    ])

    now = datetime.datetime.utcnow()

    cert = x509.CertificateBuilder()
    cert = cert.subject_name(name)
    cert = cert.issuer_name(name)  # subject_name == issuer_name for a self-signed certificate
    cert = cert.public_key(key.public_key())
    cert = cert.serial_number(x509.random_serial_number())
    cert = cert.not_valid_before(now)
    cert = cert.not_valid_after(now.replace(year=now.year + years_valid))
    cert = cert.add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
    cert = cert.sign(key, hash_class, default_backend())

    with open(path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    log.debug('created a self-signed certificate ' + path)
    return path


def load_certificate(path):
    """Load a X.509 certificate from a file.

    Parameters
    ----------
    path : :obj:`str`
        The path to the certificate file.

    Returns
    -------
    :class:`~cryptography.x509.Certificate`
        The X.509 certificate.
    """
    with open(path, 'rb') as f:
        data = f.read()
    log.debug('load certificate ' + path)
    return x509.load_pem_x509_certificate(data, default_backend())


def save_remote_certificate(host, port, path):
    """Save a remote certificate to a file.

    Parameters
    ----------
    host : :obj:`str`
        The name of the host.
    port : :obj:`int`
        The port number on the host.
    path : :obj:`str`
        The path to where to save the certificate. Example, ``path/to/store/certificate.pem``.

    Returns
    -------
    :obj:`str`
        The certificate data as a PEM-encoded string.
    """
    try:
        cert = ssl.get_server_certificate((host, port))
    except ssl.SSLError as e:
        log.error('cannot get certificate from {}:{}. {}'.format(host, port, e))
        return

    if path is None:
        path = os.path.join(CERT_DIR, '{}.crt'.format(host))
    _ensure_root_path(path)

    with open(path, 'wb') as f:
        f.write(cert.encode())

    log.info('got certificate from {}:{}'.format(host, port))
    return cert


def get_default_cert_path():
    """:obj:`str`: Returns the default certificate path."""
    return os.path.join(CERT_DIR, socket.gethostname() + '.crt')


def get_default_key_path():
    """:obj:`str`: Returns the default key path."""
    return os.path.join(KEY_DIR, socket.gethostname() + '.key')


def _ensure_root_path(path):
    """Ensure that the root directory for the file path exists."""
    root = os.path.dirname(path)
    if not os.path.isdir(root):
        os.makedirs(root)
