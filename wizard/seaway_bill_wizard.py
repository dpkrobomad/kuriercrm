# -*- coding: utf-8 -*-

import json
from urllib.parse import urlencode

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ReportSeawayBill(models.AbstractModel):
    """Report model for Seaway Bill (wizard) PDF/HTML"""
    _name = 'report.deepu_sale.report_seaway_bill_template'
    _description = 'Seaway Bill Report'

    LINES_PER_PAGE = 6
    LINES_FIRST_PAGE = 3  # fewer lines on page 1 so terms + bottom + footer fit

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['seaway.bill.wizard'].browse(docids)
        company = None
        for doc in docs:
            if doc.sale_order_id:
                company = doc.sale_order_id.company_id
                break
        if not company:
            company = self.env.company
        # First chunk = few lines so terms+bottom+footer fit on page 1; rest = full chunks
        doc_chunks = {}
        for doc in docs:
            if not doc or not doc.id:
                continue
            lines = list(doc.line_ids) if doc.line_ids else []
            n_first = self.LINES_FIRST_PAGE
            n_rest = self.LINES_PER_PAGE
            if not lines:
                chunks = [[]]
            else:
                first = lines[:n_first]
                rest = lines[n_first:]
                chunks = [first] if first else []
                for i in range(0, len(rest), n_rest):
                    chunks.append(rest[i:i + n_rest])
                if not chunks:
                    chunks = [[]]
            doc_chunks[doc.id] = {'chunks': chunks, 'total_sheets': len(chunks)}
        return {
            'doc_ids': docids,
            'doc_model': 'seaway.bill.wizard',
            'docs': docs,
            'company': company,
            'res_company': company,
            'doc_chunks': doc_chunks or {},
        }


class ReportSeawayBillDocument(models.AbstractModel):
    """Report model for Seaway Bill (saved bill) PDF"""
    _name = 'report.deepu_sale.report_seaway_bill_document'
    _description = 'Seaway Bill Document Report'

    LINES_PER_PAGE = 6
    LINES_FIRST_PAGE = 3

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['seaway.bill'].browse(docids)
        company = None
        for doc in docs:
            if doc.sale_order_id:
                company = doc.sale_order_id.company_id
                break
        if not company:
            company = self.env.company
        doc_chunks = {}
        for doc in docs:
            if not doc or not doc.id:
                continue
            lines = list(doc.line_ids) if doc.line_ids else []
            n_first = self.LINES_FIRST_PAGE
            n_rest = self.LINES_PER_PAGE
            if not lines:
                chunks = [[]]
            else:
                first = lines[:n_first]
                rest = lines[n_first:]
                chunks = [first] if first else []
                for i in range(0, len(rest), n_rest):
                    chunks.append(rest[i:i + n_rest])
                if not chunks:
                    chunks = [[]]
            doc_chunks[doc.id] = {'chunks': chunks, 'total_sheets': len(chunks)}
        return {
            'doc_ids': docids,
            'doc_model': 'seaway.bill',
            'docs': docs,
            'company': company,
            'res_company': company,
            'doc_chunks': doc_chunks or {},
        }


class SeawayBillWizardLine(models.TransientModel):
    _name = 'seaway.bill.wizard.line'
    _description = 'Seaway Bill Wizard Line Item'

    wizard_id = fields.Many2one('seaway.bill.wizard', string='Wizard', required=True, ondelete='cascade')

    marks_and_nos_container = fields.Text(string='MARKS AND NOS CONTAINER')
    seals = fields.Text(string='SEALS')
    no_and_kind_of_package = fields.Text(string='No and kind of package')
    description = fields.Text(string='DESCRIPTION OF PACKAGES AND GOODS, SAID TO CONTAIN')
    gross_weight = fields.Float(string='GROSS WEIGHT (KGS)', digits=(16, 3))
    net_weight = fields.Float(string='NET WEIGHT (KGS)', digits=(16, 3))
    measurement = fields.Float(string='MEASUREMENT (CBM)', digits=(16, 3))


class SeawayBillWizard(models.TransientModel):
    _name = 'seaway.bill.wizard'
    _description = 'Seaway Bill Wizard'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, readonly=True)
    seaway_bill_id = fields.Many2one('seaway.bill', string='Seaway Bill', readonly=True, help='Existing seaway bill when editing')

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

    # 4. B/L Number (sequence, pre-generated for new bills)
    bl_number = fields.Char(string='Bill of Lading Number', readonly=True)

    # 5. Notify Party
    notify_party = fields.Text(string='Notify Party')

    # 6. PRE-CARRIAGE BY
    pre_carriage_by = fields.Char(string='PRE-CARRIAGE BY')

    # 7. Place of Receipt (sync to sale_order on save)
    place_of_receipt = fields.Char(string='Place of Receipt')

    # 8. Freight To Be Paid At
    freight_to_be_paid_at_id = fields.Many2one('seaway.freight.option', string='Freight To Be Paid At')

    # 9. NO. OF ORIG. BL
    no_of_orig_bl = fields.Integer(string='NO. OF ORIG. BL', default=0)

    # 10. Vessel/Voyage No
    vessel_voyage_no = fields.Char(string='Vessel/Voyage No')

    # 11. pol / 12. pod
    pol = fields.Char(string='Port of Loading')
    pod = fields.Char(string='Port of Destination')

    # 13. FINAL PLACE OF
    final_place_of = fields.Char(string='FINAL PLACE OF')

    # 14. FCL/LCL option
    fcl_lcl_option = fields.Selection([
        ('fcl_fcl', 'FCL to FCL'),
        ('lcl_fcl', 'LCL to FCL'),
        ('fcl_lcl', 'FCL to LCL'),
    ], string='Container Option')

    # 15. Shipped on Board
    shipped_on_board = fields.Datetime(string='Shipped on Board')

    # 17. Delivery Agent
    delivery_agent = fields.Text(string='Delivery Agent')

    # 17. Place of Issue - country
    place_of_issue_country_id = fields.Many2one('res.country', string='Place of Issue (Country)')

    # 18. Issued date
    issued_date = fields.Date(string='Date of Issue')

    # Line items (transient, saved to seaway.bill.line on action_save)
    line_ids = fields.One2many('seaway.bill.wizard.line', 'wizard_id', string='Line Items')

    def _default_line_ids_from_sale_order(self, sale_order):
        """Build default line_ids from sale order: LCL = cargo totals; FCL = container details."""
        lines = []
        ts = (sale_order.ts or '').strip()
        if ts == 'LCL' and sale_order.product_line_ids:
            total_pcs = sum((p.totalpcs or 0) for p in sale_order.product_line_ids)
            total_gross = sum((p.grossWeight or 0) for p in sale_order.product_line_ids)
            total_volume = sum((p.volume or 0) for p in sale_order.product_line_ids)
            lines.append((0, 0, {
                'description': 'Total No. Of PCS: %s' % total_pcs,
                'gross_weight': total_gross,
                'measurement': total_volume,
                'net_weight': 0.0,
            }))
        elif ts == 'FCL' and sale_order.container_line_ids:
            # typeOfContainer: '1'=20 Ft, '2'=40 Ft, '3'=40 Ft HC, '4'=20 Ft RF, '5'=40 Ft RF
            type_labels = {
                '1': "20'",
                '2': "40'",
                '3': "40' HC",
                '4': "20' RF",
                '5': "40' RF",
            }
            by_type = {}
            for c in sale_order.container_line_ids:
                key = c.typeOfContainer or ''
                n = c.noOfContainers or 0
                by_type[key] = by_type.get(key, 0) + n
            parts = []
            for key in ('1', '2', '3', '4', '5'):
                if by_type.get(key, 0):
                    parts.append('%sx%s' % (by_type[key], type_labels.get(key, key)))
            no_and_kind = '\n'.join(parts) if parts else ''
            lines.append((0, 0, {
                'no_and_kind_of_package': no_and_kind,
                'gross_weight': 0.0,
                'net_weight': 0.0,
                'measurement': 0.0,
            }))
        return lines

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            sale_order = self.env['sale.order'].browse(active_id)
            tracking = sale_order.tracking_id

            # Shipper/Consignee: prefer tracking, else sale_order
            shipper = (tracking and tracking.shipper) or sale_order.originAddress or ''
            consignee = (tracking and tracking.consignee) or sale_order.destinationAddress or ''

            # From sale_order
            place_of_receipt = sale_order.place_of_receipt or ''
            pol = sale_order.portOfLoading or ''
            pod = sale_order.portOfDestination or ''

            # From tracking
            vessel_voyage_no = (tracking and tracking.Flight_Vessel_Schedule) or ''
            shipped_on_board = (tracking and tracking.actual_departure) or False

            # Create seaway bill for new orders so sequence is generated and stored (even for draft)
            seaway_bill = self.env['seaway.bill'].search([('sale_order_id', '=', sale_order.id)], limit=1)
            if not seaway_bill:
                seaway_bill = self.env['seaway.bill'].create({'sale_order_id': sale_order.id})
                res['bl_number'] = seaway_bill.bl_number
                res['seaway_bill_id'] = seaway_bill.id

            res.update({
                'sale_order_id': sale_order.id,
                'shipper': shipper,
                'consignee': consignee,
                'place_of_receipt': place_of_receipt,
                'pol': pol,
                'pod': pod,
                'vessel_voyage_no': vessel_voyage_no,
                'shipped_on_board': shipped_on_board,
            })

            # If seaway bill exists, load its data (seaway_bill already searched above)
            if seaway_bill:
                res.update({
                    'seaway_bill_id': seaway_bill.id,
                    'bl_number': seaway_bill.bl_number,
                    'bill_type': seaway_bill.bill_type,
                    'notify_party': seaway_bill.notify_party,
                    'pre_carriage_by': seaway_bill.pre_carriage_by,
                    'freight_to_be_paid_at_id': seaway_bill.freight_to_be_paid_at_id.id,
                    'no_of_orig_bl': seaway_bill.no_of_orig_bl,
                    'final_place_of': seaway_bill.final_place_of,
                    'fcl_lcl_option': seaway_bill.fcl_lcl_option,
                    'delivery_agent': seaway_bill.delivery_agent,
                    'place_of_issue_country_id': seaway_bill.place_of_issue_country_id.id,
                    'issued_date': seaway_bill.issued_date,
                })
                if seaway_bill.shipper:
                    res['shipper'] = seaway_bill.shipper
                if seaway_bill.consignee:
                    res['consignee'] = seaway_bill.consignee
                if seaway_bill.place_of_receipt:
                    res['place_of_receipt'] = seaway_bill.place_of_receipt
                if seaway_bill.pol:
                    res['pol'] = seaway_bill.pol
                if seaway_bill.pod:
                    res['pod'] = seaway_bill.pod
                if seaway_bill.vessel_voyage_no:
                    res['vessel_voyage_no'] = seaway_bill.vessel_voyage_no
                # Shipped on Board: prefer tracking.actual_departure when tracking exists
                if not (tracking and tracking.actual_departure) and seaway_bill.shipped_on_board:
                    res['shipped_on_board'] = seaway_bill.shipped_on_board
                # Load line items from saved bill, or build from sale order (LCL/FCL)
                if 'line_ids' in fields_list:
                    if seaway_bill.line_ids:
                        res['line_ids'] = [(0, 0, {
                            'marks_and_nos_container': l.marks_and_nos_container,
                            'seals': l.seals,
                            'no_and_kind_of_package': l.no_and_kind_of_package,
                            'description': l.description,
                            'gross_weight': l.gross_weight,
                            'net_weight': l.net_weight,
                            'measurement': l.measurement,
                        }) for l in seaway_bill.line_ids]
                    else:
                        # No saved lines: fill from sale order by shipment type
                        line_vals = self._default_line_ids_from_sale_order(sale_order)
                        if line_vals:
                            res['line_ids'] = line_vals

            # Compute no_of_orig_bl based on bill_type
            bill_type = res.get('bill_type', 'draft_seaway')
            res['no_of_orig_bl'] = 3 if bill_type in ('original', 'non_negotiable_bl_copy') else 0

        return res

    @api.onchange('bill_type')
    def _onchange_bill_type(self):
        if self.bill_type in ('original', 'non_negotiable_bl_copy'):
            self.no_of_orig_bl = 3
        else:
            self.no_of_orig_bl = 0

    def action_save(self):
        self.ensure_one()
        vals = {
            'sale_order_id': self.sale_order_id.id,
            'shipper': self.shipper,
            'consignee': self.consignee,
            'bill_type': self.bill_type,
            'notify_party': self.notify_party,
            'pre_carriage_by': self.pre_carriage_by,
            'place_of_receipt': self.place_of_receipt,
            'freight_to_be_paid_at_id': self.freight_to_be_paid_at_id.id,
            'no_of_orig_bl': 3 if self.bill_type in ('original', 'non_negotiable_bl_copy') else 0,
            'vessel_voyage_no': self.vessel_voyage_no,
            'pol': self.pol,
            'pod': self.pod,
            'final_place_of': self.final_place_of,
            'fcl_lcl_option': self.fcl_lcl_option,
            'shipped_on_board': self.shipped_on_board,
            'delivery_agent': self.delivery_agent,
            'place_of_issue_country_id': self.place_of_issue_country_id.id,
            'issued_date': self.issued_date,
        }
        if self.seaway_bill_id:
            self.seaway_bill_id.write(vals)
            seaway_bill = self.seaway_bill_id
            # Replace lines
            seaway_bill.line_ids.unlink()
        else:
            seaway_bill = self.env['seaway.bill'].create(vals)

        # Save line items
        for line in self.line_ids:
            self.env['seaway.bill.line'].create({
                'seaway_bill_id': seaway_bill.id,
                'marks_and_nos_container': line.marks_and_nos_container,
                'seals': line.seals,
                'no_and_kind_of_package': line.no_and_kind_of_package,
                'description': line.description,
                'gross_weight': line.gross_weight,
                'net_weight': line.net_weight,
                'measurement': line.measurement,
            })

        # Sync place_of_receipt to sale_order if changed
        if self.place_of_receipt and self.place_of_receipt != self.sale_order_id.place_of_receipt:
            self.sale_order_id.place_of_receipt = self.place_of_receipt

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seaway.bill',
            'res_id': seaway_bill.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _seaway_bill_report_url(self):
        """Build report HTML URL for preview in new tab."""
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069').rstrip('/')
        report_name = 'deepu_sale.report_seaway_bill_template'
        ids = ','.join(str(i) for i in self.ids)
        ctx = json.dumps(dict(
            lang=self.env.context.get('lang'),
            uid=self.env.uid,
            tz=self.env.context.get('tz'),
            active_ids=self.ids,
        ))
        return f"{base}/report/html/{report_name}/{ids}?{urlencode({'context': ctx})}"

    def action_preview_seaway_bill(self):
        """Open Seaway Bill in browser (new tab) for preview."""
        return {
            'type': 'ir.actions.act_url',
            'url': self._seaway_bill_report_url(),
            'target': 'new',
        }

    def action_print_seaway_bill_pdf(self):
        """Download Seaway Bill as PDF."""
        return self.env.ref('deepu_sale.action_report_seaway_bill_pdf').report_action(self, data=None, config=False)
