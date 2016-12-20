#!/usr/bin/env python3

from os import urandom
from hashlib import sha1

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

__author__ = 'Thomas Bell'

pkcs_padding = PKCS1v15()
backend = default_backend()

def generate_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
        backend=backend
    )
    public_key = private_key.public_key()
    return private_key, public_key

def encrypt_public_key_info(public_key):
    return public_key.encrypt(public_key.public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo), pkcs_padding)

def decrypt_with_private_key(private_key, encrypted_payload):
    private_key.decrypt(encrypted_payload, pkcs_padding)

class CryptoSocket:

    def __init__(self, sock):
        self.sock = sock
        self.cipher = None
        self.encryptor = None
        self.decryptor = None

    def init_cipher(self, cipher):
        self.cipher = cipher
        self.encryptor = cipher.encryptor()
        self.decryptor = cipher.decryptor()

    def __getattr__(self, item):
        return getattr(self.sock, item, None)

    def recv(self, bufsize, flags=0):
        if not self.cipher:
            return self.sock.recv(bufsize, flags)

        buf = self.sock.recv(bufsize, flags)
        return self.decryptor.update(buf)

    def send(self, buf, flags=0):
        if not self.cipher:
            return self.sock.send(buf, flags)

        payload = self.encryptor.update(buf)
        return self.sock.send(payload, flags)

    def sendall(self, buf, flags=0):
        if not self.cipher:
            return self.sock.sendall(buf, flags)

        payload = self.encryptor.update(buf)
        return self.sock.send(payload, flags)

class CryptoState:

    def __init__(self, conn):
        self.connection = conn
        self.server = conn.server
        self.private_key = self.server.private_key
        self.public_key = self.server.public_key
        self.verify_token = urandom(4)
        self.aes_cipher = None
        self.sock = CryptoSocket(conn._sock)

    def get_encrypted_key_info(self):
        return self.public_key.encrypt(self.public_key.public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo), pkcs_padding)

    def decrypt_rsa(self, payload):
        return self.private_key.decrypt(payload, pkcs_padding)

    def init_aes(self, shared_secret):
        self.aes_cipher = Cipher(
            algorithms.AES(shared_secret),
            modes.CFB8(shared_secret),
            backend=backend)

        self.sock.init_cipher(self.aes_cipher)

    def decrypt_aes(self, buffer):
        decrypt = self.aes_cipher.decryptor()
        payload = decrypt.update(buffer)
        payload += decrypt.finalize()
        return payload

    def generate_login_hash(self, shared_secret):
        sha = sha1()
        sha.update(b'')
        sha.update(shared_secret)
        sha.update(self.get_encrypted_key_info())
        digest = sha.digest()
        if digest[0] & 0x80:
            # calculate two's complement
            digest = [(~x) & 0xFF for x in digest]
            for i in range(len(digest)-1, -1, -1):
                digest[i] += 1
                if digest[i] != 0x00:  # overflow
                    break

            # minecraft login hashes are signed (two's complement) and strip leading zeroes
            return '-' + ''.join('{:02x}'.format(x) for x in digest).lstrip('0')
        else:
            return ''.join('{:02x}'.format(x) for x in digest).lstrip('0')
