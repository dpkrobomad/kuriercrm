# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Sync all countries into seaway.freight.option so they appear in the dropdown."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['seaway.freight.option'].sync_countries()
