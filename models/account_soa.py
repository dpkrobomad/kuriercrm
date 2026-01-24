from odoo import models, fields, api, tools
from datetime import datetime, timedelta

class AccountSOA(models.Model):
    _name = 'account.soa'
    _description = 'Statement of Account'
    _auto = False

    partner_id = fields.Many2one('res.partner', string='Customer')
    credit_limit = fields.Float(string='Credit Limit AED')
    credit_days = fields.Integer(string='Credit Days Agreed')
    total_due = fields.Float(string='Total Amount Due AED')
    days_0_30 = fields.Float(string='0-30 days')
    days_31_60 = fields.Float(string='31-60 days')
    days_61_90 = fields.Float(string='61-90 days')
    days_91_120 = fields.Float(string='91-120 days')
    days_121_150 = fields.Float(string='121-150 days')
    days_151_180 = fields.Float(string='151-180 days')
    days_above_180 = fields.Float(string='180 and above')
    invoice_line_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        compute='_compute_invoice_lines',
        readonly=True,
    )
    paid_invoice_count = fields.Integer(string='Paid Invoices')
    partial_invoice_count = fields.Integer(string='Partially Paid Invoices')
    unpaid_invoice_count = fields.Integer(string='Unpaid Invoices')

    def _get_invoice_domain(self):
        return [
            ('partner_id', '=', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['partial', 'not_paid']),
            ('journal_id.type', '=', 'sale')
        ]

    @api.depends('partner_id')
    def _compute_invoice_lines(self):
        for record in self:
            domain = [
                ('partner_id', '=', record.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['partial', 'not_paid']),
                ('journal_id.type', '=', 'sale')
            ]
            record.invoice_line_ids = self.env['account.move'].search(domain)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
                WITH aging AS (
                    SELECT 
                        partner_id,
                        SUM(CASE WHEN age <= 30 THEN amount_residual ELSE 0 END) as days_0_30,
                        SUM(CASE WHEN age > 30 AND age <= 60 THEN amount_residual ELSE 0 END) as days_31_60,
                        SUM(CASE WHEN age > 60 AND age <= 90 THEN amount_residual ELSE 0 END) as days_61_90,
                        SUM(CASE WHEN age > 90 AND age <= 120 THEN amount_residual ELSE 0 END) as days_91_120,
                        SUM(CASE WHEN age > 120 AND age <= 150 THEN amount_residual ELSE 0 END) as days_121_150,
                        SUM(CASE WHEN age > 150 AND age <= 180 THEN amount_residual ELSE 0 END) as days_151_180,
                        SUM(CASE WHEN age > 180 THEN amount_residual ELSE 0 END) as days_above_180,
                        SUM(amount_residual) as total_due
                    FROM (
                        SELECT 
                            partner_id,
                            amount_residual,
                            DATE_PART('day', NOW() - invoice_date) as age
                        FROM account_move am
                        JOIN account_journal aj ON aj.id = am.journal_id
                        WHERE am.move_type = 'out_invoice'
                        AND am.state = 'posted'
                        AND am.payment_state in ('not_paid', 'partial')
                        AND am.amount_residual > 0
                        AND aj.type = 'sale'
                    ) AS subquery
                    GROUP BY partner_id
                ),
                invoice_counts AS (
                    SELECT 
                        partner_id,
                        COUNT(CASE WHEN payment_state = 'paid' THEN 1 END) as paid_count,
                        COUNT(CASE WHEN payment_state = 'partial' THEN 1 END) as partial_count,
                        COUNT(CASE WHEN payment_state = 'not_paid' THEN 1 END) as unpaid_count
                    FROM account_move
                    WHERE move_type = 'out_invoice'
                    AND state = 'posted'
                    GROUP BY partner_id
                ),
                payment_terms AS (
                    SELECT 
                        pt.id as payment_term_id,
                        COALESCE(MAX(apt.days), 0) as payment_days
                    FROM account_payment_term pt
                    LEFT JOIN account_payment_term_line apt ON apt.payment_id = pt.id
                    GROUP BY pt.id
                )
                SELECT
                    ROW_NUMBER() OVER () as id,
                    p.id as partner_id,
                    p.credit_limit,
                    COALESCE(pt.payment_days, 0) as credit_days,
                    COALESCE(a.total_due, 0) as total_due,
                    COALESCE(a.days_0_30, 0) as days_0_30,
                    COALESCE(a.days_31_60, 0) as days_31_60,
                    COALESCE(a.days_61_90, 0) as days_61_90,
                    COALESCE(a.days_91_120, 0) as days_91_120,
                    COALESCE(a.days_121_150, 0) as days_121_150,
                    COALESCE(a.days_151_180, 0) as days_151_180,
                    COALESCE(a.days_above_180, 0) as days_above_180,
                    COALESCE(ic.paid_count, 0) as paid_invoice_count,
                    COALESCE(ic.partial_count, 0) as partial_invoice_count,
                    COALESCE(ic.unpaid_count, 0) as unpaid_invoice_count
                FROM res_partner p
                LEFT JOIN aging a ON a.partner_id = p.id
                LEFT JOIN payment_terms pt ON pt.payment_term_id = p.payment_term_id
                LEFT JOIN invoice_counts ic ON ic.partner_id = p.id
                WHERE p.customer_rank > 0
                AND COALESCE(a.total_due, 0) > 0
            )
        ''' % self._table) 

    def action_view_detail(self):
        self.ensure_one()
        return {
            'name': 'Customer Statement Detail',
            'view_mode': 'form',
            'res_model': 'account.soa',
            'res_id': self.id,
            'view_id': self.env.ref('deepu_sale.view_account_soa_detail_form').id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def _report_xlsx_installed(self):
        return bool(
            self.env['ir.module.module'].search(
                [('name', '=', 'report_xlsx'), ('state', '=', 'installed')],
                limit=1,
            )
        )

    def action_export_xlsx(self):
        if not self._report_xlsx_installed():
            from odoo.exceptions import UserError
            raise UserError(
                'Excel export requires the "report_xlsx" module. '
                'Install it from Apps, then upgrade deepu_sale and add '
                '"reports/account_soa_report.xml" back to the manifest.'
            )
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'deepu_sale.report_soa_xlsx',
            'report_file': 'Statement of Account',
            'data': {'ids': self.ids},
        }

    def action_export_detail_xlsx(self):
        self.ensure_one()
        if not self._report_xlsx_installed():
            from odoo.exceptions import UserError
            raise UserError(
                'Excel export requires the "report_xlsx" module. '
                'Install it from Apps, then upgrade deepu_sale and add '
                '"reports/account_soa_report.xml" back to the manifest.'
            )
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'report_name': 'deepu_sale.report_soa_detail_xlsx',
            'report_file': 'Statement of Account Detail',
            'context': {'active_model': 'account.soa'},
            'data': {'ids': self.ids},
        } 