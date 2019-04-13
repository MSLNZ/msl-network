"""
Helper functions for connecting to a remote computer via SSH_.

Follow these `instructions <https://winscp.net/eng/docs/guide_windows_openssh_server>`_
to install/enable an SSH_ server on Windows.

The two functions :func:`.start_manager` and :func:`.parse_console_script_kwargs`
are meant to be used together to automatically start a Network
:class:`~msl.network.manager.Manager`, and possibly
:class:`~msl.network.service.Service`\\s, on a remote computer.

See :ref:`ssh-example` for an example on how to start a :class:`~msl.network.service.Service`
on a Raspberry Pi from another computer.

.. _SSH: https://www.ssh.com/ssh/
"""
import sys
import time
import socket
import getpass
import warnings

from cryptography.utils import CryptographyDeprecationWarning
try:
    import paramiko
except ImportError:
    paramiko = None

from .exceptions import MSLNetworkError
from .json import (
    serialize,
    deserialize,
)


def parse_console_script_kwargs():
    """Parses the command line for keyword arguments sent from a remote computer.

    Returns
    -------
    :class:`dict`
        The keyword arguments that were passed from :func:`.start_manager`.
    """
    try:
        index = sys.argv.index('--kwargs')
    except ValueError:
        return {}
    else:
        return deserialize(sys.argv[index + 1])


def start_manager(hostname, console_script_path, *, ssh_username=None, ssh_password=None,
                  timeout=10, as_sudo=False, missing_host_key_policy=None,
                  paramiko_kwargs=None, **kwargs):
    """Start a Network :class:`~msl.network.manager.Manager` on a remote computer.

    .. _cs: https://python-packaging.readthedocs.io/en/latest/command-line-scripts.html#the-console-scripts-entry-point

    Parameters
    ----------
    hostname : :class:`str`
        The hostname of the remote computer. For example -- ``'192.168.1.100'``,
        ``'raspberrypi'``, ``'pi@raspberrypi'``
    console_script_path : :class:`str`
        The file path to where the `console script <cs_>`_ is located on the remote computer.
    ssh_username : :class:`str`, optional
        The username to use to establish the SSH_ connection. If :data:`None` and the
        `ssh_username` is not specified in `hostname` then you will be asked for
        the `ssh_username`.
    ssh_password : :class:`str`, optional
        The password to use to establish the SSH_ connection. If :data:`None`
        then you will be asked for the `ssh_password`.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait for the SSH_ connection.
    as_sudo : :class:`bool`, optional
        Whether to run the `console script <cs_>`_ as a superuser.
    missing_host_key_policy : :class:`~paramiko.client.MissingHostKeyPolicy`, optional
        The policy to use when connecting to servers without a known host key. If
        :data:`None` then uses :class:`~paramiko.client.AutoAddPolicy`.
    paramiko_kwargs : :class:`dict`, optional
        Additional keyword arguments that are passed to :func:`.connect`.
    kwargs
        The keyword arguments in :func:`~msl.network.manager.run_forever`, and if
        that `console script <cs>`_ also starts :class:`~msl.network.service.Service`\\s
        on the remote computer as well then the keyword arguments also found in
        :meth:`~msl.network.service.Service.start`. The `kwargs` should be parsed
        by :func:`.parse_console_script_kwargs` on the remote computer.
    """
    logfile = console_script_path + '.log'

    command = 'sudo ' + console_script_path if as_sudo else console_script_path
    command += ' --kwargs {!r} > {!r} 2>&1 &'.format(serialize(kwargs), logfile)

    if paramiko_kwargs is None:
        paramiko_kwargs = {}

    ssh_client = connect(hostname, username=ssh_username, password=ssh_password,
                         timeout=timeout, missing_host_key_policy=missing_host_key_policy,
                         **paramiko_kwargs)

    exec_command(ssh_client, command, timeout=timeout)

    # wait for the Manager to start
    success = False
    t0 = time.time()
    while True:
        try:
            stdout = exec_command(ssh_client, 'cat ' + logfile)  # cat is for *nix
        except MSLNetworkError:
            stdout = exec_command(ssh_client, 'type ' + logfile)  # type is for Windows

        for line in stdout:
            if 'Network Manager running' in line:
                success = True
                break
            if 'ERROR' in line or 'Error:' in line:
                ssh_client.close()
                raise MSLNetworkError('Cannot start Manager\n\n' + '\n'.join(stdout))

        if success:
            break

        if time.time() - t0 > timeout:  # just to avoid getting stuck forever
            break

    ssh_client.close()


def connect(hostname, *, username=None, password=None, timeout=10,
            missing_host_key_policy=None, **kwargs):
    """SSH_ to a remote computer.

    Parameters
    ----------
    hostname : :class:`str`
        The hostname of the remote computer. For example -- ``'192.168.1.100'``,
        ``'raspberrypi'``, ``'pi@raspberrypi'``
    username : :class:`str`, optional
        The username to use to establish the SSH_ connection. If :data:`None` and the
        `username` is not specified in `hostname` then you will be asked for
        the `username`.
    password : :class:`str`, optional
        The password to use to establish the SSH_ connection. If :data:`None`
        then you will be asked for the `password`.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait for the SSH_ connection.
    missing_host_key_policy : :class:`~paramiko.client.MissingHostKeyPolicy`, optional
        The policy to use when connecting to servers without a known host key. If
        :data:`None` then uses :class:`~paramiko.client.AutoAddPolicy`.
    kwargs
        Additional keyword arguments that are passed to
        :meth:`~paramiko.client.SSHClient.connect`.

    Returns
    -------
    :class:`~paramiko.client.SSHClient`
        The SSH_ connection to the remote computer.
    """
    if paramiko is None:
        raise ImportError('paramiko is not installed, run: pip/conda install paramiko')

    if '@' in hostname:
        username, hostname = hostname.split('@')

    if username is None:
        username = input('Enter the SSH username: ')

    if not username:
        raise ValueError('You must specify the SSH username')

    if password is None:
        password = getpass.getpass('{}@{}\'s password: '.format(username, hostname))

    if not password:
        raise ValueError('You must specify the SSH password')

    if missing_host_key_policy is None:
        missing_host_key_policy = paramiko.AutoAddPolicy()

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(missing_host_key_policy)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=CryptographyDeprecationWarning)
        ssh_client.connect(hostname, username=username, password=password, timeout=timeout, **kwargs)
    return ssh_client


def exec_command(ssh_client, command, *, timeout=10):
    """Execute the SSH_ command on the remote computer.

    Parameters
    ----------
    ssh_client : :class:`~paramiko.client.SSHClient`
        The SSH_ client that has already established a connection to the remote computer.
        See also :func:`.connect`.
    command : :class:`str`
        The command to execute on the remote computer.
    timeout : :class:`float`, optional
        The maximum number of seconds to wait for the command to finish.

    Raises
    ------
    :class:`~msl.network.exceptions.MSLNetworkError`
        If an error occurred. Either a timeout or stderr on the remote computer
        contains text from executing the `command`.

    Returns
    -------
    :class:`list` of :class:`str`
        stdout from the remote computer.
    """
    stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
    try:
        lines = stdout.readlines()
    except socket.timeout:
        ssh_client.close()
        raise MSLNetworkError('\nTimeout executing SSH command: {!r}'.format(command)) from None
    else:
        error_message = ''.join(stderr.readlines())
        if error_message:
            ssh_client.close()
            raise MSLNetworkError('\n' + error_message)

    return [line.rstrip('\n') for line in lines]