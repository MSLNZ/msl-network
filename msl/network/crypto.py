"""
Functions to create a self-signed certificate for the secure SSL/TLS protocol.
"""
import os
import re
import ssl
import socket
import logging
import inspect
import datetime

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import dsa

from .utils import ensure_root_path
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
    ensure_root_path(path)

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

    log.debug('create private {} key {}'.format(algorithm_u, path))
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
        The path to where to save the certificate. Example,
        ``path/to/store/certificate.pem``.
    key_path : :obj:`str`, optional
        The path to where the private key is saved which will be used to
        digitally sign the certificate. If :obj:`None` then automatically
        generates a new private key (overwriting the default private key
        if one already exists).
    key_password : :obj:`str`, optional
        The password to use to decrypt the private key.
    algorithm : :obj:`str`, optional
        The hash algorithm to use. Default is ``SHA256``. See
        `this <https://cryptography.io/en/latest/hazmat/primitives/cryptographic-hashes/#cryptographic-hash-algorithms>`_
        link for example hash-algorithm names.
    years_valid : :obj:`float`, optional
        The number of years that the certificate is valid for. If you want to
        specify that the certificate is valid for 3 months then set `years_valid`
        to be ``0.25``. Default is ``100`` years.

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
    ensure_root_path(path)

    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'NZ'),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Wellington'),
        x509.NameAttribute(NameOID.LOCALITY_NAME, 'Lower Hutt'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Measurement Standards Laboratory of New Zealand'),
        x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname()),
    ])

    now = datetime.datetime.utcnow()

    years_valid = max(0, years_valid)
    years = int(years_valid)
    days = int((years_valid - years) * 365)
    expires = now.replace(year=now.year + years)
    if days > 0:
        expires += datetime.timedelta(days=days)

    cert = x509.CertificateBuilder()
    cert = cert.subject_name(name)
    cert = cert.issuer_name(name)  # subject_name == issuer_name for a self-signed certificate
    cert = cert.public_key(key.public_key())
    cert = cert.serial_number(x509.random_serial_number())
    cert = cert.not_valid_before(now)
    cert = cert.not_valid_after(expires)
    cert = cert.add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
    cert = cert.sign(key, hash_class, default_backend())

    with open(path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    log.debug('create self-signed certificate ' + path)
    return path


def load_certificate(path):
    """Load a PEM certificate from a file.

    Parameters
    ----------
    path : :obj:`str`
        The path to the certificate file.

    Returns
    -------
    :class:`~cryptography.x509.Certificate`
        The PEM certificate.
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
    ensure_root_path(path)

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


def get_fingerprint(cert, algorithm=hashes.SHA1):
    """Get the fingerprint of the certificate.

    Parameters
    ----------
    cert : :class:`~cryptography.x509.Certificate`
        The PEM certificate.
    algorithm : :class:`~cryptography.hazmat.primitives.hashes.HashAlgorithm`
        The hash algorithm.

    Returns
    -------
    :obj:`str`
        The fingerprint as a colon-separated hex string.
    """
    s = cert.fingerprint(algorithm()).hex()
    return ':'.join(s[i:i+2] for i in range(0, len(s), 2))


def get_details(cert):
    """Get the details of the certificate.

    Parameters
    ----------
    cert : :class:`~cryptography.x509.Certificate`
        The certificate.

    Returns
    -------
    :obj:`str`
        The details about the certificate.
    """
    def to_hex_string(val):
        # create a colon-separated hex string
        if isinstance(val, bytes):
            val = val.hex()
        elif isinstance(val, int):
            val = str(hex(val))[2:]
            if len(val) % 2 == 1:
                val = '0'+val
        return ':'.join(val[i:i+2] for i in range(0, len(val), 2))

    def name_oid(value):
        s = ''
        for name in vars(NameOID):
            if name.startswith('_'):
                continue
            attrib = value.get_attributes_for_oid(getattr(NameOID, name))
            if attrib:
                s += ('  {}: {}\n'.format(name.replace('_', ' ').lower().title(), attrib[0].value))
        return s

    def justify(hex_string):
        h = hex_string
        n = 75
        return '    ' + '    \n    '.join(h[i:i+n] for i in range(0, len(h), n)) + '\n'

    def oid_to_dict(oid):
        match = re.search(r'oid=(.+), name=(.+)\)', str(oid))
        return {'oid': match.group(1), 'name': match.group(2)}

    details = ''
    details += 'Version: {}\n'.format(cert.version.name)

    details += 'Serial Number: {}\n'.format(to_hex_string(cert.serial_number))

    details += 'Issuer:\n'
    details += name_oid(cert.issuer)

    details += 'Validity:\n'
    details += '  Not Before: {}\n'.format(cert.not_valid_before.strftime('%d %B %Y %H:%M:%S GMT'))
    details += '  Not After : {}\n'.format(cert.not_valid_after.strftime('%d %B %Y %H:%M:%S GMT'))

    details += 'Subject:\n'
    details += name_oid(cert.subject)

    details += 'Subject Public Key Info:\n'
    key = cert.public_key()
    if issubclass(key.__class__, ec.EllipticCurvePublicKey):
        details += '  Encryption: Elliptic Curve\n'
        details += '  Curve: {}\n'.format(key.curve.name)
        details += '  Key Size: {}\n'.format(key.key_size)
        details += '  Key:\n'
        k = '04:' + to_hex_string(key.public_numbers().x) + ':' + to_hex_string(key.public_numbers().y)
        details += justify(k)
    elif issubclass(key.__class__, rsa.RSAPublicKey):
        details += '  Encryption: RSA\n'
        details += '  Exponent: {}\n'.format(key.public_numbers().e)
        details += '  Key Size: {}\n'.format(key.key_size)
        details += '  Key:\n'
        details += justify('00:' + to_hex_string(key.public_numbers().n))
    elif issubclass(key.__class__, dsa.DSAPublicKey):
        details += '  Encryption: DSA\n'
        details += '  Key Size: {}\n'.format(key.key_size)
        details += '  Y:\n'
        details += justify(to_hex_string(key.public_numbers().y))
        details += '  P:\n'
        details += justify(to_hex_string(key.public_numbers().parameter_numbers.p))
        details += '  Q:\n'
        details += justify(to_hex_string(key.public_numbers().parameter_numbers.q))
        details += '  G:\n'
        details += justify(to_hex_string(key.public_numbers().parameter_numbers.g))
    else:
        raise NotImplementedError('Unsupported public key {}'.format(key.__class__.__name__))

    details += 'Extensions:\n'
    for ext in cert.extensions:
        details += '  ' + str(ext.value).replace('<', '').replace('>', '') + ':\n'
        details += '    Critical: {}\n'.format(ext.critical)
        d = oid_to_dict(ext.oid)
        details += '    OID: {}\n'.format(d['oid'])

    details += 'Signature Algorithm:\n'
    d = oid_to_dict(cert.signature_algorithm_oid)
    details += '  OID: {}\n'.format(d['oid'])
    details += '  Name: {}\n'.format(d['name'])
    details += '  Value:\n'
    details += justify(to_hex_string(cert.signature))

    details += 'Fingerprint (SHA1):\n  {}'.format(to_hex_string(cert.fingerprint(hashes.SHA1())))

    return details
