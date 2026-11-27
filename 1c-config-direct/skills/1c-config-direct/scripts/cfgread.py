# cfgread.py — read a 1C configuration straight from its storage: the Config table of a server database (MS SQL)
# or a .cf / .cfe file. No designer, no XML dump. Read-only.
#
#   py -X utf8 cfgread.py [--cache DIR] [--no-sync] <source> <command> [options]
#
# <source>:  sql:<db> | sql:<server>/<db>   rows of dbo.Config, cached and synced incrementally
#            <file.cf> | <file.cfe>          configuration file
#            <1Cv8.1CD> | <file base folder> Config table of a file infobase (storage format 8.3.8), read in place
#            <folder>                        rows already dumped one file per FileName
# commands:  info | objects | modules | module | grep | fields | export | diff | check        (see SKILL.md)
import sys
sys.dont_write_bytecode = True                          # no __pycache__ inside the skill folder
import argparse, collections, difflib, os, re, subprocess, time  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v8cfg import Source  # noqa: E402
from v8meta import Configuration, Field, normalize_query, show_type, export_path, show_value  # noqa: E402
from v8std import standard_attributes, STD_TS_RU  # noqa: E402
from onecd import Source1CD, is_1cd  # noqa: E402

NO_TEXT = ('image only', 'encrypted', 'form without module', 'binary')   # plus any 'container:…'


def note(msg):
    """service line: to stderr, after whatever stdout already holds"""
    sys.stdout.flush()
    print('# ' + msg, file=sys.stderr)
    sys.stderr.flush()


def cache_root(a):
    return a.cache or os.environ.get('CFGREAD_CACHE') or os.path.join(
        os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), '1c-config-direct')


def open_source(spec, a):
    """-> (Configuration, description, extra facts)"""
    facts = {}
    if spec.startswith('sql:'):
        rest = spec[4:]
        server, db = rest.split('/', 1) if '/' in rest else ('.', rest)
        safe = re.sub(r'[^\w.-]', '_', ('local' if server in ('.', 'localhost', '(local)') else server) + '__' + db)
        folder = os.path.join(cache_root(a), safe, 'Config')
        if not a.no_sync or not os.path.isdir(folder):
            r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(HERE, 'sql_config.ps1'),
                                '-Server', server, '-Base', db, '-Out', folder], capture_output=True, text=True, encoding='utf-8', errors='replace')
            if r.returncode != 0:
                sys.exit('SQL sync failed:\n' + (r.stderr or r.stdout).strip())
            note(r.stdout.strip())
        info = os.path.join(folder, '_info.tsv')
        if os.path.isfile(info):
            for line in open(info, encoding='utf-8-sig'):
                k, _, v = line.rstrip('\r\n').partition('\t')
                facts.setdefault(k, []).append(v)
            facts.setdefault('extension', [])
        src = Source(folder)
        desc = 'SQL %s/%s (cache %s)' % (server, db, folder)
    elif (os.path.isfile(spec) and is_1cd(spec)) or (os.path.isdir(spec) and os.path.isfile(os.path.join(spec, '1Cv8.1CD'))):
        path = spec if os.path.isfile(spec) else os.path.join(spec, '1Cv8.1CD')
        try:
            src = Source1CD(path)
        except ValueError as e:
            sys.exit(str(e))
        facts = src.facts()
        desc = 'file infobase %s (%.0f MB, modified %s)' % (
            path, os.path.getsize(path) / 1e6, time.strftime('%d.%m.%Y %H:%M', time.localtime(os.path.getmtime(path))))
    elif os.path.isdir(spec):
        src, desc = Source(spec), 'folder ' + spec
    elif os.path.isfile(spec):
        src, desc = Source(spec), 'file ' + spec
    else:
        sys.exit('source not found: ' + spec)
    return Configuration(src), desc, facts


def full_name(m):
    return '%s.%s' % (m.path, m.kind)


def has_text(fmt):
    return fmt not in NO_TEXT and not fmt.startswith('container:')


def select(mods, flt, own_only=False):
    """modules for a filter: exact module name; then the named object (with its forms and commands, or only its own
    modules when own_only); then a 'name.' prefix; then a substring"""
    if not flt:
        return list(mods)
    q = normalize_query(flt).lower().rstrip('.')
    for test in (lambda m: full_name(m).lower() == q,
                 lambda m: m.path.lower() == q or (not own_only and m.path.lower().startswith(q + '.')),
                 lambda m: full_name(m).lower().startswith(q + '.'),
                 lambda m: q in full_name(m).lower()):
        hit = [m for m in mods if test(m)]
        if hit:
            return hit
    return []


def with_texts(cfg, mods):
    for m in mods:
        fmt, txt = cfg.module_text(m.file, m.kind)
        yield m._replace(fmt=fmt, text=txt)


PROC = re.compile(r'^\s*(?:Асинх\s+)?(?:Процедура|Функция|Procedure|Function)\s+([\wА-Яа-яЁё]+)', re.I)


def proc_at(lines):
    """line index -> name of the procedure/function the line belongs to"""
    names, cur = [], ''
    for l in lines:
        m = PROC.match(l)
        if m:
            cur = m.group(1)
        names.append(cur)
        if re.match(r'^\s*(КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)\b', l, re.I):
            cur = ''
    return names


# ---------------------------------------------------------------------------------------------- commands
def cmd_info(cfg, desc, facts, a):
    vendor, version = cfg.property_strings()
    syn = cfg.synonyms.get('ru') or cfg.synonyms.get('uk') or ''
    print('source:          ', desc)
    print('configuration:   ', cfg.name, ('— ' + syn) if syn else '')
    print('kind:            ', 'extension (.cfe)' if cfg.is_extension else 'configuration')
    print('vendor/version:  ', vendor or '-', '/', version or '-')
    print('compatibility:   ', cfg.compatibility())
    if getattr(cfg.src, 'layout', None):
        print('file layout:     ', cfg.src.layout)
    if cfg.src.dynupdate:
        print('dynamic updates:  %d — changed files are read from their latest _dynupdate_ copies' % len(cfg.src.dynupdate))
    if 'configsave_rows' in facts:
        v = facts['configsave_rows'][0]
        print('ConfigSave rows: ', v, '(saved in the designer, not applied to the database: not visible here)' if v not in ('0', '-1') else '')
    if 'extension' in facts:
        print('extensions:      ', ', '.join(facts['extension']) or 'none',
              '(installed in the database, not read by this tool)' if facts['extension'] else '')
    by = collections.Counter(cfg.items[u].cls for u in cfg.top)
    print('objects:          %d top-level, %d with forms/commands/templates' % (len(cfg.top), len(cfg.items)))
    for cls, n in sorted(by.items(), key=lambda x: -x[1]):
        print('   %-30s %d' % (cls, n))
    mods = list(cfg.modules())
    fm = collections.Counter(m.fmt for m in mods)
    print('modules:         ', len(mods), dict(fm))
    print('without text:    ', sum(n for f, n in fm.items() if not has_text(f)),
          '(image only = no source supplied, encrypted = password protected)')
    print('empty:           ', sum(1 for m in mods if m.text is not None and not m.text.strip()))


def cmd_objects(cfg, desc, facts, a):
    q = normalize_query(a.filter).lower() if a.filter else ''
    for it in cfg.items.values():
        if it.cls in ('Forms', 'Templates', 'Commands') and not a.all:
            continue
        if q in it.path.lower():
            syn = it.synonyms.get('ru') or it.synonyms.get('uk') or ''
            print('%-60s %s' % (it.path, syn))


def cmd_modules(cfg, desc, facts, a):
    n = 0
    for m in with_texts(cfg, select(list(cfg.modules(with_text=False)), a.filter)):
        if a.no_text and has_text(m.fmt):
            continue
        n += 1
        print('%-80s %-20s %7s' % (full_name(m), m.fmt, len(m.text) if m.text is not None else '-'))
    note('%d modules (length "-" = no source text)' % n)


def cmd_module(cfg, desc, facts, a):
    mods = select(list(cfg.modules(with_text=False)), a.name, own_only=True)
    if not mods:
        sys.exit('no module matches %r' % a.name)
    objects = {m.path for m in mods}
    if len(mods) > 1 and len(objects) > 1 and not a.all:
        print('%d modules match, give a fuller name or --all:' % len(mods))
        for m in mods[:80]:
            print('  ', full_name(m))
        return
    lo, hi = 1, None
    if a.lines:
        p = a.lines.split('-')
        lo, hi = int(p[0] or 1), (int(p[1]) if len(p) > 1 and p[1] else None)
    for m in with_texts(cfg, mods):
        print('//////// %s   [%s, %s]' % (full_name(m), m.fmt, m.file))
        if m.text is None:
            print('(no source text: %s)' % m.fmt)
            continue
        lines = m.text.splitlines()
        for i in range(lo - 1, min(len(lines), hi or len(lines))):
            print('%5d  %s' % (i + 1, lines[i]) if a.n or a.lines else lines[i])


def cmd_grep(cfg, desc, facts, a):
    rx = re.compile(a.regex if a.re else re.escape(a.regex), re.I if a.ignore_case else 0)
    files = hits = 0
    for m in with_texts(cfg, select(list(cfg.modules(with_text=False)), a.path)):
        if m.text is None:
            continue
        lines = m.text.splitlines()
        found = [i for i, l in enumerate(lines) if rx.search(l)]
        if not found:
            continue
        files += 1
        hits += len(found)
        if a.files:
            print('%s: %d' % (full_name(m), len(found)))
            continue
        procs = proc_at(lines) if a.proc else None
        show = sorted({j for i in found for j in range(max(0, i - a.ctx), min(len(lines), i + a.ctx + 1))})
        hitset, prev = set(found), None
        for j in show:
            if a.ctx and prev is not None and j != prev + 1:
                print('--')
            sep = ':' if j in hitset else '-'
            where = (' (%s)' % (procs[j] or 'module body')) if procs and j in hitset else ''
            print('%s%s%d%s%s %s' % (full_name(m), sep, j + 1, sep, where, lines[j].rstrip()))
            prev = j
        if a.max and hits >= a.max:
            note('stopped after %d matching lines (--max %d)' % (hits, a.max))
            return
    note('%d modules, %d matching lines' % (files, hits))


def field_rows(cfg, objects=None, standard=True):
    """(Field, StdAttr or None) object by object: standard attributes first, LineNumber of a tabular section before
    the section's own fields; a standard attribute has kind 'Standard', its Russian name and no uuid"""
    own, std = collections.defaultdict(list), collections.defaultdict(list)
    for f in cfg.fields():
        own[f.obj].append(f)
    if standard:
        for s in standard_attributes(cfg, objects):
            std[s.obj].append(s)
    as_field = lambda s: Field(s.obj, 'Standard', s.ts, s.ru, '', s.types)
    for it, tree in cfg.trees():
        if objects is not None and it.path not in objects:
            continue
        by_ts = collections.OrderedDict()
        for s in std[it.path]:
            if not s.ts:
                yield as_field(s), s
            else:
                by_ts.setdefault(s.ts, []).append(s)
        for f in own[it.path]:
            for s in by_ts.pop(f.path, []):
                yield as_field(s), s
            yield f, None
        for rows in by_ts.values():                    # standard tabular sections, sections without attributes
            for s in rows:
                yield as_field(s), s


def show_settings(st):
    parts = []
    for k in ('Synonym', 'ToolTip', 'Comment', 'Mask', 'FillChecking', 'FillFromFillingValue'):
        v = st.get(k)
        if isinstance(v, dict):
            v = v.get('ru') or v.get('uk') or next(iter(v.values()), '')
        if v:
            parts.append('%s=%s' % (k, ' '.join(v.split())[:60]))
    return '; '.join(parts)


def cmd_fields(cfg, desc, facts, a):
    q = normalize_query(a.filter).lower().rstrip('.') if a.filter else ''
    paths = [it.path for it, tree in cfg.trees()]
    exact = [p for p in paths if p.lower() == q]
    for f, s in field_rows(cfg, set(exact or [p for p in paths if q in p.lower()]), not a.no_standard):
        name = (f.path + '.' if f.path else '') + f.name + (' (%s)' % s.name if s else '')
        extra = ''
        if s:
            st = show_settings(s.settings)
            extra = ('  [%s]' % st if st else '') + ('  (assumed)' if s.how else '')
        print('%-45s %-12s %-45s %s%s' % (f.obj, f.kind, name, show_type(f.types), extra))


def select_objects(cfg, flt):
    """top-level objects for a filter: exact object name, then 'name.' prefix, then substring"""
    objs = [(it, tree) for it, tree in cfg.trees()]
    if not flt:
        return objs
    q = normalize_query(flt).lower().rstrip('.')
    for test in (lambda it: it.path.lower() == q, lambda it: it.path.lower().startswith(q + '.'), lambda it: q in it.path.lower()):
        hit = [(it, t) for it, t in objs if test(it)]
        if hit:
            return hit
    return []


HOW = {'assumed': '  (assumed)', 'extension': '  (in extension)'}
FIELD_LISTS = ('InputByString', 'DataLockFields')


def shown(it, prop, v):
    """a property value for the screen: fields of the object itself without its name (Description, Артикул)"""
    if prop in FIELD_LISTS and isinstance(v, list):
        from v8comp import short
        return ', '.join(short(it.path, x) or '' for x in v)
    return show_value(v)


def cmd_props(cfg, desc, facts, a):
    objs = select_objects(cfg, a.filter)
    if a.prop:
        want = a.prop.lower()
        for it, tree in objs:
            for prop, v, how in cfg.properties(it, tree):
                if prop.lower() == want:
                    print('%-60s %s%s' % (it.path, shown(it, prop, v), HOW.get(how, '')))
        return
    for it, tree in objs:
        syn = it.synonyms.get('ru') or it.synonyms.get('uk') or ''
        print('%s%s   [format version %s]' % (it.path, ('  — ' + syn) if syn else '', tree[1][0] if isinstance(tree[1], list) else '?'))
        for prop, v, how in cfg.properties(it, tree):
            sv = shown(it, prop, v)
            if sv == '' and not a.all:
                continue
            if prop == 'Characteristics' and isinstance(v, list) and len(v) > 1:     # one characteristic per line
                for i, x in enumerate(v):
                    print('   %-34s %s%s' % (prop if i == 0 else '', x, HOW.get(how, '') if i == 0 else ''))
                continue
            print('   %-34s %s%s' % (prop, sv, HOW.get(how, '')))


def cmd_usedby(cfg, desc, facts, a):
    q = normalize_query(a.name).rstrip('.')
    ql = q.lower()
    hits = 0
    for it, tree in cfg.trees():
        for prop, v, how in cfg.properties(it, tree):
            if prop in FIELD_LISTS and it.path.lower() == ql:   # the object's own input-by-string fields are no usage
                continue
            vals = v if isinstance(v, list) else [v] if isinstance(v, str) else []
            for x in vals:
                xl = x.lower()
                if xl == ql or xl.startswith(ql + '.'):
                    print('%-60s %-28s %s' % (it.path, prop, x))
                    hits += 1
    if a.types:                                        # attributes whose type refers to the object
        from v8meta import SINGULAR
        cls, _, name = q.partition('.')
        single = SINGULAR.get(cls, cls[:-1]).lower()
        for f in cfg.fields():
            for k, v in f.types:
                if k in ('Type', 'TypeSet') and isinstance(v, str) and '.' in v:
                    tcls, _, tname = v.partition('.')
                    if tname.lower() == name.lower() and tcls.lower().startswith(single):
                        print('%-60s %-28s %s' % (f.obj, 'type: ' + ((f.path + '.') if f.path else '') + f.name, v))
                        hits += 1
    note('%d references to %s' % (hits, q))


def cmd_export(cfg, desc, facts, a):
    os.makedirs(a.dir, exist_ok=True)
    n = skipped = 0
    for m in with_texts(cfg, select(list(cfg.modules(with_text=False)), a.path)):
        if m.text is None:
            skipped += 1
            continue
        p = os.path.join(a.dir, export_path(m))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(m.text)
        n += 1
    with open(os.path.join(a.dir, 'objects.tsv'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        for it in cfg.items.values():
            f.write('%s\t%s\t%s\t%s\n' % (it.path, it.cls, it.uuid, it.synonyms.get('ru') or it.synonyms.get('uk') or ''))
    if not a.no_fields:
        with open(os.path.join(a.dir, 'fields.tsv'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
            for fl, s in field_rows(cfg):
                f.write('%s\t%s\t%s\t%s\t%s\n' % (fl.obj, fl.kind, (fl.path + '.' if fl.path else '') + fl.name, show_type(fl.types), fl.uuid))
    with open(os.path.join(a.dir, 'props.tsv'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        for it, tree in cfg.trees():
            for prop, v, how in cfg.properties(it, tree):
                f.write('%s\t%s\t%s\t%s\n' % (it.path, prop, show_value(v).replace('\t', ' ').replace('\n', ' '), how))
    print('exported %d modules to %s (%d without source text skipped); objects.tsv, props.tsv%s' % (
        n, a.dir, skipped, '' if a.no_fields else ', fields.tsv'))


def cmd_diff(cfg, desc, facts, a):
    other, desc2, _ = open_source(a.other, a)
    m1 = {full_name(m): m.text for m in with_texts(cfg, select(list(cfg.modules(with_text=False)), a.path))}
    m2 = {full_name(m): m.text for m in with_texts(other, select(list(other.modules(with_text=False)), a.path))}
    norm = lambda t: None if t is None else t.replace('\r\n', '\n')
    added = sorted(set(m2) - set(m1)); removed = sorted(set(m1) - set(m2))
    changed = sorted(k for k in set(m1) & set(m2) if norm(m1[k]) != norm(m2[k]))
    print('A = %s\nB = %s' % (desc, desc2))
    print('modules: %d only in A, %d only in B, %d changed' % (len(removed), len(added), len(changed)))
    for k in removed:
        print('  - only A ', k)
    for k in added:
        print('  + only B ', k)
    for k in changed:
        a_t, b_t = (m1[k] or '').splitlines(), (m2[k] or '').splitlines()
        d = [l for l in difflib.unified_diff(a_t, b_t, lineterm='', n=0) if l[:1] in '+-' and l[:3] not in ('---', '+++')]
        print('  ~ changed %s  (+%d -%d lines)' % (k, sum(1 for l in d if l[0] == '+'), sum(1 for l in d if l[0] == '-')))
        if a.show and (a.show == '*' or normalize_query(a.show).lower() in k.lower()):
            for l in difflib.unified_diff(a_t, b_t, 'A/' + k, 'B/' + k, lineterm='', n=a.ctx):
                print('      ' + l)
    if a.props:
        q = normalize_query(a.path).lower() if a.path else ''
        p1 = {(it.path, prop): show_value(v) for it, tree in cfg.trees() if q in it.path.lower() for prop, v, how in cfg.properties(it, tree)}
        p2 = {(it.path, prop): show_value(v) for it, tree in other.trees() if q in it.path.lower() for prop, v, how in other.properties(it, tree)}
        changed_p = sorted(k for k in set(p1) & set(p2) if p1[k] != p2[k])
        print('properties: %d changed' % len(changed_p))
        for k in changed_p:
            print('  ~ %s %s | %s -> %s' % (k[0], k[1], p1[k][:80], p2[k][:80]))
    if a.fields:
        q = normalize_query(a.path).lower() if a.path else ''
        f1 = {'%s %s' % (f.obj, (f.path + '.' if f.path else '') + f.name): show_type(f.types) for f, s in field_rows(cfg) if q in f.obj.lower()}
        f2 = {'%s %s' % (f.obj, (f.path + '.' if f.path else '') + f.name): show_type(f.types) for f, s in field_rows(other) if q in f.obj.lower()}
        print('fields: %d only in A, %d only in B, %d with another type' % (
            len(set(f1) - set(f2)), len(set(f2) - set(f1)), sum(1 for k in set(f1) & set(f2) if f1[k] != f2[k])))
        for k in sorted(set(f1) - set(f2)):
            print('  - only A ', k, f1[k])
        for k in sorted(set(f2) - set(f1)):
            print('  + only B ', k, f2[k])
        for k in sorted(k for k in set(f1) & set(f2) if f1[k] != f2[k]):
            print('  ~ type   ', k, '|', f1[k], '->', f2[k])


def cmd_check(cfg, desc, facts, a):
    """self-test against an XML dump of the same configuration: module texts by path, field types by uuid"""
    import xml.etree.ElementTree as ET
    from v8cfg import container_entries, inflate, text
    conf = a.conf
    res = collections.Counter(); bad = []; seen = set()
    for m in cfg.modules():
        if m.text is None or not m.text.strip():
            res['empty or no source'] += 1
            continue
        p = os.path.join(conf, export_path(m))
        if m.kind == 'FormModule' and not os.path.isfile(p):
            p = os.path.join(os.path.dirname(os.path.dirname(p)), 'Form.bin')
        if not os.path.isfile(p):
            res['no XML file'] += 1; bad.append(('no XML file', full_name(m)))
            continue
        seen.add(os.path.normcase(p))
        raw = open(p, 'rb').read()
        x = text(inflate(dict(container_entries(raw)).get('module', b''))) if p.endswith('Form.bin') else text(raw)
        if x == m.text:
            res['module text equal'] += 1
        else:
            res['module text differs'] += 1; bad.append(('text differs', full_name(m)))
    left = []                                           # non-empty modules of the dump (.bsl and ordinary Form.bin) not met above
    for dp, dns, fns in os.walk(conf):
        for fn in fns:
            p = os.path.join(dp, fn)
            if not (fn.endswith('.bsl') or fn == 'Form.bin') or os.path.normcase(p) in seen:
                continue
            b = open(p, 'rb').read()
            if fn == 'Form.bin':
                b = inflate(dict(container_entries(b)).get('module', b'')) if b[:4] == b'\xff\xff\xff\x7f' else b''
            if b.lstrip(b'\xef\xbb\xbf').strip():
                left.append(os.path.relpath(p, conf))
    print('modules vs XML:', dict(res), '| non-empty modules in XML not matched:', len(left))
    for b in bad[:10]:
        print('   ', b)
    for l in left[:10]:
        print('    XML only:', l)
    MD, V8 = '{http://v8.1c.ru/8.3/MDClasses}', '{http://v8.1c.ru/8.1/data/core}'

    def xml_type(t):
        sq, nq, dq = t.find(V8 + 'StringQualifiers'), t.find(V8 + 'NumberQualifiers'), t.find(V8 + 'DateQualifiers')
        out = []
        for e in t:
            tag = e.tag.replace(V8, '')
            if tag == 'Type':
                v = e.text
                if v == 'xs:string':
                    out.append(('String', (sq.findtext(V8 + 'Length'), sq.findtext(V8 + 'AllowedLength')) if sq is not None else None))
                elif v == 'xs:decimal':
                    out.append(('Number', (nq.findtext(V8 + 'Digits'), nq.findtext(V8 + 'FractionDigits'), nq.findtext(V8 + 'AllowedSign')) if nq is not None else None))
                elif v == 'xs:dateTime':
                    out.append(('Date', dq.findtext(V8 + 'DateFractions') if dq is not None else None))
                elif v == 'xs:boolean':
                    out.append(('Boolean', None))
                else:
                    out.append(('Type', v.split(':')[-1]))
            elif tag == 'TypeSet':
                v = e.text.split(':')[-1]
                out.append(('TypeSet', 'AnyIBRef' if v == 'AnyRef' else v))   # older dump formats say AnyRef
        return out

    xf = {}
    for dp, dns, fns in os.walk(conf):
        if (os.sep + 'Ext' + os.sep) in (dp + os.sep):
            continue
        for fn in fns:
            if not fn.endswith('.xml'):
                continue
            try:
                root = ET.parse(os.path.join(dp, fn)).getroot()
            except ET.ParseError:
                continue
            obj = next(iter(root), None)
            if obj is None or obj.get('uuid') is None:
                continue
            for e in obj.iter():
                u = e.get('uuid')
                pr = e.find(MD + 'Properties') if u else None
                if pr is None:
                    continue
                t = pr.find(MD + 'Type')
                if t is None:
                    t = pr.find(MD + 'Source')
                if t is not None and e.tag != MD + 'StyleItem':
                    xf[u] = (pr.findtext(MD + 'Name'), xml_type(t))
    fr = collections.Counter(); fbad = []; fseen = set()
    for f in cfg.fields():
        fseen.add(f.uuid)
        x = xf.get(f.uuid)
        if not x:
            fr['not in XML'] += 1; fbad.append(('not in XML', f.obj, f.name))
        elif x[0] != f.name:
            fr['name differs'] += 1; fbad.append(('name', f.obj, f.name, x[0]))
        elif sorted(map(repr, f.types)) == sorted(map(repr, x[1])):
            fr['type equal'] += 1
        else:
            fr['type differs'] += 1; fbad.append(('type', f.obj, f.name, show_type(f.types), '| XML:', show_type(x[1])))
    print('fields vs XML:', dict(fr), '| XML fields not found:', sum(1 for u in xf if u not in fseen))
    for b in fbad[:10]:
        print('   ', b)
    # object properties against the XML properties of the same objects
    from learn_props import xml_props
    from v8meta import prop_tables
    tabs = prop_tables()
    pr_res, pr_bad = collections.Counter(), collections.defaultdict(list)
    for it, tree in cfg.trees():
        xp_path = os.path.join(conf, it.cls, it.name + '.xml')
        if not os.path.isfile(xp_path):
            continue
        xp = xml_props(xp_path)
        for prop, v, how in cfg.properties(it, tree):
            if prop not in xp:
                continue
            kind = tabs.get(it.cls, {}).get(prop, {}).get('kind', 'scalar')     # ObjectBelonging is not in the tables
            xk, xv = xp[prop]
            if kind == 'list':
                got, want = tuple(sorted(v or [])), (() if xk == 'empty' else xv)
            elif kind in ('fields', 'characteristics'):                       # the order of fields matters
                got, want = tuple(v or ()), (() if xk == 'empty' else tuple(xv))
            elif kind == 'method':
                got = v or None
                want = None if xk == 'empty' else '%s.%s' % xv if xk == 'method' else xv
            elif kind == 'ref':
                got, want = (v or None), (None if xk == 'empty' else xv)
            else:
                got, want = v, ('' if xk == 'empty' else xv)
            if got == want:
                pr_res['equal'] += 1
            else:
                pr_res['differs'] += 1
                pr_bad[(it.cls, prop)].append((it.name, show_value(list(got) if isinstance(got, tuple) else got), show_value(list(want) if isinstance(want, tuple) else want)))
    print('properties vs XML:', dict(pr_res), '| properties with differences:', len(pr_bad))
    for (cls, prop), rows in sorted(pr_bad.items(), key=lambda kv: -len(kv[1]))[:10]:
        print('    %s.%s: %d, e.g. %s: %s | XML: %s' % (cls, prop, len(rows), rows[0][0], rows[0][1][:60], rows[0][2][:60]))
    # standard attributes: the settings changed in the designer against <StandardAttributes> of the same objects
    # (the XML lists every standard attribute of the class, applicable or not; their types it does not hold)
    XR = '{http://v8.1c.ru/8.3/xcf/readable}'

    def std_of(sa):
        """{name: settings}; None when the XML has no <StandardAttributes>: nothing was changed there"""
        if sa is None:
            return None
        out = {}
        for x in sa:
            st = {}
            for c in x:
                tag, v = c.tag.replace(XR, ''), c.text or ''
                if tag in ('Synonym', 'ToolTip'):
                    loc = {i.findtext(V8 + 'lang'): i.findtext(V8 + 'content') or '' for i in c}
                    loc = {k: t for k, t in loc.items() if t}
                    if loc:
                        st[tag] = loc
                elif (tag in ('Comment', 'Mask') and v) or (tag == 'FillChecking' and v not in ('', 'DontCheck')) \
                        or (tag == 'FillFromFillingValue' and v == 'true'):
                    st[tag] = v
            out[x.get('name')] = st
        return out

    xstd, sr, sbad = {}, collections.Counter(), collections.defaultdict(list)
    for s in standard_attributes(cfg):
        cls, name = s.obj.split('.', 1)
        xp = os.path.join(conf, cls, name + '.xml')
        if xp not in xstd:
            xstd[xp] = None
            if os.path.isfile(xp):
                obj = next(iter(ET.parse(xp).getroot()))
                pr, co = obj.find(MD + 'Properties'), obj.find(MD + 'ChildObjects')
                xstd[xp] = {'': std_of(pr.find(MD + 'StandardAttributes') if pr is not None else None)}
                for t in (co.findall(MD + 'TabularSection') if co is not None else []):
                    tp = t.find(MD + 'Properties')
                    xstd[xp][tp.findtext(MD + 'Name')] = std_of(tp.find(MD + 'StandardAttributes'))
                sts = pr.find(MD + 'StandardTabularSections') if pr is not None else None
                for t in (list(sts) if sts is not None else []):          # ExtDimensionTypes, BaseCalculationTypes …
                    xstd[xp][STD_TS_RU.get(t.get('name'), t.get('name'))] = std_of(t.find(XR + 'StandardAttributes'))
        if xstd[xp] is None:
            continue
        if s.ts not in xstd[xp]:
            sr['no tabular section in XML'] += 1; sbad[(cls, s.ts, 'tabular section')].append(name)
            continue
        x = xstd[xp][s.ts]
        want = {} if x is None else x.get(s.name)
        eol = lambda t: t.replace('\r', '')     # the XML dump writes line ends (even a stored CR CR LF) as one LF
        got = {k: ({l: eol(t) for l, t in v.items()} if isinstance(v, dict) else eol(v)) for k, v in s.settings.items()}
        if want is None:
            sr['not in XML'] += 1; sbad[(cls, s.name, 'missing')].append(name)
        elif want == got:
            sr['equal'] += 1
            sr['equal, with settings'] += bool(got)
        else:
            sr['differs'] += 1
            for k in sorted(set(want) | set(got)):
                if want.get(k) != got.get(k):
                    sbad[(cls, s.name, k)].append('%s: %s | XML: %s' % (name, str(got.get(k))[:70], str(want.get(k))[:70]))
    print('standard attribute settings vs XML:', dict(sr), '| kinds of differences:', len(sbad))
    for k, rows in sorted(sbad.items(), key=lambda kv: -len(kv[1]))[:10]:
        print('    %s.%s %s: %d, e.g. %s' % (k + (len(rows), rows[0])))


def main():
    p = argparse.ArgumentParser(description='Read a 1C configuration from the Config table (MS SQL) or a .cf file.')
    p.add_argument('--no-sync', action='store_true', help='SQL source: use the cache as is (nothing is written)')
    p.add_argument('--cache', help='cache root for SQL sources (default %%LOCALAPPDATA%%\\1c-config-direct or $CFGREAD_CACHE)')
    p.add_argument('source')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('info')
    s = sub.add_parser('objects'); s.add_argument('filter', nargs='?'); s.add_argument('--all', action='store_true')
    s = sub.add_parser('modules'); s.add_argument('filter', nargs='?'); s.add_argument('--no-text', action='store_true')
    s = sub.add_parser('module'); s.add_argument('name'); s.add_argument('--all', action='store_true')
    s.add_argument('-n', action='store_true', help='number lines'); s.add_argument('--lines', help='A-B, A-, -B')
    s = sub.add_parser('grep'); s.add_argument('regex'); s.add_argument('--re', action='store_true', help='regex (default: plain text)')
    s.add_argument('-i', '--ignore-case', action='store_true'); s.add_argument('--path'); s.add_argument('--ctx', type=int, default=0)
    s.add_argument('--files', action='store_true'); s.add_argument('--proc', action='store_true'); s.add_argument('--max', type=int, default=500)
    s = sub.add_parser('fields'); s.add_argument('filter', nargs='?')
    s.add_argument('--no-standard', action='store_true', help='own fields only, without standard attributes')
    s = sub.add_parser('props'); s.add_argument('filter', nargs='?'); s.add_argument('--prop'); s.add_argument('--all', action='store_true')
    s = sub.add_parser('usedby'); s.add_argument('name'); s.add_argument('--types', action='store_true')
    s = sub.add_parser('export'); s.add_argument('dir'); s.add_argument('--path'); s.add_argument('--no-fields', action='store_true')
    s = sub.add_parser('diff'); s.add_argument('other'); s.add_argument('--path'); s.add_argument('--show')
    s.add_argument('--ctx', type=int, default=2); s.add_argument('--fields', action='store_true'); s.add_argument('--props', action='store_true')
    s = sub.add_parser('check'); s.add_argument('conf')
    a = p.parse_args()
    t0 = time.time()
    cfg, desc, facts = open_source(a.source, a)
    globals()['cmd_' + a.cmd](cfg, desc, facts, a)
    note('%.1f s' % (time.time() - t0))


if __name__ == '__main__':
    main()
