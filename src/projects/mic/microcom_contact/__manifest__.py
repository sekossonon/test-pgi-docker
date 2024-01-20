# -*- coding: utf-8 -*-
{
    'name': 'Microcom contact',
    'version': '16.0.1.0.0',
    'license': 'AGPL-3',
    'category': 'Partner Management',
    'description': """
Microcom partners management.
=============================
* Select partner/user from ref
* unique ref
* link user to an existing partner


UNACCENT INSTALLATION PROCEDURE
===================================================
Install unaccent on Postgresql 9.1+
The unaccent contrib comes with Postgresql contribs. On Debian / Ubuntu, in order to have the contribs, you need to install postgresql-contrib:
1. sudo aptitude install postgresql-contrib

2. Create the extension:
On Linux,
psql <database> -U <postgres_role> -c "CREATE EXTENSION \"unaccent\"";

On Windows,
psql -d <database> -U <postgres_role>
CREATE EXTENSION "unaccent";

3. Start the server with the option --unaccent
python /path/to/openerp-server.py --unaccent
===================================================

    """,
    'author': 'Microcom',
    'images': [],
    'depends': ['mail'],
    'demo': [],
    'test': [],
    'data': [
        'security/contact_security.xml',
        'views/contact_view.xml',
        'views/res_users_view.xml',
    ],
    'auto_install': False,
    'installable': True,
}
