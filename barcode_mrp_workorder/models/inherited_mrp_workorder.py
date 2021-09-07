# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import math

from odoo import models, fields, api, _
from odoo.addons.mrp.models.mrp_workorder import MrpWorkorder as mrpworkorder
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round

import json

import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _name = 'mrp.workorder'
    _inherit = ['mrp.workorder', 'barcodes.barcode_events_mixin']

    work_component = fields.Boolean('Component', help='Please checked it if work with component')
    work_production = fields.Boolean('Combination', help='Please checked it if work with pair product/component')
    use_bins = fields.Boolean('Bins', help='Please checked it if work with bins')
    final_component = fields.Integer('Component Lot/SN Count', track_visibility="onchange",
                                     compute="_compute_final_component")
    final_lot_id = fields.Many2one(track_visibility="onchange")
    active_move_line_ids = fields.One2many(track_visibility="onchange")
    split_lot_ids = fields.One2many('stock.production.lot.save', related="production_id.split_lot_ids",
                                    string='Lot/Serial Number')
    r_move_line_ids = fields.One2many('stock.move.line', 'workorder_id', 'Moves to Track',
                                      domain=["|", ('lot_id', '!=', False), ('lot_name', '!=', False)],
                                      help="Inventory moves for which you must scan a lot number at this work order")

    @api.multi
    def _compute_final_component(self):
        for record in self:
            record.final_component = len([x.id for x in record.active_move_line_ids if x.lot_id])

    @api.multi
    def toggle_work_component(self):
        for record in self:
            record.work_component = not record.work_component

    @api.multi
    def toggle_work_production(self):
        for record in self:
            record.work_production = not record.work_production

    @api.multi
    def toggle_use_bins(self):
        for record in self:
            record.use_bins = not record.use_bins
            if not record.use_bins:
                self.button_empty_bins()

    def _assign_default_final_lot_id(self):
        super(MrpWorkorder, self)._assign_default_final_lot_id()
        if self.production_id.product_id.tracking == 'serial' and self.work_component and not self.work_production:
            self.work_component = False

    def action_lots_glabel_print(self):
        self.ensure_one()
        if self.final_lot_id:
            lot = self.final_lot_id
            ctx = self._context.copy()
            ctx['active_model'] = 'stock.production.lot'
            ctx['active_id'] = lot.id
            docids = lot
            return self.env['ir.actions.report']._get_report_from_name('final_product_lot_label').with_context(
                ctx).report_action(docids)
        return False

    def action_product_glabel_print(self):
        self.ensure_one()
        ctx = self._context.copy()
        ctx['active_model'] = 'product.product'
        ctx['active_ids'] = [x.id for x in self.move_line_ids]
        ctx['active_id'] = self.product_id.id
        ctx['label_name'] = 'final_product_label'
        docids = self.product_id
        return self.env['ir.actions.report']._get_report_from_name('final_product_label').with_context(
            ctx).report_action(docids)

    def _auto_add_lots(self, product, lot=False, use_date=False):
        lot_obj = self.env['stock.production.lot']
        if lot:
            lot = lot_obj.create(
                {'name': lot, 'product_id': product.id, 'product_uom_id': product.product_tmpl_id.uom_id.id,
                 'use_date': use_date})
        else:
            next_lot = lot_obj.default_get(['name'])
            next_lot.update({'product_id': product.id, 'product_uom_id': product.product_tmpl_id.uom_id.id})
            lot = lot_obj.create(next_lot)
        return lot

    def add_lot_to_product(self):
        if self.final_lot_id:
            return {'warning': {
                'title': _("The barcode presents"),
                'message': _(
                    'The barcode "%(barcode)s" are added to proper product. Please push "Done" to finish this '
                    'productions or clear code on form.') % {
                               'barcode': self.final_lot_id.name}
            }}
        else:
            lot = self._auto_add_lots(self.product_id)
            if lot:
                self.final_lot_id = lot.id
        return True

    @api.multi
    def end_all(self):
        ret = super(MrpWorkorder, self).end_all()
        for workorder in self:
            filtered_lots = workorder.active_move_line_ids.filtered(lambda r: r.lot_id != False)
            if filtered_lots:
                reserved_lots = workorder.r_move_line_ids.filtered(
                    lambda r: r.lot_id.id not in [x.lot_id.id for x in filtered_lots])
                if not reserved_lots:
                    raise UserError(_(
                        'Using LOT/SN cannot found in this locations. Please goto Manufacture order and remove wrong data.'))
        return ret

    def _update_production_datails(self, move_ids):
        res = []
        for move_line in move_ids:
            bom_line_id = False
            extra_bom_line = False
            lot_id = False
            move_line_id = False
            bom_line = False
            bom_product_qty = 0.0
            if move_ids._name == 'stock.move':
                bom_product_qty = move_line.quantity_done
                quantity_done = move_line.quantity_done
                bom_line_id = move_line.bom_line_id and move_line.bom_line_id.id or False
                bom_line = move_line.bom_line_id
                extra_bom_line = move_line.extra_bom_line
                move_line_id = move_line.move_line_ids and move_line.move_line_ids[0] or False
            if move_ids._name == 'stock.move.line':
                bom_product_qty = move_line.qty_done
                quantity_done = move_line.qty_done
                bom_line_id = move_line.move_id.bom_line_id and move_line.move_id.bom_line_id.id or False
                bom_line = move_line.move_id.bom_line_id
                extra_bom_line = move_line.move_id.extra_bom_line
                lot_id = move_line.lot_id and move_line.lot_id.id or False
                move_line_id = move_line.id
            if bom_line:
                bom_product_qty = bom_line.product_qty

            res.append((0, 0, {
                'move_line_id': move_line_id,
                'product_id': move_line.product_id.id,
                'workorder_id': self.id,
                'product_qty': quantity_done,
                'operation_id': self.operation_id.id,
                'bom_line_id': bom_line_id,
                'extra_bom_line': extra_bom_line,
                'lot_id': lot_id,
                'bom_product_qty': bom_product_qty,
            }))
        # _logger.info("RES %s" % res)
        return res

    @api.model
    def _pre_record_production(self, move_line):
        move = move_line.move_id
        # Check for qty in split lots and update it
        bins = self.split_lot_ids.filtered(
            lambda
                r: r.product_id == move_line.product_id and r.lot_id == move_line.lot_id and r.workorder_id.id == self.id)
        for product in bins:
            product.write({"qty_done": move_line.qty_done})
        # Check for extra components and add in raw materials like move
        if move_line.product_id.id not in self.move_raw_ids.mapped('product_id').ids:
            product = move_line.product_id
            if product.type not in ['product', 'consu']:
                return False
            sequence = self.production_id.move_raw_ids[-1].sequence
            routing = self.production_id.routing_id
            if routing and routing.location_id:
                source_location = routing.location_id
            else:
                source_location = self.production_id.location_src_id

            sequence += 1
            data = {
                'sequence': sequence,
                'name': self.production_id.name,
                'date': self.production_id.date_planned_start,
                'date_expected': self.production_id.date_planned_start,
                'product_id': product.id,
                'product_uom_qty': move_line.qty_done,  # check for upm by product and line uom
                # 'product_uom_qty': move_line.qty_done * self.qty_production,  # check for upm by product and line uom
                # 'product_uom': product.uom_id.id,  # Need to check for correct
                'product_uom': move_line.product_uom_id.id,
                'location_id': source_location.id,
                'location_dest_id': self.production_id.product_id.property_stock_production.id,
                'raw_material_production_id': self.production_id.id,
                'company_id': self.production_id.company_id.id,
                'operation_id': self.operation_id.id,
                'price_unit': product.standard_price,
                'procure_method': 'make_to_stock',
                'origin': self.production_id.name,
                'warehouse_id': source_location.get_warehouse().id,
                'group_id': self.production_id.procurement_group_id.id,
                'propagate': self.production_id.propagate,
                'unit_factor': move_line.qty_done,
                'extra_bom_line': True,
                'workorder_id': self.id,
                'production_id': False,
            }
            move = self.env['stock.move'].create(data)
            move_line.move_id = move.id
            _logger.info("MOVE %s:%s" % (move, move_line))
        return move

    @api.model
    def _post_record_production(self):
        return True

    @api.multi
    def record_production(self):
        self.ensure_one()
        if self.qty_producing <= 0:
            raise UserError(_('Please set the quantity you are currently producing. It should be different from zero.'))

        if (self.production_id.product_id.tracking != 'none') and not self.final_lot_id and self.move_raw_ids:
            raise UserError(_('You should provide a lot/serial number for the final product'))

        # Update quantities done on each raw material line
        # For each untracked component without any 'temporary' move lines,
        # (the new workorder tablet view allows registering consumed quantities for untracked components)
        # we assume that only the theoretical quantity was used
        for move in self.move_raw_ids:
            if move.has_tracking == 'none' and (move.state not in ('done', 'cancel')) and move.bom_line_id \
                and move.unit_factor and not move.move_line_ids.filtered(lambda ml: not ml.done_wo):
                rounding = move.product_uom.rounding
                if (move.product_id == self.operation_id.material_product_id or
                    move.product_id == self.operation_id.user_product_id):
                    cycle_number = math.ceil(
                        self.qty_producing / move.workorder_id.operation_id.workcenter_id.capacity)
                    time_cycle = move.workorder_id.operation_id.get_time_cycle(quantity=self.qty_producing,
                                                                               product=self.product_id)
                    duration_expected = move.bom_line_id.product_qty * ((cycle_number * time_cycle * 100.0 / move.workorder_id.operation_id.workcenter_id.time_efficiency) * 60)
                    _logger.info("TIME duration_expected=%s, time_cycle=%s, cycle_number=%s, move=%s" % (
                        duration_expected, time_cycle, cycle_number, move._get_move_lines()))
                    move._generate_consumed_move_line(duration_expected, self.final_lot_id)
                    update_values = self._update_production_datails(move)
                    if update_values:
                        self.production_id.production_line_ids = update_values

                    # if len(move._get_move_lines()) < 2:
                    #     move.quantity_done = move.quantity_done + duration_expected
                    #     update_values = self._update_production_datails(move)
                    #     if update_values:
                    #         self.production_id.production_line_ids = update_values
                    # else:
                    #     move._set_quantity_done(move.quantity_done + duration_expected)
                    #     update_values = self._update_production_datails(move)
                    #     if update_values:
                    #         self.production_id.production_line_ids = update_values
                else:
                    if self.product_id.tracking != 'none':
                        qty_to_add = float_round(self.qty_producing * move.unit_factor, precision_rounding=rounding)
                        move._generate_consumed_move_line(qty_to_add, self.final_lot_id)
                    elif len(move._get_move_lines()) < 2:
                        move.quantity_done += float_round(self.qty_producing * move.unit_factor,
                                                          precision_rounding=rounding)
                        update_values = self._update_production_datails(move)
                        if update_values:
                            self.production_id.production_line_ids = update_values
                    else:
                        move._set_quantity_done(move.quantity_done + float_round(self.qty_producing * move.unit_factor,
                                                                                 precision_rounding=rounding))
                        update_values = self._update_production_datails(move)
                        if update_values:
                            self.production_id.production_line_ids = update_values

        # Transfer quantities from temporary to final move lots or make them final
        for move_line in self.active_move_line_ids:
            # use pre record production
            if not self._pre_record_production(move_line):
                continue
            # Check if move_line already exists
            if move_line.qty_done <= 0:  # rounding...
                move_line.sudo().unlink()
                continue
            if move_line.product_id.tracking != 'none' and not move_line.lot_id:
                raise UserError(_('You should provide a lot/serial number for a component'))
            # Search other move_line where it could be added:
            lots = self.move_line_ids.filtered(
                lambda x: (x.lot_id.id == move_line.lot_id.id) and (not x.lot_produced_id) and (not x.done_move) and (
                    x.product_id == move_line.product_id))
            if lots:
                lots[0].qty_done += move_line.qty_done
                lots[0].lot_produced_id = self.final_lot_id.id
                move_line.sudo().unlink()
                # l
                continue
            else:
                move_line.lot_produced_id = self.final_lot_id.id
                move_line.done_wo = True
        # tab
        # record all movement in history
        for move_line in self.active_move_line_ids:
            update_values = self._update_production_datails(move_line)
            if update_values:
                self.production_id.production_line_ids = update_values
        # tab
        # One a piece is produced, you can launch the next work order
        if self.next_work_order_id.state == 'pending':
            self.next_work_order_id.state = 'ready'

        # Add row in production line detail for produced qty
        final_move_ids = self.move_line_ids.filtered(
            lambda move_line: not move_line.done_move and not move_line.lot_produced_id and move_line.qty_done > 0)
        final_move_ids.write({
            'lot_produced_id': self.final_lot_id.id,
            'lot_produced_qty': self.qty_producing,
        })

        # add post record production
        if not self._post_record_production():
            return False

        # If last work order, then post lots used
        # TODO: should be same as checking if for every workorder something has been done?
        if not self.next_work_order_id:
            production_move = self.production_id.move_finished_ids.filtered(
                lambda x: (x.product_id.id == self.production_id.product_id.id) and (x.state not in ('done', 'cancel')))
            if production_move.product_id.tracking != 'none':
                move_line = production_move.move_line_ids.filtered(lambda x: x.lot_id.id == self.final_lot_id.id)
                if move_line:
                    move_line.product_uom_qty += self.qty_producing
                    move_line.qty_done += self.qty_producing
                else:
                    location_dest_id = production_move.location_dest_id.get_putaway_strategy(
                        self.product_id).id or production_move.location_dest_id.id
                    move_line.create({'move_id': production_move.id,
                                      'product_id': production_move.product_id.id,
                                      'lot_id': self.final_lot_id.id,
                                      'product_uom_qty': self.qty_producing,
                                      'product_uom_id': production_move.product_uom.id,
                                      'qty_done': self.qty_producing,
                                      'workorder_id': self.id,
                                      'location_id': production_move.location_id.id,
                                      'location_dest_id': location_dest_id,
                                      })
            else:
                production_move.quantity_done += self.qty_producing

        if not self.next_work_order_id:
            for by_product_move in self.production_id.move_finished_ids.filtered(
                lambda x: (x.product_id.id != self.production_id.product_id.id) and (
                    x.state not in ('done', 'cancel'))):
                if by_product_move.has_tracking != 'serial':
                    values = self._get_byproduct_move_line(by_product_move,
                                                           self.qty_producing * by_product_move.unit_factor)
                    self.env['stock.move.line'].create(values)
                elif by_product_move.has_tracking == 'serial':
                    qty_todo = by_product_move.product_uom._compute_quantity(
                        self.qty_producing * by_product_move.unit_factor, by_product_move.product_id.uom_id)
                    for i in range(0, int(float_round(qty_todo, precision_digits=0))):
                        values = self._get_byproduct_move_line(by_product_move, 1)
                        self.env['stock.move.line'].create(values)

        # Update workorder quantity produced
        self.qty_produced += self.qty_producing

        if self.final_lot_id:
            self.final_lot_id.use_next_on_work_order_id = self.next_work_order_id
            self.final_lot_id = False

        # Set a qty producing
        rounding = self.production_id.product_uom_id.rounding
        if float_compare(self.qty_produced, self.production_id.product_qty, precision_rounding=rounding) >= 0:
            self.qty_producing = 0
        elif self.production_id.product_id.tracking == 'serial':
            self._assign_default_final_lot_id()
            self.qty_producing = 1.0
            self._generate_lot_ids()
        else:
            self.qty_producing = float_round(self.production_id.product_qty - self.qty_produced,
                                             precision_rounding=rounding)
            self._generate_lot_ids()

        if self.next_work_order_id and self.production_id.product_id.tracking != 'none':
            self.next_work_order_id._assign_default_final_lot_id()

        if float_compare(self.qty_produced, self.production_id.product_qty, precision_rounding=rounding) >= 0:
            self.button_finish()
        # _logger.info("FINAL %s:%s %s" % (self.qty_producing, self.qty_produced, self.product_id and self.product_id.name or "no product"))
        return True

    def _check_product_create(self, lot, product, use_date):
        if not lot:
            lot = self.env['ir.sequence'].next_by_code('stock.lot.serial')
        return {
            'name': lot,
            'product_id': product.id,
            'use_date': use_date
        }

    def _check_product(self, product, qty=1.0, lot=False, code=False, use_date=False):
        lot_obj = self.env['stock.production.lot']
        location_id = self.production_id.location_dest_id
        # _logger.info("SCANNED PRODUCT %s::%s" % (product, lot))
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
            if product.tracking == 'serial' and (lot_id or available_quants):
                # check again for final lots if there no raise
                final_lots = self.env['stock.move.line'].search(
                    ['|', ('move_id.raw_material_production_id', '=', self.production_id.id),
                     ('move_id.production_id', '=', self.production_id.id), ('move_id.workorder_id', '=', self.id)])
                # _logger.info("SERIAL %s:%s" % (available_quants.ids, final_lots.filtered(lambda r: r.lot_produced_id.id == lot_id.id).ids))
                if len(final_lots.filtered(lambda r: r.lot_produced_id.id == lot_id.id).ids) > 0 or len(
                    available_quants.ids) > 0:
                    return False
            elif not lot_id:
                # create only on first wo
                lot_id = lot_obj.create(self._check_product_create(lot, product, use_date))
        else:
            # create only on first wo
            lot_id = lot_obj.create(self._check_product_create(lot, product, use_date))
        if product.tracking == 'serial':
            self.qty_producing = 1.0
        else:
            self.qty_producing += qty
        if lot_id:
            self.final_lot_id = lot_id
        # _logger.info("LOT SAVED %s" % self.final_lot_id)
        return True

    def _check_component(self, product, qty=1.0, lot=False, code=False, use_date=False):
        corresponding_ml_lot = False
        raw_corresponding_ml = self.move_raw_ids.filtered(lambda ml: ml.product_id.id == product.id)
        raw_corresponding_mll = raw_corresponding_ml.mapped("move_line_ids")
        if lot:
            lot_obj = self.env['stock.production.lot']
            corresponding_ml = self.active_move_line_ids.filtered(
                lambda ml: ml.product_id.id == product.id and ml.lots_visible and not ml.lot_id)
            if code:
                lot_id = raw_corresponding_mll.filtered(
                    lambda r: r.lot_id and r.lot_id.name == lot or r.lot_id.ref == code)
                if not lot_id:
                    lot_id = lot_obj.search(
                        [('product_id', '=', product.id), '|', ('name', '=', lot), ('ref', '=', code)])
                else:
                    lot_id = lot_id[0].lot_id
            else:
                lot_id = raw_corresponding_mll.filtered(lambda r: r.lot_id and r.lot_id.name == lot)
                if not lot_id:
                    lot_id = lot_obj.search([('product_id', '=', product.id), ('name', '=', lot)])
                else:
                    lot_id = lot_id[0].lot_id
            if not lot_id:
                lot_id = lot_obj.create({'name': lot, 'ref': code, 'product_id': product.id, 'use_date': use_date})
                corresponding_ml.write({'lot_id': lot_id.id})
            # _logger.info("COMPONENT_LOT %s:%s" % (lot_id.name, corresponding_ml.product_id.display_name))
            corresponding_ml_lot = self.active_move_line_ids.filtered(
                lambda ml: ml.product_id.id == product.id and ml.lots_visible and ml.lot_id == lot_id)
        else:
            corresponding_ml = self.active_move_line_ids.filtered(
                lambda ml: ml.product_id.id == product.id and not ml.lots_visible)
            lot_id = False

        if corresponding_ml_lot and len(corresponding_ml_lot) == 1:
            corresponding_ml = corresponding_ml_lot
        else:
            if self.use_bins:
                corresponding_ml = self.active_move_line_ids.filtered(
                    lambda ml: ml.product_id.id == product.id and ml.lots_visible)
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
            picking_type_id = self.production_id.picking_type_id
            location_id = self.production_id.location_src_id
            if lot:
                available_quants = self.env['stock.quant'].search([
                    ('lot_id', '=', lot_id.id),
                    ('location_id', 'child_of', location_id.id),
                    ('product_id', '=', product.id),
                    ('quantity', '>', 0),
                ], limit=1)
                # if available_quants:
                #    self.location_id = available_quants.location_id.id
            picking_type_lots = (picking_type_id.use_create_lots or picking_type_id.use_existing_lots)
            new_line = self.active_move_line_ids.new({
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'location_id': available_quants and available_quants.location_id.id or location_id.id,
                'location_dest_id': self.production_id.location_dest_id.id,
                'qty_done': (product.tracking == 'none' and picking_type_lots) and qty or lot_id and qty or 0.0,
                'product_uom_qty': lot_id and qty or 0.0,
                'date': fields.datetime.now(),
                'lot_id': lot_id and lot_id.id,
                'split_lot_id': lot_id and lot_id.id,
            })
            self.active_move_line_ids += new_line
            corresponding_ml = new_line
        if lot_id and product and self.use_bins:
            lot = self.production_id.split_lot_ids.filtered(
                lambda r: r.lot_id.id != lot_id.id and r.product_id.id == product.id and r.workorder_id.id == self.id)
            if len(lot.ids) == 0:
                lot.create({'production_id': self.production_id.id, 'lot_id': lot_id.id, 'product_id': product.id})
        if corresponding_ml:
            corresponding_ml.onchange_serial_number()
        return True

    def on_barcode_scanned(self, barcode):
        message = _('The barcode "%(barcode)s" doesn\'t correspond to a proper product, package or location.')
        picking_type_id = self.production_id.picking_type_id
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
                elif self.work_production or ['sub_type'] == 'pair':
                    if self._check_product(product, qty, lot, use_date):
                        return
                elif not self.work_component or parsed_result['sub_type'] == 'product':
                    if self._check_product(product, qty, lot, use_date):
                        return
                else:
                    if self._check_component(product, qty, lot, code, use_date):
                        return

            if parsed_result['type'] in ['lot']:
                product = self.product_id
                location_id = self.production_id.location_src_id
                qty = 1.0
                use_date = False
                lot = parsed_result['lot']
                code = parsed_result['code']
                product_ids = [x.product_id.id for x in self.move_raw_ids]
                # _logger.info("PARCE %s" % parsed_result)
                if self.work_production or parsed_result['sub_type'] == 'pair':
                    if self._check_product(product, qty, lot, code, use_date):
                        lRet = False
                        products = []
                        available = []
                        # first pass check in reserved material
                        tracked_moves = self.active_move_line_ids.filtered(lambda move: move.state not in ('done',
                                                                                                           'cancel') and move.product_id.tracking != 'none' and move.product_id != self.production_id.product_id)
                        lot_id = tracked_moves.filtered(lambda r: r.lot_id and r.lot_id.name == lot)
                        if lot_id:
                            available_quants = qty = lot_id[0].unit_factor * self.qty_producing
                            use_date = lot_id[0].lot_id.use_date
                            product = lot_id[0].product_id
                            products.append(product)
                            available.append(product.id)
                        # second pass check in all materials
                        if not lot_id:
                            available_quants = False
                            lot_id = self.env['stock.production.lot'].search(
                                [('name', '=', lot), ('product_id', 'in', product_ids)],
                                limit=1)  # Logic by product but search by lot in existing lots
                            if len([x.id for x in lot_id]) == 1:
                                product = self.env['product.product'].browse([lot_id.product_id.id])
                                available_quants = self.env['stock.quant'].search([
                                    ('lot_id', '=', lot_id.id),
                                    ('location_id', 'child_of', location_id.id),
                                    ('product_id', '=', product.id),
                                    ('quantity', '>', 0),
                                ])
                            use_date = lot_id.use_date
                            if available_quants:
                                qty = sum(x.quantity for x in available_quants) or 1.0
                            else:
                                qty = 1.0
                            product = lot_id.product_id
                            products.append(product)
                            available.append(product.id)
                        if len(tracked_moves) > len(available):
                            ml_all = self.active_move_line_ids.filtered(lambda
                                                                            ml: ml.product_id != self.production_id.product_id and ml.lots_visible and not ml.lot_id and ml.product_id.id not in available)
                            if ml_all:
                                qty = False
                                use_date = False
                                code = False
                                for ml in ml_all:
                                    products.append(ml.product_id)
                        for product in products:
                            _logger.info("PRODUCT %s:%s" % (lot, product.display_name))
                            lRet = lRet or self._check_component(product, qty, lot, code, use_date)
                        if lRet:
                            return
                elif self.work_component or not parsed_result['sub_type'] or parsed_result['sub_type'] == 'component':
                    lChecked = False
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
                                lChecked = True
                        if lChecked:
                            return
                    else:
                        # ml = self.active_move_line_ids.filtered(lambda ml: ml.lots_visible and not ml.lot_id)[0]
                        # if ml:
                        #   product = ml and ml[0].product_id
                        # else:
                        return
                    # _logger.info("LOT %s" % lot_id)
                    if self._check_component(product, qty, lot, code, use_date):
                        return
                elif not self.work_component or parsed_result['sub_type'] == 'product':
                    if self._check_product(product, qty, lot, code, use_date):
                        if self.production_id.product_id.tracking == 'serial' and not self.work_component and not self.work_production:
                            self.work_component = True
                        return
                    else:
                        message = _('The barcode "%(barcode)s" maybe is serial and is added to a product')
                else:
                    lot_id = self.env['stock.production.lot'].search(
                        [('name', '=', lot), ('product_id', 'in', product_ids)],
                        limit=1)  # Logic by product but search by lot in existing lots
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
                        ml = self.active_move_line_ids.filtered(lambda ml: ml.lots_visible and not ml.lot_id)[0]
                        if ml:
                            product = ml and ml[0].product_id
                        else:
                            return
                    if self._check_component(product, qty, lot, code, use_date):
                        return

        return {'warning': {
            'title': _('Wrong barcode'),
            'message': message % {
                'barcode': barcode}
        }}

    def _generate_lot_ids(self):
        """ Generate stock move lines """
        self.ensure_one()
        MoveLine = self.env['stock.move.line']
        lot_in_bins = {}

        if self.use_bins:
            # First group all used product in one list
            product_in_bins = self.env['product.product']
            for hold_row in self.split_lot_ids.filtered(
                lambda r: r.production_id.id == self.production_id.id and r.workorder_id.id == self.id):
                qty_hold = 0.0
                if not lot_in_bins.get(hold_row.product_id):
                    lot_in_bins[hold_row.product_id] = {}
                if lot_in_bins[hold_row.product_id].get(hold_row.lot_id):
                    qty_hold = lot_in_bins[hold_row.product_id][hold_row.lot_id]
                lot_in_bins[hold_row.product_id][hold_row.lot_id] = hold_row.qty_done + qty_hold
                product_in_bins |= hold_row.product_id

            for product in product_in_bins:
                qty = 0.0
                if lot_in_bins.get(product):
                    for qty_lot in lot_in_bins[product].values():
                        qty += qty_lot
                if qty > 0:
                    move_raw_ids = self.move_raw_ids.filtered(lambda r: r.product_id == product)
                    move_raw_ids.write({'unit_factor': qty, 'product_uom_qty': qty * self.qty_production})

        tracked_moves = self.move_raw_ids.filtered(
            lambda move: move.state not in ('done',
                                            'cancel') and move.product_id.tracking != 'none' and move.product_id != self.production_id.product_id and (
                             move.bom_line_id or move.extra_bom_line))
        for move in tracked_moves:
            qty = move.unit_factor * self.qty_producing
            if move.product_id.tracking == 'serial':
                while float_compare(qty, 0.0, precision_rounding=move.product_uom.rounding) > 0:
                    MoveLine.create({
                        'move_id': move.id,
                        'product_uom_qty': 0,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': min(1, qty),
                        'production_id': self.production_id.id,
                        'workorder_id': self.id,
                        'product_id': move.product_id.id,
                        'done_wo': False,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })
                    # Removed after adding the BOM from bins
                    # if self.qty_produced % self.production_id.bom_id.product_qty == 0 and current_lot_id:
                    #     current_lot_id[0].unlink()
                    qty -= 1
            else:
                if self.use_bins:
                    current_lot = self.production_id.split_lot_ids.filtered(
                        lambda
                            r: r.product_id.id == move.product_id.id and r.production_id.id == self.production_id.id and r.workorder_id.id == self.id)
                    for current_lot_id in current_lot:
                        if lot_in_bins.get(move.product_id) and lot_in_bins[move.product_id].get(current_lot_id.lot_id):
                            qty = lot_in_bins[move.product_id][current_lot_id.lot_id]
                        MoveLine.create({
                            'move_id': move.id,
                            'product_uom_qty': 0,
                            'product_uom_id': move.product_uom.id,
                            'qty_done': qty,
                            'product_id': move.product_id.id,
                            'production_id': self.production_id.id,
                            'workorder_id': self.id,
                            'done_wo': False,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': current_lot_id and current_lot_id.lot_id.id or False,
                        })
                else:
                    MoveLine.create({
                        'move_id': move.id,
                        'product_uom_qty': 0,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': qty,
                        'product_id': move.product_id.id,
                        'production_id': self.production_id.id,
                        'workorder_id': self.id,
                        'done_wo': False,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })

    @api.multi
    def button_empty_bins(self):
        self.ensure_one()
        self.production_id.split_lot_ids.filtered(
            lambda r: r.production_id.id == self.production_id.id and r.workorder_id.id == self.id).unlink()
        self.active_move_line_ids.update({'lot_id': False})


mrpworkorder.record_production = MrpWorkorder.record_production
mrpworkorder._generate_lot_ids = MrpWorkorder._generate_lot_ids
