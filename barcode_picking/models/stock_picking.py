# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools.float_utils import float_compare

import logging
_logger = logging.getLogger(__name__)


class StockMoveLine(models.Model):
    _name= 'stock.move.line'
    _inherit = ['stock.move.line', 'barcodes.barcode_events_mixin']

    product_barcode = fields.Char(related='product_id.barcode')
    location_processed = fields.Boolean()


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'barcodes.barcode_events_mixin']


    def _check_product(self, product, qty=1.0, lot=False, code=False, use_date=False):
        if lot:
            lot_obj = self.env['stock.production.lot']
            corresponding_ml = self.move_line_ids.filtered(lambda ml: ml.product_id.id == product.id and not ml.result_package_id and not ml.location_processed and ml.lots_visible)
            corresponding_ml_qty = self.move_line_ids.filtered(lambda ml: ml.product_id.id == product.id and ml.qty_done < ml.product_uom_qty and not ml.result_package_id and not ml.location_processed and ml.lots_visible)
            if corresponding_ml and not corresponding_ml_qty:
                if code:
                    lot_id = lot_obj.search([('product_id', '=', product.id), '|', ('name', '=', lot), ('ref', '=', code)])
                else:
                    lot_id = lot_obj.search([('product_id', '=', product.id), ('name', '=', lot)])
                if not lot_id:
                    lot_id = lot_obj.create({'name': lot, 'product_id': product.id, 'use_date': use_date})
                corresponding_lot = self.move_line_ids.filtered(lambda ml: ml.product_id.id == product.id and ml.lot_id == lot_id and not ml.result_package_id and not ml.location_processed and ml.lots_visible)
                _logger.info("ML %s" % corresponding_ml)
                corresponding_ml_false = False
                for corresponding_ml_line in corresponding_ml:
                    if not corresponding_lot and not corresponding_ml_line.lot_id:
                        corresponding_ml_line.write({'lot_id': lot_id.id})
                    else:
                        corresponding_ml_false = True
                if corresponding_ml_false:
                    corresponding_ml = False
            elif corresponding_ml_qty:
                if code:
                    lot_id = lot_obj.search([('product_id', '=', product.id), '|', ('name', '=', lot), ('ref', '=', code)])
                else:
                    lot_id = lot_obj.search([('product_id', '=', product.id), ('name', '=', lot)])
                if not lot_id:
                    lot_id = lot_obj.create({'name': lot, 'product_id': product.id, 'use_date': use_date})
                corresponding_lot = self.move_line_ids.filtered(lambda ml: ml.product_id.id == product.id and ml.lot_id == lot_id and ml.qty_done < ml.product_uom_qty and not ml.result_package_id and not ml.location_processed and ml.lots_visible)
                if not corresponding_lot:
                    corresponding_ml_qty.write({'lot_id': lot_id.id})
                corresponding_ml = corresponding_ml_qty
            else:
                if code:
                    lot_id = lot_obj.search([('product_id', '=', product.id), '|', ('name', '=', lot), ('ref', '=', code)])
                else:
                    lot_id = lot_obj.search([('product_id', '=', product.id), ('name', '=', lot)])

        else:
            corresponding_ml = self.move_line_ids.filtered(lambda ml: ml.product_id.id == product.id and not ml.result_package_id and not ml.location_processed and not ml.lots_visible)
            lot_id = False
        corresponding_ml = corresponding_ml[0] if corresponding_ml else False

        if corresponding_ml:
            if lot_id and qty > 1.0:
                corresponding_ml.qty_done = qty
            else:
                corresponding_ml.qty_done += qty
        else:
            # If a candidate is not found, we create one here. If the move
            # line we add here is linked to a tracked product, we don't
            # set a `qty_done`: a next scan of this product will open the
            # lots wizard.
            available_quants = False
            if lot:
                available_quants = self.env['stock.quant'].search([
                    ('lot_id', '=', lot_id.id),
                    ('location_id', 'child_of', self.location_id.id),
                    ('product_id', '=', product.id),
                    ('quantity', '>', 0),
                ], limit=1)
                #if available_quants:
                #    self.location_id = available_quants.location_id.id
            picking_type_lots = (self.picking_type_id.use_create_lots or self.picking_type_id.use_existing_lots)
            self.move_line_ids += self.move_line_ids.new({
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': available_quants and available_quants.location_id.id or self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'qty_done': (product.tracking == 'none' and picking_type_lots) and qty or lot_id and qty or 0.0,
                'product_uom_qty': lot_id and qty or 0.0,
                'date': fields.datetime.now(),
                'lot_id': lot_id and lot_id.id,
            })
        return True

    def _check_source_package(self, package):
        corresponding_po = self.move_line_ids.filtered(lambda r: r.package_id.id == package.id and r.result_package_id.id == package.id)
        for po in corresponding_po:
            po.qty_done = po.product_uom_qty
        if corresponding_po:
            self.entire_package_detail_ids.filtered(lambda p: p.name == package.name).is_processed = True
            return True
        else:
            return False

    def _check_destination_package(self, package):
        corresponding_ml = self.move_line_ids.filtered(lambda ml: not ml.result_package_id and float_compare(ml.qty_done, 0, precision_rounding=ml.product_uom_id.rounding) == 1)
        for ml in corresponding_ml:
            rounding = ml.product_uom_id.rounding
            if float_compare(ml.qty_done, ml.product_uom_qty, precision_rounding=rounding) == -1:
                self.move_line_ids += self.move_line_ids.new({
                    'product_id': ml.product_id.id,
                    'package_id': ml.package_id.id,
                    'product_uom_id': ml.product_uom_id.id,
                    'location_id': ml.location_id.id,
                    'location_dest_id': ml.location_dest_id.id,
                    'qty_done': 0.0,
                    'move_id': ml.move_id.id,
                    'date': fields.datetime.now(),
                })
            ml.result_package_id = package.id
        return True

    def _check_destination_location(self, location):
        corresponding_ml = self.move_line_ids.filtered(lambda ml: not ml.location_processed and float_compare(ml.qty_done, 0, precision_rounding=ml.product_uom_id.rounding) == 1)
        for ml in corresponding_ml:
            rounding = ml.product_uom_id.rounding
            if float_compare(ml.qty_done, ml.product_uom_qty, precision_rounding=rounding) == -1:
                self.move_line_ids += self.move_line_ids.new({
                    'product_id': ml.product_id.id,
                    'package_id': ml.package_id.id,
                    'product_uom_id': ml.product_uom_id.id,
                    'location_id': ml.location_id.id,
                    'location_dest_id': ml.location_dest_id.id,
                    'qty_done': 0.0,
                    'move_id': ml.move_id.id,
                    'date': fields.datetime.now(),
                })
            ml.update({
                'location_processed': True,
                'location_dest_id': location.id,
            })
        return True

    def on_barcode_scanned(self, barcode):
        lot = False
        use_date = False
        qty = 1.0
        if not self.picking_type_id.barcode_nomenclature_id:
            # Logic for products
            product = self.env['product.product'].search([
                '|', ('barcode', '=', barcode), ('default_code', '=', barcode)
            ], limit=1)
            if product:
                if self._check_product(product):
                    return

            product_packaging = self.env['product.packaging'].search([
                ('barcode', '=', barcode)
            ], limit=1)
            if product_packaging.product_id:
                if self._check_product(product_packaging.product_id,product_packaging.qty):
                    return

            if self.move_line_ids:
                package_source = self.env['stock.quant.package'].search([
                    ('name', '=', barcode),
                    ('location_id', 'child_of', self.location_id.id)
                ], limit=1)
                if package_source:
                    if self._check_source_package(package_source):
                        return

            package = self.env['stock.quant.package'].search([
                ('name', '=', barcode),
                '|', ('location_id', '=', False), ('location_id','child_of', self.location_dest_id.id)
            ], limit=1)
            if package:
                if self._check_destination_package(package):
                    return

            location = self.env['stock.location'].search([
                '|', ('name', '=', barcode), ('barcode', '=', barcode)
            ], limit=1)
            if location and \
                self.location_dest_id.parent_right > location.parent_left >= self.location_dest_id.parent_left:
                if self._check_destination_location(location):
                    return
        else:
            default_barcode_quantity = self.env['ir.config_parameter'].sudo().get_param('default_barcode_quantity')
            parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)

            if parsed_result['type'] in ['weight', 'product']:
                if parsed_result['type'] == 'weight':
                    product_barcode = parsed_result['base_code']
                    qty = parsed_result['value']
                else:
                    product_barcode = parsed_result['base_code']
                    lot = parsed_result['lot']
                    use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                product = self.env['product.product'].search([
                    '|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)
                ], limit=1)
                if product:
                    if self._check_product(product, qty, lot, use_date):
                        return

            if parsed_result['type'] == 'lot':
                lot = parsed_result['lot']
                code = parsed_result['code']
                lot_id = self.env['stock.production.lot'].search([
                    "|", ('name', '=', lot), ('ref', '=', code)
                ])
                if len([x.id for x in lot_id]) == 1:
                    product = self.env['product.product'].browse([lot_id.product_id.id])
                    use_date = lot_id.use_date
                    if not self.picking_type_code == 'incoming' and default_barcode_quantity:
                        available_quants = self.env['stock.quant'].search([
                            ('lot_id', '=', lot_id.id),
                            ('location_id', 'child_of', self.location_id.id),
                            ('product_id', '=', product.id),
                            ('quantity', '!=', 0),])
                        qty = sum(x.quantity-x.reserved_quantity for x in available_quants) or 1.0
                    if product:
                        if self._check_product(product, qty, lot, code, use_date):
                            return

            if parsed_result['type'] == 'package':
                if self.move_line_ids:
                    package_source = self.env['stock.quant.package'].search([
                        ('name', '=', parsed_result['code']),
                        ('location_id', 'child_of', self.location_id.id)
                    ], limit=1)
                    if package_source:
                        if self._check_source_package(package_source):
                            return
                package = self.env['stock.quant.package'].search([
                    ('name', '=', parsed_result['code']),
                    '|', ('location_id', '=', False), ('location_id','child_of', self.location_dest_id.id)
                ], limit=1)
                if package:
                    if self._check_destination_package(package):
                        return

            if parsed_result['type'] == 'location':
                location = self.env['stock.location'].search(['|', ('name', '=', parsed_result['code']), ('barcode', '=', parsed_result['code'])], limit=1)
                if location and self.location_dest_id.parent_right > location.parent_left >= self.location_dest_id.parent_left:
                    if self._check_destination_location(location):
                        return

            product_packaging = self.env['product.packaging'].search([('barcode', '=', parsed_result['code'])], limit=1)
            if product_packaging.product_id:
                if self._check_product(product_packaging.product_id,product_packaging.qty):
                    return

        msg = _('The barcode "%(barcode)s" does\'t correspond to a proper product, '
                'package or location. To add the scanned barcode to an existing product, '
                'please select one from the drop-down menu below: ') % {'barcode': barcode}
        title = _('Wrong barcode')
        product_id = self.env['product.product'].search([('barcode', '=', barcode)])
        action = self.env.ref('barcode_picking.act_open_wizard_view_stock_picking_add_product').read()[0]
        action['name'] = title or action['name']
        action['context'] = {'default_picking_type_id': self.picking_type_id.id, 'default_note': msg,
                             'default_lot': barcode,
                             'default_product_id': product_id and product_id[0].id or False,
                             'default_lot_new': lot,
                             'default_use_date': use_date}
        return {'warning': {
            'action': action,
            'title': title,
            'message': _('The barcode "%(barcode)s" does\'t correspond to a proper product, package or location.') % {
                'barcode': barcode}
        }}

