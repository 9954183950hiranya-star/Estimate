"""Report snapshots built from saved BOQ values; never change catalogue rates."""
from dataclasses import dataclass, asdict
from decimal import Decimal
from collections import OrderedDict
from html import escape
import json
from estimate_app.calculation.decimal_policy import decimal_from_text, round_money, calculate_measurement
from estimate_app.database.boq import BOQRepository
from estimate_app.database.projects import ProjectRepository

@dataclass
class ReportOptions:
    gp: str = ''
    constituency: str = ''
    financial_year: str = ''
    budget: str = ''
    prepared_by: str = ''
    designation: str = ''
    deduction_percent: str = '0'
    contingency_percent: str = '0'

    def validate(self):
        for name in ('deduction_percent', 'contingency_percent'):
            value = decimal_from_text(getattr(self, name), name)
            if value is None or value > 100:
                raise ValueError('Percentages must be between 0 and 100.')
        decimal_from_text(self.budget, 'Budget')

class ReportRepository:
    def __init__(self, connection):
        self.connection = connection
        connection.execute('CREATE TABLE IF NOT EXISTS report_options (project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE, options TEXT NOT NULL)')
        connection.commit()

    def load(self, project_id):
        row = self.connection.execute('SELECT options FROM report_options WHERE project_id=?', (project_id,)).fetchone()
        return ReportOptions(**json.loads(row[0])) if row else ReportOptions()

    def save(self, project_id, options):
        options.validate()
        self.connection.execute('INSERT INTO report_options VALUES (?,?) ON CONFLICT(project_id) DO UPDATE SET options=excluded.options', (project_id, json.dumps(asdict(options))))
        self.connection.commit()

def amount_words(value):
    small = 'Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen'.split()
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    def words(n):
        if n < 20: return small[n]
        if n < 100: return tens[n//10] + (' ' + words(n%10) if n%10 else '')
        for size, label in ((10000000,'Crore'),(100000,'Lakh'),(1000,'Thousand'),(100,'Hundred')):
            if n >= size: return words(n//size)+' '+label+(' '+words(n%size) if n%size else '')
    value = round_money(value)
    rupees = int(value)
    paise = int((value-rupees)*100)
    return 'Rupees '+words(rupees)+(' and '+words(paise)+' Paise' if paise else '')+' Only'

def build_report(connection, project_id, options):
    options.validate()
    project = ProjectRepository(connection).get(project_id)
    if project is None: raise ValueError('Save a project first.')
    repo = BOQRepository(connection)
    items = repo.list_items(project_id)
    if not items: raise ValueError('Add BOQ items and measurements first.')
    detail = []; groups = OrderedDict(); provenance = []
    for item in items:
        summary = repo.summary(item.id)
        if summary.incomplete or summary.totals.has_negative_net:
            raise ValueError(f'Item {item.serial_number}: complete measurements and rate; net quantity cannot be negative.')
        if not item.description.strip() or not item.unit.strip():
            raise ValueError(f'Item {item.serial_number}: description and unit are required.')
        section = item.work_section.strip() or 'General work'
        groups[section] = groups.get(section, Decimal(0)) + summary.amount
        detail.append([f'Item {item.serial_number} ({item.dsr_item_code})', item.description, '', '', '', '', '', item.unit, summary.totals.displayed_quantity, item.rate, summary.amount])
        for m in repo.list_measurements(item.id):
            v=m.values
            q=calculate_measurement(m.measurement_type,v).quantity
            detail.append(['Less' if m.is_deduction else 'Add', m.particulars, v.repetitions, v.number, v.length, v.breadth, v.height_depth, m.measurement_type.value, -q if m.is_deduction else q, '', m.remarks])
        detail.append(['Net quantity', '', '', '', '', '', '', item.unit, summary.totals.displayed_quantity, '', ''])
        provenance.append([item.serial_number,item.dsr_item_code,item.rate_source,item.verification_status,'Review required' if item.needs_catalogue_review else '',item.manual_override_reason or ''])
    subtotal=sum(groups.values(),Decimal(0))
    deduction=round_money(subtotal*Decimal(options.deduction_percent)/100)
    net=subtotal-deduction
    contingency=round_money(net*Decimal(options.contingency_percent)/100)
    total=net+contingency
    totals=[['Total',subtotal],[f'Less contractor profit ({options.deduction_percent}%)',deduction],['Subtotal after deduction',net],[f'Add contingency ({options.contingency_percent}%)',contingency],['Grand total',total]]
    metadata=[['Scheme ID',project.scheme_id],['Name of scheme',project.project_name],['Location',project.location],['Client / department',project.client_department],['Estimate date',project.estimate_date],['Correction cutoff',project.correction_slip_cutoff_date],['GP',options.gp],['Constituency',options.constituency],['Financial year',options.financial_year],['Budget (Rs)',options.budget]]
    return dict(metadata=metadata,detail=detail,groups=list(groups.items()),totals=totals,words=amount_words(total),provenance=provenance,prepared=[options.prepared_by,options.designation])

DETAIL_HEADERS=['Particulars','Description','Repetitions','Number','Length (m)','Breadth (m)','Height/depth (m)','Unit / mode','Quantity','Rate (Rs)','Amount / remarks']

def report_html(report):
    def esc(v): return escape('' if v is None else str(v))
    def td(v, span=1): return '<td colspan="%s">%s</td>' % (span,esc(v))
    def start(): return '<table width="100%" border="1" cellspacing="0" cellpadding="3">'
    def meta():
        return start()+''.join('<tr>'+td(k,4)+td(v,11)+'</tr>' for k,v in report['metadata'] if v)+'</table>'
    def ending():
        return ''.join('<tr>'+td(k,14)+td(format(v,'.2f'))+'</tr>' for k,v in report['totals'])+'<tr>'+td(report['words'],15)+'</tr></table><p align="right">Prepared by<br>'+esc(' / '.join(report['prepared']))+'</p>'
    body=meta()+'<h2 align="center">DETAILS OF ESTIMATE — DRAFT</h2>'+start()
    body+='<tr>'+td('Particulars of item',11)+td('Unit')+td('Quantity')+td('Rate (Rs)')+td('Amount (Rs)')+'</tr>'
    for row in report['detail']:
        if str(row[0]).startswith('Item '):
            body+='<tr>'+td(str(row[0])+': '+str(row[1]),11)+td(row[7])+td(format(row[8],'.3f'))+td(format(row[9],'.2f'))+td(format(row[10],'.2f'))+'</tr>'
        elif row[0]=='Net quantity':
            body+='<tr>'+td('Total quantity',10)+td(format(row[8],'.3f'))+td('',4)+'</tr>'
        else:
            factors=[v for v in row[2:7] if v is not None and v!='']
            working=' × '.join(map(str,factors)) if factors else 'Direct quantity'
            body+='<tr>'+td(('Less: ' if row[0]=='Less' else '')+str(row[1]),2)+td(working,8)+td(format(abs(row[8]),'.3f'))+td('',4)+'</tr>'
            if row[10]:body+='<tr>'+td('Remarks: '+str(row[10]),15)+'</tr>'
    body+=ending()+'<h2 style="page-break-before:always">Rate sources and review status</h2>'+start()
    for row in [['Item','Code','Source','Status','Review','Reason']]+report['provenance']:body+='<tr>'+''.join(td(v) for v in row)+'</tr>'
    return '<html><head><style>body {font-family:Arial;font-size:9pt;} h2 {font-size:12pt;}</style></head><body>'+body+'</table></body></html>'


def export_excel(report,path):
    import xlsxwriter
    with xlsxwriter.Workbook(str(path),{'strings_to_formulas':False,'strings_to_urls':False}) as book:
        base={'font_name':'Arial','font_size':10,'valign':'top','text_wrap':True}
        text=book.add_format(base)
        border=book.add_format(dict(base,border=1))
        title=book.add_format(dict(base,bold=True,align='center'))
        money=book.add_format(dict(base,num_format='#,##0.00',align='right'))
        qty=book.add_format(dict(base,num_format='0.000',align='right'))
        sheet=book.add_worksheet('Estimate')
        sheet.set_column('A:A',16);sheet.set_column('B:J',5);sheet.set_column('K:K',11);sheet.set_column('L:L',9);sheet.set_column('M:O',14)
        sheet.set_landscape();sheet.set_paper(9);sheet.fit_to_pages(1,0);sheet.set_footer('&CPage &P of &N')
        def merged(r,a,b,value,fmt=text):sheet.merge_range(r,a,r,b,value,fmt)
        def metadata(r):
            for k,v in report['metadata']:
                if v:merged(r,0,5,k);sheet.write(r,6,':');merged(r,7,14,v);sheet.set_row(r,30);r+=1
            return r
        def ending(r):
            for k,v in report['totals']:merged(r,0,13,k);sheet.write_number(r,14,float(v),money);sheet.set_row(r,24);r+=1
            merged(r,0,14,report['words']);sheet.set_row(r,32);r+=2
            merged(r,10,14,'Prepared by');r+=1;merged(r,10,14,' / '.join(report['prepared']));sheet.set_row(r,36)
            return r+2
        r=metadata(0);merged(r,0,14,'DETAILS OF ESTIMATE — DRAFT',title);r+=1
        merged(r,0,10,'Particulars of item',border)
        for col,label in enumerate(['Unit','Quantity','Rate (Rs)','Amount (Rs)'],11):sheet.write(r,col,label,border)
        r+=1
        for row in report['detail']:
            if str(row[0]).startswith('Item '):
                description=str(row[0])+': '+str(row[1]);merged(r,0,10,description,border)
                sheet.write(r,11,row[7],border)
                for col,value in enumerate(row[8:11],12):sheet.write_number(r,col,float(value),qty if col==12 else money)
                sheet.set_row(r,max(45,15*(len(description)//85+1)))
            elif row[0]=='Net quantity':merged(r,0,9,'Total quantity');sheet.write_number(r,10,float(row[8]),qty)
            else:
                sheet.write(r,0,('Less ' if row[0]=='Less' else '')+str(row[1]),text)
                factors=[v for v in row[2:7] if v is not None and v!='']
                for i,value in enumerate(factors):
                    sheet.write_number(r,1+i*2,float(value),text)
                    if i<len(factors)-1:sheet.write(r,2+i*2,'×',text)
                sheet.write_number(r,10,float(abs(row[8])),qty);sheet.set_row(r,30)
                if row[10]:r+=1;merged(r,0,14,'Remarks: '+str(row[10]));sheet.set_row(r,30)
            r+=1
        r=ending(r+1)
        sheet.print_area(0,0,r,14)
        source=book.add_worksheet('Rate sources');source.set_column(0,1,14);source.set_column(2,5,35)
        source.write_row(0,0,['Item','Code','Source','Status','Review','Reason'],border)
        for i,row in enumerate(report['provenance'],1):source.write_row(i,0,row,text)
