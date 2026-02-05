# -*- coding: utf-8 -*-

import re
import logging

from odoo import models, api

_logger = logging.getLogger(__name__)


def _clean_container_number(container_number):
    """Clean container number for ShipsGo API: strip, uppercase, remove extra spaces/dashes."""
    if not container_number:
        return ''
    cleaned = (container_number or '').strip().upper()
    # Remove spaces and common separators (e.g. "ABC 1234567" -> "ABC1234567")
    cleaned = re.sub(r'[\s\-]+', '', cleaned)
    return cleaned


class ShipsgoTrackingUpdate(models.Model):
    _name = 'shipsgo.tracking.update'
    _description = 'ShipsGo Tracking Update (Cron)'

    @api.model
    def run_shipsgo_check(self):
        """
        Cron method: find tracking records that are not delivered, have a container number,
        and is_shipsgo_tracking=False. Clean container number, call ShipsGo API, set
        is_shipsgo_tracking True/False accordingly.
        """
        Tracking = self.env['deepu.sale.tracking']
        domain = [
            ('state', '!=', 'delivered'),
            ('container_number', '!=', False),
            ('container_number', '!=', ''),
            ('is_shipsgo_tracking', '=', False),
        ]
        trackings = Tracking.search(domain)
        _logger.info('ShipsGo check: found %s tracking(s) to check', len(trackings))

        for record in trackings:
            cleaned = _clean_container_number(record.container_number)
            if not cleaned:
                continue
            try:
                data, status_code = Tracking._fetch_tracking_info(cleaned)
                record.write({'is_shipsgo_tracking': status_code == 200})
                if status_code == 200:
                    _logger.info('ShipsGo: tracking %s container %s -> is_shipsgo_tracking=True', record.name, cleaned)
                else:
                    _logger.debug('ShipsGo: tracking %s container %s -> is_shipsgo_tracking=False (status=%s)', record.name, cleaned, status_code)
            except Exception as e:
                _logger.exception('ShipsGo: failed for tracking %s container %s: %s', record.name, cleaned, e)
                record.write({'is_shipsgo_tracking': False})

        return True
