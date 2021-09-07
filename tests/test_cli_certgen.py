import os
import tempfile

import pytest

from msl.network import cli
from msl.network.cryptography import (
    load_certificate,
    get_fingerprint,
    generate_key,
    get_default_cert_path,
)


def process(command):
    parser = cli.configure_parser()
    args = parser.parse_args(command.split())
    args.func(args)


@pytest.mark.parametrize('years', [-1, '1.3j', None])
def test_bad_years_valid(years, capsys):
    process('certgen --years-valid {}'.format(years))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'ValueError: The --years-valid value must be a positive number'
    assert not err


def test_no_args(capsys):
    process('certgen')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Created the self-signed certificate {!r}'.format(get_default_cert_path())
    assert not err


def test_password(capsys):
    key_file = os.path.join(tempfile.gettempdir(), 'key.private')
    generate_key(path=key_file, password='the password')

    process('certgen --key-file {} --key-file-password the password'.format(key_file))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Created the self-signed certificate {!r}'.format(get_default_cert_path())
    assert not err

    os.remove(key_file)


def test_password_file(capsys):
    pw_file = os.path.join(tempfile.gettempdir(), 'password.tmp')
    pw = 'the password'
    with open(pw_file, mode='wt') as fp:
        fp.write(pw)

    key_file = os.path.join(tempfile.gettempdir(), 'key.private')
    generate_key(path=key_file, password=pw)

    process('certgen --key-file {} --key-file-password {}'.format(key_file, pw_file))
    out, err = capsys.readouterr()
    assert not err
    assert out.splitlines() == [
        'Reading the key password from the file',
        'Created the self-signed certificate {!r}'.format(get_default_cert_path())
    ]

    os.remove(pw_file)
    os.remove(key_file)


def test_show(capsys):
    process('certgen --show')
    out, err = capsys.readouterr()
    assert not err
    out_lines = out.splitlines()
    assert out_lines[0] == 'Created the self-signed certificate {!r}'.format(get_default_cert_path())
    assert not out_lines[1]
    assert out_lines[2] == 'Version: v3'
    assert out_lines[-2] == 'Fingerprint (SHA1):'
    assert out_lines[-1] == get_fingerprint(load_certificate(get_default_cert_path()))


def test_algorithm(capsys):
    process('certgen --algorithm SHA512')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Created the self-signed certificate {!r}'.format(get_default_cert_path())
    assert not err


def test_algorithm_invalid(capsys):
    process('certgen --algorithm XXX')
    out, err = capsys.readouterr()
    assert out.startswith("ValueError: Invalid hash algorithm 'XXX'")
    assert not err


def test_out_path(capsys):
    cert_path = os.path.join(tempfile.gettempdir(), 'cert.pem')
    try:
        os.remove(cert_path)
    except OSError:
        pass

    assert not os.path.isfile(cert_path)
    process('certgen {}'.format(cert_path))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Created the self-signed certificate {!r}'.format(cert_path)
    assert not err
    assert os.path.isfile(cert_path)

    os.remove(cert_path)
