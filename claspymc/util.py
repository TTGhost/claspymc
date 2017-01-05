#!/usr/bin/env python3

import os
import uuid

import appdirs
from .version import APP_NAME, APP_AUTHOR, APP_VERSION

from .ecache import Cache

UUID_NAMESPACE = uuid.UUID('a71dca7e-c0f6-4399-935f-a818651f6a36')
cache = Cache((APP_NAME, APP_AUTHOR), "{}/{}".format(APP_NAME, APP_VERSION))

DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
def data_filename(server, filename):
    directory = server.config.get("data_dir", DATA_DIR)
    if not os.path.isdir(directory):
        os.mkdir(directory)

    return os.path.join(directory, filename)


def print_hex_dump(contents):
    for pos in range(0x0000, len(contents), 16):
        row = contents[pos:pos+16]
        print("{:04x} {:04x}: {: <47} | {: <16} |".format(
            (pos << 16) & 0xFFFF,
            pos & 0xFFFF,
            ' '.join('{:02x}'.format(x) for x in row),
            ''.join((chr(x) if (0x20 <= x < 0x7f) else '.') for x in row)))
