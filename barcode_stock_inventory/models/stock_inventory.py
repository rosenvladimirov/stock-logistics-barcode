# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
# from odoo.exceptions import UserError
#
# import json

import logging

_logger = logging.getLogger(__name__)


class StockInventoryLine(models.Model):
    _inherit = "stock.inventory.line"

    product_barcode = fields.Char(related='product_id.barcode')


class StockInventory(models.Model):
    _name = 'stock.inventory'
    _inherit = ['stock.inventory', 'barcodes.barcode_events_mixin']

    scan_location_id = fields.Many2one('stock.location', 'Scanned Location', store=False)

    def _add_product(self, product, qty=1.0, lot=False, code=False, use_date=False):
        _logger.info("ADD PRODUCT %s:%s" % (product, lot))
        lot_id = False
        if lot and not code:
            lot_id = self.env['stock.production.lot']. \
                search([('product_id', '=', product.id), ('name', '=', lot)])
        elif lot and code:
            lot_id = self.env['stock.production.lot']. \
                search([('product_id', '=', product.id), ('name', '=', lot), ('ref', '=', code)])
        if lot_id:
            corresponding_line = self.line_ids. \
                filtered(lambda r: r.product_id.id == product.id and r.prod_lot_id == lot_id
                                   and (self.scan_location_id.id == r.location_id.id or not self.scan_location_id))
        else:
            corresponding_line = self.line_ids.filtered(lambda r: r.product_id.id == product.id and (
                self.scan_location_id.id == r.location_id.id or not self.scan_location_id))
        if corresponding_line and corresponding_line[0].product_qty != corresponding_line[0].theoretical_qty:
            corresponding_line[0].product_qty += qty
        elif corresponding_line and corresponding_line[0].product_qty == corresponding_line[0].theoretical_qty:
            corresponding_line._compute_theoretical_qty()
            corresponding_line.product_qty = corresponding_line.theoretical_qty
        else:
            # if not self.product_id:
            #     self.theoretical_qty = 0
            #     return
            quants = self.env['stock.quant'].search([
                ('company_id', '=', self.company_id.id),
                ('location_id', '=', self.scan_location_id.id or self.location_id.id),
                ('lot_id', '=', lot_id and lot_id.id or False),
                ('product_id', '=', product.id),
                ('owner_id', '=', self.partner_id.id),
                ('package_id', '=', self.package_id.id)])
            theoretical_qty = sum([x.quantity for x in quants])

            line_id = self.line_ids.new({
                'location_id': self.scan_location_id.id or self.location_id.id,
                'product_id': product.id,
                'prod_lot_id': lot_id and lot_id.id or False,
                'product_uom_id': product.uom_id.id,
                'theoretical_qty': theoretical_qty,
                'product_qty': theoretical_qty,
            })
            # line_id._compute_theoretical_qty()
            self.line_ids += line_id
        return True

    @api.depends('line_ids')
    def on_barcode_scanned(self, barcode):
        message = _('The barcode "%(barcode)s" not found')
        warehouse = self.location_id.get_warehouse()
        picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'internal')])
        if warehouse:
            picking_type_id = picking_type_id.filtered(lambda r: r.warehouse_id == warehouse)
        _logger.info("BARCODE %s" % picking_type_id)

        if not picking_type_id.barcode_nomenclature_id:
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
            message = _('The barcode "%(barcode)s" not found')
        else:
            parsed_result = picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
            _logger.info("PARCE %s:%s" % (parsed_result, picking_type_id))

            if parsed_result['type'] in ['product']:
                lot_id = False
                product_barcode = parsed_result['base_code']
                qty = 1.0
                lot = parsed_result['lot']
                code = parsed_result['code']
                use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                product = self.env['product.product'].search(
                    ['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)], limit=1)
                if self._add_product(product, qty, lot, use_date):
                    return
                message = _('The barcode "%(barcode)s" not found')

            elif parsed_result['type'] in ['weight', 'product']:
                lot = parsed_result['lot']
                use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                if parsed_result['type'] == 'weight':
                    product_barcode = parsed_result['base_code']
                    qty = parsed_result['value']
                else:  # product
                    product_barcode = parsed_result['base_code']
                    qty = 1.0
                product = self.env['product.product'].search(
                    ['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)],
                    limit=1)
                if product:
                    if self._add_product(product, qty, lot, use_date):
                        return
                message = _('The barcode "%(barcode)s" not found')

            elif parsed_result['type'] == 'lot':
                qty = 1.0
                lot = parsed_result['lot']
                code = False

                if code:
                    lot_id = self.env['stock.production.lot'].search(["|", ('name', '=', lot),
                                                                      ('ref', '=', code)], limit=1)
                else:
                    lot_id = self.env['stock.production.lot'].search([('name', '=', lot)], limit=1)
                if lot_id:
                    product = self.env['product.product'].browse([lot_id.product_id.id])
                    use_date = lot_id.use_date
                    if product:
                        if self._add_product(product, qty, lot, code, use_date):
                            return
                message = _('The lot "%(barcode)s" not found')

        return {'warning': {
            'title': _('Wrong barcode'),
            'message': message % {
                'barcode': barcode}
        }}
