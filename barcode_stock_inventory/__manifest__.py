# -*- coding: utf-8 -*-

{
    'name': "Barcode on Stock Inventory",
    'summary': "Add support for barcode scanning in Stock Inventory Adjustment.",
    'description': """
        This module adds support for barcodes scanning to the Stock Inventory Adjustment.
    """,
    'category': 'Warehouse',
    'version': '11.0.0.1.0',
    'depends': [
        'barcodes',
        'mrp',
        'product_gs_standard',
        #'stock_autoprint'
        ],
    'data': [

    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}
