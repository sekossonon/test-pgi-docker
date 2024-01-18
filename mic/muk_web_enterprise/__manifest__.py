
{
    'name': 'MuK Backend Theme for Enterprise',
    'summary': 'Odoo Enterprise Backend Theme',
    'version': '16.0.1.0.6',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'Microcom',
    'website': 'http://www.microcom.ca/',
    'depends': [
        'base_setup',
        'web_editor',
        'mail',
    ],
    'data': [
        'templates/webclient.xml',
        'views/res_users.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            (
                'muk_web_enterprise/static/src/colors.scss'
            ),
        ],
        'web._assets_backend_helpers': [
            'muk_web_enterprise/static/src/variables.scss',
            'muk_web_enterprise/static/src/mixins.scss',
        ],
        'web.assets_backend': [
            'muk_web_enterprise/static/src/webclient/**/*.xml',
            'muk_web_enterprise/static/src/webclient/**/*.scss',
            'muk_web_enterprise/static/src/webclient/**/*.js',
            'muk_web_enterprise/static/src/core/**/*.xml',
            'muk_web_enterprise/static/src/core/**/*.scss',
            'muk_web_enterprise/static/src/core/**/*.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': True,
    'uninstall_hook': '_uninstall_cleanup',
}
