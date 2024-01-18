# -*- coding: utf-8 -*-

from odoo import models, fields, api

# reverse and copy into <progressbar> colors
# web/static/src/less/webclient.less only defines those 4 classes:
#   .bg-success-full
#   .bg-warning-full
#   .bg-danger-full
#   .bg-info-full
# they are required by web/static/src/js/views/kanban/kanban_column_progressbar.js
MAP = {
    "secondary": "added",  # .bg-secondary-full undefined
    "primary": "zero",  # .bg-primary-full undefined
    "info": "start",
    "success": "half",
    "warning": "near",
    "danger": "over",
}
REMAINING_STATUS = [
    (MAP['secondary'], 'Added'),
    (MAP['primary'], 'Not Planned'),
    (MAP['info'], 'Started'),
    (MAP['success'], 'Half'),
    (MAP['warning'], 'Near'),
    (MAP['danger'], 'Over'),
]


class ProjectSprint(models.Model):
    _name = "project.sprint"
    _description = 'Project Sprint'
    _order = 'date_start desc,id desc'

    name = fields.Char('Name', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('project.sprint'))
    date_start = fields.Datetime('Date Start')
    date_end = fields.Datetime('Date End')
    sprint_line_ids = fields.One2many(
        comodel_name='project.sprint.line',
        inverse_name='sprint_id',
        string='Sprint Lines', copy=False)
    added_later = fields.Boolean('Added Later', help="Default for created lines")
    line_count = fields.Integer(compute='_compute_line_count', string="Tasks")
    line_count2 = fields.Integer(compute='_compute_line_count', string="Tasks Count")

    def _compute_line_count(self):
        for line in self:
            line.line_count = len(line.sprint_line_ids)
            line.line_count2 = line.line_count


class ProjectSprintLine(models.Model):
    _name = "project.sprint.line"
    _description = 'Project Sprint Line'
    _order = 'sprint_id, task_id, id desc'

    sprint_id = fields.Many2one('project.sprint', string='Sprint', required=True)
    task_id = fields.Many2one('project.task', string='Task')
    user_id = fields.Many2one('res.users', string='User')
    description = fields.Char('Description')
    planned_hours = fields.Float('Planned hours')
    real_hours = fields.Float('Real hours')
    remaining_status = fields.Selection(
        REMAINING_STATUS, string='Status', compute="_compute_remaining_status", store=True)
    task_completed_percent = fields.Integer(r'% completed', related="task_id.completed_percent")
    added_later = fields.Boolean('Added Later')
    # drag-n-drop between columns will try to write user_ref
    user_ref = fields.Char(related='user_id.ref', string="User Ref", readonly=True)
    color = fields.Integer(string='Color Index')
    stage_id = fields.Many2one(related='task_id.stage_id')
    grey_out = fields.Boolean(related='task_id.stage_id.grey_out')
    project_id = fields.Many2one(related='task_id.project_id')
    kanban_state = fields.Selection(related='task_id.kanban_state')
    client_ref = fields.Char(related='task_id.partner_id.ref')
    priority_microcom = fields.Selection(related='task_id.priority_microcom')

    def _compute_remaining_status(self):
        # added_later = bg-secondary
        # no planned = bg-primary
        # under half = bg-info
        # under 3/4 = bg-success
        # undertime = bg-warning
        # overtime = bg-danger
        for line in self:
            if line.added_later:
                line.remaining_status = MAP['secondary']
            elif line.planned_hours == 0:
                line.remaining_status = MAP['primary']
            elif line.real_hours < line.planned_hours * 0.5:
                line.remaining_status = MAP['info']
            elif line.real_hours < line.planned_hours * 0.75:
                line.remaining_status = MAP['success']
            elif line.real_hours <= line.planned_hours:
                line.remaining_status = MAP['warning']
            else:
                # over planned duration
                line.remaining_status = MAP['danger']

    @api.onchange('sprint_id')
    def _onchange_sprint_id(self):
        for record in self:
            record.added_later = record.sprint_id.added_later

    @api.onchange('task_id')
    def _onchange_task_id(self):
        for record in self:
            if not record.user_id:
                record.user_id = record.task_id.user_id

    # Fixes: WARNING odoo.api.create: The model ... is not overriding the create method in batch
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.task_id and not record.task_id.user_id:
                record.task_id.user_id = record.user_id
        return records

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if 'task_id' in vals:
                if record.task_id and not record.task_id.user_id:
                    record.task_id.user_id = record.user_id
        return res

    def action_duplicate(self):
        # this uses type="object" behavior in web._onKanbanActionClicked()
        # also see custom action for cover image in project._onKanbanActionClicked()
        self.ensure_one()
        duplicate = self.copy()
        action = self.env.ref('project_agile.view_project_sprint_line_action')
        result = action.read()[0]
        result['context'] = {}
        res = self.env.ref('project_agile.view_project_sprint_line_form')
        result['views'] = [(res.id, 'form')]
        result['res_id'] = duplicate.id
        return result


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    grey_out = fields.Boolean('Greyed Out')


class Project(models.Model):
    _inherit = "project.project"

    show_sprint = fields.Boolean('Sprint', default=True)


class Task(models.Model):
    _inherit = "project.task"

    show_sprint = fields.Boolean(related='project_id.show_sprint', readonly=True)
    completed_percent = fields.Integer('% Completed')
    sprint_line_ids = fields.One2many(
        comodel_name='project.sprint.line',
        inverse_name='task_id',
        string='Sprint Lines')
    difference_startup = fields.Float('Start-up')
    difference_research = fields.Float('Research')
    difference_learning = fields.Float('Learning')
    difference_unexpected = fields.Float('Unexpected')
    difference_explanation = fields.Html('Explanation ')
    r_d_doubt = fields.Html('Doubt')
    r_d_exploration_path = fields.Html('Exploration Path')
    r_d_what_learned = fields.Html('Conclusion or learning')

    def add_to_backlog(self):
        """ Add an sprint_line to backlog sprint.
        """

        self.env['project.sprint.line'].create({
            'task_id': self.id,
            'sprint_id': self.env.ref("project_agile.project_sprint_backlog").id,
            'user_id': self.user_id and self.user_id.id or False
        })

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Task, self).create(vals_list)
        for record in res:
            record.add_to_backlog()
        return res

    @api.onchange('user_id')
    def _onchange_user(self):
        if len(self.sprint_line_ids) == 1:
            self.sprint_line_ids.user_id = self.user_id
