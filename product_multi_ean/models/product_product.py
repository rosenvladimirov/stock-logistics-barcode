# © 2012-2014 Guewen Baconnier (Camptocamp SA)
# © 2015 Roberto Lizana (Trey)
# © 2016 Pedro M. Baeza
# © 2018 Xavier Jimenez (QubiQ)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class ProductEan13(models.Model):
    _name = 'product.ean13'
    _description = "List of EAN13 for a product."
    _order = 'sequence, id'

    name = fields.Char(
        string='EAN13',
        size=13,
        required=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=0,
    )
    product_id = fields.Many2one(
        string='Product',
        comodel_name='product.product',
        required=True,
    )

    @api.multi
    @api.constrains('name')
    @api.onchange('name')
    def _check_name(self):
        barcode_obj = self.env['barcode.nomenclature']
        for record in self.filtered('name'):
                if not barcode_obj.check_ean(record.name):
                    raise UserError(
                        _('You provided an invalid "EAN13 Barcode" reference. '
                          'You may use the "Internal Reference" '
                          'field instead.'))

    @api.multi
    @api.constrains('name')
    def _check_duplicates(self):
        for record in self:
            eans = self.search(
                [('id', '!=', record.id), ('name', '=', record.name)])
            if eans:
                raise UserError(
                    _('The EAN13 Barcode "%s" already exists for product '
                      '"%s"') % (record.name, eans[0].product_id.name))


class ProductProduct(models.Model):
    _inherit = 'product.product'

    ean13_ids = fields.One2many(
        comodel_name='product.ean13',
        inverse_name='product_id',
        string='EAN13',
    )
    barcode = fields.Char(
        string='Main EAN13',
        compute='_compute_barcode',
        store=True,
        inverse='_inverse_barcode',
        compute_sudo=True,
        inverse_sudo=True,
    )

    @api.multi
    @api.depends('ean13_ids')
    def _compute_barcode(self):
        for product in self:
            product.barcode = product.ean13_ids[:1].name

    @api.multi
    def _inverse_barcode(self):
        for product in self:
            #_logger.info("ean13 inverce %s" % product.barcode)
            if product.barcode:
                ean13_obj = self.env['product.ean13'].sudo()
                if product.ean13_ids:
                    if not product.ean13_ids.search([('name', '=', product.barcode)]):
                        ean13_obj.create(self._prepare_ean13_vals())

                    #product.ean13_ids[:1].write({'name': product.barcode})
                else:
                    ean13_obj.create(self._prepare_ean13_vals())

    @api.multi
    def _prepare_ean13_vals(self):
        self.ensure_one()
        return {
            'product_id': self.id,
            'name': self.barcode,
        }

    @api.multi
    def write(self, vals):
        if 'barcode' in vals and not vals['barcode']: 
            #_logger.info("ean13 %s" % vals)
            for product in self:
                ean13 = product.ean13_ids.search([('name', '=', product.barcode)])
                if ean13:
                    ean13.sudo().unlink()
        return super(ProductProduct, self).write(vals)

    @api.model
    def search(self, domain, *args, **kwargs):
        if list(filter(lambda x: x[0] == 'barcode', domain)):
            ean_operator = list(
                filter(lambda x: x[0] == 'barcode', domain)
            )[0][1]
            ean_value = list(
                filter(lambda x: x[0] == 'barcode', domain)
            )[0][2]

            eans = self.env['product.ean13'].search(
                [('name', ean_operator, ean_value)])
            domain = list(filter(lambda x: x[0] != 'barcode', domain))
            domain += [('ean13_ids', 'in', eans.ids)]
        return super(ProductProduct, self).search(domain, *args, **kwargs)
