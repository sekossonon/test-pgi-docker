/** @odoo-module */
import { useService } from "@web/core/utils/hooks";
const {Component, onWillStart } = owl;

export class TimesheetDashBoard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        onWillStart(async () => {
            this.timesheetData = await this.orm.call(
                "microcom.timesheet",
                "retrieve_dashboard",
            );
        });
    }

    async setSearchContext(ev) {
        let action_name = ev.currentTarget.getAttribute("name");
        let filter_name = $(ev.currentTarget).data('res-id');
        const action = await this.orm.call('microcom.timesheet', action_name , [[filter_name]]);
        this.action.doAction(action);

    }
}

TimesheetDashBoard.template = 'microcom_ts.TimesheetDashboard'
