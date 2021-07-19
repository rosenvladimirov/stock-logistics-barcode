odoo.define('barcode_mrp_workorder.MRPWorkorderBarcodeHandler', function (require) {
"use strict";

var field_registry = require('web.field_registry');
var AbstractField = require('web.AbstractField');

var MRPWorkorderBarcodeComponentHandler = AbstractField.extend({
    init: function() {
        this._super.apply(this, arguments);

        this.trigger_up('activeBarcode', {
            name: this.name,
            notifyChange: false,
            fieldName: 'active_move_line_ids',
            quantity: 'qty_done',
            setQuantityWithKeypress: true,
            commands: {
                barcode: '_barcodeAddX2MQuantity',
            }
        });
    },
});

field_registry.add('mrp_workorder_barcode_component_handler', MRPWorkorderBarcodeComponentHandler);

});