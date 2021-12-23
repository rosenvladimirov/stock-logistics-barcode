# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons.mrp_repair.models.mrp_repair import Repair as repair
import logging

_logger = logging.getLogger(__name__)


class Repair(models.Model):
    _name = 'mrp.repair'
    _inherit = ['mrp.repair', 'barcodes.barcode_events_mixin']

    @api.model
    def _default_picking_type_id(self):
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        if warehouse:
            return warehouse.int_type_id.id
        return False

    work_component = fields.Boolean('Component', help='Please checked it if work with component')
    picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', required=True, readonly=True,
                                      states={'draft': [('readonly', False)]}, default=_default_picking_type_id)

    @api.onchange('product_id')
    def onchange_product_id(self):
        self.guarantee_limit = False
        if not self._context.get('no_erase_lot', False):
            self.lot_id = False
        if self.product_id:
            self.product_uom = self.product_id.uom_id.id

    @api.multi
    def toggle_work_component(self):
        for record in self:
            record.work_component = not record.work_component

    @api.onchange('location_id')
    def _onchange_location(self):
        args = self.company_id and [('company_id', '=', self.company_id.id)] or []
        warehouse = self.env['stock.warehouse'].search(args, limit=1)
        if self.location_id.usage == 'internal':
            self.picking_type_id = warehouse.int_type_id
        elif self.location_id.usage == 'production':
            self.picking_type_id = warehouse.manu_type_id
        else:
            self.picking_type_id = warehouse.int_type_id

    def _check_product(self, product, qty=1.0, lot=False, code=False, use_date=False):
        lot_obj = self.env['stock.production.lot']
        location_id = self.location_id
        lot_id = False
        if lot:
            if code:
                lot_id = lot_obj.search([('product_id', '=', product.id), '|', ('name', '=', lot), ('ref', '=', code)])
            else:
                lot_id = lot_obj.search([('product_id', '=', product.id), ('name', '=', lot)])
            available_quants = self.env['stock.quant'].search([
                ('lot_id', '=', lot_id.id),
                ('location_id', 'child_of', location_id.id),
                ('product_id', '=', product.id),
                ('quantity', '>', 0),
            ], limit=1)
            # if not available_quants:
            #     lot_id = False
        if lot_id:
            self.product_id = product
            self.lot_id = lot_id
            # self.product_qty = qty
            # self.location_id = lot_id.location_id
            # self.location_dest_id = lot_id.location_id
        _logger.info("LOT SAVED %s" % self.lot_id)
        return True

    def _check_component(self, product, qty=1.0, lot=False, code=False, use_date=False):
        corresponding_ml_lot = False
        raw_corresponding_ml = self.operations.filtered(lambda ml: ml.product_id.id == product.id)
        if lot:
            lot_obj = self.env['stock.production.lot']
            if code:
                lot_id = raw_corresponding_ml.filtered(lambda r: r.lot_id.name == lot).mapped('lot_id')
                if not lot_id:
                    lot_id = lot_obj.search(
                        [('product_id', '=', product.id), '|', ('name', '=', lot), ('ref', '=', code)])
                else:
                    lot_id = lot_id[0].lot_id
            else:
                lot_id = raw_corresponding_ml.filtered(lambda r: r.lot_id.name == lot).mapped('lot_id')
                if not lot_id:
                    lot_id = lot_obj.search([('product_id', '=', product.id), ('name', '=', lot)])
                else:
                    lot_id = lot_id[0].lot_id
            if not lot_id:
                lot_id = lot_obj.create({'name': lot, 'ref': code, 'product_id': product.id, 'use_date': use_date})
                raw_corresponding_ml.write({'lot_id': lot_id.id})
            corresponding_ml_lot = self.operations.filtered(
                lambda ml: ml.product_id.id == product.id and ml.lots_visible and ml.lot_id == lot_id)
        else:
            corresponding_ml = self.operations.filtered(
                lambda ml: ml.product_id.id == product.id and not ml.lots_visible)
            lot_id = False

        if corresponding_ml_lot and len(corresponding_ml_lot) == 1:
            corresponding_ml = corresponding_ml_lot
        else:
            corresponding_ml = corresponding_ml[0] if corresponding_ml else False

        if corresponding_ml and (lot and lot_id):
            corresponding_ml.write({'lot_id': lot_id.id})

        if corresponding_ml:
            if raw_corresponding_ml and not raw_corresponding_ml.product_id.tracking == 'serial':
                qty = raw_corresponding_ml.product_uom_qty / self.qty_production
            if lot_id and qty:
                corresponding_ml.qty_done = qty
            elif lot_id and not qty:
                pass
            else:
                corresponding_ml.qty_done += qty
        else:
            available_quants = False
            location_id = self.location_id
            if lot:
                available_quants = self.env['stock.quant'].search([
                    ('lot_id', '=', lot_id.id),
                    ('location_id', 'child_of', location_id.id),
                    ('product_id', '=', product.id),
                    ('quantity', '>', 0),
                ], limit=1)
                # if available_quants:
                #    self.location_id = available_quants.location_id.id
            new_line = self.operations.new({
                'type': 'replace',
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': available_quants and available_quants.location_id.id or location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'product_uom_qty': lot_id and qty or 0.0,
                'lot_id': lot_id and lot_id.id,
            })
            self.operations += new_line
            corresponding_ml = new_line
        if corresponding_ml:
            corresponding_ml.onchange_product_id()
        return True

    def on_barcode_scanned(self, barcode):
        message = _('The barcode "%(barcode)s" doesn\'t correspond to a proper product, package or location.')
        picking_type_id = self.picking_type_id
        if not picking_type_id.barcode_nomenclature_id:
            product = self.env['product.product'].search(
                ['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1)
            if product:
                if self._check_component(product):
                    return

            product_packaging = self.env['product.packaging'].search([('barcode', '=', barcode)], limit=1)
            if product_packaging.product_id:
                if self._check_component(product_packaging.product_id, product_packaging.qty):
                    return
        else:
            parsed_result = picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
            if parsed_result['type'] in ['product']:
                product_barcode = parsed_result['base_code']
                qty = 1.0
                lot = parsed_result['lot']
                code = parsed_result['code']
                use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                product = self.env['product.product'].search(
                    ['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)], limit=1)
                if not product:
                    product = self.product_id
                if self.work_component or ['sub_type'] == 'component':
                    if self._check_component(product, qty, lot, use_date):
                        return
                elif not self.work_component or parsed_result['sub_type'] == 'product':
                    if self._check_product(product, qty, lot, use_date):
                        return
                else:
                    if self._check_component(product, qty, lot, code, use_date):
                        return

            if parsed_result['type'] in ['lot']:
                product = self.product_id
                location_id = self.location_id
                qty = 1.0
                use_date = False
                lot = parsed_result['lot']
                code = parsed_result['code']
                product_ids = [x.product_id.id for x in self.operations]

                _logger.info("PARCE %s(%s)" % (parsed_result, self.work_component))
                if self.work_component or not parsed_result['sub_type'] or parsed_result['sub_type'] == 'component':
                    lot_id = self.env['stock.production.lot'].search([('name', '=', lot), (
                        'product_id', 'in', product_ids)])  # Logic by product but search by lot in existing lots
                    if len([x.id for x in lot_id]) >= 1:
                        for line in lot_id:
                            product = self.env['product.product'].browse([line.product_id.id])
                            available_quants = self.env['stock.quant'].search([
                                ('lot_id', '=', line.id),
                                ('location_id', 'child_of', location_id.id),
                                ('product_id', '=', product.id),
                                ('quantity', '>', 0),
                            ])
                            use_date = line.use_date
                            qty = sum(x.quantity for x in available_quants) or 1.0
                            product = line.product_id
                            if self._check_component(product, qty, lot, code, use_date):
                                return
                        return
                    else:
                        return
                elif not self.work_component or parsed_result['sub_type'] == 'product':
                    lot_id = self.env['stock.production.lot'].search([('name', '=', lot)])
                    _logger.info("LOT FOUND %s" % lot_id)
                    if lot_id:
                        product = lot_id[-1].product_id
                    if self.with_context(dict(self._context, no_erase_lot=True))._check_product(product, qty, lot, code, use_date):
                        return
                    else:
                        message = _('The barcode "%(barcode)s" maybe is serial and is added to a product')
                else:
                    lot_id = self.env['stock.production.lot'].search([('name', '=', lot)])
                    # Logic by product but search by lot in existing lots
                    if len([x.id for x in lot_id]) == 1:
                        product = self.env['product.product'].browse([lot_id.product_id.id])
                        available_quants = self.env['stock.quant'].search([
                            ('lot_id', '=', lot_id.id),
                            ('location_id', 'child_of', location_id.id),
                            ('product_id', '=', product.id),
                            ('quantity', '>', 0),
                        ])
                        use_date = lot_id.use_date
                        qty = sum(x.quantity for x in available_quants) or 1.0
                        product = lot_id.product_id
                    else:
                        ml = self.operations.filtered(lambda ml: ml.lots_visible and not ml.lot_id)[0]
                        if ml:
                            product = ml and ml[0].product_id
                        else:
                            product = ml[0]
                    if self._check_component(product, qty, lot, code, use_date):
                        return

        return {'warning': {
            'title': _('Wrong barcode'),
            'message': message % {
                'barcode': barcode}
        }}


repair.onchange_product_id = Repair.onchange_product_id
