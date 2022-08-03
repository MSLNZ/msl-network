import os
import tempfile

from msl.network import utils
from msl.network.constants import DISCONNECT_REQUEST


def test_terminal_parser():

    assert utils.parse_terminal_input('') is None
    assert utils.parse_terminal_input('    ') is None
    assert utils.parse_terminal_input('hello') is None
    assert utils.parse_terminal_input('"hello"') is None
    assert utils.parse_terminal_input('"hello goodbye') is None
    assert utils.parse_terminal_input('"hello world today"') is None

    for item in ['hello goodbye', '"hello" goodbye', 'hello "goodbye"', "'hello' goodbye", "hello 'goodbye'"]:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'hello'
        assert d['attribute'] == 'goodbye'
        assert isinstance(d['args'], list) and not d['args']
        assert isinstance(d['kwargs'], dict) and not d['kwargs']

    for item in ['hello GooDbye x=-1 y=4', 'hello GooDbye x =  -1   y =    4']:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'hello'
        assert d['attribute'] == 'GooDbye'
        assert isinstance(d['args'], list) and not d['args']
        assert len(d['kwargs']) == 2
        assert d['kwargs']['x'] == -1
        assert d['kwargs']['y'] == 4

    for item in ['hello goodbye x="1 2" y=3', '   "hello"  "goodbye"   x = "1 2"   y   =3   ']:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'hello'
        assert d['attribute'] == 'goodbye'
        assert isinstance(d['args'], list) and not d['args']
        assert len(d['kwargs']) == 2
        assert d['kwargs']['x'] == '1 2'
        assert d['kwargs']['y'] == 3

    d = utils.parse_terminal_input('"hello world" goodbye w = .62 x=1 y=-4.2 z="test" ')
    assert d['service'] == 'hello world'
    assert d['attribute'] == 'goodbye'
    assert isinstance(d['args'], list) and not d['args']
    assert len(d['kwargs']) == 4
    assert d['kwargs']['w'] == 0.62
    assert d['kwargs']['x'] == 1
    assert d['kwargs']['y'] == -4.2
    assert d['kwargs']['z'] == 'test'

    d = utils.parse_terminal_input('"hello world today" goodbye')
    assert d['service'] == 'hello world today'
    assert d['attribute'] == 'goodbye'
    assert isinstance(d['args'], list) and not d['args']
    assert isinstance(d['kwargs'], dict) and not d['kwargs']

    d = utils.parse_terminal_input('"hello world today" good_bye x=None y=true z=test w=false')
    assert d['service'] == 'hello world today'
    assert d['attribute'] == 'good_bye'
    assert isinstance(d['args'], list) and not d['args']
    assert len(d['kwargs']) == 4
    assert not d['kwargs']['w']
    assert d['kwargs']['x'] is None
    assert d['kwargs']['y']
    assert d['kwargs']['z'] == 'test'

    d = utils.parse_terminal_input('"String Editor" concat s1="first string" x=1  s2=" the second string" ')
    assert d['service'] == 'String Editor'
    assert d['attribute'] == 'concat'
    assert isinstance(d['args'], list) and not d['args']
    assert len(d['kwargs']) == 3
    assert d['kwargs']['s1'] == 'first string'
    assert d['kwargs']['x'] == 1
    assert d['kwargs']['s2'] == ' the second string'

    d = utils.parse_terminal_input('"String Editor" concat "first string" 1  " the second string" ')
    assert d['service'] == 'String Editor'
    assert d['attribute'] == 'concat'
    assert len(d['args']) == 3
    assert d['args'][0] == 'first string'
    assert d['args'][1] == 1
    assert d['args'][2] == ' the second string'
    assert isinstance(d['kwargs'], dict) and not d['kwargs']

    d = utils.parse_terminal_input('"String Editor" concat "first string" 1  s1=" the second string" ')
    assert d['service'] == 'String Editor'
    assert d['attribute'] == 'concat'
    assert len(d['args']) == 2
    assert d['args'][0] == 'first string'
    assert d['args'][1] == 1
    assert len(d['kwargs']) == 1
    assert d['kwargs']['s1'] == ' the second string'

    d = utils.parse_terminal_input('Vector cross_product x=[1,2,3] y=[4,5,6]')
    assert d['service'] == 'Vector'
    assert d['attribute'] == 'cross_product'
    assert isinstance(d['args'], list) and not d['args']
    assert len(d['kwargs']) == 2
    assert d['kwargs']['x'] == [1, 2, 3]
    assert d['kwargs']['y'] == [4, 5, 6]

    d = utils.parse_terminal_input('Math is_null w=none x=None y=NULL z=null')
    assert d['service'] == 'Math'
    assert d['attribute'] == 'is_null'
    assert isinstance(d['args'], list) and not d['args']
    assert len(d['kwargs']) == 4
    assert d['kwargs']['w'] is None
    assert d['kwargs']['x'] is None
    assert d['kwargs']['y'] is None
    assert d['kwargs']['z'] is None

    for item in ['link Basic Math', 'linkBasic Math', 'link "Basic Math"', 'link  Basic Math ']:
        d = utils.parse_terminal_input(item)
        assert d['service'] is 'Manager'
        assert d['attribute'] == 'link'
        assert d['args'][0] == 'Basic Math'
        assert isinstance(d['kwargs'], dict) and not d['kwargs']

    for item in ['disconnect', DISCONNECT_REQUEST, 'exit', 'EXIT']:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'self'
        assert d['attribute'] == DISCONNECT_REQUEST
        assert isinstance(d['args'], list) and not d['args']
        assert isinstance(d['kwargs'], dict) and not d['kwargs']

    d = utils.parse_terminal_input('client')
    assert d['type'] == 'client'
    assert d['name'] == 'Client'

    d = utils.parse_terminal_input('CliEnt')
    assert d['type'] == 'client'
    assert d['name'] == 'Client'

    d = utils.parse_terminal_input('Client The Client today')
    assert d['type'] == 'client'
    assert d['name'] == 'The Client today'

    d = utils.parse_terminal_input('client "The Client"')
    assert d['type'] == 'client'
    assert d['name'] == 'The Client'

    d = utils.parse_terminal_input('ServiceName method 1.1 2.2 "another arg" x  = 3   y="4"')
    assert d['service'] == 'ServiceName'
    assert d['attribute'] == 'method'
    assert len(d['args']) == 3
    assert len(d['kwargs']) == 2
    assert d['args'][0] == 1.1
    assert d['args'][1] == 2.2
    assert d['args'][2] == 'another arg'
    assert d['kwargs']['x'] == 3
    assert d['kwargs']['y'] == '4'

    d = utils.parse_terminal_input('identity')
    assert d['service'] == 'Manager'
    assert d['attribute'] == 'identity'


def test_ensure_root():
    dirname = os.path.join(tempfile.gettempdir(), 'msl', 'network', 'testing')

    path = dirname + '/filename.txt'

    assert not os.path.isfile(path)
    assert not os.path.isdir(dirname)

    utils.ensure_root_path(path)

    assert os.path.isdir(dirname)
    assert not os.path.isfile(path)

    os.removedirs(dirname)
    assert not os.path.isdir(dirname)

    # these should not raise an error (nor create any directories)
    utils.ensure_root_path(None)  # noqa
    utils.ensure_root_path('')


def test_is_manager_regex():
    search = utils._is_manager_regex.search
    assert search('name') is None
    assert search('name:') is None
    assert search('name1') is None
    assert search('name:1') is None
    assert search('name12') is None
    assert search('Manager') is None
    assert search('Manager:') is None
    assert search('Manager[name') is None
    assert search('Manager[name:') is None
    assert search('Manager[name:1875') is None
    assert search('Manager[name:1]') is not None
    assert search('Manager[name:12]') is not None
    assert search('Manager[name:12345]') is not None
    assert search('Manager[n.a.m.e:12345]') is not None
    assert search('Manager[192.168.1.100:12345]') is not None
    assert search('manager[name:12]') is None
    assert search('Manager[name:1875] ') is None


def test_numeric_address_regex():
    # the regex pattern is not meant to be an IPv4 parser
    search = utils._numeric_address_regex.search

    # valid
    assert search('1.2.3.4') is not None
    assert search('999.999.999.999') is not None
    assert search('1.2.3.4.5') is not None
    assert search('1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa') is not None
    assert search('1.0.0.127.in-addr.arpa') is not None
    assert search('1.2.3.4444') is not None
    assert search('1.2.3.4x') is not None

    # invalid
    assert search('1.2.3') is None
    assert search('localhost') is None
    assert search('en.wikipedia.org') is None
    assert search('1111.2.3.4') is None
    assert search('1.2222.3.4') is None
    assert search('1.2.3333.4') is None
    assert search('x1.2.3.4') is None
    assert search('1x.2.3.4') is None
    assert search('1.x2.3.4') is None
    assert search('1.2x.3.4') is None
    assert search('1.2.x3.4') is None
    assert search('1.2.3x.4') is None
    assert search('1.2.3.x4') is None
