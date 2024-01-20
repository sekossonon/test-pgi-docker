# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models, _
from odoo.tools.misc import clean_context, format_date
from odoo.exceptions import UserError, ValidationError


class RsdeWizard(models.TransientModel):
    _name = 'rsde.wizard'

    rsde_id = fields.Many2one('microcom.rsde', string='R&D')
    incertitude_id = fields.Many2one('uncertainty.or.innovation', 'Incertitude or Innovation')
    tag_ids = fields.Many2many('uncertainty.or.innovation.tags', 'rsde_wiz_tag_rel', string='Tag uncertainty or innovation')
    tag_domain = fields.Char(string="Tag domain", compute="_compute_tag_domain")
    idea_or_hypothesis_id = fields.Many2one('idea.hypothesis', string='Idea or hypothesis')
    idea_or_hypothesis_domain = fields.Char(string="Idea domain", compute="_compute_idea_or_hypothesis_domain")
    rsde_work_description = fields.Text('Work or progress')
    rsde_obstacle_description = fields.Text('Obstacle or accomplishment')
    rsde_conclusion_description = fields.Text('Conclusion, learning, reuse')
    rsde_work_lines = fields.Many2many(
        'rsde.work', string='Work or progress line', compute='_compute_rsde_work_lines')
    rsde_obstacle_lines = fields.Many2many(
        'rsde.obstacle', string='Obstacle or accomplishment line', compute='_compute_rsde_obstacle_lines')
    rsde_conclusion_lines = fields.Many2many(
        'rsde.conclusion', string='Conclusion, learning, reuse line', compute='_compute_rsde_conclusion_lines')
    hide_grids = fields.Boolean('Hide History Grids', default=True)
    filter_tags = fields.Boolean('Filter Tags')
    # external data
    timesheet_id = fields.Many2one('microcom.timesheet', 'Timesheet')
    task_id = fields.Many2one('project.task', 'Task')

    @api.depends('incertitude_id', 'incertitude_id.tag_ids', 'tag_ids', 'filter_tags')
    def _compute_tag_domain(self):
        for rec in self:
            if rec.filter_tags:
                tag_domain = []
            else:
                tag_domain = [('id', 'in', self.incertitude_id.tag_ids.ids)]
            rec.tag_domain = json.dumps(tag_domain)

    @api.depends('incertitude_id', 'incertitude_id.hypothesis_lines', 'idea_or_hypothesis_id')
    def _compute_idea_or_hypothesis_domain(self):
        for rec in self:
            idea_or_hypothesis_domain = [('id', 'in', self.incertitude_id.hypothesis_lines.ids)]
            rec.idea_or_hypothesis_domain = json.dumps(idea_or_hypothesis_domain)

    @api.depends('task_id', 'idea_or_hypothesis_id')
    def _compute_rsde_work_lines(self):
        for rec in self:
            work_lines = self.env['rsde.work'].search([
                ('task_id', '=', rec.task_id.id),
                ('idea_or_hypothesis_id', '=', rec.idea_or_hypothesis_id.id)])
            rec.rsde_work_lines = work_lines

    @api.depends('task_id', 'idea_or_hypothesis_id')
    def _compute_rsde_obstacle_lines(self):
        for rec in self:
            obstacle_lines = self.env['rsde.obstacle'].search([
                ('task_id', '=', rec.task_id.id),
                ('idea_or_hypothesis_id', '=', rec.idea_or_hypothesis_id.id)])
            rec.rsde_obstacle_lines = obstacle_lines

    @api.depends('task_id', 'idea_or_hypothesis_id')
    def _compute_rsde_conclusion_lines(self):
        for rec in self:
            conclusion_lines = self.env['rsde.conclusion'].search([
                ('task_id', '=', rec.task_id.id),
                ('idea_or_hypothesis_id', '=', rec.idea_or_hypothesis_id.id)])
            rec.rsde_conclusion_lines = conclusion_lines

    @api.onchange('incertitude_id')
    def foo(self):
        for rec in self:
            rec.tag_ids = rec.incertitude_id.tag_ids
            rec.idea_or_hypothesis_id = rec.incertitude_id.hypothesis_lines[:1]

    def button_save(self):
        # update rsde
        if not self.rsde_id:
            self.rsde_id = self.env['microcom.rsde'].create({
                'user_id': self.env.user.id,
                'timesheet_id': self.timesheet_id.id,
                # 'task_id': self.task_id.id,
                # warning, task_id must be related= or it will not updated
            })
        self.rsde_id.tag_ids = self.tag_ids
        self.rsde_id.incertitude_id = self.incertitude_id
        self.rsde_id.idea_or_hypothesis_id = self.idea_or_hypothesis_id
        # update incertitude
        self.incertitude_id.tag_ids += self.tag_ids
        #
        # update work
        if not self.rsde_id.rsde_work_id and self.rsde_work_description:
            self.rsde_id.rsde_work_id = self.env['rsde.work'].create({
                'rsde_id': self.rsde_id.id,
            })
        self.rsde_id.rsde_work_id.description = self.rsde_work_description
        #
        # update obstacle
        if not self.rsde_id.rsde_obstacle_id and self.rsde_obstacle_description:
            self.rsde_id.rsde_obstacle_id = self.env['rsde.obstacle'].create({
                'rsde_id': self.rsde_id.id,
            })
        self.rsde_id.rsde_obstacle_id.description = self.rsde_obstacle_description
        #
        # update conclusion
        if not self.rsde_id.rsde_conclusion_id and self.rsde_conclusion_description:
            self.rsde_id.rsde_conclusion_id = self.env['rsde.conclusion'].create({
                'rsde_id': self.rsde_id.id,
            })
        self.rsde_id.rsde_conclusion_id.description = self.rsde_conclusion_description
