#!/usr/bin/env python3
"""Bounded native-coordinate extraction: Volume II PDF pages 14–18 only.
No live database writes. Output remains unverified. Never uses old OCR caches.
"""
import csv, json, re, hashlib, zipfile, sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

CODE = re.compile(r'13\.[0-9]+[A-Za-z]?(?:\.[0-9]+[A-Za-z]?)*$')
RATE = re.compile(r'(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}$')
HEADERS = 'schedule_name,edition,volume,chapter,item_code,parent_item_code,description,original_unit,canonical_unit,rate,source_document_name,source_page,is_heading'.split(',')

def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

def lines(words):
    # Geometry, not PDF block order, determines reading order.
    groups = []
    for w in sorted(words, key=lambda w:(w[1],w[0])):
        if groups and abs(w[1]-groups[-1][0][1]) < 2.5:
            groups[-1].append(w)
        else: groups.append([w])
    return [' '.join(w[4] for w in sorted(g,key=lambda w:w[0])) for g in groups]

def parse_page(words, width, height, page):
    # Locate the actual column headers. Fail closed if absent/ambiguous.
    headers = {}
    for name in ('Description','Unit','Rate'):
        hits = [w for w in words if w[4] == name and w[1] < height*.14]
        if len(hits)!=1: raise ValueError(f'PDF {page}: cannot locate unique {name} column')
        headers[name]=hits[0]
    unit_x=headers['Unit'][0]-width*.025
    rate_x=headers['Rate'][0]-width*.035
    top=max(w[3] for w in headers.values())+2
    bottom=height*.935
    anchors=[w for w in words if CODE.fullmatch(w[4]) and w[0]<width*.28 and top<w[1]<bottom and w[4]!='13.0']
    anchors.sort(key=lambda w:(w[1],w[0]))
    if not anchors: raise ValueError(f'PDF {page}: no item anchors in code column')
    result=[]; notes=[]
    # Unnumbered headings are collected separately and terminate descriptions.
    dwords=[w for w in words if width*.17<w[0]<unit_x and top<w[1]<bottom]
    heading_ys=[]
    line_groups = []
    for word in sorted(dwords, key=lambda w: (w[1], w[0])):
        if line_groups and abs(word[1] - line_groups[-1][0][1]) < 2.5:
            line_groups[-1].append(word)
        else:
            line_groups.append([word])
    for group in line_groups:
        text = ' '.join(w[4] for w in sorted(group, key=lambda w: w[0]))
        normalized = re.sub(r'\bmm\b', 'MM', text)
        y = min(w[1] for w in group)
        if (len(text) > 5 and any(c.isalpha() for c in text)
                and normalized.upper() == normalized
                and not any(abs(y - a[1]) < 3 for a in anchors)):
            heading_ys.append(y)
            notes.append({'pdf_page': page, 'text': text})
    for i,a in enumerate(anchors):
        end=anchors[i+1][1]-1 if i+1<len(anchors) else bottom
        stop=min([y-1 for y in heading_ys if a[1]+3<y<end]+[end])
        band=[w for w in words if a[1]-1<=w[1]<stop and w is not a]
        desc=lines([w for w in band if a[2]+1<w[0]<unit_x])
        unit=' '.join(lines([w for w in band if unit_x<=w[0]<rate_x]))
        rate=' '.join(lines([w for w in band if rate_x<=w[0]]))
        result.append({'code':a[4], 'description':' '.join(desc), 'unit':unit,
                       'rate':rate,'pdf_page':page,'bbox':[a[0],a[1],width,stop]})
    return result,notes

def main():
    import fitz
    root=Path.cwd()
    if not (root/'estimate_app').is_dir(): raise SystemExit('Run from /workspaces/Estimate')
    matches=[p for p in (root/'reference_sources').glob('*.pdf') if 'vol_2' in p.name.lower()]
    if len(matches)!=1: raise SystemExit('Expected exactly one Vol_2 PDF in reference_sources')
    source=matches[0]; before=hashlib.sha256(source.read_bytes()).hexdigest()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=root/'.chapter_extraction'/'repair_runs'/stamp; out.mkdir(parents=True)
    raw=[]; notes=[]; exceptions=[]; inventory=[]
    with fitz.open(source) as doc:
        for number in range(14,19):
            p=doc[number-1]; words=p.get_text('words')
            (out/f'page_{number}_words.json').write_text(json.dumps(words,ensure_ascii=False,indent=2))
            (out/f'page_{number}_native.txt').write_text(p.get_text(),encoding='utf-8')
            p.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(out/f'page_{number}.png')
            footer=[w[4] for w in words if w[1]>p.rect.height*.93 and re.fullmatch(r'\d{3}',w[4])]
            printed=footer[0] if len(footer)==1 else ''
            inventory.append({'pdf_page':number,'printed_page':printed,'native_word_count':len(words)})
            try:
                rr,nn=parse_page(words,p.rect.width,p.rect.height,number);raw+=rr;notes+=nn
            except ValueError as e: exceptions.append({'code':'','issue':str(e)})
    counts=Counter(r['code'] for r in raw); bycode={r['code']:r for r in raw}
    candidates=[]
    for r in raw:
        code=r['code']; unit=r['unit']; rate=r['rate']; issue=''
        children=[c for c in bycode if c.startswith(code+'.')]
        parent=code.rsplit('.',1)[0] if code.count('.')>1 else ''
        heading=not unit and not rate and bool(children)
        if code in {'13.61', '13.61.1'}: issue='Source wording anomaly: door-frame parent with painting child; source review required'
        elif counts[code]!=1: issue='Duplicate code anchor'
        elif not r['description']: issue='Missing description'
        elif not heading and (not unit or not RATE.fullmatch(rate)): issue='Unresolved unit/rate; not promoted to heading'
        elif parent and parent not in bycode: issue='Parent outside extracted range or unresolved'
        if issue: exceptions.append({'code':code,'issue':issue});continue
        candidates.append(dict(zip(HEADERS,['CPWD DSR Civil','2023','Volume 2','Finishing',code,parent,r['description'],unit,unit,rate.replace(',',''),source.name,str(r['pdf_page']),'true' if heading else 'false'])))
    # Remove descendants of rejected parents, transitively.
    while True:
        codes={r['item_code'] for r in candidates}
        bad=[r for r in candidates if r['parent_item_code'] and r['parent_item_code'] not in codes]
        if not bad:break
        for r in bad: candidates.remove(r);exceptions.append({'code':r['item_code'],'issue':'Parent quarantined'})
    expected={'13.10':('sqm','506.60'),'13.11':('sqm','518.55'),'13.12':('sqm','537.45'),'13.13':('sqm','378.70')}
    actual={r['item_code']:r for r in candidates}; checks=[]
    for code,(unit,rate) in expected.items():
        r=actual.get(code);ok=bool(r and r['original_unit']==unit and r['rate']==rate and r['is_heading']=='false')
        checks.append({'code':code,'expected_unit':unit,'expected_rate':rate,'pass':ok})
    checks.append({'code':'no_spurious_13.1015','expected_unit':'','expected_rate':'','pass':'13.1015' not in bycode})
    write_csv(out/'candidates.csv',candidates,HEADERS)
    write_csv(out/'exceptions.csv',exceptions,['code','issue'])
    write_csv(out/'regression_checks.csv',checks,['code','expected_unit','expected_rate','pass'])
    write_csv(out/'page_inventory.csv',inventory,['pdf_page','printed_page','native_word_count'])
    write_csv(out/'headings.csv',notes,['pdf_page','text'])
    (out/'raw_rows.json').write_text(json.dumps(raw,indent=2,ensure_ascii=False))
    # Import only into an in-memory database, never user data.
    sys.path.insert(0,str(root))
    import sqlite3
    from estimate_app.database.connection import initialise
    from estimate_app.database.catalogue import CatalogueRepository
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row;initialise(con)
    validation=''
    try:
        repo=CatalogueRepository(con); preview=repo.preview_csv(out/'candidates.csv')
        validation=f'preview_errors={preview.errors}\n'
        if not preview.errors:repo.import_csv(out/'candidates.csv');validation+='isolated_import=passed\n'
    except Exception as e:validation+=f'isolated_import_error={type(e).__name__}: {e}\n'
    finally:con.close()
    after=hashlib.sha256(source.read_bytes()).hexdigest()
    (out/'validation.txt').write_text(validation)
    (out/'README.txt').write_text(f'UNVERIFIED REPAIR DEMONSTRATION ONLY\nsource={source.name}\nsha256_before={before}\nsha256_after={after}\ncandidates={len(candidates)}\nexceptions={len(exceptions)}\nKnown-error checks passed={all(c["pass"] for c in checks)}\nNative coordinates used; no OCR caches used. No full-volume claim.\nRaw rows and images must be reviewed for notes, boundaries and wording.\nExpected values are regression assertions only, never substituted into extraction.\nExisting application tests have not been run by this script.\n')
    import shutil
    shutil.copyfile(__file__,out/'repair_step4b.py')
    dest=out/'step4b_repair_review.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in out.iterdir():
            if p!=dest:z.write(p,p.name)
    print(f'Review ZIP: {dest}\nCandidates: {len(candidates)}; exceptions: {len(exceptions)}')
    if before!=after:raise SystemExit('Source changed; reject this run')
    if not all(c['pass'] for c in checks):raise SystemExit('Known-error checks failed. Upload the review ZIP for diagnosis; do not import.')
    print('Known-error checks passed. All candidates still require source review.')

if __name__=='__main__': main()
