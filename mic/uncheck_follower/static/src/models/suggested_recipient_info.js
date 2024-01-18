/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr } from '@mail/model/model_field';

registerPatch({
    name: 'SuggestedRecipientInfo',
    fields: {
        isSelected: {
            compute() {
                return false;
            },
        },
    },
});
