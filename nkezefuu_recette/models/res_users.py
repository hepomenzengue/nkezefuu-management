# -*- coding: utf-8 -*-

from odoo import models

TESTEUR = 'tester'
ADMIN = 'acceptance_admin'
DEVELOPPEUR = 'mobile_developer'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _recette_roles(self):
        """Profils de recette de l'utilisateur, sous forme d'ensemble de codes.

        Administrateur de recette implique Testeur (groups.xml), et has_group suit cette
        implication : il n'y a rien à recalculer ici.

        Rien n'est déduit du statut d'administrateur système : administrer le serveur
        et participer à la recette sont deux rôles distincts. Un compte sans profil de
        recette n'a donc aucun accès, même s'il administre Odoo.
        """
        self.ensure_one()
        roles = set()
        if self.has_group('nkezefuu_recette.group_recette_testeur'):
            roles.add(TESTEUR)
        if self.has_group('nkezefuu_recette.group_recette_admin'):
            roles.add(ADMIN)
        if self.has_group('nkezefuu_recette.group_recette_developpeur'):
            roles.add(DEVELOPPEUR)
        return roles
