# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPickingAddProduct(models.TransientModel):
        _name = "stock_picking.add.product"
        _description = "Add immediately missing scanned product"

        product_id = fields.Many2one('product.product')
        note = fields.Text("Message", readonly=True)
        lot = fields.Char("Lot")
        picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type')
        lot_new = fields.Char('Check Lot/SN')
        use_date = fields.Char('Check Date')

        def validate_lot(self):
                if self.lot and self.product_id and self.picking_type_id:
                        lot_obj = self.env['stock.production.lot']
                        check_lot = self.lot
                        
                        parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(check_lot)
                        product_barcode = False
                        lot = False
                        code = False
                        use_date = False
                        lot_id = False
                        if parsed_result['type'] in ['weight', 'product']:
                                if parsed_result['type'] == 'weight':
                                        product_barcode = parsed_result['base_code']
                                else:  # product
                                        product_barcode = parsed_result['base_code']
                                        lot = parsed_result['lot']
                                        use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                        if parsed_result['type'] == 'lot':
                                lot = parsed_result['lot']
                                code = parsed_result['code']
                                product_barcode = parsed_result['base_code']
                                use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                        if product_barcode:
                                self.product_id.write({'barcode': product_barcode})
                        if code:
                            lot_id = lot_obj.search([('product_id', '=', self.product_id.id), '|', ('name', '=', lot), ('ref', '=', code)])
                        else:
                            lot_id = lot_obj.search([('product_id', '=', self.product_id.id), ('name', '=', lot)])
                        if not lot_id:
                                if not lot:
                                        next_lot = lot_obj.default_get(['name'])
                                        next_lot.update({'product_id': self.product_id.id,
                                                         'product_uom_id': self.product_id.product_tmpl_id.uom_id.id,
                                                         'use_date': use_date})
                                else:
                                        next_lot = {'name': lot,
                                                        'product_id': self.product_id.id,
                                                         'product_uom_id': self.product_id.product_tmpl_id.uom_id.id,
                                                         'use_date': use_date}
                                lot_id = lot_obj.create(next_lot)
                return  True