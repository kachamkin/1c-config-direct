# Read-only reader of a 1C file infobase (1Cv8.1CD, storage format 8.3.8): tables, records, blobs.
# Only what is needed to read the configuration tables (Config, ConfigSave, _ExtensionsInfo); nothing is ever written.
#
# Layout (format 8.3.8, page size from the header, 8192 in practice):
#   page 0   header: "1CDBMSV8", version 8.3.8.0, number of pages (uint32), reserved (int32), page size (uint32)
#   object   header page: sig 1C FD, fatlevel (int16), version (3 x uint32), length (uint64), page numbers (uint32...);
#            fatlevel 0 -> data pages, fatlevel 1 -> FAT pages holding pagesize/4 data page numbers each
#   page 2   root object; it is a blob store: 256-byte blocks = next block (uint32), used length (uint16), 250 data bytes;
#            block 1 = language[32], number of tables (int32), blob indexes of the table descriptions (int32...)
#   table    description = brace text {"Name",0,{"Fields",{name,type,nullable,length,precision,"CS"},...},
#            {"Indexes",...},{"Recordlock","0"},{"Files",<records object>,<blob object>,<index object>}}
#   record   1 byte "free" flag, then a record version field (type RV) if the table has one, then the other fields in
#            description order; a nullable field has a 1-byte flag in front
import mmap, re, struct

from v8cfg import Source, parse_brace, unq, text, GUID_RE

FIELD_SIZE = {'B': lambda l: l, 'L': lambda l: 1, 'N': lambda l: (l + 2) // 2, 'NC': lambda l: l * 2,
              'NVC': lambda l: l * 2 + 2, 'RV': lambda l: 16, 'NT': lambda l: 8, 'I': lambda l: 8, 'DT': lambda l: 7}


class Obj:
    """an object (file) inside the database file"""

    def __init__(self, db, page_no):
        self.db = db
        h = db.page(page_no)
        if h[:2] != b'\x1c\xfd':
            raise ValueError('no data object at page %d' % page_no)
        fat = struct.unpack_from('<h', h, 2)[0]
        self.length = struct.unpack_from('<Q', h, 16)[0]
        ps = db.ps
        n = (self.length + ps - 1) // ps
        if fat == 0:
            self.pages = list(struct.unpack_from('<%dI' % n, h, 24))
        else:
            per = ps // 4
            pages = []
            for fp in struct.unpack_from('<%dI' % ((n + per - 1) // per), h, 24):
                pages.extend(struct.unpack_from('<%dI' % per, db.page(fp), 0))
            self.pages = pages[:n]

    def read(self, off, size):
        ps, out = self.db.ps, bytearray()
        while size > 0:
            pi, po = divmod(off, ps)
            take = min(size, ps - po)
            base = self.pages[pi] * ps + po
            out += self.db.mm[base:base + take]
            off += take
            size -= take
        return bytes(out)

    def blob(self, index, length=None):
        out = bytearray()
        while index:
            blk = self.read(index * 256, 256)
            nxt, ln = struct.unpack_from('<IH', blk, 0)
            out += blk[6:6 + ln]
            index = nxt
        return bytes(out if length is None else out[:length])


class Table:
    def __init__(self, db, desc):
        t = parse_brace(desc)
        self.db, self.name, self.fields, self.files = db, unq(t[0]), [], None
        for x in t[2:]:
            if isinstance(x, list) and x and x[0] == '"Fields"':
                for fd in x[1:]:
                    self.fields.append((unq(fd[0]), unq(fd[1]), fd[2] == '1', int(fd[3])))
            elif isinstance(x, list) and x and x[0] == '"Files"':
                self.files = [int(v) for v in x[1:]]
        # the record version field (type RV) is stored right after the "free" byte, the rest in description order
        self.layout, off = [], 1
        for name, typ, null, ln in [f for f in self.fields if f[1] == 'RV'] + [f for f in self.fields if f[1] != 'RV']:
            self.layout.append((name, typ, null, ln, off))
            off += FIELD_SIZE[typ](ln) + (1 if null else 0)
        self.reclen = max(off, 5)

    def records(self, only=None):
        """dicts {FIELD: value}; NVC/NC -> str, I/NT -> (blob index, length), other types -> raw bytes"""
        data = Obj(self.db, self.files[0])
        raw = data.read(0, data.length)
        for i in range(data.length // self.reclen):
            r = raw[i * self.reclen:(i + 1) * self.reclen]
            if r[0]:                                     # free record
                continue
            rec = {}
            for name, typ, null, ln, off in self.layout:
                if only and name not in only:
                    continue
                if null:
                    if not r[off]:
                        rec[name] = None
                        continue
                    off += 1
                if typ == 'NVC':
                    k = struct.unpack_from('<H', r, off)[0]
                    rec[name] = r[off + 2:off + 2 + 2 * k].decode('utf-16-le')
                elif typ == 'NC':
                    rec[name] = r[off:off + 2 * ln].decode('utf-16-le').rstrip()
                elif typ in ('I', 'NT'):
                    rec[name] = struct.unpack_from('<II', r, off)
                else:
                    rec[name] = r[off:off + FIELD_SIZE[typ](ln)]
            yield rec

    def blobs(self):
        return Obj(self.db, self.files[1])


class OneCD:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        if self.mm[:8] != b'1CDBMSV8':
            raise ValueError('not a 1C file infobase: ' + path)
        self.version = tuple(self.mm[8:12])
        if self.version != (8, 3, 8, 0):
            raise ValueError('1CD storage format %s is not supported (only 8.3.8): %s' % ('.'.join(map(str, self.version)), path))
        self.pages_total, _, self.ps = struct.unpack_from('<IiI', self.mm, 12)
        root = Obj(self, 2)
        head = root.blob(1)
        self.lang = head[:32].rstrip(b'\0').decode('ascii', 'replace')
        n = struct.unpack_from('<i', head, 32)[0]
        self.tables = {}
        for i in struct.unpack_from('<%di' % n, head, 36):
            b = root.blob(i)
            t = Table(self, b.decode('utf-16-le') if b[1:2] == b'\0' else b.decode('utf-8', errors='replace'))
            self.tables[t.name.lower()] = t              # "Config" or "CONFIG" depending on the base

    def page(self, n):
        return self.mm[n * self.ps:(n + 1) * self.ps]

    def table(self, name):
        return self.tables.get(name.lower())


def is_1cd(path):
    try:
        with open(path, 'rb') as f:
            return f.read(8) == b'1CDBMSV8'
    except OSError:
        return False


class Source1CD(Source):
    """the Config table of a file infobase as a Source (files: name -> (blob index, length))"""

    def __init__(self, path, table='Config'):
        self.db = OneCD(path)
        t = self.db.table(table)
        if t is None:
            raise ValueError('no %s table in %s' % (table, path))
        blobs = t.blobs()
        self.files = {r['FILENAME']: r['BINARYDATA'] for r in t.records(only=('FILENAME', 'BINARYDATA'))}
        self._get = lambda key: blobs.blob(key[0], key[1]) if key and key[1] else b''
        self.layout = '1Cv8.1CD, storage format %s, table %s' % ('.'.join(map(str, self.db.version)), t.name)
        self.dynupdate = []
        if 'DynamicallyUpdated' in self.files:
            self.dynupdate = re.findall(GUID_RE, text(self.raw('DynamicallyUpdated')))
            for g in self.dynupdate:
                tag = '_dynupdate_' + g
                for n in [x for x in self.files if tag in x]:
                    self.files[n.replace(tag, '')] = self.files.pop(n)

    def facts(self):
        """ConfigSave rows and installed extensions, as the SQL source reports them"""
        out = {}
        cs = self.db.table('ConfigSave')
        out['configsave_rows'] = [str(sum(1 for _ in cs.records(only=('FILENAME',)))) if cs else '-1']
        ext = self.db.table('_ExtensionsInfo')
        names = []
        if ext:
            fld = next((f[0] for f in ext.fields if f[0].upper() == '_EXTNAME'), None)
            if fld:
                names = [r[fld] for r in ext.records(only=(fld,))]
        out['extension'] = names
        return out
