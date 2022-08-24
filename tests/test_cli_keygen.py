import os
import tempfile

import pytest

from msl.network import cli
from msl.network.cryptography import get_default_key_path
from msl.network.cryptography import load_key


def process(command):
    parser = cli.configure_parser()
    args = parser.parse_args(command.split())
    args.func(args)


@pytest.mark.parametrize('size', [-1, '1.3j', None])
def test_bad_size_valid(size, capsys):
    process(f'keygen --size {size}')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'ValueError: The --size value must be a positive integer'
    assert not err


def test_no_args(capsys):
    process('keygen')
    out, err = capsys.readouterr()
    assert out.rstrip() == f'Created private RSA key {get_default_key_path()!r}'
    assert not err
    load_key(get_default_key_path())


def test_password(capsys):
    process('keygen --password the password')
    out, err = capsys.readouterr()
    assert out.rstrip() == f'Created private RSA key {get_default_key_path()!r}'
    assert not err

    load_key(get_default_key_path(), password='the password')


def test_password_file(capsys):
    pw_file = os.path.join(tempfile.gettempdir(), 'password.tmp')
    with open(pw_file, mode='wt') as fp:
        fp.write('the password')

    process(f'keygen --password {pw_file}')
    out, err = capsys.readouterr()
    assert not err
    assert out.splitlines() == [
        'Reading the key password from the file',
        f'Created private RSA key {get_default_key_path()!r}'
    ]

    load_key(get_default_key_path(), password='the password')

    os.remove(pw_file)


@pytest.mark.parametrize('algorithm', ['rsa', 'dsa', 'ecc'])
def test_algorithm(algorithm, capsys):
    process(f'keygen {algorithm}')
    out, err = capsys.readouterr()
    assert out.rstrip() == f'Created private {algorithm.upper()} key {get_default_key_path()!r}'
    assert not err
    load_key(get_default_key_path())


def test_curve_invalid(capsys):
    process('keygen ecc --curve XXX')
    out, err = capsys.readouterr()
    assert out.startswith("ValueError: Invalid curve name 'XXX'")
    assert not err


def test_size_invalid(capsys):
    process('keygen dsa --size 1234')
    out, err = capsys.readouterr()
    # an error message from the cryptography developers
    assert out.startswith('ValueError: ')
    assert not err


def test_out_path(capsys):
    key_path = os.path.join(tempfile.gettempdir(), 'key.private')
    try:
        os.remove(key_path)
    except OSError:
        pass

    assert not os.path.isfile(key_path)
    process(f'keygen --out {key_path}')
    out, err = capsys.readouterr()
    assert out.rstrip() == f'Created private RSA key {key_path!r}'
    assert not err
    assert os.path.isfile(key_path)
    load_key(key_path)

    os.remove(key_path)
