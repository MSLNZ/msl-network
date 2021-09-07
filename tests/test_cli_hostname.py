import os

import pytest

import conftest

from msl.network import cli
from msl.network.database import HostnamesTable
from msl.network.constants import DATABASE
from msl.network.utils import localhost_aliases


def process(command):
    parser = cli.configure_parser()
    args = parser.parse_args(command.split())
    args.func(args)


def remove_default():
    try:
        os.remove(DATABASE)
    except OSError:
        pass


def test_path():
    conftest.Manager.remove_files()
    remove_default()

    assert DATABASE != conftest.Manager.database
    assert not os.path.isfile(DATABASE)
    assert not os.path.isfile(conftest.Manager.database)

    # need to specify an action, so use the "list" action
    process('hostname list')
    assert os.path.isfile(DATABASE)
    assert not os.path.isfile(conftest.Manager.database)
    os.remove(DATABASE)

    process('hostname list --database {}'.format(conftest.Manager.database))
    assert os.path.isfile(conftest.Manager.database)
    assert not os.path.isfile(DATABASE)
    os.remove(conftest.Manager.database)


def test_list(capsys):
    process('hostname list')
    out, err = capsys.readouterr()
    assert not err
    out_lines = out.splitlines()
    assert out_lines[0] == 'Trusted devices in {}'.format(DATABASE)
    assert not out_lines[1]
    assert out_lines[2] == 'Hostnames:'
    for i, alias in enumerate(sorted(localhost_aliases())):
        assert out_lines[i+3] == '  ' + alias


@pytest.mark.parametrize(
    ('action', 'verb'),
    [('add', 'added'), ('insert', 'inserted'),
     ('remove', 'removed'), ('delete', 'deleted')]
)
def test_no_hostnames(action, verb, capsys):
    process('hostname ' + action)
    out, err = capsys.readouterr()
    assert out.rstrip() == 'No hostnames were {}'.format(verb)
    assert not err


@pytest.mark.parametrize(
    ('action', 'verb'),
    [('add', 'Added'), ('insert', 'Inserted')]
)
def test_add(action, verb, capsys):
    remove_default()

    process('hostname {} HOSTNAME1 abc123 MSLNZ-12345'.format(action))
    out, err = capsys.readouterr()
    assert not err
    assert out.splitlines() == [
        '{} HOSTNAME1'.format(verb),
        '{} abc123'.format(verb),
        '{} MSLNZ-12345'.format(verb)
    ]

    table = HostnamesTable()
    assert 'HOSTNAME1' in table.hostnames()
    assert 'abc123' in table.hostnames()
    assert 'MSLNZ-12345' in table.hostnames()
    table.close()

    remove_default()


@pytest.mark.parametrize(
    ('action', 'verb'),
    [('remove', 'Removed'), ('delete', 'Deleted')]
)
def test_remove(action, verb, capsys):
    remove_default()

    process('hostname {} 127.0.0.1 ::1 localhost'.format(action))
    out, err = capsys.readouterr()
    assert not err
    assert out.splitlines() == [
        '{} 127.0.0.1'.format(verb),
        '{} ::1'.format(verb),
        '{} localhost'.format(verb)
    ]

    table = HostnamesTable()
    assert 'localhost' not in table.hostnames()
    assert '::1' not in table.hostnames()
    assert '127.0.0.1' not in table.hostnames()
    table.close()

    remove_default()


@pytest.mark.parametrize(
    ('action', 'verb'),
    [('remove', 'Removed'), ('delete', 'Deleted')]
)
def test_remove_invalid(action, verb, capsys):
    process('hostname {} mslnz ::1 abc'.format(action))
    out, err = capsys.readouterr()
    out_lines = out.splitlines()
    assert out_lines == [
        "Cannot {} 'mslnz'. This hostname is not in the table.".format(action),
        '{} ::1'.format(verb),
        "Cannot {} 'abc'. This hostname is not in the table.".format(action),
    ]
    assert not err
    remove_default()
