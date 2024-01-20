/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { RelationalModel } from "@web/views/relational_model";

/**
 * This model is overridden to update all entries of the same day
 */

export class TimesheetRelationalModel extends RelationalModel {
    async reloadRecords(record) {
        const records = this.rootType === "record" ? [this.root] : this.root.records;
        const relatedRecords = records.filter(
            (r) => r.id !== record.id && r.data.date.ts == record.data.date.ts
        );

        await Promise.all([record, ...relatedRecords].map((r) => r.load()));

        this.trigger("record-updated", { record, relatedRecords });
        this.notify();
    }
}
