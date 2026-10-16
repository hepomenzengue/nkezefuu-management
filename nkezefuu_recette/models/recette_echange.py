# -*- coding: utf-8 -*-

import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype

TYPES_ECHANGE = [
    ('result', 'Résultat du test'),
    # Le testeur corrige le texte de son dernier résultat ou y joint des captures,
    # sans changer le statut
    ('amend', 'Modification du résultat'),
    ('reply', 'Réponse du développeur'),
    ('comment', 'Commentaire'),
    ('edit', 'Modification du cas'),
    ('archive', 'Archivage'),
    ('restore', 'Restauration'),
]

# Captures d'écran jointes à un message : le site les réduit avant l'envoi (environ
# 1600 pixels de large), la limite de taille ne vise que les envois anormaux.
CAPTURES_MAX = 5
TAILLE_MAX_CAPTURE_MO = 3
TYPES_CAPTURE = ('image/png', 'image/jpeg', 'image/webp')


class RecetteEchange(models.Model):
    """L'historique d'un cas : une entrée par résultat, réponse, commentaire ou
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
    tour = fields.Integer(string='Itération')
    type = fields.Selection(TYPES_ECHANGE, string='Type', required=True)
    # Code du résultat (type result) ou du statut de correction (type reply) posé à ce moment-là
    statut = fields.Char(string='Statut posé')
    texte = fields.Text(string='Texte')
    auteur_id = fields.Many2one('res.users', string='Auteur', required=True, ondelete='restrict')
    # Pièces jointes standard rattachées à l'échange, créées avec lui (_ajouter_echange)
    capture_ids = fields.One2many('ir.attachment', 'res_id', string="Captures d'écran",
                                  domain=[('res_model', '=', 'nkezefuu.recette.echange')])

    @api.model
    def _lire_captures(self, captures):
        """Captures envoyées par le site : liste de {name, data}, data en base64 (une
        URL data: est aussi acceptée). Renvoie [(nom, contenu, type)], ou refuse
        l'ensemble si une seule ne convient pas. Le type est lu dans le contenu, pas
        dans le nom du fichier."""
        if not captures:
            return []
        if not isinstance(captures, list):
            raise UserError("Format des captures invalide.")
        if len(captures) > CAPTURES_MAX:
            raise UserError("%d captures au plus par message." % CAPTURES_MAX)
        lues = []
        for capture in captures:
            data = capture.get('data') if isinstance(capture, dict) else None
            if not isinstance(data, str) or not data:
                raise UserError("Une capture est vide.")
            if data.startswith('data:'):
                data = data.split(',', 1)[-1]
            try:
                contenu = base64.b64decode(data, validate=True)
            except (binascii.Error, ValueError):
                raise UserError("Une capture est illisible.")
            if len(contenu) > TAILLE_MAX_CAPTURE_MO * 1024 * 1024:
                raise UserError("Une capture dépasse %d Mo." % TAILLE_MAX_CAPTURE_MO)
            mimetype = guess_mimetype(contenu)
            if mimetype not in TYPES_CAPTURE:
                raise UserError("Seules les images PNG, JPEG ou WebP sont acceptées.")
            nom = str(capture.get('name') or '').strip()[:100] or 'capture'
            lues.append((nom, contenu, mimetype))
        return lues

    def write(self, vals):
        raise UserError("Un échange de recette ne se modifie pas.")

    def unlink(self):
        raise UserError("Un échange de recette ne se supprime pas.")
