import base64
import struct
from requests.compat import is_py2

if is_py2:
    unicode_type = unicode
    byte_type = str
    text_types = (unicode, str)
else:
    unicode_type = str
    byte_type = bytes
    text_types = (str, )


def to_bytes(x, charset='utf-8', errors='strict'):
    if x is None:
        return None
    if isinstance(x, byte_type):
        return x
    if isinstance(x, unicode_type):
        return x.encode(charset, errors)
    if isinstance(x, (int, float)):
        return str(x).encode(charset, errors)
    return byte_type(x)


def to_unicode(x, charset='utf-8', errors='strict', allow_none_charset=False):
    if x is None:
        return None
    if not isinstance(x, byte_type):
        return unicode_type(x)
    if charset is None and allow_none_charset:
        return x
    return x.decode(charset, errors)


def urlsafe_b64decode(s):
    s += b'=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def urlsafe_b64encode(s):
    return base64.urlsafe_b64encode(s).rstrip(b'=')


def base64_to_int(s):
    data = urlsafe_b64decode(to_bytes(s, charset='ascii'))
    buf = struct.unpack('%sB' % len(data), data)
    return int(''.join(["%02x" % byte for byte in buf]), 16)


def int_to_base64(num):
    if num < 0:
        raise ValueError('Must be a positive integer')

    if hasattr(int, 'to_bytes'):
        s = num.to_bytes((num.bit_length() + 7) // 8, 'big', signed=False)
    else:
        buf = []
        while num:
            num, remainder = divmod(num, 256)
            buf.append(remainder)
        buf.reverse()
        s = struct.pack('%sB' % len(buf), *buf)
    return to_unicode(urlsafe_b64encode(s))
