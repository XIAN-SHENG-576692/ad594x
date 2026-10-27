#!/usr/bin/env python3
"""Extract reviewed high-level register setting families from allowed driver h/c.

The mapping table is reviewed source interpretation, not driver implementation.
Reimporting requires the exact source files; rendering needs only committed data.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


def constant(expression):
    try:
        node = ast.parse(expression, mode='eval').body
        def visit(n):
            if isinstance(n, ast.Constant) and type(n.value) is int:
                return n.value
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.LShift, ast.BitOr)):
                a,b=visit(n.left),visit(n.right)
                return a << b if isinstance(n.op,ast.LShift) else a | b
            raise ValueError('nonconstant expression')
        return visit(node)
    except (SyntaxError, ValueError):
        return None


def build(header, implementation):
    lines=header.read_text().splitlines()
    code=implementation.read_text().splitlines()
    families=defaultdict(list)
    for line_no,line in enumerate(lines,1):
        match=re.match(r'#define\s+(\S+)\s+(.*)',line)
        if not match or line_no < 2397:
            continue
        name,body=match.groups()
        expression=re.split(r'/\*|//',body)[0].strip()
        description=re.search(r'/\*\*?<?\s*(.*?)\s*\*/',body)
        setting={'name':name,'source_value':expression,'value':constant(expression),
            'description': description.group(1) if description else name.replace('_',' '),
            'source_line':line_no,
            'source_refs':[{'source':'driver','location':f'ad5940.h:{line_no}'}]}
        families[name.split('_')[0]].append(setting)
    groups=[]
    consumed=set()
    def add(family,targets=(),evidence=(),status='direct',encoding='unshifted',settings=None,note=''):
        consumed.add(family)
        values=[dict(s) for s in (families[family] if settings is None else settings)]
        numeric_labels={'ADCPGA':'GAIN','ADCSINC2OSR':'OSR','ADCSINC3OSR':'OSR',
            'ADCAVGNUM':'SAMPLES','DFTNUM':'POINTS','STATSAMPLE':'SAMPLES',
            'STATDEV':'DEVIATION','HSTIARTIA':'OHMS','LPTIARTIA':'OHMS',
            'LPTIARF':'OHMS','LPTIARLOAD':'OHMS','EXCITBUFGAIN':'GAIN',
            'HSDACGAIN':'GAIN','ADCCLKDIV':'DIV','SYSCLKDIV':'DIV','SEQID':'SEQUENCE'}
        for item in values:
            suffix=item['name'].split('_',1)[-1].upper()
            if suffix[0].isdigit():
                suffix=numeric_labels.get(family,'SETTING')+'_'+suffix
            item['enum_name']=suffix
        if status != 'direct':
            for item in values:
                item['value']=None
        group={'family':family,'status':status,'targets':[{'register':r,'field':f} for r,f in targets],
            'encoding':encoding,'evidence_lines':[{'file':'ad5940.c','line':n,'text':code[n-1].strip()} for n in evidence],
            'settings':values}
        if note:group['notes']=[note]
        groups.append(group)
        return group
    # Direct unshifted encodings: each C assignment/shift is anchored below.
    direct={
        'AFEPWR':('PMBW','SYSHS',[937,939]),'AFEBW':('PMBW','SYSBW',[938,939]),
        'WGTYPE':('WGCON','TYPESEL',[1234]),
        'EXCITBUFGAIN':('HSDACCON','INAMPGNMDE',[1087,1088]),
        'HSDACGAIN':('HSDACCON','ATTENEN',[1089,1090]),
        'HSTIABIAS':('HSTIACON','VBIASSEL',[1119,1120]),
        'HSTIARTIA':('HSRTIACON','RTIACON',[1126,1127]),
        'LPDACSRC':('LPDACCON0','WAVETYPE',[1320]),
        'LPDACVZERO':('LPDACCON0','VZEROMUX',[1321]),
        'LPDACVBIAS':('LPDACCON0','VBIASMUX',[1322]),
        'LPDACREF':('LPDACCON0','REFSEL',[1323]),
        'LPTIARF':('LPTIACON0','TIARF',[1383]),
        'LPTIARLOAD':('LPTIACON0','TIARL',[1382]),
        'LPTIARTIA':('LPTIACON0','TIAGAIN',[1381]),
        'ADCPGA':('ADCCON','GNPGA',[1505]),'ADCMUXP':('ADCCON','MUXSELP',[1501,1641]),
        'ADCMUXN':('ADCCON','MUXSELN',[1502,1642]),
        'ADCRATE':('ADCFILTERCON','ADCSAMPLERATE',[1532]),
        'ADCSINC3OSR':('ADCFILTERCON','SINC3OSR',[1540]),
        'ADCSINC2OSR':('ADCFILTERCON','SINC2OSR',[1539]),
        'ADCAVGNUM':('ADCFILTERCON','AVRGNUM',[1541]),
        'DFTNUM':('DFTCON','DFTNUM',[1740]),'STATSAMPLE':('STATSCON','SAMPLENUM',[1688]),
        'STATDEV':('STATSCON','STDDEV',[1689]),
        'SEQMEMSIZE':('CMDDATACON','CMD_MEM_SEL',[1934]),
        'FIFOMODE':('CMDDATACON','DATAMEMMDE',[1784,1785]),
        'FIFOSRC':('FIFOCON','DATAFIFOSRCSEL',[1803]),
        'FIFOSIZE':('CMDDATACON','DATA_MEM_SEL',[1786,1787]),
        'WUPTENDSEQ':('CON','ENDSEQ',[2299]),
        'SLPKEY':('SEQSLPLOCK','SEQ_SLP_PW',[2854]),
        'HPOSCOUT':('HPOSCCON','CLK32MHZEN',[2522,2536]),
        'LPMODECLK':('LPMODECLKSEL','LFSYSCLKEN',[2837]),
        'SYSCLKSRC':('CLKSEL','SYSCLKSEL',[2464,2466]),
        'ADCCLKSRC':('CLKSEL','ADCCLKSEL',[2465,2466]),
        'SYSCLKDIV':('CLKCON0','SYSCLKDIV',[2458,2459]),
    }
    for family,(reg,field,evidence) in direct.items():
        note=''
        if family=='AFEBW':note='NOACT is documented as keep-current, but this driver writes encoding zero directly. Preserve documented discrepancy; zero is the raw SYSBW setting.'
        add(family,[(reg,field)],evidence,note=note)
    # DFT average is a distinct control path, not DFTINSEL encoding 3.
    add('DFTSRC',[('DFTCON','DFTINSEL')],[1731,1737],settings=[s for s in families['DFTSRC'] if s['name']!='DFTSRC_AVG'])
    add('DFTSRC',[('ADCFILTERCON','AVRGEN'),('DFTCON','DFTINSEL')],[1724,1725,1737],status='composite',settings=[s for s in families['DFTSRC'] if s['name']=='DFTSRC_AVG'],note='AVG enables AVRGEN and leaves DFTINSEL at initialized zero; raw API value 3 is not written to DFTINSEL.')
    add('LPAMPPWR',[('LPTIACON0','IBOOST'),('LPTIACON0','HALFPWR')],[1376,1377,1379],status='composite',note='HALF sets HALFPWR=1; other settings shift value into IBOOST. API values are not one field encoding.')
    add('HSTIADERTIA',[('DE0RESCON','DE0RCON')],list(range(1140,1163)),status='composite',note='API settings are transformed: 1K through TODE map to 11 through 18 in bits7:3, OPEN maps31; 50/100/200 require RLOAD-dependent lookup. Initial range check rejects these three despite later lookup branch. No raw API value is a DE0RCON field setting.')
    add('HSTIADERLOAD',[('DE0RESCON','DE0RCON')],[1165],status='composite',note='Value contributes bits2:0 of combined DE0RCON; cannot be presented as whole-field enumeration independent of DERTIA.')
    add('ADCCLKDIV',[('CLKCON0','ADCCLKDIV')],[2457,2458],status='unresolved',note='Header documents ADC divider constants, but implementation writes SysClkDiv to both divider contributions and uses SYSCLKDIV position. No faithful ADC divider assignment evidence; retain raw constants pending datasheet mapping.')
    add('SEQID',[('SEQORDER',f'SEQ{x}') for x in 'ABCDEFGH'],list(range(2273,2289)),note='Same sequence identifiers also select software sequence information registers; only SEQORDER field encodings emitted.')
    add('SEQGPIOTRIG',[(r,f'IRQ{i}MDE') for r,start in [('EI0CON',0),('EI1CON',4)] for i in range(start,start+4)],status='unresolved',note='Named GPIO trigger modes documented in header, but ad5940_SEQGpioTrigCfg declaration is explicitly not implemented (header4044); field association requires datasheet confirmation.')
    # GPIO function constants are pre-shifted register bit values.
    for i in range(8):
        group=add(f'GP{i}',[('GP0CON',f'PIN{i}CFG')],[2735,2769],encoding=f'source_value >> {2*i}')
        for item in group['settings']:item['value'] >>= 2*i
        if i>=4:group['notes']=['Header documents this pin as unavailable on AD5941.']
        if i==2:group.setdefault('notes',[]).append('GP2_TRIG comment says Sequence1; preserve source comment pending datasheet reconciliation.')
        if i==5:group.setdefault('notes',[]).append('GP5_GPIO spelling says GPIO while comment says Internal Power ON reset; preserve disagreement.')
    # Bitmask source flags map to bit=1 in each documented destination field.
    canonical=json.loads((Path(__file__).resolve().parents[1]/'data/registers.json').read_text())
    registers={r['name']:r for b in canonical['blocks'] for r in b['registers']}
    def bitflags(family,regnames,evidence,aggregate_reason):
        for s in families[family]:
            val=s['value']
            if not val or val & (val-1):
                add(family,[(r,'*') for r in regnames],evidence,status='composite',settings=[s],note=aggregate_reason)
                continue
            bit=val.bit_length()-1
            targets=[]
            for regname in regnames:
                targets.extend((regname,f['name']) for f in registers[regname]['fields'] if f['position']==bit and f['width']==1)
            if not targets:
                add(family,[(r,'*') for r in regnames],evidence,status='unresolved',settings=[s],note=f'Flag bit{bit} lacks a canonical one-bit field; preserve for reconciliation.')
            else:
                group=add(family,targets,evidence,encoding=f'source bitmask >> {bit}',settings=[s])
                group['settings'][0]['value']=1
    for family,reg,evidence in [('SWD','DSWFULLCON',[1054]),('SWP','PSWFULLCON',[1058]),('SWN','NSWFULLCON',[1062]),('SWT','TSWFULLCON',[1066]),('LPDACSW','LPDACSW0',[1338])]:
        bitflags(family,[reg],evidence,'Zero opens all switches together; not a single bitfield setting.')
    bitflags('AFEINTSRC',['INTCSEL0','INTCSEL1','INTCCLR','INTCFLAG0','INTCFLAG1'],[2616,2619,2666],'ALLINT combines 32 sources; not a single-field encoding.')
    # AGPIO pin flags are whole aggregate field bitsets, not one-bit fields.
    add('AGPIO',[(r,f) for r,f in [('GP0OEN','OEN'),('GP0PE','PE'),('GP0IEN','IEN'),('GP0OUT','OUT'),('GP0SET','SET'),('GP0CLR','CLR'),('GP0TGL','TGL'),('SYNCEXTDEVICE','SYNC')]], [2157,2739,2743,2747,2751],note='Individual pin mask is a legal aggregate bitmask; multiple pin masks may be ORed. Header3350-3352 explicitly extends masks to GP0SET/CLR/TGL. Meaning of 1 depends on destination register; not an enable promise for every destination.')
    for family,reg,evidence,note in [
        ('AFECTRL','AFECON',list(range(830,859)),'API selection mask and boolean Enable control multiple AFECON fields; HPREFDIS and ALDOILIMITEN have inverted behavior. A selector mask is not a raw field encoding.'),
        ('LPMODECTRL','LPMODECON',list(range(882,914)),'API selection mask plus boolean Enable transform HFOSCPD, HPREFDIS, ALDOEN inversely; remaining bits positive. Do not emit selectors as raw field values.')]:
        add(family,[(reg,'*')],evidence,status='composite',note=note)
    # Per-register unlocking key constants; same driver source, not independent votes.
    for s in families['KEY']:
        target={'KEY_OSCCON':('OSCKEY','OSCKEY'),'KEY_CALDATLOCK':('CALDATLOCK','KEY'),'KEY_LPMODEKEY':('LPMODEKEY','KEY')}[s['name']]
        evidence=[i for i,l in enumerate(code,1) if s['name'] in l]
        group=add('KEY',[target],evidence[:4],settings=[s])
        if not evidence:
            # The named calibration key is documented in the header even
            # though this driver does not use that macro in its C functions.
            group['evidence_lines']=[{'file':header.name,'line':s['source_line'],
                'text':lines[s['source_line']-1].strip()}]
    exclusions={
        'SPICMD':'SPI wire protocol command bytes, not register field settings.',
        'AFEINTC':'Software index selecting interrupt controller address, not a register field.',
        'DATATYPE':'Software clock-estimation algorithm selector, not a register encoding.',
        'SEQ':'Sequencer instruction constructors/actions/array-length helper; execution semantics, not register constants.',
        'LPTIASW(n)':'Function-like bit selector accepts arbitrary parameter; no finite settings. LPTIASW0 switch fields already represented.',
        'IS':'Software argument validation predicates, not hardware values.',
        'NULL':'C null-pointer compatibility helper.', 'MATH':'Floating-point calculation constant.',
        'AD5940':'ADIID is identification fact; CHIPID is silicon-dependent driver placeholder, not field settings.',
        'PARA':'Software parameter-check placeholder.', 'SILICON':'Compile-time implementation version selection.',
        '':'Compile-time waveform bitwidth depends on SILICON_VER; not a field setting.',
    }
    for family in sorted(set(families)-consumed):
        if family not in exclusions:raise ValueError(f'unreviewed family {family}')
        add(family,status='excluded',note=exclusions[family])
    counts=Counter(g['status'] for g in groups for _ in g['settings'])
    # Every original high-level declaration must appear once, including exclusions.
    original=[s['name'] for ss in families.values() for s in ss]
    recorded=[s['name'] for g in groups for s in g['settings']]
    if Counter(original)!=Counter(recorded):raise ValueError('setting coverage mismatch')
    return {'schema_version':1,'source':'driver','scope':'All active #define declarations after register bitfield section, ad5940.h lines2397-3532; no commented-out constants or enum declarations.',
        'source_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (header,implementation)},
        'groups':groups,'coverage':{'declarations':len(original),'families':len(families),'groups':len(groups),'by_status':dict(counts)},
        'policy':'Only direct groups expose unshifted field settings. Composite, unresolved and excluded groups retain exact raw source facts; no invented single-field mapping. h and c are one independent driver source.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--header',type=Path,required=True)
    parser.add_argument('--implementation',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('data/driver_settings.json'))
    args=parser.parse_args()
    data=build(args.header,args.implementation)
    args.output.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data['coverage'],indent=2))

if __name__=='__main__':main()
