# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from random import randint
from datetime import datetime


class Rsde(models.Model):
    _name = 'microcom.rsde'
    _inherit = 'mail.thread'
    _order = 'id desc'
    _description = 'Ce modèle représente des informations de recherche et de développement.'

    task_id = fields.Many2one('project.task', string='Task', related='timesheet_id.task_id')
    user_id = fields.Many2one('res.users', 'User', ondelete='restrict')
    timesheet_id = fields.Many2one('microcom.timesheet', 'Timesheet', ondelete='restrict')
    incertitude_id = fields.Many2one('uncertainty.or.innovation', 'Incertitude or Innovation', ondelete='restrict')
    idea_or_hypothesis_id = fields.Many2one('idea.hypothesis', string='Idea or hypothesis', ondelete='restrict')
    tag_ids = fields.Many2many('uncertainty.or.innovation.tags', string='Tag uncertainty or innovation')
    rsde_work_description = fields.Text('Work or progress', related='rsde_work_id.description')
    rsde_obstacle_description = fields.Text('Obstacle or accomplishment', related='rsde_obstacle_id.description')
    rsde_conclusion_description = fields.Text('Conclusion, learning, reuse', related='rsde_conclusion_id.description')
    date = fields.Date('Date', default=fields.Date.today)
    rsde_work_id = fields.Many2one('rsde.work', 'Work or progress')
    rsde_work_lines = fields.Many2many(
        'rsde.work', string='Work or progress line', compute='_compute_rsde_work_lines')
    rsde_obstacle_id = fields.Many2one('rsde.obstacle', 'Obstacle or accomplishment')
    rsde_obstacle_lines = fields.Many2many(
        'rsde.obstacle', string='Obstacle or accomplishment line', compute='_compute_rsde_obstacle_lines')
    rsde_conclusion_id = fields.Many2one('rsde.conclusion', 'Conclusion, learning, reuse')
    rsde_conclusion_lines = fields.Many2many(
        'rsde.conclusion', string='Conclusion, learning, reuse line', compute='_compute_rsde_conclusion_lines')
    hide_grids = fields.Boolean('Hide History Grids', default=True)

    @api.depends('rsde_work_id')
    def _compute_rsde_work_lines(self):
        for rec in self:
            work_lines = self.env['rsde.work'].search([
                ('task_id', '=', rec.task_id.id),
                ('idea_or_hypothesis_id', '=', rec.idea_or_hypothesis_id.id)])
            rec.rsde_work_lines = work_lines

    @api.depends('rsde_obstacle_id')
    def _compute_rsde_obstacle_lines(self):
        for rec in self:
            obstacle_lines = self.env['rsde.obstacle'].search([
                ('task_id', '=', rec.task_id.id),
                ('idea_or_hypothesis_id', '=', rec.idea_or_hypothesis_id.id)])
            rec.rsde_obstacle_lines = obstacle_lines

    @api.depends('rsde_conclusion_id')
    def _compute_rsde_conclusion_lines(self):
        for rec in self:
            conclusion_lines = self.env['rsde.conclusion'].search([
                ('task_id', '=', rec.task_id.id),
                ('idea_or_hypothesis_id', '=', rec.idea_or_hypothesis_id.id)])
            rec.rsde_conclusion_lines = conclusion_lines

    def action_show_timesheet(self):
        return {
            'name': 'Timesheet',
            'view_mode': 'tree',
            'res_model': 'microcom.timesheet',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'domain': [('task_id', '=', self.task_id.id), ('state', '=', 'open'), ('has_rsde', '=', True)]
        }


class RsdeWork(models.Model):
    _name = 'rsde.work'
    _rec_name = 'description'
    _order = 'id desc'

    name = fields.Char('Name')
    description = fields.Text('Description')
    date = fields.Date('Date', default=fields.Date.today)
    rsde_id = fields.Many2one('microcom.rsde', string='R&D', ondelete='restrict')
    user_id = fields.Many2one(related='rsde_id.user_id', store=True)
    idea_or_hypothesis_id = fields.Many2one(related='rsde_id.idea_or_hypothesis_id', store=True)
    timesheet_id = fields.Many2one(related='rsde_id.timesheet_id', store=True)
    task_id = fields.Many2one(related='rsde_id.task_id', store=True)


class RsdeObstacle(models.Model):
    _name = 'rsde.obstacle'
    _rec_name = 'description'
    _order = 'id desc'

    name = fields.Char('Name')
    description = fields.Text('Description')
    date = fields.Date('Date', default=fields.Date.today)
    rsde_id = fields.Many2one('microcom.rsde', string='R&D', ondelete='restrict')
    user_id = fields.Many2one(related='rsde_id.user_id', store=True)
    idea_or_hypothesis_id = fields.Many2one(related='rsde_id.idea_or_hypothesis_id', store=True)
    timesheet_id = fields.Many2one(related='rsde_id.timesheet_id', store=True)
    task_id = fields.Many2one(related='rsde_id.task_id', store=True)


class RsdeConclusion(models.Model):
    _name = 'rsde.conclusion'
    _rec_name = 'description'
    _order = 'id desc'

    name = fields.Char('Name')
    description = fields.Text('Description')
    date = fields.Date('Date', default=fields.Date.today)
    rsde_id = fields.Many2one('microcom.rsde', string='R&D', ondelete='restrict')
    user_id = fields.Many2one(related='rsde_id.user_id', store=True)
    idea_or_hypothesis_id = fields.Many2one(related='rsde_id.idea_or_hypothesis_id', store=True)
    timesheet_id = fields.Many2one(related='rsde_id.timesheet_id', store=True)
    task_id = fields.Many2one(related='rsde_id.task_id', store=True)
