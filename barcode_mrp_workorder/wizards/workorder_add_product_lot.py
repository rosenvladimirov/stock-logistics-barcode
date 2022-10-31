# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import float_compare


class WorkorderAddProductLot(models.TransientModel):
    _name = "workorder_add.product.lot"
    _description = "Add lots for product in work order"

    product_id = fields.Many2one('product.product', required=True)
    lot_id = fields.Many2one('stock.production.lot', 'Lot')
    lot_name = fields.Char('Lot/Serial Number')
    workorder_id = fields.Many2one('mrp.workorder', 'Work order', required=True)
    quantity = fields.Float('Quantity to add')

    @api.multi
    def add_new_lot(self):
        self.ensure_one()
        workorder_id = self.workorder_id
        if not workorder_id and self._context.get('active_model') == 'mrp.workorder':
            workorder_id = self.env['mrp.workorder'].browse(self._context['active_ids'])
        production_id = workorder_id.production_id
        if self.lot_name and not self.lot_id:
            lot_id = workorder_id._auto_add_lots(self.product_id, lot=self.lot_name)
        elif self.lot_id:
            lot_id = self.lot_id
        else:
            lot_id = workorder_id._auto_add_lots(self.product_id)
        if lot_id:
            self.workorder_id.final_lot_id = lot_id
        if self.quantity > 0:
            self.workorder_id.qty_producing = self.quantity
