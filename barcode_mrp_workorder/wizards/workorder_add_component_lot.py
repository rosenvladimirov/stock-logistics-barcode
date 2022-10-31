# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import float_compare


class WorkorderAddComponentLot(models.TransientModel):
    _name = "workorder_add.component.lot"
    _description = "Add extra lots in work order"

    def _get_default_product_uom_id(self):
        return self.env['product.uom'].search([], limit=1, order='id').id

    product_id = fields.Many2one('product.product', required=True)
    lot_id = fields.Many2one('stock.production.lot', 'Lot')
    lot_name = fields.Char('Lot/Serial Number')
    workorder_id = fields.Many2one('mrp.workorder')
    product_ids = fields.One2many('product.product', compute='_compute_product_ids')
    quantity = fields.Float('Quantity to add')
    product_uom_id = fields.Many2one('product.uom', 'Product Unit of Measure', default=_get_default_product_uom_id,
                                     required=True,
                                     help="Unit of Measure (Unit of Measure) is the "
                                          "unit of measurement for the inventory control")

    def _compute_product_ids(self):
        for component in self:
            if component.workorder_id:
                production = self.workorder_id.production_id
                workorder = component.workorder_id
                tracked_moves = production.move_raw_ids.filtered(
                    lambda move: move.state not in ('done', 'cancel')
                                 and move.product_id.tracking != 'none' and move.product_id != production.product_id
                                 and move.operation_id == workorder.operation_id)
                component.product_ids = [(4, x.product_id.id) for x in tracked_moves]

    @api.multi
    def add_new_lot(self):
        self.ensure_one()
        if self.workorder_id:
            lot_obj = self.env['stock.production.lot']
            workorder = self.workorder_id
            production = self.workorder_id.production_id
            MoveLine = self.env['stock.move.line']
            routing = production.routing_id
            qty = self.quantity != 0.0 and self.quantity or self.workorder_id.qty_remaining

            if routing and routing.location_id:
                source_location = routing.location_id
            else:
                source_location = production.location_src_id

            if not self.lot_id:
                next_lot = lot_obj.default_get(['name'])
                next_lot.update({'product_id': self.product_id.id,
                                 'product_uom_id': self.product_id.product_tmpl_id.uom_id.id})
                lot_id = self.env['stock.production.lot'].create(next_lot)
                if lot_id:
                    self.lot_id = lot_id
            if self.product_id.tracking == 'serial':
                while float_compare(qty, 0.0, precision_rounding=self.product_uom_id.rounding) > 0:
                    if not self.lot_id:
                        next_lot = lot_obj.default_get(['name'])
                        next_lot.update({'product_id': self.product_id.id,
                                         'product_uom_id': self.product_id.product_tmpl_id.uom_id.id})
                        lot_id = self.env['stock.production.lot'].create(next_lot)
                        if lot_id:
                            self.lot_id = lot_id
                    workorder.active_move_line_ids += MoveLine.new({
                        'product_uom_qty': 0,
                        'product_uom_id': self.product_uom_id.id,  # Need to check for correct
                        'qty_done': 1.0,
                        'production_id': production.id,
                        'workorder_id': workorder.id,
                        'product_id': self.product_id.id,
                        'lot_id': self.lot_id.id,
                        'lot_name': self.lot_name,
                        'done_wo': False,
                        'location_id': source_location.id,
                        'location_dest_id': self.product_id.property_stock_production.id,
                    })
                    qty -= 1.0
                    self.lot_id = False
            else:
                workorder.active_move_line_ids += MoveLine.new({
                    'product_uom_qty': 0,
                    'product_uom_id': self.product_uom_id.id,  # Need to check for correct
                    'product_id': self.product_id.id,
                    'lot_id': self.lot_id.id,
                    'lot_name': self.lot_name,
                    'qty_done': qty,
                    'production_id': production.id,
                    'workorder_id': workorder.id,
                    'done_wo': False,
                    'location_id': source_location.id,
                    'location_dest_id': self.product_id.property_stock_production.id,
                })
        return True
