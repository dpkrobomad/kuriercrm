from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_limit = fields.Float(string='Credit Limit', default=0.0)
    payment_term_id = fields.Many2one(
        'account.payment.term', 
        string='Default Payment Terms',
        help="This payment term will be used by default on new customer invoices."
    )

    def action_create_account(self):
        self.ensure_one()
        view = self.env.ref('deepu_sale.view_create_account_wizard_form')  # <-- your wizard form xmlid
        return {
            'name': 'Create Account',
            'type': 'ir.actions.act_window',
            'res_model': 'create.account.wizard',
            'view_mode': 'form',
            'view_id': view.id,                # <-- this line
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'active_id': self.id,
            }
        }


    @api.constrains('credit_limit')
    def _check_credit_limit(self):
        for partner in self:
            if partner.credit_limit < 0:
                raise ValidationError("Credit limit cannot be negative!") 
