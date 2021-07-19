# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    purchase_barcode_nomenclature_id = fields.Many2one(related='company_id.purchase_barcode_nomenclature_id')
