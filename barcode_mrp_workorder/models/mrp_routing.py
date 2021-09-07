# -*- coding: utf-8 -*-
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models, fields, _

class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    user_product_id = fields.Many2one(
        'product.product', 'Labor Cost',
        help="If a product variant is defined the BOM to calculate cost price for operation.", old_name="product_id")
    material_product_id = fields.Many2one(
        'product.product', 'Equipment cost',
        help="If a product variant is defined the BOM to calculate cost price for operation.")
    resource_type = fields.Selection([
        ('both', 'Both Human and Material (Equipment)'),
        ('user', 'Human'),
        ('material', 'Material')], string='Resource Type',
        default='material', required=True)

    @api.multi
    def get_time_cycle(self, quantity, product=None ):
        'returneaza timpul per unitate'
        self.ensure_one()
        return self.time_cycle
