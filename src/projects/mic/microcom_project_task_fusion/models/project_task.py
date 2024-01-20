# -*- coding: utf-8 -*-
##############################################################################
#    Microcom, Project Task Fusion
#    Copyright (C) 2023 Microcom #Technologies All Rights Reserved
#    Part of Odoo. See LICENSE file for full copyright and licensing details.
##############################################################################

from odoo import fields, models, api, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def merge_tasks(self, task_id, task_ids):
        taks_description = ''
        for task in task_ids:
            task.action_ids.write({'task_id': task_id.id})
            #
            if task.customer_description:
                customer_description = '[%s:] %s' % (task.name, task.customer_description)
                task_id.customer_description = task_id.customer_description + '\n' + customer_description
            if task.description:
                task_description = '[%s:] %s' % (task.name, task.description)
                task_id.description = task_id.description + '\n' + task_description
            #
            for sub_tasks in task.child_ids:
                # sb_id = sub_tasks.copy()
                sub_tasks.parent_id = sub_tasks.id

        return True
