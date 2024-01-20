# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Task(models.Model):
    _inherit = "project.task"

    rsde_lines = fields.One2many('microcom.rsde', 'task_id', 'Research And Development Line')
