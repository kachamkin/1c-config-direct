# Minimal reader for 1C config files taken from the Config table or from a .cf container.
import os, re, struct, zlib

GUID_RE = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def inflate(raw):
    try:
        return zlib.decompress(raw, -15)
    except zlib.error:
        return raw


def _hex(b, off, w):
    return int(b[off:off + w].decode('ascii'), 16)


def _block(c, addr, w):
    # block header: \r\n + size + ' ' + page + ' ' + next + ' ' + \r\n ; w = 8 (classic) or 16 (64-bit format)
    hs = 2 + 3 * (w + 1) + 2
    size = _hex(c, addr + 2, w)
    end = int('7' + 'f' * (w - 1), 16)
    out = bytearray(); remaining = size; cur = addr
    while cur != end and remaining > 0:
        page = _hex(c, cur + 2 + w + 1, w)
        nxt = _hex(c, cur + 2 + 2 * (w + 1), w)
        take = min(page, remaining)
        out += c[cur + hs: cur + hs + take]
        remaining -= take
        cur = nxt
    return bytes(out)


_TOC_HEADER = re.compile(rb'\r\n[0-9a-f]{8} [0-9a-f]{8} [0-9a-f]{8} \r\n')


def is_container(b):
    # header: first free block (7fffffff when there are none -- old containers rewritten in place keep a free list,
    # and its pages still hold stale text), page size, revision, reserved; the TOC block follows at offset 16
    return len(b) > 47 and _TOC_HEADER.match(b, 16) is not None


def container_index(c):
    """[(name, data block address | None)] of a v8 container (classic 32-bit addresses); c may be bytes or mmap"""
    toc = _block(c, 16, 8)
    res = []
    for i in range(0, len(toc) - 11, 12):
        a, d, _ = struct.unpack_from('<iii', toc, i)
        name = _block(c, a, 8)[20:].decode('utf-16-le', errors='replace').split('\0')[0]
        res.append((name, None if d == 0x7fffffff else d))
    return res


def container_entries(c):
    """[(name, data)] of a v8 container, data not inflated."""
    return [(n, _block(c, d, 8) if d is not None else b'') for n, d in container_index(c)]


# Newer .cf files (seen with compatibility 8.3.17, 8.3.20, 8.3.23, 8.3.27) are a small classic container holding a stub
# "empty configuration" for old readers, followed by the real one in a 64-bit container: header = 8 bytes FF,
# page size, revision, reserved (20 bytes), then blocks with 16-hex-digit fields; TOC records are 3 x uint64;
# addresses are relative to the start of the 64-bit container.
_HDR64 = re.compile(rb'\xff{8}.{12}\r\n[0-9A-Fa-f]{16} [0-9A-Fa-f]{16} [0-9A-Fa-f]{16} \r\n', re.S)
_END64 = (0xffffffffffffffff, 0x7fffffffffffffff)


def find_container64(c, limit=1 << 20):
    m = _HDR64.search(c[:limit])
    return m.start() if m else None


def _block64(c, base, addr):
    hs = 2 + 3 * 17 + 2
    p = base + addr
    size = int(c[p + 2:p + 18], 16)
    out = bytearray(); remaining = size; cur = addr
    while remaining > 0 and cur not in _END64:
        p = base + cur
        page = int(c[p + 19:p + 35], 16)
        nxt = int(c[p + 36:p + 52], 16)
        take = min(page, remaining)
        out += c[p + hs:p + hs + take]
        remaining -= take
        cur = nxt
    return bytes(out)


def container64_index(c, base):
    toc = _block64(c, base, 20)
    res = []
    for i in range(0, len(toc) - 23, 24):
        a, d, _ = struct.unpack_from('<QQQ', toc, i)
        name = _block64(c, base, a)[20:].decode('utf-16-le', errors='replace').split('\0')[0]
        res.append((name, None if d in _END64 else d))
    return res


def text(b):
    if b[:3] == b'\xef\xbb\xbf':
        b = b[3:]
    return b.decode('utf-8', errors='replace')


class Source:
    """Files of a configuration: a directory dumped from the Config table, or a .cf file.
    files: logical name -> storage key. After a dynamic update the current copy of a changed file is stored as
    "<name>_dynupdate_<guid>" (guid from the DynamicallyUpdated record); such copies replace the base names."""

    def __init__(self, path):
        if os.path.isdir(path):
            self.files = {n: os.path.join(path, n) for n in os.listdir(path) if not n.startswith('_')}
            self._get = lambda key: open(key, 'rb').read()
        else:
            import mmap
            with open(path, 'rb') as f:
                self._mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)   # big .cf files are not loaded whole
            base = find_container64(self._mm)
            self.layout = 'classic'
            if base is not None:                          # stub + 64-bit container: the real configuration is the latter
                self.layout = '64-bit container at %d' % base
                self.files = {n: d for n, d in container64_index(self._mm, base)}
                self._get = lambda key: _block64(self._mm, base, key) if key is not None else b''
            elif is_container(self._mm[:64]):
                self.files = {n: d for n, d in container_index(self._mm)}
                self._get = lambda key: _block(self._mm, key, 8) if key is not None else b''
            else:
                raise ValueError('not a 1C container: ' + path)
        # dynamic updates: DynamicallyUpdated = {1,<count>,<guid1>,<guid2>,…} in order of application; every update
        # stores the changed files as "<name>_dynupdate_<guid>", so a later copy overrides an earlier one and the base
        self.dynupdate = []
        if 'DynamicallyUpdated' in self.files:
            self.dynupdate = re.findall(GUID_RE, text(self.raw('DynamicallyUpdated')))
            for g in self.dynupdate:
                tag = '_dynupdate_' + g
                for n in [x for x in self.files if tag in x]:
                    self.files[n.replace(tag, '')] = self.files.pop(n)

    def raw(self, name):
        return inflate(self._get(self.files[name]))

    def has(self, name):
        return name in self.files


_BRACE_TOK = re.compile(r'"[^"]*(?:""[^"]*)*"|[{}]|[^,{}"\s][^,{}"\r\n]*')


def parse_brace(t):
    """1C brace text -> nested lists; atoms stay as raw tokens, strings keep their quotes ('"..."')."""
    stack = [[]]
    for m in _BRACE_TOK.finditer(t):
        s = m.group(0)
        if s == '{':
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif s == '}':
            stack.pop()
        else:
            stack[-1].append(s)
    return stack[0][0] if stack[0] else None


def unq(s):
    """'"a""b"' -> 'a"b'"""
    return s[1:-1].replace('""', '"') if isinstance(s, str) and s[:1] == '"' else s
