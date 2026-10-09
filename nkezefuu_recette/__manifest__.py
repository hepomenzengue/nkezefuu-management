{
    'name': 'NKEZEFUU RECETTE',
    'version': '17.0.1.0.0',
    'summary': "Suivi de la recette fonctionnelle de l'application mobile, exposé en API",
    'description': """
Recette fonctionnelle de l'application mobile NKEZEFUU.

Les cas de test, leurs résultats et la discussion entre le testeur et le
développeur mobile sont enregistrés ici, et manipulés uniquement par API depuis
le site de documentation des services. Le module n'a volontairement ni vue ni
menu.

Trois profils : Testeur, Admin testeur (qui inclut Testeur) et Développeur
mobile. Les administrateurs système sont automatiquement Admin testeur.
""",
    'category': 'Uncategorized',
    'author': 'hepomenzengue@nkezefuu',
    'depends': ['nkezefuu'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/recette_donnees.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
