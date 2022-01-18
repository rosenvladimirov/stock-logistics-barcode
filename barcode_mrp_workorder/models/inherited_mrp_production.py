# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round
from odoo.addons import decimal_precision as dp

import json

import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _inherit = 'mrp.production'

    split_lot_ids = fields.One2many('stock.production.lot.save', 'production_id', string='Lot/Serial Number')
    production_line_ids = fields.Many2many('mrp.production.line', string='Detailed operations for productions')

    @api.multi
    def write(self, vals):
        res = super(MrpProduction, self).write(vals)
        if 'move_raw_ids' in vals and not self.is_locked:
            for line in self.move_raw_ids.filtered(lambda move: move.operation_id and not move.workorder_id):
                for workorder in self.workorder_ids.filtered(lambda r: r.operation_id == line.operation_id):
                    line.workorder_id = workorder.id
                    continue
        return res

    @api.multi
    def _generate_workorders(self, exploded_boms):
        workorders = super(MrpProduction, self)._generate_workorders(exploded_boms)
        for workorder in workorders:
            if workorder.operation_id.user_product_id and workorder.move_raw_ids.filtered(lambda r: r.product_id == workorder.operation_id.user_product_id):
                workorder.user_price_unit = workorder.operation_id.user_product_id.standard_price
            if workorder.operation_id.material_product_id and workorder.move_raw_ids.filtered(lambda r: r.product_id == workorder.operation_id.material_product_id):
                workorder.material_price_unit = workorder.operation_id.material_product_id.standard_price
        return workorders


class MrpProductionLine(models.Model):
    """ Manufacturing Orders """
    _name = 'mrp.production.line'
    _description = 'Manufacturing Order Lines'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # rows
    product_id = fields.Many2one('product.product', 'Product', domain=[('type', 'in', ['product', 'consu', 'service'])])
    # columns
    workorder_id = fields.Many2one('mrp.workorder', 'Work Orders')
    # values
    product_qty = fields.Float('Quantity Of Product', digits=dp.get_precision('Product Unit of Measure'),
                               track_visibility='onchange')
    bom_product_qty = fields.Float('BOM Quantity Of Product', digits=dp.get_precision('Product Unit of Measure'),
                                   track_visibility='onchange')
    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial Number')
    product_wo = fields.Integer('Checked by workorder', track_visibility='onchange')
    # move_ids = fields.Many2many('stock.move', string='Stock moves')
    move_line_id = fields.Many2one('stock.move.line', 'Packing Operation')
    operation_id = fields.Many2one('mrp.routing.workcenter', 'Operation')
    display_name = fields.Char(compute="_compute_display_name")
    bom_line_id = fields.Many2one('mrp.bom.line', 'BoM Line')
    extra_bom_line = fields.Boolean('Is extra BOM line', help='Come from extra BOM line when start to produce')

    @api.depends('workorder_id', 'operation_id')
    def _compute_display_name(self):
        for record in self:
            if record.operation_id:
                record.display_name = "%s(%s)" % (record.workorder_id.name, record.operation_id.name)
            else:
                record.display_name = record.workorder_id.name


class StockProductionLotSave(models.Model):
    _name = "stock.production.lot.save"
    _description = "Place holder for current lots"

    lot_id = fields.Many2one('stock.production.lot', 'Lot/Serial Number',
                             index=True, ondelete='cascade', required=True)
    production_id = fields.Many2one(
        'mrp.production', 'Manufacturing Order',
        index=True, ondelete='cascade', required=True)
    workorder_id = fields.Many2one('mrp.workorder', 'Work Orders')
    operation_id = fields.Many2one(
        'mrp.routing.workcenter', 'Operation To Consume')
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', 'in', ['product', 'consu'])], index=True, required=True)
    qty_done = fields.Float('Quantity done')

    # def unlink(self):
    #    _logger.info("DELETE %s" % self, test)
    #    return super(StockProductionLotSave, self).unlink()

    def get_split_lot_value(self, move_line, workorder):
        return {
            'product_id': move_line.product_id.id,
            'lot_id': move_line.lot_id and move_line.lot_id.id or False,
            'production_id': workorder.production_id.id,
            'workorder_id': workorder.id,
            'operation_id': workorder.operation_id and workorder.operation_id.id or False,
        }
