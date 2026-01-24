import json
from urllib.parse import urlencode

from odoo import models, fields, api

class ReportPOD(models.AbstractModel):
    """Report model for POD to ensure company context is passed correctly"""
    _name = 'report.deepu_sale.report_pod_template'
    _description = 'POD Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Override to pass company context for external_layout"""
        docs = self.env['pod.wizard'].browse(docids)
        # Get company from tracking -> sale_order, or use default company
        company = None
        for doc in docs:
            if doc.tracking_id and doc.tracking_id.sale_order_id:
                company = doc.tracking_id.sale_order_id.company_id
                break
        if not company:
            company = self.env.company
        
        return {
            'doc_ids': docids,
            'doc_model': 'pod.wizard',
            'docs': docs,
            'company': company,
            'res_company': company,  # Fallback for external_layout
        }

class PODWizard(models.TransientModel):
    _name = 'pod.wizard'
    _description = 'POD Wizard'

    tracking_id = fields.Many2one('deepu.sale.tracking', string="Tracking", required=True)
    consignee_address = fields.Text(string="Consignee Address")
    cargo_details = fields.Text(string="Cargo Details")
    no_cartons = fields.Char(string="No. Of Cartons")
    awb_bl = fields.Char(string="Air Way Bill / BL #")
    haulier_plate = fields.Char(string="Haulier Plate #")
    truck_number = fields.Char(string="Truck #")
    delivery_date = fields.Datetime(string="Delivery Date")
    goods_received_ok = fields.Char(string="Goods Received in Good conditions")
    remarks = fields.Text(string="Recipient Remarks If Any")
    receiver_name = fields.Char(string="Receiver's Name")
    date_time = fields.Datetime(string="Date & Time")
    po_number = fields.Char(string="PO Number")

    @api.model
    def default_get(self, fields):
        res = super(PODWizard, self).default_get(fields)
        tracking_id = self.env.context.get('default_tracking_id')
        
        if tracking_id:
            tracking = self.env['deepu.sale.tracking'].browse(tracking_id)
            so = tracking.sale_order_id
            awb_bl_value = tracking.oceanBillOfLading or tracking.awb or tracking.billOfLading
            cargo = so.commodityType if so else ''
            if so and (so.no_of_pcs or so.totalChargableWeight):
                parts = [x for x in (so.commodityType, so.no_of_pcs and f"{so.no_of_pcs} pcs", so.totalChargableWeight and f"CW {so.totalChargableWeight}") if x]
                cargo = ' | '.join(parts) if parts else cargo
            res.update({
                'consignee_address': tracking.consignee or (so.destinationAddress if so else ''),
                'cargo_details': cargo,
                'awb_bl': awb_bl_value,
                'po_number': tracking.po_number,
                'delivery_date': tracking.date_of_delivery or tracking.final_delivery_date,
                'date_time': tracking.date_of_delivery,
            })
        return res

    def _pod_report_url(self):
        """Build report HTML URL to open in new tab (preview)."""
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069').rstrip('/')
        report_name = 'deepu_sale.report_pod_template'
        ids = ','.join(str(i) for i in self.ids)
        ctx = json.dumps(dict(
            lang=self.env.context.get('lang'),
            uid=self.env.uid,
            tz=self.env.context.get('tz'),
            active_ids=self.ids,
        ))
        return f"{base}/report/html/{report_name}/{ids}?{urlencode({'context': ctx})}"

    def preview_pod(self):
        """Open POD in browser (new tab) so user can preview and print from there."""
        return {
            'type': 'ir.actions.act_url',
            'url': self._pod_report_url(),
            'target': 'new',
        }

    def print_pod(self):
        """Open POD in browser (new tab) for preview, then user prints from browser."""
        return self.preview_pod()

    def download_pdf(self):
        """Download POD as PDF (same template: inline styles + logo)."""
        return self.env.ref('deepu_sale.action_report_pod_pdf').report_action(self, data=None, config=False)

