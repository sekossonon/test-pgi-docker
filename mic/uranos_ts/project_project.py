# coding: utf-8

from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    project_category_id = fields.Many2one('project.microcom.category', string='Project Category')
    show_timesheet = fields.Boolean(string='Show Timesheet', default=True)

    high_level_budget_min = fields.Float('Min High Level Budget',
                                         help='Budget in dollars for all the project')
    high_level_budget_max = fields.Float('Max High Level Budget',
                                         help='Budget in dollars for all the project')
    high_level_hour_min = fields.Float('Min High Level Hours',
                                       help='Budget in hours for all the project')
    high_level_hour_max = fields.Float('Max High Level Hours',
                                       help='Budget in hours for all the project')
    task_duration_min = fields.Float('Min duration (task)', compute='_compute_task_duration_min', store=True,
                                     help='Calculated from tasks, sum of duration in hours')
    task_duration_max = fields.Float('Max duration (task)', compute='_compute_task_duration_max', store=True,
                                     help='Calculated from tasks, sum of duration in hours')

    duration_total = fields.Float('Total Hours', compute='_compute_duration_total',
                                  groups='uranos_ts.group_uranos_ts, uranos_ts.group_uranos_ts_admin', store=True,
                                  help='Total of hour from timesheet')
    sale_total = fields.Float('Total Sales', compute='_compute_sale_total',
                              groups='uranos_ts.group_uranos_ts_admin', store=True,
                              help='Total of sale price computed from Uranos timesheet')

    duration_remaining_min = fields.Float('Remaining hours min', compute='_compute_duration_remaining_min',
                                          groups='uranos_ts.group_uranos_ts')
    duration_remaining_max = fields.Float('Remaining hours max', compute='_compute_duration_remaining_max',
                                          groups='uranos_ts.group_uranos_ts')
    sale_remaining_min = fields.Float('Max Sales Remaining min', compute='_compute_sale_remaining_min',
                                      groups='uranos_ts.group_uranos_ts_admin')
    sale_remaining_max = fields.Float('Min Sales Remaining max', compute='_compute_sale_remaining_max',
                                      groups='uranos_ts.group_uranos_ts_admin')
    sale_percentage = fields.Float('Remaining', compute='_compute_sale_percentage',
                                   groups='uranos_ts.group_uranos_ts')
    percentage_type = fields.Selection([('high_level_budget_min', 'High Level Budget Min'),
                                        ('high_level_budget_max', 'High Level Budget Max'),
                                        ('high_level_hour_min', 'High Level Hours Min'),
                                        ('high_level_hour_max', 'High Level Hours Max'),
                                        ('task_duration_min', 'Tasks duration min'),
                                        ('task_duration_max', 'Tasks duration max')], string='Percentage Based on',
                                       default='high_level_budget_max',
                                       help='Change the calculation method displayed in Kanban view progress bar')

    @api.depends('tasks.actual_duration')
    def _compute_duration_total(self):
        for record in self:
            record.duration_total = sum(record.tasks.mapped('actual_duration'))

    @api.depends('tasks.actual_sale')
    def _compute_sale_total(self):
        for record in self:
            record.sale_total = sum(record.tasks.mapped('actual_sale'))

    @api.depends('tasks.planned_hours')
    def _compute_task_duration_min(self):
        for record in self:
            record.task_duration_min = sum(record.tasks.mapped('planned_hours'))

    @api.depends('tasks.max_hours')
    def _compute_task_duration_max(self):
        for record in self:
            record.task_duration_max = sum(record.tasks.mapped('max_hours'))

    @api.depends('duration_total', 'task_duration_min')
    def _compute_duration_remaining_min(self):
        for record in self:
            record.duration_remaining_min = record.task_duration_min - record.duration_total

    @api.depends('duration_total', 'task_duration_max')
    def _compute_duration_remaining_max(self):
        for record in self:
            record.duration_remaining_max = record.task_duration_max - record.duration_total

    @api.depends('sale_total', 'high_level_budget_min')
    def _compute_sale_remaining_min(self):
        for record in self:
            record.sale_remaining_min = record.high_level_budget_min - record.sale_total

    @api.depends('sale_total', 'high_level_budget_max')
    def _compute_sale_remaining_max(self):
        for record in self:
            record.sale_remaining_max = record.high_level_budget_max - record.sale_total

    def _calculate_percent(self, total, first_value, second_value):
        if first_value:
            return total / first_value * 100
        if second_value:
            return total / second_value * 100
        return 0

    @api.depends('sale_total', 'high_level_budget_min', 'high_level_budget_max', 'percentage_type',
                 'duration_total', 'task_duration_min', 'task_duration_max', 'high_level_hour_min',
                 'high_level_hour_max')
    def _compute_sale_percentage(self):
        for record in self:
            if record.percentage_type == 'high_level_budget_min':
                record.sale_percentage = self._calculate_percent(record.sudo().sale_total, record.high_level_budget_min,
                                                                 record.high_level_budget_max)
            elif record.percentage_type == 'high_level_budget_max':
                record.sale_percentage = self._calculate_percent(record.sudo().sale_total, record.high_level_budget_max,
                                                                 record.high_level_budget_min)
            elif record.percentage_type == 'task_duration_min':
                record.sale_percentage = self._calculate_percent(record.duration_total, record.task_duration_min,
                                                                 record.task_duration_max)
            elif record.percentage_type == 'task_duration_max':
                record.sale_percentage = self._calculate_percent(record.duration_total, record.task_duration_max,
                                                                 record.task_duration_min)
            elif record.percentage_type == 'high_level_hour_min':
                record.sale_percentage = self._calculate_percent(record.duration_total, record.high_level_hour_min,
                                                                 record.high_level_hour_max)
            elif record.percentage_type == 'high_level_hour_max':
                record.sale_percentage = self._calculate_percent(record.duration_total, record.high_level_hour_max,
                                                                 record.high_level_hour_min)
            else:
                record.sale_percentage = 0

        # Max 100% limited by the widget.
        if record.sale_percentage > 100:
            record.sale_percentage = 100
