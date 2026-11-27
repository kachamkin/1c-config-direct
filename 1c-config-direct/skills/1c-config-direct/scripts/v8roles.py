# Rights of roles. A role keeps them in <role uuid>.0:
#   {10,{N,<object>…},{K,{"<template name>","<template text>"}…},<set for new objects>,<set for attributes by
#    default>,<independent rights of child objects>,4294967295}          flags: 1 true, 0 or 4294967295 false
#   object    {<reference>,<rights>}
#   reference {1,<uuid>,0,0|1} — an object, a field (attribute, dimension, resource…), a form, a command, a nested
#             subsystem, an operation, an URL template or its method; the configuration itself goes by the uuid of
#             its description (the file "root" names);
#             {1,<uuid>,K,<step>×K,1}, step {<standard id>,03f171e8-… (standard attribute) | 28db313d-… (standard
#             tabular section)}: a standard attribute of the object or of its tabular section;
#             {1,<register>,2,{k,03f171e8-…},{k,91162600-… | b3b48b29-…},1}: ExtDimension<k+1> | ExtDimensionType<k+1>
#   rights    {0,<right uuid>,1|-1,…} (1 granted, -1 not), or with restrictions
#             {1,N,<right uuid>,1|-1…,K,{<right uuid>,{M,<condition>…}}…},
#             condition {1,"<text>",F,<field>×F}; field {{0},{<standard id>}}, {{0},{0,<field uuid>}}, a tabular section
#             {{0,<ts uuid>},{0}}, its attribute {{0,<ts uuid>},{0,<uuid>}} or line number {{0,<ts uuid>},{<id>}};
#             the first condition, without text and fields, is the default one (no restriction)
# A right uuid names the same right in every class: role_rights.json, with the rights of each kind of object.
# A right the stored list lacks (a role written by an older platform) the platform derives: the data history rights
# (but UpdateDataHistorySettings) are "set for new objects" and Read, the main window modes and AnalyticsSystemClient
# are granted, debugging and the configuration reading rights follow Administration; any other has the default.
# The XML dump writes a right when it differs from that default — "set for new objects" for an object, the
# configuration, a command, a subsystem; "set for attributes by default" for a field, a tabular section, a standard
# attribute — or has a condition; it never writes standard attributes of tabular sections.
import collections, json, os, re
from v8cfg import text, parse_brace, unq

STEP = {'03f171e8-326f-41c6-9fa5-932a0b12cddf': 'StandardAttribute', '28db313d-dbc2-4b83-8c4a-d2aeee708062': 'StandardTabularSection'}
GUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
FIELD_KINDS = {'Attribute', 'TabularSection', 'Dimension', 'Resource', 'StandardAttribute', 'StandardTabularSection',
               'AddressingAttribute', 'AccountingFlag', 'ExtDimensionAccountingFlag'}
HISTORY = ('ReadDataHistory', 'ReadDataHistoryOfMissingData', 'UpdateDataHistory', 'UpdateDataHistoryOfMissingData',
           'UpdateDataHistoryVersionComment', 'ViewDataHistory', 'EditDataHistoryVersionComment', 'SwitchToDataHistoryVersion')
WINDOW = ('MainWindowModeNormal', 'MainWindowModeWorkplace', 'MainWindowModeEmbeddedWorkplace', 'MainWindowModeFullscreenWorkplace',
          'MainWindowModeKiosk', 'AnalyticsSystemClient')
BY_ADMIN = ('MainConfigurationRead', 'MainConfigurationChange', 'ConfigurationExtensionsRead', 'UsersRead', 'Debug')
# standard fields of conditions that are no standard attributes
RLS_STD = {'Documents': {'-6': 'DataVersion'}, 'Catalogs': {'-9': 'DataVersion'}, 'ChartsOfAccounts': {'-3': 'DataVersion'}}

Role = collections.namedtuple('Role', 'flags objects templates')        # flags: (new objects, attributes, independent)
Object = collections.namedtuple('Object', 'ref rights restrictions')    # rights [(uuid, bool)]; restrictions {uuid: [(text, fields)]}
_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'role_rights.json'), encoding='utf-8'))
    return _TABLE


def right_name(u):
    return table()['rights'].get(u, u)


def _rights(node):
    if not isinstance(node, list) or not node:
        return [], {}
    if node[0] == '0':
        prs = node[1:]
        return [(prs[i], prs[i + 1] == '1') for i in range(0, len(prs) - 1, 2)], {}
    n = int(node[1])
    rights = [(node[2 + 2 * k], node[3 + 2 * k] == '1') for k in range(n)]
    i = 2 + 2 * n
    k = int(node[i]) if len(node) > i else 0
    restr = {}
    for r in node[i + 1:i + 1 + k]:
        conds = []
        for c in r[1][1:]:
            nf = int(c[2]) if len(c) > 2 else 0
            conds.append((unq(c[1]), c[3:3 + nf]))
        restr[r[0]] = conds
    return rights, restr


def read(cfg, it):
    """Role of a role object, or None"""
    if not cfg.src.has(it.uuid + '.0'):
        return None
    t = parse_brace(text(cfg.src.raw(it.uuid + '.0')))
    objects = []
    for ob in t[1][1:] if isinstance(t[1], list) else ():
        rights, restr = _rights(ob[1] if len(ob) > 1 else None)
        objects.append(Object(ob[0], rights, restr))
    templates = [(unq(x[0]), unq(x[1])) for x in t[2][1:] if isinstance(x, list) and len(x) > 1] if len(t) > 2 else []
    flags = tuple(v == '1' for v in t[3:6]) if len(t) > 5 else (False, True, False)
    return Role(flags, objects, templates)


# names as the XML dump writes them: Catalog.X, Catalog.X.TabularSection.T.Attribute.A, Subsystem.A.Subsystem.B …
EXTRA_SINGULAR = {'CommonForms': 'CommonForm', 'CommonCommands': 'CommonCommand', 'SessionParameters': 'SessionParameter',
                  'Subsystems': 'Subsystem', 'WebServices': 'WebService', 'HTTPServices': 'HTTPService', 'Interfaces': 'Interface',
                  'CommonAttributes': 'CommonAttribute', 'IntegrationServices': 'IntegrationService', 'CommonModules': 'CommonModule',
                  'CommonTemplates': 'CommonTemplate', 'ExternalDataSources': 'ExternalDataSource', 'Bots': 'Bot',
                  'FunctionalOptions': 'FunctionalOption', 'ScheduledJobs': 'ScheduledJob'}
COLL = {'Attributes': 'Attribute', 'TabularSections': 'TabularSection', 'Dimensions': 'Dimension', 'Resources': 'Resource',
        'AddressingAttributes': 'AddressingAttribute', 'AccountingFlags': 'AccountingFlag',
        'ExtDimensionAccountingFlags': 'ExtDimensionAccountingFlag', 'Forms': 'Form', 'Templates': 'Template', 'Commands': 'Command'}
# elements kept inside the description of an object (or, for subsystems, in files of their own): kind by depth
NESTED = {'HTTPServices': ('URLTemplate', 'Method'), 'WebServices': ('Operation', 'Parameter'), 'CalculationRegisters': ('Recalculation',),
          'Subsystems': ('Subsystem',) * 8, 'IntegrationServices': ('Channel',)}


def singular(cls):
    from v8meta import SINGULAR
    return SINGULAR.get(cls) or EXTRA_SINGULAR.get(cls) or cls[:-1]


def xml_name(path):
    """Catalogs.X.TabularSections.T.Attributes.A -> Catalog.X.TabularSection.T.Attribute.A"""
    parts = path.split('.')
    out = [singular(parts[0])] + parts[1:2]
    for i in range(2, len(parts) - 1, 2):
        out += [COLL.get(parts[i], parts[i]), parts[i + 1]]
    return '.'.join(out)


def kind(name):
    """kind of a role object by its name: Configuration, the class of an object (Catalog), or the kind of a nested
    one (Attribute, TabularSection, StandardAttribute, Command, Subsystem, Operation …)"""
    parts = name.split('.')
    return 'Configuration' if parts[0] == 'Configuration' else parts[0] if len(parts) == 2 else parts[-2]


def _collections(node, depth=0):
    """collections {<guid>,N,…} inside a node, not looking into them"""
    from v8meta import is_collection
    for x in node if isinstance(node, list) else ():
        if is_collection(x):
            yield x
        elif isinstance(x, list) and depth < 12:
            yield from _collections(x, depth + 1)


def _nested(cfg, cls, base, node, kinds, out, depth=0, seen=None):
    from v8meta import find_name_block
    seen = seen if seen is not None else set()
    if depth >= len(kinds):
        return
    for coll in _collections(node):
        for child in coll[2:2 + int(coll[1])]:
            if isinstance(child, str) and GUID.match(child):            # a subsystem keeps its children in files
                if child in seen or not cfg.src.has(child):
                    continue
                seen.add(child)
                sub = parse_brace(text(cfg.src.raw(child)))
                nb = find_name_block(sub)
                if nb:
                    name = '%s.%s.%s' % (base, kinds[depth], unq(nb[2]))
                    out.setdefault(nb[1][2], (name, cls))
                    _nested(cfg, cls, name, sub, kinds, out, depth + 1, seen)
            elif isinstance(child, list):
                nb = find_name_block(child)
                if nb:
                    name = '%s.%s.%s' % (base, kinds[depth], unq(nb[2]))
                    out.setdefault(nb[1][2], (name, cls))
                    _nested(cfg, cls, name, child, kinds, out, depth + 1, seen)


def names(cfg):
    """{uuid: (name as in the XML dump, class of the top object)} of everything a role can give rights to"""
    if getattr(cfg, '_role_names', None) is None:
        out = {cfg.cfg_file: ('Configuration.' + cfg.name, 'Configuration')}
        for u, it in cfg.items.items():
            if it.cls != 'Configuration':
                out[u] = (xml_name(it.path), it.path.split('.')[0])
        for u, p in cfg.comp_context().names.items():              # fields and tabular sections
            if u not in out and '.' in p:
                out[u] = (xml_name(p), p.split('.')[0])
        nested = {}
        for it, tree in cfg.trees():
            if it.cls in NESTED:
                _nested(cfg, it.cls, xml_name(it.path), tree, NESTED[it.cls], nested)
        for u, v in nested.items():
            out.setdefault(u, v)
        cfg._role_names = out
    return cfg._role_names


def object_name(cfg, ref):
    """name of a reference of a role object as the XML dump writes it, or None (an object that is gone)"""
    from v8std import STD_IDS, STD_TS, TS_LINE_ID, EXT_DIM, EXT_DIM_TYPE
    if not isinstance(ref, list) or len(ref) < 4:
        return None
    hit = names(cfg).get(ref[1])
    if hit is None:
        return None
    out, cls = hit
    depth = int(ref[2]) if ref[2].lstrip('-').isdigit() else 0
    steps = ref[3:3 + depth]
    if len(steps) == 2 and all(isinstance(x, list) and len(x) > 1 for x in steps) and steps[1][1] in (EXT_DIM, EXT_DIM_TYPE) \
            and steps[0][0].isdigit():
        return '%s.StandardAttribute.%s%d' % (out, 'ExtDimension' if steps[1][1] == EXT_DIM else 'ExtDimensionType', int(steps[0][0]) + 1)
    sts = None
    for s in steps:
        if not isinstance(s, list) or len(s) < 2:
            return None
        kind_ = STEP.get(s[1])
        if kind_ == 'StandardTabularSection':
            sts = STD_TS.get(cls, {}).get(s[0])
            out += '.StandardTabularSection.' + (sts[0] if sts else s[0])
        elif kind_ == 'StandardAttribute':
            if sts:
                nm = sts[2].get(s[0])
            elif '.TabularSection.' in out and s[0] == TS_LINE_ID.get(cls, '-10'):
                nm = 'LineNumber'
            else:
                nm = STD_IDS.get(cls, {}).get(s[0])
            if nm is None:
                return None                                    # a standard attribute this object does not have
            out += '.StandardAttribute.' + nm
        else:
            return None
    return out


def default(name, flags):
    """the value a right of this object has unless the role says otherwise"""
    return flags[1] if kind(name) in FIELD_KINDS else flags[0]


def effective(name, flags, ob):
    """{right: granted} of a role object in the platform order: the stored values and the rights the platform derives
    for a stored list that lacks them; rights neither stored nor derived have the default"""
    stored = collections.OrderedDict((right_name(u), v) for u, v in ob.rights)
    out = collections.OrderedDict()
    k = kind(name)
    known = list(table()['kinds'].get(k, ()))
    if k == 'Configuration':                     # rights no stored list of the samples had: derived only
        known += [n for n in WINDOW + BY_ADMIN if n not in known]
    for n in known:
        if n in stored:
            out[n] = stored[n]
        elif n in HISTORY:
            out[n] = flags[0] and stored.get('Read', flags[0])
        elif n in WINDOW:
            out[n] = True
        elif n in BY_ADMIN:
            out[n] = stored.get('Administration', flags[0])
    for n, v in stored.items():
        out.setdefault(n, v)
    return out


def _field(cfg, cls, f):
    """a field of a condition: {{0},…} of the object, {{0,<ts uuid>},…} of a tabular section, {{<id>},…} of a standard
    tabular section; then {0} the section itself, {0,<uuid>} a field, {<id>} a standard attribute"""
    from v8std import STD_IDS, STD_TS, TS_LINE_ID
    nm = cfg.comp_context().names
    first = f[0] if isinstance(f[0], list) and f[0] else ['0']
    last = f[1] if len(f) > 1 and isinstance(f[1], list) and f[1] else ['0']
    own = lambda u: nm.get(u, '?' + u[:8]).split('.')[-1]
    if first[0] != '0':                                        # a standard tabular section
        sts = STD_TS.get(cls, {}).get(first[0])
        ts = sts[0] if sts else '#' + first[0]
        if last == ['0']:
            return ts
        if len(last) > 1:
            return ts + '.' + own(last[1])
        return ts + '.' + ((sts[2].get(last[0]) if sts else None) or '#' + last[0])
    if len(first) > 1:                                         # a tabular section of the object
        ts = own(first[1])
        if last == ['0']:
            return ts
        if len(last) > 1:
            return ts + '.' + own(last[1])
        return ts + '.' + ('LineNumber' if last[0] == TS_LINE_ID.get(cls, '-10') else '#' + last[0])
    if len(last) > 1:
        return own(last[1])
    return STD_IDS.get(cls, {}).get(last[0]) or RLS_STD.get(cls, {}).get(last[0]) or '#' + last[0]


def conditions(cfg, ob):
    """{right: [(fields, condition text)]} of a role object, the default condition left out; fields sorted, as the
    XML dump writes them; line ends of the text as stored"""
    cls = names(cfg).get(ob.ref[1], ('', ''))[1] if isinstance(ob.ref, list) and len(ob.ref) > 1 else ''
    out = {}
    for u, conds in ob.restrictions.items():
        lst = []
        for text_, fields in conds:
            fl = sorted(_field(cfg, cls, f) for f in fields if isinstance(f, list) and f)
            if fl or text_:
                lst.append((fl, text_))
        if lst:
            out[right_name(u)] = lst
    return out


# rights the XML dump knows only from a format version on (Rights.xml version="2.22")
XML_SINCE = {n: (2, 22) for n in BY_ADMIN}


def written(name, flags, eff, conds, version=(9, 99)):
    """{right: granted} the XML dump of that format version writes for a role object"""
    if '.TabularSection.' in name and '.StandardAttribute.' in name:
        return {}
    d = default(name, flags)
    return {n: v for n, v in eff.items() if (v != d or n in conds) and XML_SINCE.get(n, (0, 0)) <= version}


def xml_role(path):
    """(flags, {object: {right: (granted, [(fields, condition)])}}, [(template, condition)], format version) of
    Ext/Rights.xml"""
    import xml.etree.ElementTree as ET
    NS = '{http://v8.1c.ru/8.2/roles}'
    r = ET.parse(path).getroot()
    flags = tuple(r.findtext(NS + k) == 'true' for k in ('setForNewObjects', 'setForAttributesByDefault', 'independentRightsOfChildObjects'))
    objs = collections.OrderedDict()
    for o in r.findall(NS + 'object'):
        rights = collections.OrderedDict()
        for rt in o.findall(NS + 'right'):
            restr = [(sorted(f.text or '' for f in rb.findall(NS + 'field')), rb.findtext(NS + 'condition') or '')
                     for rb in rt.findall(NS + 'restrictionByCondition')]
            rights[rt.findtext(NS + 'name')] = (rt.findtext(NS + 'value') == 'true', restr)
        objs[o.findtext(NS + 'name')] = rights
    templates = [(t.findtext(NS + 'name') or '', t.findtext(NS + 'condition') or '') for t in r.findall(NS + 'restrictionTemplate')]
    version = tuple(int(x) for x in (r.get('version') or '0.0').split('.')[:2] if x.isdigit())
    return flags, objs, templates, version
