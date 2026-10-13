# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.exceptions import AccessDenied, MissingError, UserError, ValidationError
from odoo.http import request
from werkzeug.wrappers import Response

from ..models.recette_cas import BALLES, RESULTATS, SUITES
from ..models.recette_echange import TYPES_ECHANGE
from .socle import SocleApi

_logger = logging.getLogger(__name__)

# Odoo de base ne refuse que le mot de passe vide : le module de politique de mots de
# passe n'est pas installé sur cette instance.
LONGUEUR_MIN_MOT_DE_PASSE = 8

COUNTERS = ('total', 'not_tested', 'passed', 'failed', 'regression', 'blocked', 'not_implemented', 'assigned_to_me')

# Champs d'un cas que l'administrateur de recette peut modifier : nom dans l'API,
# nom du champ Odoo.
CHAMPS_MODIFIABLES = {
    'screen': 'ecran',
    'user_profile': 'profil',
    'action': 'action',
    'expected_result': 'attendu',
    'step_id': 'etape_id',
}


class RecetteController(SocleApi, http.Controller):
    """Connexion au site apps-docs.nkezefuu.com, compte de l'utilisateur, et API
    de la recette.

    Les règles (qui peut poser quoi, l'action attendue, les itérations) sont dans
    les méthodes de nkezefuu.recette.cas : ce contrôleur authentifie, lit le
    corps, appelle, et sérialise. Chaque écriture tourne dans un savepoint, pour
    qu'un refus au milieu d'une opération n'en laisse rien en base.
    """

    # ------------------------------------------------------------------
    # Sérialisation
    # ------------------------------------------------------------------
    @staticmethod
    def _dt(value):
        # Odoo stocke en UTC : le Z final permet au navigateur de convertir en heure locale.
        return value.strftime('%Y-%m-%dT%H:%M:%SZ') if value else None

    @staticmethod
    def _user(user):
        return {'id': user.id, 'name': user.name} if user else None

    def _compteurs(self, cases, user):
        balles = cases._balles_du_profil(user._recette_roles())
        resultats = cases.mapped('resultat')
        return {
            'total': len(cases),
            'not_tested': resultats.count('not_tested'),
            'passed': resultats.count('passed') + resultats.count('passed_after_fix'),
            'failed': resultats.count('failed') + resultats.count('still_failing'),
            'regression': resultats.count('regression'),
            'blocked': resultats.count('blocked'),
            'not_implemented': resultats.count('not_implemented'),
            # En attente d'une action de ce profil
            'assigned_to_me': len(cases.filtered(lambda c: c.balle in balles)),
        }

    def _serialize_journey(self, parcours, user):
        cases = request.env['nkezefuu.recette.cas'].sudo().search([('parcours_id', '=', parcours.id)])
        return {
            'code': parcours.code,
            'name': parcours.name,
            'group': parcours.groupe,
            'prefix': parcours.prefixe_recette,
            'counters': self._compteurs(cases, user),
        }

    def _serialize_cas(self, cas, user, numeros, avec_echanges=False):
        """numeros : {id d'étape: numéro affiché}, calculé une fois par parcours."""
        roles = user._recette_roles()
        dernier_ok = cas._dernier_resultat_ok()
        regression = cas._echange_regression()
        data = {
            'id': cas.id,
            'reference': cas.reference,
            'number': cas.numero,
            'journey': {'code': cas.parcours_id.code, 'name': cas.parcours_id.name},
            'step': {'id': cas.etape_id.id, 'key': cas.etape_id.cle,
                     'number': numeros.get(cas.etape_id.id), 'title': cas.etape_id.titre},
            'screen': cas.ecran,
            'user_profile': cas.profil,
            'action': cas.action,
            'expected_result': cas.attendu,
            'active': cas.active,
            'result': self._sel(cas.resultat, RESULTATS),
            'observed_result': cas.constat or '',
            'tested_by': self._user(cas.teste_par),
            'tested_at': self._dt(cas.teste_le),
            'app_version': cas.version_apk or '',
            'fix_status': self._sel(cas.suite, SUITES),
            'reply': cas.reponse or '',
            'replied_by': self._user(cas.repondu_par),
            'replied_at': self._dt(cas.repondu_le),
            'iteration': cas.tour,
            'awaiting': self._sel(cas.balle, BALLES),
            'last_passed_version': dernier_ok.version_apk or None,
            'regression_version': regression.version_apk or None,
            'permissions': cas._droits(roles),
        }
        if avec_echanges:
            data['history'] = [self._serialize_echange(e) for e in cas.echange_ids]
        return data

    def _serialize_echange(self, echange):
        selection = RESULTATS if echange.type == 'result' else SUITES if echange.type == 'reply' else []
        return {
            'id': echange.id,
            'iteration': echange.tour,
            'type': self._sel(echange.type, TYPES_ECHANGE),
            'status': self._sel(echange.statut, selection) if echange.statut else None,
            'text': echange.texte or '',
            'app_version': echange.version_apk or '',
            'author': self._user(echange.auteur_id),
            'date': self._dt(echange.create_date),
        }

    def _serialize_step(self, etape, cases, user, numeros):
        """Une étape de la recette avec ses cas, pris dans `cases` (déjà filtrés)."""
        return {
            'id': etape.id,
            'key': etape.cle,
            'number': numeros.get(etape.id),
            'title': etape.titre,
            'cases': [self._serialize_cas(c, user, numeros) for c in cases.filtered(lambda c: c.etape_id == etape)],
        }

    @staticmethod
    def _numeros(parcours):
        return {etape.id: numero for etape, numero in parcours._etapes_dans_l_ordre()}

    def _cas_complet(self, cas, user):
        cas.invalidate_recordset()
        return {'case': self._serialize_cas(cas, user, self._numeros(cas.parcours_id), avec_echanges=True)}

    def _get_cas(self, cas_id):
        cas = request.env['nkezefuu.recette.cas'].sudo().with_context(active_test=False).browse(cas_id).exists()
        if not cas:
            raise MissingError('Cas introuvable')
        return cas

    # ------------------------------------------------------------------
    # Connexion et compte
    # ------------------------------------------------------------------
    @staticmethod
    def _profil(user):
        return {'id': user.id, 'name': user.name, 'login': user.login, 'roles': sorted(user._recette_roles())}

    def _session(self, user, paire):
        return dict(paire, user=self._profil(user))

    @http.route('/api/recette/auth/login', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def login(self, **kw):
        """Identifiant et mot de passe contre une paire de jetons. Passe par
        res.users.authenticate, et donc par la protection d'Odoo contre les essais de
        mot de passe en rafale, sans ouvrir de session web."""
        headers = self._headers('POST')
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)
        try:
            body = self._body()
        except ValueError:
            return self._error(headers, 400, 'Format JSON invalide')
        login, password = body.get('login'), body.get('password')
        if not login or not password:
            return self._error(headers, 400, 'Identifiant et mot de passe requis')
        try:
            auth_info = request.env['res.users'].authenticate(
                {'type': 'password', 'login': login, 'password': password},
                {'interactive': True})
        except AccessDenied:
            # Message volontairement identique que l'identifiant existe ou non : la
            # page de connexion est publique, elle ne doit pas permettre de deviner
            # les comptes.
            return self._error(headers, 401, 'Identifiant ou mot de passe incorrect')

        user = request.env['res.users'].sudo().browse(auth_info['uid'])
        if not user._recette_roles():
            return self._error(headers, 403, "Ce compte n'a pas accès au site.")
        paire = request.env['nkezefuu.recette.jeton']._emettre(user)
        return self._ok(headers, **self._session(user, paire))

    @http.route('/api/recette/auth/refresh', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def refresh(self, **kw):
        """Nouvelle paire contre le jeton de renouvellement, qui est consommé. À
        appeler quand une route répond 401, sans redemander le mot de passe."""
        headers = self._headers('POST')
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)
        try:
            body = self._body()
        except ValueError:
            return self._error(headers, 400, 'Format JSON invalide')
        paire = request.env['nkezefuu.recette.jeton']._renouveler(body.get('refresh_token'))
        if not paire:
            return self._error(headers, 401, 'Session expirée, reconnectez-vous')
        user = request.env['nkezefuu.recette.jeton']._utilisateur_du_jeton(paire['token'])
        if not user._recette_roles():
            return self._error(headers, 403, "Ce compte n'a pas accès au site.")
        return self._ok(headers, **self._session(user, paire))

    @http.route('/api/recette/auth/logout', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def logout(self, **kw):
        headers = self._headers('POST')
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)
        request.env['nkezefuu.recette.jeton']._revoquer(self._jeton_bearer())
        return self._ok(headers)

    @http.route('/api/recette/account/profile', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def profile(self, **kw):
        def action(user, body):
            return {'user': self._profil(user)}
        return self._run('GET', action)

    @http.route('/api/recette/account/password', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def password(self, **kw):
        """L'utilisateur connecté change son mot de passe, en redonnant l'actuel pour
        qu'un jeton volé ne suffise pas à prendre le compte.

        change_password d'Odoo ne passe pas par la protection contre les essais en
        rafale de la connexion : on l'y fait passer ici, sinon cette route
        permettrait de deviner le mot de passe actuel sans limite.

        Toutes les paires de jetons du compte sont ensuite révoquées, ce qui
        déconnecte les autres appareils, et une nouvelle paire est renvoyée avec la
        session, comme à la connexion.
        """
        headers = self._headers('POST')
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)
        user, error = self._authenticate(headers)
        if error:
            return error
        try:
            body = self._body()
        except ValueError:
            return self._error(headers, 400, 'Format JSON invalide')
        ancien = body.get('current_password') or ''
        nouveau = (body.get('new_password') or '').strip()
        if not ancien or not nouveau:
            return self._error(headers, 400, 'Mot de passe actuel et nouveau mot de passe requis')
        if len(nouveau) < LONGUEUR_MIN_MOT_DE_PASSE:
            return self._error(headers, 400, 'Le nouveau mot de passe doit contenir au moins %d caractères'
                               % LONGUEUR_MIN_MOT_DE_PASSE)
        if nouveau == ancien:
            return self._error(headers, 400, "Le nouveau mot de passe doit être différent de l'actuel")

        Users = request.env['res.users']
        verifie = False
        try:
            with request.env.cr.savepoint():
                with Users._assert_can_auth(user=user.login):
                    # Entrer dans ce bloc veut dire qu'aucun délai d'attente n'est en
                    # cours : un refus levé avant vient de la protection, pas du mot
                    # de passe.
                    verifie = True
                    Users.change_password(ancien, nouveau)
                Jeton = request.env['nkezefuu.recette.jeton']
                Jeton._revoquer_tout(user)
                paire = Jeton._emettre(user)
        except AccessDenied:
            if not verifie:
                return self._error(headers, 429, 'Trop de tentatives, réessayez plus tard')
            # 400 et non 401 : sur un 401 le site renouvellerait les jetons, comme si
            # la session avait expiré.
            return self._error(headers, 400, 'Mot de passe actuel incorrect')
        except (UserError, ValidationError) as e:
            return self._error(headers, 400, str(e.args[0]) if e.args else str(e))
        except Exception as e:
            _logger.exception("Erreur API recette")
            return self._error(headers, 500, 'Une erreur est survenue: %s' % e)
        return self._ok(headers, **self._session(user, paire))

    # ------------------------------------------------------------------
    # Recette des parcours
    # ------------------------------------------------------------------
    @http.route('/api/recette/journeys', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def acceptance_journeys(self, **kw):
        """Tableau de bord : les indicateurs de chaque parcours, et leur synthèse."""
        def action(user, body):
            tous = request.env['nkezefuu.doc.parcours'].sudo().search([])
            data = [self._serialize_journey(p, user) for p in tous]
            summary = {k: sum(p['counters'][k] for p in data) for k in COUNTERS}
            return {'journeys': data, 'summary': summary}
        return self._run('GET', action)

    @http.route('/api/recette/journeys/<string:code>', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def acceptance_journey(self, code, **kw):
        """La recette d'un parcours : toutes ses étapes dans l'ordre de lecture,
        chacune avec ses cas. Une étape sans cas est renvoyée quand même : le site
        s'en sert pour la liste des étapes à la modification d'un cas.

        Filtres cumulables : assigned_to_me=1 (en attente d'une action de ce
        profil), status=failed,regression (codes de résultat séparés par des
        virgules), include_archived=1 pour inclure les cas archivés."""
        def action(user, body):
            parcours = self._get_journey(code)
            args = request.httprequest.args
            domain = [('parcours_id', '=', parcours.id)]
            if args.get('assigned_to_me') == '1':
                domain.append(('balle', 'in', request.env['nkezefuu.recette.cas']._balles_du_profil(user._recette_roles())))
            if args.get('status'):
                domain.append(('resultat', 'in', [r.strip() for r in args['status'].split(',') if r.strip()]))
            Cas = request.env['nkezefuu.recette.cas'].sudo()
            if args.get('include_archived') == '1':
                Cas = Cas.with_context(active_test=False)
            cases = Cas.search(domain)

            numeros = self._numeros(parcours)
            steps = [self._serialize_step(etape, cases, user, numeros) for etape, _numero in parcours._etapes_dans_l_ordre()]
            return {'journey': self._serialize_journey(parcours, user), 'steps': steps}
        return self._run('GET', action)

    @http.route('/api/recette/steps/<int:step_id>/not-implemented', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def step_not_implemented(self, step_id, **kw):
        """Signale qu'une étape entière manque dans l'application : ses cas non
        testés passent en « Non implémenté ». Corps : observed_result, app_version.
        Renvoie l'étape avec tous ses cas, et les indicateurs du parcours."""
        def action(user, body):
            etape = request.env['nkezefuu.doc.etape'].sudo().browse(step_id).exists()
            if not etape:
                raise MissingError('Étape introuvable')
            Cas = request.env['nkezefuu.recette.cas']
            Cas.signaler_etape_non_implementee(user, etape, body.get('observed_result'), body.get('app_version'))
            Cas.invalidate_model()
            cases = Cas.sudo().search([('etape_id', '=', etape.id)])
            parcours = etape.parcours_id
            return {'journey': self._serialize_journey(parcours, user),
                    'step': self._serialize_step(etape, cases, user, self._numeros(parcours))}
        return self._run('POST', action, ecriture=True)

    # ------------------------------------------------------------------
    # Cas
    # ------------------------------------------------------------------
    @http.route('/api/recette/cases/<int:cas_id>', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def case(self, cas_id, **kw):
        def action(user, body):
            return self._cas_complet(self._get_cas(cas_id), user)
        return self._run('GET', action)

    @http.route('/api/recette/cases/<int:cas_id>/update', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def case_update(self, cas_id, **kw):
        def action(user, body):
            vals = {CHAMPS_MODIFIABLES[k]: v for k, v in body.items() if k in CHAMPS_MODIFIABLES}
            cas = self._get_cas(cas_id).modifier(user, vals)
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cases/<int:cas_id>/archive', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def case_archive(self, cas_id, **kw):
        def action(user, body):
            return self._cas_complet(self._get_cas(cas_id).archiver(user), user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cases/<int:cas_id>/restore', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def case_restore(self, cas_id, **kw):
        def action(user, body):
            return self._cas_complet(self._get_cas(cas_id).restaurer(user), user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cases/<int:cas_id>/result', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def case_result(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).poser_resultat(
                user, body.get('result'), body.get('observed_result'), body.get('app_version'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cases/<int:cas_id>/reply', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def case_reply(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).poser_suite(user, body.get('fix_status'), body.get('reply'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cases/<int:cas_id>/comment', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def case_comment(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).commenter(user, body.get('text'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)
