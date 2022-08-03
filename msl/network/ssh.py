"""
Helper functions for connecting to a remote computer via SSH_.

Follow these `instructions <https://winscp.net/eng/docs/guide_windows_openssh_server>`_
to install/enable an SSH_ server on Windows. You can also create an SSH_ server using the
`paramiko <https://docs.paramiko.org/en/stable/api/server.html>`_ package (which is included
when MSL-Network is installed).

The two functions :func:`.start_manager` and :func:`.parse_console_script_kwargs`
are meant to be used together to automatically start a Network
:class:`~msl.network.manager.Manager`, and possibly
:class:`~msl.network.service.Service`\\s, on a remote computer.

See :ref:`ssh-example` for an example on how to start a :class:`~msl.network.service.Service`
on a Raspberry Pi from another computer.

.. _SSH: https://www.ssh.com/academy/ssh
"""
import sys
import time
import socket
import getpass
import warnings

import paramiko
from cryptography.utils import CryptographyDeprecationWarning

from .constants import NETWORK_MANAGER_RUNNING_PREFIX
from .json import (
    serialize,
    deserialize,
)


def parse_console_script_kwargs():
    """Parses the command line for keyword arguments sent from a remote computer.

    .. versionadded:: 0.4

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


def start_manager(host, console_script_path, *, ssh_username=None, ssh_password=None,
                  timeout=10, as_sudo=False, missing_host_key_policy=None,
                  paramiko_kwargs=None, **kwargs):
    """Start a Network :class:`~msl.network.manager.Manager` on a remote computer.

    .. versionadded:: 0.4

    .. _cs: https://python-packaging.readthedocs.io/en/latest/command-line-scripts.html#the-console-scripts-entry-point

    Parameters
    ----------
    host : :class:`str`
        The hostname (or IP address) of the remote computer. For example -- ``'192.168.1.100'``,
        ``'raspberrypi'``, ``'pi@raspberrypi'``
    console_script_path : :class:`str`
        The file path to where the `console script <cs_>`_ is located on the remote computer.
    ssh_username : :class:`str`, optional
        The username to use to establish the SSH_ connection. If :data:`None` and the
        `ssh_username` is not specified in `host` then you will be asked for
        the `ssh_username`.
    ssh_password : :class:`str`, optional
        The password to use to establish the SSH_ connection. If :data:`None`
        then you will be asked for the `ssh_password`.
    timeout : :class:`int` or :class:`float`, optional
        The maximum number of seconds to wait for the SSH_ connection.
    as_sudo : :class:`bool`, optional
        Whether to run the `console script <cs_>`_ as a superuser.
    missing_host_key_policy : :class:`~paramiko.client.MissingHostKeyPolicy`, optional
        The policy to use when connecting to servers without a known host key. If
        :data:`None` then uses :class:`~paramiko.client.AutoAddPolicy`.
    paramiko_kwargs : :class:`dict`, optional
        Additional keyword arguments that are passed to :func:`ssh.connect <.connect>`.
    kwargs
        The keyword arguments in :func:`~msl.network.manager.run_forever`, and if
        that `console script <cs>`_ also starts :class:`~msl.network.service.Service`\\s
        on the remote computer as well, then the keyword arguments also found in
        :meth:`~msl.network.service.Service.start`. The `kwargs` should be parsed
        by :func:`.parse_console_script_kwargs` on the remote computer.
    """
    logfile = console_script_path + '.log'

    command = 'sudo ' + console_script_path if as_sudo else console_script_path
    command += f' --kwargs {serialize(kwargs)!r} > {logfile!r} 2>&1 &'

    if paramiko_kwargs is None:
        paramiko_kwargs = {}

    ssh_client = connect(host, username=ssh_username, password=ssh_password,
                         timeout=timeout, missing_host_key_policy=missing_host_key_policy,
                         **paramiko_kwargs)

    exec_command(ssh_client, command, timeout=timeout)

    # wait for the Manager to start
    success = False
    t0 = time.time()
    while True:
        try:
            stdout = exec_command(ssh_client, 'cat ' + logfile)  # cat is for *nix
        except RuntimeError:
            stdout = exec_command(ssh_client, 'type ' + logfile)  # type is for Windows

        for line in stdout:
            if NETWORK_MANAGER_RUNNING_PREFIX in line:
                success = True
                break
            if 'ERROR' in line or 'Error:' in line:
                ssh_client.close()
                raise RuntimeError('Cannot start Manager\n\n' + '\n'.join(stdout))

        if success:
            break

        if time.time() - t0 > timeout:
            # Just to avoid getting stuck forever.
            # Don't raise an error, maybe the Manager is running by the time
            # a Client tries to connect if the Manager is not running then
            # the Client will get an error when trying to connect.
            break

    ssh_client.close()


def connect(host, *, username=None, password=None, timeout=10, missing_host_key_policy=None, **kwargs):
    """SSH_ to a remote computer.

    .. versionadded:: 0.4

    Parameters
    ----------
    host : :class:`str`
        The hostname (or IP address) of the remote computer. For example -- ``'192.168.1.100'``,
        ``'raspberrypi'``, ``'pi@raspberrypi'``
    username : :class:`str`, optional
        The username to use to establish the SSH_ connection. If :data:`None` and the
        `username` is not specified in `host` then you will be asked for
        the `username`.
    password : :class:`str`, optional
        The password to use to establish the SSH_ connection. If :data:`None`
        then you will be asked for the `password`.
    timeout : :class:`int` or :class:`float`, optional
        The maximum number of seconds to wait for the SSH_ connection.
    missing_host_key_policy : :class:`~paramiko.client.MissingHostKeyPolicy`, optional
        The policy to use when connecting to servers without a known host key. If
        :data:`None` then uses :class:`~paramiko.client.AutoAddPolicy`.
    kwargs
        Additional keyword arguments that are passed to
        :meth:`SSHClient.connect <paramiko.client.SSHClient.connect>`.

    Returns
    -------
    :class:`~paramiko.client.SSHClient`
        The SSH_ connection to the remote computer.
    """
    if '@' in host:
        username, host = host.split('@')

    if username is None:
        username = input('Enter the SSH username: ')

    if not username:
        raise ValueError('You must specify the SSH username')

    if password is None:
        password = getpass.getpass(f'{username}@{host}\'s password: ')

    if not password:
        raise ValueError('You must specify the SSH password')

    if missing_host_key_policy is None:
        missing_host_key_policy = paramiko.AutoAddPolicy()

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(missing_host_key_policy)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=CryptographyDeprecationWarning)
        ssh_client.connect(host, username=username, password=password, timeout=timeout, **kwargs)
    return ssh_client


def exec_command(ssh_client, command, *, timeout=10):
    """Execute the SSH_ command on the remote computer.

    .. versionadded:: 0.4

    Parameters
    ----------
    ssh_client : :class:`~paramiko.client.SSHClient`
        The SSH_ client that has already established a connection to the remote computer.
        See also :func:`.connect`.
    command : :class:`str`
        The command to execute on the remote computer.
    timeout : :class:`int` or :class:`float`, optional
        The maximum number of seconds to wait for the command to finish.

    Raises
    ------
    RuntimeError
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
        raise RuntimeError(f'\nTimeout executing SSH command: {command!r}') from None
    else:
        error_message = ''.join(stderr.readlines())
        if error_message:
            ssh_client.close()
            raise RuntimeError('\n' + error_message)

    return [line.rstrip('\n') for line in lines]
