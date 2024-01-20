# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError, ValidationError

TASK_PREFIX = 'TA'

KANBAN_STATES = [
    ('normal',),
    ('approval', 'Approval'),
    ('blocked', 'Blocked'),
    ('done',)
]

KANBAN_STATES_ONDELETE = {
    "approval": "set normal",
    "blocked": "set normal",
}

TASK_CREATE_RESTRICTION_SELECTION = [
    ('managers', 'Managers'),
    ('managers_only', 'Only Project Managers'),
]


class ProjectTaskQualityControlItem(models.Model):
    _name = "project.task.quality.control.item"
    _order = 'sequence,id'
    _description = 'Project Task Quality Control Item'

    name = fields.Char('Description', required=True)
    sequence = fields.Integer('Sequence')
    process_id = fields.Many2one('project.task.process', string="Process")

    @api.model_create_multi
    def create(self, vals_list):
        # TODO:MIGRATED
        res = self.env['project.task.quality.control.item']
        for vals in vals_list:
            vals['sequence'] = self.env['project.task.quality.control.item'].search_count([])
            res |= super().create(vals)
        return res


class ProjectTaskCheckline(models.Model):
    _name = "project.task.checkline"
    _description = 'Project Task Checkline'

    sequence = fields.Integer('Sequence')
    done = fields.Boolean('Done')
    comment = fields.Text('Comment')
    quality_control_item_id = fields.Many2one('project.task.quality.control.item', string='Quality Control Items')
    task_id = fields.Many2one('project.task', string='Parent Task')


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    legend_approved = fields.Char(
        'Yellow Kanban Label', default=lambda s: _('Approved'), translate=True, required=True,
        help='Custom text')

    def unlink(self):
        if len(self.project_ids.mapped('task_ids')) > 0:
            raise ValidationError(_('Error! You cannot delete column with task linked to. (In all projects)'))
        return super(ProjectTaskType, self).unlink()


class Project(models.Model):
    _inherit = "project.project"

    description = fields.Text('Description')
    show_checklist = fields.Boolean('Show Checklist', default=True)
    process_ids = fields.Many2many('project.task.process', string="Project Processes")
    task_creation_restriction = fields.Selection(
        selection=TASK_CREATE_RESTRICTION_SELECTION,
        string="Restrict task creation to",
        help="Restricts the ability to create task to only the project responsible "
             "and/or all users with Project Manager privilege\n"
             "* None: any user can create the tasks on this project\n"
             "* Managers: Only the manager of this project and the users with Project Manager privilege can create "
             "tasks on this project\n"
             "* Project Managers: Only the users with Project Manager privilege can create tasks on this project\n",
        groups="project.group_project_manager"
    )
    is_deadline_required = fields.Boolean(default=False, string='Is deadline required')

    def _check_create_task_restriction(self):
        user_is_not_project_manager = not self.user_has_groups('project.group_project_manager')
        for project in self.sudo():
            user_is_not_the_manager = project.user_id != self.env.user

            if not project.task_creation_restriction:
                continue

            error_msg = _("You cannot create task on the project %s.\n") % project.name

            if project.task_creation_restriction == 'managers' and (
                    user_is_not_the_manager and user_is_not_project_manager):
                error_msg += _("Only either the manager of this project or the project managers are allowed to do so")
                raise UserError(error_msg)

            if project.task_creation_restriction == 'managers_only' and user_is_not_project_manager:
                error_msg += _("Only the project managers are allowed to do so")
                raise UserError(error_msg)

    # Don't copy task when copying project.
    def copy(self, default=None):
        if default is None:
            default = {'tasks': False}
        project = super(Project, self).copy(default)
        return project


class ProjectTask(models.Model):
    _inherit = "project.task"
    _order = "priority_microcom desc, sequence, id desc"

    # cannot use selection_add= because of reorder
    kanban_state = fields.Selection(string='State', selection_add=KANBAN_STATES, default='normal',
                                    ondelete=KANBAN_STATES_ONDELETE,
                                    help="A task's kanban state indicates special situations affecting it:\n"
                                         " * Normal is the default situation\n"
                                         " * Approval indicates something needs approval in this task\n"
                                         " * Blocked indicates something is preventing the progress of this task\n"
                                         " * Ready for next stage indicates the task is ready to be pulled to the next stage", )
    planned_hours = fields.Float(string='Planned')
    max_hours = fields.Float(string='Max')
    # TODO reactivate wall tracking for priority_microcom
    priority_microcom = fields.Selection(
        selection=[('0', _('None')), ('1', _('Nice to have')), ('2', _('Low')),
                   ('3', _('Normal')), ('4', _('High')), ('5', _('Very High'))],
        help="A task's priority indicates when the task should be done:\n"
             " 5 - Extremely High (Down situation. Should be done immediately)\n"
             " 4 - High (It is urgent but it can wait until we finish what we've started)\n"
             " 3 - Normal (Do in sequence order and after higher priority's tasks)\n"
             " 2 - Low (To do when there's a lack of tasks)\n"
             " 1 - Nice to have (Task not very time-consuming to be done while in the module)\n"
             " 0 - No priority set", required=True, default='0')
    legend_approved = fields.Char(related='stage_id.legend_approved', string='Kanban Approved Explanation',
                                  readonly=True, related_sudo=False)
    show_url = fields.Boolean(related='process_id.show_url')
    pr_url = fields.Char('Pull Request URL')
    show_checklist = fields.Boolean(related='project_id.show_checklist', readonly=True)
    checkline_ids = fields.One2many('project.task.checkline', 'task_id', string='Checklist')
    customer_description = fields.Text('Customer Description')
    project_id = fields.Many2one(required=True)
    process_id = fields.Many2one("project.task.process", string="Process")
    is_deadline_required = fields.Boolean(related="project_id.is_deadline_required", string='Is deadline required')
    project_partner_id = fields.Many2one(
        related='project_id.partner_id',
        store=True
    )
    microcom_sequence = fields.Char(
        string='Prefix'
    )
    id_to_char = fields.Char(
    )

    def _compute_microcom_sequence(self):
        for rec in self:
            rec.microcom_sequence = '%s%s' % (TASK_PREFIX, rec.id)
            rec.id_to_char = '%s' % (rec.id)

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        """ override to add legend_approved
        """
        for task in self:
            if task.kanban_state == 'normal':
                task.kanban_state_label = task.legend_done
            elif task.kanban_state == 'blocked':
                task.kanban_state_label = task.legend_blocked
            elif task.kanban_state == 'approval':
                task.kanban_state_label = task.legend_approved
            else:
                task.kanban_state_label = task.legend_normal

    @api.onchange('process_id')
    def onchange_process_id(self):
        """ fill quality control checklist
        """
        if self.process_id and self.process_id.quality_control_item_ids:
            # reset checklist to match quality process
            if self.checkline_ids:
                self.checkline_ids = False
            for line in self.process_id.quality_control_item_ids:
                self.checkline_ids += self.env['project.task.checkline'].new({
                    'quality_control_item_id': line.id,
                    'task_id': self.id,
                })

    def _apply_qualitycontrol_list(self):
        """ fill quality control checklist
        """
        qualitycontrol_ids = self.env['project.task.quality.control.item'].search([])
        for task in self:
            for check_id in qualitycontrol_ids:
                self.env['project.task.checkline'].create({
                    'quality_control_item_id': check_id.id,
                    'task_id': task.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            project = self.env['project.project'].browse(vals.get('project_id'))
            project._check_create_task_restriction()
        res = super(ProjectTask, self).create(vals_list)
        res._apply_qualitycontrol_list()
        res._compute_microcom_sequence()
        return res

    def write(self, vals):
        if ('active' in vals and not vals['active']) and not self.env.user.has_group('base.group_system'):
            raise ValidationError(_('You are not authorized to archive this task.'))
        return super(ProjectTask, self).write(vals)

    @api.model
    def _patch_priority(self):
        """ patch for migration
        """
        for task in self.search([]):
            if task.priority_microcom is False:
                task.priority_microcom = task.priority
                task.priority = 0
