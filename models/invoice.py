from cgitb import reset
from odoo import models, fields, api,SUPERUSER_ID, _
from datetime import datetime, timedelta
from itertools import groupby
import json
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, html_keep_url, is_html_empty

class AccountMove(models.Model):
    _inherit = 'account.move'
    vendor_bill_ref = fields.Many2many('account.move','vendorbills_refs','rel_1invref','rel2_vendorbillref',string='Vendor Bills')
    # invoice_ref = fields.Many2one('account.move')
    ts = fields.Char('Shipemnt Type')
    st = fields.Char('Shipemnt Terms')
    # test = fields.Char('test',compute="_onchange_SaleId")
    # contact = fields.Many2one('res.partner',string='Contact Person')
    contact_person = fields.Char('Contact Person',compute='_compute_contact')
    po_number = fields.Char('PO Number')
    typeOfShipment = fields.Many2one('site_settings.shipment_type',string="Type Of Shipment")
    shipmentTerms = fields.Many2one('site_settings.terms_of_shipment',string="Shipment Terms")
    portOfLoading = fields.Char('Port of Loading',store=True)
    portOfDestination = fields.Char('Port of Destination',store=True)
    originCountry = fields.Char('Origin Country',store=True)
    destinationCountry = fields.Char('Destination Country',store=True)
    consignee = fields.Char(string="Consignee")
    shipper = fields.Char(string="Shipper")
    no_of_pcs = fields.Integer(string="Pcs")
    totalChargableWeight = fields.Float('Total CW/CBM',compute="_compute_TotalChargable", store=True)
    cargoWeight = fields.Char('Cargo Weight')
    commodityType = fields.Char('Commodity Type')
    tracking_id = fields.Many2one('deepu.sale.tracking',string='Tracking Ref.')
    sale_id = fields.Many2one('sale.order',string='Quotation Ref.')
    oceanBillOfLading = fields.Char('Bill Of Lading')
    awb = fields.Char('Air Way Bill')
    billOfLading = fields.Char('Truck Way Bill')
    container_number = fields.Char(string="Container Number")
    usd = fields.Float(string="Amount in USD",compute="_currency_convert",digits=(12,2))
    eur = fields.Float(string="Amount in EUR",compute="_currency_convert",digits=(12,2))
    gbp = fields.Float(string="Amount in GBP",compute="_currency_convert",digits=(12,2))
    
    profit_and_loss = fields.Float('Profit in AED',compute="_profit_calculate")
    
    is_loss = fields.Boolean('Is Loss',default=False)
    custom_terms = fields.Html(string='Terms and Conditions', widget='html', help="Terms and Conditions", placeholder="Terms and Conditions...")
    exchange_rates = fields.Char('Exchange Rates')
    # profit_and_loss_perc = fields.Float('Profit in AED',compute="_profit_calculate",digits=(12,2))
    
    show_sib_account = fields.Boolean('Show SIB Account in Invoice',default=False)
    product_line_ids = fields.One2many('deepu.account.order.line','account_order_id')
    container_line_ids = fields.One2many('deepu.account.container.line','account_container_order_id')
    @api.depends('tax_totals_json')
    def _currency_convert(self):
        curr_obj = self.env['res.currency']
        usd_obj = curr_obj.sudo().search([('name','=','USD')])
        eur_obj = curr_obj.sudo().search([('name','=','EUR')])
        gbp_obj = curr_obj.sudo().search([('name','=','GBP')])
        
        print(usd_obj,'^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
        if self.amount_total >0:
            self.usd = self.amount_total*usd_obj.rate
            self.eur = self.amount_total*eur_obj.rate
            self.gbp = self.amount_total*gbp_obj.rate
        else:
            self.usd = None
            self.eur = None
            self.gbp = None
            
    # @api.depends('vendor_bill_ref')
    def _profit_calculate(self):
        for rec in self:
            rec.profit_and_loss = 0
            bill_total = 0
            for bill in rec.vendor_bill_ref:
                bill_total += float(bill.amount_total)
                print(bill,">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>bill")
            print(rec,">>>>>>>>>>>>>>>&&&&&&&&&&&&")
            profit = 0.0
            profit = rec.amount_total - bill_total
            rec.profit_and_loss = profit
            
            # if rec.amount_total > bill_total:
            # rec.profit_and_loss = 0   
            if profit < 0 :
                rec.is_loss = True
            else:
                rec.is_loss = False
            #     rec.profit_and_loss = bill_total - rec.amount_total
            # elif rec.amount_total == bill_total:
            #     rec.profit_and_loss = 0.0
            
            
        
            
    @api.depends('partner_id')
    def _compute_contact(self):
        print(">>>>>>>>>>>")
        for rec in self:
            if rec.partner_id.contact_person !=None and rec.partner_id.contact_person!='':
                rec.contact_person = rec.partner_id.contact_person
            else:
                rec.contact_person = ''
                
            if rec.sale_id:
                rec.portOfLoading = rec.sale_id.portOfLoading
                rec.totalChargableWeight = rec.sale_id.totalChargableWeight
                if rec.oceanBillOfLading:
                    rec.sale_id.tracking_id.oceanBillOfLading=rec.oceanBillOfLading
                if rec.awb:
                    rec.sale_id.tracking_id.awb=rec.awb
                if rec.billOfLading:
                    rec.sale_id.tracking_id.billOfLading=rec.billOfLading
                if rec.sale_id.container_number:
                    rec.container_number=rec.sale_id.container_number
                    

                
    
    @api.onchange('typeOfShipment')
    def _onchange_typeOfShipment(self):
        if self.typeOfShipment:
            self.ts = self.typeOfShipment.name
            
    @api.onchange('shipmentTerms')
    def _onchange_shipmentTerms(self):
        if self.shipmentTerms:
            self.st = self.shipmentTerms.name

    @api.depends('product_line_ids')
    def _compute_TotalChargable(self):
        for rec in self:
            print(rec.product_line_ids,'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            vals = 0.0
            count = 0 
            if rec.ts!='FCL':
                for product in rec.product_line_ids:
                    count +=1
                    if product.volume :
                        print(product,product.volume,product,'$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')
                        vals += (product.chargableWeight)
                        print(vals,'**************************************')
                rec.totalChargableWeight = vals
            else:
                rec.totalChargableWeight = None
                
    @api.onchange('sale_id')
    def _onchange_SaleId(self):
        for rec in self:
            rec.ensure_one()
            print(rec.sale_id,rec.sale_id.partner_id,rec.sale_id.originAddress, "&&&&&&&&&&&&&&&&>>>>>>>>sale id changed")

            try:
                if rec.move_type == "out_invoice":
                    rec.partner_id = rec.sale_id.partner_id
                print("changing other fields >>>>>>>>>>>>>>>>>>>>>>>>")
                # rec.sale_id = rec.tracking_id.sale_order_id
                rec.shipper = rec.sale_id.originAddress
                rec.consignee = rec.sale_id.destinationAddress
                rec.po_number = rec.sale_id.po_number
                rec.commodityType = rec.sale_id.commodityType
                rec.portOfLoading = rec.sale_id.portOfLoading
                rec.portOfDestination = rec.sale_id.portOfDestination
                rec.originCountry = rec.sale_id.originCountry
                rec.destinationCountry = rec.sale_id.destinationCountry
                rec.no_of_pcs = rec.sale_id.no_of_pcs
                rec.typeOfShipment = rec.sale_id.typeOfShipment
                rec.shipmentTerms = rec.sale_id.shipmentTerms
                rec.tracking_id = rec.sale_id.tracking_id
                
                
                print("changing other fields",rec.tracking_id,rec.shipmentTerms ,">>>>>>>>>>>>>>>>>>>>>>>>")

            except Exception as e:
                print(e, ">>>>>>>>>>>>>>>>>exception")
                rec.partner_id = ''
                rec.shipper = ''
                rec.consignee = ''
                rec.po_number = ''
                rec.commodityType = ''
                rec.portOfLoading = ''
                rec.portOfDestination = ''
                rec.originCountry = ''
                rec.destinationCountry = ''
                rec.no_of_pcs = ''
                rec.typeOfShipment = ''
                rec.shipmentTerms = ''
                rec.tracking_id = ''
    

    @api.depends('sale_id')
    def _compute_on_invoice_load(self):
        for rec in self:
            print("Invoice loaded!", rec)
    # @api.onchange('tracking_id')
    # def _onchange_TrackingId(self):
    #     print(self,"&&&&&&&&&&&&&&&&")
        

    #     for rec in self:
    #         rec.sale_id = rec.tracking_id.sale_order_id
            
#################################################################### NEW CHANGE 9/10/23 start
            
#     @api.onchange('sale_id')
#     def _onchange_SaleId(self):
#         print(self,"&&&&&&&&&&&&&&&&>>>>>>>>sale id changed")
# #################################################################### NEW CHANGE 9/10/23 end
#         try:
#             for rec in self:
#                 print(rec,rec.partner_id,rec.sale_id,">>>>>>>")
#                 if rec.move_type == "out_invoice":
#                     rec.partner_id = self.sale_id.partner_id
#                 rec.sale_id = self.tracking_id.sale_order_id
#                 # rec.partner_id = self.sale_id.partner_id.id
#                 rec.shipper = rec.sale_id.originAddress
#                 rec.consignee = rec.sale_id.destinationAddress
#                 rec.po_number = rec.sale_id.po_number
#                 rec.commodityType = rec.sale_id.commodityType
#                 rec.portOfLoading = rec.sale_id.portOfLoading
#                 rec.portOfDestination = rec.sale_id.portOfDestination
#                 rec.originCountry = rec.sale_id.originCountry
#                 rec.destinationCountry = rec.sale_id.destinationCountry
#                 rec.no_of_pcs = rec.sale_id.no_of_pcs
#                 rec.typeOfShipment = rec.sale_id.typeOfShipment
#                 rec.shipmentTerms = rec.sale_id.shipmentTerms
#                 rec.tracking_id = rec.sale_id.tracking_id
#         except Exception as e:
#             print(e,">>>>>>>>>>>>>>>>>exception")
#             for rec in self:
#                 rec.partner_id = ''
#                 rec.shipper = ''
#                 rec.consignee = ''
#                 rec.po_number = ''
#                 rec.commodityType = ''
#                 rec.portOfLoading = ''
#                 rec.portOfDestination = ''
#                 rec.originCountry = ''
#                 rec.destinationCountry = ''
#                 rec.no_of_pcs = ''
#                 rec.typeOfShipment = ''
#                 rec.shipmentTerms = ''
#                 rec.tracking_id = ''
            
            
            
    # @api.onchange('sale_id')
    # def _onchange_SaleId(self):
    #     print(self,"&&&&&&&&&&&&&&&&")
    #     try:
    #         for rec in self:
    #             rec.partner_id = self.sale_id.partner_id.id
    #             rec.shipper = rec.sale_id.originAddress
    #             rec.consignee = rec.sale_id.destinationAddress
    #             rec.po_number = rec.sale_id.po_number
    #             rec.commodityType = rec.sale_id.commodityType
    #             rec.portOfLoading = rec.sale_id.portOfLoading
    #             rec.portOfDestination = rec.sale_id.portOfDestination
    #             rec.originCountry = rec.sale_id.originCountry
    #             rec.destinationCountry = rec.sale_id.destinationCountry
    #             rec.no_of_pcs = rec.sale_id.no_of_pcs
    #             rec.typeOfShipment = rec.sale_id.typeOfShipment
    #             rec.shipmentTerms = rec.sale_id.shipmentTerms
    #             rec.tracking_id = rec.sale_id.tracking_id
                
    #     except Exception as e:
    #         print(e)
    #         for rec in self:
    #             rec.partner_id = ''
    #             rec.shipper = ''
    #             rec.consignee = ''
    #             rec.po_number = ''
    #             rec.commodityType = ''
    #             rec.portOfLoading = ''
    #             rec.portOfDestination = ''
    #             rec.originCountry = ''
    #             rec.destinationCountry = ''
    #             rec.no_of_pcs = ''
    #             rec.typeOfShipment = ''
    #             rec.shipmentTerms = ''
    #             rec.tracking_id = ''
    # @api.model   
    # def write(self,values):
    #     # Call super to execute the original write method
    #     result = super(AccountMove, self).write(values)
    #     if self.sale_id:
    #         try:
    #             if self.move_type == "out_invoice":
    #                 sales = self.env['sale.order'].search([('id', '=', self.sale_id.id)])
    #                 for sale in sales:
    #                     print(sale.order_line.invoice_lines,"move ids ")
    #                     # sale.write({'invoice_ids': [(4,self.id)]})
    #                     # print(sale.invoice_ids)

                
          
    #         except Exception as e :
    #             print(e)

    #     # Add your custom logic here
    #     # ...

    #     return result    
            
    
    @api.model
    def create(self, vals):
        
        result = super(AccountMove, self).create(vals)
        
        
        print("___________")
        print("___________")
        print("___________")
        print("___________",result)
        product_items = []
        container_items = []
        if result.sale_id:
            print(result.move_type)
            # try:
            #     if result.move_type == "out_invoice":
            #         result.sale_id.invoice_ids |= result
            # except Exception as e :
            #     print(e)
            if result.sale_id.product_line_ids:
                for line in result.sale_id.product_line_ids:
                    product_items.append((0, 0, {'account_order_id':result.id,
                                                 'length': line.length,
                                                 'width': line.width,
                                                 'height': line.height,
                                                 'totalpcs': line.totalpcs,
                                                 'grossWeight': line.grossWeight,
                                                 'volume': line.volume,
                                                 }))
            if result.sale_id.container_line_ids:
                for cline in result.sale_id.container_line_ids:
                    container_items.append((0, 0, {'account_container_order_id':result.id,
                                                 'typeOfContainer': cline.typeOfContainer,
                                                 'noOfContainers': cline.noOfContainers,
                                                 'temperature': cline.temperature,
                                                 }))
        result.sudo().update({'product_line_ids': product_items})

        
        return result

class AccountProductOrder(models.Model):
    _name = 'deepu.account.order.line'
    account_order_id = fields.Many2one('account.move')
    length = fields.Float('Length')
    width = fields.Float('Width')
    height = fields.Float('Height')
    totalpcs = fields.Integer('Total pcs')
    grossWeight = fields.Float('Gross Weight')
    volume = fields.Float(string='Volume',compute='_compute_weight')
    chargableWeight = fields.Float(string='Chargable Weight',compute='_compute_chargable')
    
    
    @api.depends('length','width','height','totalpcs')
    def _compute_weight(self):
        for item in self:
            print(item,'self *************************************')
            if item.account_order_id.ts=='Air Freight' and item.length  and item.width  and item.height  and item.totalpcs    :
                print(item.account_order_id.ts,item.width,item.totalpcs,item.length,item.height)
                val = (item.length)*(item.width)*(item.height)*(item.totalpcs)
                print(val)
                item.volume = round((val/6000),2)
            elif item.account_order_id.ts=='LCL' and item.length  and item.width  and item.height  and item.totalpcs    :
                print(item.account_order_id.ts,item.width,item.totalpcs,item.length,item.height)
                val = (item.length)*(item.width)*(item.height)*(item.totalpcs)
                print(val)
                item.volume = round((val/1000000),2)
                item.volume = ''
        
            elif item.account_order_id.ts=='Courier Service' and item.length  and item.width  and item.height  and item.totalpcs   :
                val = (item.length)*(item.width)*(item.height)*(item.totalpcs)
                print(val)
                item.volume = round((val/5000),2)
            else:
                item.volume =None
            
    @api.depends('grossWeight','volume')
    def _compute_chargable(self):
        for item in self:
            try:
                if item.account_order_id.ts=='Air Freight' or item.account_order_id.ts=='Courier Service' or item.account_order_id.ts=='Road Freight' and item.volume is not None and item.grossWeight is not None:
                    if (item.grossWeight) > (item.volume):
                        item.chargableWeight = item.grossWeight
                    else:
                            item.chargableWeight = item.volume
                
                elif item.account_order_id.ts=='LCL' and item.volume is not None and item.grossWeight is not None:
                    gwcbm = (item.grossWeight)
                    print(gwcbm)
                    gwcbm = gwcbm/1000
                    gwcbm = round(gwcbm,2)
                    if gwcbm > (item.volume):
                        item.chargableWeight = gwcbm
                    else:
                        item.chargableWeight = item.volume
                else:
                    item.chargableWeight = None
                
            except Exception as e:
                print(e,'errorrrrrrr>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
            
   
class AccountContainers(models.Model):
    _name = 'deepu.account.container.line'
    
    account_container_order_id = fields.Many2one('account.move')
    typeOfContainer = fields.Selection([('1', '20 Ft'), ('2', '40 Ft'), ('3', '40 Ft HC'),('4', '20 Ft RF'),('5', '40 Ft RF')], string='Type of Container')
    noOfContainers = fields.Char('No. of Containers')
    temperature = fields.Char('Temperature °C')


class CustomersCustom(models.Model):
    _inherit = 'res.partner'
    
    contact_person = fields.Char('Contact Person')
    
# class CustomersCompanyCustom(models.Model):
#     _inherit = 'res.company'
    
#     contact_person = fields.Char('Contact Person')
    
    
