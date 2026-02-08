# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SeawayBillLine(models.Model):
    _name = 'seaway.bill.line'
    _description = 'Seaway Bill Line Item'
    _order = 'sequence, id'

    seaway_bill_id = fields.Many2one('seaway.bill', string='Seaway Bill', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)

    marks_and_nos_container = fields.Text(string='MARKS AND NOS CONTAINER')
    seals = fields.Text(string='SEALS')
    no_and_kind_of_package = fields.Text(string='No and kind of package')
    description = fields.Text(string='DESCRIPTION OF PACKAGES AND GOODS, SAID TO CONTAIN')
    gross_weight = fields.Float(string='GROSS WEIGHT (KGS)', digits=(16, 3))
    net_weight = fields.Float(string='NET WEIGHT (KGS)', digits=(16, 3))
    measurement = fields.Float(string='MEASUREMENT (CBM)', digits=(16, 3))
