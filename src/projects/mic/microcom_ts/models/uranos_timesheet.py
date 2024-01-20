
from odoo import models, _


class UranosAction(models.Model):
    _inherit = "uranos.action"

    def import_request_button(self):
        odoo_task = self.env['project.task'].with_context(active_test=False).sudo().search(
            [('request_pk', '=', self.request_id.pk_request)])
        if odoo_task:
            raise UserError(_('Task already exist'))

        wiz = self.env['microcom.timesheet.import.request'].create({
            'partner_id': self.customer_partner_id.id,
            'uranos_request_id': self.request_id.id,
        })
        return {
            'name': _('Import Request'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.import.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def close_request_button(self):
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'close',
            'task_id': self.task_id.id,
        })
        wiz._onchange_task_id()
        return {
            'name': _('Close Task'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.close.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def reopen_request_button(self):
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'open',
            'task_id': self.task_id.id,
        })
        wiz._onchange_task_id()
        return {
            'name': _('Reopen Request'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.close.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }


class UranosFollowup(models.Model):
    _inherit = "uranos.followup"

    def import_request_button(self):
        odoo_task = self.env['project.task'].with_context(active_test=False).sudo().search(
            [('request_pk', '=', self.request_id.pk_request)])
        if odoo_task:
            raise UserError(_('Task already exist'))

        wiz = self.env['microcom.timesheet.import.request'].create({
            'partner_id': self.customer_partner_id.id,
            'uranos_request_id': self.request_id.id,
        })
        return {
            'name': _('Import Request'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.import.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def close_request_button(self):
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'close',
            'task_id': self.task_id.id,
        })
        wiz._onchange_task_id()
        return {
            'name': _('Close Task'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.close.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }

    def reopen_request_button(self):
        wiz = self.env['microcom.timesheet.close.request'].create({
            'mode': 'open',
            'task_id': self.task_id.id,
        })
        wiz._onchange_task_id()
        return {
            'name': _('Reopen Request'),
            'view_mode': 'form',
            'res_model': 'microcom.timesheet.close.request',
            'type': 'ir.actions.act_window',
            'res_id': wiz.id,
            'target': 'new',
        }
