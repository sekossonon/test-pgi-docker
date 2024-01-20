/** @odoo-module **/

import { registry } from '@web/core/registry';
import { StateSelectionField } from '@web/views/fields/state_selection/state_selection_field';

export class ApprovalStateSelectionField extends StateSelectionField {
    setup() {
        super.setup();
        this.colors = {
            blocked: "red",
            done: "green",
            approval: "yellow"

        };
    }
}

registry.category('fields').add('kanban.state_selection', ApprovalStateSelectionField);