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
    def table(rows, headers=None):
        head='<tr>'+''.join('<th>'+escape(str(v))+'</th>' for v in headers)+'</tr>' if headers else ''
        return '<table border="1" cellspacing="0" cellpadding="4">'+head+''.join('<tr>'+''.join('<td>'+escape('' if v is None else str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
    footer='<p>'+escape(report['words'])+'</p><p>Prepared by: '+escape(' / '.join(report['prepared']))+'</p>'
    return '<html><head><style>body {font-family: Arial; font-size:9pt;} th {background:#eeeeee;} table {width:100%;} h1 {font-size:15pt;}</style></head><body><h1>DRAFT — DETAILS OF ESTIMATE</h1>'+table(report['metadata'])+table(report['detail'],DETAIL_HEADERS)+table(report['totals'])+footer+'<h1 style="page-break-before:always">DRAFT — ABSTRACT OF COST</h1>'+table(report['metadata'])+table(report['groups'],['Work component','Amount (Rs)'])+table(report['totals'])+footer+'<h1 style="page-break-before:always">Rate sources and review status</h1>'+table(report['provenance'],['Item','Code','Source','Status','Review','Override reason'])+'</body></html>'

def export_excel(report, path):
    # Local desktop export dependency, not part of the calculation engine.
    import xlsxwriter
    with xlsxwriter.Workbook(str(path), {'strings_to_formulas':False,'strings_to_urls':False}) as book:
        text=book.add_format({'font_name':'Arial','font_size':10,'text_wrap':True,'valign':'top','border':1})
        money=book.add_format({'font_name':'Arial','font_size':10,'num_format':'#,##0.00','border':1,'valign':'top'})
        quantity=book.add_format({'font_name':'Arial','font_size':10,'num_format':'0.000','border':1,'valign':'top'})
        bold=book.add_format({'font_name':'Arial','bold':True,'text_wrap':True,'border':1,'bg_color':'#EEEEEE'})
        for name,headers,rows in [('Detailed estimate',DETAIL_HEADERS,report['detail']),('Abstract of cost',['Work component','Amount (Rs)'],report['groups']),('Rate sources',['Item','Code','Source','Status','Review','Override reason'],report['provenance'])]:
            sheet=book.add_worksheet(name);sheet.set_landscape();sheet.set_paper(9);sheet.fit_to_pages(1,0)
            sheet.set_column(0,0,24);sheet.set_column(1,1,65 if name=='Detailed estimate' else 35);sheet.set_column(2,len(headers)-1,14) if len(headers)>2 else None
            sheet.write(0,0,'DRAFT — '+name.upper(),bold)
            r=2
            for label,value in report['metadata']:
                sheet.write(r,0,label,bold);sheet.write(r,1,value,text);r+=1
            r+=1;sheet.write_row(r,0,headers,bold);sheet.repeat_rows(r);sheet.freeze_panes(r+1,0);r+=1
            for row in rows:
                for col,value in enumerate(row):
                    if isinstance(value,Decimal):sheet.write_number(r,col,float(value),quantity if name=='Detailed estimate' and col==8 else money)
                    else:sheet.write(r,col,'' if value is None else value,text)
                longest=max((len(str(v or '')) for v in row),default=0)
                sheet.set_row(r,max(30,15*((longest//60)+1)));r+=1
            if name!='Rate sources':
                r+=1
                for label,value in report['totals']:
                    sheet.write(r,0,label,bold);sheet.write_number(r,1,float(value),money);r+=1
                sheet.merge_range(r,0,r,max(1,len(headers)-1),report['words'],text);sheet.set_row(r,35)
                sheet.write(r+2,0,'Prepared by',bold);sheet.write(r+2,1,' / '.join(report['prepared']),text)
            sheet.set_footer('&CPage &P of &N');sheet.print_area(0,0,r+3,len(headers)-1)
