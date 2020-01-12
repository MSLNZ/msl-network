import time

import helper  # located in the tests folder

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

    services = helper.ServiceStarter((Heartbeat, Echo))

    cxn = connect(**services.kwargs)

    link_hb = cxn.link('Heartbeat')
    lc_hb = LinkedClient('Heartbeat', **services.kwargs)

    # the Echo Service does not emit notifications so make sure that the Manager
    # does not route any notifications from Heartbeat to the links with Echo
    link_echo = cxn.link('Echo')
    link_echo.notification_handler = handler3
    lc_echo = LinkedClient('Echo', **services.kwargs)
    lc_echo.notification_handler = handler4

    link_hb.set_heart_rate(10)
    link_hb.reset()

    # the link will start to receive notifications 2 seconds earlier
    link_hb.notification_handler = handler1
    time.sleep(2)

    lc_hb.reset()
    lc_hb.notification_handler = handler2
    time.sleep(2)

    assert len(values1)
    assert len(values2)
    assert len(values3) == 0  # the Echo Service does not emit notifications
    assert len(values4) == 0  # the Echo Service does not emit notifications
    assert len(values1) > 20
    assert len(values2) > 10
    assert values1.count(5.0) == 2  # the value 5 should appear twice since reset() was called twice
    assert values2.count(5.0) == 1

    link_hb.disconnect()
    lc_hb.disconnect()
    link_echo.disconnect()
    lc_echo.disconnect()
    services.shutdown(cxn)