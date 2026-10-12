# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models

DUREE_ACCES = timedelta(hours=8)
DUREE_RENOUVELLEMENT = timedelta(days=30)


def _empreinte(jeton):
    return hashlib.sha256(jeton.encode('utf-8')).hexdigest()


class RecetteJeton(models.Model):
    """Jetons de connexion à l'API de la recette.

    Le module tourne sur une instance dédiée, sans le module nkezefuu : il gère donc
    lui-même ses jetons. Une connexion produit une paire : un jeton d'accès court, et
    un jeton de renouvellement long qui produit une nouvelle paire et invalide
    l'ancienne. Seules les empreintes sont stockées : une fuite de la base ne donne
    accès à rien.
    """
    _name = 'nkezefuu.recette.jeton'
    _description = 'Jeton de connexion à la recette'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    empreinte_acces = fields.Char(required=True, index=True)
    empreinte_renouvellement = fields.Char(required=True, index=True)
    acces_expire_le = fields.Datetime(required=True)
    renouvellement_expire_le = fields.Datetime(required=True)

    @api.model
    def _emettre(self, user):
        """Nouvelle paire pour cet utilisateur. Purge au passage ses paires mortes,
        ce qui évite une tâche planifiée."""
        maintenant = fields.Datetime.now()
        self.sudo().search([('user_id', '=', user.id),
                            ('renouvellement_expire_le', '<', maintenant)]).unlink()
        acces, renouvellement = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.sudo().create({
            'user_id': user.id,
            'empreinte_acces': _empreinte(acces),
            'empreinte_renouvellement': _empreinte(renouvellement),
            'acces_expire_le': maintenant + DUREE_ACCES,
            'renouvellement_expire_le': maintenant + DUREE_RENOUVELLEMENT,
        })
        return {
            'token': acces,
            'expires_in': int(DUREE_ACCES.total_seconds()),
            'refresh_token': renouvellement,
            'refresh_expires_in': int(DUREE_RENOUVELLEMENT.total_seconds()),
        }

    @api.model
    def _utilisateur_du_jeton(self, acces):
        """L'utilisateur d'un jeton d'accès valide, ou un enregistrement vide. Un
        compte archivé perd ses accès immédiatement."""
        if not acces:
            return self.env['res.users']
        jeton = self.sudo().search([('empreinte_acces', '=', _empreinte(acces)),
                                    ('acces_expire_le', '>', fields.Datetime.now())], limit=1)
        return jeton.user_id.filtered('active')

    @api.model
    def _renouveler(self, renouvellement):
        """Nouvelle paire contre un jeton de renouvellement valide, qui est consommé :
        rejoué une seconde fois, il ne donne plus rien. None si invalide."""
        if not renouvellement:
            return None
        jeton = self.sudo().search([('empreinte_renouvellement', '=', _empreinte(renouvellement)),
                                    ('renouvellement_expire_le', '>', fields.Datetime.now())], limit=1)
        user = jeton.user_id.filtered('active')
        if not user:
            return None
        jeton.unlink()
        return self._emettre(user)

    @api.model
    def _revoquer(self, acces):
        """Déconnexion : supprime la paire de ce jeton d'accès."""
        if acces:
            self.sudo().search([('empreinte_acces', '=', _empreinte(acces))]).unlink()

    @api.model
    def _revoquer_tout(self, user):
        """Supprime toutes les paires de l'utilisateur, sur tous ses appareils."""
        self.sudo().search([('user_id', '=', user.id)]).unlink()
