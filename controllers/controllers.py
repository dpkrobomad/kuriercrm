# -*- coding: utf-8 -*-
from odoo import http
import json
from odoo.http import request
import ast,os,io,base64,mimetypes
from cryptography.fernet import Fernet
from datetime import datetime, timedelta,date
from collections import Counter
from odoo import fields
import re
import logging
_logger = logging.getLogger(__name__)
# from geopy.geocoders import Nominatim
from mapbox import Geocoder
from dateutil.relativedelta import relativedelta
ENCRYPT_KEY = "z6RQzmOUM_VsSztO-BV_BACglvrnkn5COO8RWTkXqik="

class DeepuSaleController(http.Controller): 
    def none_to_empty_str(items):
        return {k: v if v is not None else '' for k, v in items}
    
    def get_first_string(self,input_string):
        # Define the pattern to split the string using , | .
        pattern = r'[,.|:]'

        # Use re.split() to split the string based on the pattern
        parts = re.split(pattern, input_string)

        # Get the first part of the split string (i.e., the string before the first , | .)
        first_string = parts[0]
        first_string=first_string.lower().capitalize()
        return first_string
    

# Replace 'YOUR_MAPBOX_ACCESS_TOKEN' with your actual Mapbox access token
    

    def get_coordinates(self,place_name):
        mapbox_access_token = 'pk.eyJ1Ijoia3VyaWVydm9nZWwiLCJhIjoiY2xvY2prN25uMTdvbDJpcWI2ZDkxNXRwcyJ9.cg2D629kyfneN-t7TLwkWw'
        geocoder = Geocoder(access_token=mapbox_access_token)
        response = geocoder.forward(place_name)
        features = response.json()['features']

        if features:
            # Extract coordinates from the first result
            coordinates = features[0]['center']
            return coordinates
        else:
            return None
    
    # def get_coordinates(self,address_or_list):
    
    #     geolocator = Nominatim(user_agent="DjangoApp")

    #     if isinstance(address_or_list, list):
    #         if len(address_or_list) == 2:
    #             return address_or_list
    #         else:
    #             return None

    #     location = geolocator.geocode(address_or_list)

    #     if location:
    #         return [location.longitude, location.latitude]
    #     else:
    #         return None
    
    def convert_time(self,t):
        if t:
        # ATA_datetime = datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
            formatted_ATA = t.strftime('%d %b %Y %I:%M %p')
            return formatted_ATA
        else:
            return "Not Available"
    @http.route('/get/kuriervogel/order/',type='http',csrf=False,auth="public")
    def getSaleOrder(self,**post):
 
        print(post)
        name = post['name']
        email = post['email']
        phone = post['phone']
        originCountry = post['originCountry']
        destinationCountry = post['destinationCountry']
        company = post['company']
        ts = request.env['site_settings.shipment_type']
        tsid = ts.sudo().search([('name','=',post['typeOfShipment'])])
        typeOfShipment = tsid.id
        st = request.env['site_settings.terms_of_shipment']
        stid = st.sudo().search([('name','=',post['shipmentTerms'])])
        shipmentTerms = stid.id
        cargoReadyDate = post['cargoReadyDate'] if post['cargoReadyDate'] else None
        commodityType = post['commodityType']
        portOfLoading = post['portOfLoading']
        portOfDestination = post['portOfDestination']
        originZip = post['originZip']
        originAddress = post['originAddress']
        destinationZip = post['destinationZip']
        destinationAddress = post['destinationAddress']
        sitems = post['seaitems']
        seaItems = ast.literal_eval(sitems)
        cargoWeight = post['cargoWeight']
        items = post['items']
        items= items.replace('\'','')
        print(items)
        items_list = ast.literal_eval(items)
        company_obj = request.env['res.partner']
        # user_obj = request.env['res.users']
        sale_obj = request.env['sale.order']
        company_fetched = company_obj.sudo().search(['&',('parent_id','=',None),('email','=',email.strip())])
        if company_fetched:
            print(company_fetched.name,'')
        else:
            cvals = {
                'name' : company,
                'email': email,
                'phone':phone,
                'company_type':'company'
            }
            company_fetched = company_obj.sudo().create(cvals)
            
        
        salesvals = {
        'ts':post['typeOfShipment'],
        'st':post['shipmentTerms'],
        'state':'draft',
        # 'contact':company_fetched.id,
        'partner_id' : company_fetched.id,
        'typeOfShipment' : typeOfShipment,
        'shipmentTerms' : shipmentTerms,
        'cargoReadyDate' : cargoReadyDate,
        'originCountry' : originCountry,
        'destinationCountry' : destinationCountry,
        'commodityType' : commodityType,
        'originZip' : originZip,
        'originAddress' : originAddress,
        'destinationZip' : destinationZip,
        'destinationAddress' : destinationAddress,
        'portOfLoading':portOfLoading,
        'portOfDestination':portOfDestination,
        'cargoWeight' : cargoWeight,
        
        }
        print(salesvals,">>>>>>>>>>>>>>>>>>>>sales vals")
        sale_order = sale_obj.sudo().create(salesvals)
        
        itemTotalWeight = 0
        itemTotalGW = 0 
        if post['typeOfShipment']=='Air Freight':
            print('air')
            for item in items_list:
                volume = float(item['volume'])
                gW = float(item['grossWeight'])
                itemTotalWeight+= volume
                itemTotalGW += gW
                cGW = gW/167
                print(cGW,'CGWWWWWWWWWWWWWWWWWW')
                chargableWeight = volume if volume > cGW else cGW 
                cargo_obj = request.env['deepu.sale.order.line']
                cargoVals = {
                    'sale_order_id':sale_order.id,
                    'length':item['length'],
                    'width':item['width'],
                    'height':item['height'],
                    'totalpcs':item['totalpcs'],
                    'grossWeight':item['grossWeight'],
                }
                newCargo = cargo_obj.sudo().create(cargoVals)
                print(newCargo,'>>>>>>>>>>>>>>>>>>>>>>>>>')

           
        elif post['typeOfShipment']=='Sea Freight':
            print('sea')
            for item in seaItems:
                cargo_obj = request.env['deepu.sale.container.line']
                cargoVals = {
                    'sale_container_order_id':sale_order.id,
                    'typeOfContainer':item['typeOfContainer'],
                    'noOfContainers':int(item['noOfContainers']),
                }
                newCargo = cargo_obj.sudo().create(cargoVals)
                print(newCargo,'>>>>>>>>>>>>>>>>>>>>>>>>>')
            
        elif post['typeOfShipment']=='LCL':
            print('LCL')
            for item in items_list:
                itemTotalWeight+= float(item['volume'])
                itemTotalGW += float(item['grossWeight'])
                chargableWeight = 0 
                cargo_obj = request.env['deepu.sale.order.line']
                cargoVals = {
                    'sale_order_id':sale_order.id,
                    'length':item['length'],
                    'width':item['width'],
                    'height':item['height'],
                    'totalpcs':item['totalpcs'],
                    'grossWeight':item['grossWeight'],
                }
                newCargo = cargo_obj.sudo().create(cargoVals)
        elif post['typeOfShipment']=='Road Freight':
            print('Road Freight')
            for item in items_list:
                itemTotalWeight+= float(item['volume'])
                itemTotalGW += float(item['grossWeight'])
                cargo_obj = request.env['deepu.sale.order.line']
                cargoVals = {
                    'sale_order_id':sale_order.id,
                    'length':item['length'],
                    'width':item['width'],
                    'height':item['height'],
                    'totalpcs':item['totalpcs'],
                    'grossWeight':item['grossWeight'],
                }
                newCargo = cargo_obj.sudo().create(cargoVals)
        elif post['typeOfShipment']=='Courier Service':
            print('Courier Service')
            for item in items_list:
                itemTotalWeight+= float(item['volume'])
                itemTotalGW += float(item['grossWeight'])
                cargo_obj = request.env['deepu.sale.order.line']
                cargoVals = {
                'sale_order_id':sale_order.id,
                'length':item['length'],
                'width':item['width'],
                'height':item['height'],
                'totalpcs':item['totalpcs'],
                'grossWeight':item['grossWeight'],
                }
                newCargo = cargo_obj.sudo().create(cargoVals)
        
        print(itemTotalWeight, itemTotalGW,'****************************************************************')
        print('>>>>>>>>>>>>>>>>>>>>')


    @http.route('/register/user/',methods=["POST"],type="json",csrf=False,auth="public")
    def postUser(self,**post):
        print('>>>>>>>>>>>>>>>>>>>>>>>>')
        data = json.loads(request.httprequest.data)
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        company = data.get('company')
        password = data.get('password')
        print(post,data)
        company_obj = request.env['res.partner']
        # user_obj = request.env['res.users']
        company_fetched = company_obj.sudo().search(['&',('parent_id','=',None),('email','=',email.strip())])
        print(company_fetched,"Company Fetched")
        if company_fetched:
            print(company_fetched.name,'>>>>>>>>>>>>>company')
        else:
            cvals = {
                'name' : company,
                'email': email,
                'phone':phone,
                'company_type':'company',
                'contact_person':name
            }
            company_fetched = company_obj.sudo().create(cvals)
        
        # user = user_obj.sudo().search([('email','=',email.strip())])
        # print('Searching partner',user,user.partner_id.id,user.partner_id.name)
        # if user:
        #     print(user.partner_id.name)
        # else:
        #     vals = {
        #     'name' : name,
        #     'email': email,
        #     'phone':phone,
        #     'login':email,
        #     'password' : password,
        #     'groups_id': [(6, 0,[request.env.ref('base.group_portal').id])]
        #     }
        #     user = user_obj.sudo().create(vals)
        #     print('new partner created',user.name)
        #     print("groups1 : ", user.sudo().groups_id)
            # user.sudo().groups_id = [request.env.ref('base.group_portal').id]
            # print("groups2 : ", user.sudo().groups_id)
        # partner = request.env['res.partner'].sudo().search([('id','=',user.partner_id.id)])
        # partner.parent_id = company_fetched.id
        if company_fetched:
        
            return {"sussess":True,"status":200,"partner_id":company_fetched.id}
        else:
            return {"sussess":False,"status":404}
        
        
    @http.route('/get/tracking/',methods=["POST"],type='json',csrf=False,auth="public")
    def getTrackings(self,**post):
        data = json.loads(request.httprequest.data)
        pid = int(data.get('pid'))
        print(data)
        user_obj = request.env['res.partner']
        track_obj = request.env['deepu.sale.tracking']
        user = user_obj.sudo().search([('id','=',pid)])
        trackings = list()
        if user :
            tracking = track_obj.sudo().search([('sale_order_id.partner_id','=',pid)],order="id desc")
            print(tracking)
            for t in tracking:
                try:
                    shippers = t.shipper.split(",")
                    shipper = shippers[0]
                    consignees=t.consignee.split(",")
                    consignee = consignees[0]
                except:
                    shipper = t.shipper
                    consignee = t.consignee
                    
                vals = {"tracking_id":t.id,
                        "tracking_number":t.name,
                        "customer":t.sale_order_id.partner_id.name,
                        "typeOfShipment":t.shipmentType,
                        "shipmentTerms":t.shipmentTerms,
                        "originCountry":t.sale_order_id.originCountry,
                        "destinationCountry":t.sale_order_id.destinationCountry,
                        "portOfLoading":t.sale_order_id.portOfLoading,
                        "portOfDestination":t.sale_order_id.portOfDestination,
                        "shipper":shipper,
                        "consignee":consignee,
                        "totalCW":round(t.totalCW, 2),
                        "cargoWeight":round(t.sale_order_id.cargoWeight,2),
                        "po_number":t.po_number,
                        "scheduled_departure":self.convert_time(t.scheduled_departure),
                        "scheduled_arrival":self.convert_time(t.scheduled_arrival),
                        "actual_departure":self.convert_time(t.actual_departure),
                        "actual_arrival":self.convert_time(t.actual_arrival),
                        "bill_of_lading":t.oceanBillOfLading if t.oceanBillOfLading else t.awb if t.awb else t.billOfLading if t.billOfLading else None,
                        "status":t.state,
                        "remark":t.remarks,
                        "created_at":t.date_created,
                        }
                trackings.append(vals)
                print(vals,'>>>>>>>>>>>>>>>>>>>>')
                
            # print(tracking,'>>>>>>>>>>>>>>>>>>>>')
            return {"success":True,"message":"Success","trackings":trackings}
        else:
            return {"success":False,"message":"Not AUthenticated","trackings":None}
        
    @http.route('/get/tracking/details',methods=["POST"],type='json',csrf=False,auth="public")
    def getTrackingDetails(self,**post):
        data = json.loads(request.httprequest.data)
        pid = int(data.get('pid'))
        tid = int(data.get('tid'))
        if pid and tid :
            print(data)
            user_obj = request.env['res.partner']
            track_obj = request.env['deepu.sale.tracking']
            invoice_obj = request.env['account.move']
            user = user_obj.sudo().search([('id','=',pid)])
        
        
            tracking = track_obj.sudo().search([('id','=',tid),('sale_order_id.partner_id','=',pid)])
            invoice_urls = []
            try:
                invoice = invoice_obj.sudo().search([('tracking_id','=',tracking.id),('sale_id','=',tracking.sale_order_id.id),('move_type', '=', 'out_invoice')])
                invoice_url = invoice.get_portal_url()
            except Exception as e:
                invoice_url = None
                
                try:
                    for inv in invoice:
                        invoice_urls.append(inv.get_portal_url())
                except Exception as e:
                    print(e)
                print(e,">>>>>>>>>>>>>error inv")
            try:
                print(tracking.sale_order_id)
                quotation_url = tracking.sale_order_id.get_portal_url()
            except Exception as e:
                quotation_url = ''
                print(e,">>>>>>>>>>>>>error quote")
            events = list()
            vessels = list()
            containers = list()
            containers1 = list()
            documents = list()
            for event in tracking.event_line_ids:
                ev = {"eventId":event.id,"event":event.event.name,"date":event.date,"location":event.location,"comments":event.comments}
                events.append(ev)
            for v in tracking.vessels_line_ids:
                vessel = {"vId":v.id,"vessel":v.vessel,"voyage":v.voyage,"departure":v.departure,"delivery":v.delivery,"Port":v.Port,"ArrivalDate":v.ArrivalDate,"DepartureDate":v.DepartureDate,"VesselIMO":v.VesselIMO}
                vessels.append(vessel)
            for i in tracking.sale_order_id.product_line_ids:
                c = {"length":i.length,"width":i.width,"height":i.height,"totalpcs":i.totalpcs,"grossWeight":i.grossWeight,"volume":i.volume,"chargableWeight":i.chargableWeight}
                containers.append(c)
            for j in tracking.sale_order_id.container_line_ids:
                d = {"typeOfContainer":j.typeOfContainer,"noOfContainers":j.noOfContainers}
                containers1.append(d)
            for d in tracking.docs_line_ids:
                key=ENCRYPT_KEY.encode('utf8')
                fernet = Fernet(key)
                data=str({"pid":pid,"id":d.id})
                encMessage = fernet.encrypt(data.encode())
                doc = {"docId":d.id,"file_name":d.file_name,"token":encMessage}
                documents.append(doc)
            blcontainers=list() 
            for k in tracking.blcontainers:
                blcontainer = {"cId":k.id,"containerNumber":k.name,"ContainerTEU":k.ContainerTEU,"ContainerType":k.ContainerType,"BLGateOutDate":k.BLGateOutDate,"BLEmptyReturnDate":k.BLEmptyReturnDate}
                blcontainers.append(blcontainer)
            originCountryCoords=self.get_coordinates(tracking.sale_order_id.originCountry)    
            destinationCountryCoords=self.get_coordinates(tracking.sale_order_id.destinationCountry)    
            vals = {
                "id":tracking.id,
                "name":tracking.name,
                "createdAt":tracking.date_created,
                "customer":tracking.sale_order_id.partner_id.name,
                "poNumber":tracking.po_number,
                "relatedQuotation":tracking.sale_order_id.name,
                "shipmentType":tracking.shipmentType,
                "shipmentTerms":tracking.shipmentTerms,
                "consignee":tracking.consignee,
                "shipper":tracking.shipper,
                "portOfLoading":tracking.sale_order_id.portOfLoading,
                "portOfDestination":tracking.sale_order_id.portOfDestination,
                "originCountry":tracking.sale_order_id.originCountry,
                "destinationCountry":tracking.sale_order_id.destinationCountry,
                "originCountryCoords":originCountryCoords,
                "destinationCountryCoords":destinationCountryCoords,
                "scheduledDeparture":self.convert_time(tracking.scheduled_departure),
                "scheduledArrival":self.convert_time(tracking.scheduled_arrival),
                "actualDeparture":self.convert_time(tracking.actual_departure),
                "actualArrival":self.convert_time(tracking.actual_arrival),
                "chargableWeight":tracking.totalCW,
                "noOfPieces":tracking.no_of_pcs,
                "bill_of_lading":tracking.oceanBillOfLading if tracking.oceanBillOfLading else tracking.awb if tracking.awb else tracking.billOfLading if tracking.billOfLading else None,
                "is_transshipment":tracking.is_transshipment,
                "container_number":tracking.container_number,
                "remarks":tracking.remarks,
                "status":tracking.state,
                "events":events,
                "vessels":vessels,
                "containers":containers,
                "containers1":containers1,
                "quotation":quotation_url,
                "invoice":invoice_url,
                "invoices":invoice_urls,
                "documents":documents,
                #shipsgo details
                "is_transshipment":tracking.is_transshipment,
                "transit_time":tracking.transit_time,
                "transit_delay":tracking.transit_delay,
                "final_delivery_date":tracking.final_delivery_date,
                "final_delivery_place":tracking.final_delivery_place,
                "empty_return_date":tracking.empty_return_date,
                "gate_out_date":tracking.gate_out_date,
                "container_type":tracking.container_type,
                "ContainerTEU":tracking.container_teu,
                "carrier":tracking.shipping_line,
                "bookingNo":tracking.booking_no,
                "co2":tracking.co2,
                "sailing_status":tracking.sailing_status,
                "shipsgo_checking_status":tracking.shipsgo_checking_status,
                "LiveMapUrl":tracking.is_shipsgo_tracking,
                "is_tracking_done":tracking.is_tracking_done,
                "ContainerNumber":tracking.container_number,
                "BLContainerCount":tracking.BLContainerCount,
                "BLContainers":blcontainers
                
                
            }
            return {"success":True,"message":"Success","details":vals}
        else:
            return {"success":False,"message":"Not AUthenticated","details":None}
        
        
    @http.route('/get/tracking/number',methods=["POST"],type='json',csrf=False,auth="public")
    def getTrackingDetailsNumber(self,**post):
        data = json.loads(request.httprequest.data)
        pid = int(data.get('pid'))
        tno = data.get('tno')
        print(data)
        user_obj = request.env['res.partner']
        track_obj = request.env['deepu.sale.tracking']
        invoice_obj = request.env['account.move']
        user = user_obj.sudo().search([('id','=',pid)])
        
        if user :
            tracking = track_obj.sudo().search([('name','=',tno),('sale_order_id.partner_id','=',pid)])
            try:
                invoice = invoice_obj.sudo().search([('tracking_id','=',tracking.id),('sale_id','=',tracking.sale_order_id.id)])
                invoice_url = invoice.get_portal_url()
            except Exception as e:
                invoice_url = ''
                print(e)
            events = list()
            vessels = list()
            containers = list()
            containers1 = list()
            documents = list()
            for event in tracking.event_line_ids:
                ev = {"eventId":event.id,"event":event.event.name,"date":event.date,"location":event.location,"comments":event.comments}
                events.append(ev)
            for v in tracking.vessels_line_ids:
                vessel = {"vId":v.id,"vessel":v.vessel,"voyage":v.voyage,"departure":v.departure,"delivery":v.delivery}
                vessels.append(vessel)
            for i in tracking.sale_order_id.product_line_ids:
                c = {"length":i.length,"width":i.width,"height":i.height,"totalpcs":i.totalpcs,"grossWeight":i.grossWeight,"volume":i.volume,"chargableWeight":i.chargableWeight}
                containers.append(c)
            for j in tracking.sale_order_id.container_line_ids:
                d = {"typeOfContainer":j.typeOfContainer,"noOfContainers":j.noOfContainers}
                containers1.append(d)
            for d in tracking.docs_line_ids:
                key=ENCRYPT_KEY.encode('utf8')
                fernet = Fernet(key)
                data=str({"pid":pid,"id":d.id})
                encMessage = fernet.encrypt(data.encode())
                doc = {"docId":d.id,"file_name":d.file_name,"token":encMessage}
                documents.append(doc)
            vals = {
                "id":tracking.id,
                "name":tracking.name,
                "createdAt":tracking.date_created,
                "customer":tracking.sale_order_id.partner_id.name,
                "poNumber":tracking.po_number,
                "relatedQuotation":tracking.sale_order_id.name,
                "shipmentType":tracking.shipmentType,
                "shipmentTerms":tracking.shipmentTerms,
                "consignee":tracking.consignee,
                "shipper":tracking.shipper,
                "portOfLoading":tracking.sale_order_id.portOfLoading,
                "portOfDestination":tracking.sale_order_id.portOfDestination,
                "originCountry":tracking.sale_order_id.originCountry,
                "destinationCountry":tracking.sale_order_id.destinationCountry,
                "scheduledDeparture":self.convert_time(tracking.scheduled_departure),
                "scheduledArrival":self.convert_time(tracking.scheduled_arrival),
                "actualDeparture":self.convert_time(tracking.actual_departure),
                "actualArrival":self.convert_time(tracking.actual_arrival),
                "chargableWeight":tracking.totalCW,
                "noOfPieces":tracking.no_of_pcs,
                "bill_of_lading":tracking.oceanBillOfLading if tracking.oceanBillOfLading else tracking.awb if tracking.awb else tracking.billOfLading if tracking.billOfLading else None,
                "remarks":tracking.remarks,
                "status":tracking.state,
                "events":events,
                "vessels":vessels,
                "containers":containers,
                "containers1":containers1,
                "quotation":tracking.sale_order_id.get_portal_url(),
                "invoice":invoice_url,
                "documents":documents,
            }
            return {"success":True,"message":"Success","details":vals}
        else:
            return {"success":False,"message":"Not AUthenticated","details":None}
        
        
    @http.route('/track-by-number',methods=["POST"],type='json',csrf=False,auth="public")
    def getTrackingDetailsNumber(self,**kw):
        print("entered>>>>>>>>>>>>>>>>>>>>>>>>>")
        data = json.loads(request.httprequest.data)
        tno = data.get('tno')
        # data = json.loads(request.httprequest.data)
        # tno = kw['tno']
        # print(data)
        # user_obj = request.env['res.partner']
        track_obj = request.env['deepu.sale.tracking']
        tracking = track_obj.sudo().search([('name','=',tno)])
        
        if tracking :
            

            events = list()
            vessels = list()
            containers = list()
            containers1 = list()
            for event in tracking.event_line_ids:
                ev = {"eventId":event.id,"event":event.event.name,"date":event.date,"location":event.location,"comments":event.comments}
                events.append(ev)
            for v in tracking.vessels_line_ids:
                vessel = {"vId":v.id,"vessel":v.vessel,"voyage":v.voyage,"departure":v.departure,"delivery":v.delivery}
                vessels.append(vessel)
            for i in tracking.sale_order_id.product_line_ids:
                c = {"length":i.length,"width":i.width,"height":i.height,"totalpcs":i.totalpcs,"grossWeight":i.grossWeight,"volume":i.volume,"chargableWeight":i.chargableWeight}
                containers.append(c)
            for j in tracking.sale_order_id.container_line_ids:
                d = {"typeOfContainer":j.typeOfContainer,"noOfContainers":j.noOfContainers}
                containers1.append(d)
            vals = {
                "id":tracking.id,
                "name":tracking.name,
                "createdAt":tracking.date_created,
                "customer":tracking.sale_order_id.partner_id.name,
                "poNumber":tracking.po_number,
                "relatedQuotation":tracking.sale_order_id.name,
                "shipmentType":tracking.shipmentType,
                "shipmentTerms":tracking.shipmentTerms,
                "consignee":tracking.consignee,
                "shipper":tracking.shipper,
                "portOfLoading":tracking.sale_order_id.portOfLoading,
                "portOfDestination":tracking.sale_order_id.portOfDestination,
                "originCountry":tracking.sale_order_id.originCountry,
                "destinationCountry":tracking.sale_order_id.destinationCountry,
                "scheduledDeparture":self.convert_time(tracking.scheduled_departure),
                "scheduledArrival":self.convert_time(tracking.scheduled_arrival),
                "actualDeparture":self.convert_time(tracking.actual_departure),
                "actualArrival":self.convert_time(tracking.actual_arrival),
                "chargableWeight":tracking.totalCW,
                "noOfPieces":tracking.no_of_pcs,
                "bill_of_lading":tracking.oceanBillOfLading if tracking.oceanBillOfLading else tracking.awb if tracking.awb else tracking.billOfLading if tracking.billOfLading else None,
                "remarks":tracking.remarks,
                "status":tracking.state,
                "events":events,
                "vessels":vessels,
                "containers":containers,
                "containers1":containers1
            }
            return {"success":True,"message":"Success","details":vals}
        else:
            return {"success":False,"message":"Not AUthenticated","details":None}
    
    
        
    @http.route('/get/this-week-tracking/',methods=["POST"],type='json',csrf=False,auth="public")
    def getThisWeekTrackings(self,**post):
        data = json.loads(request.httprequest.data)
        pid = int(data.get('pid'))
        print(data)
        user_obj = request.env['res.partner']
        user = user_obj.sudo().search([('id','=',pid)])
        trackings = list()
        if user :
            today = fields.Date.today()
            next_week = today + timedelta(days=7)
            shipments = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('scheduled_arrival', '>=', today),
                ('scheduled_arrival', '<', next_week),
                ('state', 'not in', [ 'cancel'])
            ], order='scheduled_arrival')
            for t in shipments:
                try:
                    shippers = t.shipper.split(",")
                    shipper = shippers[0]
                    consignees=t.consignee.split(",")
                    consignee = consignees[0]
                except:
                    shipper = t.shipper
                    consignee = t.consignee
                    
                vals = {"tracking_id":t.id,
                        "tracking_number":t.name,
                        "customer":t.sale_order_id.partner_id.name,
                        "typeOfShipment":t.shipmentType,
                        "shipmentTerms":t.shipmentTerms,
                        "shipper":shipper,
                        "consignee":consignee,
                        "totalCW":round(t.totalCW, 2),
                        "cargoWeight":t.sale_order_id.cargoWeight,
                        "po_number":t.po_number,
                        "status":t.state,
                        "remark":t.remarks,
                        }
                trackings.append(vals)
                print(vals,'>>>>>>>>>>>>>>>>>>>>')
                
            # print(tracking,'>>>>>>>>>>>>>>>>>>>>')
            return {"success":True,"message":"Success","trackings":trackings}
        else:
            return {"success":False,"message":"Not AUthenticated","trackings":None}
    
    @http.route('/get/next-30-tracking/',methods=["POST"],type='json',csrf=False,auth="public")
    def getNext30Trackings(self,**post):
        data = json.loads(request.httprequest.data)
        pid = int(data.get('pid'))
        print(data)
        user_obj = request.env['res.partner']
        user = user_obj.sudo().search([('id','=',pid)])
        trackings = list()
        if user :
            today = fields.Date.today()
            next_30_days = today + timedelta(days=30)
            shipments_next_30 = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('scheduled_arrival', '>=', today),
                ('scheduled_arrival', '<', next_30_days),
                ('state', 'not in', [ 'cancel'])
            ], order='scheduled_arrival')
            for t in shipments_next_30:
                try:
                    shippers = t.shipper.split(",")
                    shipper = shippers[0]
                    consignees=t.consignee.split(",")
                    consignee = consignees[0]
                except:
                    shipper = t.shipper
                    consignee = t.consignee
                    
                vals = {"tracking_id":t.id,
                        "tracking_number":t.name,
                        "customer":t.sale_order_id.partner_id.name,
                        "typeOfShipment":t.shipmentType,
                        "shipmentTerms":t.shipmentTerms,
                        "shipper":shipper,
                        "consignee":consignee,
                        "totalCW":round(t.totalCW, 2),
                        "cargoWeight":t.sale_order_id.cargoWeight,
                        "po_number":t.po_number,
                        "status":t.state,
                        "remark":t.remarks,
                        }
                trackings.append(vals)
                print(vals,'>>>>>>>>>>>>>>>>>>>>')
                
            # print(tracking,'>>>>>>>>>>>>>>>>>>>>')
            return {"success":True,"message":"Success","trackings":trackings}
        else:
            return {"success":False,"message":"Not AUthenticated","trackings":None}
    
    
    
    @http.route('/get/current-tracking/',methods=["POST"],type='json',csrf=False,auth="public")
    def getCurrentTrackings(self,**post):
        data = json.loads(request.httprequest.data)
        pid = int(data.get('pid'))
        country = data.get('country')
        print(data)
        user_obj = request.env['res.partner']
        user = user_obj.sudo().search([('id','=',pid)])
        trackings = list()
        if user :
            if country =="all":
                current_shipments = request.env['deepu.sale.tracking'].sudo().search([
                    ('partner_id', '=', pid),
                    ('state', 'not in', [ 'cancel', 'delivered']),
                ])
            else:
                current_shipments = request.env['deepu.sale.tracking'].sudo().search([
                    ('partner_id', '=', pid),
                    ('state', 'not in', [ 'cancel', 'delivered']),
                    ('sale_order_id.originCountry','=',country)
                ])
            print(current_shipments,"()()()()()()()()()()()()()()()()")
            for t in current_shipments:
                try:
                    shippers = t.shipper.split(",")
                    shipper = shippers[0]
                    consignees=t.consignee.split(",")
                    consignee = consignees[0]
                except:
                    shipper = t.shipper
                    consignee = t.consignee
                    
                vals = {"tracking_id":t.id,
                        "tracking_number":t.name,
                        "customer":t.sale_order_id.partner_id.name,
                        "typeOfShipment":t.shipmentType,
                        "shipmentTerms":t.shipmentTerms,
                        "shipper":shipper,
                        "consignee":consignee,
                        "totalCW":round(t.totalCW, 2),
                        "cargoWeight":t.sale_order_id.cargoWeight,
                        "po_number":t.po_number,
                        "status":t.state,
                        "remark":t.remarks,
                        }
                trackings.append(vals)
                print(vals,'>>>>>>>>>>>>>>>>>>>>')
                
            # print(tracking,'>>>>>>>>>>>>>>>>>>>>')
            return {"success":True,"message":"Success","trackings":trackings}
        else:
            return {"success":False,"message":"Not AUthenticated","trackings":None}
    
    
    @http.route('/get/tracking/attention/',methods=["POST"],type='json',csrf=False,auth="public")
    def getAttentionTrackings(self,**post):
        data = json.loads(request.httprequest.data)
        print(data)
        pid = int(data.get('pid'))
        country = data.get('country')
        
        user_obj = request.env['res.partner']
        user = user_obj.sudo().search([('id','=',pid)])
        trackings = list()
        if user :
            if country =="all":
                attention_required = request.env['deepu.sale.tracking'].sudo().search([
                    ('partner_id', '=', pid),
                    ('state', 'not in', ['cancel', 'delivered','draft'])]
                )
            else:
                attention_required = request.env['deepu.sale.tracking'].sudo().search([
                    ('partner_id', '=', pid),
                    ('state', 'not in', ['cancel', 'delivered','draft']),
                    ('sale_order_id.originCountry','=',country)]
                )
            for t in attention_required:
                if t.actual_arrival and t.scheduled_arrival:
                    if t.actual_arrival > t.scheduled_arrival or t.required_attention==True:
                        try:
                            shippers = t.shipper.split(",")
                            shipper = shippers[0]
                            consignees=t.consignee.split(",")
                            consignee = consignees[0]
                        except:
                            shipper = t.shipper
                            consignee = t.consignee
                            
                        vals = {"tracking_id":t.id,
                                "tracking_number":t.name,
                                "customer":t.sale_order_id.partner_id.name,
                                "typeOfShipment":t.shipmentType,
                                "shipmentTerms":t.shipmentTerms,
                                "shipper":shipper,
                                "consignee":consignee,
                                "totalCW":round(t.totalCW, 2),
                                "cargoWeight":t.sale_order_id.cargoWeight,
                                "po_number":t.po_number,
                                "status":t.state,
                                "remark":t.remarks,
                                }
                        trackings.append(vals)
                        print(vals,'>>>>>>>>>>>>>>>>>>>>')
                
            # print(tracking,'>>>>>>>>>>>>>>>>>>>>')
            return {"success":True,"message":"Success","trackings":trackings}
        else:
            return {"success":False,"message":"Not AUthenticated","trackings":None}
    
    
    @http.route('/login_customer/<token>', type='http', auth='public', methods=['GET'], csrf=False)
    def login_action(self,access_token=None,**kw):
        db="kvmay12"
        print(kw)
        fernet = Fernet(ENCRYPT_KEY.encode('UTF-8'))
        token = kw['token']
        token = token.encode('UTF-8')
        decMessage = fernet.decrypt(token).decode()
        data = ast.literal_eval(decMessage)
        print(data)
        access_token = access_token or request.httprequest.args.get('access_token')
        # print(access_token)
        pass1 = data['auth'].encode('UTF-8')
        password = fernet.decrypt(pass1).decode()
        uid = request.session.authenticate(db,data['user'],password)
        url = '/my/orders/'+str(data['doc_id'])+'?access_token='+str(access_token)+'&report_type=pdf'
        # print(url)
        return request.redirect(url)
        
    
    # http://127.0.0.1:8069/mail/view?model=sale.order&res_id=35&access_token=9474d606-fe36-4913-a2f2-b15518d540b1&auth_signup_token=a6KFVsa9TGqQJXk9v66w
    
    @http.route('/attachment/<token>',type='http',auth='public', methods=['GET'],csrf=False)
    def testdownload(self,**kw):
        fernet = Fernet(ENCRYPT_KEY.encode('UTF-8'))
        token = kw['token']
        token = token.encode('UTF-8')
        decMessage = fernet.decrypt(token).decode()
        data = ast.literal_eval(decMessage)
        print(token)
        fileobj = request.env['deepu.sale.docs.line']
        doc_id = int(data['id'])
        binaryfile = fileobj.sudo().search([('id','=',doc_id)])
        print(binaryfile.file_name)
        data = io.BytesIO(base64.standard_b64decode(binaryfile["file"]))
            # we follow what is done in ir_http's binary_content for the extension management
        extension = os.path.splitext(binaryfile["file_name"] or '')[1]
        extension = extension if extension else mimetypes.guess_extension(binaryfile["mimetype"] or '')
        filename = binaryfile['file_name']
        print(filename)
        filename = filename if os.path.splitext(filename)[1] else filename + extension
        print(filename)
        return http.send_file(data, filename=filename, as_attachment=True)
        # return http.send_file(binaryfile, filename=binaryfile.file_name, as_attachment=False)
        
    @http.route('/shipment/dashboard/graph/', type='json', auth='public' , methods=['POST'],csrf=False)
    def get_invoice_graph_data(self, **kwargs):
        pid = int(request.jsonrequest.get('pid'))
        days = int(request.jsonrequest.get('days'))
        print(pid,">>>>>>>>>>>>>>>>pid")
        if pid and days:
            partner = request.env['res.partner'].sudo().browse(pid)
            if partner:
                end_date = fields.Date.today()
                
                if days == 365:
                    # If num_days is 365, get all invoices of the current year
                    start_date = date(end_date.year, 1, 1)
                elif days == 30:
                    start_date = date(end_date.year,end_date.month, 1)
                else:
                    # For other values of num_days, calculate the start date accordingly
                    start_date = end_date - timedelta(days=days)
                domain = [
                    ('partner_id', '=', partner.id),
                    ('move_type', '=', 'out_invoice'),  # Correct field name for move type
                    ('invoice_date', '>=', start_date.strftime('%Y-%m-%d')),  # Format start_date as a string with single quotes
                    ('invoice_date', '<=', end_date.strftime('%Y-%m-%d')),  # Format end_date as a string with single quotes
                    ('state', '=', 'posted')
                ]

                if days == 365:
                    invoices_data = request.env['account.move'].sudo().read_group(
                        domain=domain,
                        fields=['invoice_date', 'amount_total', 'amount_residual'],
                        groupby= ['invoice_date'] ,
                        lazy=False
                    ) 
                else :
                    groupby_parameter = "invoice_date::date" 
                    def format_domain_element(element):
                        field, operator, value = element
                        if isinstance(value, str):
                            return f"{field} {operator} '{value}'"
                        return f"{field} {operator} {value}"

                # Format the domain_str with correct conditions
                    domain_str = ' AND '.join([format_domain_element(elem) for elem in domain]) 
                    query = f"""
                        SELECT {groupby_parameter} AS invoice_date, SUM(amount_total) AS amount_total, SUM(amount_residual) AS amount_residual
                        FROM account_move
                        WHERE {domain_str}
                        GROUP BY {groupby_parameter}
                        ORDER BY {groupby_parameter}
                    """
                    print(query)
                    request.env.cr.execute(query, {'pid': partner.id})
                    invoices_data = request.env.cr.dictfetchall()
                graph_data = {
                    'labels': [data['invoice_date'] for data in invoices_data],
                    'invoice_amounts': [data['amount_total'] for data in invoices_data],
                    'due_amounts': [data['amount_residual']for data in invoices_data],
                }

                return graph_data
            return {'error': 'No partner found.'}

        return {'error': 'No pid provided.'}

    @http.route('/shipment/dashboard', type='json', auth='public' , methods=['POST'],csrf=False)
    def get_shipment_count(self, **kwargs):
        pid = int(request.jsonrequest.get('pid'))
        days = int(request.jsonrequest.get('days'))
        days=365
        current_year = date.today().year
        print(pid,">>>>>>>>>>>>>>>>pid")
        if pid and days:
            end_date = fields.Date.today()
                
            # if days == 365:
            #     # If num_days is 365, get all invoices of the current year
            #     start_date = date(end_date.year, 1, 1)
            # elif days == 30:
            #     start_date = date(end_date.year,end_date.month, 1)
            # else:
            #     # For other values of num_days, calculate the start date accordingly
            #     start_date = end_date - timedelta(days=days)
            start_date = end_date - timedelta(days=365)
            domain = [
                ('partner_id', '=', pid),
                ('move_type', '=', 'out_invoice'),  # Correct field name for move type
                ('invoice_date', '>=', start_date.strftime('%Y-%m-%d')),  # Format start_date as a string with single quotes
                ('invoice_date', '<=', end_date.strftime('%Y-%m-%d')),  # Format end_date as a string with single quotes
                ('state', '=', 'posted')
            ]

            if days == 365:
                invoices_data = request.env['account.move'].sudo().read_group(
                    domain=domain,
                    fields=['invoice_date', 'amount_total', 'amount_residual'],
                    groupby= ['invoice_date'] ,
                    lazy=False
                ) 
            else :
                groupby_parameter = "invoice_date::date" 
                def format_domain_element(element):
                    field, operator, value = element
                    if isinstance(value, str):
                        return f"{field} {operator} '{value}'"
                    return f"{field} {operator} {value}"

            # Format the domain_str with correct conditions
                domain_str = ' AND '.join([format_domain_element(elem) for elem in domain]) 
                query = f"""
                    SELECT {groupby_parameter} AS invoice_date, SUM(amount_total) AS amount_total, SUM(amount_residual) AS amount_residual
                    FROM account_move
                    WHERE {domain_str}
                    GROUP BY {groupby_parameter}
                    ORDER BY {groupby_parameter}
                """
                print(query)
                request.env.cr.execute(query, {'pid': pid})
                invoices_data = request.env.cr.dictfetchall()
                
                
            shipments_graph = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('scheduled_arrival', '>=', start_date),
                ('state', 'not in', [ 'cancel'])
            ], order='scheduled_arrival DESC')
            month_abbr = {
                1: "Jan",
                2: "Feb",
                3: "Mar",
                4: "Apr",
                5: "May",
                6: "Jun",
                7: "Jul",
                8: "Aug",
                9: "Sep",
                10: "Oct",
                11: "Nov",
                12: "Dec",
            }
            
            # ontime_shipments = {month: 0 for month in range(1, 13)}
            # delayed_shipments = {month: 0 for month in range(1, 13)}

            # # Set to store unique months with shipment data
            # months_with_shipment_data = set()

            # # Loop through shipments and categorize them based on scheduled_departure
            # for shipment in shipments_graph:
            #     if shipment.scheduled_arrival and shipment.actual_arrival:
            #         month = shipment.scheduled_arrival.month

            #         # Add the month to the set of months with shipment data
            #         months_with_shipment_data.add(month)

            #         # Check if the shipment is on-time or delayed
            #         if shipment.actual_arrival <= shipment.scheduled_arrival and not shipment.required_attention:
            #             ontime_shipments[month] += 1
            #         else:
            #             delayed_shipments[month] += 1

            # # Organize data in the required format for months with shipment data
            # labels = [month_abbr[month] for month in sorted(months_with_shipment_data)]
            # ontime_shipments_data = [ontime_shipments[month] for month in sorted(months_with_shipment_data)]
            # delayed_shipments_data = [delayed_shipments[month] for month in sorted(months_with_shipment_data)]

            # result_data = {
            #     "labels": labels,
            #     "ontime_shipments": ontime_shipments_data,
            #     "delayed_shipments": delayed_shipments_data,
            # }
            # Adjust the ontime_shipments and delayed_shipments to include year
            ontime_shipments = {}
            delayed_shipments = {}

            # Loop through shipments and categorize them based on scheduled_departure
            for shipment in shipments_graph:
                if shipment.scheduled_arrival and shipment.actual_arrival:
                    year_month = (shipment.scheduled_arrival.year, shipment.scheduled_arrival.month)

                    # Initialize the count for the year-month combination if it doesn't exist
                    if year_month not in ontime_shipments:
                        ontime_shipments[year_month] = 0
                        delayed_shipments[year_month] = 0

                    # Check if the shipment is on-time or delayed
                    if shipment.actual_arrival <= shipment.scheduled_arrival and not shipment.required_attention:
                        ontime_shipments[year_month] += 1
                    else:
                        delayed_shipments[year_month] += 1

            # Organize data in the required format
            sorted_year_months = sorted(ontime_shipments.keys())
            labels = [f"{month_abbr[month]} {year}" for year, month in sorted_year_months]
            ontime_shipments_data = [ontime_shipments[year_month] for year_month in sorted_year_months]
            delayed_shipments_data = [delayed_shipments[year_month] for year_month in sorted_year_months]

            result_data = {
                "labels": labels,
                "ontime_shipments": ontime_shipments_data,
                "delayed_shipments": delayed_shipments_data,
            }




                
            
            print(shipments_graph,">>>>>>>>>>>>>>shipment graph")

           
            # graph_data = {
            #      "labels": labels,
            #     'invoice_amounts':ontime_shipments_data,
            #     'due_amounts':delayed_shipments_data,
            # }
            
            tracking_count = request.env['deepu.sale.tracking'].sudo().search_count([
                ('sale_order_id.partner_id', '=', pid),
                ('state', '!=', 'cancel')
            ])

            today = fields.Date.today()
            next_week = today + timedelta(days=7)

            shipments = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('scheduled_arrival', '>=', today),
                ('scheduled_arrival', '<', next_week),
                ('state', 'not in', [ 'cancel'])
            ], order='scheduled_arrival')

            next_30_days = today + timedelta(days=30)
            shipments_next_30 = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('scheduled_arrival', '>=', today),
                ('scheduled_arrival', '<', next_30_days),
                ('state', 'not in', [ 'cancel', 'delivered',])
            ], order='scheduled_arrival')

            current_shipments_attention = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('state', 'not in', [ 'cancel','delivered'])
            ])
            
            current_shipments = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('state', 'not in', [ 'cancel','delivered'])
            ])
            # print(current_shipments,">>>>>>>>>>>>>current shipments")
            attention_required_shipments = []
            required_shipments = []
            
            for shipment in current_shipments_attention:
                if shipment.actual_arrival and shipment.scheduled_arrival:
                    if shipment.actual_arrival > shipment.scheduled_arrival or shipment.required_attention==True:
                        attention_required_shipments.append(shipment)

            attention_required = request.env['deepu.sale.tracking'].sudo().search([
                ('partner_id', '=', pid),
                ('state', 'not in', ['cancel', 'delivered']),
                ('required_attention', '=', True)]
            )
            origin_countries = Counter(shipment['sale_order_id']['originCountry'] for shipment in current_shipments)
            origin_countries_attention = Counter(shipment['sale_order_id']['originCountry'] for shipment in attention_required_shipments)
            response = [{'origin_country': country, 'num_shipments': count} for country, count in origin_countries.items()]
            response_attention = [{'origin_country': country, 'num_shipments': count} for country, count in origin_countries_attention.items()]
            total_current_count = sum(origin_countries.values())
            total_delayed_count = sum(origin_countries_attention.values())

            shipment_data = [{
                'id':shipment.id,
                'shipmentType': shipment.shipmentType,
                'scheduled_arrival': shipment.scheduled_arrival.strftime('%d/%m/%Y'),
                'shipper':self.get_first_string(shipment.shipper) 
                # shipment.shipper.split(',')[0].strip().lower().capitalize(),
            } for shipment in shipments]

            shipments_next_30_days = [{
                'id':shipment30.id,
                'shipmentType': shipment30.shipmentType,
                'scheduled_arrival': shipment30.scheduled_arrival.strftime('%d/%m/%Y'),
                'shipper':self.get_first_string(shipment30.shipper)
                # .split(',')[0].strip().lower().capitalize(),
            } for shipment30 in shipments_next_30]
            
            invoices = request.env['account.move'].sudo().search([
                ('partner_id', '=', pid),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                ('invoice_date', '>=', start_date.strftime('%Y-%m-%d')), 
                ('invoice_date', '<=', end_date.strftime('%Y-%m-%d')), 
            ], order='invoice_date_due')
            
            
            total_amount = sum(invoice.amount_total for invoice in invoices)
            total_due = sum(invoice.amount_residual for invoice in invoices)
            total_overdue = sum(invoice.amount_residual for invoice in invoices.filtered(lambda inv: inv.invoice_date_due and inv.invoice_date_due < fields.Date.today()))
            overdue_percentage = (total_overdue / total_due) * 100 if total_due != 0 else 0.0
            
            # shipment_types = request.env['deepu.sale.tracking'].sudo().search_read([
            #     ('partner_id', '=', pid),
            #     ('state', 'not in', ['draft', 'cancel'])
            # ], ['shipmentType', 'totalCW', 'date_of_delivery'])
            shipment_types = request.env['site_settings.shipment_type'].sudo().search([])
            shipment_details = []
            for shipment in shipment_types:
                shipment_type = shipment.name
                shipments = request.env['account.move'].sudo().search([
                    ('partner_id', '=', pid),
                    ('typeOfShipment', '=', shipment_type),
                    ('state', '=', 'posted'),
                    ('move_type', '=', 'out_invoice')
                ])
                
                shipment_outstanding = sum(shipment.amount_residual for shipment in shipments)
                shipment_overdue = sum(shipment.amount_residual for shipment in shipments if shipment.filtered(lambda inv: inv.invoice_date_due and inv.invoice_date_due < fields.Date.today()))
                shipment_overdue_percentage = (shipment_overdue / shipment_outstanding) * 100 if shipment_outstanding != 0 else 0.0
                
                shipment_details.append({
                    'shipmentType': shipment_type,
                    'outstanding': shipment_outstanding,
                    'overdue': shipment_overdue,
                    'overdue_percentage': round(shipment_overdue_percentage,2)
                })
            
            states = {
                "labels":['Draft','Booked','Departed','Transit','Arrived','Under Clearance','Out For Delivery','Delivered'],
                "values":[
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'draft'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'booked'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'departed'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'transit'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'transit'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'clearance'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'out'),('partner_id', '=', pid)]),
                request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'delivered'),('partner_id', '=', pid)]),
                # request.env['deepu.sale.tracking'].sudo().search_count([('state', '=', 'cancel'),('partner_id', '=', pid)])
                ]
            }
            print(pid,"(((((((((((((())))))))))))))")
            sdomain = [
                ('partner_id', '=', pid),
                ('state', 'not in', [ 'cancel','delivered','draft']),
                ('date_created', '>=', fields.Datetime.to_string(fields.datetime.now() - timedelta(days=int(days)))),
            ]
            
            ongoing_trackings = request.env['deepu.sale.tracking'].sudo().search(sdomain)
            print(ongoing_trackings,">>>>>>>>trackings ")
            ongoing_shipments = []
            for tracking in ongoing_trackings:
                # shipment_type =''
                # if tracking.shipmentType == 'Air Freight':
                #     shipment_type="airport"
                # elif tracking.shipmentType in ['FCL','LCL','Sea Freight']:
                #     shipment_type="ferry"
                # elif tracking.shipmentType in ['Road Freight','Courier Service']:
                #     shipment_type="bus"
                events = list()
                vessels = list()
                containers = list()
                containers1 = list()
                
                for event in tracking.event_line_ids:
                    ev = {"eventId":event.id,"event":event.event.name,"date":event.date,"location":event.location,"comments":event.comments}
                    events.append(ev)
                for v in tracking.vessels_line_ids:
                    vessel = {"vId":v.id,"vessel":v.vessel,"voyage":v.voyage,"departure":v.departure,"delivery":v.delivery}
                    vessels.append(vessel)
                for i in tracking.sale_order_id.product_line_ids:
                    c = {"length":i.length,"width":i.width,"height":i.height,"totalpcs":i.totalpcs,"grossWeight":i.grossWeight,"volume":i.volume,"chargableWeight":i.chargableWeight}
                    containers.append(c)
                for j in tracking.sale_order_id.container_line_ids:
                    d = {"typeOfContainer":j.typeOfContainer,"noOfContainers":j.noOfContainers}
                    containers1.append(d)
                    
                

                shipment = {
                    'id': tracking.id,
                    'originCountry': tracking.sale_order_id.originCountry,
                    'destinationCountry': tracking.sale_order_id.destinationCountry,
                    'trackingNumber': tracking.name,
                    'amount': tracking.sale_order_id.amount_total,
                    'status': tracking.state,
                    "shipmentType":tracking.shipmentType,
                    "shipmentTerms":tracking.shipmentTerms,
                    "scheduled_departure":self.convert_time(tracking.scheduled_departure),
                    "scheduled_arrival":self.convert_time(tracking.scheduled_arrival),
                    "actual_departure":self.convert_time(tracking.actual_departure),
                    "actual_arrival":self.convert_time(tracking.actual_arrival),
                    "totalCW":tracking.totalCW,
                    "consignee":tracking.consignee,
                    "shipper":tracking.shipper,
                    "state":tracking.state,
                    "required_attention":tracking.required_attention,
                    "po_number":tracking.po_number,
                    "name":tracking.name,
                    "createdAt":tracking.date_created,
                    "customer":tracking.sale_order_id.partner_id.name,
                    "poNumber":tracking.po_number,
                    "relatedQuotation":tracking.sale_order_id.name,
                    "shipmentType":tracking.shipmentType,
                    "shipmentTerms":tracking.shipmentTerms,
                    "consignee":tracking.consignee,
                    "shipper":tracking.shipper,
                    "portOfLoading":tracking.sale_order_id.portOfLoading,
                    "portOfDestination":tracking.sale_order_id.portOfDestination,
                    "originCountry":tracking.sale_order_id.originCountry,
                    "destinationCountry":tracking.sale_order_id.destinationCountry,
                    "scheduledDeparture":self.convert_time(tracking.scheduled_departure),
                    "scheduledArrival":self.convert_time(tracking.scheduled_arrival),
                    "actualDeparture":self.convert_time(tracking.actual_departure),
                    "actualArrival":self.convert_time(tracking.actual_arrival),
                    "chargableWeight":tracking.totalCW,
                    "noOfPieces":tracking.no_of_pcs,
                    "bill_of_lading":tracking.oceanBillOfLading if tracking.oceanBillOfLading else tracking.awb if tracking.awb else tracking.billOfLading if tracking.billOfLading else None,
                    "remarks":tracking.remarks,
                    "status":tracking.state,
                    "events":events,
                    "vessels":vessels,
                    "containers":containers,
                    "containers1":containers1,
                    "st":tracking.shipmentType
                }
                ongoing_shipments.append(shipment)
            # ddomain = [
            #     ('partner_id', '=', pid),
            #     # ('scheduled_arrival', '=', 'actual_arrival'),
            #     ('state', '=', 'delivered'),
            # ]
            # delivered_trackings = request.env['deepu.sale.tracking'].sudo().search(ddomain).read(fields=['name','date_created','scheduled_arrival','actual_arrival'])
            # print(ongoing_trackings,">>>>>>>>>>ongoing")
            # print(delivered_trackings,">>>>>>>>>>delivered")      
            
            # delivered_trackings_list = [dtracking for dtracking in delivered_trackings if dtracking['scheduled_arrival'] == dtracking['actual_arrival']]
            # print(delivered_trackings_list)   
            vals= {
                'totalinvoice': round(total_amount,2),
                'total_due':  round(total_due,2),
                'total_overdue':  round(total_overdue,2),
                'overdue_percentage': round(overdue_percentage,2),
                'shipment_details': shipment_details,
                'count': tracking_count,
                'total_delayed_count': total_delayed_count,
                'total_current_count': total_current_count,
                'shipments_this_week': shipment_data,
                'shipments_next_30': shipments_next_30_days,
                'current_shipments': response,
                'delayed_shipments': response_attention,
                'account_graph':result_data,
                'shipment_graph':states,
                'ongoing_shipments':ongoing_shipments
            }
            print(vals)
            return vals
        else:
            return {'error': 'No pid provided.'}
    
   
        
   
        

        
        
        
        
        
        
        
        
        
        
        
        
