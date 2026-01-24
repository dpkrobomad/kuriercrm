from odoo import models, fields, api
import requests
import json
import base64
from odoo.exceptions import ValidationError

class CreateAccountWizard(models.TransientModel):
    _name = 'create.account.wizard'
    _description = 'Create Account Wizard'

    partner_id = fields.Many2one('res.partner', string='Customer')
    company_name = fields.Char('Company Name', readonly=True)
    contact_person = fields.Char('Contact Person', readonly=True)
    email = fields.Char('Email', readonly=True)
    phone = fields.Char('Phone', readonly=True)
    partner_ref = fields.Char('Partner ID', readonly=True)
    password = fields.Char('Password', required=True)
    confirm_password = fields.Char('Confirm Password', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            partner = self.env['res.partner'].browse(self.env.context.get('active_id'))
            res.update({
                'partner_id': partner.id,
                'company_name': partner.name,
                'contact_person': partner.contact_person,
                'email': partner.email,
                'phone': partner.phone or partner.mobile,
                'partner_ref': partner.id,
            })
        return res

    def action_create_account(self):
        self.ensure_one()
        
        # Check if passwords match
        if self.password != self.confirm_password:
            raise ValidationError("Passwords don't match!")

        # Encode password in base64
        password_bytes = self.password.encode('utf-8')
        base64_password = base64.b64encode(password_bytes).decode('utf-8')

        # Get partner data
        partner = self.env['res.partner'].browse(self.partner_id.id)
        if not partner:
            raise ValidationError("Partner not found!")

        # Validate required fields
        if not partner.email:
            raise ValidationError("Email is required for the customer!")
        if not partner.contact_person:
            raise ValidationError("Contact Person is required for the customer!")
        if not partner.phone and not partner.mobile:
            raise ValidationError("Phone number is required for the customer!")

        data = {
            'fullname': partner.contact_person,
            'email': partner.email,
            'phone': partner.phone or partner.mobile,
            'OdooId': partner.id,
            'company': partner.name,
            'password': base64_password
        }

        try:
            # Prepare headers - Django REST Framework API expects standard JSON headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            
            print("Sending data to Django API:", data)  # Debug print
            response = requests.post(
                'http://127.0.0.1:8000/api/create_user/',
                json=data,
                headers=headers,
                timeout=30  # Add timeout to prevent hanging
            )
            print("Response status:", response.status_code)  # Debug print
            print("Response:", response.text)  # Debug print
            
            # Parse response based on Django API response format
            try:
                result = response.json()
            except (ValueError, json.JSONDecodeError):
                result = {}
            
            # Handle different status codes based on Django API responses
            if response.status_code == 201:
                # Success response: {"success": True, "message": "..."}
                if result.get('success'):
                    # Close the wizard on success
                    return {'type': 'ir.actions.act_window_close'}
                else:
                    error_msg = result.get('message', 'Unknown error occurred')
                    raise ValidationError(f"API returned error: {error_msg}")
            
            elif response.status_code == 400:
                # Bad request: {"error": "..."}
                error_msg = result.get('error', 'Bad request. Please check the data.')
                raise ValidationError(f"API Error: {error_msg}")
            
            elif response.status_code == 403:
                # Forbidden - likely Django REST Framework permission issue
                error_msg = "Access forbidden (403). "
                if result.get('detail'):
                    error_msg += f"Django API Error: {result['detail']}"
                elif result.get('error'):
                    error_msg += f"API Error: {result['error']}"
                else:
                    error_msg += "The Django API may require permission_classes = [AllowAny] in the view."
                raise ValidationError(error_msg)
            
            elif response.status_code == 401:
                raise ValidationError("Unauthorized. The Django API may require authentication.")
            
            elif response.status_code == 404:
                raise ValidationError("API endpoint not found. Please verify the endpoint URL.")
            
            elif response.status_code >= 500:
                # Server error: {"error": "..."}
                error_msg = result.get('error', f'Server error ({response.status_code})')
                raise ValidationError(f"Server error: {error_msg}")
            
            # For any other status code, raise an error
            response.raise_for_status()
            
            # Close the wizard if we get here
            return {'type': 'ir.actions.act_window_close'}
            
        except requests.exceptions.Timeout:
            raise ValidationError("Request timed out. Please check your connection and try again.")
        except requests.exceptions.ConnectionError:
            raise ValidationError("Connection error. Please check your internet connection.")
        except requests.exceptions.HTTPError as e:
            raise ValidationError(f"HTTP error occurred: {str(e)}")
        except ValidationError:
            # Re-raise ValidationError as-is
            raise
        except Exception as e:
            raise ValidationError(f"Failed to create account: {str(e)}") 