# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code par défaut Facturable')
    travel_billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code par défaut Déplacement')
    client_billing_rate = fields.One2many('timesheet.invoice.rate', 'employee_id', 'Codes facturation clients')


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"
    """
    les champs doivent être dupliqués ici pour la gestion des droits.

    En effet, hr.employee et hr.employee.public heritent tous les deux de hr.employee.base; donc les deux ont des
    champs en commun. 

    hr.employee.public est un modele vue qui tire ses donnees de la table de hr.employee: il fait un select sur les
    champs que les deux objects ont en commun.

    Odoo retourne un object du model hr.employee.public au lieu de hr.employee si le user n'a pas les
    droits du groupe hr.group_hr_user.

    Alors si on veut rendre un champ custom de hr.employee dans hr.employee.public il faut aussi le definir dans
    hr.employee.public
    """

    billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code par défaut Facturable')
    travel_billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code par défaut Déplacement')
    client_billing_rate = fields.One2many('timesheet.invoice.rate', 'employee_id', 'Codes facturation clients')


class TimesheetInvoiceRate(models.Model):
    _name = 'timesheet.invoice.rate'
    _description = 'Invoice rate code'

    partner_id = fields.Many2one('res.partner', 'Client')
    project_id = fields.Many2one('project.project', 'Projet')
    employee_id = fields.Many2one('hr.employee', 'Employé')
    billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code Facturable', required=True)
    travel_billing_code_id = fields.Many2one('microcom.timesheet.billing', 'Code pour Déplacement', required=True)

    @api.onchange('project_id')
    def onchange_project(self):
        if self.project_id:
            self.partner_id = self.project_id.partner_id
