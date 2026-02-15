
from odoo import models, fields, api,SUPERUSER_ID, _
from datetime import datetime, timedelta
from itertools import groupby
import json
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, html_keep_url, is_html_empty
import requests
import logging
_logger = logging.getLogger(__name__)

# KURIER_HOST = 'http://127.0.0.1:8000/'
KURIER_HOST = 'https://kuriervogel.com/'

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    # _inherit = [ 'mail.thread', 'mail.activity.mixin', 'resource.mixin', 'avatar.mixin']
    # name = fields.Char(string="Employee Name", related='resource_id.name', store=True, readonly=False, tracking=True)
    
    
    
    # contact = fields.Many2one('res.partner',string='Contact Name')
    ts = fields.Char('Shipemnt Type')
    st = fields.Char('Shipemnt Terms')
    contact = fields.Many2one('res.partner',string='Contact Person')
    contact_person = fields.Char('Contact Person',compute='_compute_contact')
    po_number = fields.Char('PO Number')
    email_ref_no = fields.Char('KV Email Ref No', index=True)
    typeOfShipment = fields.Many2one('site_settings.shipment_type',string="Type Of Shipment")
    shipmentTerms = fields.Many2one('site_settings.terms_of_shipment',string="Shipment Terms")
    cargoReadyDate = fields.Date('Cargo Ready Date')
    portOfLoading = fields.Char('Port Of Loading')
    portOfDestination = fields.Char('Port Of Destination')
    originCountry = fields.Char('Origin Country')
    originCountry_id = fields.Many2one('res.country',string='Origin Country New')
    destinationCountry_id = fields.Many2one('res.country',string='Destination Country New')
    destinationCountry = fields.Char('Destination Country')
    commodityType = fields.Char('Commodity Type')
    originZip = fields.Char('Origin Zip')
    originAddress = fields.Char('Shipper')
    destinationZip = fields.Char('Destination Zip')
    destinationAddress = fields.Char('Consignee')
    cargoWeight = fields.Float('Cargo Weight')
    product_line_ids = fields.One2many('deepu.sale.order.line','sale_order_id')
    container_line_ids = fields.One2many('deepu.sale.container.line','sale_container_order_id')
    totalChargableWeight = fields.Float('Total CW/CBM',compute="_compute_TotalChargable")
    no_of_pcs = fields.Integer(string="Pcs")
    new_state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('tracking','Tracking'),
        ('delivered','Delivered'),
        ('invoiced','Invoiced'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, default='draft',tracking=True)
    tracking_id = fields.Many2one('deepu.sale.tracking',string='Tracking ID')
    is_delivered = fields.Boolean(string="Delivered", compute="_compute_is_delivered", store=True)
    oceanBillOfLading = fields.Char('Bill Of Lading')
    awb = fields.Char('Air Way Bill')
    billOfLading = fields.Char('Truck Way Bill')
    container_number = fields.Char(string="Container Number")
    is_transshipment = fields.Boolean(string="Is Transshipment",default=False)
    place_of_receipt = fields.Char(string="Place of Receipt")
    seaway_bill_ids = fields.One2many('seaway.bill', 'sale_order_id', string='Seaway Bills', readonly=True)
    seaway_bill_id = fields.Many2one('seaway.bill', string='Seaway Bill', compute='_compute_seaway_bill_id', store=False, readonly=True)
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            recs = self.search(['|', ('name', operator, name), ('email_ref_no', operator, name)] + args, limit=limit)
            return recs.name_get()
        return super().name_search(name=name, args=args, operator=operator, limit=limit)
    
    def action_tracking(self):
        
        for rec in self:
            
            rec.new_state = 'tracking'
            vals = {
                'sale_order_id':rec.id,
                'partner_id':rec.partner_id.id
                }
            tracking_obj = rec.env['deepu.sale.tracking']
            result = tracking_obj.sudo().create(vals)
            rec.tracking_id = result.id
            
            
    def preview_tracking(self):
        for rec in self:
     
            view_id = rec.env.ref('deepu_sale.sale_tracking_view_form').id
            return {'type': 'ir.actions.act_window',
                    'name': ('self.tracking_id.name'),
                    'res_model': 'deepu.sale.tracking',
                    'view_mode': 'form',
                    'context': {'default_sale_order_id': rec.id} ,
                    'views': [[view_id, 'form']],
                    'flags': {'initial_mode': 'view'}
                    }

    def action_open_seaway_bill_wizard(self):
        self.ensure_one()
        if not self.tracking_id:
            raise UserError(_('No tracking is available for this Quotation'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bill of Lading'),
            'res_model': 'seaway.bill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'active_model': 'sale.order'},
        }

    def action_view_seaway_bill(self):
        self.ensure_one()
        if not self.seaway_bill_id:
            return self.action_open_seaway_bill_wizard()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bill of Lading'),
            'res_model': 'seaway.bill',
            'res_id': self.seaway_bill_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    
    @api.onchange('originCountry_id')
    def _onchange_originCountry_id(self):
        if self.originCountry_id:
            self.originCountry = self.originCountry_id.name
    
    @api.onchange('destinationCountry_id')
    def _onchange_destinationCountry_id(self):
        if self.destinationCountry_id:
            self.destinationCountry = self.destinationCountry_id.name
    
    @api.depends('seaway_bill_ids')
    def _compute_seaway_bill_id(self):
        for rec in self:
            rec.seaway_bill_id = rec.seaway_bill_ids[:1] if rec.seaway_bill_ids else False

    @api.onchange('typeOfShipment')
    def _onchange_typeOfShipment(self):
        if self.typeOfShipment:
            self.ts = self.typeOfShipment.name
            
    @api.onchange('shipmentTerms')
    def _onchange_shipmentTerms(self):
        if self.shipmentTerms:
            self.st = self.shipmentTerms.name
    
    @api.depends('partner_id')
    def _compute_contact(self):

        for rec in self:
            if rec.partner_id.contact_person !=None and rec.partner_id.contact_person!='':
                rec.contact_person = rec.partner_id.contact_person
            else:
                rec.contact_person = ''
            
            if rec.destinationCountry:
                country = rec.env['res.country'].sudo().search([('name', '=', rec.destinationCountry)], limit=1)
                if country:
                    rec.destinationCountry_id = country.id
                else:
                    rec.destinationCountry_id = False
            else:
                rec.destinationCountry_id = False
            
            if rec.originCountry:
                country = rec.env['res.country'].sudo().search([('name', '=', rec.originCountry)], limit=1)
                if country:
                    rec.originCountry_id = country.id
                else:
                    rec.originCountry_id = False
            else:
                rec.originCountry_id = False
            
            
   

    
    @api.depends('product_line_ids','cargoWeight','container_line_ids')
    def _compute_TotalChargable(self):
        for rec in self:

            vals = 0.0
            count = 0 
            tp = 0
            if rec.ts!='FCL':
                for product in rec.product_line_ids:
                    count +=1
                    tp+=product.totalpcs
                    if product.volume:
                        print(product.chargableWeight,"prod cw>>>>>>>>>>>>>>>>>")
                        vals += (product.chargableWeight)
                rec.no_of_pcs = tp
                rec.totalChargableWeight = vals
                print(vals,">>>>>>>>>>>>>>>>>")
            else:
                rec.totalChargableWeight = rec.cargoWeight
                for c in rec.container_line_ids:
                    tp += c.noOfContainers
                rec.no_of_pcs = tp
                
                
    def write(self, vals):
        if 'state' in vals and vals['state']:
            if vals['state'] == 'sent':
                vals['new_state'] = 'sent'
            elif vals['state'] == 'sale':
                vals['new_state'] = 'sale'
            elif vals['state'] == 'draft':
                vals['new_state'] = 'draft'
            elif vals['state'] == 'cancel':
                vals['new_state'] = 'cancel'
        
        return super(SaleOrder,self).write(vals)
    
    def _prepare_invoice(self):
        self.new_state='invoiced'
        invoice_vals = super(SaleOrder,self)._prepare_invoice()
        invoice_vals['sale_id'] = self.id
        invoice_vals['tracking_id'] = self.tracking_id
        invoice_vals['ts'] = self.ts
        invoice_vals['st'] = self.st
        invoice_vals['po_number'] = self.po_number
        invoice_vals['typeOfShipment'] = self.typeOfShipment
        invoice_vals['shipmentTerms'] = self.shipmentTerms
        invoice_vals['portOfLoading'] = self.portOfLoading
        invoice_vals['portOfDestination'] = self.portOfDestination
        invoice_vals['originCountry'] = self.originCountry
        invoice_vals['destinationCountry'] = self.destinationCountry
        invoice_vals['no_of_pcs'] = self.no_of_pcs
        invoice_vals['totalChargableWeight'] = self.totalChargableWeight
        invoice_vals['cargoWeight'] = self.cargoWeight
        invoice_vals['consignee'] = self.tracking_id.consignee
        invoice_vals['shipper'] = self.tracking_id.shipper
        invoice_vals['commodityType'] = self.commodityType
        invoice_vals['contact_person'] = self.contact_person
        invoice_vals['oceanBillOfLading'] = self.oceanBillOfLading
        invoice_vals['awb'] = self.awb
        invoice_vals['billOfLading'] = self.billOfLading
        invoice_vals['container_number'] = self.container_number
        
        return invoice_vals
    
    @api.depends('tracking_id.state')
    def _compute_is_delivered(self):
        for rec in self:
            rec.is_delivered = rec.tracking_id.state == 'delivered' if rec.tracking_id else False
        

      
class DeepuSaleOrderLines(models.Model):
    _inherit = 'sale.order.line'
    
   

    sale_currency = fields.Many2one('res.currency',default=127,string="Currency")
    new_unit_price = fields.Float(string="Unit Price")
    new_cost = fields.Float(string="Cost")
    deepu_sale_unit_price = fields.Float(string="Unit Sale Price",compute="currencyChanged")
    deepu_sale_cost = fields.Float(string="Unit Cost",compute="CostChanged")
    

    @api.onchange('new_unit_price','sale_currency')
    def currencyChanged(self):
        if self.sale_currency.name=="AED":
            self.price_unit = self.new_unit_price
            self.deepu_sale_unit_price = self.new_unit_price
        else:
            self.price_unit = self.new_unit_price*self.sale_currency.inverse_rate
            self.deepu_sale_unit_price = self.new_unit_price*self.sale_currency.inverse_rate
    @api.onchange('new_cost','sale_currency')
    def CostChanged(self):
        if self.sale_currency.name=="AED":
            self.purchase_price = self.new_cost
            self.deepu_sale_cost = self.new_cost
        else:
            self.purchase_price = self.new_cost*self.sale_currency.inverse_rate
            self.deepu_sale_cost = self.new_cost*self.sale_currency.inverse_rate
        
    # @api.depends('purchase_price')
    # def cost_changed(self):
    #     res={}
    #     if self.price_unit < self.purchase_price:
    #         warning = {"title": _("Price Error!"), "message": _("Do not sell below the purchase price.")}
    #         res["warning"] = warning
    #     else:
    #         self.margin = 
            
            

    #     for item in self:
    #         print(item,self)
    #         curr = self.currency.name
    #         self.new_unit_price.set("string", "Unit Price in "+curr)

class SaleProductOrder(models.Model):
    _name = 'deepu.sale.order.line'
    sale_order_id = fields.Many2one('sale.order')
    length = fields.Float('Length')
    width = fields.Float('Width')
    height = fields.Float('Height')
    totalpcs = fields.Integer('Total pcs')
    grossWeight = fields.Float('Gross Weight')
    volume = fields.Float(string='Volume/CBM',compute='_compute_weight')
    chargableWeight = fields.Float(string='Chargable Weight',compute='_compute_chargable')
    
    
    @api.depends('length','width','height','totalpcs')
    def _compute_weight(self):
        for item in self:

            if item.sale_order_id.ts=='Air Freight' and item.length  and item.width  and item.height  and item.totalpcs    :

                val = (item.length)*(item.width)*(item.height)*(item.totalpcs)
         
                item.volume = round((val/6000),2)
            elif item.sale_order_id.ts=='LCL' and item.length  and item.width  and item.height  and item.totalpcs    :
                
                val = (item.length)*(item.width)*(item.height)*(item.totalpcs)
         
                item.volume = round((val/1000000),2)

        
            elif item.sale_order_id.ts=='Courier Service' and item.length  and item.width  and item.height  and item.totalpcs   :
                val = (item.length)*(item.width)*(item.height)*(item.totalpcs)
         
                item.volume = round((val/5000),2)
            else:
                item.volume =None
            
    @api.depends('grossWeight','volume')
    def _compute_chargable(self):
        for item in self:
            try:
                if item.sale_order_id.ts=='Air Freight' or item.sale_order_id.ts=='Courier Service' or item.sale_order_id.ts=='Road Freight' and item.volume is not None and item.grossWeight is not None:
                    if (item.grossWeight) > (item.volume):
                        item.chargableWeight = item.grossWeight
                    else:
                            item.chargableWeight = item.volume
                
                elif item.sale_order_id.ts=='LCL' and item.volume is not None and item.grossWeight is not None:
                    gwcbm = (item.grossWeight)
          
                    gwcbm = gwcbm/1000
                    gwcbm = round(gwcbm,2)
                    if gwcbm > (item.volume):
                        item.chargableWeight = gwcbm
                    else:
                        item.chargableWeight = item.volume
                else:
                    item.chargableWeight = None
                
            except Exception as e:
                print(e)
            
   
class Containers(models.Model):
    _name = 'deepu.sale.container.line'
    
    sale_container_order_id = fields.Many2one('sale.order')
    typeOfContainer = fields.Selection([('1', '20 Ft'), ('2', '40 Ft'), ('3', '40 Ft HC'),('4', '20 Ft RF'),('5', '40 Ft RF')], string='Type of Container')
    noOfContainers = fields.Integer('No. of Containers')
    temperature = fields.Char('Temperature °C')

##################################################################   Tracking Module #################################################################
##################################################################   Tracking Module #################################################################
##################################################################   Tracking Module #################################################################
##################################################################   Tracking Module #################################################################
    
class Tracking(models.Model):
    _name = 'deepu.sale.tracking'
    _description = "Tracking"
    _inherit = [ 'mail.thread', 'mail.activity.mixin', 'resource.mixin', 'avatar.mixin']
    _order = "name desc"
    name = fields.Char(string='Tracking Number', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    contact = fields.Many2one('res.partner',string='Contact Person',compute="_compute_fields")
    date_created = fields.Datetime(string='Created Date', required=True, readonly=True, index=True, copy=False, default=fields.Datetime.now, help="Creation date of tracking")
    sale_order_id = fields.Many2one('sale.order',string="Quotation Ref.", required=True)
    shipmentType = fields.Char(string="Type of Shipment",compute="_compute_fields",store=True)
    shipmentTerms = fields.Char(string="Terms of Shipment",compute="_compute_fields",store=True)
    scheduled_departure = fields.Datetime(string="Scheduled Departure")
    scheduled_arrival = fields.Datetime(string="Scheduled Arrival")
    actual_departure = fields.Datetime(string="Actual Departure")
    actual_arrival = fields.Datetime(string="Actual Arrival")
    Flight_Vessel_Schedule =  fields.Char(string="Flight/Vessel Schedule")
    date_of_delivery = fields.Datetime(string="Delivered Date")
    no_of_pcs = fields.Integer(string="Pcs")
    totalCW = fields.Float(string="Chargable Weight",compute="_compute_fields")
    consignee = fields.Char(string="Consignee")
    shipper = fields.Char(string="Shipper")
    remarks = fields.Text(string="Remarks",compute="NewEventAdded")
    event_line_ids = fields.One2many('deepu.sale.shipment.history.line','tracking_id')
    vessels_line_ids = fields.One2many('deepu.sale.vessels.line','tracking_id')
    docs_line_ids = fields.One2many('deepu.sale.docs.line','tracking_id')
    state = fields.Selection([
        ('draft','Draft'),
        ('booked', 'Booked'),
        ('departed', 'Departed from Origin Port'),
        ('transit', 'In Transit'),
        ('arrived', 'Arrived at Destination Port'),
        ('clearance', 'Under Clearance'),
        ('out', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, default='draft',tracking=True)
    prev_state = fields.Char(string="Previous State")
    is_invoiced = fields.Boolean(compute='_compute_is_invoiced', string="Is Invoiced")
    required_attention = fields.Boolean(string="Required Attention",default=False)
    partner_id = fields.Many2one(
        'res.partner', string='Customer', readonly=True,
        required=True, change_default=True, index=True, tracking=1,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",compute='_compute_fields',store=True)
    po_number = fields.Char(compute='_compute_fields',string="PO Number")
    sent_action_email = fields.Boolean(string="Send Email for Action",default=True)
    oceanBillOfLading = fields.Char('Bill Of Lading')
    awb = fields.Char('Air Way Bill')
    billOfLading = fields.Char('Truck Way Bill')
    container_number = fields.Char(string="Container Number")
    is_transshipment = fields.Boolean(string="Is Transshipment",default=False)
    container_numbers = fields.One2many(
        'deepu.sale.shipmentcontainer', 
        'shipment_id', 
        string='Container Numbers'
    )

    transit_time = fields.Char(string="Transit Time")
    transit_delay = fields.Char(string="Transit Delay")
    final_delivery_date = fields.Date(string="Final Delivery Date")
    final_delivery_place = fields.Char(string="Final Delivery Place")
    empty_return_date = fields.Char(string="Empty Return Date")
    gate_out_date = fields.Date(string="Gate Out Date")
    container_type = fields.Char(string="Container Type")
    container_teu = fields.Char(string="Container TEU")
    shipping_line = fields.Char(string="Shipping Line")
    booking_no = fields.Char(string="Booking Ref. No")
    co2 = fields.Char(string="CO2 Emission")
    sailing_status = fields.Char(string="Sailing Status")
    shipsgo_checking_status = fields.Char(string="Shipsgo Checking Status")
    is_shipsgo_tracking = fields.Boolean(string="Shipsgo Tracking", default=False)
    is_tracking_done = fields.Boolean(string="Is Tracking Done" , default=False)
    BLContainerCount = fields.Integer(string="BL Container Count")
    blcontainers = fields.One2many(
        'deepu.tracking.blcontainer', 
        'shipment_id', 
        string='BLContainers'
    )

    @api.depends('sale_order_id', 'sale_order_id.invoice_ids')
    def _compute_is_invoiced(self):
        for rec in self:
            rec.is_invoiced = bool(
                rec.sale_order_id
                and rec.sale_order_id.invoice_ids
                and rec.sale_order_id.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
            )

    def _fetch_tracking_info(self, container_number):
        import requests
        try:
            response = requests.get(f'https://shipsgo.com/api/ContainerService/GetContainerInfo?authCode=6e98cefbe062fe1906bbf63ce5d74780&requestId={container_number}&mapPoint=true&co2=true&containerType=true')
            # Assuming the response is in JSON format
            data = response.json()
            print(">>>>>>>>>>>data>>>>>>>>>>>>",data,type(data),response.status_code)
            if response.status_code==200:
                return (data[0], response.status_code)
            else:
                return (data,response.status_code)
        except requests.RequestException as e:
            # Handle exceptions such as connection errors, timeouts, etc.
            # Log the exception or take other appropriate actions
            _logger.error(f"Failed to fetch tracking info: {e}")
            # Return None or an empty dict and an error status code to indicate failure
            return ({}, 500)
    @api.onchange('container_number')
    def _onchange_container_number(self):
        print("onchange executed 1>>>>>>")
        for rec in self:
            if rec.container_number:
                print("onchange executed 2>>>>>>",rec.container_number)
                # Call your API here
                response , status_code  = rec._fetch_tracking_info(rec.container_number)
                print("onchange executed 3>>>>>>",status_code)
                if status_code == 200:
                    print("200 true making true>>>>>>")
                    rec.is_shipsgo_tracking = True
                else:
                    print("false making false>>>>>>")
                    # Handle cases where the API call fails or does not return 200
                    rec.is_shipsgo_tracking = False
            else:
                rec.is_shipsgo_tracking = False
    def fetch_and_update_tracking_details(self):
        print('**********************Records with is_shipsgo_tracking True: %s', self.search_count([('sailing_status', '!=', 'Discharged')]))
        print('**********************Records with is_shipsgo_tracking True: %s', self.search_count([('container_number', '!=', False)]))
        print('**********************Records with is_shipsgo_tracking True: %s', self.search_count([('empty_return_date', '=', False)]))
        print('**********************Records with is_shipsgo_tracking True: %s', self.search_count([('is_shipsgo_tracking', '=', True)]))
        # Assuming you have a field in your model to store the tracking ID or similar
        tracking_ids = self.search([
            # ('sailing_status', '!=', 'Discharged'),
            # ('container_number', '!=', False),  #
            # ('empty_return_date', '=', False),  
            ('is_tracking_done', '=', False), 
            ('is_shipsgo_tracking', '=', True), 
        ])

        print("Tracking Counts found",len(tracking_ids),type(tracking_ids))
        for record in tracking_ids:
            # Make the API call
            print(">>>>>>>>>>container number>>>>>>>>>",record.container_number)
            # This is a placeholder URL and parameters. You'll need to replace these with your actual API details
            data,status_code = self._fetch_tracking_info(record.container_number)
            print("running >>>>>>> ",status_code,data,status_code)
            if status_code == 200:
                actual_departure_str = data.get('DepartureDate')
                actual_departure = datetime.strptime(actual_departure_str, "%d/%m/%Y").date() if actual_departure_str else None
            
                actual_arrival_str = data.get('ArrivalDate')
                actual_arrival = datetime.strptime(actual_arrival_str,  "%d/%m/%Y").date() if actual_arrival_str else None
                scheduled_arrival_str = data.get('FirstETA')
                scheduled_arrival = datetime.strptime(scheduled_arrival_str,  "%d/%m/%Y").date() if scheduled_arrival_str else None
                gate_out_date_str = data.get('GateOutDate')
                gate_out_date = datetime.strptime(gate_out_date_str, "%d/%m/%Y").date() if gate_out_date_str else None
                empty_return_date_str = data.get('EmptyReturnDate')
                empty_return_date = datetime.strptime(empty_return_date_str, "%d/%m/%Y").date() if empty_return_date_str else None
                final_delivery_date_str = data.get('FinalDeliveryDate')
                final_delivery_date = datetime.strptime(final_delivery_date_str, "%d/%m/%Y").date() if final_delivery_date_str else None
                blcontainerz = data.get('BLContainers',[])
                print(blcontainerz)
                print("checking containers >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",type(blcontainerz))
                vessels = data.get('TSPorts',[])
                

                v={
                    "Vessel":data.get('Vessel'),
                    "VesselIMO":data.get('VesselIMO'),
                    "DepartureDate":data.get('DepartureDate'),
                    "ArrivalDate":data.get('ArrivalDate'),
                    "Port":data.get('Pol')
                }
                vessels.insert(0,v)
                container_name_list = list()
                for container in record.blcontainers:
                    container_name_list.append(container.name)
                for contr in blcontainerz:
                    print("Running containers >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                    if contr["ContainerCode"] not in container_name_list:
                        BLGateOutDate_str = contr.get('BLGateOutDate')
                        BLGateOutDate = datetime.strptime(BLGateOutDate_str, "%d/%m/%Y").date() if BLGateOutDate_str else None
                        BLEmptyReturnDate_str = contr.get('BLEmptyReturnDate')
                        BLEmptyReturnDate = datetime.strptime(BLEmptyReturnDate_str, "%d/%m/%Y").date() if BLEmptyReturnDate_str else None
                        new_container = self.env['deepu.tracking.blcontainer'].create({
                            'name': contr.get('ContainerCode'),
                            'ContainerTEU':contr.get('ContainerTEU'),
                            'ContainerType': contr.get('ContainerType'),
                            'BLGateOutDate': BLGateOutDate,
                            'BLEmptyReturnDate': BLEmptyReturnDate,
                            'shipment_id': record.id,
                        })
                        print("adding containers >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",new_container.id,new_container.name)
                        record.write({
                            'blcontainers': [(4, new_container.id)]
                        })
                        print("Writing containers >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",record.blcontainers)
                    else:
                        print("Condition Failed >>>>>>>>>>>>>>>>>>>",container_name_list)  
                shipsgo_vessel_list = list()
                for vessel in record.vessels_line_ids:
                    shipsgo_vessel_list.append(vessel.VesselIMO)
                
                for vessel in vessels:
                    if vessel["VesselIMO"] not in shipsgo_vessel_list:
                        ArrivalDate_str = vessel.get('ArrivalDate')
                        ArrivalDate = datetime.strptime(ArrivalDate_str, "%d/%m/%Y").date() if ArrivalDate_str else None
                        DepartureDate_str = vessel.get('DepartureDate')
                        DepartureDate = datetime.strptime(DepartureDate_str, "%d/%m/%Y").date() if DepartureDate_str else None
                        new_vessel = self.env['deepu.sale.vessels.line'].create({
                            'vessel': vessel.get('Vessel'),
                            'Port':vessel.get('Port'),
                            'ArrivalDate': ArrivalDate,
                            'DepartureDate': DepartureDate,
                            'VesselIMO': vessel.get('VesselIMO'),
                            'tracking_id': record.id,
                        })
                        record.write({
                            'vessels_line_ids': [(4, new_vessel.id)]
                        })


 
                    
                record.write({
                    'sailing_status': data.get('SailingStatus', None),
                    'shipping_line': data.get('ShippingLine', None),
                    'container_teu': data.get('ContainerTEU', None),
                    'container_type': data.get('ContainerType', None),
                    'gate_out_date':gate_out_date,
                    'empty_return_date':empty_return_date,
                    'date_of_delivery': final_delivery_date,
                    'actual_departure': actual_departure,
                    'actual_arrival': actual_arrival,
                    'scheduled_arrival': scheduled_arrival,
                    'final_delivery_place': data.get('FinalDeliveryPlace', None),
                    'transit_time': data.get('FormatedTransitTime', None),
                    'transit_delay': data.get('ETA', None),
                    'co2': data.get('Co2Emission', None),
                    'booking_no': data.get('ReferenceNo', None),
                    'is_shipsgo_tracking': True,
                    'is_tracking_done': True if empty_return_date else False,
                    'BLContainerCount': data.get('BLContainerCount',None),
                    # Update other fields as necessary
                })
    @api.depends('event_line_ids')
    def NewEventAdded(self):
        
        for rec in self:
            comment = ''
            for i in rec.event_line_ids:
    
                comment = i.comments
            rec.remarks = comment
        
    
    # @api.model
    # def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
    #     if self._context.get('sale_show_partner_name'):
    #         if operator == 'ilike' and not (name or '').strip():
    #             domain = []
    #         elif operator in ('ilike', 'like', '=', '=like', '=ilike'):
    #             domain = expression.AND([
    #                 args or [],
    #                 ['|', ('name', operator, name), ('partner_id.name', operator, name)]
    #             ])
    #             return self._search(domain, limit=limit, access_rights_uid=name_get_uid)
    #     return super(SaleOrder, self)._name_search(name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
    @api.depends('sale_order_id')
    def _compute_fields(self):
        for rec in self:

            if rec.sale_order_id.id !=False:
                if rec.sale_order_id.ts:
                    rec.shipmentType = rec.sale_order_id.ts
                else:
                    rec.shipmentType = None
                if rec.sale_order_id.st:
                    rec.shipmentTerms = rec.sale_order_id.st
                else:
                    rec.shipmentTerms = None
                # rec.no_of_pcs = rec.sale_order_id.
                if rec.sale_order_id.totalChargableWeight:
                    rec.totalCW = rec.sale_order_id.totalChargableWeight
                else:
                    rec.totalCW = None
                if rec.sale_order_id.po_number:
                    rec.po_number = rec.sale_order_id.po_number
                else:
                    rec.po_number = None   
                rec.partner_id = rec.sale_order_id.partner_id 
                if rec.sale_order_id.no_of_pcs:
                    rec.no_of_pcs = rec.sale_order_id.no_of_pcs
                else:
                    rec.no_of_pcs = None
                if rec.sale_order_id.originAddress:
                    rec.shipper = rec.sale_order_id.originAddress
                else:
                     rec.shipper = None
                if rec.sale_order_id.destinationAddress:
                    rec.consignee = rec.sale_order_id.destinationAddress
                else:
                    rec.consignee = None
                
                if rec.sale_order_id.contact:
                    rec.contact = rec.sale_order_id.contact
                else:
                    rec.contact = None
                
                if rec.oceanBillOfLading:
                    rec.sale_order_id.oceanBillOfLading = rec.oceanBillOfLading
                else:
                    rec.sale_order_id.oceanBillOfLading = None
                
                if rec.awb:
                    rec.sale_order_id.awb = rec.awb
                else:
                    rec.sale_order_id.awb = None
                
                if rec.billOfLading:
                    rec.sale_order_id.billOfLading = rec.billOfLading
                else:
                    rec.sale_order_id.billOfLading = None
                    
                if rec.container_number:
                    rec.sale_order_id.container_number = rec.container_number 
                else:
                    rec.sale_order_id.container_number = None
                
                    
            
            else:
               
                rec.shipmentType = None
                rec.shipmentTerms = None
                rec.totalCW = None
                rec.po_number = None   
                rec.partner_id = None
                rec.consignee = None
                rec.shipper = None
                rec.contact = None
                # rec.oceanBillOfLading = None
                # rec.awb = None
                # rec.billOfLading = None
            
            

            
            
            
            
            
            


    @api.model
    def create(self, vals):

        if vals.get('name', _('New')) == _('New'):

            seq_date = None
            if 'date_created' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_created']))

            newname = self.env['ir.sequence'].sudo().next_by_code('sale.tracking') or _('New')
            vals['name'] = newname

        if vals.get('is_transshipment') and 'container_numbers' in vals:
            # Assuming the structure of 'container_numbers' in vals is [(6, 0, [IDs])], we take the last ID
            last_container_id = vals['container_numbers'][-1][-1][-1]  # Get the last ID from the list
            last_container = self.env['deepu.sale.shipmentcontainer'].browse(last_container_id)
            vals['container_number'] = last_container.name  # Assuming there's a 'container_number' field in 'deepu.sale.shipmentcontainer'

        result = super(Tracking, self).create(vals)
        return result
    
    def write(self, vals):
        res = super(Tracking, self).write(vals)
        if 'container_numbers' in vals or 'is_transshipment' in vals:
            for record in self:
                # Only update container_number if is_transshipment is True
                if record.is_transshipment:
                    # Retrieve the last container number from the related 'container_numbers' records
                    if record.container_numbers:
                        last_container = record.container_numbers.sorted(key='id', reverse=True)[0]
                        record.container_number = last_container.name  # Assuming there's a 'container_number' field in 'deepu.sale.shipmentcontainer'
        if 'container_number' in vals and not 'is_shipsgo_tracking' in vals:
            for rec in self:
                response , status_code  = rec._fetch_tracking_info(rec.container_number)
                print("onchange executed 3>>>>>>",status_code)
                if status_code == 200:
                    print("200 true making true>>>>>>")
                    rec.is_shipsgo_tracking = True
                else:
                    print("false making false>>>>>>")
                    # Handle cases where the API call fails or does not return 200
                    rec.is_shipsgo_tracking = False
                    
        if 'container_number' in vals and  'is_shipsgo_tracking' in vals and 'empty_return_date' in vals:
            for rec in self:
                rec.is_tracking_done = True
                
            
            
        return res
    
    def action_print_pod(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Print POD',
            'res_model': 'pod.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tracking_id': self.id,
            },
        }
    
    def action_booked(self):

        for rec in self:
            rec.prev_state = rec.state

            if rec.scheduled_arrival is False or rec.scheduled_departure is False:
                raise ValidationError("Scheduled Departure & Scheduled Arrival must be provided!!!")
            elif rec.partner_id.name is False or rec.partner_id.name=='' :
                raise ValidationError("Customer Name must be provided")
            elif rec.partner_id.email is False or rec.partner_id.email=='':
                raise ValidationError("No email address provided for the customer "+rec.partner_id.name)
            elif rec.sale_order_id.portOfLoading is False or rec.sale_order_id.portOfDestination is False:
                raise ValidationError("Port of Loading & Destination must be provided")
            if rec.sent_action_email is False:
                rec.state = 'booked'
            else:
                url = KURIER_HOST+"booked"
   
                header = {
                "Content-Type":"application/json"
                }
                
                # if rec.partner_id.name is False or rec.partner_id.email is False or rec.scheduled_departure is False or rec.scheduled_arrival is False or rec.name is False or rec.sale_order_id.portOfLoading is False or rec.sale_order_id.portOfDestination is False:
                #     raise ValidationError("Customer Name , Customer Email , Scheduled Departure , Scheduled Arrival , Port of Loading & Destination must be provided")
                payload = {"name":rec.partner_id.name,"email":rec.partner_id.email,"etd":str(rec.scheduled_departure),"eta":str(rec.scheduled_arrival),"tracking_no":rec.name,"pol":rec.sale_order_id.portOfLoading,"pod":rec.sale_order_id.portOfDestination,"po_number":rec.po_number or ""}
                try:
                    result = requests.post(url,data=json.dumps(payload), headers=header)
                    print(">>>>>>>>>>>>>>>>>>>>>>>>result",result)
                    if result.status_code == 200:

                        res = json.loads(result.content.decode('UTF-8'))

                        if res['status']==True:
                            rec.state = 'booked'
                        else:
                            print("Failed To change ")
                    else:
                        print(result.status_code)
                except Exception as e:
                    print(e,">>>>>>>>>>>>>>>>>>>>>>>>error")
                    _logger.error(f"Error in action_booked: {e}")
                    
    
            
    
    def action_departed(self):
        for rec in self:
            rec.prev_state = rec.state

            if rec.actual_departure is False or rec.Flight_Vessel_Schedule is False:
                raise ValidationError("Actual Departure & Flight/Vessel Schedule must be provided!!!")
            if rec.sent_action_email is False:
                rec.state = 'departed'
            else:
                url = KURIER_HOST+"departed"
  
                header = {
                "Content-Type":"application/json"
                }
                payload = {"name":rec.partner_id.name,"email":rec.partner_id.email,"flight_vessel":rec.Flight_Vessel_Schedule,"atd":str(rec.actual_departure),"eta":str(rec.scheduled_arrival),"tracking_no":rec.name,"pol":rec.sale_order_id.portOfLoading,"po_number":rec.po_number or ""}
                try:
                    result = requests.post(url,data=json.dumps(payload), headers=header)
                    if result.status_code == 200:

                        res = json.loads(result.content.decode('UTF-8'))

                        if res['status']==True:
                            rec.state = 'departed'
                        else:
                            print("Failed To change ")
                    else:
                        print(result.status_code)
                except Exception as e:
                    print(e,">>>>>>>>>>>>>>>>>>>>>>>>error")
                    _logger.error(f"Error in action_departed: {e}")
    def action_transpotation(self):
        for rec in self:
            rec.prev_state = rec.state
            if rec.sent_action_email is False:
                rec.state = 'transit'
            else:
                url = KURIER_HOST + "transportation"
                header = {
                    "Content-Type": "application/json",
                    "User-Agent": "Odoo/15.0 (KurierCRM)",
                }
                payload = {"name": rec.partner_id.name, "email": rec.partner_id.email, "tracking_no": rec.name, "po_number": rec.po_number or ""}
                try:
                    _logger.info("action_transportation payload: %s", payload)
                    result = requests.post(url, data=json.dumps(payload), headers=header, timeout=30)
                    if result.status_code == 200:

                        res = json.loads(result.content.decode('UTF-8'))

                        if res['status']==True:
                            rec.state = 'transit'
                        else:
                            print("Failed To change ")
                    else:
                        _logger.warning("action_transportation API returned %s: %s", result.status_code, result.content[:500] if result.content else "")
                except Exception as e:
                    _logger.error("Error in action_transportation: %s", e, exc_info=True)
    def action_arrived(self):
        for rec in self:
            rec.prev_state = rec.state
            if rec.actual_arrival is False :
                raise ValidationError("Actual Arrival must be provided!!!")
            if rec.sent_action_email is False:
                rec.state = 'arrived'
            else:
                url = KURIER_HOST+"arrived"

                header = {
                "Content-Type":"application/json"
                }
                payload = {"name":rec.partner_id.name,"email":rec.partner_id.email,"ata":str(rec.actual_arrival),"tracking_no":rec.name,"pol":rec.sale_order_id.portOfLoading,"pod":rec.sale_order_id.portOfDestination,"po_number":rec.po_number or ""}
                try:
                    result = requests.post(url,data=json.dumps(payload), headers=header)
                    print(">>>>>>>>>>>>>>>>>>>>>>>>result",result)
                    if result.status_code == 200:
  
                        res = json.loads(result.content.decode('UTF-8'))
                        print(">>>>>>>>>>>>>>>>>>>>>>>>res",res)
    
                        if res['status']==True:
                            rec.state = 'arrived'
                        else:
                            print("Failed To change ")
                    else:
                        print(result.status_code)
                except Exception as e:
                    print(e,">>>>>>>>>>>>>>>>>>>>>>>>error")
                    _logger.error(f"Error in action_arrived: {e}")
    def action_clearance(self):
        for rec in self:
            rec.prev_state = rec.state
            if rec.sent_action_email is False:
                rec.state = 'clearance'
            else:
                url = KURIER_HOST+"clearance"
                
                header = {
                "Content-Type":"application/json"
                }
                payload = {"name":rec.partner_id.name,"email":rec.partner_id.email,"tracking_no":rec.name,"po_number":rec.po_number or ""}
                try:
                    result = requests.post(url,data=json.dumps(payload), headers=header)
                    print(">>>>>>>>>>>>>>>>>>>>>>>>result",result)
                    if result.status_code == 200:

                        res = json.loads(result.content.decode('UTF-8'))
                        print(">>>>>>>>>>>>>>>>>>>>>>>>res",res)

                        if res['status']==True:
                            rec.state = 'clearance'
                        else:
                            print("Failed To change ")
                    else:
                        print(result.status_code)
                except Exception as e:
                    print(e,">>>>>>>>>>>>>>>>>>>>>>>>error")
                    _logger.error(f"Error in action_clearance: {e}")
            
    def action_out_for_delivery(self):
        for rec in self:
            rec.prev_state = rec.state
            if rec.sent_action_email is False:
                rec.state = 'out'
            else:
                url = KURIER_HOST+"out_for_delivery"
                
                header = {
                "Content-Type":"application/json"
                }
                payload = {"name":rec.partner_id.name,"email":rec.partner_id.email,"tracking_no":rec.name,"po_number":rec.po_number or ""}
                try:
                    result = requests.post(url,data=json.dumps(payload), headers=header)
                    print(">>>>>>>>>>>>>>>>>>>>>>>>result",result)
                    if result.status_code == 200:

                        res = json.loads(result.content.decode('UTF-8'))
                        print(">>>>>>>>>>>>>>>>>>>>>>>>res",res)

                        if res['status']==True:
                            rec.state = 'out'
                        else:
                            print("Failed To change ")
                    else:
                        print(result.status_code)
                except Exception as e:
                    print(e,">>>>>>>>>>>>>>>>>>>>>>>>error")
                    _logger.error(f"Error in action_out_for_delivery: {e}")
    
    def action_delivered(self):
        # date_of_delivery
        for rec in self:
            rec.prev_state = rec.state
            if rec.date_of_delivery is False :
                raise ValidationError("Delivered Date must be provided!!!")
            if rec.sent_action_email is False:
                rec.state = 'delivered'
            else:
                url = KURIER_HOST+"delivered"
                
                header = {
                "Content-Type":"application/json"
                }
                payload = {"name":rec.partner_id.name,"email":rec.partner_id.email,"ata":str(rec.actual_arrival),"tracking_no":rec.name,"pol":rec.sale_order_id.portOfLoading,"pod":rec.sale_order_id.portOfDestination,"delivered_date":str(rec.date_of_delivery),"po_number":rec.po_number or ""}
                try:
                    result = requests.post(url,data=json.dumps(payload), headers=header)
                    print(">>>>>>>>>>>>>>>>>>>>>>>>result",result)
                    if result.status_code == 200:
                    
                        res = json.loads(result.content.decode('UTF-8'))
                        print(">>>>>>>>>>>>>>>>>>>>>>>>res",res)
                    
                        if res['status']==True:
                            rec.state = 'delivered'
                            rec.sale_order_id.is_delivered = True
                            rec.sale_order_id.new_state = 'delivered'
                        else:
                            print("Failed To change ")
                    else:
                        print(result.status_code)
                except Exception as e:
                    print(e,">>>>>>>>>>>>>>>>>>>>>>>>error")
                    _logger.error(f"Error in action_delivered: {e}")
            
    def action_cencel(self):
        for rec in self:
            rec.prev_state = rec.state
            rec.state = 'cancel'
            
    def action_set_to_prev(self):
        for rec in self:
            rec.state = rec.prev_state
            # rec.state = 'arrived'
    def action_set_draft(self):
        for rec in self:
            rec.prev_state = rec.state
            rec.state = 'draft'
                
class ShipmentContainer(models.Model):
    _name = 'deepu.sale.shipmentcontainer'
    _description = 'Shipment Container'

    name = fields.Char('Container Number')
    shipment_id = fields.Many2one('deepu.sale.tracking', string='Tracking Number')

class BLContainer(models.Model):
    _name = 'deepu.tracking.blcontainer'
    _description = 'BLContainers'
    
    name = fields.Char('Container Number')
    ContainerTEU = fields.Char('ContainerTEU')
    ContainerType = fields.Char('ContainerType')
    BLGateOutDate = fields.Char('BLGateOutDate')
    BLEmptyReturnDate = fields.Char('BLEmptyReturnDate')
    shipment_id = fields.Many2one('deepu.sale.tracking', string="Tracking Number",readonly=True,required=True)



class ShipmentEvents(models.Model):
    _name = 'deepu.sale.events'
    
    internal_reference = fields.Char(string="Internal Reference")
    name = fields.Char(string="Event Name")
    
    
class ShipmentStatusHistory(models.Model):
    _name = 'deepu.sale.shipment.history.line'
    
    tracking_id = fields.Many2one('deepu.sale.tracking', string='Tracking No.',readonly=True,required=True)
    event = fields.Many2one('deepu.sale.events',string="Event")
    date = fields.Datetime(string="Date")
    location = fields.Char(string="Location")
    comments = fields.Text(string="Comments")
    
    
class Vessels(models.Model):
    _name = 'deepu.sale.vessels.line'
    tracking_id = fields.Many2one('deepu.sale.tracking', string="Tracking Number",readonly=True,required=True)
    vessel = fields.Char(string="Vessel")	
    Port = fields.Char(string="Port")	
    ArrivalDate = fields.Date(string="ArrivalDate")	
    DepartureDate = fields.Date(string="DepartureDate")	
    voyage= fields.Char(string="Voyage")	
    VesselIMO= fields.Char(string="VesselIMO")	
    departure= fields.Char(string="Departure")	
    delivery = fields.Char(string="Delivery")

class DocLines(models.Model):
    _name = 'deepu.sale.docs.line'
    tracking_id = fields.Many2one('deepu.sale.tracking', string="Tracking Number",readonly=True,required=True)
    file_name = fields.Char("File Name")
    file = fields.Binary(string="file",attachment=True)
    # url = fields.Char(string="URL",compute="compute_url")
    
    @api.depends('file')
    def compute_url(self):
        for rec in self:
            print(rec)
    
    # @api.constrains('file')
    # def _check_file(self):
    #     for rec in self:
    #         print(rec)
    #         print(str(rec.file_name),">>>>>>>>>>>>>>>>>>")
    #         if str(rec.file_name.split(".")[1]) not in  ['pdf','doc','docx','xls','xlsx'] :
    #             raise ValidationError("Cannot upload file different from .pdf,.doc,.docx,xls and xlsx file")
    
class Contact(models.Model):
    _name = 'deepu.sale.contact'
    first_name = fields.Char(string="First Name")
    last_name = fields.Char(string="Last Name")	
    email = fields.Char(string="Email")		
    phone = fields.Char(string="Phone")		
    company = fields.Char(string="Company")		
    message = fields.Text(string="Message")	
    
    
# class ResPartnerModel(models.Model):
#     _name = "res.partner"
#     _description = "Res Partner Customized"

#     @api.model
#     def create(self, vals):
#         print(self,">>>>>>>>>>>>>>>>>>>>>>>>self")
#         print(vals,">>>>>>>>>>>>>>>>>>>>>>>>vals")
#         # Do some business logic, modify vals...
#         ...
#         # Then call super to execute the parent method
#         return super().create(vals)	


class EmailCCTemplate(models.TransientModel):
    _inherit = 'mail.compose.message'
    
    email_cc = fields.Char(string="CC")		
    
    
    
    