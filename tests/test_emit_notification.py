import time

import conftest

from msl.network import connect, LinkedClient
from msl.examples.network import Heartbeat, Echo


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
