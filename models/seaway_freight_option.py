# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SeawayFreightOption(models.Model):
    _name = 'seaway.freight.option'
    _description = 'Seaway Bill Freight Option (Freight Prepaid, Freight Collect, Countries)'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    country_id = fields.Many2one('res.country', string='Country', help='Link to country when this is a country option')

    @api.model
    def sync_countries(self):
        """Create freight option records for all countries (called on module init)."""
        countries = self.env['res.country'].search([])
        for country in countries:
            existing = self.search([('country_id', '=', country.id)], limit=1)
            if not existing:
                self.create({'name': country.name, 'country_id': country.id, 'sequence': 20})
        return True
