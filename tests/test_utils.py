from msl.network import utils


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
        assert isinstance(d['parameters'], dict) and not d['parameters']

    for item in ['hello GooDbye x=-1 y=4', 'hello GooDbye x =  -1   y =    4']:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'hello'
        assert d['attribute'] == 'GooDbye'
        assert len(d['parameters']) == 2
        assert d['parameters']['x'] == -1
        assert d['parameters']['y'] == 4

    for item in ['hello goodbye x="1 2" y=3', '   "hello"  "goodbye"   x = "1 2"   y   =3   ']:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'hello'
        assert d['attribute'] == 'goodbye'
        assert len(d['parameters']) == 2
        assert d['parameters']['x'] == '1 2'
        assert d['parameters']['y'] == 3

    d = utils.parse_terminal_input('"hello world" goodbye w = .62 x=1 y=-4.2 z="test" ')
    assert d['service'] == 'hello world'
    assert d['attribute'] == 'goodbye'
    assert len(d['parameters']) == 4
    assert d['parameters']['w'] == 0.62
    assert d['parameters']['x'] == 1
    assert d['parameters']['y'] == -4.2
    assert d['parameters']['z'] == 'test'

    d = utils.parse_terminal_input('"hello world today" goodbye')
    assert d['service'] == 'hello world today'
    assert d['attribute'] == 'goodbye'
    assert isinstance(d['parameters'], dict) and not d['parameters']

    d = utils.parse_terminal_input('"hello world today" good_bye x=None y=true z=test w=false')
    assert d['service'] == 'hello world today'
    assert d['attribute'] == 'good_bye'
    assert len(d['parameters']) == 4
    assert not d['parameters']['w']
    assert d['parameters']['x'] is None
    assert d['parameters']['y']
    assert d['parameters']['z'] == 'test'

    d = utils.parse_terminal_input('"String Editor" concat s1="first string" x=1  s2=" the second string" ')
    assert d['service'] == 'String Editor'
    assert d['attribute'] == 'concat'
    assert len(d['parameters']) == 3
    assert d['parameters']['s1'] == 'first string'
    assert d['parameters']['x'] == 1
    assert d['parameters']['s2'] == ' the second string'

    d = utils.parse_terminal_input('Vector cross_product x=[1,2,3] y=[4,5,6]')
    assert d['service'] == 'Vector'
    assert d['attribute'] == 'cross_product'
    assert len(d['parameters']) == 2
    assert d['parameters']['x'] == [1, 2, 3]
    assert d['parameters']['y'] == [4, 5, 6]

    d = utils.parse_terminal_input('Math is_null w=none x=None y=NULL z=null')
    assert d['service'] == 'Math'
    assert d['attribute'] == 'is_null'
    assert len(d['parameters']) == 4
    assert d['parameters']['w'] is None
    assert d['parameters']['x'] is None
    assert d['parameters']['y'] is None
    assert d['parameters']['z'] is None

    for item in ['link Basic Math', 'linkBasic Math', 'link "Basic Math"', 'link  Basic Math ']:
        d = utils.parse_terminal_input(item)
        assert d['service'] is None
        assert d['attribute'] == 'link'
        assert d['parameters']['service'] == 'Basic Math'

    for item in ['disconnect', '__disconnect__', 'exit', 'EXIT']:
        d = utils.parse_terminal_input(item)
        assert d['service'] == 'self'
        assert d['attribute'] == '__disconnect__'
        assert isinstance(d['parameters'], dict) and not d['parameters']

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
