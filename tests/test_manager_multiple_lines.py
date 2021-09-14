import json
import time
import socket
import threading

import conftest

from msl.network import connect
from msl.network.constants import TERMINATION, NOTIFICATION_UUID
from msl.examples.network import Echo


def test_from_service():
    # this tests that the Manager can handle multiple
    # replies from a Service in a single network packet

    service_connected = []
    notifications = []

    def create_socket_service():
        name = 'ManualService'
        with socket.socket() as sock:
            sock.connect(('localhost', manager.port))
            service_connected.append(True)

            # receive the "username" request
            request = json.loads(sock.recv(1024))
            assert request['attribute'] == 'username'
            sock.sendall(json.dumps({
                'error': False,
                'result': manager.admin_username,
                'requester': request['requester'],
                'uuid': request['uuid'],
            }).encode() + TERMINATION)

            # receive the "password" request
            request = json.loads(sock.recv(1024))
            assert request['attribute'] == 'password'
            sock.sendall(json.dumps({
                'error': False,
                'result': manager.admin_password,
                'requester': request['requester'],
                'uuid': request['uuid'],
            }).encode() + TERMINATION)

            # receive the "identity" request
            request = json.loads(sock.recv(1024))
            assert request['attribute'] == 'identity'
            sock.sendall(json.dumps({
                'error': False,
                'result': {
                    'type': 'service',
                    'name': name,
                    'attributes': {'multiple': ''},
                },
                'requester': request['requester'],
                'uuid': request['uuid'],
            }).encode() + TERMINATION)

            # receive the request from the Client
            request = json.loads(sock.recv(1024))
            response = json.dumps({
                'error': False,
                'result': 'the request was a success!',
                'requester': request['requester'],
                'uuid': request['uuid']}).encode()
            notify1 = json.dumps({
                'error': False,
                'result': [[1], {'a': 1}],
                'service': name,
                'uuid': NOTIFICATION_UUID,
            }).encode()
            notify2 = json.dumps({
                'error': False,
                'result': [[2], {'b': 2}],
                'service': name,
                'uuid': NOTIFICATION_UUID,
            }).encode()
            sock.sendall(notify1 + TERMINATION + response + TERMINATION + notify2 + TERMINATION)

            # wait for the Manager to shutdown
            sock.recv(1024)

    def handle_notification(*args, **kwargs):
        notifications.append([args, kwargs])

    # start the Manager
    manager = conftest.Manager(disable_tls=True)

    # start the Service
    t = threading.Thread(target=create_socket_service, daemon=True)
    t.start()
    while not service_connected:
        time.sleep(0.1)

    # perform the test
    cxn = connect(**manager.kwargs)
    link = cxn.link('ManualService')
    link.notification_handler = handle_notification
    reply = link.multiple()
    assert reply == 'the request was a success!'
    assert notifications == [[(1,), {'a': 1}], [(2,), {'b': 2}]]

    manager.shutdown(connection=cxn)


def test_from_client():
    # this tests that the Manager can handle multiple
    # requests from a Client in a single network packet

    manager = conftest.Manager(Echo, disable_tls=True)

    with socket.socket() as sock:
        sock.connect(('localhost', manager.port))

        # send all data as though the Client is connected via a terminal

        # receive the "username" request
        request = json.loads(sock.recv(1024))
        assert request['attribute'] == 'username'
        sock.sendall(manager.admin_username.encode() + TERMINATION)

        # receive the "password" request
        request = json.loads(sock.recv(1024))
        assert request['attribute'] == 'password'
        sock.sendall(manager.admin_password.encode() + TERMINATION)

        # receive the "identity" request
        request = json.loads(sock.recv(1024))
        assert request['attribute'] == 'identity'
        sock.sendall(b'client' + TERMINATION)

        # link with Echo
        sock.sendall(b'link Echo' + TERMINATION)
        reply = json.loads(sock.recv(1024))
        assert 'echo' in reply['result']['attributes']

        # send multiple lines to the Manager
        sock.sendall(b'Echo echo 1' + TERMINATION +
                     b'Echo echo 1 2' + TERMINATION +
                     b'Echo echo x=3' + TERMINATION)

        reply1 = json.loads(sock.recv(1024))
        reply2 = json.loads(sock.recv(1024))
        reply3 = json.loads(sock.recv(1024))
        assert reply1['result'] == [[1], {}]
        assert reply2['result'] == [[1, 2], {}]
        assert reply3['result'] == [[], {'x': 3}]

    manager.shutdown()
