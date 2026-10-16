{
    'name': 'NKEZEFUU RECETTE',
    'version': '19.0.1.2.0',
    # Négatif pour passer devant les modules standard, dont la séquence vaut 100 :
    # même convention que nkezefuu (-100) et nkezefuu_fuu (-99) côté coopérative.
    'sequence': -100,
    'summary': "Documentation et recette fonctionnelle de l'application mobile, exposées en API",
    'description': """
Documentation et recette fonctionnelle de l'application mobile NKEZEFUU.

La documentation (services de l'API mobile, parcours et leurs étapes, cas de
test API) est chargée depuis les fichiers JSON de data/documentation à chaque
mise à jour du module.

La recette est organisée par version de l'application : chaque version ne
contient que les cas de ses nouveautés, rattachés aux étapes des parcours, avec
leurs résultats et l'historique des échanges entre le testeur et le développeur
mobile. Une version publiée est figée. Les cas reportés sont repris dans la
version suivante, et une régression se signale depuis le cas conforme d'une
version publiée.

Tout est lu et manipulé uniquement par API depuis le site apps-docs.nkezefuu.com,
qui demande une connexion pour chacune de ses pages. Le module n'a volontairement
ni vue ni menu.

Il tourne sur l'instance Odoo 19 de management.nkezefuu.com, indépendante de la
production de la coopérative : il ne dépend pas du module nkezefuu et gère
lui-même ses jetons de connexion.

Trois profils, attribués explicitement : Testeur, Administrateur de recette (qui
inclut Testeur) et Développeur mobile. Chacun donne accès à tout le site. Un même
compte peut porter un profil de recette et le profil de développeur, qui sont
dans deux privilèges distincts. Le statut d'administrateur système ne donne par
lui-même aucun accès au site.
""",
    'category': 'Recette',
    'author': 'hepomenzengue@nkezefuu',
    'depends': ['base'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/documentation.xml',
        'data/recette_versions.xml',
        'data/recette_donnees.xml',
        'data/recette_suppressions.xml',
    ],
    'installable': True,
    # Déclaré comme application pour rester visible dans la liste des Applications
    # sans avoir à y retirer le filtre, malgré l'absence de menu.
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
