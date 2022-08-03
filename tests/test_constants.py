import os

from msl.network import constants


def test_user_dir():
    assert os.path.expanduser('~') == constants.USER_DIR


def test_ipv4_addresses():
    assert len(constants.IPV4_ADDRESSES) > 0
