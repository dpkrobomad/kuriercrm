# -*- coding: utf-8 -*-
{
    'name': "Sale CustomeS",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '15.0.1.5',

    # any module necessary for this one to work correctly
    'depends': ['base','web','sale','sale_management','account','site_settings'],

    # always loaded
    'data': [
        'security/kvadmin_security.xml',
        'security/ir.model.access.csv',
        'data/sale_data.xml',
        'data/seaway_data.xml',
        'data/seaway_sync_countries.xml',
        'data/cron_job.xml',
        'views/views.xml',
        'views/sequence.xml',
        'views/tracking.xml',
        'views/sale_views.xml',
        # 'views/kurier_document_template.xml',
        'views/account_view.xml',
        'views/templates.xml',
        'report/report_layout.xml',
        'report/quotation_report.xml',
        'report/invoice.xml',
        'views/pod_wizard_view.xml',
        'report/report_pod.xml',
        'views/partner_view.xml',
        'views/create_account_wizard_view.xml',
        'views/account_soa_view.xml',
        'views/seaway_bill_wizard_view.xml',
        'views/seaway_bill_views.xml',
        'report/report_seaway_bill.xml',
        # XLSX reports; include when report_xlsx is installed
        # 'reports/account_soa_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'deepu_sale/static/src/css/decoration.css',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'post_init_hook': 'deepu_sale.hooks:post_init_hook',
}
