# -*- coding: utf-8 -*-

{
    'name': "Barcode on sale",
    'summary': "Add support for barcode scanning in sale order.",
    'description': """
        This module adds support for barcodes scanning to the sale orders.
    """,
    'category': 'Sales',
    'version': '11.0.0.1.0',
    'depends': [
        'barcodes',
        'sale',
        'base',
        'stock'
    ],
    'data': [
        'views/res_config_settings.xml',
        'views/sale_barcode_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}
