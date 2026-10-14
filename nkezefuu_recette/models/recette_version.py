# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .res_users import ADMIN

TYPES_VERSION = [
    ('patch', 'Correctif'),
    ('minor', 'Évolution'),
    ('major', 'Majeure'),
]

ETATS_VERSION = [
    ('in_progress', 'En recette'),
    ('published', 'Publiée'),
]

# Une version ne se publie que si chacun de ses cas actifs est dans l'un de ces états.
RESULTATS_PUBLIABLES = ('passed', 'passed_after_fix', 'postponed')


class RecetteVersion(models.Model):
    """Une version de l'application soumise à la recette.

    Une version ne contient que ses nouveautés : les cas écrits pour les
    fonctionnalités, mises à jour et correctifs qu'elle apporte. Les parcours et
    les services, eux, ne sont pas versionnés.

    Une seule version est en recette à la fois. Elle est déclarée dans les données
    du module (_declarer, appelé par data/recette_versions.xml), ou ouverte
    automatiquement en Correctif quand le testeur signale une régression alors
    qu'aucune version n'est en recette. Une fois publiée, une version et ses cas ne
    changent plus.

    Le numéro n'est jamais saisi librement : il doit suivre la dernière version
    publiée, et son type (Correctif, Évolution, Majeure) s'en déduit.
    """
    _name = 'nkezefuu.recette.version'
    _description = "Version de l'application en recette"
    _order = 'majeur desc, mineur desc, correctif desc'

    name = fields.Char(string='Version', compute='_compute_name', store=True)
    majeur = fields.Integer(string='Majeur', required=True, readonly=True)
    mineur = fields.Integer(string='Mineur', required=True, readonly=True)
    correctif = fields.Integer(string='Correctif', required=True, readonly=True)
    type = fields.Selection(TYPES_VERSION, string='Type', required=True, readonly=True)
    etat = fields.Selection(ETATS_VERSION, string='État', required=True, default='in_progress', readonly=True)
    ouverte_le = fields.Datetime(string='Ouverte le', required=True, default=fields.Datetime.now, readonly=True)
    publiee_le = fields.Datetime(string='Publiée le', readonly=True)
    publiee_par = fields.Many2one('res.users', string='Publiée par', ondelete='restrict', readonly=True)
    cas_ids = fields.One2many('nkezefuu.recette.cas', 'version_id', string='Cas de recette')

    _numero_unique = models.Constraint('unique(majeur, mineur, correctif)', 'Cette version existe déjà.')
    _une_en_recette = models.UniqueIndex("(etat) WHERE etat = 'in_progress'",
                                         'Une seule version peut être en recette à la fois.')

    @api.depends('majeur', 'mineur', 'correctif')
    def _compute_name(self):
        for version in self:
            version.name = '%d.%d.%d' % (version.majeur, version.mineur, version.correctif)

    # ----------------------------------------------------------------------
    # Lectures
    # ----------------------------------------------------------------------
    @api.model
    def _en_recette(self):
        return self.sudo().search([('etat', '=', 'in_progress')], limit=1)

    @api.model
    def _derniere_publiee(self):
        return self.sudo().search([('etat', '=', 'published')], limit=1)

    @api.model
    def _par_defaut(self):
        """La version affichée quand le site n'en demande pas : celle en recette,
        sinon la dernière publiée."""
        return self._en_recette() or self._derniere_publiee()

    def _cas_bloquants(self):
        """Cas actifs qui empêchent la publication."""
        self.ensure_one()
        return self.cas_ids.filtered(lambda c: c.resultat not in RESULTATS_PUBLIABLES)

    @api.model
    def _suivante(self, type_version):
        """Numéro de la version suivante pour ce type, à partir de la dernière
        publiée (0.0.0 s'il n'y en a pas encore)."""
        base = self._derniere_publiee()
        majeur, mineur, correctif = (base.majeur, base.mineur, base.correctif) if base else (0, 0, 0)
        if type_version == 'major':
            return majeur + 1, 0, 0
        if type_version == 'minor':
            return majeur, mineur + 1, 0
        return majeur, mineur, correctif + 1

    # ----------------------------------------------------------------------
    # Ouverture
    # ----------------------------------------------------------------------
    @api.model
    def _declarer(self, numero):
        """Déclare la version en recette, depuis les données du module. Rejoué à
        chaque mise à jour, sans effet si la version existe déjà.

        - Le numéro doit suivre la dernière version publiée ; le type s'en déduit.
        - Si une autre version est déjà en recette (un Correctif ouvert
          automatiquement par une régression), elle prend ce numéro et ce type :
          ses cas sont conservés.
        - Sinon, la version est créée.
        """
        trouve = re.fullmatch(r'\s*(\d+)\.(\d+)\.(\d+)\s*', numero or '')
        if not trouve:
            raise UserError("Numéro de version invalide : « %s ». Format attendu : 0.1.0." % numero)
        cible = tuple(int(n) for n in trouve.groups())
        Version = self.sudo()
        if Version.search_count([('majeur', '=', cible[0]), ('mineur', '=', cible[1]), ('correctif', '=', cible[2])]):
            return

        type_version = next((t for t, _label in TYPES_VERSION if self._suivante(t) == cible), None)
        if not type_version:
            base = self._derniere_publiee()
            raise UserError(
                "La version %s ne suit pas la dernière version publiée (%s). Versions possibles : %s." % (
                    numero, base.name if base else 'aucune',
                    ', '.join('%d.%d.%d (%s)' % (self._suivante(t) + (label,)) for t, label in TYPES_VERSION)))

        vals = {'majeur': cible[0], 'mineur': cible[1], 'correctif': cible[2], 'type': type_version}
        en_recette = self._en_recette()
        if en_recette:
            en_recette.write(vals)
        else:
            self._ouvrir(vals)

    @api.model
    def _ouvrir_correctif(self):
        """Version en recette, ouverte en Correctif si aucune ne l'est : utilisé par
        le signalement d'une régression."""
        en_recette = self._en_recette()
        if en_recette:
            return en_recette
        majeur, mineur, correctif = self._suivante('patch')
        return self._ouvrir({'majeur': majeur, 'mineur': mineur, 'correctif': correctif, 'type': 'patch'})

    @api.model
    def _ouvrir(self, vals):
        """Crée la version en recette, et y reprend les cas reportés des versions
        publiées qui n'ont pas encore été repris."""
        version = self.sudo().create(vals)
        reportes = self.env['nkezefuu.recette.cas'].sudo().search([
            ('version_id.etat', '=', 'published'),
            ('resultat', '=', 'postponed'),
        ]).filtered(lambda c: not c.reprise_ids)
        for cas in reportes:
            cas._reprendre(version, 'postponed')
        return version

    # ----------------------------------------------------------------------
    # Publication
    # ----------------------------------------------------------------------
    def publier(self, user):
        """L'administrateur de recette publie la version : elle est figée, avec ses
        cas. Refusé tant qu'un cas actif n'est ni conforme ni reporté."""
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'administrateur de recette peut publier une version.")
        if self.etat != 'in_progress':
            raise UserError("La version %s est déjà publiée." % self.name)
        if not self.cas_ids:
            raise UserError("La version %s ne contient aucun cas." % self.name)
        bloquants = self._cas_bloquants()
        if bloquants:
            raise UserError("Publication impossible : %d cas ne sont ni conformes ni reportés." % len(bloquants))
        self.sudo().write({'etat': 'published', 'publiee_le': fields.Datetime.now(), 'publiee_par': user.id})
        return self
