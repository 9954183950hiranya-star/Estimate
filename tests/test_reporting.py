import sqlite3
from decimal import Decimal as D
import pytest
from estimate_app.database.connection import initialise
from estimate_app.database.projects import Project,ProjectRepository
from estimate_app.database.boq import BOQItem,BOQRepository,Measurement
from estimate_app.calculation.decimal_policy import MeasurementType as T,MeasurementValues as V
from estimate_app.reporting.estimate import ReportOptions,ReportRepository,build_report,report_html,amount_words

def setup():
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row;initialise(con)
    p=ProjectRepository(con).save(Project(None,'Test <school>','ID','Place','Dept','2026-01-01','2026-01-01'))
    repo=BOQRepository(con)
    item=repo.save_item(BOQItem(None,p.id,1,'Building','test','Synthetic plaster','sqm',T.AREA,D('10')))
    return con,p,repo,item

def test_report_reconciles_deductions_and_adjustments():
    con,p,repo,item=setup()
    for deduction,qty in [(False,'12'),(True,'2')]:
        repo.save_measurement(Measurement(None,item.id,'Wall',deduction,T.DIRECT,V(direct_quantity=D(qty))))
    options=ReportOptions(deduction_percent='15',contingency_percent='1')
    r=build_report(con,p.id,options)
    assert r['totals'][-1][1]==D('85.85')
    assert r['groups']==[('Building',D('100.00'))]
    assert 'Test &lt;school&gt;' in report_html(r)
    assert r['provenance'][0][3]=='Unverified'
    assert amount_words(D('1000000'))=='Rupees Ten Lakh Only'
    storage=ReportRepository(con);storage.save(p.id,options)
    assert storage.load(p.id)==options

def test_incomplete_and_negative_reports_blocked():
    con,p,repo,item=setup()
    with pytest.raises(ValueError):build_report(con,p.id,ReportOptions())
    repo.save_measurement(Measurement(None,item.id,'Deduct',True,T.DIRECT,V(direct_quantity=D(1))))
    with pytest.raises(ValueError):build_report(con,p.id,ReportOptions())

@pytest.mark.parametrize('value',['NaN','-1','101',''])
def test_invalid_adjustments(value):
    with pytest.raises(ValueError):ReportOptions(deduction_percent=value).validate()
