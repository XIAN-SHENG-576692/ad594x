#!/usr/bin/env python3
"""Import factual register declarations and indexed PDF register tables.

Inputs are temporary permitted-source downloads, never bundled vendor files.
The checked-in JSON is the reviewed, offline rendering input; this importer is
an acquisition aid, not a replacement for reviewing ambiguities in the tables.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

HEX = lambda n: f'0x{n:08X}'


def compact(text):
    text = text.replace('\u0002','')
    text = re.sub(r'(?<=[/×*])\s*2(30|20|18|17|15|10)\b',lambda m:'2^'+m.group(1),text)
    text = re.sub(r'Data Sheet AD5940/AD5941.*', '', text)
    text = re.sub(r'\s+', ' ', text).strip(' .')
    for old,new in [('This bit is the control bit for ',''),('This bit determines ','Selects '),('This bit selects ','Selects '),('These bits select ','Selects '),('This bit enables ','Enables '),('This bit disables ','Disables '),('Set this bit to 1 to ','Use 1 to '),('Clear this bit to 0 to ','Use 0 to '),('Set to 1 to ','1: '),('Clear to 0 to ','0: '),('This value is a signed number represented in twos complement format','Signed two’s-complement value'),('This value is an unsigned number','Unsigned value')]:
        text=text.replace(old,new)
    text = re.sub(r'^(?:AFE|AGPIO|AFECON|ALLON|INTC|WUPTMR|SPII2CS) ', '', text)
    text = text.replace('Configuration', 'configuration').replace('Register', 'register')
    return text + '.' if text else 'Meaning not specified by the permitted sources.'


def reference(source, location):
    return {'source': source, 'location': location}


def load_driver(path):
    definitions = {}
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        m = re.match(r'#define\s+((?:REG|BITP|BITM|ENUM)_\w+)\s+(0x[\da-fA-F]+|\d+)\s*(?:/\*\s*(.*?)\s*\*/)?', line)
        if m:
            name, value, desc = m.groups()
            if name in definitions and definitions[name][0] != int(value, 0):
                raise ValueError(f'driver redefines {name}')
            definitions[name] = (int(value, 0), desc or '', line_no)
    regs = {}
    for key, (addr, desc, line) in definitions.items():
        if not key.startswith('REG_') or key.endswith('_RESET'):
            continue
        full = key[4:]
        block, name = full.split('_', 1)
        reset = definitions.get(key + '_RESET', (None, '', line))[0]
        regs[full] = {'name': name, 'address': HEX(addr), 'reset': HEX(reset) if reset is not None else None,
                      'storage_width': 32 if 0x1000 <= addr <= 0x3014 else 16,
                      'access': '?', 'description': compact(desc),
                      'source_refs': [reference('driver', f'ad5940.h:{line}'),reference('driver',f'ad5940.h:{definitions[key+"_RESET"][2]} reset declaration')],
                      'evidence_status': 'single-source', 'fields': [], 'notes': []}
    for full, reg in regs.items():
        prefix = 'BITM_' + full + '_'
        for key, (mask, desc, line) in definitions.items():
            if not key.startswith(prefix):
                continue
            name = key[len(prefix):]
            if name in ('RESRVED','RESERVED'):
                reg.setdefault('legacy_reserved_definitions',[]).append({'name':name,'mask':HEX(mask),'source_refs':[reference('driver',f'ad5940.h:{line}')]})
                continue
            pk = 'BITP_' + full + '_' + name
            pos = definitions.get(pk, ((mask & -mask).bit_length() - 1, '', line))[0]
            width = mask.bit_count()
            if mask != ((1 << width) - 1) << pos:
                raise ValueError(f'non-contiguous {key}')
            reset = int(reg['reset'], 0) if reg['reset'] is not None else None
            reg['fields'].append({'name': name, 'position': pos, 'width': width, 'mask': HEX(mask),
                'reset': HEX((reset & mask) >> pos) if reset is not None else None,
                'access': '?', 'description': compact(desc), 'enumerations': [],
                'source_refs': [reference('driver', f'ad5940.h:{line} mask'),reference('driver',f'ad5940.h:{definitions[pk][2]} position')],
                'evidence_status': 'single-source', 'notes': []})
        ep = 'ENUM_' + full + '_'
        for key, (value, desc, line) in definitions.items():
            if not key.startswith(ep):
                continue
            fieldname = desc.split(':', 1)[0].strip()
            fields = [f for f in reg['fields'] if f['name'] == fieldname]
            if not fields:
                raise ValueError(f'unmatched enum {key}: {fieldname}')
            field = fields[0]
            if value & ~int(field['mask'], 0):
                raise ValueError(f'enum outside mask {key}')
            enum_name = key[len(ep):]
            enum_name = {'12BIT':'BITS12','11':'CAPA_LPTIA','1':'CAPA_OR_RAMP_HPTIA'}.get(enum_name,enum_name)
            if enum_name[0].isdigit():
                enum_name = 'VALUE_' + enum_name
            field['enumerations'].append({'name': enum_name, 'driver_name':key[len(ep):], 'value': HEX(value >> field['position']),
                'description': compact(desc.split(':', 1)[-1]),
                'source_refs': [reference('driver', f'ad5940.h:{line}')]})
    return regs, definitions


def load_pdf(paths):
    lines = {}
    for path in paths:
        for s in path.read_text().splitlines():
            m = re.match(r'L(\d+)@P(\d+)(?:-\d+)?: (.*)', s)
            if m:
                n, page, text = m.groups()
                lines[int(n)] = (int(page) + 1, text)
    return lines


def pdf_records(lines, driver_regs):
    records = {}
    current = None
    field = None
    in_table = False
    shared_tables = []
    for number, (page, text) in sorted(lines.items()):
        m = re.match(r'Address (0x[\dA-Fa-f]+), Reset: (0x[\dA-Fa-f]+), Name: (\w+)', text)
        if m:
            addr, reset, name = m.groups()
            name = name.removesuffix('Data')
            current = records.setdefault(name, {'address': int(addr, 0), 'resets': [], 'fields': [], 'page': page})
            current['resets'].append((int(reset, 0), page, 'register detail'))
            in_table = False
            field = None
            continue
        m = re.match(r'(0x[\da-fA-F]+) (\w+) (.*?) (0x[\da-fA-F]+) (R/W1C|R/W|R|W)\s*$', text)
        if m:
            addr, name, desc, reset, access = m.groups()
            rec = records.setdefault(name, {'address': int(addr, 0), 'resets': [], 'fields': [], 'page': page})
            rec['resets'].append((int(reset, 0), page, 'summary'))
            rec['access'] = access
            continue
        m = re.search(r'Bit Descriptions for (\w+)(?: and (\w+))?(?: Registers?)?', text, re.I)
        if m:
            name = m.group(1).removesuffix('Data')
            if m.group(2):
                shared_tables.append((name,m.group(2)))
            if 'x' in name:
                expanded = [name.replace('x',str(i)) for i in range(4)]
                for other in expanded[1:]:
                    shared_tables.append((expanded[0],other))
                name = expanded[0]
            current = records.get(name)
            in_table = current is not None
            field = None
            continue
        if not current or not in_table:
            continue
        if re.search(r'Registers?[—–]',text):
            in_table=False
            field=None
            continue
        section_starts=[25,28,30,36,43,50,54,64,71,72,74,87,89,99,104,107,112,118,122,127,129,132,137]
        section=lambda p:sum(p>=start for start in section_starts)
        if section(page)!=section(current['page']):
            in_table=False
            field=None
            continue
        # Only uppercase field labels (plus the identification exceptions) are
        # valid starters; this excludes enumeration rows such as '0 Enables...'.
        m = re.match(r'(\[\d+:\d+\]|\d+) (Reserved|Part ID|Revision|[A-Z][A-Za-z0-9_]*(?:\[[^]]+\])?)(?:\s+|$)(.*)', text)
        if m:
            bits, name, body = m.groups()
            name = re.sub(r'\[[^]]+\]$','',name)
            driver_match = [r for r in driver_regs.values() if int(r['address'], 0) == current['address']]
            known_names = {f['name'] for r in driver_match for f in r['fields']}
            mixed_names={'Count','Data','Key','Mean','Rate','Set','Sync','Timeout','Value','Variance','Part ID','Revision','Reserved'}
            if any(c.islower() for c in name) and name not in mixed_names and name.upper() not in known_names:
                if field:
                    field['body'] += ' ' + text
                    field['lines'].append(text)
                continue
            if name.upper() in known_names:
                name = name.upper()
            name = {'Part ID':'PARTID','Revision':'REVISION'}.get(name,name)
            if name.upper() == 'RESERVED':
                name = 'Reserved'
            lookahead = body
            for offset in range(1, 8):
                next_text = lines.get(number+offset, (0,''))[1]
                if re.match(r'(?:\[\d+:\d+\]|\d+) ', next_text):
                    break
                lookahead += ' ' + next_text
            if name not in known_names and name != 'Reserved' and not (re.fullmatch(r'SW\d+',name) and 'switch control' in body) and not bits.startswith('[') and not re.search(r'0x[0-9a-fA-F]+ (?:R/W|R|W)\b', lookahead):
                if field:
                    field['body'] += ' ' + text
                    field['lines'].append(text)
                continue
            if name not in ('Reserved', 'Part ID', 'Revision') and len(name) == 1:
                continue
            nums = [int(x) for x in re.findall(r'\d+', bits)]
            hi, lo = (nums[0], nums[-1])
            if hi > 31 or lo > hi:
                continue
            field = {'name': {'Part ID': 'PARTID', 'Revision': 'REVISION'}.get(name, name.upper()),
                'position': lo, 'width': hi-lo+1, 'body': body, 'page': page, 'enums': [], 'lines': [body]}
            current['fields'].append(field)
        elif field:
            if text.startswith(('Table ', 'Bits Bit Name', 'analog.com ', 'Data Sheet', 'Address ')):
                continue
            # Keep text only until reset/access is seen; enumeration rows are
            # separately interpreted while preserving numeric setting facts.
            field['body'] += ' ' + text
            field['lines'].append(text)
    for rec in records.values():
        for field in rec['fields']:
            m = re.search(r'(0x[\da-fA-F]+) (R/W1C|R/W|R|W)(?:\b|Data)', field['body'])
            if m:
                field['reset'], field['access'] = int(m.group(1), 0), m.group(2)
            else:
                rm = re.search(r'0x[0-9a-fA-F]+',field['body'])
                am = re.search(r'\b(R/W1C|R/W|R|W)\b',field['body'])
                field['reset'], field['access'] = (int(rm.group(),0) if rm else None), (am.group() if am else '?')
    for first, second in set(shared_tables):
        if first in records and second in records:
            records[second]['fields'] = records[first]['fields']
    return records


def build(driver, pdfs):
    regs, definitions = load_driver(driver)
    pdf_lines = load_pdf(pdfs)
    pdf = pdf_records(pdf_lines, regs)
    conflicts = []
    pdf_only = []
    def conflict(reg, attribute, candidates, reason, chosen=None):
        item = {'register': reg['name'], 'attribute': attribute, 'candidates': candidates,
                'resolution': 'unresolved' if chosen is None else 'resolved', 'chosen': chosen, 'reason': reason, 'source_refs': list(reg['source_refs'])}
        conflicts.append(item)
        reg['notes'].append(f'{attribute}: {reason}')
        reg['evidence_status'] = item['resolution']
    # Preserve driver directory blocks; datasheet-only registers are collected in
    # a separate source-defined group instead of inventing a hardware block.
    for name, rec in pdf.items():
        matches = [r for r in regs.values() if int(r['address'],0) == rec['address']]
        if not matches:
            reg = {'name': name, 'address': HEX(rec['address']), 'reset': None,
                'storage_width': 32 if 0x1000 <= rec['address'] <= 0x3014 else 16,
                'access': '?', 'description': f'{name} register.', 'source_refs': [],
                'evidence_status': 'single-source', 'fields': [], 'notes': []}
            regs['DATASHEET_'+name] = reg
            pdf_only.append(name)
        else:
            reg = matches[0]
        reg['source_refs'].append(reference('datasheet', f'p. {rec["page"]}'))
        if name!=reg['name']:
            reg.setdefault('datasheet_names',[]).append(name)
            reg['notes'].append('Datasheet register name '+name+' maps by address to driver name '+reg['name']+'.')
        reg['access'] = rec.get('access', '?')
        candidates = {v for v, _, _ in rec['resets']}
        driver_reset = int(reg['reset'], 0) if reg['reset'] else None
        # Repetition of summary/detail in one publication is one source, not votes.
        if len(candidates) == 1:
            pdf_reset = next(iter(candidates))
            if driver_reset is not None and driver_reset != pdf_reset:
                if name == 'ADIID':
                    reg['reset'] = HEX(pdf_reset)
                    conflict(reg, 'reset', [HEX(driver_reset), HEX(pdf_reset)],
                        'Driver reset declaration is zero; datasheet identification detail and driver runtime AD5940_ADIID identify 0x4144.', HEX(pdf_reset))
                else:
                    reg['reset'] = None
                    conflict(reg, 'reset', [HEX(driver_reset), HEX(pdf_reset)],
                        'Driver declaration and datasheet disagree; repeated tables in one document are not independent votes.')
            else:
                reg['reset'] = HEX(pdf_reset)
        elif candidates:
            reg['reset'] = None
            conflict(reg, 'reset', [HEX(v) for v in sorted(candidates)], 'Datasheet register tables disagree.')
        occupied_pdf = 0
        reserved_pdf = 0
        for pf in rec['fields']:
            mask = ((1 << pf['width'])-1) << pf['position']
            occupied_pdf |= mask
            if pf['name'].upper() == 'RESERVED':
                reserved_pdf |= mask
                reg.setdefault('reserved_regions',[]).append({'position':pf['position'],'width':pf['width'],'reset':HEX(pf['reset']) if pf['reset'] is not None else None,'access':pf['access'],'description':compact(pf['body'].split('0x')[0]),'source_refs':[reference('datasheet',f'p. {pf["page"]}')]})
                continue
            matches = [f for f in reg['fields'] if f['name'] == pf['name']]
            # A same-range label is a documented alias; keep driver canonical name.
            if not matches:
                matches = [f for f in reg['fields'] if f['position'] == pf['position'] and f['width'] == pf['width']]
            if matches:
                f = matches[0]
                if (f['position'], f['width']) != (pf['position'], pf['width']):
                    conflict(reg, 'field.'+f['name']+'.range',
                        [f'{f["position"]}:{f["width"]}', f'{pf["position"]}:{pf["width"]}'],
                        'Driver and datasheet disagree on field range; source alternatives preserved in conflict ledger.')
                    f['range_conflict'] = True
            else:
                f = {'name': pf['name'], 'position': pf['position'], 'width': pf['width'], 'mask': HEX(mask),
                    'reset': None, 'access': '?', 'description': compact(pf['body'].split('0x')[0].split('.')[0]),
                    'source_refs': [], 'enumerations': [], 'evidence_status': 'single-source', 'notes': []}
                reg['fields'].append(f)
            if f['name'] != pf['name']:
                f['driver_name'] = f['name']
                f['name'] = pf['name']
            f['source_refs'].append(reference('datasheet', f'p. {pf["page"]}'))
            semantic_lines=[]
            for semantic_line in pf['lines']:
                if re.match(r'(?:0x[0-9A-Fa-f]+|[01]+) ',semantic_line):
                    break
                semantic_lines.append(semantic_line)
            semantic=re.sub(r'0x[0-9A-Fa-f]+(?: (?:R/W1C|R/W|R|W))?$', '', ' '.join(semantic_lines)).strip()
            f['description'] = compact(semantic)
            f['evidence_status']='corroborated' if len({r['source'] for r in f['source_refs']})>1 and not f.get('range_conflict') else 'unresolved' if f.get('range_conflict') else 'single-source'
            enum_lines = []
            for enum_line in pf['lines'][1:]:
                enum_line=enum_line.split('Data Sheet')[0]
                if re.fullmatch(r'0x[0-9A-Fa-f]+ (?:R/W|R|W)',enum_line.strip()):
                    continue
                starter=re.match(r'(0x[0-9A-Fa-f]+|[01]+) (.+)',enum_line)
                valid_starter=False
                if starter:
                    raw_code,raw_meaning=starter.groups()
                    raw_value=int(raw_code,16) if raw_code.startswith('0x') else int(raw_code,2)
                    valid_starter=raw_value<(1<<f['width']) and not re.match(r'[−–+*/]|(?:kHz|MHz|Hz)\b',raw_meaning)
                if valid_starter:
                    enum_lines.append(enum_line)
                elif enum_lines and not enum_line.startswith(('analog.com','Bits Bit Name','Table ','Data Sheet')) and not (enum_line.isupper() and len(enum_line)>10):
                    enum_lines[-1] += ' ' + enum_line
            for enum_line in enum_lines:
                em = re.match(r'(0x[0-9A-Fa-f]+|[01]+) (.+)', enum_line)
                if not em:
                    continue
                code, meaning = em.groups()
                value = int(code, 16) if code.startswith('0x') else int(code, 2)
                if meaning.strip().strip('.') in ('R/W1C','R/W','R','W'):
                    continue
                if value >= 1 << f['width']:
                    continue
                meaning = re.sub(r' (?:R/W|R|W)$', '', meaning).split('Data Sheet')[0]
                range_match=re.match(r'to ([01]+) (.+)',meaning)
                if range_match:
                    end_value=int(range_match.group(1),2)
                    range_meaning=range_match.group(2)
                    for extra_value in range(value+1,min(end_value+1,1<<f['width'])):
                        if not any(int(e['value'],0)==extra_value for e in f['enumerations']):
                            f['enumerations'].append({'name':'VALUE_'+str(extra_value),'value':HEX(extra_value),'description':compact(range_meaning),'source_refs':[reference('datasheet',f'p. {pf["page"]}')]})
                    meaning=range_meaning
                existing=next((e for e in f['enumerations'] if int(e['value'],0)==value),None)
                if existing:
                    existing['description']=compact(meaning)
                    existing['source_refs'].append(reference('datasheet',f'p. {pf["page"]}'))
                    continue
                tokens = re.sub(r'[^A-Za-z0-9]+','_',meaning.upper()).strip('_').split('_')
                enum_name = '_'.join(tokens[:7])
                if not enum_name or enum_name[0].isdigit():
                    enum_name = 'VALUE_' + enum_name
                if any(e['name']==enum_name for e in f['enumerations']):
                    enum_name += '_CODE_' + str(value)
                f['enumerations'].append({'name':enum_name,'value':HEX(value),'description':compact(meaning),
                    'source_refs':[reference('datasheet',f'p. {pf["page"]}')]})
            f['access'] = pf['access']
            if pf['reset'] is not None:
                f['reset'] = HEX(pf['reset'])
                if reg['reset'] is not None and pf['reset'] != ((int(reg['reset'],0)>>f['position']) & ((1<<f['width'])-1)):
                    conflict(reg,'field.'+f['name']+'.reset',[f['reset'],HEX((int(reg['reset'],0)>>f['position']) & ((1<<f['width'])-1))], 'Datasheet field reset disagrees with register reset.')
                    f['reset'] = None
                    f['evidence_status']='unresolved'
                if reg['name']=='CHIPID' and f['name']=='REVISION':
                    conflict(reg,'field.REVISION.reset',['0x00000003','0x00000002','0x00000000'],'Datasheet revision field, register summary, and driver reset disagree.')
                    f['reset'] = None
                    f['evidence_status']='unresolved'
            elif reg['reset'] is not None:
                f['reset'] = HEX((int(reg['reset'],0) >> f['position']) & ((1<<f['width'])-1))
            else:
                f['reset'] = None
        # Detailed PDF bits supersede broad legacy aggregate declarations.
        reg['legacy_aliases'] = []
        for aggregate in list(reg['fields']):
            others = [f for f in reg['fields'] if f is not aggregate and len(f['source_refs']) and any(r['source']=='datasheet' for r in f['source_refs']) and int(f['mask'],0) & int(aggregate['mask'],0)]
            if others and {r['source'] for r in aggregate['source_refs']}=={'driver'} and aggregate['width']>max(f['width'] for f in others):
                reg['legacy_aliases'].append(aggregate)
                reg['fields'].remove(aggregate)
        # Datasheet reserved regions contradict several legacy driver bit names.
        for f in reg['fields']:
            if int(f['mask'], 0) & reserved_pdf:
                f['access'] = '?'
                f['evidence_status']='unresolved'
                f['notes'].append('Legacy driver field overlaps a datasheet reserved region; writability unresolved.')
                conflict(reg, 'field.'+f['name']+'.access', ['driver named field', 'datasheet reserved'],
                    'Named legacy driver field overlaps a reserved region in the datasheet.')
        reg['pdf_reserved_mask'] = HEX(reserved_pdf)
        reg['pdf_table_coverage_mask'] = HEX(occupied_pdf)
        # Do not silently assume upper bits reserved when table coverage is partial.
    for full, reg in regs.items():
        known = 0
        writable = 0
        unknown = 0
        for f in reg['fields']:
            mask = int(f['mask'], 0)
            known |= mask
            if f['access']=='?' and reg['access']=='R' and not f['notes']:
                f['access']='R'
                f['notes'].append('Read access follows the read-only register summary.')
            if f['access'] in ('R/W', 'R/W1C', 'W'):
                writable |= mask
            elif f['access'] == '?':
                unknown |= mask
        reg['writable_mask'] = HEX(0) if reg['access']=='R' else (None if unknown else HEX(writable))
        reserved_ties=any('overlaps a datasheet reserved' in note for f in reg['fields'] for note in f['notes'])
        incomplete_reserved_coverage=reg.get('pdf_table_coverage_mask') is not None and int(reg['pdf_table_coverage_mask'],0)!=(1<<reg['storage_width'])-1
        reg['reserved_mask'] = None if reserved_ties or incomplete_reserved_coverage else reg.get('pdf_reserved_mask')
        if reg['reserved_mask'] is None:
            reg['notes'].append('Reserved mask unknown: named driver fields conflict with datasheet reserved regions.' if reserved_ties else 'Reserved mask unknown: PDF table leaves some storage bits unclassified.' if incomplete_reserved_coverage else 'Reserved mask unknown: driver declarations do not establish that unlisted bits are reserved.')
        if unknown and reg['writable_mask'] is None:
            reg['notes'].append('Writable mask unknown: at least one field lacks resolved access evidence.')
        # Reset fields from driver cannot remain as invented zero after a register reset tie.
        for f in reg['fields']:
            if reg['reset'] is None and {r['source'] for r in f['source_refs']}=={'driver'}:
                f['reset'] = None
        if reg['name']=='PMBW':
            for f in reg['fields']:
                if f['name']=='SYSBW':
                    for e in f['enumerations']:
                        e['name']={0:'AUTO',1:'50KHZ',2:'100KHZ',3:'250KHZ'}[int(e['value'],0)]
                elif f['name']=='SYSHS':
                    for e in f['enumerations']:
                        e['name']={0:'LOW_POWER',1:'HIGH_POWER'}[int(e['value'],0)]
        if reg['name']=='WGFCW':
            reg['notes'].append('Second-generation silicon uses a 24-bit frequency word divided by 2^30; driver header3526-3532 also records first-generation 20-bit/2^26 behavior. Indexed PDF superscripts are normalized explicitly.')
            reg['source_refs'].extend([reference('driver','ad5940.h:3526-3532'),reference('driver','ad5940.c:1262-1269')])
        if reg['name']=='WGPHASE':
            reg['notes'].append('Phase conversion uses 2^20, consistent with the 20-bit field; indexed PDF text collapses superscripts to 220.')
        if reg['name']=='ADIID':
            reg['source_refs'].extend([reference('driver','ad5940.h:3512 fixed AD5940_ADIID value'),reference('driver','ad5940.c:2936-2939 post-reset identification validation')])
        reg['fields'].sort(key=lambda f:(-f['position'], f['name']))
    settings_path=Path('data/driver_settings.json')
    settings_inventory=json.loads(settings_path.read_text()) if settings_path.exists() else None
    setting_integrations=[]
    if settings_inventory:
        for group in settings_inventory['groups']:
            if group['status']!='direct':
                continue
            for target in group['targets']:
                candidates=[r for r in regs.values() if r['name']==target['register']]
                if not candidates:
                    setting_integrations.append({'target':target,'status':'unmatched-register'})
                    continue
                reg=candidates[0]
                candidates=[f for f in reg['fields'] if target['field'] in (f['name'],f.get('driver_name'))]
                if not candidates:
                    setting_integrations.append({'target':target,'status':'unmatched-field'})
                    continue
                f=candidates[0]
                for group_note in group.get('notes',[]):
                    if group_note not in f['notes']:
                        f['notes'].append(group_note)
                for setting in group['settings']:
                    value=setting['value']
                    value=int(value,0) if isinstance(value,str) else value
                    if value is None or value<0 or value>=1<<f['width']:
                        setting_integrations.append({'setting':setting['name'],'target':target,'status':'outside-field-range'})
                        continue
                    suffix=setting['name'].split('_',1)[-1]
                    family=group['family']
                    stem={'ADCPGA':'GAIN_','ADCSINC2OSR':'OSR_','ADCSINC3OSR':'OSR_','DFTNUM':'POINTS_','STATSAMPLE':'SAMPLES_','ADCAVGNUM':'SAMPLES_','STATDEV':'FACTOR_'}.get(family,'')
                    name=setting.get('enum_name',stem+suffix)
                    name=re.sub(r'[^A-Za-z0-9_]','_',name).upper()
                    description=compact(setting['description'].lstrip('*< '))
                    refs=list(setting.get('source_refs',[]))
                    refs.extend(reference('driver',e['file']+':'+str(e['line'])) for e in group.get('evidence_lines',[]))
                    existing=next((e for e in f['enumerations'] if int(e['value'],0)==value),None)
                    alternative={'name':setting['name'],'value':HEX(value),'description':description,'source_refs':refs}
                    if existing:
                        existing.setdefault('source_alternatives',[]).append(alternative)
                        existing['source_refs'].extend(refs)
                        if len(existing['name'])>30:
                            existing['name']=name
                    else:
                        if any(e['name']==name for e in f['enumerations']):
                            name+='_CODE_'+str(value)
                        f['enumerations'].append({'name':name,'value':HEX(value),'description':description,'source_refs':refs,'source_alternatives':[alternative]})
                    setting_integrations.append({'setting':setting['name'],'target':target,'status':'mapped'})
    pmbw=next(r for r in regs.values() if r['name']=='PMBW')
    conflict(pmbw,'field.SYSBW.enum.0.meaning',[
        {'source':'datasheet','location':'p. 27, Table 10','meaning':'automatic bandwidth configuration based on waveform frequency'},
        {'source':'driver','location':'ad5940.h:2484; ad5940.c:937-939','meaning':'AFEBW_NOACT documentation says retain current setting, but raw zero is written'}],
        'Data sheet automatic-selection semantics and driver keep-current prose disagree. Both meanings remain qualified by source; no semantic majority is asserted.')
    groups = [
        (25,27,'configuration'),(28,29,'identification'),(30,35,'low_power_dac'),
        (36,42,'low_power_tia'),(43,49,'high_speed_dac'),(50,53,'high_speed_tia'),
        (54,63,'adc'),(64,70,'adc_calibration'),(71,71,'adc_postprocessing'),
        (72,73,'adc_statistics'),(74,86,'switch_matrix'),(87,88,'voltage_references'),
        (89,98,'sequencer_fifo'),(99,103,'waveform_generator'),(104,106,'spi'),
        (107,111,'wakeup_timer'),(112,117,'interrupts'),(118,121,'external_interrupts'),
        (122,126,'gpio'),(127,128,'resets'),(129,131,'power_modes'),(132,136,'clocking')]
    grouped = {}
    for full, reg in regs.items():
        reg['driver_block']=full.split('_',1)[0]
        pages=[int(ref['location'].split('.')[1].strip()) for ref in reg['source_refs'] if ref['source']=='datasheet']
        group=next((name for lo,hi,name in groups if pages and lo<=pages[0]<=hi),None)
        if group is None:
            name=reg['name']
            group=('adc_calibration' if any(t in name for t in ['GAIN','OFFSET','CAL','GN']) else
                'adc' if name.startswith(('ADC','AFE_TEMP','TEMP')) else
                'sequencer_fifo' if name.startswith(('SEQ','FIFO','CMD','DATA')) else
                'wakeup_timer' if full.startswith('WUPTMR_') else
                'gpio' if full.startswith('AGPIO_') else
                'interrupts' if full.startswith('INTC_') else
                'spi' if full.startswith('SPII2CS_') else
                'clocking' if any(t in name for t in ['CLK','OSC']) else
                'power_modes' if 'MODE' in name or 'PWR' in name else
                'resets' if 'RST' in name else 'configuration')
            reg['notes'].append('Functional grouping inferred from driver register purpose; no datasheet register detail matched.')
        grouped.setdefault(group,[]).append(reg)
    blocks=[{'name':name,'title':name.replace('_',' ').title()+' registers','registers':sorted(rs,key=lambda r:(int(r['address'],0),r['name']))} for name,rs in sorted(grouped.items())]
    notes_path=Path('data/block_notes.json')
    if notes_path.exists():
        block_notes=json.loads(notes_path.read_text())
        for block in blocks:
            entries=block_notes.get(block['name'],[])
            block['notes']=[e['description'] for e in entries]
            block['source_refs']=[r for e in entries for r in e.get('source_refs',[])]
    return {'schema_version':1, 'device':'AD5940/AD5941', 'family':'ad594x',
        'sources':[{'id':'driver','title':'ADI no-OS AD5940 driver register declarations',
            'url':'https://github.com/analogdevicesinc/no-OS/tree/main/drivers/afe/ad5940',
            'accessed':'2026-10-27','files':{'ad5940.h':hashlib.sha256(driver.read_bytes()).hexdigest(),'ad5940.c':hashlib.sha256(driver.with_suffix('.c').read_bytes()).hexdigest()}},
            {'id':'datasheet','title':'AD5940/AD5941 data sheet Rev. G',
             'url':'https://www.analog.com/media/en/technical-documentation/data-sheets/ad5940-5941.pdf','accessed':'2026-10-27','extraction_sha256':hashlib.sha256(pdfs[0].read_bytes()).hexdigest(),'extraction_format':'web PDF indexed text; not the binary PDF hash'}],
        'blocks':blocks, 'conflicts':conflicts,'driver_enum_declarations':enum_inventory(driver), 'driver_settings':settings_inventory,'driver_setting_integrations':setting_integrations,
        'coverage':{'registers':len(regs),'driver_registers':len(regs)-len(pdf_only),'datasheet_registers':len({r['address'] for r in pdf.values()}),
            'datasheet_only_registers':pdf_only,'fields':sum(len(r['fields']) for r in regs.values()),
            'driver_definition_count':len(definitions),'driver_definition_kinds':{prefix:sum(k.startswith(prefix+'_') for k in definitions) for prefix in ['REG','BITP','BITM','ENUM']},'driver_only_registers':[r['name'] for r in regs.values() if not any(ref['source']=='datasheet' for ref in r['source_refs'])],'highlevel_setting_definitions':sum(len(g['settings']) for g in settings_inventory['groups']) if settings_inventory else 0,'highlevel_target_applications':len(setting_integrations),'enumerations':sum(len(f['enumerations']) for r in regs.values() for f in r['fields']),'pdf_indexed_lines':len(pdf_lines),
            'policy':'Unknown and tied numeric attributes are null; renderer must omit those constants and explain. Source repetition does not create majority evidence.'}}


def enum_inventory(driver):
    result=[]
    current=None
    next_value=0
    for line_number,line in enumerate(driver.read_text().splitlines(),1):
        if re.match(r'^(?:typedef enum|enum ad5940_afe_result)',line):
            current={'kind':'protocol-context' if line.startswith('typedef') else 'software-selector',
                'reason':'SPI address-pointer selectors have no established PNTR field association in the permitted implementation.' if line.startswith('typedef') else 'Software result dispatch selectors are not register field encodings.',
                'settings':[]}
            result.append(current)
            next_value=0
            continue
        if current and line.strip().startswith('}'):
            current=None
            continue
        if current:
            m=re.match(r'\s*(SPI_POINTER_\w+|AFERESULT_\w+)(?:\s*=\s*(\d+))?',line)
            if m:
                name,value=m.groups()
                if value is not None:
                    next_value=int(value)
                current['settings'].append({'name':name,'value':HEX(next_value),'source_refs':[reference('driver',f'ad5940.h:{line_number}')]})
                next_value+=1
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--driver',type=Path,required=True)
    ap.add_argument('--pdf-text',type=Path,action='append',required=True)
    ap.add_argument('--output',type=Path,default=Path('data/registers.json'))
    args=ap.parse_args()
    data=build(args.driver,args.pdf_text)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data['coverage'],indent=2))


if __name__=='__main__':
    main()
