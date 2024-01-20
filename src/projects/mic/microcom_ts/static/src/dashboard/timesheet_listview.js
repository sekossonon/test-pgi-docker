/** @odoo-module **/

import { TimesheetDashBoard } from '@microcom_ts/dashboard/timesheet_dashboard';
import { QuickTsListRenderer } from '@microcom_ts/views/list_view';

QuickTsListRenderer.template = 'microcom_ts.timesheetListView';
QuickTsListRenderer.components= Object.assign({}, QuickTsListRenderer.components, {TimesheetDashBoard})