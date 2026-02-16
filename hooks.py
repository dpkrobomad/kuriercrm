# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Sync all countries into seaway.freight.option so they appear in the dropdown."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env['seaway.freight.option'].sync_countries()
    except KeyError:
        pass  # Model may not exist
    # Ensure price_unit_foreign column exists on account_move_line (custom field)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'account_move_line' AND column_name = 'price_unit_foreign'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE account_move_line ADD COLUMN price_unit_foreign double precision
        """)
    # Recompute foreign totals for existing vendor bills with USD/EUR/GBP
    moves = env['account.move'].search([
        ('move_type', '=', 'in_invoice'),
        ('currency_selection', 'in', ('USD', 'EUR', 'GBP')),
    ])
    if moves:
        moves._recompute_foreign_totals()
