{
    'name': "agent_ia",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base'],

    'data': [
        'views/views.xml',
    ],
    
    'assets':{
        "web.assets_backend": [
            "agent_ia/static/src/xml/**/*.xml",
            "agent_ia/static/src/css/**/*.css",
            "agent_ia/static/src/js/**/*.js",
        ]
    }
    
}

