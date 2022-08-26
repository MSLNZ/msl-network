import threading
import time

import conftest
from msl.examples.network import Echo
from msl.examples.network import Heartbeat
from msl.network import LinkedClient
from msl.network import Service
from msl.network import connect


def test_client_linkedclient_handlers():

    values1 = []
    values2 = []
    values3 = []
    values4 = []

    def handler1(counter):  # don't need to specify kwargs since none are emitted
        values1.append(counter)

    def handler2(counter):  # don't need to specify kwargs since none are emitted
        values2.append(counter)

    def handler3(*args, **kwargs):
        values3.append(1)

    def handler4(*args, **kwargs):
        values4.append(1)

    manager = conftest.Manager(Echo, Heartbeat, add_heartbeat_task=True)
    cxn = connect(**manager.kwargs)
    link_hb = cxn.link('Heartbeat')
    lc_hb = LinkedClient('Heartbeat', **manager.kwargs)

    # the Echo Service does not emit notifications so make sure that the Manager
    # does not route any notifications from Heartbeat to the links with Echo
    link_echo = cxn.link('Echo')
    link_echo.notification_handler = handler3
    lc_echo = LinkedClient('Echo', **manager.kwargs)
    lc_echo.notification_handler = handler4

    assert link_echo.echo('foo', x=-1) == [['foo'], {'x': -1}]
    assert lc_echo.echo('bar', 0) == [['bar', 0], {}]

    link_hb.set_heart_rate(10)
    link_hb.reset()

    # the link will start to receive notifications 5 seconds earlier
    link_hb.notification_handler = handler1
    time.sleep(5)

    lc_hb.reset()
    lc_hb.notification_handler = handler2
    time.sleep(5)

    assert len(values1) > 30
    assert len(values1) > len(values2) * 1.5  # ideally len(values1) == len(values2) * 2
    assert len(values3) == 0  # the Echo Service does not emit notifications
    assert len(values4) == 0  # the Echo Service does not emit notifications
    assert values1.count(3) == 2  # the value 3 should appear twice since reset() was called twice
    assert values2.count(3) == 1

    assert link_echo.echo(foo='bar') == [[], {'foo': 'bar'}]
    assert lc_echo.echo() == [[], {}]

    link_hb.unlink()
    lc_hb.unlink()
    link_echo.disconnect()  # disconnect is an alias for unlink
    lc_echo.disconnect()
    manager.shutdown(connection=cxn)


def test_threadsafe():

    class ThreadIDs(Service):

        def get_thread_ids(self):
            for i in range(10):
                self.emit_notification_threadsafe(i, index=i+10)
            return {
                'loop_thread_id': self.loop_thread_id,
                'current_thread_id': threading.get_ident(),
                'main_thread_id': threading.main_thread().ident,
                'asyncio_thread_id': self._loop._thread_id,
            }

    def handler(*args, **kwargs):
        assert len(args) == 1
        assert len(kwargs) == 1
        arguments.append(args[0])
        keywords.append(kwargs['index'])

    arguments = []
    keywords = []

    manager = conftest.Manager(ThreadIDs)

    cxn = connect(**manager.kwargs)
    ids = cxn.link('ThreadIDs')
    ids.notification_handler = handler

    assert cxn.loop_thread_id is not None
    assert cxn.loop_thread_id != threading.get_ident()
    assert cxn.loop_thread_id != threading.main_thread().ident
    assert cxn.loop_thread_id == cxn._loop._thread_id

    t = ids.get_thread_ids()
    assert t['loop_thread_id'] != t['main_thread_id']
    assert t['loop_thread_id'] != t['current_thread_id']
    assert t['loop_thread_id'] == t['asyncio_thread_id']
    assert t['main_thread_id'] == threading.get_ident()

    assert arguments == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert keywords == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]

    manager.shutdown(connection=cxn)
