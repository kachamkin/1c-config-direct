# Standard attributes (Ref, Code, Description, Owner, Parent, Date, Number, Period, Recorder, LineNumber, Account,
# ExtDimension1…, CalculationType ...) and standard tabular sections (ExtDimensionTypes of a chart of accounts,
# Leading/Displacing/BaseCalculationTypes of a chart of calculation types).
# Their types are not stored: the platform derives them from object properties, and which of them exist depends on
# the properties too (Parent only in a hierarchical catalog, Account only in a non-correspondent accounting register,
# BegOfBasePeriod only in a calculation register with a base period). The rules below were checked against what the
# platform itself reports over COM, on client configurations and on a synthetic one built to hold the rare values.
# Settings changed in the designer (synonym, tooltip, fill checking ...) are stored per attribute as a property bag
#     {-id},510405d3-…,{14,N,<property GUID>,<value>,…}
# in a list near the object header (or in the header of a tabular section); the ids per class and the property GUIDs
# were learned against XML dumps. The list of an object is absent when nothing was changed.
import collections
import re
from v8meta import unq, is_collection, find_name_block, KIND

StdAttr = collections.namedtuple('StdAttr', 'obj ts name ru types settings how')
STD_SA = '510405d3-2a0c-4fea-960a-7fee59b32f9b'
STD_LSTR = '87024738-fc2a-4436-ada1-df79d395c424'
STD_KEYS = {
    'cf4abea3-37b2-11d4-940f-008048da11f9': 'Synonym', '4690ff70-e3fa-4914-9127-6a9acc5fc949': 'ToolTip',
    'cf4abea4-37b2-11d4-940f-008048da11f9': 'Comment', '2723eb98-b4c1-498a-a6f3-70444757902f': 'FillChecking',
    'f49e4ced-4033-4e6c-8755-9fbaaccd6078': 'Mask', '2c8143d5-4248-4c43-8bfb-307c0be2e415': 'FillFromFillingValue',
}
STD_FILLCHECK = {'0': 'DontCheck', '1': 'ShowError'}
# id of a standard attribute in the stored list -> its name, per class
STD_IDS = {
    'Catalogs': {'-13': 'PredefinedDataName', '-10': 'Predefined', '-8': 'Ref', '-7': 'DeletionMark', '-6': 'IsFolder',
                 '-5': 'Owner', '-4': 'Parent', '-3': 'Description', '-2': 'Code'},
    'ChartsOfCharacteristicTypes': {'-14': 'PredefinedDataName', '-11': 'ValueType', '-9': 'Description', '-8': 'Code',
                                    '-7': 'IsFolder', '-6': 'Parent', '-5': 'Predefined', '-4': 'DeletionMark', '-2': 'Ref'},
    'Documents': {'-7': 'Posted', '-5': 'Ref', '-4': 'DeletionMark', '-3': 'Date', '-2': 'Number'},
    'Enums': {'-3': 'Order', '-2': 'Ref'},
    'ExchangePlans': {'-13': 'ThisNode', '-10': 'ReceivedNo', '-9': 'SentNo', '-6': 'Ref', '-4': 'DeletionMark',
                      '-3': 'Description', '-2': 'Code'},
    'BusinessProcesses': {'-9': 'Started', '-8': 'HeadTask', '-7': 'Completed', '-5': 'Ref', '-4': 'DeletionMark',
                          '-3': 'Date', '-2': 'Number'},
    'Tasks': {'-10': 'Executed', '-9': 'Description', '-8': 'RoutePoint', '-7': 'BusinessProcess', '-5': 'Ref',
              '-4': 'DeletionMark', '-3': 'Date', '-2': 'Number'},
    'DocumentJournals': {'-60003': 'Type', '-101': 'Ref', '-100': 'Date', '-7': 'Posted', '-4': 'DeletionMark', '-2': 'Number'},
    'InformationRegisters': {'-5': 'Active', '-4': 'LineNumber', '-3': 'Recorder', '-2': 'Period'},
    'AccumulationRegisters': {'-9': 'RecordType', '-5': 'Active', '-4': 'LineNumber', '-3': 'Recorder', '-2': 'Period'},
    'ChartsOfAccounts': {'-28': 'PredefinedDataName', '-17': 'Order', '-11': 'OffBalance', '-10': 'Type', '-8': 'Description',
                         '-7': 'Code', '-6': 'Parent', '-5': 'Predefined', '-4': 'DeletionMark', '-2': 'Ref'},
    # ExtDimension<k+1> and ExtDimensionType<k+1> have the ids <k>/EXT_DIM and <k>/EXT_DIM_TYPE
    'AccountingRegisters': {'-10': 'Account', '-9': 'RecordType', '-5': 'Active', '-4': 'LineNumber', '-3': 'Recorder', '-2': 'Period'},
    'ChartsOfCalculationTypes': {'-11': 'PredefinedDataName', '-8': 'Predefined', '-6': 'Ref', '-5': 'DeletionMark',
                                 '-4': 'ActionPeriodIsBasic', '-3': 'Description', '-2': 'Code'},
    'CalculationRegisters': {'-13': 'RegistrationPeriod', '-11': 'ReversingEntry', '-10': 'Active', '-9': 'EndOfBasePeriod',
                             '-8': 'BegOfBasePeriod', '-7': 'EndOfActionPeriod', '-6': 'BegOfActionPeriod', '-5': 'ActionPeriod',
                             '-4': 'CalculationType', '-3': 'LineNumber', '-2': 'Recorder'},
}
EXT_DIM, EXT_DIM_TYPE = '91162600-3161-4326-89a0-4a7cecd5092a', 'b3b48b29-d652-47ab-9d21-7e06768c31b5'
_CT = {'-102': 'Predefined', '-101': 'CalculationType', '-100': 'LineNumber'}
# standard tabular sections: id of the section in its block -> (name, Russian name, ids of its attributes)
STD_TS = {
    'ChartsOfAccounts': {'-12': ('ExtDimensionTypes', 'ВидыСубконто',
                                 {'-15': 'TurnoversOnly', '-14': 'Predefined', '-13': 'ExtDimensionType', '-12': 'LineNumber'})},
    'ChartsOfCalculationTypes': {'-30': ('LeadingCalculationTypes', 'ВедущиеВидыРасчета', _CT),
                                 '-20': ('DisplacingCalculationTypes', 'ВытесняющиеВидыРасчета', _CT),
                                 '-10': ('BaseCalculationTypes', 'БазовыеВидыРасчета', _CT)},
}
STD_TS_RU = {en: ru for sections in STD_TS.values() for en, ru, ids in sections.values()}
# id of LineNumber in the list of a tabular section (elsewhere '-10')
TS_LINE_ID = {'DataProcessors': '-3', 'Reports': '-3', 'ChartsOfCalculationTypes': '-100'}
# collection of tabular sections per class ('' = not seen yet: any collection that is not a field collection)
TS_COLL = {'Catalogs': '932159f9-95b2-4e76-a8dd-8849fe5c5ded', 'Documents': '21c53e09-8950-4b5e-a6a0-1054f1bbc274',
           'ChartsOfCharacteristicTypes': '54e36536-7863-42fd-bea3-c5edd3122fdc', 'ExchangePlans': '52293f4b-f98c-43ea-a80f-41047ae7ab58',
           'BusinessProcesses': 'a3fe6537-d787-40f7-8a06-419d2f0c1cfd', 'ChartsOfCalculationTypes': '054aa8cf-faa6-4634-aef4-1087ca0d88fc',
           'DataProcessors': '2bcef0d1-0981-11d6-b9b8-0050bae0a95d', 'Reports': 'b077d780-29e2-11d6-a3c7-0050bae0a776',
           'Tasks': '', 'ChartsOfAccounts': ''}
STD_RU = {
    'Ref': 'Ссылка', 'DeletionMark': 'ПометкаУдаления', 'Predefined': 'Предопределенный', 'PredefinedDataName': 'ИмяПредопределенныхДанных',
    'Code': 'Код', 'Description': 'Наименование', 'Owner': 'Владелец', 'Parent': 'Родитель', 'IsFolder': 'ЭтоГруппа',
    'Date': 'Дата', 'Number': 'Номер', 'Posted': 'Проведен', 'Period': 'Период', 'Recorder': 'Регистратор',
    'LineNumber': 'НомерСтроки', 'Active': 'Активность', 'RecordType': 'ВидДвижения', 'ValueType': 'ТипЗначения',
    'ThisNode': 'ЭтотУзел', 'SentNo': 'НомерОтправленного', 'ReceivedNo': 'НомерПринятого', 'Started': 'Стартован',
    'Completed': 'Завершен', 'HeadTask': 'ВедущаяЗадача', 'Executed': 'Выполнена', 'BusinessProcess': 'БизнесПроцесс',
    'RoutePoint': 'ТочкаМаршрута', 'Order': 'Порядок', 'Type': 'Тип', 'OffBalance': 'Забалансовый', 'Account': 'Счет',
    'TurnoversOnly': 'ТолькоОбороты', 'ExtDimensionType': 'ВидСубконто', 'ActionPeriodIsBasic': 'ПериодДействияБазовый',
    'CalculationType': 'ВидРасчета', 'RegistrationPeriod': 'ПериодРегистрации', 'ReversingEntry': 'Сторно',
    'BegOfBasePeriod': 'БазовыйПериодНачало', 'EndOfBasePeriod': 'БазовыйПериодКонец', 'ActionPeriod': 'ПериодДействия',
    'BegOfActionPeriod': 'ПериодДействияНачало', 'EndOfActionPeriod': 'ПериодДействияКонец',
}
RU_IN = {('ChartsOfAccounts', 'Type'): 'Вид', ('ExtDimensionTypes', 'Predefined'): 'Предопределенное'}
REF_OF = {'Catalogs': 'CatalogRef', 'Documents': 'DocumentRef', 'Enums': 'EnumRef', 'ExchangePlans': 'ExchangePlanRef',
          'ChartsOfCharacteristicTypes': 'ChartOfCharacteristicTypesRef', 'ChartsOfAccounts': 'ChartOfAccountsRef',
          'ChartsOfCalculationTypes': 'ChartOfCalculationTypesRef', 'BusinessProcesses': 'BusinessProcessRef', 'Tasks': 'TaskRef'}
# properties an attribute depends on: when one of them was read from an assumed place, so is the attribute
DEPS = {'Code': ('CodeLength', 'CodeType', 'CodeAllowedLength'), 'Description': ('DescriptionLength',),
        'Number': ('NumberType', 'NumberLength', 'NumberAllowedLength'), 'Order': ('OrderLength',),
        'Parent': ('Hierarchical',), 'IsFolder': ('Hierarchical', 'HierarchyType'), 'Owner': ('Owners',),
        'Period': ('InformationRegisterPeriodicity',), 'Recorder': ('WriteMode',), 'LineNumber': ('WriteMode',),
        'Active': ('WriteMode',), 'RecordType': ('RegisterType', 'Correspondence'), 'Account': ('Correspondence',),
        'ActionPeriodIsBasic': ('ActionPeriodUse',), 'BegOfBasePeriod': ('BasePeriod',), 'EndOfBasePeriod': ('BasePeriod',),
        'ActionPeriod': ('ActionPeriod',), 'BegOfActionPeriod': ('ActionPeriod',), 'EndOfActionPeriod': ('ActionPeriod',)}
BOOL, DATETIME = [('Boolean', None)], [('Date', 'DateTime')]
LINE5, LINE9 = [('Number', ('5', '0', 'Nonnegative'))], [('Number', ('9', '0', 'Nonnegative'))]


def _ru(scope, name):
    if (scope, name) in RU_IN:
        return RU_IN[(scope, name)]
    m = re.fullmatch(r'(ExtDimension|ExtDimensionType)(\d+)', name)
    if m:
        return ('Субконто' if m.group(1) == 'ExtDimension' else 'ВидСубконто') + m.group(2)
    return STD_RU.get(name, name)


def _refs(paths):
    out = []
    for p in paths or []:
        cls, _, name = (p or '').partition('.')
        if cls in REF_OF and name and '.' not in name:
            out.append(('Type', '%s.%s' % (REF_OF[cls], name)))
    return sorted(out)


def _string(length, allowed='Variable'):
    return [('String', (length, 'Fixed' if allowed == 'Fixed' else 'Variable'))]


def _code(kind, length, allowed):
    return [('Number', (length, '0', 'Nonnegative'))] if kind == 'Number' else _string(length, allowed)


def _sa_list(node, depth):
    """first stored standard-attribute list within `depth` levels, not entering child collections"""
    if not isinstance(node, list):
        return None
    if len(node) > 4 and isinstance(node[1], str) and node[1].isdigit() and STD_SA in node:
        return node
    if depth > 0:
        for x in node:
            if isinstance(x, list) and not is_collection(x):
                r = _sa_list(x, depth - 1)
                if r is not None:
                    return r
    return None


def _bag_value(prop, v):
    if not isinstance(v, list) or not v:
        return None
    if v[0] == '"#"' and len(v) > 2 and v[1] == STD_LSTR:
        s = [unq(y) for y in v[2][1:] if isinstance(y, str)] if isinstance(v[2], list) else []
        return {lang: t for lang, t in zip(s[::2], s[1::2]) if t} or None
    if v[0] == '"#"' and len(v) > 2 and isinstance(v[2], str) and prop == 'FillChecking':
        return STD_FILLCHECK.get(v[2], '?' + v[2])
    if v[0] == '"S"' and len(v) > 1:
        return unq(v[1]) or None
    if v[0] == '"B"' and len(v) > 1:
        return 'true' if v[1] == '1' else 'false'
    return None


def _bags_of(lst):
    """{id: {setting: value}} of a stored list; an id is '-13' or, for ExtDimension<k+1>, '<k>/<GUID of the kind>'.
    Only settings that differ from the defaults are kept."""
    out = {}
    for i, x in enumerate(lst or []):
        if x != STD_SA or i == 0 or i + 1 >= len(lst) or not isinstance(lst[i - 1], list) or not lst[i - 1]:
            continue
        b, vals = lst[i + 1], {}
        if isinstance(b, list) and len(b) > 1 and isinstance(b[1], str) and b[1].isdigit():
            for j in range(2, len(b) - 1, 2):
                prop = STD_KEYS.get(b[j])
                val = _bag_value(prop, b[j + 1]) if prop else None
                if val is not None and not (prop == 'FillChecking' and val == 'DontCheck') \
                        and not (prop == 'FillFromFillingValue' and val == 'false'):
                    vals[prop] = val
        out['/'.join(y for y in lst[i - 1] if isinstance(y, str))] = vals
    return out


def bags(node, depth):
    return _bags_of(_sa_list(node, depth))


def _std_ts_lists(tree):
    """{id of a standard tabular section: its stored list}: blocks {0,N,<id>,{…},<id>,{…}} in the object header"""
    out = {}

    def walk(node, depth):
        if not isinstance(node, list) or depth > 3:
            return
        n = node[1] if len(node) > 1 and isinstance(node[1], str) and node[1].isdigit() else None
        if node and node[0] == '0' and n and int(n) and len(node) == 2 + 2 * int(n):
            pairs = [(node[2 + 2 * j], node[3 + 2 * j]) for j in range(int(n))]
            if all(isinstance(k, str) and k.startswith('-') and isinstance(v, list) for k, v in pairs):
                for k, v in pairs:
                    lst = _sa_list(v, 2)
                    if lst is not None:
                        out[k] = lst
                if out:
                    return
        for x in node:
            if isinstance(x, list) and not is_collection(x):
                walk(x, depth + 1)
    walk(tree[1] if len(tree) > 1 else None, 0)
    return out


def tabular_sections(cls, tree):
    """yield (name, node) of every tabular section, with or without attributes: a member of the class's collection of
    tabular sections (URL templates of HTTP services and operations of web services look the same, so the class decides)"""
    want = TS_COLL.get(cls)
    if want is None:
        return
    for coll in tree:
        if is_collection(coll) and (coll[0] == want or (want == '' and coll[0] not in KIND)):
            for x in coll[2:]:
                if isinstance(x, list) and x and isinstance(x[0], list) and any(is_collection(y) for y in x[1:]):
                    nb = find_name_block(x[0])
                    if nb:
                        yield unq(nb[2]), x


def _journal_number(docs):
    """the number of a journal: a string as long as the longest string number of its documents (fixed when all of them
    are fixed) and/or a number as long as the longest numeric one"""
    strs = [d for d in docs if (d.get('NumberType') or 'String') == 'String']
    nums = [d for d in docs if d.get('NumberType') == 'Number']
    length = lambda ds: str(max([int(d['NumberLength']) for d in ds if (d.get('NumberLength') or '').isdigit()] or [0]))
    out = [('Number', (length(nums), '0', 'Nonnegative'))] if nums else []
    if strs or not nums:
        out += _string(length(strs), 'Fixed' if strs and all(d.get('NumberAllowedLength') == 'Fixed' for d in strs) else 'Variable')
    return out


def standard_attributes(cfg, objects=None):
    """yield StdAttr: the classes above with their standard tabular sections, and LineNumber of every tabular section"""
    trees = cfg.trees()
    props, assumed_props = {}, {}
    for it, tree in trees:
        ps = cfg.properties(it, tree)
        props[it.uuid] = {p: v for p, v, how in ps}
        assumed_props[it.uuid] = {p for p, v, how in ps if how == 'assumed'}
    path_props = {it.path: props[it.uuid] for it, tree in trees}
    value_type = {f.obj: f.types for f in cfg.fields() if f.kind == 'Type' and f.obj.startswith('ChartsOfCharacteristicTypes.')}
    calc_charts = sorted(('Type', 'ChartOfCalculationTypesRef.' + it.name) for it, tree in trees if it.cls == 'ChartsOfCalculationTypes')
    all_tasks = sorted(('Type', 'TaskRef.' + it.name) for it, tree in trees if it.cls == 'Tasks')
    recorders, bp_of_task = collections.defaultdict(list), collections.defaultdict(list)
    for it, tree in trees:
        pr = props[it.uuid]
        if it.cls == 'Documents':
            for r in pr.get('RegisterRecords') or []:
                recorders[r].append(it.path)
        elif it.cls == 'BusinessProcesses' and pr.get('Task'):
            bp_of_task[pr['Task']].append(it.path)
    for it, tree in trees:
        if objects is not None and it.path not in objects:
            continue
        cls, g = it.cls, props[it.uuid].get
        nz = lambda p: g(p) not in (None, '0')
        ref = [('Type', '%s.%s' % (REF_OF[cls], it.name))] if cls in REF_OF else []
        rows, std_ts, assumed = [], [], set()
        if cfg.adopted(tree):
            pass                        # borrowed by an extension: its properties live in the configuration only
        elif cls in ('Catalogs', 'ChartsOfCharacteristicTypes'):
            hier = g('Hierarchical') == 'true'
            folders = hier and (cls == 'ChartsOfCharacteristicTypes' or g('HierarchyType') != 'HierarchyOfItems')
            rows = [('PredefinedDataName', _string('256')), ('Predefined', BOOL), ('Ref', ref), ('DeletionMark', BOOL)]
            if folders:
                rows.append(('IsFolder', BOOL))
            if cls == 'Catalogs' and g('Owners'):
                rows.append(('Owner', _refs(g('Owners'))))
            if hier:
                rows.append(('Parent', ref))
            if nz('DescriptionLength'):
                rows.append(('Description', _string(g('DescriptionLength'))))
            if nz('CodeLength'):
                rows.append(('Code', _code(g('CodeType') or 'String', g('CodeLength'), g('CodeAllowedLength'))))
            if cls == 'ChartsOfCharacteristicTypes':
                rows.append(('ValueType', [('Type', 'TypeDescription')]))
        elif cls in ('Documents', 'BusinessProcesses', 'Tasks'):
            rows = [('Ref', ref), ('DeletionMark', BOOL), ('Date', DATETIME)]
            if nz('NumberLength'):
                if not g('NumberType'):
                    assumed.add('Number')
                rows.append(('Number', _code(g('NumberType') or 'String', g('NumberLength'), g('NumberAllowedLength'))))
            if cls == 'Documents':
                rows.append(('Posted', BOOL))
            elif cls == 'BusinessProcesses':                 # the head task may be a task of any kind
                rows += [('Started', BOOL), ('Completed', BOOL), ('HeadTask', all_tasks)]
            else:
                if nz('DescriptionLength'):
                    rows.append(('Description', _string(g('DescriptionLength'))))
                rows.append(('Executed', BOOL))
                bps = bp_of_task.get(it.path, [])
                if bps:                                      # only a task some business process uses
                    rows += [('BusinessProcess', _refs(bps)),
                             ('RoutePoint', sorted(('Type', 'BusinessProcessRoutePointRef.' + p.split('.', 1)[1]) for p in bps))]
        elif cls == 'Enums':
            rows = [('Ref', ref), ('Order', [('Number', ('0', '0', 'Any'))])]
        elif cls == 'ExchangePlans':
            rows = [('Ref', ref), ('DeletionMark', BOOL)]
            if nz('CodeLength'):
                rows.append(('Code', _string(g('CodeLength'), g('CodeAllowedLength'))))
            if nz('DescriptionLength'):
                rows.append(('Description', _string(g('DescriptionLength'))))
            rows += [('ThisNode', BOOL), ('SentNo', [('Number', ('10', '0', 'Nonnegative'))]),
                     ('ReceivedNo', [('Number', ('10', '0', 'Nonnegative'))])]
        elif cls == 'DocumentJournals':
            rows = [('Type', [('Type', 'Type')]), ('Ref', _refs(g('RegisteredDocuments'))), ('Date', DATETIME), ('Posted', BOOL),
                    ('DeletionMark', BOOL), ('Number', _journal_number([path_props.get(p, {}) for p in g('RegisteredDocuments') or []]))]
        elif cls in ('InformationRegisters', 'AccumulationRegisters'):
            per = g('InformationRegisterPeriodicity') if cls == 'InformationRegisters' else 'Second'
            sub = cls == 'AccumulationRegisters' or g('WriteMode') == 'RecorderSubordinate'
            if per and per != 'Nonperiodical':
                rows.append(('Period', [('Date', 'DateTime' if per in ('Second', 'RecorderPosition') else 'Date')]))
            if sub:
                rows += [('Recorder', _refs(recorders.get(it.path, []))), ('LineNumber', LINE9), ('Active', BOOL)]
            if cls == 'AccumulationRegisters' and g('RegisterType') == 'Balance':
                rows.append(('RecordType', [('Type', 'AccumulationMovementType')]))
        elif cls == 'ChartsOfAccounts':
            rows = [('PredefinedDataName', _string('256'))]
            if nz('OrderLength'):
                rows.append(('Order', _string(g('OrderLength'))))
            rows += [('OffBalance', BOOL), ('Type', [('Type', 'AccountType')])]
            if nz('DescriptionLength'):
                rows.append(('Description', _string(g('DescriptionLength'))))
            if nz('CodeLength'):
                rows.append(('Code', _string(g('CodeLength'))))
            rows += [('Parent', ref), ('Predefined', BOOL), ('DeletionMark', BOOL), ('Ref', ref)]
            std_ts = [('ExtDimensionTypes', [('TurnoversOnly', BOOL), ('Predefined', BOOL),
                                             ('ExtDimensionType', _refs([g('ExtDimensionTypes')])), ('LineNumber', LINE5)])]
        elif cls == 'AccountingRegisters':
            chart = path_props.get(g('ChartOfAccounts') or '', {})
            cct = chart.get('ExtDimensionTypes') or ''
            count = int(chart.get('MaxExtDimensionCount') or 0) if cct else 0
            if g('Correspondence') == 'false':              # a correspondent register has neither Account nor RecordType
                rows = [('Account', _refs([g('ChartOfAccounts')])), ('RecordType', [('Type', 'AccountingMovementType')])]
            rows += [('Active', BOOL), ('LineNumber', LINE9), ('Recorder', _refs(recorders.get(it.path, []))), ('Period', DATETIME)]
            for k in range(1, count + 1):
                rows += [('ExtDimension%d' % k, value_type.get(cct, [])), ('ExtDimensionType%d' % k, _refs([cct]))]
        elif cls == 'ChartsOfCalculationTypes':
            action = g('ActionPeriodUse') == 'true'
            rows = [('PredefinedDataName', _string('256')), ('Predefined', BOOL), ('Ref', ref), ('DeletionMark', BOOL)]
            if action:
                rows.append(('ActionPeriodIsBasic', BOOL))
            if nz('DescriptionLength'):
                rows.append(('Description', _string(g('DescriptionLength'))))
            if nz('CodeLength'):
                rows.append(('Code', _code(g('CodeType') or 'String', g('CodeLength'), g('CodeAllowedLength'))))
            ct = lambda types: [('Predefined', BOOL), ('CalculationType', types), ('LineNumber', LINE5)]
            std_ts = [('LeadingCalculationTypes', ct(calc_charts))]
            if action:
                std_ts.append(('DisplacingCalculationTypes', ct(ref)))
            if g('DependenceOnCalculationTypes') not in (None, 'DontUse'):
                std_ts.append(('BaseCalculationTypes', ct(_refs(g('BaseCalculationTypes')))))
        elif cls == 'CalculationRegisters':
            rows = [('RegistrationPeriod', DATETIME), ('ReversingEntry', BOOL), ('Active', BOOL)]
            if g('BasePeriod') == 'true':
                rows += [('EndOfBasePeriod', DATETIME), ('BegOfBasePeriod', DATETIME)]
            if g('ActionPeriod') == 'true':
                rows += [('EndOfActionPeriod', DATETIME), ('BegOfActionPeriod', DATETIME), ('ActionPeriod', DATETIME)]
            rows += [('CalculationType', _refs([g('ChartOfCalculationTypes')])), ('LineNumber', LINE9),
                     ('Recorder', _refs(recorders.get(it.path, [])))]
        if rows:
            ids = {v: k for k, v in STD_IDS.get(cls, {}).items()}
            own = bags(tree, 3)
            for name, types in rows:
                m = re.fullmatch(r'(ExtDimension|ExtDimensionType)(\d+)', name)
                key = '%d/%s' % (int(m.group(2)) - 1, EXT_DIM if m.group(1) == 'ExtDimension' else EXT_DIM_TYPE) if m else ids.get(name)
                guess = name in assumed or any(p in assumed_props[it.uuid] for p in DEPS.get(name, ()))
                yield StdAttr(it.path, '', name, _ru(cls, name), types, own.get(key, {}), 'assumed' if guess else '')
        if std_ts:
            lists = _std_ts_lists(tree)
            for en, attrs in std_ts:
                tid, (_, ru_ts, attr_ids) = next((k, v) for k, v in STD_TS[cls].items() if v[0] == en)
                stored, rid = _bags_of(lists.get(tid)), {v: k for k, v in attr_ids.items()}
                for name, types in attrs:
                    yield StdAttr(it.path, ru_ts, name, _ru(en, name), types, stored.get(rid.get(name), {}), '')
        line_id = TS_LINE_ID.get(cls, '-10')
        for ts, node in tabular_sections(cls, tree):
            yield StdAttr(it.path, ts, 'LineNumber', 'НомерСтроки', LINE5, bags(node[0], 5).get(line_id, {}), '')
