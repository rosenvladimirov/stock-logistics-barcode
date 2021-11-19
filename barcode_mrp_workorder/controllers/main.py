# -*- coding: utf-8 -*-

from odoo import http, tools, _
from odoo.http import request
from odoo.addons.web.controllers.main import ensure_db
import json

import logging

_logger = logging.getLogger(__name__)


class WebsiteWorkorder(http.Controller):

    def _workorder_update_json(self, workorder_id, product_id, lot_ref, lot_id):
        _logger.info("WO %s:%s:%s:%s:%s" % (workorder_id.ids, product_id, workorder_id.product_id.default_code, lot_ref, lot_id))
        if workorder_id and workorder_id.product_id.default_code == product_id:
            if len(workorder_id.ids) > 1:
                retrn = {'error': {
                    'title': _('Wrong workorder'),
                    'message': 'To many work orders found with some name!!!'
                }}
            else:
                swith_mode = workorder_id.work_component
                workorder_id.work_component = False
                workorder_id.work_production = False
                final_lot_id = self.env['stock.production.lot'].search([('product_id', '=', workorder_id.product_id.id) ,('name', '=', lot_ref)])
                if final_lot_id:
                    return {'error': {
                        'title': _('Wrong lot'),
                        'message': 'The lot is exist in database!!!'
                    }}
                workorder_id.final_lot_id = workorder_id._check_product_create(self, lot_ref, workorder_id.product_id,
                                                                               False, force_name=True)
                # retrn = workorder_id.on_barcode_scanned(lot_ref)
                # if not retrn or (retrn and not retrn.get('warning')):
                workorder_id.work_component = True
                retrn = workorder_id.on_barcode_scanned(lot_id)
                if retrn:
                    retrn = {'error': retrn.get('warning')}
                # else:
                #     retrn = {'error': retrn.get('warning')}
                workorder_id.work_component = swith_mode
                if retrn:
                    retrn = {'error': {
                        'title': _('Wrong lot'),
                        'message': 'The lot is not in components or in product!!!'
                    }}
                else:
                    retrn = {"ok": {"title": "Communication successful", "message": "Added new row in work order"}}
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
            csrf_token = request.csrf_token()
            _logger.info("WORKORDER %s::%s:%s" % (workorder_id, request.csrf_token(), workorder_id and workorder_id.access_token))
            if workorder_id:
                if csrf_token != workorder_id.access_token:
                    workorder_id.access_token = csrf_token
                    # workorder_id.access_token = workorder_id._get_default_access_token()
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
        return self._workorder_update_json(request.env['mrp.workorder'].sudo().search([('access_token', '=', access_token)]), product_id, lot_ref, lot_id)

    @http.route(['/workorder/ready'], type='http', auth="public", website=True, csrf=False)
    def workorder_ready(self, access_token=None, **post):
        return json.dumps({'result': {"title": "Communication successful", "message": "System is available"}})

    @http.route(['/workorder/save'], type='http', auth="public", website=True, csrf=False)
    def workorder_save(self, access_token=None, **post):
        workorder_id = request.env['mrp.workorder'].sudo().search([('access_token', '=', access_token)])
        if workorder_id:
            workorder_id.record_production()
            return {"ok": {"title": "Communication successful", "message": "Added new row in workorder"}}
        return {'error': {
                    'title': _('Wrong workorder'),
                    'message': 'To many work orders found with some name!!!'
                }}

    @http.route(['/workorder/update_post'], type='http', auth="public", website=True, csrf=False)
    def workorder_update_post(self, product_id, lot_id=None, lot_ref=None, search='', access_token=None, **post):
        _logger.info('HTTP %s:%s:%s:%s in %s:%s' % (product_id, lot_id, lot_ref, search, request.env['mrp.workorder'], access_token))
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
        return json.dumps(self._workorder_update_json(request.env['mrp.workorder'].sudo().search([('access_token', '=', str(access_token))]), product_id, lot_ref, lot_id))

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
