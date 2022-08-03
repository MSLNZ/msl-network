import io
import os
import re
import ssl
import tempfile

import pytest

from msl.network import cryptography
from msl.network.constants import (
    CERT_DIR,
    HOSTNAME,
    DEFAULT_YEARS_VALID,
)


def remove_files():
    filename = 'msl-network-testing'
    key_path = os.path.join(tempfile.gettempdir(), filename + '.key')
    cert_path = os.path.join(tempfile.gettempdir(), filename + '.crt')

    paths = [
        cryptography.get_default_key_path(),
        cryptography.get_default_cert_path(),
        key_path,
        cert_path
    ]

    for p in paths:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
        assert not os.path.isfile(p)
    return key_path, cert_path


def teardown():
    remove_files()


def test_defaults():
    # do not specify any kwargs
    remove_files()
    assert not os.path.isfile(cryptography.get_default_key_path())
    assert not os.path.isfile(cryptography.get_default_cert_path())

    # a private key will automatically be created
    cert_path = cryptography.generate_certificate()
    assert os.path.isfile(cryptography.get_default_key_path())
    assert cert_path == cryptography.get_default_cert_path()

    cert = cryptography.load_certificate(cert_path)
    assert isinstance(cert, cryptography.x509.Certificate)

    meta = cryptography.get_metadata(cert)
    assert meta['issuer']['common_name'] == HOSTNAME
    assert meta['subject']['common_name'] == HOSTNAME
    assert meta['key']['encryption'] == 'RSA'
    assert meta['key']['exponent'] == 65537
    assert meta['key']['size'] == 2048


@pytest.mark.parametrize(
    'kwargs',
    [{'password': None, 'size': 2048, 'algorithm': 'SHA1', 'years_valid': None},
     {'password': 'pass', 'size': 1024, 'algorithm': 'SHA224', 'years_valid': 1},
     {'password': 'ss', 'size': 2048, 'algorithm': 'SHA256', 'years_valid': 2},
     {'password': None, 'size': 1024, 'algorithm': 'SHA384', 'years_valid': 3},
     {'password': None, 'size': 4096, 'algorithm': 'SHA512', 'years_valid': 4},
     {'password': None, 'size': 2048, 'algorithm': 'MD5', 'years_valid': 5}]
)
def test_rsa(kwargs):
    key_file, cert_file = remove_files()

    out = cryptography.generate_key(
        path=key_file, password=kwargs['password'], size=kwargs['size']
    )
    assert out == key_file

    out = cryptography.generate_certificate(
        path=cert_file, key_path=key_file, key_password=kwargs['password'],
        algorithm=kwargs['algorithm'], years_valid=kwargs['years_valid'],
    )
    assert out == cert_file

    cert = cryptography.load_certificate(cert_file)
    meta = cryptography.get_metadata(cert)
    assert meta['issuer']['common_name'] == HOSTNAME
    assert meta['subject']['common_name'] == HOSTNAME
    assert meta['key']['encryption'] == 'RSA'
    assert meta['key']['exponent'] == 65537
    assert meta['key']['size'] == kwargs['size']
    assert meta['fingerprint'] == cryptography.get_fingerprint(cert)
    duration = meta['valid_to'].year - meta['valid_from'].year
    if kwargs['years_valid'] is None:
        assert duration == DEFAULT_YEARS_VALID
    else:
        assert duration == kwargs['years_valid']


@pytest.mark.parametrize(
    'kwargs',
    [{'password': None, 'size': 1024, 'algorithm': 'SHA1', 'years_valid': None},
     {'password': 'pass', 'size': 2048, 'algorithm': 'SHA224', 'years_valid': 1},
     {'password': 'word', 'size': 3072, 'algorithm': 'SHA256', 'years_valid': 2},
     {'password': None, 'size': 4096, 'algorithm': 'SHA1', 'years_valid': 3}]
)
def test_dsa(kwargs):
    key_file, cert_file = remove_files()

    out = cryptography.generate_key(
        path=key_file, password=kwargs['password'], size=kwargs['size'], algorithm='dsa'
    )
    assert out == key_file

    out = cryptography.generate_certificate(
        path=cert_file, key_path=key_file, key_password=kwargs['password'],
        algorithm=kwargs['algorithm'], years_valid=kwargs['years_valid'],
    )
    assert out == cert_file

    cert = cryptography.load_certificate(cert_file)
    meta = cryptography.get_metadata(cert)
    assert meta['issuer']['common_name'] == HOSTNAME
    assert meta['subject']['common_name'] == HOSTNAME
    assert meta['key']['encryption'] == 'DSA'
    assert meta['key']['size'] == kwargs['size']
    assert meta['fingerprint'] == cryptography.get_fingerprint(cert)
    duration = meta['valid_to'].year - meta['valid_from'].year
    if kwargs['years_valid'] is None:
        assert duration == DEFAULT_YEARS_VALID
    else:
        assert duration == kwargs['years_valid']


@pytest.mark.parametrize(
    'kwargs',
    [{'password': None, 'algorithm': 'SHA1', 'years_valid': None, 'curve': 'secp192r1'},
     {'password': 'pass', 'algorithm': 'SHA224', 'years_valid': 1, 'curve': 'secp224r1'},
     {'password': 'ss', 'algorithm': 'SHA256', 'years_valid': 2, 'curve': 'secp256r1'},
     {'password': None, 'algorithm': 'SHA384', 'years_valid': 3, 'curve': 'secp384r1'},
     {'password': 'hi', 'algorithm': 'SHA512', 'years_valid': 4, 'curve': 'secp521r1'},
     {'password': None, 'algorithm': 'SHA1', 'years_valid': 5, 'curve': 'secp256k1'},
     {'password': 'word', 'algorithm': 'SHA224', 'years_valid': 6, 'curve': 'sect163k1'},
     {'password': None, 'algorithm': 'SHA256', 'years_valid': 7, 'curve': 'sect409k1'},
     {'password': None, 'algorithm': 'SHA384', 'years_valid': 8, 'curve': 'sect283r1'},
     {'password': None, 'algorithm': 'SHA512', 'years_valid': 9, 'curve': 'brainpoolP256r1'},
     ]
)
def test_ecc(kwargs):
    key_file, cert_file = remove_files()

    out = cryptography.generate_key(
        path=key_file, password=kwargs['password'], algorithm='ecc', curve=kwargs['curve']
    )
    assert out == key_file

    out = cryptography.generate_certificate(
        path=cert_file, key_path=key_file, key_password=kwargs['password'],
        algorithm=kwargs['algorithm'], years_valid=kwargs['years_valid'],
    )
    assert out == cert_file

    cert = cryptography.load_certificate(cert_file)
    meta = cryptography.get_metadata(cert)
    assert meta['issuer']['common_name'] == HOSTNAME
    assert meta['subject']['common_name'] == HOSTNAME
    assert meta['key']['encryption'] == 'Elliptic Curve'
    assert meta['key']['curve'] == kwargs['curve']
    assert meta['fingerprint'] == cryptography.get_fingerprint(cert)
    duration = meta['valid_to'].year - meta['valid_from'].year
    if kwargs['years_valid'] is None:
        assert duration == DEFAULT_YEARS_VALID
    else:
        assert duration == kwargs['years_valid']


def test_raises():
    for value in ['', 'invalid']:
        match = r'The encryption algorithm must be RSA, DSA or ECC'
        with pytest.raises(ValueError, match=match):
            cryptography.generate_key(algorithm=value)

        match = f'Invalid curve name {value.upper()!r}'
        with pytest.raises(ValueError, match=match):
            cryptography.generate_key(algorithm='ECC', curve=value)

        match = f'Invalid hash algorithm {value.upper()!r}'
        with pytest.raises(ValueError, match=match):
            cryptography.generate_certificate(algorithm=value)

    for obj in [None, True, set(), dict(), tuple(), 2, 1.2, 8j]:
        with pytest.raises(TypeError, match=r'The "cert" parameter must be a string or bytes'):
            cryptography.load_certificate(obj)
        with pytest.raises(TypeError, match=r'must be a string or HashAlgorithm instance'):
            cryptography.generate_certificate(algorithm=None)

    with pytest.raises(ValueError, match=r'Digest size must be \d+'):
        cryptography.generate_certificate(algorithm='BLAKE2b')


def test_fingerprint():
    cryptography.generate_key()
    cryptography.generate_certificate()
    cert = cryptography.load_certificate(cryptography.get_default_cert_path())

    # don't care about the fingerprint value
    # test that calling the function does not raise an exception
    cryptography.get_fingerprint(cert)
    cryptography.get_fingerprint(cert, algorithm='SHA1')
    cryptography.get_fingerprint(cert, algorithm=cryptography.hashes.SHA1())
    cryptography.get_fingerprint(cert, algorithm='blake2s', digest_size=32)
    cryptography.get_fingerprint(cert, algorithm=cryptography.hashes.BLAKE2b(64))


def test_years_valid_fractional():
    cert_path = cryptography.generate_certificate(years_valid=7.4)
    meta = cryptography.get_metadata(cryptography.load_certificate(cert_path))
    # this approximate calculation should be good enough to within a few days
    assert abs((meta['valid_to'] - meta['valid_from']).days - 7.4 * 365) < 5


def test_get_metadata_as_string():
    cert = cryptography.load_certificate(cryptography.generate_certificate())
    string = cryptography.get_metadata_as_string(cert)
    assert re.search(r'Encryption: RSA', string)
    assert re.search(r'Size: 2048', string)
    assert re.search(f'Common Name: {HOSTNAME}', string)
    assert re.search(cryptography.get_fingerprint(cert), string)


def test_custom_subject_name():
    a = cryptography.x509.NameAttribute
    o = cryptography.x509.NameOID
    name = cryptography.x509.Name([
        a(o.COUNTRY_NAME, 'ZZ'),
        a(o.STATE_OR_PROVINCE_NAME, 'Here'),
        a(o.LOCALITY_NAME, 'City'),
        a(o.ORGANIZATION_NAME, 'ORG'),
        a(o.COMMON_NAME, 'MSLNZ12345'),
        a(o.EMAIL_ADDRESS, 'me@you.com'),
    ])

    cert_path = cryptography.generate_certificate(name=name)
    meta = cryptography.get_metadata(cryptography.load_certificate(cert_path))
    assert meta['issuer'] == meta['subject']
    assert meta['subject']['country_name'] == 'ZZ'
    assert meta['subject']['state_or_province_name'] == 'Here'
    assert meta['subject']['locality_name'] == 'City'
    assert meta['subject']['organization_name'] == 'ORG'
    assert meta['subject']['common_name'] == 'MSLNZ12345'
    assert meta['subject']['email_address'] == 'me@you.com'


def test_get_ssl_context(monkeypatch, capsys):
    google_crt = os.path.join(CERT_DIR, 'www.google.com.crt')
    if os.path.isfile(google_crt):
        os.remove(google_crt)

    monkeypatch.setattr('sys.stdin', io.StringIO('y'))
    ca_file, context = cryptography.get_ssl_context(host='www.google.com', port=443)
    assert isinstance(context, ssl.SSLContext)
    captured = capsys.readouterr()
    assert captured.out.startswith('The certificate for www.google.com is not cached')
    assert not captured.err
    os.remove(ca_file)

    monkeypatch.setattr('sys.stdin', io.StringIO('n'))
    ca_file, context = cryptography.get_ssl_context(host='www.google.com', port=443)
    assert ca_file == ''
    assert context is None
    assert not os.path.isfile(google_crt)

    ca_file, context = cryptography.get_ssl_context(host='www.google.com', port=443, auto_save=True)
    assert ca_file == google_crt
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname

    ca_file2, context2 = cryptography.get_ssl_context(host='www.google.com')
    assert ca_file == ca_file2
    assert isinstance(context2, ssl.SSLContext)
    assert context.check_hostname

    ca_file3, context3 = cryptography.get_ssl_context(cert_file=ca_file)
    assert ca_file == ca_file3
    assert isinstance(context3, ssl.SSLContext)
    assert context.check_hostname

    default_cert_path = cryptography.get_default_cert_path()
    if os.path.isfile(default_cert_path):
        os.remove(default_cert_path)

    for kws in [{}, {'host': 'localhost'}, {'port': 12345}]:
        with pytest.raises(ValueError, match=r'Must specify the host and port or the cert_file'):
            cryptography.get_ssl_context(**kws)

    os.remove(ca_file)

    for f in ['', 'invalid.crt', ca_file, google_crt]:
        with pytest.raises(FileNotFoundError):
            cryptography.get_ssl_context(cert_file=f)
