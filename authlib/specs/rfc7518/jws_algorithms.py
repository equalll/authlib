# -*- coding: utf-8 -*-
"""
    authlib.specs.rfc7518.jws
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    "alg" (Algorithm) Header Parameter Values for JWS per `Section 3`_.

    .. _`Section 3`: https://tools.ietf.org/html/rfc7518#section-3
"""

import binascii
import hmac
import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key, load_pem_public_key, load_ssh_public_key
)
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey, RSAPublicKey
)
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey, EllipticCurvePublicKey, ECDSA
)
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature, encode_dss_signature
)
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
from authlib.specs.rfc7515 import JWSAlgorithm
from authlib.common.encoding import to_bytes


class NoneAlgorithm(JWSAlgorithm):
    def prepare_sign_key(self, key):
        return None

    def prepare_verify_key(self, key):
        return None

    def sign(self, msg, key):
        return b''

    def verify(self, msg, key, sig):
        return False


class HMACAlgorithm(JWSAlgorithm):
    def __init__(self, hash_alg):
        self.hash_alg = hash_alg

    def prepare_sign_key(self, key):
        return to_bytes(key)

    def prepare_verify_key(self, key):
        key = to_bytes(key)
        return key

    def sign(self, msg, key):
        return hmac.new(key, msg, self.hash_alg).digest()

    def verify(self, msg, key, sig):
        return hmac.compare_digest(sig, self.sign(msg, key))


class RSAAlgorithm(JWSAlgorithm):
    def __init__(self, hash_alg):
        self.hash_alg = hash_alg

    def prepare_sign_key(self, key):
        if isinstance(key, RSAPrivateKey):
            return key
        key = to_bytes(key)
        return load_pem_private_key(key, password=None, backend=default_backend())

    def prepare_verify_key(self, key):
        if isinstance(key, RSAPublicKey):
            return key
        key = to_bytes(key)
        if key.startswith(b'ssh-rsa'):
            return load_ssh_public_key(key, backend=default_backend())
        else:
            return load_pem_public_key(key, backend=default_backend())

    def sign(self, msg, key):
        return key.sign(msg, padding.PKCS1v15(), self.hash_alg())

    def verify(self, msg, key, sig):
        try:
            key.verify(sig, msg, padding.PKCS1v15(), self.hash_alg())
            return True
        except InvalidSignature:
            return False


class ECAlgorithm(JWSAlgorithm):
    def __init__(self, hash_alg):
        self.hash_alg = hash_alg

    def prepare_sign_key(self, key):
        if isinstance(key, EllipticCurvePrivateKey):
            return key
        key = to_bytes(key)
        return load_pem_private_key(key, password=None, backend=default_backend())

    def prepare_verify_key(self, key):
        if isinstance(key, EllipticCurvePublicKey):
            return key
        if key.startswith(b'ecdsa-sha2-'):
            return load_ssh_public_key(key, backend=default_backend())
        return load_pem_public_key(key, backend=default_backend())

    def sign(self, msg, key):
        der_sig = key.sign(msg, ECDSA(self.hash_alg()))

        return der_to_raw_signature(der_sig, key.curve)

    def verify(self, msg, key, sig):
        try:
            der_sig = raw_to_der_signature(sig, key.curve)
        except ValueError:
            return False

        try:
            key.verify(der_sig, msg, ECDSA(self.hash_alg()))
            return True
        except InvalidSignature:
            return False


class RSAPSSAlgorithm(RSAAlgorithm):
    def sign(self, msg, key):
        return key.sign(
            msg,
            padding.PSS(
                mgf=padding.MGF1(self.hash_alg()),
                salt_length=self.hash_alg.digest_size
            ),
            self.hash_alg()
        )

    def verify(self, msg, key, sig):
        try:
            key.verify(
                sig,
                msg,
                padding.PSS(
                    mgf=padding.MGF1(self.hash_alg()),
                    salt_length=self.hash_alg.digest_size
                ),
                self.hash_alg()
            )
            return True
        except InvalidSignature:
            return False


JWS_ALGORITHMS = {
    'none': NoneAlgorithm(),
    'HS256': HMACAlgorithm(hashlib.sha256),
    'HS384': HMACAlgorithm(hashlib.sha384),
    'HS512': HMACAlgorithm(hashlib.sha512),
    'RS256': RSAAlgorithm(hashes.SHA256),
    'RS384': RSAAlgorithm(hashes.SHA384),
    'RS512': RSAAlgorithm(hashes.SHA512),
    'ES256': ECAlgorithm(hashes.SHA256),
    'ES384': ECAlgorithm(hashes.SHA384),
    'ES512': ECAlgorithm(hashes.SHA512),
    'PS256': RSAPSSAlgorithm(hashes.SHA256),
    'PS384': RSAPSSAlgorithm(hashes.SHA384),
    'PS512': RSAPSSAlgorithm(hashes.SHA512)
}


def number_to_bytes(num, num_bytes):
    padded_hex = '%0*x' % (2 * num_bytes, num)
    big_endian = binascii.a2b_hex(padded_hex.encode('ascii'))
    return big_endian


def bytes_to_number(string):
    return int(binascii.b2a_hex(string), 16)


def der_to_raw_signature(der_sig, curve):
    length = (curve.key_size + 7) // 8
    r, s = decode_dss_signature(der_sig)
    return number_to_bytes(r, length) + number_to_bytes(s, length)


def raw_to_der_signature(raw_sig, curve):
    length = (curve.key_size + 7) // 8

    if len(raw_sig) != 2 * length:
        raise ValueError('Invalid signature')

    r = bytes_to_number(raw_sig[:length])
    s = bytes_to_number(raw_sig[length:])
    return encode_dss_signature(r, s)
