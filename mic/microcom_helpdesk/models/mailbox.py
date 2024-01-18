# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProjectMailbox(models.Model):
    _name = 'project.mailbox'
    _description = "Project Mailbox"

    name = fields.Char('Name')
    fetchmail_server_id = fields.Many2one('fetchmail.server', string='Inbound Mail Server')
    department_id = fields.Many2one('res.partner.department', string='Department')
    mail_ids = fields.One2many('project.mail', 'mailbox_id', string="Project Mails")
    # mail_count = fields.Integer('Mail Count', default=11)
    project_id = fields.Many2one('project.project', string='Default Project')
    source_id = fields.Many2one('task.source', string='Default Source')

    _sql_constraints = [
        ('fetchmail_unique', 'unique(fetchmail_server_id)',
         'There should be one project mailbox per Inbound Mail Server'),
    ]


class ProjectMail(models.Model):
    _name = 'project.mail'
    _description = "Project Mail"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'subject'

    state = fields.Selection([
        ('draft', 'New'),
        ('assigned', 'Assigned'),
        ('done', 'Done')], string='State', default='draft')
    mailbox_id = fields.Many2one('project.mailbox', string='Mailbox')
    partner_id = fields.Many2one('res.partner', string='Customer')
    project_id = fields.Many2one('project.project', string='Project')
    task_id = fields.Many2one('project.task', string='Task')
    email_to = fields.Char('TO')
    email_cc = fields.Char('CC')
    fetchmail_server_id = fields.Many2one('fetchmail.server', "Inbound Mail Server", readonly=True, index=True)
    # copied from message received
    original_message_id = fields.Many2one('mail.message', string='Original Message')
    subject = fields.Char(related='original_message_id.subject')
    date = fields.Datetime(related='original_message_id.date')
    email_from = fields.Char(related='original_message_id.email_from')
    author_id = fields.Many2one(related='original_message_id.author_id', string='Contact')
    body = fields.Html(related='original_message_id.body')
    attachment_ids = fields.Many2many(related='original_message_id.attachment_ids')

    @api.onchange('partner_id', 'project_id')
    def _onchange_partner_id(self):
        self.ensure_one()
        #
        # cleanup
        if self.partner_id and self.project_id:
            task_partners = self.project_id.task_ids.mapped('partner_id')
            if not task_partners and self.project_id.partner_id:
                # when project is not owned by a partner, we can always add a task there
                self.project_id = False
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
            return {'domain': {'task_id': [], 'project_id': []}}

    @api.onchange('task_id')
    def _onchange_task_id(self):
        self.ensure_one()
        if self.task_id:
            self.partner_id = self.task_id.partner_id
            self.project_id = self.task_id.project_id

    def _join_task(self):
        # changing state makes everything readonly
        self.state = 'assigned'
        # move mail
        self.original_message_id.model = self.task_id._name
        self.original_message_id.res_id = self.task_id.id
        self.original_message_id.record_name = self.task_id.name_get()[0][1]
        # add followers
        self.task_id.message_subscribe(self.original_message_id.partner_ids.ids)

    def button_create_task(self):
        self.task_id = self.env['project.task'].create({
            'project_id': self.project_id.id,
            'partner_id': self.partner_id.id,
            'name': self.subject,
            'description': self.body,
            'contact_id': self.author_id.id,
            'source_id': self.mailbox_id.source_id.id,
            'date_start': self.date,
        })
        self._join_task()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Task'),
            'res_model': 'project.task',
            'target': 'current',
            'view_mode': 'form',
            'res_id': self.task_id.id,
        }

    def button_join_task(self):
        self._join_task()

    def button_ignore(self):
        self.partner_id = False
        self.project_id = False
        self.task_id = False
        self.state = 'done'

    def message_post(self, **kwargs):
        # keep lost info
        self.email_to = kwargs.get('to')
        self.email_cc = kwargs.get('cc')
        # link to mailbox
        fetchmail_server_id_id = self.env.context.get('fetchmail_server_id')
        fetchmail_server_id = self.env['fetchmail.server'].browse(fetchmail_server_id_id)
        self.fetchmail_server_id = fetchmail_server_id
        project_mailbox = self.env['project.mailbox'].search(
            [('fetchmail_server_id', '=', fetchmail_server_id.id)], limit=1)
        self.mailbox_id = project_mailbox
        self.project_id = project_mailbox.project_id
        #
        res = super().message_post(**kwargs)
        self.original_message_id = res
        self.partner_id = self.author_id.parent_id or self.author_id
        return res

