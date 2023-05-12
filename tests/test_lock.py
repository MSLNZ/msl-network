import pytest

import conftest
from msl.examples.network import Echo
from msl.network import LinkedClient
from msl.network import connect


def test_raises_unlinked():
    # Test that a Client must first establish a Link before acquiring a lock
    # This intentionally accesses a private method

    manager = conftest.Manager(Echo)
    cxn = connect(**manager.kwargs)

    with pytest.raises(RuntimeError, match=r'cannot acquire a lock because it is not linked'):
        cxn._new_request('Manager', 'acquire_lock', 'Echo', shared=False)

    # releasing a lock if a link does not exist is okay
    assert cxn._new_request('Manager', 'release_lock', 'Echo') == []

    # but an error is raised if the Service name is invalid
    with pytest.raises(RuntimeError, match=r"'Invalid' service does not exist, .* cannot release the lock"):
        cxn._new_request('Manager', 'release_lock', 'Invalid')

    echo = cxn.link('Echo')
    with pytest.raises(RuntimeError, match=r"'Invalid' service does not exist, .* cannot acquire a lock"):
        cxn._new_request('Manager', 'acquire_lock', 'Invalid', shared=False)
    echo.unlink()

    manager.shutdown(connection=cxn)


def test_exclusive():
    manager = conftest.Manager(Echo)
    cxn1 = connect(**manager.kwargs)

    echo1 = cxn1.link('Echo')
    links = echo1.acquire_lock()
    assert links == [str(cxn1)]
    assert echo1.echo(1) == [[1], {}]

    # re-locking is okay
    assert echo1.acquire_lock() == links
    assert echo1.acquire_lock() == links
    assert echo1.acquire_lock() == links

    # re-linking then re-locking is okay
    echo1_b = cxn1.link('Echo')
    assert echo1_b.acquire_lock() == links
    assert echo1_b.acquire_lock() == links
    assert echo1_b.acquire_lock() == links

    # another link cannot be established
    cxn2 = cxn1.spawn()
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        cxn2.link('Echo')

    # allow another Client to lock
    assert echo1.release_lock() == []

    # releasing the lock does not allow for an exclusive lock to be made
    # since the link still exists
    echo2 = cxn2.link('Echo')
    with pytest.raises(RuntimeError, match=r'cannot acquire an exclusive lock, there are 2 links'):
        echo2.acquire_lock()

    # unlink,
    echo1.unlink()

    # and now another Client can lock the Service
    assert echo2.acquire_lock() == [str(cxn2)]
    assert echo2.echo(y=2) == [[], {'y': 2}]

    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        cxn1.link('Echo')

    # don't explicitly release the lock, just disconnect
    cxn2.disconnect()

    # another Client can now get a lock (the lock was automatically released)
    cxn3 = cxn1.spawn()
    echo3 = cxn3.link('Echo')
    assert echo3.acquire_lock() == [str(cxn3)]
    assert echo3.echo(0, z='hi') == [[0], {'z': 'hi'}]
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        cxn1.link('Echo')

    # don't explicitly release the lock, just unlink
    echo3.unlink()

    # another Client can now get a lock (the lock was automatically released)
    cxn4 = cxn1.spawn()
    echo4 = cxn4.link('Echo')
    assert echo4.acquire_lock() == [str(cxn4)]
    assert echo4.echo(hello='world') == [[], {'hello': 'world'}]
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        cxn1.link('Echo')
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        cxn3.link('Echo')
    assert echo4.acquire_lock() == [str(cxn4)]
    assert echo4.release_lock() == []
    echo4.unlink()

    cxn3.disconnect()
    cxn4.disconnect()
    manager.shutdown(connection=cxn1)


def test_shared():
    manager = conftest.Manager(Echo)

    c1 = connect(**manager.kwargs)
    c2 = c1.spawn()
    c3 = connect(**manager.kwargs)
    c4 = c2.spawn()
    c5 = connect(**manager.kwargs)
    c6 = c4.spawn()

    e1 = c1.link('Echo')
    assert e1.acquire_lock(shared=True) == [str(c1)]
    # multiple times is okay, even requesting an exclusive lock
    assert e1.acquire_lock(shared=False) == [str(c1)]
    assert e1.acquire_lock(shared=True) == [str(c1)]

    # even though it is shared, a new link is not possible
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        c2.link('Echo')

    assert e1.release_lock() == []

    e2 = c2.link('Echo')

    with pytest.raises(RuntimeError, match=r'cannot acquire an exclusive lock, there are 2 links'):
        e2.acquire_lock()

    # e1 is still an active link, just not an active lock
    links = e2.acquire_lock(shared=True)
    assert len(links) == 2
    assert str(c1) in links
    assert str(c2) in links
    assert e2.release_lock() == []

    e4 = c4.link('Echo')
    with pytest.raises(RuntimeError, match=r'cannot acquire an exclusive lock, there are 3 links'):
        e4.acquire_lock()

    links = e4.acquire_lock(shared=True)
    assert len(links) == 3
    assert str(c1) in links
    assert str(c2) in links
    assert str(c4) in links

    # e1 was already linked when e4 requested a shared lock
    links = e1.acquire_lock(shared=True)
    assert len(links) == 3
    assert str(c1) in links
    assert str(c2) in links
    assert str(c4) in links

    # e2 was already linked when e4 and e1 requested a shared lock
    links = e2.acquire_lock(shared=True)
    assert len(links) == 3
    assert str(c1) in links
    assert str(c2) in links
    assert str(c4) in links

    # the links are working
    assert e1.echo(1) == [[1], {}]
    assert e2.echo(2) == [[2], {}]
    assert e4.echo(3) == [[3], {}]

    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        c3.link('Echo')

    # e1 releases, but e2 and e4 still share it
    locks = e1.release_lock()
    assert len(locks) == 2
    assert str(c2) in locks
    assert str(c4) in locks

    # the links are working (e1 did not unlink, it only released its lock)
    assert e1.echo(1) == [[1], {}]
    assert e2.echo(2) == [[2], {}]
    assert e4.echo(3) == [[3], {}]

    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        c5.link('Echo')

    # the lock automatically got released
    e2.unlink()

    # e4 still holds a lock, so no new links are allowed
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        c6.link('Echo')

    # the e1 and e4 links are still working, e2 unlinked
    assert e1.echo(1) == [[1], {}]
    with pytest.raises(AttributeError, match=r'the link has been broken'):
        e2.echo(2)
    assert e4.echo(3) == [[3], {}]

    with pytest.raises(RuntimeError, match=r'cannot acquire an exclusive lock, there are 2 links'):
        e1.acquire_lock()

    links = e1.acquire_lock(shared=True)
    assert len(links) == 2
    assert str(c1) in links
    assert str(c4) in links
    assert e4.release_lock() == [str(c1)]
    assert e1.release_lock() == []

    # all locks have been released, new links can now be made
    e3 = c3.link('Echo')
    e5 = c5.link('Echo')
    e6 = c6.link('Echo')

    assert len(e1.acquire_lock(shared=True)) == 5
    assert len(e3.acquire_lock(shared=True)) == 5
    assert len(e4.acquire_lock(shared=True)) == 5
    assert len(e5.acquire_lock(shared=True)) == 5
    assert len(e6.acquire_lock(shared=True)) == 5

    assert e1.echo(1) == [[1], {}]
    assert e3.echo('e3') == [['e3'], {}]
    assert e4.echo(3) == [[3], {}]
    assert e5.echo('e5') == [['e5'], {}]
    assert e6.echo('e6') == [['e6'], {}]

    c7 = c1.spawn()
    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        c7.link('Echo')

    assert len(e1.release_lock()) == 4
    assert len(e3.release_lock()) == 3
    assert len(e4.release_lock()) == 2
    assert e5.release_lock() == [str(c6)]
    assert e6.release_lock() == []

    c2.disconnect()
    c3.disconnect()
    c4.disconnect()
    c5.disconnect()
    c6.disconnect()

    e7 = c7.link('Echo')
    assert e7.echo(e=7) == [[], {'e': 7}]
    c7.disconnect()

    manager.shutdown(connection=c1)


def test_linked_client():
    manager = conftest.Manager(Echo)
    link = LinkedClient('Echo', **manager.kwargs)
    assert link.acquire_lock() == [str(link.client)]
    assert link.echo('hi') == [['hi'], {}]

    with pytest.raises(RuntimeError, match=r"'Echo' service is locked"):
        LinkedClient('Echo', **manager.kwargs)

    assert link.release_lock() == []

    link.unlink()

    with pytest.raises(AttributeError, match=r'acquire_lock'):
        link.acquire_lock()
    with pytest.raises(AttributeError, match=r'release_lock'):
        link.release_lock()

    manager.shutdown(connection=link.client)
