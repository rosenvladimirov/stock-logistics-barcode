# -*- coding: utf-8 -*-

{
    'name': "Barcode on MRP Workorders",
    'summary': "Add support for barcode scanning in Manufacture working order.",
    'description': """
        This module adds support for barcodes scanning to the Manufacturing managment system.
    """,
    'category': 'Manufacturing',
    'version': '11.0.0.5.0',
    'depends': [
        'barcodes',
        'mrp',
        'stock',
        'product_gs_standard',
        'stock_packing_center',
        'website',
        ],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_bom_view.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workorder_views.xml',
        'views/stock_picking_views.xml',
        'views/barcode_mrp_workorder.xml',
        'views/mrp_routing_views.xml',
        'views/stock_account_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}
