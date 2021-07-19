# -*- coding: utf-8 -*-

{
    'name': "Barcode on MRP workorder",
    'summary': "Add support for barcode scanning in workorder.",
    'description': """
        This module adds support for barcodes scanning to the warehouse management system.
    """,
    'category': 'Warehouse',
    'version': '11.0.0.1.0',
    'depends': ['barcodes', 'stock'],
    'data': [
        'views/picking_barcode_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}
