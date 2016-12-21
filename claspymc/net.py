#!/usr/bin/env python3

import sys
import socket

__author__ = 'Thomas Bell'

class ProtocolError(Exception):
    pass

class IllegalData(ProtocolError):
    pass

def safe_recv(sock, buflen):
    buf = bytearray()
    if buflen == 0:
        return buf

    try:
        while len(buf) < buflen:
            new_data = sock.recv(buflen - len(buf))
            if not new_data:
                break

            buf += new_data

    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)

    if len(buf) < buflen:
        raise ProtocolError("connection closed")

    return buf

def safe_send(sock, buf):
    if type(buf) is str:
        buf = buf.encode("utf8")

    try:
        sock.sendall(buf)
    except (BrokenPipeError, OSError, socket.timeout) as e:
        print(e, file=sys.stderr)
        raise ProtocolError(e)

