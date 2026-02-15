# -*- coding: utf-8 -*-
"""
Set bl_number to tracking number (KV-TK...) for existing seaway bills.
"""
from odoo import api, SUPERUSER_ID


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    SeawayBill = env['seaway.bill']
    for bill in SeawayBill.search([]):
        if bill.sale_order_id and bill.sale_order_id.tracking_id:
            new_bl = bill.sale_order_id.tracking_id.name
            if new_bl and bill.bl_number != new_bl:
                bill.sudo().write({'bl_number': new_bl})
