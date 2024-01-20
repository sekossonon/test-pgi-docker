/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";


export function notifyQuickCreateAction(env, action) {
    env.bus.trigger('quick-timesheet-create', action.context);
}

registry.category("actions").add("microcom_ts.QuickTimesheetCreate", notifyQuickCreateAction);