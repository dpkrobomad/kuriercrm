from cgitb import reset
from odoo import models, fields, api, SUPERUSER_ID, _
from datetime import datetime, timedelta
from itertools import groupby
import json
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, html_keep_url, is_html_empty
from odoo.tools.misc import format_amount


def _convert_foreign_to_aed(env, from_amount, currency_code, company, date):
    """Convert amount from foreign currency (USD/EUR/GBP) to company currency (AED)."""
    if not from_amount or not currency_code or currency_code == 'AED':
        return from_amount or 0.0
    from_currency = env['res.currency'].sudo().search([('name', '=', currency_code)], limit=1)
    company_currency = company.currency_id
    if not from_currency or not company_currency:
        return from_amount
    return from_currency._convert(from_amount, company_currency, company, date)


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
    currency_selection = fields.Selection([('AED', 'AED'), ('USD', 'USD'), ('EUR', 'EUR') , ('GBP', 'GBP')], string='Currency', default='AED')
    # profit_and_loss_perc = fields.Float('Profit in AED',compute="_profit_calculate",digits=(12,2))

    amount_total_in_selected_currency = fields.Float(
        string='Total in Selected Currency',
        compute='_compute_amount_total_in_selected_currency',
        store=True,
        digits=(16, 2),
        help='Sum of line totals in the currency selected by currency_selection (USD/EUR/GBP).'
    )

    @api.depends('invoice_line_ids.price_unit_foreign', 'invoice_line_ids.quantity', 'currency_selection', 'move_type')
    def _compute_amount_total_in_selected_currency(self):
        for move in self:
            if move.currency_selection in ('USD', 'EUR', 'GBP') and move.move_type == 'in_invoice':
                total = move._get_total_in_selected_currency()
                move.amount_total_in_selected_currency = total
            else:
                move.amount_total_in_selected_currency = 0.0

    def _get_total_in_selected_currency(self):
        """Sum of price_unit_foreign * quantity from invoice lines. Reads from DB when needed."""
        self.ensure_one()
        if self.currency_selection not in ('USD', 'EUR', 'GBP') or self.move_type != 'in_invoice':
            return 0.0

        def _sum_from_orm():
            total = 0.0
            for line in self.invoice_line_ids:
                if not line.display_type and line.price_unit_foreign:
                    total += (line.price_unit_foreign or 0) * (line.quantity or 0.0)
            return total

        # Use ORM for new/unsaved records (onchange, NewId) - psycopg2 can't adapt NewId
        if isinstance(self.id, models.NewId):
            return _sum_from_orm()
        # SQL read for persisted records (avoids cache issues after direct SQL update)
        try:
            self.env.cr.execute("""
                SELECT COALESCE(SUM(
                    COALESCE(aml.price_unit_foreign, 0) * COALESCE(aml.quantity, 0)
                ), 0)
                FROM account_move_line aml
                WHERE aml.move_id = %s
                  AND (aml.exclude_from_invoice_tab IS NULL OR aml.exclude_from_invoice_tab = false)
                  AND (aml.display_type IS NULL OR aml.display_type NOT IN ('line_section', 'line_note'))
            """, (self.id,))
            return float(self.env.cr.fetchone()[0])
        except Exception:
            return _sum_from_orm()

    total_foreign = fields.Char(
        string='Total Foreign',
        compute='_compute_total_foreign',
        store=True,
        help='Total in selected foreign currency with symbol (e.g. $2,000.00)'
    )

    def action_recompute_foreign_totals(self):
        """Button: force recompute stored totals from line price_unit_foreign."""
        self._recompute_foreign_totals()
        return {'type': 'ir.actions.act_window_close'}

    def _recompute_foreign_totals(self):
        """Force recompute and persist amount_total_in_selected_currency and total_foreign.
        Use for fixing stored totals when price_unit_foreign was saved via SQL or for existing records."""
        for move in self:
            if move.currency_selection not in ('USD', 'EUR', 'GBP') or move.move_type != 'in_invoice':
                continue
            total = move._get_total_in_selected_currency()
            currency = self.env['res.currency'].sudo().search(
                [('name', '=', move.currency_selection)], limit=1
            )
            total_foreign = format_amount(move.env, total, currency) if currency and total else ''
            move.write({
                'amount_total_in_selected_currency': total,
                'total_foreign': total_foreign,
            })

    @api.depends('amount_total_in_selected_currency', 'currency_selection', 'move_type')
    def _compute_total_foreign(self):
        for move in self:
            if (move.move_type == 'in_invoice'
                    and move.currency_selection in ('USD', 'EUR', 'GBP')
                    and move.amount_total_in_selected_currency):
                currency = self.env['res.currency'].sudo().search(
                    [('name', '=', move.currency_selection)], limit=1
                )
                if currency:
                    move.total_foreign = format_amount(
                        move.env, move.amount_total_in_selected_currency, currency
                    )
                else:
                    move.total_foreign = ''
            else:
                move.total_foreign = ''

    show_sib_account = fields.Boolean('Show SIB Account in Invoice',default=False)
    
    product_line_ids = fields.One2many('deepu.account.order.line','account_order_id')
    container_line_ids = fields.One2many('deepu.account.container.line','account_container_order_id')
    @api.depends('tax_totals_json')
    def _currency_convert(self):
        curr_obj = self.env['res.currency']
        usd_obj = curr_obj.sudo().search([('name', '=', 'USD')], limit=1)
        eur_obj = curr_obj.sudo().search([('name', '=', 'EUR')], limit=1)
        gbp_obj = curr_obj.sudo().search([('name', '=', 'GBP')], limit=1)
        for rec in self:
            if rec.amount_total > 0 and usd_obj and eur_obj and gbp_obj:
                rec.usd = rec.amount_total * usd_obj.rate
                rec.eur = rec.amount_total * eur_obj.rate
                rec.gbp = rec.amount_total * gbp_obj.rate
            else:
                rec.usd = None
                rec.eur = None
                rec.gbp = None
            
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

    def write(self, vals):
        """Capture price_unit_foreign and explicitly persist after save (autocomplete may drop it)."""
        foreign_values = {}
        # Capture from invoice_line_ids (client form) or line_ids (autocomplete internal write)
        for key in ('invoice_line_ids', 'line_ids'):
            cmds = vals.get(key) or []
            for cmd in cmds:
                if len(cmd) >= 3 and cmd[0] == 1:  # UPDATE
                    line_vals = cmd[2] if isinstance(cmd[2], dict) else {}
                    if 'price_unit_foreign' in line_vals:
                        foreign_values[cmd[1]] = line_vals['price_unit_foreign']
        result = super().write(vals)
        if foreign_values and result:
            # Use direct SQL to guarantee persistence (ORM/autocomplete may filter our field)
            for line_id, value in foreign_values.items():
                line = self.env['account.move.line'].browse(line_id).exists()
                if line and line.move_id in self:
                    # Direct SQL update to bypass any ORM filtering
                    self.env.cr.execute(
                        "UPDATE account_move_line SET price_unit_foreign = %s WHERE id = %s",
                        (float(value or 0), line_id)
                    )
            # Recompute and persist stored totals (SQL read in _get_total_in_selected_currency avoids cache)
            affected = self.filtered(
                lambda m: m.currency_selection in ('USD', 'EUR', 'GBP') and m.move_type == 'in_invoice'
            )
            if affected:
                affected._recompute_foreign_totals()
        return result

    def _move_autocomplete_invoice_lines_create(self, vals_list):
        """Apply price_unit from price_unit_foreign before autocomplete for vendor bills."""
        for vals in vals_list:
            if vals.get('currency_selection') in ('USD', 'EUR', 'GBP') and vals.get('move_type') == 'in_invoice':
                company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
                date = vals.get('invoice_date') or vals.get('date') or fields.Date.context_today(self)
                for key in ('invoice_line_ids', 'line_ids'):
                    for cmd in vals.get(key, []) or []:
                        if len(cmd) >= 3 and cmd[0] == 0 and isinstance(cmd[2], dict):  # (0, 0, line_vals)
                            line_vals = cmd[2]
                            if line_vals.get('price_unit_foreign') is not None:
                                line_vals['price_unit'] = _convert_foreign_to_aed(
                                    self.env, line_vals['price_unit_foreign'], vals['currency_selection'], company, date
                                )
        return super()._move_autocomplete_invoice_lines_create(vals_list)

    def _move_autocomplete_invoice_lines_values(self):
        """Preserve price_unit_foreign in values - inject from context (form may not include it in _convert_to_write)."""
        values = super()._move_autocomplete_invoice_lines_values()
        # Use pending foreign values from write (passed via context) - form payload may be dropped by autocomplete
        pending = self.env.context.get('_price_unit_foreign_pending') or {}
        if not pending or self.currency_selection not in ('USD', 'EUR', 'GBP') or self.move_type != 'in_invoice':
            return values
        line_ids = values.get('line_ids') or []
        for cmd in line_ids:
            if len(cmd) >= 3 and cmd[0] == 1 and isinstance(cmd[2], dict):
                if cmd[1] in pending:
                    cmd[2]['price_unit_foreign'] = pending[cmd[1]]
        return values

    def _move_autocomplete_invoice_lines_write(self, vals):
        """Ensure price_unit_foreign is applied and preserved through autocomplete."""
        if vals.get('invoice_line_ids') and not vals.get('line_ids') and self:
            move = self[0]
            pending_foreign = {}
            if move.currency_selection in ('USD', 'EUR', 'GBP') and move.move_type == 'in_invoice':
                for cmd in vals['invoice_line_ids']:
                    if len(cmd) >= 3 and cmd[0] == 1:
                        line_vals = cmd[2]
                        if isinstance(line_vals, dict) and 'price_unit_foreign' in line_vals:
                            line_id = cmd[1]
                            val = line_vals['price_unit_foreign']
                            pending_foreign[line_id] = float(val) if val is not None else 0.0
                            company = move.company_id
                            date = move.invoice_date or fields.Date.context_today(self)
                            line_vals['price_unit'] = _convert_foreign_to_aed(
                                self.env, val, move.currency_selection, company, date
                            )
            # Pass to _move_autocomplete_invoice_lines_values via context
            return super(AccountMove, self.with_context(_price_unit_foreign_pending=pending_foreign))._move_autocomplete_invoice_lines_write(vals)
        return super()._move_autocomplete_invoice_lines_write(vals)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_unit_foreign = fields.Float(
        string='Price (Foreign)',
        digits='Product Price',
        help='Enter price in the selected currency (USD/EUR/GBP). It will be converted to AED.'
    )

    @api.onchange('price_unit_foreign')
    def _onchange_price_unit_foreign(self):
        """Convert foreign price to AED and update price_unit when currency_selection is USD/EUR/GBP."""
        if not self.price_unit_foreign or not self.move_id:
            return
        move = self.move_id
        if move.currency_selection not in ('USD', 'EUR', 'GBP') or move.move_type != 'in_invoice':
            return
        company = move.company_id
        date = move.invoice_date or fields.Date.context_today(self)
        self.price_unit = _convert_foreign_to_aed(
            self.env, self.price_unit_foreign, move.currency_selection, company, date
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move = self._get_move_for_foreign_conversion(vals, records=None)
            self._apply_foreign_to_price_unit(vals, move)
        return super().create(vals_list)

    def write(self, vals):
        move = self._get_move_for_foreign_conversion(vals, records=self) if self else None
        self._apply_foreign_to_price_unit(vals, move)
        return super().write(vals)

    def _get_move_for_foreign_conversion(self, vals, records=None):
        """Get the account.move for currency conversion from vals or records."""
        if 'price_unit_foreign' not in vals:
            return None
        if records:
            move = records[0].move_id
        elif vals.get('move_id'):
            move = self.env['account.move'].browse(vals['move_id'])
        else:
            move = self.env['account.move'].browse(self.env.context.get('default_move_id'))
        if not move or move.currency_selection not in ('USD', 'EUR', 'GBP') or move.move_type != 'in_invoice':
            return None
        return move

    def _apply_foreign_to_price_unit(self, vals, move):
        """When price_unit_foreign is set, convert and set price_unit in vals."""
        if 'price_unit_foreign' not in vals or not move:
            return
        foreign = vals.get('price_unit_foreign')
        if foreign is None:
            return
        company = move.company_id
        date = move.invoice_date or fields.Date.context_today(self)
        vals['price_unit'] = _convert_foreign_to_aed(
            self.env, foreign, move.currency_selection, company, date
        )


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
    
    
