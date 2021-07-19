# -*- coding: utf-8 -*-

from odoo import fields, api, models, _


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'barcodes.barcode_events_mixin']

    def _check_product(self, product, qty=1.0, lot=False, use_date=False):
        order_line = self.order_line.filtered(lambda r: r.product_id.id == product.id)
        if order_line:
            order_line.product_uom_qty += qty
            order_line.product_uom_change()
        else:
            vals = {
                'product_id': product.id,
                'product_uom': product.uom_po_id.id or product.uom_id.id,
                'product_qty': qty,
                'state': 'draft',
                'order_id': self.id,
            }
            order_line = self.order_line.new(vals)
            order_line.onchange_product_id()
            #self.order_line += order_line
        return True

    def on_barcode_scanned(self, barcode):
        if self.state != 'draft':
            return
        if not self.company_id.purchase_barcode_nomenclature_id:
            # Logic for products
            product = self.env['product.product'].search(['|', ('barcode', '=', barcode), ('default_code', '=', barcode)], limit=1)
            if product:
                if self._check_product(product):
                    return
        else:
            parsed_result = self.company_id.purchase_barcode_nomenclature_id.parse_barcode(barcode)
            lot = False
            use_date = False
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

            elif parsed_result['type'] == 'lot':
                product_barcode = parsed_result['base_code']
                product = self.env['product.product'].search(['|', ('barcode', '=', product_barcode), ('default_code', '=', product_barcode)])
                if product:
                    if self._check_product(product, 1.0):
                        return

        return {'warning': {
            'title': _('Wrong barcode'),
            'message': _('The barcode "%(barcode)s" doesn\'t correspond to a proper product or lot') % {'barcode': barcode}
        }}


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _inherit = ['purchase.order.line', 'barcodes.barcode_events_mixin']

    product_barcode = fields.Char(related='product_id.barcode')
