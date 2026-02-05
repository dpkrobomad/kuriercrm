# -*- coding: utf-8 -*-

import re
import time
import logging
from datetime import datetime, timedelta

from odoo import models, api

_logger = logging.getLogger(__name__)

# ShipsGo limit: 100 requests per minute
SHIPSGO_REQUESTS_PER_MINUTE = 100
SHIPSGO_DELAY_BETWEEN_REQUESTS = 60.0 / SHIPSGO_REQUESTS_PER_MINUTE  # ~0.6 seconds
# Process at most this many per cron run to stay under 100/min
SHIPSGO_BATCH_SIZE = 100
# If more remain after a batch, run again after this many minutes
SHIPSGO_NEXT_RUN_MINUTES = 1


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
        trackings = Tracking.search(domain, limit=SHIPSGO_BATCH_SIZE)
        total = len(trackings)
        _logger.info('ShipsGo check: processing %s tracking(s) (batch max %s)', total, SHIPSGO_BATCH_SIZE)

        for i, record in enumerate(trackings):
            # Rate limit: wait before each request (except first) to stay under 100/min
            if i > 0:
                time.sleep(SHIPSGO_DELAY_BETWEEN_REQUESTS)

            cleaned = _clean_container_number(record.container_number)
            if not cleaned:
                record.write({'shipsgo_checking_status': 'Error: Empty container number after clean'})
                continue
            try:
                data, status_code = Tracking._fetch_tracking_info(cleaned)
                if status_code == 200:
                    record.write({
                        'is_shipsgo_tracking': True,
                        'shipsgo_checking_status': 'Success',
                    })
                    _logger.info('ShipsGo: tracking %s container %s -> is_shipsgo_tracking=True', record.name, cleaned)
                else:
                    err_msg = str(data)[:200] if data else 'No data'
                    status_str = 'Error: HTTP %s - %s' % (status_code, err_msg)
                    record.write({
                        'is_shipsgo_tracking': False,
                        'shipsgo_checking_status': status_str[:200],
                    })
                    _logger.debug('ShipsGo: tracking %s container %s -> is_shipsgo_tracking=False (status=%s)', record.name, cleaned, status_code)
            except Exception as e:
                err_str = str(e)[:180]
                record.write({
                    'is_shipsgo_tracking': False,
                    'shipsgo_checking_status': 'Error: %s' % err_str,
                })
                _logger.exception('ShipsGo: failed for tracking %s container %s: %s', record.name, cleaned, e)

        # If we processed a full batch, there may be more; reschedule cron to run in 1 minute
        if total >= SHIPSGO_BATCH_SIZE:
            remaining = Tracking.search_count(domain)
            if remaining > 0:
                cron = self.env['ir.cron'].sudo().search([
                    ('model_id.model', '=', 'shipsgo.tracking.update'),
                    ('code', 'ilike', 'run_shipsgo_check'),
                ], limit=1)
                if cron:
                    next_run = datetime.now() + timedelta(minutes=SHIPSGO_NEXT_RUN_MINUTES)
                    cron.write({'nextcall': next_run})
                    _logger.info('ShipsGo: rescheduled cron at %s (~%s remaining)', next_run, remaining)

        return True
