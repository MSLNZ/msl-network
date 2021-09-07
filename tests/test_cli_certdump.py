import os
import tempfile

from msl.network import cli
from msl.network.cryptography import (
    generate_certificate,
    load_certificate,
    get_fingerprint,
)


def process(command):
    parser = cli.configure_parser()
    args = parser.parse_args(command.split())
    args.func(args)


def test_invalid_certificate(capsys):
    process('certdump does-not-exist.pem')
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Cannot find does-not-exist.pem'
    assert not err


def test_file(capsys):
    tmp = tempfile.gettempdir() + 'out.tmp'
    path = generate_certificate()
    process('certdump {} --out {}'.format(path, tmp))
    out, err = capsys.readouterr()
    assert out.rstrip() == 'Dumped the certificate details to ' + tmp
    assert not err

    with open(tmp, mode='rt') as fp:
        lines = [line.rstrip() for line in fp.readlines()]

    assert lines[0] == 'Certificate details for {}'.format(path)
    assert lines[1] == 'Version: v3'
    assert lines[-2] == 'Fingerprint (SHA1):'
    assert lines[-1] == get_fingerprint(load_certificate(path))

    os.remove(tmp)


def test_stdout(capsys):
    path = generate_certificate()
    process('certdump {}'.format(path))
    out, err = capsys.readouterr()
    out_lines = out.splitlines()
    assert not err
    assert out_lines[0] == 'Version: v3'
    assert out_lines[-2] == 'Fingerprint (SHA1):'
    assert out_lines[-1] == get_fingerprint(load_certificate(path))
