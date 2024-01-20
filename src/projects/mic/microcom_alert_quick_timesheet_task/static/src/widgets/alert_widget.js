/** @odoo-module **/

import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
const rpc = require('web.rpc');

const { Component, EventBus, onWillRender} = owl;

export class TimesheetAlertPopOver extends Component {
    setup() {
        this.actionService = useService("action");
    }

    openTimesheet() {
         var task_id = this.props.record.data.task_id[0]
         var partner_id = this.props.record.data.partner_id[0]
         this.actionService.doAction({
            name: "Full Timesheet",
            type: "ir.actions.act_window",
            res_model: "microcom.timesheet.history",
            target: "current",
            views: [
                [false, "form"],
                [false, "list"],
            ],
            context: {task_id:task_id, partner_id:partner_id},
        });
    }

/*        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Full Timesheet",
            res_model: "microcom.timesheet.history",
            domain: [],
            views: [[false, "list"]],
            target: "current",
            view_id: "microcom_alert_quick_timesheet_task.microcom_timesheet_history_action",
            context: {
                active_model: 'microcom.timesheet.history',
*//*                search_default_task_id: this.props.record.data.task_id[0],
                search_default_partner_id: this.props.record.data.partner_id[0],
                search_default_user_id: this.props.record.data.user_timesheet_alert_id[0],
                search_default_open: 1,*//*
                create:false,
                edit:false,
            },
        });*/
}

TimesheetAlertPopOver.template = "microcom_alert_quick_timesheet_task.TimesheetAlertPopOver";
export class TimesheetAlert extends Component {
   static template = 'FieldTimesheetAlert'

   setup(){
        super.setup();
        this.bus = new EventBus();
        this.popover = usePopover();
        this.closePopover = null;
        this.user = useService("user");
        this.calcData = {};
        onWillRender(async () => {
            //this.user_hasGroup = await this.user.hasGroup("uranos_ts.group_uranos_ts_all");
            this.initCalcData();
        })
   }

    initCalcData() {
        // calculate data
        const { data } = this.props.record;
/*        if (this.user_hasGroup) {
               this.calcData.group_access = true;
            } else {
                this.calcData.group_access = false;
            }*/
    }

/*    updateCalcData() {
        // popup specific data
        const { data } = this.props.record;
        alert();

        if (!data.user_timesheet_alert_name) {
            return;
        }
        this.calcData.user_timesheet_alert_name = data.user_timesheet_alert_name
    }*/

    showPopup(ev) {
        //this.updateCalcData();
        this.closePopover = this.popover.add(
            ev.currentTarget,
            this.constructor.components.Popover,
            {bus: this.bus, record: this.props.record, calcData: this.calcData},
            {
                position: 'top',
            }
            );
        this.bus.addEventListener('close-popover', this.closePopover);
    }

}
TimesheetAlert.components = { Popover: TimesheetAlertPopOver };
registry.category("fields").add("timesheet_alert", TimesheetAlert);