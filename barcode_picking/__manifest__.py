# -*- coding: utf-8 -*-

{
    'name': "Barcode on MRP workorder",
    'summary': "Add support for barcode scanning in workorder.",
    'description': """
        This module adds support for barcodes scanning to the warehouse management system.
    """,
    'category': 'Warehouse',
    'version': '11.0.0.2.0',
    'depends': ['barcodes', 'stock'],
    'data': [
        'data/ir_config_parameter.xml',
        'views/picking_barcode_views.xml',
        'wizard/stock_picking_add_product.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}
