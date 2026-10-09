# -*- coding: utf-8 -*-

from odoo import models

TESTEUR = 'testeur'
ADMIN = 'admin_testeur'
DEVELOPPEUR = 'developpeur'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _recette_roles(self):
        """Profils de recette de l'utilisateur, sous forme d'ensemble de codes.

        Admin testeur implique Testeur (groups.xml), et un administrateur système est
        Admin testeur : has_group suit ces implications, il n'y a rien à recalculer.
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
