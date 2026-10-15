# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .res_users import ADMIN, DEVELOPPEUR, TESTEUR

RESULTATS = [
    ('not_tested', 'Non testé'),
    ('passed', 'Conforme'),
    # Ce qui était demandé est bon, mais un point reste à corriger (souvent sur un
    # ajout du développeur) : le cas retourne au développeur avec la réserve à lever.
    ('passed_with_reserve', 'Conforme avec réserve'),
    ('failed', 'Non conforme'),
    ('blocked', 'Bloqué'),
    # La fonction, l'écran ou le bouton n'existe pas dans l'application : à ne pas
    # confondre avec Non conforme (elle existe mais se comporte mal) ni avec Bloqué
    # (le test est empêché par autre chose, et reste à la main du testeur).
    ('not_implemented', 'Non implémenté'),
    ('passed_after_fix', 'Conforme après correction'),
    ('still_failing', 'Toujours non conforme'),
    # Posé seulement par le signalement d'une régression, sur le cas créé dans la
    # version en recette (signaler_regression) : jamais choisi dans la liste.
    ('regression', 'Régression'),
    # Décision de l'administrateur de recette : la version peut sortir sans ce cas,
    # qui est repris automatiquement dans la version suivante.
    ('postponed', 'Reporté'),
]

ORIGINES = [
    ('regression', 'Régression'),
    ('postponed', 'Report'),
]

SUITES = [
    ('in_progress', "En cours d'analyse"),
    ('fixed_to_retest', 'Corrigé, à retester'),
    ('works_as_intended', 'Fonctionnement normal'),
    ('needs_clarification', 'Précisions demandées'),
]

BALLES = [
    ('tester', 'Testeur'),
    ('developer', 'Développeur'),
    ('closed', 'Clôturé'),
]

RESULTATS_OK = ('passed', 'passed_after_fix')
RESULTATS_EN_ECHEC = ('passed_with_reserve', 'failed', 'still_failing', 'regression', 'not_implemented')

# Ce que le testeur peut poser selon que le développeur a répondu en dernier ou non.
# Après une réponse, il confirme ou conteste ; sans réponse, il constate.
# Non implémenté reste possible après une réponse : la fonction peut être toujours
# absente de la version livrée.
RESULTATS_SANS_REPONSE = ('passed', 'passed_with_reserve', 'failed', 'blocked', 'not_implemented')
RESULTATS_APRES_REPONSE = ('passed', 'passed_after_fix', 'passed_with_reserve', 'still_failing', 'blocked',
                           'not_implemented')

# Le résultat observé est exigé dès que quelque chose ne va pas : un cas en échec
# sans explication ne sert à rien au développeur. Pour un report, le même champ
# porte le motif, et pour une conformité avec réserve, la réserve.
RESULTATS_AVEC_CONSTAT = ('passed_with_reserve', 'failed', 'still_failing', 'regression', 'blocked', 'not_implemented', 'postponed')

# Le développeur ne peut répondre que si le testeur attend son action, ou pour
# compléter sa propre réponse tant que le testeur n'a pas repris la main.
RESULTATS_A_TRAITER = ('passed_with_reserve', 'failed', 'still_failing', 'regression', 'blocked', 'not_implemented')

# Une réponse sans explication est acceptée pour « En cours d'analyse » et « Corrigé, à
# retester » : le testeur rejoue le même cas, le statut suffit. « Fonctionnement normal »
# doit dire pourquoi, et « Précisions demandées » ce qui manque.
SUITES_SANS_TEXTE = ('in_progress', 'fixed_to_retest')

CHAMPS_TEXTE = ('ecran', 'profil', 'action', 'attendu')
LIBELLES_TEXTE = {
    'ecran': 'Écran',
    'profil': 'Profil utilisateur',
    'action': 'Action à réaliser',
    'attendu': 'Résultat attendu',
}


class RecetteCas(models.Model):
    """Un cas de recette, rattaché à une étape de parcours et à une version de
    l'application, et testé dans l'application mobile.

    Les cas sont livrés par les données du module : ils rejoignent la version en
    recette au moment où ils sont créés. Le serveur en crée aussi deux sortes, liées
    à leur cas d'origine : la régression signalée sur un cas conforme d'une version
    publiée, et la reprise d'un cas reporté à l'ouverture de la version suivante.
    Le site ne crée pas de cas, l'administrateur de recette les reformule seulement.

    Une fois sa version publiée, un cas ne change plus : seul le signalement d'une
    régression reste possible depuis lui.

    Les champs d'état (résultat, suite, horodatages, itération, action attendue) ne
    changent que par
    poser_resultat / poser_suite, qui ajoutent l'échange correspondant dans la même
    transaction. Aucun accès en écriture direct n'est donné (ir.model.access) :
    tout passe par l'API, qui appelle ces méthodes.
    """
    _name = 'nkezefuu.recette.cas'
    _description = 'Cas de recette'
    _order = 'version_id, parcours_id, sequence, numero'
    _rec_name = 'reference'

    # --- Le cas de test ----------------------------------------------------
    # Un cas créé sans version rejoint celle en recette (voir create).
    version_id = fields.Many2one('nkezefuu.recette.version', string='Version', required=True,
                                 ondelete='restrict', index=True)
    # restrict : une étape retirée des fichiers de parcours ne doit pas emporter ses
    # cas et leurs résultats (voir nkezefuu.doc.chargement).
    etape_id = fields.Many2one('nkezefuu.doc.etape', string='Étape du parcours', required=True,
                               ondelete='restrict', index=True)
    parcours_id = fields.Many2one('nkezefuu.doc.parcours', string='Parcours', related='etape_id.parcours_id',
                                  store=True, index=True)
    # Ordre du cas dans son étape
    sequence = fields.Integer(string='Séquence', default=10)
    # Jamais renuméroté : c'est un identifiant, cité dans les échanges. Un cas créé
    # sans numéro prend le suivant du parcours, quelle que soit son étape ou sa
    # version (voir create).
    numero = fields.Integer(string='Numéro', required=True, readonly=True)
    reference = fields.Char(string='Réf.', compute='_compute_reference', store=True)
    ecran = fields.Char(string='Écran', required=True)
    profil = fields.Char(string='Profil utilisateur', required=True)
    action = fields.Text(string='Action à réaliser', required=True)
    attendu = fields.Text(string='Résultat attendu', required=True)
    active = fields.Boolean(default=True)

    # --- Lien avec un cas d'une version publiée -----------------------------
    origine_id = fields.Many2one('nkezefuu.recette.cas', string="Cas d'origine", ondelete='restrict',
                                 index=True, readonly=True)
    origine_type = fields.Selection(ORIGINES, string='Origine', readonly=True)
    reprise_ids = fields.One2many('nkezefuu.recette.cas', 'origine_id', string='Repris dans',
                                  context={'active_test': False})

    # --- Zone du testeur : l'état du moment --------------------------------
    resultat = fields.Selection(RESULTATS, string='Résultat', required=True, default='not_tested')
    constat = fields.Text(string='Résultat observé')
    teste_par = fields.Many2one('res.users', string='Testé par', ondelete='restrict')
    teste_le = fields.Datetime(string='Testé le')

    # --- Zone du développeur : l'état du moment ----------------------------
    suite = fields.Selection(SUITES, string='Statut de correction')
    reponse = fields.Text(string='Réponse du développeur mobile')
    repondu_par = fields.Many2one('res.users', string='Répondu par', ondelete='restrict')
    repondu_le = fields.Datetime(string='Répondu le')

    # --- Suivi -------------------------------------------------------------
    # Qui a agi en dernier sur l'état : c'est ce qui départage, par exemple, un
    # Non conforme posé avant ou après une réponse du développeur.
    dernier_acteur = fields.Selection([('tester', 'Testeur'), ('developer', 'Développeur')],
                                      string='Dernier acteur')
    tour = fields.Integer(string='Itération', default=0)
    balle = fields.Selection(BALLES, string='Action attendue de', compute='_compute_balle', store=True)
    echange_ids = fields.One2many('nkezefuu.recette.echange', 'cas_id', string='Historique des échanges')

    _numero_unique = models.Constraint('unique(parcours_id, numero)',
                                       'Ce numéro de cas existe déjà dans ce parcours.')

    @api.model_create_multi
    def create(self, vals_list):
        if any(not vals.get('version_id') for vals in vals_list):
            en_recette = self.env['nkezefuu.recette.version']._en_recette()
            if not en_recette:
                raise UserError("Aucune version n'est en recette : déclarez-la dans "
                                "data/recette_versions.xml avant d'ajouter des cas.")
            for vals in vals_list:
                vals.setdefault('version_id', en_recette.id)
        Etape = self.env['nkezefuu.doc.etape'].sudo()
        dernier = {}
        for vals in vals_list:
            if vals.get('numero'):
                continue
            parcours = Etape.browse(vals['etape_id']).parcours_id
            if parcours.id not in dernier:
                # Par l'étape : le parcours du cas est un champ calculé, pas encore
                # écrit en base pour un cas créé dans la même transaction.
                self.env.cr.execute("""
                    SELECT COALESCE(MAX(c.numero), 0)
                      FROM nkezefuu_recette_cas c
                      JOIN nkezefuu_doc_etape e ON e.id = c.etape_id
                     WHERE e.parcours_id = %s
                """, (parcours.id,))
                dernier[parcours.id] = self.env.cr.fetchone()[0]
            dernier[parcours.id] += 1
            vals['numero'] = dernier[parcours.id]
        return super().create(vals_list)

    @api.depends('parcours_id.prefixe_recette', 'numero')
    def _compute_reference(self):
        for cas in self:
            cas.reference = '%s-%03d' % (cas.parcours_id.prefixe_recette or '', cas.numero or 0)

    @api.depends('resultat', 'suite', 'dernier_acteur')
    def _compute_balle(self):
        for cas in self:
            if cas.resultat == 'postponed':
                cas.balle = 'closed'
            elif cas.dernier_acteur == 'developer':
                cas.balle = 'developer' if cas.suite == 'in_progress' else 'tester'
            elif cas.resultat in RESULTATS_OK:
                cas.balle = 'closed'
            elif cas.resultat in RESULTATS_EN_ECHEC:
                cas.balle = 'developer'
            else:
                # Non testé, ou Bloqué : c'est au testeur d'avancer
                cas.balle = 'tester'

    # ----------------------------------------------------------------------
    # Lectures utiles à l'API
    # ----------------------------------------------------------------------
    def _en_recette(self):
        self.ensure_one()
        return self.version_id.etat == 'in_progress'

    def _verifier_modifiable(self):
        self.ensure_one()
        if not self._en_recette():
            raise UserError("La version %s est publiée : ses cas ne se modifient plus." % self.version_id.name)

    def _regression_ouverte(self):
        """Régression déjà signalée depuis ce cas, dans la version en recette."""
        self.ensure_one()
        return self.reprise_ids.filtered(
            lambda c: c.origine_type == 'regression' and c.version_id.etat == 'in_progress')[:1]

    def _droits(self, roles):
        """Ce que ce profil peut faire sur ce cas, pour que le site n'affiche
        que les boutons utilisables, sans recalculer les règles de son côté."""
        self.ensure_one()
        if not self._en_recette():
            # Version publiée : lecture seule, hormis le signalement d'une régression.
            return {
                'allowed_results': [],
                'allowed_fix_statuses': [],
                'can_comment': False,
                'can_edit': False,
                'can_archive': False,
                'can_restore': False,
                'can_report_regression': bool(TESTEUR in roles and self.active and self.resultat in RESULTATS_OK
                                              and not self._regression_ouverte()),
            }
        resultats, suites = [], []
        if self.active:
            if TESTEUR in roles:
                resultats = list(self._resultats_permis(roles))
            if DEVELOPPEUR in roles and self._peut_repondre():
                suites = [code for code, _label in SUITES]
        return {
            'allowed_results': resultats,
            'allowed_fix_statuses': suites,
            'can_comment': bool(roles),
            'can_edit': ADMIN in roles,
            'can_archive': ADMIN in roles and self.active,
            'can_restore': ADMIN in roles and not self.active,
            'can_report_regression': False,
        }

    def _resultats_permis(self, roles):
        self.ensure_one()
        if self.dernier_acteur == 'developer':
            permis = list(RESULTATS_APRES_REPONSE)
        else:
            permis = list(RESULTATS_SANS_REPONSE)
        # Reporter un cas, ou le remettre à « Non testé » (par exemple après avoir
        # réécrit le résultat attendu), est réservé à l'administrateur de recette.
        if ADMIN in roles:
            if self.resultat != 'postponed':
                permis.append('postponed')
            if self.resultat != 'not_tested':
                permis.append('not_tested')
        return permis

    def _peut_repondre(self):
        self.ensure_one()
        return self.dernier_acteur == 'developer' or self.resultat in RESULTATS_A_TRAITER

    # ----------------------------------------------------------------------
    # Écritures : seules portes d'entrée de l'API
    # ----------------------------------------------------------------------
    def _ajouter_echange(self, user, type_echange, statut=False, texte=False):
        self.ensure_one()
        return self.env['nkezefuu.recette.echange'].sudo().create({
            'cas_id': self.id,
            'tour': self.tour,
            'type': type_echange,
            'statut': statut,
            'texte': texte,
            'auteur_id': user.id,
        })

    def poser_resultat(self, user, resultat, constat=False):
        """Le testeur pose un résultat, ou l'administrateur de recette reporte le
        cas. Ouvre un nouveau tour au premier test, ou quand le testeur reprend la
        main après une réponse du développeur."""
        self.ensure_one()
        roles = user._recette_roles()
        if TESTEUR not in roles:
            raise AccessError("Seul un testeur peut poser un résultat.")
        self._verifier_modifiable()
        if not self.active:
            raise UserError("Ce cas est archivé.")
        if resultat not in dict(RESULTATS):
            raise UserError("Résultat inconnu : %s." % resultat)

        if resultat not in self._resultats_permis(roles):
            if resultat == 'regression':
                raise UserError("Une régression se signale depuis le cas conforme d'une version publiée.")
            if resultat == 'postponed' and ADMIN not in roles:
                raise UserError("Seul l'administrateur de recette peut reporter un cas.")
            if resultat in ('passed_after_fix', 'still_failing'):
                raise UserError("Aucune réponse du développeur n'est en attente sur ce cas. "
                                "Posez « Conforme » ou « Non conforme ».")
            if resultat == 'failed':
                raise UserError("Le développeur a répondu : posez « Toujours non conforme », "
                                "« Conforme après correction », ou « Conforme » si vous acceptez sa réponse.")
            if resultat == 'not_tested':
                raise UserError("Seul l'administrateur de recette peut remettre un cas à « Non testé ».")
            raise UserError("Ce résultat n'est pas possible dans l'état actuel du cas.")

        constat = (constat or '').strip()
        if resultat == 'postponed' and not constat:
            raise UserError("Indiquez le motif du report.")
        if resultat == 'passed_with_reserve' and not constat:
            raise UserError("Indiquez la réserve : ce qui reste à corriger pour que le cas soit conforme.")
        if resultat in RESULTATS_AVEC_CONSTAT and not constat:
            raise UserError("Renseignez le résultat observé : sans lui, le développeur "
                            "ne peut pas reproduire le problème.")

        # Une itération s'ouvre au premier test, au premier test qui suit une remise à
        # zéro, ou quand le testeur reprend la main après une réponse. Ni la remise à
        # zéro ni le report, qui sont des décisions et non des tests, n'en ouvrent.
        nouveau_tour = resultat not in ('not_tested', 'postponed') and (
            self.tour == 0
            or self.resultat == 'not_tested'
            or self.dernier_acteur == 'developer'
        )
        vals = {
            'resultat': resultat,
            'constat': constat or False,
            'teste_par': user.id,
            'teste_le': fields.Datetime.now(),
            'dernier_acteur': 'tester',
        }
        if nouveau_tour:
            vals['tour'] = self.tour + 1
        if nouveau_tour or resultat == 'not_tested':
            # Nouvel aller-retour : la zone du développeur repart vide sur le cas,
            # sa réponse précédente reste dans l'historique.
            vals.update({'suite': False, 'reponse': False, 'repondu_par': False, 'repondu_le': False})
        if resultat == 'not_tested':
            vals.update({'constat': False, 'dernier_acteur': False})

        self.sudo().write(vals)
        self._ajouter_echange(user, 'result', statut=resultat, texte=constat or False)
        return self

    def poser_suite(self, user, suite, reponse=False):
        """Le développeur mobile répond au testeur."""
        self.ensure_one()
        if DEVELOPPEUR not in user._recette_roles():
            raise AccessError("Seul le développeur mobile peut répondre.")
        self._verifier_modifiable()
        if not self.active:
            raise UserError("Ce cas est archivé.")
        if suite not in dict(SUITES):
            raise UserError("Statut de correction inconnu : %s." % suite)
        if not self._peut_repondre():
            raise UserError("Rien à traiter : le testeur n'a pas signalé de problème sur ce cas.")
        reponse = (reponse or '').strip()
        if suite not in SUITES_SANS_TEXTE and not reponse:
            raise UserError("Expliquez votre réponse : le testeur doit savoir pourquoi le "
                            "fonctionnement est normal, ou quelle précision vous attendez.")

        self.sudo().write({
            'suite': suite,
            'reponse': reponse or False,
            'repondu_par': user.id,
            'repondu_le': fields.Datetime.now(),
            'dernier_acteur': 'developer',
        })
        self._ajouter_echange(user, 'reply', statut=suite, texte=reponse or False)
        return self

    @api.model
    def signaler_etape_non_implementee(self, user, etape, constat):
        """Le testeur signale en une fois qu'une étape entière manque dans
        l'application : chaque cas encore non testé de l'étape, dans la version en
        recette, passe en « Non implémenté », avec le même résultat observé, comme
        s'il était posé cas par cas. Les cas déjà testés gardent leur résultat."""
        if TESTEUR not in user._recette_roles():
            raise AccessError("Seul un testeur peut signaler une étape non implémentée.")
        cases = self.sudo().search([('etape_id', '=', etape.id), ('resultat', '=', 'not_tested'),
                                    ('version_id.etat', '=', 'in_progress')])
        if not cases:
            raise UserError("Aucun cas non testé dans cette étape : signalez les cas un par un.")
        for cas in cases:
            cas.poser_resultat(user, 'not_implemented', constat)
        return cases

    def _reprendre(self, version, origine_type):
        """Nouveau cas dans `version`, avec la même consigne que celui-ci, lié à lui
        comme cas d'origine. Il prend le numéro suivant du parcours."""
        self.ensure_one()
        return self.sudo().create({
            'version_id': version.id,
            'etape_id': self.etape_id.id,
            'sequence': self.sequence,
            'ecran': self.ecran,
            'profil': self.profil,
            'action': self.action,
            'attendu': self.attendu,
            'origine_id': self.id,
            'origine_type': origine_type,
        })

    def signaler_regression(self, user, constat):
        """Le testeur constate qu'un cas conforme d'une version publiée ne
        fonctionne plus. Le cas d'origine ne change pas : un nouveau cas est créé
        dans la version en recette, en « Régression », et suit le circuit habituel.
        S'il n'y a pas de version en recette, un Correctif est ouvert."""
        self.ensure_one()
        if TESTEUR not in user._recette_roles():
            raise AccessError("Seul un testeur peut signaler une régression.")
        if self._en_recette():
            raise UserError("Ce cas est dans la version en recette : posez « Non conforme ».")
        if not self.active or self.resultat not in RESULTATS_OK:
            raise UserError("Une régression se signale depuis un cas conforme.")
        deja = self._regression_ouverte()
        if deja:
            raise UserError("Régression déjà signalée en %s (%s)." % (deja.version_id.name, deja.reference))
        constat = (constat or '').strip()
        if not constat:
            raise UserError("Renseignez le résultat observé : sans lui, le développeur "
                            "ne peut pas reproduire le problème.")

        version = self.env['nkezefuu.recette.version']._ouvrir_correctif()
        cas = self._reprendre(version, 'regression')
        cas.write({
            'resultat': 'regression',
            'constat': constat,
            'teste_par': user.id,
            'teste_le': fields.Datetime.now(),
            'dernier_acteur': 'tester',
            'tour': 1,
        })
        cas._ajouter_echange(user, 'result', statut='regression', texte=constat)
        return cas

    def commenter(self, user, texte):
        """Message libre, sans changer l'état : tous les profils."""
        self.ensure_one()
        if not user._recette_roles():
            raise AccessError("Ce compte n'a pas accès à la recette.")
        self._verifier_modifiable()
        texte = (texte or '').strip()
        if not texte:
            raise UserError("Le commentaire est vide.")
        self._ajouter_echange(user, 'comment', texte=texte)
        return self

    def modifier(self, user, vals):
        """Reformulation d'un cas, ou changement d'étape dans le même parcours :
        administrateur de recette seulement. Chaque champ changé est tracé dans
        l'historique, ancienne et nouvelle valeur."""
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'administrateur de recette peut modifier un cas.")
        self._verifier_modifiable()

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

        if 'etape_id' in vals:
            etape = self.env['nkezefuu.doc.etape'].sudo().browse(int(vals['etape_id'] or 0)).exists()
            if not etape or etape.parcours_id != self.parcours_id:
                raise UserError("Étape introuvable dans ce parcours.")
            if etape != self.etape_id:
                changements.append("Étape : « %s » devient « %s »" % (self.etape_id.titre, etape.titre))
                nouvelles['etape_id'] = etape.id

        if not nouvelles:
            return self
        self.sudo().write(nouvelles)
        self._ajouter_echange(user, 'edit', texte="\n".join(changements))
        return self

    def archiver(self, user):
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'administrateur de recette peut archiver un cas.")
        self._verifier_modifiable()
        if not self.active:
            raise UserError("Ce cas est déjà archivé.")
        self.sudo().write({'active': False})
        self._ajouter_echange(user, 'archive')
        return self

    def restaurer(self, user):
        self.ensure_one()
        if ADMIN not in user._recette_roles():
            raise AccessError("Seul l'administrateur de recette peut restaurer un cas.")
        self._verifier_modifiable()
        if self.active:
            raise UserError("Ce cas n'est pas archivé.")
        self.sudo().write({'active': True})
        self._ajouter_echange(user, 'restore')
        return self
