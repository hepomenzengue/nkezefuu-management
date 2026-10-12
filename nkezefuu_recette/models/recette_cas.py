# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .res_users import ADMIN, DEVELOPPEUR, TESTEUR

RESULTATS = [
    ('non_teste', 'Non testé'),
    ('ok', 'OK'),
    ('ko', 'KO'),
    ('bloque', 'Bloqué'),
    ('ok_apres_correction', 'OK après correction'),
    ('toujours_ko', 'Toujours KO'),
    ('regression', 'Régression'),
]

SUITES = [
    ('en_cours', 'En cours'),
    ('corrige_a_retester', 'Corrigé, à retester'),
    ('pas_un_defaut', 'Pas un défaut'),
    ('a_preciser', 'À préciser'),
]

BALLES = [
    ('testeur', 'Testeur'),
    ('developpeur', 'Développeur'),
    ('termine', 'Terminé'),
]

RESULTATS_OK = ('ok', 'ok_apres_correction')
RESULTATS_EN_ECHEC = ('ko', 'toujours_ko', 'regression')

# Ce que le testeur peut poser selon que le développeur a répondu en dernier ou non.
# Après une réponse, il confirme ou conteste ; sans réponse, il constate.
RESULTATS_SANS_REPONSE = ('ok', 'ko', 'bloque', 'regression')
RESULTATS_APRES_REPONSE = ('ok', 'ok_apres_correction', 'toujours_ko', 'bloque')

# Un constat est exigé dès que quelque chose ne va pas : une ligne en échec sans
# explication ne sert à rien au développeur.
RESULTATS_AVEC_CONSTAT = ('ko', 'toujours_ko', 'regression', 'bloque')

# Le développeur ne peut répondre que si le testeur lui a renvoyé la balle, ou pour
# compléter sa propre réponse tant que le testeur n'a pas repris la main.
RESULTATS_A_TRAITER = ('ko', 'toujours_ko', 'regression', 'bloque')

# Une réponse sans explication n'est acceptée que pour « En cours ».
SUITES_SANS_TEXTE = ('en_cours',)

CHAMPS_TEXTE = ('ecran', 'profil', 'action', 'attendu')
LIBELLES_TEXTE = {
    'ecran': 'Écran',
    'profil': 'Qui teste',
    'action': 'Ce que je fais',
    'attendu': 'Ce que je dois voir',
    'section_id': 'Section',
}


class RecetteCas(models.Model):
    """Une ligne de tableau de recette, avec les colonnes du classeur Excel.

    Les champs d'état (résultat, suite, horodatages, tour, balle) ne changent que par
    poser_resultat / poser_suite, qui ajoutent l'échange correspondant dans la même
    transaction. Aucun accès en écriture direct n'est donné (ir.model.access) :
    tout passe par l'API, qui appelle ces méthodes.
    """
    _name = 'nkezefuu.recette.cas'
    _description = 'Cas de recette'
    _order = 'tableau_id, section_sequence, sequence, numero'
    _rec_name = 'reference'

    # --- Le cas de test ----------------------------------------------------
    tableau_id = fields.Many2one('nkezefuu.recette.tableau', string='Tableau', required=True,
                                 ondelete='restrict', index=True)
    section_id = fields.Many2one('nkezefuu.recette.section', string='Section', required=True,
                                 ondelete='restrict', index=True)
    section_sequence = fields.Integer(string='Séquence de la section', related='section_id.sequence', store=True)
    sequence = fields.Integer(string='Séquence', default=10)
    # Attribué à la création et jamais renuméroté : c'est un identifiant, cité dans
    # les discussions. Un cas ajouté plus tard dans la section 2 prend le numéro
    # suivant du tableau, pas une place dans la suite de la section.
    numero = fields.Integer(string='Numéro', required=True, readonly=True)
    reference = fields.Char(string='N°', compute='_compute_reference', store=True)
    ecran = fields.Char(string='Écran', required=True)
    profil = fields.Char(string='Qui teste', required=True)
    action = fields.Text(string='Ce que je fais', required=True)
    attendu = fields.Text(string='Ce que je dois voir', required=True)
    active = fields.Boolean(default=True)

    # --- Zone du testeur : l'état du moment --------------------------------
    resultat = fields.Selection(RESULTATS, string='Résultat', required=True, default='non_teste')
    constat = fields.Text(string="Ce que j'ai vu")
    teste_par = fields.Many2one('res.users', string='Testé par', ondelete='restrict')
    teste_le = fields.Datetime(string='Testé le')
    version_apk = fields.Char(string='Version testée')

    # --- Zone du développeur : l'état du moment ----------------------------
    suite = fields.Selection(SUITES, string='Suite à donner')
    reponse = fields.Text(string='Réponse du développeur mobile')
    repondu_par = fields.Many2one('res.users', string='Répondu par', ondelete='restrict')
    repondu_le = fields.Datetime(string='Répondu le')

    # --- Suivi -------------------------------------------------------------
    # Qui a agi en dernier sur l'état : c'est ce qui départage, par exemple, un KO
    # posé avant ou après une réponse du développeur.
    dernier_acteur = fields.Selection([('testeur', 'Testeur'), ('developpeur', 'Développeur')],
                                      string='Dernier acteur')
    tour = fields.Integer(string='Tour', default=0)
    balle = fields.Selection(BALLES, string='À qui la balle', compute='_compute_balle', store=True)
    echange_ids = fields.One2many('nkezefuu.recette.echange', 'cas_id', string='Discussion')

    _numero_unique = models.Constraint('unique(tableau_id, numero)',
                                       'Ce numéro de cas existe déjà dans ce tableau.')

    @api.depends('tableau_id.prefixe', 'numero')
    def _compute_reference(self):
        for cas in self:
            cas.reference = '%s-%03d' % (cas.tableau_id.prefixe or '', cas.numero or 0)

    @api.depends('resultat', 'suite', 'dernier_acteur')
    def _compute_balle(self):
        for cas in self:
            if cas.dernier_acteur == 'developpeur':
                cas.balle = 'developpeur' if cas.suite == 'en_cours' else 'testeur'
            elif cas.resultat in RESULTATS_OK:
                cas.balle = 'termine'
            elif cas.resultat in RESULTATS_EN_ECHEC:
                cas.balle = 'developpeur'
            else:
                # Non testé, ou Bloqué : c'est au testeur de pouvoir avancer
                cas.balle = 'testeur'

    # ----------------------------------------------------------------------
    # Lectures utiles à l'API
    # ----------------------------------------------------------------------
    def _dernier_resultat_ok(self):
        """Dernier échange du testeur qui a validé le cas, pour afficher la version
        du dernier OK à côté d'une régression."""
        self.ensure_one()
        return self.echange_ids.filtered(
            lambda e: e.type == 'resultat' and e.statut in RESULTATS_OK
        )[-1:]

    def _echange_regression(self):
        self.ensure_one()
        if self.resultat != 'regression':
            return self.env['nkezefuu.recette.echange']
        return self.echange_ids.filtered(
            lambda e: e.type == 'resultat' and e.statut == 'regression'
        )[-1:]

    @api.model
    def _balles_du_profil(self, roles):
        """Les valeurs de « balle » qui désignent ce profil, pour le filtre « à moi »."""
        balles = []
        if TESTEUR in roles:
            balles.append('testeur')
        if DEVELOPPEUR in roles:
            balles.append('developpeur')
        return balles

    def _droits(self, roles):
        """Ce que ce profil peut faire sur cette ligne, pour que le site n'affiche
        que les boutons utilisables, sans recalculer les règles de son côté."""
        self.ensure_one()
        resultats, suites = [], []
        if self.active:
            if TESTEUR in roles:
                resultats = list(self._resultats_permis(roles))
            if DEVELOPPEUR in roles and self._peut_repondre():
                suites = [code for code, _label in SUITES]
        return {
            'resultats_permis': resultats,
            'suites_permises': suites,
            'peut_commenter': bool(roles),
            'peut_modifier': ADMIN in roles,
            'peut_archiver': ADMIN in roles and self.active,
            'peut_restaurer': ADMIN in roles and not self.active,
        }

    def _resultats_permis(self, roles):
        self.ensure_one()
        if self.dernier_acteur == 'developpeur':
            permis = list(RESULTATS_APRES_REPONSE)
        else:
            permis = [r for r in RESULTATS_SANS_REPONSE
                      if r != 'regression' or self.resultat in RESULTATS_OK]
        # Remettre une ligne à « Non testé » est réservé à l'admin testeur, par
        # exemple après avoir réécrit ce qui est attendu.
        if ADMIN in roles and self.resultat != 'non_teste':
            permis.append('non_teste')
        return permis

    def _peut_repondre(self):
        self.ensure_one()
        return self.dernier_acteur == 'developpeur' or self.resultat in RESULTATS_A_TRAITER

    # ----------------------------------------------------------------------
    # Écritures : seules portes d'entrée de l'API
    # ----------------------------------------------------------------------
    def _ajouter_echange(self, user, type_echange, statut=False, texte=False, version_apk=False):
        self.ensure_one()
        return self.env['nkezefuu.recette.echange'].sudo().create({
            'cas_id': self.id,
            'tour': self.tour,
            'type': type_echange,
            'statut': statut,
            'texte': texte,
            'version_apk': version_apk,
            'auteur_id': user.id,
        })

    @api.model
    def creer(self, user, tableau, section, ecran, profil, action, attendu):
        """Ajout d'un cas depuis le site : tous les profils."""
        if not user._recette_roles():
            raise AccessError("Ce compte n'a pas accès à la recette.")
        if section.tableau_id != tableau:
            raise UserError("Cette section n'appartient pas à ce tableau.")
        valeurs = {'ecran': ecran, 'profil': profil, 'action': action, 'attendu': attendu}
        manquants = [LIBELLES_TEXTE[k] for k, v in valeurs.items() if not (v or '').strip()]
        if manquants:
            raise UserError("Champs obligatoires manquants : %s." % ', '.join(manquants))

        tous = self.sudo().with_context(active_test=False)
        dernier = tous.search([('tableau_id', '=', tableau.id)], order='numero desc', limit=1)
        dans_section = tous.search([('section_id', '=', section.id)], order='sequence desc', limit=1)
        return self.sudo().create(dict(
            {k: v.strip() for k, v in valeurs.items()},
            tableau_id=tableau.id,
            section_id=section.id,
            numero=(dernier.numero or 0) + 1,
            sequence=(dans_section.sequence or 0) + 10,
        ))

    def poser_resultat(self, user, resultat, constat=False, version_apk=False):
        """Le testeur pose un résultat. Ouvre un nouveau tour s'il reprend la main
        après une réponse du développeur, ou s'il signale une régression."""
        self.ensure_one()
        roles = user._recette_roles()
        if TESTEUR not in roles:
            raise AccessError("Seul un testeur peut poser un résultat.")
        if not self.active:
            raise UserError("Ce cas est archivé.")
        if resultat not in dict(RESULTATS):
            raise UserError("Résultat inconnu : %s." % resultat)

        if resultat not in self._resultats_permis(roles):
            if resultat == 'regression':
                raise UserError("Ce cas n'a jamais été validé : il ne peut pas régresser. "
                                "Posez KO.")
            if resultat in ('ok_apres_correction', 'toujours_ko'):
                raise UserError("Aucune réponse du développeur n'est en attente sur ce cas. "
                                "Posez OK ou KO.")
            if resultat == 'ko':
                raise UserError("Le développeur a répondu : posez Toujours KO, "
                                "OK après correction, ou OK si vous acceptez sa réponse.")
            if resultat == 'non_teste':
                raise UserError("Seul l'admin testeur peut remettre un cas à « Non testé ».")
            raise UserError("Ce résultat n'est pas possible dans l'état actuel du cas.")

        constat = (constat or '').strip()
        version_apk = (version_apk or '').strip()
        if resultat in RESULTATS_AVEC_CONSTAT and not constat:
            raise UserError("Décrivez ce que vous avez vu : sans constat, le développeur "
                            "ne peut pas reproduire le problème.")
        if resultat != 'non_teste' and not version_apk:
            raise UserError("Indiquez la version de l'application testée.")

        # Un tour s'ouvre au premier test, au premier test qui suit une remise à zéro,
        # quand le testeur reprend la main après une réponse, ou sur une régression.
        # La remise à zéro elle-même n'en ouvre pas.
        nouveau_tour = resultat != 'non_teste' and (
            self.tour == 0
            or self.resultat == 'non_teste'
            or self.dernier_acteur == 'developpeur'
            or resultat == 'regression'
        )
        vals = {
            'resultat': resultat,
            'constat': constat or False,
            'teste_par': user.id,
            'teste_le': fields.Datetime.now(),
            'version_apk': version_apk or False,
            'dernier_acteur': 'testeur',
        }
        if nouveau_tour:
            vals['tour'] = self.tour + 1
        if nouveau_tour or resultat == 'non_teste':
            # Nouvel aller-retour : la zone du développeur repart vide sur la ligne,
            # sa réponse précédente reste dans la discussion.
            vals.update({'suite': False, 'reponse': False, 'repondu_par': False, 'repondu_le': False})
        if resultat == 'non_teste':
            vals.update({'constat': False, 'version_apk': False, 'dernier_acteur': False})

        self.sudo().write(vals)
        self._ajouter_echange(user, 'resultat', statut=resultat, texte=constat or False,
                              version_apk=version_apk or False)
        return self

    def poser_suite(self, user, suite, reponse=False):
        """Le développeur mobile répond au testeur."""
        self.ensure_one()
        if DEVELOPPEUR not in user._recette_roles():
            raise AccessError("Seul le développeur mobile peut poser une suite.")
        if not self.active:
            raise UserError("Ce cas est archivé.")
        if suite not in dict(SUITES):
            raise UserError("Suite inconnue : %s." % suite)
        if not self._peut_repondre():
            raise UserError("Rien à traiter : le testeur n'a pas signalé de problème sur ce cas.")
        reponse = (reponse or '').strip()
        if suite not in SUITES_SANS_TEXTE and not reponse:
            raise UserError("Expliquez votre réponse : le testeur doit savoir quoi revérifier, "
                            "ou pourquoi ce n'est pas un défaut.")

        self.sudo().write({
            'suite': suite,
            'reponse': reponse or False,
            'repondu_par': user.id,
            'repondu_le': fields.Datetime.now(),
            'dernier_acteur': 'developpeur',
        })
        self._ajouter_echange(user, 'suite', statut=suite, texte=reponse or False)
        return self

    def commenter(self, user, texte):
        """Message libre, sans changer l'état : tous les profils."""
        self.ensure_one()
        if not user._recette_roles():
            raise AccessError("Ce compte n'a pas accès à la recette.")
        texte = (texte or '').strip()
        if not texte:
            raise UserError("Le commentaire est vide.")
        self._ajouter_echange(user, 'commentaire', texte=texte)
        return self

    def modifier(self, user, vals):
        """Correction du texte d'un cas : admin testeur seulement. Chaque champ
        changé est tracé dans la discussion, ancienne et nouvelle valeur."""
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'admin testeur peut modifier un cas existant.")

        changements, nouvelles = [], {}
        for champ in CHAMPS_TEXTE:
            if champ not in vals:
                continue
            valeur = (vals[champ] or '').strip()
            if not valeur:
                raise UserError("Le champ « %s » ne peut pas être vide." % LIBELLES_TEXTE[champ])
            if valeur != self[champ]:
                changements.append("%s : « %s » devient « %s »" % (LIBELLES_TEXTE[champ], self[champ], valeur))
                nouvelles[champ] = valeur

        if 'section_id' in vals:
            section = self.env['nkezefuu.recette.section'].sudo().browse(int(vals['section_id'] or 0)).exists()
            if not section or section.tableau_id != self.tableau_id:
                raise UserError("Section introuvable dans ce tableau.")
            if section != self.section_id:
                changements.append("Section : « %s » devient « %s »" % (self.section_id.name, section.name))
                nouvelles['section_id'] = section.id

        if not nouvelles:
            return self
        self.sudo().write(nouvelles)
        self._ajouter_echange(user, 'modification', texte="\n".join(changements))
        return self

    def archiver(self, user):
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'admin testeur peut archiver un cas.")
        if not self.active:
            raise UserError("Ce cas est déjà archivé.")
        self.sudo().write({'active': False})
        self._ajouter_echange(user, 'archivage')
        return self

    def restaurer(self, user):
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'admin testeur peut restaurer un cas.")
        if self.active:
            raise UserError("Ce cas n'est pas archivé.")
        self.sudo().write({'active': True})
        self._ajouter_echange(user, 'restauration')
        return self
