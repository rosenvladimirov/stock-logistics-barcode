# -*- coding: utf-8 -*-

from odoo import http, tools, _
from odoo.http import request
from odoo.addons.web.controllers.main import ensure_db
import json

import logging

_logger = logging.getLogger(__name__)


class WebsiteWorkorder(http.Controller):

    def _workorder_update_json(self, workorder_id, product_id, lot_ref, lot_id):
        if workorder_id and workorder_id.product_id.default_code == product_id:
            if len(workorder_id.ids) > 1:
                retrn = {'error': {
                    'title': _('Wrong workorder'),
                    'message': 'To many work orders found with some name!!!'
                }}
            else:
                swith_mode = workorder_id.work_component
                workorder_id.work_component = False
                retrn = workorder_id.on_barcode_scanned(lot_ref)
                if retrn and not retrn.get('warning'):
                    workorder_id.work_component = True
                    workorder_id.on_barcode_scanned(lot_id)
                workorder_id.work_component = swith_mode
                if not retrn:
                    retrn = {'error': {
                        'title': _('Wrong lot'),
                        'message': 'The lot is not in components or in product!!!'
                    }}
                else:
                    retrn = {"ok": {"title": "Communication successful", "message": "Added new row in workorder"}}
        else:
            retrn = {'error': {
                'title': _('Wrong workorder information'),
                'message': 'The product ref or work order is wrong!!!'
            }}
        return retrn

    @http.route(['/workorder/login'], type='http', auth="public", website=True, csrf=False)
    def workorder_login(self, search=None, db=None, login=None, password=None, **post):
        ensure_db()
        if search is None or not search:
            return json.dumps({'error': {
                'title': _('Wrong Workorder'),
                'message': 'The workorder search is not defined!!!'
            }})
        if db is None:
            db = request.session.db
        uid = request.session.authenticate(db, str(login), str(password))
        _logger.info("LOGIN %s:%s:%s:%s::%s" % (db, str(login), str(password), search, uid))
        if uid:
            workorder_id = request.env['mrp.workorder'].search([('name', 'ilike', str(search))])
            _logger.info("WORKORDER %s:%s" % (workorder_id, workorder_id and workorder_id.access_token))
            if workorder_id:
                if not workorder_id.access_token:
                    workorder_id.access_token = workorder_id._get_default_access_token()
                return json.dumps({'access_token': workorder_id.access_token})
            else:
                return json.dumps({'error': {
                    'title': _('Wrong Workorder'),
                    'message': 'The workorder not found!!!'
                }})
        return json.dumps({'ok': {"title": "Communication successful", "message": "Login successful"}})

    @http.route(['/workorder'], type='http', auth="public", website=True)
    def workorder(self, product_id, lot_id=None, lot_ref=None, access_token=None, **post):
        _logger.info('POST %s:%s:%s:%s' % (product_id, lot_id, lot_ref, access_token))
        if lot_id is None or lot_ref is None:
            return {'error': {
                'title': _('Wrong lots'),
                'message': 'The lot or lot ref is wrong!!!'
            }}
        if not product_id:
            return {'error': {
                'title': _('Wrong product ref'),
                'message': 'The product ref is not defined!!!'
            }}
        return self._workorder_update_json(request.env['mrp.workorder'].search([('access_token', '=', access_token)]), product_id, lot_ref, lot_id)

    @http.route(['/workorder/update_post'], type='http', auth="public", website=True, csrf=False)
    def workorder_update_post(self, product_id, lot_id=None, lot_ref=None, search='', **post):
        _logger.info('HTTP %s:%s:%s:%s in %s' % (product_id, lot_id, lot_ref, search, request.env['mrp.workorder']))
        if lot_id is None or lot_ref is None:
            return json.dumps({'error': {
                'title': _('Wrong lots'),
                'message': 'The lot or lot ref is wrong!!!'
            }})
        if not product_id:
            return json.dumps({'error': {
                'title': _('Wrong product ref'),
                'message': 'The product ref is not defined!!!'
            }})
        return json.dumps(self._workorder_update_json(request.env['mrp.workorder'].search([('name', 'ilike', str(search))]), product_id, lot_ref, lot_id))

    @http.route(['/workorder/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def workorder_update_json(self, product_id=None, lot_id=None, lot_ref=None, search='', **post):
        _logger.info('JSON %s:%s:%s:%s::%s' % (product_id, lot_id, lot_ref, search, post))
        if lot_id is None or lot_ref is None:
            return {'error': {
                'title': _('Wrong lots'),
                'message': 'The lot or lot ref is wrong!!!'
            }}
        if not product_id:
            return {'error': {
                'title': _('Wrong product ref'),
                'message': 'The product ref is not defined!!!'
            }}
        return self._workorder_update_json(request.env['mrp.workorder'].search([('name', '=', search)]), product_id, lot_ref, lot_id)
