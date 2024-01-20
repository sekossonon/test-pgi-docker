# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProjectTaskProcess(models.Model):
    _name = "project.task.process"
    _description = "Project Quality Control Process"

    name = fields.Char('Description', required=True)
    show_url = fields.Boolean('Show Pull Request URL', default=True)
    project_ids = fields.Many2many("project.project", string="Projects")
    quality_control_item_ids = fields.One2many(
        "project.task.quality.control.item", "process_id", string="Control quality")

