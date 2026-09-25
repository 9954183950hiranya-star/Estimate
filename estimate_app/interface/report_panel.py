from pathlib import Path
from dataclasses import fields
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLineEdit,QPushButton,QMessageBox,QFileDialog,QTextBrowser
from PySide6.QtGui import QTextDocument,QPageSize,QPageLayout
from PySide6.QtPrintSupport import QPrinter
from estimate_app.reporting.estimate import ReportOptions,ReportRepository,build_report,report_html,export_excel

class ReportPanel(QWidget):
    def __init__(self, connection):
        super().__init__()
        self.connection=connection;self.repository=ReportRepository(connection);self.project_id=None
        layout=QVBoxLayout(self);form=QFormLayout();self.inputs={}
        labels={'gp':'GP / local body','constituency':'Constituency','financial_year':'Financial year','budget':'Budget (Rs, optional)','prepared_by':'Prepared by','designation':'Designation / office','deduction_percent':'Contractor profit deduction (%)','contingency_percent':'Contingency on net subtotal (%)'}
        for field in fields(ReportOptions):
            control=QLineEdit();self.inputs[field.name]=control;form.addRow(labels[field.name],control)
        layout.addLayout(form)
        for label,callback in [('Save report settings',self.save),('Preview saved estimate',self.preview),('Export Excel',self.excel),('Export PDF',self.pdf)]:
            button=QPushButton(label);button.clicked.connect(callback);layout.addWidget(button)
        self.browser=QTextBrowser();layout.addWidget(self.browser)
        self.set_project(None)

    def set_project(self, project_id):
        self.project_id=project_id;self.setEnabled(project_id is not None);self.browser.clear()
        options=self.repository.load(project_id) if project_id is not None else ReportOptions()
        for name,control in self.inputs.items():control.setText(getattr(options,name))

    def options(self):
        value=ReportOptions(**{name:control.text().strip() for name,control in self.inputs.items()});value.validate();return value

    def save(self):
        try:self.repository.save(self.project_id,self.options())
        except (ValueError,ArithmeticError) as error:QMessageBox.warning(self,'Report settings',str(error))

    def report(self):
        options=self.options();report=build_report(self.connection,self.project_id,options)
        self.repository.save(self.project_id,options);return report

    def preview(self):
        try:self.browser.setHtml(report_html(self.report()))
        except (ValueError,ArithmeticError) as error:QMessageBox.warning(self,'Cannot generate report',str(error))

    def excel(self):
        self.export('xlsx')

    def pdf(self):
        self.export('pdf')

    def export(self, kind):
        try:
            report=self.report()
            filename,_=QFileDialog.getSaveFileName(self,'Export draft estimate','estimate.'+kind,kind.upper()+' (*.'+kind+')')
            if not filename:return
            if not filename.lower().endswith('.'+kind):filename+='.'+kind
            if kind=='xlsx':export_excel(report,Path(filename))
            else:
                printer=QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat);printer.setOutputFileName(filename)
                printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4));printer.setPageOrientation(QPageLayout.Orientation.Landscape)
                doc=QTextDocument();doc.setHtml(report_html(report));doc.print_(printer)
            QMessageBox.information(self,'Export complete',filename)
        except (ValueError,ArithmeticError,OSError,ImportError) as error:QMessageBox.warning(self,'Export failed',str(error))
