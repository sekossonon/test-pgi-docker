# -*- coding: utf-8 -*-

import random
from datetime import datetime

from odoo import fields, models, _
from odoo.exceptions import UserError


class ProjectTeam(models.Model):
    _name = "project.team"
    _description = 'Project Team'
    # _order = 'date desc,id desc'

    name = fields.Char('Name')
    user_ids = fields.Many2many('res.users', string='Users')
    create_daily_automatic = fields.Boolean('Create daily automatically')
    daily_default_time = fields.Char('Daily default hour')


class ProjectDaily(models.Model):
    _name = "project.daily"
    _description = 'Daily'
    _order = 'date desc,id desc'

    name = fields.Char('Name', compute='_compute_name')
    team_id = fields.Many2one('project.team', 'Team')
    date = fields.Date('Date', default=fields.Date.context_today)
    start_time = fields.Char('Start Time')
    daily_line_ids = fields.One2many(
        comodel_name='project.daily.line',
        inverse_name='daily_id',
        string='Daily Lines', copy=False)
    comment = fields.Html('Comments')
    line_count = fields.Integer(compute='_compute_line_count', string="Tasks")

    def _compute_name(self):
        for line in self:
            line.name = '%s - %s' % (line.date, line.start_time)

    def _compute_line_count(self):
        for line in self:
            line.line_count = len(line.daily_line_ids)

    def button_nothing(self):
        pass

    def add_line_randomly(self):
        # no duplicates
        present_users = self.daily_line_ids.mapped('user_id')
        missing_users = list(self.team_id.user_ids - present_users)
        if not missing_users:
            raise UserError(_('No missing users'))

        random.shuffle(missing_users)
        for user in missing_users:
            last = self.env['project.daily.line'].search([('user_id', '=', user.id)], order='id desc', limit=1)
            self.daily_line_ids.create({
                'daily_id': self.id,
                'user_id': user.id,
                'planned': last and last.next_day or False,
                'problems': last and last.problems or False,
                'backlog': last and last.backlog or False
            })

    def automatic_create_new_daily(self):
        if datetime.today().weekday() not in [5, 6]:
            # Do not execute saturday and sunday
            teams = self.env['project.team'].search([('create_daily_automatic', '=', True)])

            for team in teams:
                daily = self.create({
                    'team_id': team.id,
                    'start_time': team.daily_default_time
                })
                daily.add_line_randomly()


class ProjectDailyLine(models.Model):
    _name = "project.daily.line"
    _description = 'Daily line'

    daily_id = fields.Many2one('project.daily')
    user_id = fields.Many2one('res.users', string='User')
    planned = fields.Html('Planned')
    executed = fields.Html('Executed')
    next_day = fields.Html('Next day')
    problems = fields.Html('problems')
    backlog = fields.Html('Backlog')
    summary = fields.Html('Summary', compute='_compute_summary')

    def _compute_summary(self):
        for line in self:
            line.summary = '<hr>'.join([
                line.planned or '',
                line.executed or '',
                line.next_day or '',
                line.problems or '',
                line.backlog or '',
            ])
