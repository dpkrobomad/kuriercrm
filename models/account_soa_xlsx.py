from odoo import models

class AccountSOAXlsx(models.AbstractModel):
    _name = 'report.deepu_sale.report_soa_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Statement of Account Excel Report'

    def generate_xlsx_report(self, workbook, data, records):
        # Main SOA Sheet
        sheet = workbook.add_worksheet('Statement of Account')
        bold = workbook.add_format({'bold': True})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        money_format = workbook.add_format({'num_format': '#,##0.00'})

        # Headers
        headers = ['Customer', 'Credit Limit', 'Credit Days', 'Total Due', '0-30 Days', 
                  '31-60 Days', '61-90 Days', '91-120 Days', '121-150 Days', 
                  '151-180 Days', '180+ Days']
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)

        # Data
        row = 1
        start_row = row
        for obj in records:
            sheet.write(row, 0, obj.partner_id.name)
            sheet.write(row, 1, obj.credit_limit, money_format)
            sheet.write(row, 2, obj.credit_days)
            sheet.write(row, 3, obj.total_due, money_format)
            sheet.write(row, 4, obj.days_0_30, money_format)
            sheet.write(row, 5, obj.days_31_60, money_format)
            sheet.write(row, 6, obj.days_61_90, money_format)
            sheet.write(row, 7, obj.days_91_120, money_format)
            sheet.write(row, 8, obj.days_121_150, money_format)
            sheet.write(row, 9, obj.days_151_180, money_format)
            sheet.write(row, 10, obj.days_above_180, money_format)
            row += 1

        # Add totals at the bottom
        if row > start_row:
            sheet.write(row, 0, 'Total', bold)
            for col in range(1, 11):
                col_letter = chr(65 + col)  # Convert number to letter (1=A, 2=B, etc)
                sheet.write(row, col, 
                          f'=SUM({col_letter}{start_row+1}:{col_letter}{row})', 
                          money_format)

    def _write_detail_sheet(self, sheet, record, bold, date_format, money_format):
        headers = ['Invoice Number', 'Date', 'Due Date', 'Amount', 'Balance', 'Status']
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)

        row = 1
        for inv in record.invoice_line_ids:
            sheet.write(row, 0, inv.name)
            sheet.write(row, 1, inv.invoice_date, date_format)
            sheet.write(row, 2, inv.invoice_date_due, date_format)
            sheet.write(row, 3, inv.amount_total, money_format)
            sheet.write(row, 4, inv.amount_residual, money_format)
            sheet.write(row, 5, inv.payment_state)
            row += 1 

class AccountSOADetailXlsx(models.AbstractModel):
    _name = 'report.deepu_sale.report_soa_detail_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Statement of Account Detail Excel Report'

    def generate_xlsx_report(self, workbook, data, records):
        bold = workbook.add_format({'bold': True})
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        
        for record in records:
            # Limit sheet name to 31 chars (Excel limitation)
            sheet_name = record.partner_id.name[:31]
            sheet = workbook.add_worksheet(sheet_name)
            
            # Header
            sheet.write(0, 0, 'Customer:', bold)
            sheet.write(0, 1, record.partner_id.name)
            sheet.write(1, 0, 'Credit Limit:', bold)
            sheet.write(1, 1, record.credit_limit, money_format)
            sheet.write(2, 0, 'Credit Days:', bold)
            sheet.write(2, 1, record.credit_days)
            
            # Outstanding Invoices
            row = 4
            sheet.write(row, 0, 'Outstanding Invoices', bold)
            row += 1
            
            headers = ['Invoice Number', 'Date', 'Due Date', 'Amount', 'Due Amount', 'Status']
            for col, header in enumerate(headers):
                sheet.write(row, col, header, bold)
            
            row += 1
            start_row = row
            
            for inv in record.invoice_line_ids:
                sheet.write(row, 0, inv.name)
                sheet.write(row, 1, inv.invoice_date, date_format)
                sheet.write(row, 2, inv.invoice_date_due, date_format)
                sheet.write(row, 3, inv.amount_total, money_format)
                sheet.write(row, 4, inv.amount_residual, money_format)
                sheet.write(row, 5, inv.payment_state)
                row += 1
            
            # Write totals
            if row > start_row:
                sheet.write(row, 0, 'Total', bold)
                sheet.write(row, 3, f'=SUM(D{start_row+1}:D{row})', money_format)
                sheet.write(row, 4, f'=SUM(E{start_row+1}:E{row})', money_format)
            
            # Aging Analysis
            row += 2
            sheet.write(row, 0, 'Aging Analysis', bold)
            row += 1
            aging_data = [
                ('0-30 days', record.days_0_30),
                ('31-60 days', record.days_31_60),
                ('61-90 days', record.days_61_90),
                ('91-120 days', record.days_91_120),
                ('121-150 days', record.days_121_150),
                ('151-180 days', record.days_151_180),
                ('180+ days', record.days_above_180),
                ('Total', record.total_due)
            ]
            
            for label, value in aging_data:
                sheet.write(row, 0, label, bold)
                sheet.write(row, 1, value, money_format)
                row += 1 