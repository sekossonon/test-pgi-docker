# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project Task Fusion
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, api, _
from odoo.exceptions import UserError


# 15908
class ProjectTaskFusionWizard(models.TransientModel):
    _name = 'project.task.fusion.wizard'
    _description = 'project task fusion wizard'

    project_id = fields.Many2one(
        'project.project',
        string="Project",
        readonly=True
    )
    task_ids = fields.Many2many(
        'project.task',
        string="Tasks to Merge",
        required=True
    )
    task_id = fields.Many2one(
        'project.task',
        string="In",
        required=True
    )

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_ids = self.env.context.get('active_ids')
        current_task_id = self.env['project.task'].browse(active_ids[0])
        res['project_id'] = current_task_id.project_id.id
        res['task_id'] = current_task_id.id
        return res

    def merge_tasks(self):
        for wizard in self:
            task_id = wizard.task_id
            task_ids = wizard.task_ids
            if task_id.partner_id.id not in [x.partner_id.id for x in task_ids]:
                raise UserError(_("Tasks don't have the same client"))
            #
            msg_origin = [x.name for x in task_ids]
            #
            task_id.sudo().merge_tasks(task_ids)
            #
            msg_body = _("This tasks has been merged from: <b>%s</b>") % (msg_origin)
            wizard.task_id.message_post(body=msg_body)
        return True
