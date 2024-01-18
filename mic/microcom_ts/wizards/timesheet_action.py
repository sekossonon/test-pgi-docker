# -*- coding: utf-8 -*-
from odoo import fields, models, api

from ..models.project_task import create_request


class CreateTsEvent(models.TransientModel):
    _name = 'microcom.timesheet.create.event'
    _description = 'Timesheet create event'

    name = fields.Char('Short Description')
    description = fields.Text('Description')
    internal_comment = fields.Text('Internal')
    task_id = fields.Many2one('project.task', 'task')

    def create_ts_event(self):
        # if not self.task_id.request_pk:
        #     create_request(self.task_id)
        timesheet_record = self.env['microcom.timesheet'].create(self.task_id._prepare_timesheet(
            self.name,
            description=self.description,
            internal_comment=self.internal_comment
        ))
        # if not timesheet_record.billing_code_id:
        #     # set billing code
        #     timesheet_record.onchange_user_project()
        # if not timesheet_record.followup_id:
        #     fu_data = self.task_id._prepare_main_followup()
        #     fu_data.update(is_main=False, billing_code_id=timesheet_record.billing_code_id.id)
        #     self.env['project.task.followup'].create(fu_data)
        #     timesheet_record.select_followup()


class ChangeTimesheetTaskWizard(models.TransientModel):
    _name = 'microcom.timesheet.task.wizard'
    _description = 'Timesheet task wizard'

    partner_id = fields.Many2one('res.partner', string='Customer')
    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string="Task", required=True)
    timesheet_ids = fields.Many2many('microcom.timesheet', required=True, readonly=True)

    @api.onchange('partner_id', 'project_id')
    def _onchange_partner_id(self):
        self.ensure_one()
        #
        # cleanup
        if self.partner_id and self.partner_id != self.task_id.partner_id:
            self.task_id = False
        if self.project_id and self.project_id != self.task_id.project_id:
            self.task_id = False
        #
        # domain
        if self.partner_id and self.project_id:
            allowed_tasks = self.env['project.task'].search([('partner_id', '=', self.partner_id.id)])
            allowed_projects = allowed_tasks.mapped('project_id')
            return {'domain': {
                'task_id': [('partner_id', '=', self.partner_id.id), ('project_id', '=', self.project_id.id)],
                'project_id': [('id', 'in', allowed_projects.ids)]
            }}
        elif self.partner_id:
            allowed_tasks = self.env['project.task'].search([('partner_id', '=', self.partner_id.id)])
            allowed_projects = allowed_tasks.mapped('project_id')
            return {'domain': {
                'task_id': [('partner_id', '=', self.partner_id.id)],
                'project_id': [('id', 'in', allowed_projects.ids)]
            }}
        elif self.project_id:
            return {'domain': {
                'task_id': [('project_id', '=', self.project_id.id)],
                'project_id': []
            }}
        else:
            return {'domain': {
                'task_id': [],
                'project_id': []
            }}

    @api.onchange('task_id')
    def _onchange_task_id(self):
        for wizard in self:
            if wizard.task_id:
                wizard.partner_id = wizard.task_id.project_id.partner_id
                wizard.project_id = wizard.task_id.project_id

    def button_change_task(self):
        self.timesheet_ids._change_task(self.task_id)


class WizardBudgetTemplate(models.TransientModel):
    _name = 'wizard.budget.template'
    _description = 'Wizard budget template'

    name = fields.Char('Name', required=True)
    task_id = fields.Many2one('project.task', 'task')

    def button_save_as_template(self):
        budget_template = self.env['task.budget.template'].create({'name': self.name})
        for line in self.task_id.budget_line_ids:
            budget_vals = {
                'name': line.name,
                'template_id': budget_template.id,
                'employee_ids': [Command.set(line.employee_ids.ids)],
                'stage_ids': [Command.set(line.stage_ids.ids)],
                'planned_hours': line.planned_hours,
                'max_hours': line.max_hours,
                'percentage': line.percentage,
                'billing_code_id': line.billing_code_id.id}
            template_line = self.env['task.budget.template.line'].create(budget_vals)
            line.template_line_id = template_line
        formula_lines = self.task_id.budget_line_ids.filtered(lambda x: x.budget_line_ids)
        for fl in formula_lines:
            lines = self.task_id.budget_line_ids.filtered(lambda l: l.id in fl.budget_line_ids.ids)
            template_lines = lines.mapped('template_line_id')
            template_line.template_line_ids = template_lines
        self.task_id.budget_template_id = budget_template
