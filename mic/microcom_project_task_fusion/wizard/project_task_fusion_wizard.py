# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project Task Fusion
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, api, _


class ProjectTaskFusionWizard(models.Model):
    _name = 'project.task.fusion.wizard'
    _description = 'project task fusion wizard'

    project_id = fields.Many2one(
        'project.project',
        string="Project",
        readonly=True
    )
    task_ids = fields.Many2many(
        'project.task',
        string="Fusion With",
        required=True
    )
    task_id = fields.Many2one(
        'project.task',
        string="Task",
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
            msg_origin = [x.name for x in task_ids]
            #
            self.sudo().env['project.task'].merge_tasks(task_id, task_ids)
            #
            msg_body = _("This tasks has been merged from: <b>%s</b>") % (msg_origin)
            wizard.task_id.message_post(body=msg_body)
        return True
