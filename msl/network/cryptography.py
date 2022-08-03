"""
Functions to create a self-signed certificate for the secure SSL/TLS protocol.
"""
import os
import ssl
import inspect
import datetime
import textwrap
from ipaddress import IPv4Address

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import (
    ec,
    rsa,
    dsa,
)

from .utils import (
    logger,
    ensure_root_path,
    _oid_regex,
)
from .constants import (
    KEY_DIR,
    CERT_DIR,
    HOSTNAME,
    DEFAULT_YEARS_VALID,
    IPV4_ADDRESSES,
)

hash_map = {}


def generate_key(*, path=None, algorithm='RSA', password=None, size=2048, curve='SECP384R1'):
    """Generate a new private key.

    Parameters
    ----------
    path : :class:`str`, optional
        The path to save the private key to. If not specified then save the
        private key in the default directory with the default filename.
    algorithm : :class:`str`, optional
        The encryption algorithm to use to generate the private key.
        Options are:

            * ``RSA`` - Rivest, Shamir, and Adleman algorithm.
            * ``DSA`` - Digital Signature Algorithm.
            * ``ECC`` - Elliptic Curve Cryptography.

    password : :class:`str`, optional
        The password to use to encrypt the key.
    size : :class:`int`, optional
        The size (number of bits) of the key. Only used if `algorithm` is
        ``RSA`` or ``DSA``.
    curve : :class:`str`, optional
        The name of the elliptic curve to use. Only used if `algorithm` is
        ``ECC``. See :ref:`hazmat/primitives/asymmetric/ec:elliptic curves`
        for example elliptic-curve names.

    Returns
    -------
    :class:`str`
        The path to the private key.
    """
    algorithm_u = algorithm.upper()
    if algorithm_u == 'RSA':
        key = rsa.generate_private_key(65537, size)
    elif algorithm_u == 'DSA':
        key = dsa.generate_private_key(size)
    elif algorithm_u == 'ECC':
        curve_u = curve.upper()
        types = {k.upper(): v for k, v in ec._CURVE_TYPES.items()}  # yep, access the private dict
        try:
            curve_class = types[curve_u]
        except KeyError:
            msg = 'Invalid curve name {!r}. Allowed curves are\n{}'.format(
                curve_u, ', '.join(sorted(types.keys())))
            raise ValueError(msg) from None
        key = ec.generate_private_key(curve_class)
    else:
        raise ValueError(
            'The encryption algorithm must be '
            'RSA, DSA or ECC. Got {}'.format(algorithm_u)
        )

    if path is None:
        path = get_default_key_path()
    ensure_root_path(path)

    if password is None:
        encryption = serialization.NoEncryption()
    else:
        encryption = serialization.BestAvailableEncryption(password.encode())

    with open(path, mode='wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        ))

    logger.debug('create private %s key %s', algorithm_u, path)
    return path


def load_key(path, *, password=None):
    """Load a private key from a file.

    Parameters
    ----------
    path : :class:`str`
        The path to a key file.
    password : :class:`str`, optional
        The password to use to decrypt the private key.

    Returns
    -------
    :class:`~cryptography.hazmat.primitives.asymmetric.rsa.RSAPrivateKey`, :class:`~cryptography.hazmat.primitives.asymmetric.dsa.DSAPrivateKey` or :class:`~cryptography.hazmat.primitives.asymmetric.ec.EllipticCurvePrivateKey`
        The private key.
    """
    with open(path, mode='rb') as f:
        data = f.read()
    pw = None if password is None else password.encode()
    logger.debug('load private key %s', path)
    return serialization.load_pem_private_key(data=data, password=pw)


def generate_certificate(*, path=None, key_path=None, key_password=None,
                         algorithm='SHA256', years_valid=None,
                         digest_size=None, name=None, extensions=None):
    """Generate a self-signed certificate.

    .. versionchanged:: 1.0
       Added the `digest_size`, `name` and `extensions` keyword arguments.

    Parameters
    ----------
    path : :class:`str`, optional
        The path to save the certificate to. If not specified then save the
        certificate in the default directory with the default filename.
    key_path : :class:`str`, optional
        The path to the private key which will be used to digitally sign the
        certificate. If not specified then automatically generates a new
        private key (overwriting the default private key if one already exists).
    key_password : :class:`str`, optional
        The password to use to decrypt the private key.
    algorithm : :class:`str` or :class:`~cryptography.hazmat.primitives.hashes.HashAlgorithm`, optional
        The hash algorithm to use. See :ref:`hazmat/primitives/cryptographic-hashes:message digests (hashing)`
        for allowed hash algorithms.
    years_valid : :class:`int` or :class:`float`, optional
        The number of years that the certificate is valid for. If you want to
        specify that the certificate is valid for 3 months then set `years_valid`
        to be 0.25. Default is 100 years for 64-bit platforms and 15
        years for 32-bit platforms.
    digest_size : :class:`int`, optional
        The digest size (if the hash `algorithm` requires one).
    name : :class:`~cryptography.x509.Name`, optional
        The object to use for the
        :meth:`~cryptography.x509.CertificateBuilder.subject_name` and the
        :meth:`~cryptography.x509.CertificateBuilder.issuer_name`. If not
        specified then a default `name` is used.
    extensions : :class:`list` of :class:`~cryptography.x509.ExtensionType`, optional
        The extensions to add to the certificate.

    Returns
    -------
    :class:`str`
        The path to the self-signed certificate that was generated.
    """
    hash_class = _hash_class(algorithm=algorithm, digest_size=digest_size)

    if key_path is None:
        key_path = get_default_key_path()
        if not os.path.isfile(key_path):
            generate_key(path=key_path)
    key = load_key(path=key_path, password=key_password)

    if path is None:
        path = get_default_cert_path()
    ensure_root_path(path)

    if name is None:
        a = x509.NameAttribute
        name = x509.Name([
            a(NameOID.COUNTRY_NAME, 'NZ'),
            a(NameOID.STATE_OR_PROVINCE_NAME, 'Wellington'),
            a(NameOID.LOCALITY_NAME, 'Lower Hutt'),
            a(NameOID.ORGANIZATION_NAME, 'Measurement Standards Laboratory of New Zealand'),
            a(NameOID.COMMON_NAME, HOSTNAME),
            a(NameOID.EMAIL_ADDRESS, 'info@measurement.govt.nz'),
        ])

    if extensions is None:
        extensions = []

    names = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    if not extensions and any(cn.value == HOSTNAME for cn in names):
        dns = [x509.DNSName(domain) for domain in (HOSTNAME, 'localhost')]
        ips = [x509.IPAddress(IPv4Address(ip)) for ip in ('127.0.0.1', *IPV4_ADDRESSES)]
        extensions.append(x509.SubjectAlternativeName(dns + ips))  # noqa

    now = datetime.datetime.utcnow()

    years_valid = DEFAULT_YEARS_VALID if years_valid is None else max(0, years_valid)
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
    for ext in extensions:
        cert = cert.add_extension(ext, critical=False)
    cert = cert.sign(key, hash_class)

    with open(path, mode='wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.debug('create self-signed certificate %s', path)
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
        with open(cert, mode='rb') as f:
            data = f.read()
        logger.debug('load certificate %s', cert)
    elif isinstance(cert, bytes):
        data = cert
    else:
        raise TypeError('The "cert" parameter must be a string or bytes')
    return x509.load_pem_x509_certificate(data)


def get_default_cert_path():
    """:class:`str`: Returns the default certificate path."""
    return os.path.join(CERT_DIR, 'localhost.crt')


def get_default_key_path():
    """:class:`str`: Returns the default key path."""
    return os.path.join(KEY_DIR, 'localhost.key')


def get_fingerprint(cert, *, algorithm='SHA1', digest_size=None):
    """Get the fingerprint of a certificate.

    .. versionchanged:: 1.0
       Added the `digest_size` keyword argument and allow
       `algorithm` to be a string.

    Parameters
    ----------
    cert : :class:`~cryptography.x509.Certificate`
        The PEM certificate.
    algorithm : :class:`str` or :class:`~cryptography.hazmat.primitives.hashes.HashAlgorithm`, optional
        The hash algorithm to use. See :ref:`hazmat/primitives/cryptographic-hashes:message digests (hashing)`
        for allowed hash algorithms.
    digest_size : :class:`int`, optional
        The digest size (if the hash `algorithm` requires one).

    Returns
    -------
    :class:`str`
        The fingerprint as a colon-separated hex string.
    """
    hash_class = _hash_class(algorithm=algorithm, digest_size=digest_size)
    fingerprint = cert.fingerprint(hash_class).hex()
    return ':'.join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))


def get_metadata(cert):
    """Get the metadata of a certificate.

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
        match = _oid_regex.search(str(oid))
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
        try:
            # This try..except block fixes the following::
            #   CryptographyDeprecationWarning: encode_point has been deprecated on ElliptcCurvePublicNumbers
            #   and will be removed in a future version. Please use EllipticCurvePublicKey.public_bytes to
            #   obtain both compressed and uncompressed point encoding.
            # In v2.5 the X962 name was added to the Encoding enum so previous versions will throw an AttributeError
            meta['key']['key'] = to_hex_string(
                key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
            )
        except AttributeError:
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
    """Returns the metadata of a certificate as a *human-readable* string.

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


def get_ssl_context(*, cert_file=None, host=None, port=None, auto_save=False):
    """Get the SSL context.

    Gets the context either from connecting to a remote server or from loading
    it from a file.

    To get the context from a remote server you must specify both `host`
    and `port`.

    .. versionchanged:: 0.4
       Renamed `certificate` to `certfile`.

    .. versionchanged:: 1.0
       Renamed `certfile` to `cert_file`.
       Added the `auto_save` keyword argument.

    Parameters
    ----------
    cert_file : :class:`str`, optional
        The path to a certificate file to load. If specified then
        `host`, `port` and `auto_save` are ignored.
    host : :class:`str`, optional
        The hostname or IP address of the remote server to connect to.
    port : :class:`int`, optional
        The port number of the remote server to connect to.
    auto_save : :class:`bool`, optional
        Whether to automatically save the certificate from the server.
        Default is to ask before saving.

    Returns
    -------
    :class:`str`
        The path to the certificate file that was loaded.
    :class:`ssl.SSLContext`
        The SSL context.
    """
    ca_file = cert_file or os.path.join(CERT_DIR, '{}.crt'.format(host))
    try:
        return ca_file, ssl.create_default_context(cafile=ca_file)
    except FileNotFoundError:
        if cert_file is not None:
            raise

    if host is None or port is None:
        raise ValueError('Must specify the host and port or the cert_file')

    # TODO Starting from Python 3.10 the ssl.get_server_certificate()
    #  function will accept a timeout argument so a `timeout` kwarg
    #  could be added to get_ssl_context()
    cert_data = ssl.get_server_certificate((host, port)).encode()

    cert = load_certificate(cert_data)
    fingerprint = get_fingerprint(cert)
    name = cert.signature_algorithm_oid._name

    if not auto_save:
        p1 = 'The certificate for {host} is not cached in the registry. ' \
             'You have no guarantee that the server is the computer that ' \
             'you think it is.'.format(host=host)
        p2 = '\nThe server\'s {name} key fingerprint is\n{fingerprint}\n'.format(
            name=name, fingerprint=fingerprint)
        p3 = 'If you trust this host you can save the certificate in the registry ' \
             'and continue to connect, otherwise this is your final chance to abort.'

        width = 60
        print('\n'.join(textwrap.wrap(p1, width=width)))
        print(p2)
        print('\n'.join(textwrap.wrap(p3, width=width)))
        print('')

        while True:
            r = input('Continue? y/n: ').lower()
            if r.startswith('n'):
                return '', None
            elif r.startswith('y'):
                break

    ensure_root_path(ca_file)
    with open(ca_file, mode='wb') as f:
        f.write(cert_data)

    return get_ssl_context(cert_file=ca_file)


def _hash_class(*, algorithm='', digest_size=None):
    """Return an instance of the HashAlgorithm.

    Parameters
    ----------
    algorithm : str or HashAlgorithm
    digest_size : None or int
    """
    if isinstance(algorithm, hashes.HashAlgorithm):
        return algorithm

    if not isinstance(algorithm, str):
        raise TypeError('The hash algorithm must be a string or HashAlgorithm instance')

    if not hash_map:
        for item in dir(hashes):
            obj = getattr(hashes, item)
            item_upper = item.upper()
            if item.startswith('_') or not inspect.isclass(obj) or item_upper == 'HASHALGORITHM':
                continue
            if issubclass(obj, hashes.HashAlgorithm):
                hash_map[item_upper] = obj

    algorithm_u = algorithm.upper()
    try:
        return hash_map[algorithm_u]()
    except TypeError:
        return hash_map[algorithm_u](digest_size)
    except KeyError:
        allowed = ', '.join(hash_map.keys())
        msg = 'Invalid hash algorithm {!r}. Allowed algorithms are\n{}'.format(
            algorithm_u, allowed)
        raise ValueError(msg) from None
