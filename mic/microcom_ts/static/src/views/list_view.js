/** @odoo-module **/
import { useBus } from '@web/core/utils/hooks';
import { ListController } from '@web/views/list/list_controller';
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from '@web/views/list/list_view';
import { registry } from "@web/core/registry";
import { DynamicRecordList } from "@web/views/relational_model";
import { TimesheetRelationalModel } from "./timesheet_model";
import { ViewButton } from "@web/views/view_button/view_button";


class QuickTsListController extends ListController {
    setup(){
        super.setup();
        useBus(this.env.bus, 'quick-timesheet-create', this._onQuickCreateRequested);
    }
    _onQuickCreateRequested(event){
        var context = event.detail;
        var defaultContext = this._extractDefaultContext(context);
        this.createRecord({context: context, defaultContext: defaultContext});
    }
    _extractDefaultContext(context){
        var default_context = {};
        for (const key in context) {
            if (key.startsWith("default_")) {
                default_context[key] = context[key];
                delete context[key];
            }
        }
        return default_context;
    }
    async createRecord({group, context, defaultContext}={}) {
        const list = (group && group.list) || this.model.root;
        if (this.editable) {
            if (!(list instanceof DynamicRecordList)) {
                throw new Error("List should be a DynamicRecordList");
            }
            if (list.editedRecord) {
                await list.editedRecord.save();
            }
            if (!list.editedRecord) {
                await (group || list).createRecord({context: context, defaultContext: defaultContext}, this.editable === "top");
            }
            this.render();
        } else {
            await this.props.createRecord();
        }
    }
}


class TimesheetViewButton extends ViewButton {
    async onClick(ev) {
        if (this.props.clickParams.name == "button_view_ts" && this.props.className == "js_switch_view") {
            this.env.bus.trigger('quick-timesheet-open-record', this.props.record.id);
        } else {
            super.onClick(ev);
        }
    }
}

TimesheetViewButton.props = [...TimesheetViewButton.props];
export class QuickTsListRenderer extends ListRenderer {
    setup(){
        super.setup();
        useBus(this.env.bus, 'quick-timesheet-open-record', this._onOpenRecordRequested);
    }

    _onOpenRecordRequested(event){
        const recordId = event.detail;
        const record = this.props.list.records.find((r) => r.id == recordId);
        if (record && !record.isVirtual && !this.props.archInfo.noOpen) {
            this.props.openRecord(record);
        }
    }
}
QuickTsListRenderer.components = { ...ListRenderer.components, ViewButton: TimesheetViewButton };


export const quickTsListView = {
    ...listView,
    Controller: QuickTsListController,
    Renderer: QuickTsListRenderer,
    Model: TimesheetRelationalModel
};

registry.category("views").add("quick_ts_list", quickTsListView);