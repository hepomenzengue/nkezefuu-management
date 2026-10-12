{
    'name': 'NKEZEFUU RECETTE',
    'version': '19.0.1.0.0',
    # Négatif pour passer devant les modules standard, dont la séquence vaut 100 :
    # même convention que nkezefuu (-100) et nkezefuu_fuu (-99) côté coopérative.
    'sequence': -100,
    'summary': "Suivi de la recette fonctionnelle de l'application mobile, exposé en API",
    'description': """
Recette fonctionnelle de l'application mobile NKEZEFUU.

Les cas de test, leurs résultats et la discussion entre le testeur et le
développeur mobile sont enregistrés ici, et manipulés uniquement par API depuis
le site apps-docs.nkezefuu.com. Le module n'a volontairement ni vue ni
menu.

Il tourne sur l'instance Odoo 19 de management.nkezefuu.com, indépendante de la
production de la coopérative : il ne dépend pas du module nkezefuu et gère
lui-même ses jetons de connexion.

Trois profils, attribués explicitement : Testeur, Admin testeur (qui inclut
Testeur) et Développeur mobile. Un même compte peut porter un profil de recette
et le profil de développeur, qui sont dans deux privilèges distincts. Le statut
d'administrateur système ne donne par lui-même aucun accès à la recette.
""",
    'category': 'Recette',
    'author': 'hepomenzengue@nkezefuu',
    'depends': ['base'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/recette_donnees.xml',
    ],
    'installable': True,
    # Déclaré comme application pour rester visible dans la liste des Applications
    # sans avoir à y retirer le filtre, malgré l'absence de menu.
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
