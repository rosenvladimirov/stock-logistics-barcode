# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    sale_barcode_nomenclature_id = fields.Many2one(related='company_id.sale_barcode_nomenclature_id')
