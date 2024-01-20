/** @odoo-module **/

import { _lt } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { parseInteger } from "@web/views/fields/parsers";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";

const { Component } = owl;

function formatMinuteTime(value) {
    var pattern = '%2d:%02d';
    if (value < 0) {
        value = Math.abs(value);
        pattern = '-' + pattern;
    }
    var hour = Math.floor(value / 60);
    var min = Math.round(value % 60);
    if (min === 60){
        min = 0;
        hour = hour + 1;
    }
    return _.str.sprintf(pattern, hour, min);
}

export function parseMinuteTime(value) {
    var factor = 1;
    if (value[0] === '-') {
        value = value.slice(1);
        factor = -1;
    }
    var minute_time_pair = value.split(":");
    if (minute_time_pair.length !== 2) {
        var minutes = parseInteger(value);
        if (minutes >= 100) {
            var hours = Math.floor(minutes / 100);
            minutes = (hours * 60) + (minutes - (hours * 100))
        }
        return factor * minutes;
    }
    var hours = parseInteger(minute_time_pair[0]);
    var minutes = parseInteger(minute_time_pair[1]);
    return factor * (hours * 60 + minutes);
}

export class MinuteTimeField extends Component {
    setup() {
        useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (v) => parseMinuteTime(v),
        });
        useNumpadDecimal();
    }

    get formattedValue() {
        return formatMinuteTime(this.props.value);
    }
}

MinuteTimeField.template = "microcom_ts.MinuteTimeField";
MinuteTimeField.props = {
    ...standardFieldProps,
    placeholder: { type: String, optional: true },
};

MinuteTimeField.displayName = _lt("Time");
MinuteTimeField.supportedTypes = ["integer"];

MinuteTimeField.isEmpty = () => false;
MinuteTimeField.extractProps = ({ attrs }) => {
    return {
        placeholder: attrs.placeholder,
    };
};

registry.category("fields").add("minute_time", MinuteTimeField);
registry.category("formatters").add("minute_time", formatMinuteTime);
registry.category("parsers").add("minute_time", parseMinuteTime);
