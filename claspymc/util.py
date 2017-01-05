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


def print_hex_dump(contents,
                   print_all=False,
                   format_line=None,
                   omit_line=None):

    def _format_line(offset, data):
        return "| {:02x} {:04x} | {: <47} | {: <16} |".format(
            (offset >> 16) & 0xFF,
            offset & 0xFFFF,
            ' '.join('{:02x}'.format(x) for x in data),
            ''.join((chr(x) if (0x20 <= x < 0x7f) else '.') for x in data))

    if format_line is None:
        format_line = _format_line

    if omit_line is None:
        omit_line = "|         |                                                 |                  |"

    previous_row = None
    omitted = 0
    for pos in range(0x0000, len(contents), 16):
        row = contents[pos:pos+16]
        if row != previous_row or print_all:
            if omitted != 0:
                if omitted > 1:
                    print(omit_line)
                else:
                    print(format_line(pos-16, previous_row))

            print(format_line(pos, row))

            omitted = 0
        else:
            omitted += 1

        previous_row = row
