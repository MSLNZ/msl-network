import os
import socket
import tempfile

import pytest

from msl.network import cryptography


def test_cryo():
    filename = 'msl-network-testing'
    key_path = os.path.join(tempfile.gettempdir(), filename + '.key')
    cert_path = os.path.join(tempfile.gettempdir(), filename + '.crt')
    dump_path = os.path.join(tempfile.gettempdir(), filename + '.txt')

    cryptography.generate_key(path=key_path)
    with pytest.raises(TypeError):
        cryptography.generate_certificate(path=cert_path, key_path=key_path, key_password='password')

    cryptography.generate_key(path=key_path, password='password')
    with pytest.raises(TypeError):
        cryptography.generate_certificate(path=cert_path, key_path=key_path)

    cryptography.generate_key(path=key_path, password='password')
    with pytest.raises(TypeError):
        cryptography.load_key(key_path)  # no password specified
    path = cryptography.generate_certificate(path=cert_path, key_path=key_path, key_password='password')
    cert = cryptography.load_certificate(path)
    meta = cryptography.get_metadata(cert)
    assert meta['key']['encryption'] == 'RSA'
    assert meta['key']['size'] == 2048

    with pytest.raises(ValueError):
        cryptography.generate_key(path=key_path, algorithm='XXX')

    cryptography.generate_key(path=key_path, algorithm='DSA')
    path = cryptography.generate_certificate(path=cert_path, key_path=key_path)
    cert = cryptography.load_certificate(path)
    meta = cryptography.get_metadata(cert)
    assert meta['key']['encryption'] == 'DSA'
    assert meta['key']['size'] == 2048

    cryptography.generate_key(path=key_path, algorithm='ECC')
    path = cryptography.generate_certificate(path=cert_path, key_path=key_path)
    cert = cryptography.load_certificate(path)
    meta = cryptography.get_metadata(cert)
    assert meta['key']['encryption'] == 'Elliptic Curve'
    assert meta['key']['curve'] == 'SECP384R1'.lower()
    assert meta['key']['size'] == 384

    fingerprint = cryptography.get_fingerprint(cert)
    with open(dump_path, 'w') as fp:
        fp.write(cryptography.get_metadata_as_string(cert))
    with open(dump_path, 'r') as fp:
        fp.readline().startswith('Version:')

    with open(path, 'rb') as fp:
        pem = fp.read()
    cert2 = cryptography.load_certificate(pem)
    assert fingerprint == cryptography.get_fingerprint(cert2)

    cryptography.generate_key(path=key_path, size=4096)
    cryptography.generate_certificate(path=cert_path, key_path=key_path, years_valid=7)
    meta = cryptography.get_metadata(cryptography.load_certificate(cert_path))
    assert meta['key']['encryption'] == 'RSA'
    assert meta['key']['size'] == 4096
    assert meta['valid_to'].year - meta['valid_from'].year == 7

    cryptography.generate_key(path=key_path, algorithm='DSA', size=1024)
    cryptography.generate_certificate(path=cert_path, key_path=key_path, years_valid=7.4)
    meta = cryptography.get_metadata(cryptography.load_certificate(cert_path))
    assert meta['issuer']['common_name'] == socket.gethostname()
    assert meta['subject']['common_name'] == socket.gethostname()
    assert meta['key']['encryption'] == 'DSA'
    assert meta['key']['size'] == 1024
    # the approximate calculation should be good enough to within a few days
    assert abs((meta['valid_to'] - meta['valid_from']).days - 7.4 * 365) < 10

    os.remove(key_path)
    os.remove(cert_path)
    os.remove(dump_path)
