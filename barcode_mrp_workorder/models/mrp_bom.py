# -*- coding: utf-8 -*-
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models, fields, _

import logging
_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = 'mrp.bom.line'

    work_production = fields.Boolean('Combination', help='Please checked it if work with pair product/component')
