import os
import sys
import tempfile

from msl.network import cli
from msl.network.database import HostnamesTable

db = os.path.join(tempfile.gettempdir(), 'test_cli_hostname.db')
out = os.path.join(tempfile.gettempdir(), 'test_cli_hostname.tmp')
table = HostnamesTable(database=db)


def get_args(command):
    parser = cli.configure_parser()
    return parser.parse_args(command.split())


def teardown_module(module):
    table.close()
    os.remove(db)
    os.remove(out)


def test_cli_hostname():
    for h in ['hostname_'+str(i) for i in range(10)]:
        table.insert(h)

    original_names = table.hostnames()

    base_command = 'hostname --database {} '.format(db)

    # action: list
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'list')
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('Trusted')
    assert lines[2] == 'Hostnames:'
    assert 'hostname_0' in lines
    assert 'hostname_9' in lines

    # action: add ... nothing
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'add')
    args.func(args)
    assert len(table.hostnames()) == len(original_names)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('No hostnames were')

    # action: remove ... nothing
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'remove')
    args.func(args)
    assert len(table.hostnames()) == len(original_names)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('No hostnames were')

    # action: add
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'add HOSTNAME1 HOSTNAME2')
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('Added HOSTNAME1')
    assert lines[1].startswith('Added HOSTNAME2')
    assert 'HOSTNAME1' in table.hostnames()
    assert 'HOSTNAME2' in table.hostnames()

    # action: remove
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'remove HOSTNAME1 HOSTNAME2')
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('Removed HOSTNAME1')
    assert lines[1].startswith('Removed HOSTNAME2')
    assert 'HOSTNAME1' not in table.hostnames()
    assert 'HOSTNAME2' not in table.hostnames()

    # action: insert
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'insert ABC def XYZ')
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('Inserted ABC')
    assert lines[1].startswith('Inserted def')
    assert lines[2].startswith('Inserted XYZ')
    assert 'ABC' in table.hostnames()
    assert 'def' in table.hostnames()
    assert 'XYZ' in table.hostnames()

    # action: delete
    sys.stdout = open(out, 'w')
    args = get_args(base_command + 'delete ABC def XYZ')
    args.func(args)
    sys.stdout.close()
    lines = [line.strip() for line in open(out, 'r').readlines()]
    assert lines[0].startswith('Deleted ABC')
    assert lines[1].startswith('Deleted def')
    assert lines[2].startswith('Deleted XYZ')
    assert 'ABC' not in table.hostnames()
    assert 'def' not in table.hostnames()
    assert 'XYZ' not in table.hostnames()
