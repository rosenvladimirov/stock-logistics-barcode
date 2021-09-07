# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import Counter

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round, groupby
from odoo.addons import decimal_precision as dp
from odoo.addons.stock.models.stock_move_line import StockMoveLine as stockmoveline


class StockMove(models.Model):
    _inherit = 'stock.move'

    extra_bom_line = fields.Boolean('Is extra BOM line', help='Come from extra BOM line when start to produce')
    bom_unit_factor = fields.Float('Product Quantity', related="bom_line_id.product_qty")
    bom_product_qty = fields.Float('Unit Factor', compute="_compute_bom_product_qty")

    @api.depends('production_id', 'production_id.product_qty', 'bom_line_id.product_qty')
    def _compute_bom_product_qty(self):
        for record in self:
            if record.production_id and record.bom_line_id:
                record.bom_product_qty = record.production_id.product_qty * record.bom_line_id.product_qty


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    lot_produced_id = fields.Many2one(track_visibility="onchange")
    lot_id = fields.Many2one(track_visibility="onchange")
    lot_name = fields.Char(track_visibility="onchange")
    work_as = fields.Selection([
        ('bins', _('Use bins')),
        ('production', _('Combination')),
        ('component', _('Component')),
    ], string='Rule', help='Use the rules of conduct when filling in the lines for consumption or production')

    @api.onchange('lot_name', 'lot_id')
    def onchange_serial_number(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This includes:
            - automatically switch `qty_done` to 1.0
            - warn if he has already encoded `lot_name` in another move line
        """
        res = {}
        if self.product_id.tracking == 'serial':
            check_qty = False
            if not self.qty_done:
                self.qty_done = 1
                check_qty = True

            message = None
            if self.lot_name or self.lot_id:
                move_lines_to_check = self._get_similar_move_lines() - self
                if self.lot_name and check_qty:
                    counter = Counter(move_lines_to_check.mapped('lot_name'))
                    if counter.get(self.lot_name) and counter[self.lot_name] > 1:
                        message = _('You cannot use the same serial number twice. Please correct the serial numbers encoded.')
                elif self.lot_id and check_qty:
                    counter = Counter(move_lines_to_check.mapped('lot_id.id'))
                    if counter.get(self.lot_id.id) and counter[self.lot_id.id] > 1:
                        message = _('You cannot use the same serial number twice. Please correct the serial numbers encoded.')
                elif self.lot_name and not check_qty:
                    counter = {}
                    for lot_name, lines in groupby(move_lines_to_check.sorted(lambda r: r.lot_name), lambda r: r.lot_name):
                        save_lines = list(lines)
                        counter[lot_name] = sum([x.qty_done for x in save_lines])
                    if counter.get(self.lot_name) and counter[self.lot_name] > 1:
                        message = _(
                            'You cannot use the same serial number twice. Please correct the serial numbers encoded.')
                elif self.lot_id and not check_qty:
                    counter = {}
                    for lot_id, lines in groupby(move_lines_to_check.sorted(lambda r: r.lot_id.id), lambda r: r.lot_id):
                        save_lines = list(lines)
                        counter[lot_id] = sum([x.qty_done for x in save_lines])
                    if counter.get(self.lot_id) and counter[self.lot_id] > 1:
                        message = _('You cannot use the same serial number twice. Please correct the serial numbers encoded.')
            if message:
                res['warning'] = {'title': _('Warning'), 'message': message}
        return res

stockmoveline.onchange_serial_number = StockMoveLine.onchange_serial_number
