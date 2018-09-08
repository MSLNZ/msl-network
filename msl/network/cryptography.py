"""
Functions to create a self-signed certificate for the secure SSL/TLS protocol.
"""
import os
import re
import ssl
import sys
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
from .constants import KEY_DIR, CERT_DIR, HOSTNAME

log = logging.getLogger(__name__)

_DEFAULT_YEARS_VALID = 100 if sys.maxsize > 2**32 else 15


def generate_key(*, path=None, algorithm='RSA', password=None, size=2048, curve='SECP384R1'):
    """Generate a new private key.

    Parameters
    ----------
    path : :class:`str`, optional
        The path to where to save the private key. Example, ``path/to/store/key.pem``.
        If :data:`None` then save the key in the default directory with the
        default filename.
    algorithm : :class:`str`, optional
        The encryption algorithm to use to generate the private key. Options are:

        * ``RSA`` - Rivest, Shamir, and Adleman algorithm.
        * ``DSA`` - Digital Signature Algorithm.
        * ``ECC`` - Elliptic Curve Cryptography.

    password : :class:`str`, optional
        The password to use to encrypt the key.
    size : :class:`int`, optional
        The size (number of bits) of the key. Only used if `algorithm` is ``RSA`` or ``DSA``.
    curve : :class:`str`, optional
        The name of the elliptic curve to use. Only used if `algorithm` is ``ECC``.
        See `here <https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ec/#elliptic-curves>`_
        for example elliptic-curve names.

    Returns
    -------
    :class:`str`
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
            msg = 'Unknown curve name {}. Allowed names are {}'.format(
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
        encryption = serialization.BestAvailableEncryption(str(password).encode())

    with open(path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        ))

    log.debug('create private {} key {}'.format(algorithm_u, path))
    return path


def load_key(path, *, password=None):
    """Load a private key from a file.

    Parameters
    ----------
    path : :class:`str`
        The path to the key file.
    password : :class:`str`, optional
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


def generate_certificate(*, path=None, key_path=None, key_password=None, algorithm='SHA256', years_valid=None):
    """Generate a self-signed certificate.

    Parameters
    ----------
    path : :class:`str`, optional
        The path to where to save the certificate. Example, ``path/to/store/certificate.pem``.
        If :data:`None` then save the certificate in the default directory with the
        default filename.
    key_path : :class:`str`, optional
        The path to where the private key is saved which will be used to
        digitally sign the certificate. If :data:`None` then automatically
        generates a new private key (overwriting the default private key
        if one already exists).
    key_password : :class:`str`, optional
        The password to use to decrypt the private key.
    algorithm : :class:`str`, optional
        The hash algorithm to use. Default is ``SHA256``. See
        `this <https://cryptography.io/en/latest/hazmat/primitives/cryptographic-hashes/#cryptographic-hash-algorithms>`_
        link for example hash-algorithm names.
    years_valid : :class:`float`, optional
        The number of years that the certificate is valid for. If you want to
        specify that the certificate is valid for 3 months then set `years_valid`
        to be ``0.25``. Default is ``100`` years for 64-bit platforms and ``15``
        years for 32-bit platforms.

    Returns
    -------
    :class:`str`
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
        msg = 'Invalid hash algorithm {}. Allowed algorithms are {}'.format(algorithm.upper(), allowed)
        raise ValueError(msg) from None

    if key_path is None:
        key_path = get_default_key_path()
        if not os.path.isfile(key_path):
            generate_key(path=key_path)
    key = load_key(path=key_path, password=key_password)

    if path is None:
        path = get_default_cert_path()
    ensure_root_path(path)

    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'NZ'),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Wellington'),
        x509.NameAttribute(NameOID.LOCALITY_NAME, 'Lower Hutt'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Measurement Standards Laboratory of New Zealand'),
        x509.NameAttribute(NameOID.COMMON_NAME, HOSTNAME),
        x509.NameAttribute(NameOID.EMAIL_ADDRESS, 'info@measurement.govt.nz'),
    ])

    now = datetime.datetime.utcnow()

    years_valid = _DEFAULT_YEARS_VALID if years_valid is None else max(0, years_valid)
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
    cert = cert.sign(key, hash_class, default_backend())

    with open(path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    log.debug('create self-signed certificate ' + path)
    return path


def load_certificate(cert):
    """Load a PEM certificate.

    Parameters
    ----------
    cert : :class:`str` or :class:`bytes`
        If :class:`str` then the path to the certificate file.
        If :class:`bytes` then the raw certificate data.

    Returns
    -------
    :class:`~cryptography.x509.Certificate`
        The PEM certificate.

    Raises
    ------
    TypeError
        If `cert` is not of type :class:`str` or :class:`bytes`.
    """
    if isinstance(cert, str):
        with open(cert, 'rb') as f:
            data = f.read()
        log.debug('load certificate ' + cert)
    elif isinstance(cert, bytes):
        data = cert
    else:
        raise TypeError('The "cert" parameter must be a string or bytes')
    return x509.load_pem_x509_certificate(data, default_backend())


def get_default_cert_path():
    """:class:`str`: Returns the default certificate path."""
    return os.path.join(CERT_DIR, HOSTNAME + '.crt')


def get_default_key_path():
    """:class:`str`: Returns the default key path."""
    return os.path.join(KEY_DIR, HOSTNAME + '.key')


def get_fingerprint(cert, *, algorithm=hashes.SHA1):
    """Get the fingerprint of the certificate.

    Parameters
    ----------
    cert : :class:`~cryptography.x509.Certificate`
        The PEM certificate.
    algorithm : :class:`~cryptography.hazmat.primitives.hashes.HashAlgorithm`
        The hash algorithm.

    Returns
    -------
    :class:`str`
        The fingerprint as a colon-separated hex string.
    """
    fingerprint = cert.fingerprint(algorithm()).hex()
    return ':'.join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))


def get_metadata(cert):
    """Get the metadata of the certificate.

    Parameters
    ----------
    cert : :class:`~cryptography.x509.Certificate`
        The certificate.

    Returns
    -------
    :class:`dict`
        The metadata of the certificate.
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
        oid = dict()
        for name in vars(NameOID):
            if name.startswith('_'):
                continue
            attrib = value.get_attributes_for_oid(getattr(NameOID, name))
            if attrib:
                oid[name.lower()] = attrib[0].value
        return oid

    def oid_to_dict(oid):
        match = re.search(r'oid=(.+), name=(.+)\)', str(oid))
        return {'oid': match.group(1), 'name': match.group(2)}

    meta = dict()
    meta['version'] = cert.version.name
    meta['serial_number'] = to_hex_string(cert.serial_number)
    meta['valid_from'] = cert.not_valid_before
    meta['valid_to'] = cert.not_valid_after
    meta['fingerprint'] = get_fingerprint(cert)
    meta['issuer'] = name_oid(cert.issuer)
    meta['subject'] = name_oid(cert.subject)

    meta['key'] = dict()
    key = cert.public_key()
    if issubclass(key.__class__, ec.EllipticCurvePublicKey):
        meta['key']['encryption'] = 'Elliptic Curve'
        meta['key']['curve'] = key.curve.name
        meta['key']['size'] = key.curve.key_size
        meta['key']['key'] = to_hex_string(key.public_numbers().encode_point())
    elif issubclass(key.__class__, rsa.RSAPublicKey):
        meta['key']['encryption'] = 'RSA'
        meta['key']['exponent'] = key.public_numbers().e
        meta['key']['size'] = key.key_size
        meta['key']['modulus'] = to_hex_string(key.public_numbers().n)
    elif issubclass(key.__class__, dsa.DSAPublicKey):
        meta['key']['encryption'] = 'DSA'
        meta['key']['size'] = key.key_size
        meta['key']['y'] = to_hex_string(key.public_numbers().y)
        meta['key']['p'] = to_hex_string(key.public_numbers().parameter_numbers.p)
        meta['key']['q'] = to_hex_string(key.public_numbers().parameter_numbers.q)
        meta['key']['g'] = to_hex_string(key.public_numbers().parameter_numbers.g)
    else:
        raise NotImplementedError('Unsupported public key {}'.format(key.__class__.__name__))

    meta['algorithm'] = oid_to_dict(cert.signature_algorithm_oid)
    meta['algorithm']['signature'] = to_hex_string(cert.signature)

    meta['extensions'] = dict()
    for ext in cert.extensions:
        d = oid_to_dict(ext.oid)
        meta['extensions']['oid'] = d['oid']
        meta['extensions']['name'] = d['name']
        meta['extensions']['value'] = str(ext.value)
        meta['extensions']['critical'] = ext.critical

    return meta


def get_metadata_as_string(cert):
    """Returns the metadata of the certificate as a *human-readable* string.

    Parameters
    ----------
    cert : :class:`~cryptography.x509.Certificate`
        The certificate.

    Returns
    -------
    :class:`str`
        The metadata of the certificate.
    """
    def justify(hex_string):
        h = hex_string
        n = 75
        return '    ' + '    \n    '.join(h[i:i+n] for i in range(0, len(h), n))

    def to_title(k):
        t = k.replace('_', ' ').title()
        return t.replace(' Or ', ' or ')

    meta = get_metadata(cert)

    details = list()

    details.append('Version: ' + meta['version'])

    details.append('Serial Number: ' + meta['serial_number'])

    details.append('Issuer:')
    for key, value in meta['issuer'].items():
        details.append('  {}: {}'.format(to_title(key), value))

    details.append('Validity:')
    details.append('  Not Before: ' + meta['valid_from'].strftime('%d %B %Y %H:%M:%S GMT'))
    details.append('  Not After : ' + meta['valid_to'].strftime('%d %B %Y %H:%M:%S GMT'))

    details.append('Subject:')
    for key, value in meta['subject'].items():
        details.append('  {}: {}'.format(to_title(key), value))

    details.append('Subject Public Key Info:')
    for key, value in meta['key'].items():
        if key in ['key', 'modulus', 'y', 'p', 'q', 'g']:
            details.append('  {}:'.format(key.title()))
            details.append(justify(value))
        else:
            details.append('  {}: {}'.format(to_title(key), value))

    if meta['extensions']:
        details.append('Extensions:')
        details.append('  ' + str(meta['extensions']['value']).replace('<', '').replace('>', '') + ':')
        for key, value in meta['extensions'].items():
            if key != 'value':
                details.append('    {}: {}'.format(key, value))

    details.append('Signature Algorithm:')
    details.append('  oid: ' + meta['algorithm']['oid'])
    details.append('  name: ' + meta['algorithm']['name'])
    details.append('  value:')
    details.append(justify(meta['algorithm']['signature']))

    details.append('Fingerprint (SHA1):')
    details.append(get_fingerprint(cert))

    return '\n'.join(details)


def get_ssl_context(*, host=None, port=None, certificate=None):
    """Get the SSL context.

    Gets the context either from connecting to a remote server or from loading
    it from a file.

    To get the context from a remote server you must specify both `host`
    and `port`.

    Parameters
    ----------
    host : :class:`str`, optional
        The hostname of the remote server to connect to.
    port : :class:`int`, optional
        The port number of the remote server to connect to.
    certificate : :class:`str`, optional
        The path to the certificate file to load.

    Returns
    -------
    :class:`ssl.SSLContext`
        The SSL context.
    """
    if certificate is None:

        # check that the default certificate exists
        # if it does not exist then fetch it
        certificate = os.path.join(CERT_DIR, host + '.crt')
        if not os.path.isfile(certificate):
            cert_data = ssl.get_server_certificate((host, port)).encode()
            cert = load_certificate(cert_data)
            fingerprint = get_fingerprint(cert)
            name = cert.signature_algorithm_oid._name

            print('The certificate for {host} is not cached in the registry.\n'
                  'You have no guarantee that the server is the computer that\n'
                  'you think it is.\n\n'
                  'The server\'s {name} key fingerprint is\n{fingerprint}\n\n'
                  'If you trust this host you can save the certificate in the\n'
                  'registry and continue to connect, otherwise this is your\n'
                  'final chance to abort.\n'.format(host=host, name=name, fingerprint=fingerprint))
            while True:
                r = input('Continue? y/n: ').lower()
                if r.startswith('n'):
                    return
                elif r.startswith('y'):
                    break

            ensure_root_path(certificate)
            with open(certificate, 'wb') as f:
                f.write(cert_data)

    elif not os.path.isfile(certificate):
        raise IOError('Cannot find certificate ' + certificate)

    return ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=certificate)
