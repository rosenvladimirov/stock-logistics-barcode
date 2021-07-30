# Copyright 2021 Rosen Vladimirov, BioPrint Ltd.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockMoveLocationWizard(models.TransientModel):
    _name = 'wiz.stock.move.location'
    _inherit = ['wiz.stock.move.location', 'barcodes.barcode_events_mixin']

    only_one = fields.Boolean('Only 1.0 add', default=True)

    def on_barcode_scanned(self, barcode):
        product_barcode = lot = use_date = False
        if not self.picking_type_id.barcode_nomenclature_id:
            # Logic for products
            product = self.env['product.product'].search(
                ['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1)
            if product:
                if self._check_product(product):
                    return

            product_packaging = self.env['product.packaging'].search([('barcode', '=', barcode)], limit=1)
            if product_packaging.product_id:
                if self._check_product(product_packaging.product_id, product_packaging.qty):
                    return

            # Logic for packages in source location
            if self.move_line_ids:
                package_source = self.env['stock.quant.package'].search(
                    [('name', '=', barcode), ('location_id', 'child_of', self.location_id.id)], limit=1)
                if package_source:
                    if self._check_source_package(package_source):
                        return

            # Logic for packages in destination location
            package = self.env['stock.quant.package'].search([('name', '=', barcode), '|', ('location_id', '=', False),
                                                              ('location_id', 'child_of', self.location_dest_id.id)],
                                                             limit=1)
            if package:
                if self._check_destination_package(package):
                    return

            # Logic only for destination location
            location = self.env['stock.location'].search(['|', ('name', '=', barcode), ('barcode', '=', barcode)],
                                                         limit=1)
            if location and location.parent_left < self.location_dest_id.parent_right and location.parent_left >= self.location_dest_id.parent_left:
                if self._check_destination_location(location):
                    return
        else:
            parsed_result = self.picking_type_id.barcode_nomenclature_id.parse_barcode(barcode)
            if parsed_result['type'] in ['weight', 'product']:
                if parsed_result['type'] == 'weight':
                    product_barcode = parsed_result['base_code']
                    qty = parsed_result['value']
                else: #product
                    product_barcode = parsed_result['base_code']
                    qty = 1.0
                    lot = parsed_result['lot']
                    use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                product = self.env['product.product'].search(['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)], limit=1)
                if product:
                    line = self.stock_move_location_line_ids.filtered(lambda r: r.product_id == product)
                    if line:
                        line.move_quantity += qty
                    else:
                        self.stock_move_location_line_ids += self.env['wiz.stock.move.location.line'].new({
                            'product_id': product.id,
                            'move_quantity': qty,
                            'move_location_wizard_id': self.id,
                        })
                        self.stock_move_location_line_ids[-1].onchange_product_id()
                    return
            if parsed_result['type'] == 'lot':
                product_barcode = parsed_result['base_code']
                use_date = parsed_result.get('use_date', False) and parsed_result['use_date'] or False
                lot = parsed_result['lot']
                code = parsed_result['code']
                product = False
                qty = 1.0
                lot_id = self.env['stock.production.lot'].search(["|", ('name', '=', lot), ('ref', '=', code)]) # Logic by product but search by lot in existing lots
                if len(lot_id.ids) > 0:
                    if len(lot_id.ids) > 1:
                        lot_id = self.env['stock.production.lot'].search([('product_id.barcode', '=', product_barcode), "|", ('name', '=', lot), ('ref', '=', code)])
                    if len(lot_id.ids) == 1:
                        product = self.env['product.product'].browse([lot_id.product_id.id])
                        use_date = lot_id.use_date
                        if not self.only_one:
                            available_quants = self.env['stock.quant'].search([
                                ('lot_id', '=', lot_id.id),
                                ('location_id', '=', self.origin_location_id.id),
                                ('product_id', '=', product.id),
                                ('quantity', '!=', 0),
                            ])
                            qty = sum(x.quantity-x.reserved_quantity for x in available_quants) or 1.0
                    if product:
                        line = self.stock_move_location_line_ids.filtered(lambda r: r.product_id == product and r.lot_id == lot_id[0])
                        if line:
                            if line.max_quantity < line.max_quantity + qty:
                                line.move_quantity += qty
                            elif line.max_quantity + qty - line.max_quantity >= qty:
                                line.move_quantity = line.max_quantity
                            else:
                                line.move_quantity -= qty
                        else:
                            self.stock_move_location_line_ids += self.env['wiz.stock.move.location.line'].new({
                                'product_id': product.id,
                                'lot_id': lot_id.id,
                                'move_quantity': qty,
                                'move_location_wizard_id': self.id,
                            })
                            self.stock_move_location_line_ids[-1].onchange_product_id()
                        return
        return
