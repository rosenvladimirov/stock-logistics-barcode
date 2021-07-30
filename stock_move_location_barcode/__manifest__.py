# Copyright 2021 Rosen Vladimirov
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Stock Move Location Barcode',
    'summary': """
        Add barcode support on stock_move_location""",
    'version': '11.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Rosen Vladimirov, '
              'BioPrint Ltd., '
              'Odoo Community Association (OCA)',
    'website': 'https://github.com/rosenvladimirov/stock-logistics-barcode',
    'depends': [
        'stock_move_location',
    ],
    'data': [
        'wizards/stock_move_location.xml',
    ],
    'demo': [
    ],
}
