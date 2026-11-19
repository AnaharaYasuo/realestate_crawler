# -*- coding: utf-8 -*-
import re
from package.utils.router_controller import _generate_random_mac


def test_generate_random_mac_format_and_unicast():
    mac1 = _generate_random_mac()
    mac2 = _generate_random_mac()
    assert re.match(r"^02:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}$", mac1)
    assert mac1 != mac2
