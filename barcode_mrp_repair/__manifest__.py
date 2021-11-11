# Copyright 2021 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Barcode Mrp Repair',
    'summary': """
        Add barcode support on mrp repair""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Rosen Vladimirov, BioPrint Ltd.,Odoo Community Association (OCA)',
    'website': 'https://github.com/rosenvladimirov/stock-logistics-barcode',
    'depends': [
        'mrp_repair',
        'barcodes',
    ],
    'data': [
        'views/mrp_repair_views.xml',
    ],
    'demo': [
    ],
}
