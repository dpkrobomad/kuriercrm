from odoo import models, fields, api

class PODWizard(models.TransientModel):
    _name = 'pod.wizard'
    _description = 'POD Wizard'

    tracking_id = fields.Many2one('deepu.sale.tracking', string="Tracking", required=True)
    consignee_address = fields.Char(string="Consignee Address")
    cargo_details = fields.Char(string="Cargo Details")
    no_cartons = fields.Char(string="No. Of Cartons")
    awb_bl = fields.Char(string="AWB/BL #")
    truck_number = fields.Char(string="Truck Number")
    delivery_date = fields.Datetime(string="Delivery Date")
    po_number = fields.Char(string="PO Number")
    remarks = fields.Text(string="Remarks")
    receiver_name = fields.Char(string="Receiver's Name")
    date_time = fields.Datetime(string="Date & Time")

    @api.model
    def default_get(self, fields):
        res = super(PODWizard, self).default_get(fields)
        tracking_id = self.env.context.get('default_tracking_id')
        
        if tracking_id:
            tracking = self.env['deepu.sale.tracking'].browse(tracking_id)
            awb_bl_value = tracking.oceanBillOfLading or tracking.awb or tracking.billOfLading
            res.update({
                'consignee_address': tracking.consignee,
                'cargo_details': tracking.sale_order_id.commodityType,
                'awb_bl': awb_bl_value,
                'po_number': tracking.po_number,
            })
        return res

    def preview_pod(self):
        return self.env.ref('deepu_sale.action_report_pod').report_action(self, data=None, config=False)

    def print_pod(self):
        return self.env.ref('deepu_sale.action_report_pod').report_action(self)

