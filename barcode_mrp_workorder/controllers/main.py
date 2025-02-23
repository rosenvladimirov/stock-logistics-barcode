# -*- coding: utf-8 -*-
import time

from odoo import http, tools, _
from odoo.http import request
from odoo.addons.web.controllers.main import ensure_db
import json

import logging

_logger = logging.getLogger(__name__)


class WebsiteWorkorder(http.Controller):

    # The lot_ref is final product lot/sn and lot_id is component lot/sn, product_id is default_code of final product
    # employee_id is worker id and workorder_id is found id of work order in odoo by of token
    def _workorder_update_json(self, workorder_id, product_id, lot_ref, lot_id, employee_id=None):
        seconds = time.time()
        _logger.info(
            "WO %s:%s:%s:%s:%s:%s" % (workorder_id.ids, product_id, workorder_id.product_id.default_code, lot_ref,
                                      lot_id, employee_id))
        if workorder_id and workorder_id.product_id.default_code == product_id:
            if len(workorder_id.ids) > 1:
                retrn = {'error': {
                    'title': _('Wrong workorder'),
                    'message': 'To many work orders found with some name!!!'
                }}
            else:
                if employee_id is not None:
                    employee_ids = request.env['hr.employee'].sudo().search([('id', '=', int(employee_id))])
                    if employee_ids:
                        workorder_id.employee_id = employee_ids[0]
                swith_mode = workorder_id.work_component
                workorder_id.work_component = False
                workorder_id.work_production = False
                if not lot_ref:
                    lot_ref = lot_id

                if isinstance(lot_ref, str) and lot_ref.find(';') != -1:
                    lot_ref = lot_ref.split(';')[0]

                if workorder_id.product_id.tracking in ['lot', 'serial']:
                    final_lot_id = workorder_id.env['stock.production.lot'].search(
                        [('product_id', '=', workorder_id.product_id.id), ('name', '=', lot_ref)])
                    if final_lot_id:
                        return {'error': {
                            'title': _('Wrong lot'),
                            'message': 'The lot exist in database!!!'
                        }}
                    final_lot_id = workorder_id.env['stock.production.lot'].create({
                        'name': lot_ref,
                        'product_id': workorder_id.product_id.id,
                    })
                    if final_lot_id:
                        workorder_id.on_barcode_scanned(lot_ref)
                        # workorder_id.final_lot_id = final_lot_id
                        retrn = False
                    else:
                        retrn = {'warning': {
                            'title': _('Wrong lot'),
                            'message': 'The lot is not created!!!'
                        }}
                else:
                    retrn = False
                # retrn = workorder_id.on_barcode_scanned(lot_ref)
                if not retrn or (retrn and not retrn.get('warning')):
                    if isinstance(lot_id, str) and lot_id.find(';') != -1:
                        lot_id = lot_id.split(';')[0]
                    workorder_id.work_component = True
                    retrn = workorder_id.with_context(
                        dict(workorder_id._context, consume_additional=True)).on_barcode_scanned(lot_id)
                    if retrn:
                        retrn = {'error': retrn.get('warning')}
                else:
                    retrn = {'error': retrn.get('warning')}
                workorder_id.work_component = swith_mode
                if retrn:
                    retrn = {'error': {
                        'title': _('Wrong lot'),
                        'message': 'The lot is not in components or in products!!!'
                    }}
                else:
                    workorder_id.record_production()
                    retrn = {"ok": {"title": "Communication successful", "message": "Added new row in work order"}}
        else:
            retrn = {'error': {
                'title': _('Wrong workorder information'),
                'message': 'The product ref or work order is wrong!!!'
            }}
        seconds = time.time() - seconds
        _logger.info("TIME USED %s" % seconds)
        return retrn

    @http.route(['/workorder/login'], type='http', auth="public", website=True, csrf=False)
    def workorder_login(self, search=None, product_id=None, db=None, login=None, password=None, **post):
        ensure_db()
        if product_id is not None:
            if db is None:
                db = request.session.db
            uid = request.session.authenticate(db, str(login), str(password))
            if uid:
                workorder_ids = request.env['mrp.workorder'].search(
                    [('product_id.default_code', 'ilike', str(product_id)),
                     ('state', 'not in', ('done', 'cancel'))])
                #workorder_ids = request.env['mrp.workorder'].search(
                #    [('product_id.default_code', 'ilike', str(product_id))])
                if workorder_ids:
                    _logger.info("WO: %s Product ID %s WOs: %s" % (search, product_id, workorder_ids))

                    return json.dumps({'ok': {"title": "Work orders",
                                              'message': {
                                                  "workorder": {x.id: x.name.split('(')[1][:-1] for x in workorder_ids},
                                                  "employee": {x.id: x.name for x in
                                                               request.env['hr.employee'].search([])}}}})
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
            # if employee_id is not None:
            #     employee_ids = request.env['hr.employee'].search([('name', 'ilike', str(employee_id))])
            #     if employee_ids:
            #         return json.dumps({'ok': {"title": "Employee names", "message": {x.name for x in employee_ids}}})
            workorder_id = request.env['mrp.workorder'].search([('name', 'ilike', str(search))])
            csrf_token = request.csrf_token()
            _logger.info("WORKORDER %s::%s:%s" % (
            workorder_id, request.csrf_token(), workorder_id and workorder_id.access_token))
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
        if lot_id is None:
            return {'error': {
                'title': _('Wrong lots'),
                'message': 'The lot or lot ref is wrong!!!'
            }}
        if not product_id:
            return {'error': {
                'title': _('Wrong product ref'),
                'message': 'The product ref is not defined!!!'
            }}
        return self._workorder_update_json(
            request.env['mrp.workorder'].sudo().search([('access_token', '=', access_token)]), product_id, lot_ref,
            lot_id)

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
    def workorder_update_post(self, product_id, lot_id=None, lot_ref=None, search='', access_token=None,
                              employee_id=None, **post):
        _logger.info('HTTP %s:%s:%s:%s in %s:%s' % (
        product_id, lot_id, lot_ref, search, request.env['mrp.workorder'], access_token))
        if lot_id is None:
            return json.dumps({'error': {
                'title': _('Wrong lots'),
                'message': 'The lot or lot ref is wrong!!!'
            }})
        if not product_id:
            return json.dumps({'error': {
                'title': _('Wrong product ref'),
                'message': 'The product ref is not defined!!!'
            }})
        return json.dumps(self._workorder_update_json(
            request.env['mrp.workorder'].sudo().search([('access_token', '=', str(access_token))]), product_id, lot_ref,
            lot_id, employee_id=employee_id))

    @http.route(['/workorder/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    def workorder_update_json(self, product_id=None, lot_id=None, lot_ref=None, search='', **post):
        _logger.info('JSON %s:%s:%s:%s::%s' % (product_id, lot_id, lot_ref, search, post))
        if lot_id is None:
            return {'error': {
                'title': _('Wrong lots'),
                'message': 'The lot or lot ref is wrong!!!'
            }}
        if not product_id:
            return {'error': {
                'title': _('Wrong product ref'),
                'message': 'The product ref is not defined!!!'
            }}
        return self._workorder_update_json(request.env['mrp.workorder'].search([('name', '=', search)]), product_id,
                                           lot_ref, lot_id)

    @http.route(['/workorder/update_post_depanel'], type='http', auth="public", website=True, csrf=False)
    def workorder_update_post_depanel(self, lot_id=None, search='', access_token=None, **post):
        workorder_id = request.env['mrp.workorder'].sudo().search([('access_token', '=', str(access_token))])
        _logger.info('HTTP %s:%s in %s:%s' % (lot_id, search, request.env['mrp.workorder'], access_token))
        if workorder_id:
            if len(workorder_id.ids) > 1:
                retrn = {'error': {
                    'title': _('Wrong workorder'),
                    'message': 'To many work orders found with some name!!!'
                }}
            else:
                # swith_mode = workorder_id.work_component
                # workorder_id.work_component = True
                # workorder_id.work_production = False
                retrn = workorder_id.on_barcode_scanned(lot_id)
                # workorder_id.work_component = swith_mode
                if retrn:
                    retrn = {'error': {
                        'title': _('Wrong lot'),
                        'message': 'The lot is not in components or in product!!!'
                    }}
                else:
                    workorder_id.record_production()
                    retrn = {"ok": {"title": "Communication successful", "message": "Added new row in work order"}}
        else:
            retrn = {'error': {
                'title': _('Wrong workorder information'),
                'message': 'The product ref or work order is wrong!!!'
            }}
        return json.dumps(retrn)
