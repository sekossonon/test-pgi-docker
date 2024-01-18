# -*- coding: utf-8 -*-

{
    "name": "Partner Contact Department",
    "summary": "Assign contacts to departments",
    "version": "16.0.1.0.1",
    "category": "Customer Relationship Management",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/partner-contact",
    "application": False,
    "depends": ["contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_department_view.xml",
        "views/res_partner_view.xml",
    ],
    "installable": True,
}
