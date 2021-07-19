# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import json

class stockInventoryLine(models.Model):
    _inherit = "stock.inventory.line"
    product_barcode = fields.Char(related='product_id.barcode')

class StockInventory(models.Model):
    _name = 'stock.inventory'
    _inherit = ['stock.inventory', 'barcodes.barcode_events_mixin']

    scan_location_id = fields.Many2one('stock.location', 'Scanned Location', store=False)

    @api.model
    def open_new_inventory(self):
        action = self.env.ref('stock_barcode.stock_inventory_action_new_inventory').read()[0]
        if self.env.ref('stock.warehouse0', raise_if_not_found=False):
            new_inv = self.env['stock.inventory'].create({
                'filter': 'partial',
                'name': fields.Date.context_today(self),
            })
            new_inv.action_start()
            action['res_id'] = new_inv.id
        return action

    def _add_product(self, product, qty=1.0, lot=False, code=False, use_date=False):
        corresponding_line = self.line_ids.filtered(lambda r: r.product_id.id == product.id and (self.scan_location_id.id == r.location_id.id or not self.scan_location_id))
        if corresponding_line:
            corresponding_line[0].product_qty += qty
        else:
            StockQuant = self.env['stock.quant']
            company_id = self.company_id.id
            if not company_id:
                company_id = self._uid.company_id.id
            dom = [('company_id', '=', company_id), ('location_id', '=', self.scan_location_id.id or self.location_id.id), ('lot_id', '=', False),
                        ('product_id','=', product.id), ('owner_id', '=', False), ('package_id', '=', False)]
            quants = StockQuant.search(dom)
            th_qty = sum([x.quantity for x in quants])
            self.line_ids += self.line_ids.new({
                'location_id': self.scan_location_id.id or self.location_id.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'theoretical_qty': th_qty,
                'product_qty': qty,
            })
        return True

    def on_barcode_scanned(self, barcode):
        if not self.picking_type_id.barcode_nomenclature_id:
                product = self.env['product.product'].search([('barcode', '=', barcode)])
                if product:
                        self._add_product(product)
                        return

                product_packaging = self.env['product.packaging'].search([('barcode', '=', barcode)])
                if product_packaging.product_id:
                        self._add_product(product_packaging.product_id, product_packaging.qty)
                        return

                location = self.env['stock.location'].search([('barcode', '=', barcode)])
                if location:
                        self.scan_location_id = location[0]
                        return
        else:
                parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
                # _logger.info("Parce result %s" % parsed_result)
                if parsed_result['type'] in ['weight', 'product']:
                        if parsed_result['type'] == 'weight':
                                product_barcode = parsed_result['base_code']
                                qty = parsed_result['value']
                        else:  # product
                                product_barcode = parsed_result['base_code']
                                qty = 1.0
                                lot = parsed_result['lot']
                                use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                        product = self.env['product.product'].search(
                                ['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)],
                                limit=1)
                        if product:
                                if self._add_product(product, qty, lot, use_date):
                                        return

                if parsed_result['type'] == 'lot':
                        lot = parsed_result['lot']
                        code = parsed_result['code']
                        lot_id = self.env['stock.production.lot'].search(["|", ('name', '=', lot), (
                        'ref', '=', code)])  # Logic by product but search by lot in existing lots
                        if len([x.id for x in lot_id]) == 1:
                                product = self.env['product.product'].browse([lot_id.product_id.id])
                                use_date = lot_id.use_date
                                available_quants = self.env['stock.quant'].search([
                                        ('lot_id', '=', lot_id.id),
                                        ('location_id', 'child_of', self.location_id.id),
                                        ('product_id', '=', product.id),
                                        ('quantity', '!=', 0),
                                ])
                                qty = sum(x.quantity - x.reserved_quantity for x in available_quants) or 1.0
                                # qty = product.qty_available_not_res or 1.0
                                if product:
                                        if self._add_product(product, qty, lot, code, use_date):
                                                return
