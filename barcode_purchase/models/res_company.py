# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _


class Company(models.Model):
    _inherit = "res.company"

    purchase_barcode_nomenclature_id = fields.Many2one('barcode.nomenclature', 'Purchase Barcode Nomenclature')
