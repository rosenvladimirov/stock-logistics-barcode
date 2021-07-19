# -*- coding: utf-8 -*-

{
    'name': "Barcode on purchase",
    'summary': "Add support for barcode scanning in purchase order.",
    'description': """
        This module adds support for barcodes scanning to the purchase orders.
    """,
    'category': 'Purchase',
    'version': '11.0.0.1.0',
    'depends': ['barcodes', 'purchase', 'base'],
    'data': [
        'views/res_config_settings.xml',
        'views/purchase_barcode_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}
