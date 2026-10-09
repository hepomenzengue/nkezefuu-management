# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError

TYPES_ECHANGE = [
    ('resultat', 'Résultat du testeur'),
    ('suite', 'Réponse du développeur'),
    ('commentaire', 'Commentaire'),
    ('modification', 'Modification du cas'),
    ('archivage', 'Archivage'),
    ('restauration', 'Restauration'),
]


class RecetteEchange(models.Model):
    """La discussion d'une ligne : une entrée par résultat, réponse, commentaire ou
    modification du cas. Créée uniquement par les méthodes de nkezefuu.recette.cas,
    dans la même transaction que le changement d'état qu'elle trace : l'état affiché
    et l'historique ne peuvent pas se contredire.

    Un échange ne se modifie pas et ne se supprime pas, sinon l'historique ne prouve
    plus rien. Seule la suppression du cas lui-même les emporte, au niveau SQL.
    """
    _name = 'nkezefuu.recette.echange'
    _description = 'Échange de recette'
    _order = 'create_date, id'

    cas_id = fields.Many2one('nkezefuu.recette.cas', string='Cas', required=True,
                             ondelete='cascade', index=True)
    tour = fields.Integer(string='Tour')
    type = fields.Selection(TYPES_ECHANGE, string='Type', required=True)
    # Code du résultat (type resultat) ou de la suite (type suite) posé à ce moment-là
    statut = fields.Char(string='Statut posé')
    texte = fields.Text(string='Texte')
    version_apk = fields.Char(string='Version testée')
    auteur_id = fields.Many2one('res.users', string='Auteur', required=True, ondelete='restrict')

    def write(self, vals):
        raise UserError("Un échange de recette ne se modifie pas.")

    def unlink(self):
        raise UserError("Un échange de recette ne se supprime pas.")
