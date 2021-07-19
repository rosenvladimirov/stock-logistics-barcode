# -*- coding: utf-8 -*-

from odoo import fields, api, models, _


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'barcodes.barcode_events_mixin']

    def _check_product(self, product, qty=1.0, lot=False, use_date=False):
        order_line = self.order_line.filtered(lambda r: r.product_id.id == product.id)
        if order_line:
            order_line.product_uom_qty += qty
            order_line.product_uom_change()
        else:
            vals = {
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': 1,
                'state': 'draft',
                'order_id':self.id,
            }
            order_line = self.order_line.new(vals)
            order_line.product_id_change()
            order_line.product_uom_change()
            #self.order_line += order_line
        return True

    def on_barcode_scanned(self, barcode):
        if self.state != 'draft':
            return
        if not self.company_id.sale_barcode_nomenclature_id:
            # Logic for products
            product = self.env['product.product'].search(['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1)
            if product:
                if self._check_product(product):
                    return
        else:
            parsed_result = self.company_id.sale_barcode_nomenclature_id.parse_barcode(barcode)
            #_logger.info("Parce result %s" % parsed_result)
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
                    if self._check_product(product, qty, lot, use_date):
                        return

            if parsed_result['type'] == 'lot':
                lot = parsed_result['lot']
                lot_id = self.env['stock.production.lot'].search([('name', '=', lot)]) # Logic by product but search by lot in existing lots
                if len([x.id for x in lot_id]) == 1:
                    product = self.env['product.product'].browse([lot_id.product_id.id])
                    available_quants = self.env['stock.quant'].search([
                        ('lot_id', '=', lot_id.id),
                        ('product_id', '=', product.id),
                        ('quantity', '>', 0),
                    ])
                    use_date = lot_id.use_date
                    qty = sum(x.quantity for x in available_quants) or 1.0
                    if product:
                        if self._check_product(product, qty, lot, use_date):
                            return
        return {'warning': {
            'title': _('Wrong barcode'),
            'message': _('The barcode "%(barcode)s" doesn\'t correspond to a proper product or lot') % {'barcode': barcode}
        }}


class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ['sale.order.line', 'barcodes.barcode_events_mixin']

    product_barcode = fields.Char(related='product_id.barcode')
