{
    'name': "dev_refatodo",

    'summary': "CUSTOMIZACIONES Y AUTOMATIZACIONES PARA REFATODO.COM",

    'description': """
        customizaciones
    """,

    'author': "RutiversoTech",
    'website': "",

   
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base','sale_management','web'],

    'data': [
        
        'views/views.xml'
       
    ],
    "assets": {
        "web.assets_backend": [
            "dev_refatodo/static/src/xml/**/*.xml",
            "dev_refatodo/static/src/js/**/*.js",
        ],
    },
}

