# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SeawayBill(models.Model):
    _name = 'seaway.bill'
    _description = 'Seaway Bill'
    _rec_name = 'bl_number'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    bl_number = fields.Char(string='Bill of Lading Number', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))

    # 1. Shipper / 2. Consignee
    shipper = fields.Text(string='Shipper')
    consignee = fields.Text(string='Consignee')

    # 3. Bill type
    bill_type = fields.Selection([
        ('draft_seaway', 'DRAFT SEAWAY B/L'),
        ('seaway', 'Seaway B/L'),
        ('telex', 'Telex B/L'),
        ('express', 'Express B/L'),
        ('original', 'Original B/L'),
        ('non_negotiable_bl_copy', 'Non Negotiable BL Copy'),
    ], string='Bill Type', default='draft_seaway')

    # 5. Notify Party (optional)
    notify_party = fields.Text(string='Notify Party')

    # 6. PRE-CARRIAGE BY (optional)
    pre_carriage_by = fields.Char(string='PRE-CARRIAGE BY')

    # 7. Place of Receipt
    place_of_receipt = fields.Char(string='Place of Receipt')

    # 8. Freight To Be Paid At
    freight_to_be_paid_at_id = fields.Many2one('seaway.freight.option', string='Freight To Be Paid At')

    # 9. NO. OF ORIG. BL (3 if Original B/L, else 0)
    no_of_orig_bl = fields.Integer(string='NO. OF ORIG. BL', compute='_compute_no_of_orig_bl', store=True, readonly=False)

    # 10. Vessel/Voyage No
    vessel_voyage_no = fields.Char(string='Vessel/Voyage No')

    # 11. pol / 12. pod
    pol = fields.Char(string='Port of Loading')
    pod = fields.Char(string='Port of Destination')

    # 13. FINAL PLACE OF (optional)
    final_place_of = fields.Char(string='FINAL PLACE OF')

    # 14. FCL/LCL option
    fcl_lcl_option = fields.Selection([
        ('fcl_fcl', 'FCL to FCL'),
        ('lcl_fcl', 'LCL to FCL'),
        ('fcl_lcl', 'FCL to LCL'),
    ], string='Container Option')

    # 15. Shipped on Board
    shipped_on_board = fields.Datetime(string='Shipped on Board')

    # 16. Delivery Agent
    delivery_agent = fields.Text(string='Delivery Agent')

    # 17. PLACE AND DATE OF ISSUE - country
    place_of_issue_country_id = fields.Many2one('res.country', string='Place of Issue (Country)')

    # 18. Issued date
    issued_date = fields.Date(string='Date of Issue')

    # Line items
    line_ids = fields.One2many('seaway.bill.line', 'seaway_bill_id', string='Line Items', copy=True)

    @api.depends('bill_type')
    def _compute_no_of_orig_bl(self):
        for rec in self:
            rec.no_of_orig_bl = 3 if rec.bill_type in ('original', 'non_negotiable_bl_copy') else 0

    @api.model
    def create(self, vals):
        if vals.get('bl_number', _('New')) == _('New'):
            vals['bl_number'] = self.env['ir.sequence'].next_by_code('seaway.bill') or _('New')
        return super().create(vals)

    _sql_constraints = [
        ('sale_order_unique', 'UNIQUE(sale_order_id)', 'Exactly one Seaway Bill per Sale Order.'),
    ]

    def action_print_seaway_bill_pdf(self):
        """Print Seaway Bill as PDF."""
        return self.env.ref('deepu_sale.action_report_seaway_bill_form_pdf').report_action(self, data=None, config=False)

    def action_edit_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Edit Bill of Lading'),
            'res_model': 'seaway.bill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.sale_order_id.id, 'active_model': 'sale.order'},
        }
