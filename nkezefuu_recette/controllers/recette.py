# -*- coding: utf-8 -*-

import json
import logging

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from werkzeug.wrappers import Response

from ..models.recette_cas import BALLES, RESULTATS, SUITES
from ..models.recette_echange import TYPES_ECHANGE
from ..models.res_users import ADMIN

_logger = logging.getLogger(__name__)


class RecetteController(http.Controller):
    """API de la recette fonctionnelle, appelée par le site apps-docs.nkezefuu.com.

    Mêmes conventions que l'API mobile de la coopérative : jeton Bearer, réponse
    HTTP 200 avec le vrai résultat dans customstatus, et l'objet complet renvoyé
    après toute création ou modification.

    Les règles (qui peut poser quoi, la balle, les tours) sont dans les méthodes de
    nkezefuu.recette.cas : ce contrôleur authentifie, lit le corps, appelle, et
    sérialise. Chaque écriture tourne dans un savepoint, pour qu'un refus au milieu
    d'une opération n'en laisse rien en base.
    """

    # ------------------------------------------------------------------
    # Socle
    # ------------------------------------------------------------------
    def _headers(self, methods):
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': f'{methods}, OPTIONS',
            'Access-Control-Allow-Headers': 'Authorization, Content-Type',
            'Content-Type': 'application/json',
        }

    def _json_response(self, data, headers):
        return Response(response=json.dumps(data), status=200, headers=headers,
                        content_type='application/json')

    def _ok(self, headers, **data):
        return self._json_response(dict(data, status=200, customstatus=200), headers)

    def _error(self, headers, customstatus, message):
        return self._json_response({'error': message, 'status': 200, 'customstatus': customstatus}, headers)

    def _body(self):
        return json.loads(request.httprequest.data or b'{}')

    def _jeton_bearer(self):
        auth_header = request.httprequest.headers.get('Authorization') or ''
        return auth_header.split('Bearer ', 1)[1].strip() if auth_header.startswith('Bearer ') else None

    def _authenticate(self, headers):
        """(res.users, None) si le jeton d'accès est valide et que le compte a un
        profil de recette ; (None, réponse d'erreur) sinon."""
        acces = self._jeton_bearer()
        if not acces:
            return None, self._error(headers, 401, 'Authentification requise')
        user = request.env['nkezefuu.recette.jeton']._utilisateur_du_jeton(acces)
        if not user:
            return None, self._error(headers, 401, 'Token invalide ou expiré')
        request.update_env(user=user.id)
        user = request.env['res.users'].sudo().browse(user.id)
        if not user._recette_roles():
            return None, self._error(headers, 403, "Ce compte n'a pas accès à la recette.")
        return user, None

    def _run(self, methods, action, ecriture=False):
        """Enveloppe commune : OPTIONS, authentification, lecture du corps, et
        traduction des exceptions métier en customstatus."""
        headers = self._headers(methods)
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)
        user, error = self._authenticate(headers)
        if error:
            return error
        try:
            body = self._body() if request.httprequest.method == 'POST' else {}
        except ValueError:
            return self._error(headers, 400, 'Format JSON invalide')
        try:
            if ecriture:
                with request.env.cr.savepoint():
                    data = action(user, body)
            else:
                data = action(user, body)
            return self._ok(headers, **data)
        except AccessError as e:
            return self._error(headers, 403, str(e.args[0]) if e.args else str(e))
        except MissingError as e:
            return self._error(headers, 404, str(e.args[0]) if e.args else str(e))
        except (UserError, ValidationError) as e:
            return self._error(headers, 400, str(e.args[0]) if e.args else str(e))
        except Exception as e:
            _logger.exception("Erreur API recette")
            return self._error(headers, 500, 'Une erreur est survenue: %s' % e)

    # ------------------------------------------------------------------
    # Sérialisation
    # ------------------------------------------------------------------
    @staticmethod
    def _dt(value):
        # Odoo stocke en UTC : le Z final permet au navigateur de convertir en heure locale.
        return value.strftime('%Y-%m-%dT%H:%M:%SZ') if value else None

    @staticmethod
    def _sel(code, selection):
        return {'code': code, 'label': dict(selection).get(code, code)} if code else None

    @staticmethod
    def _user(user):
        return {'id': user.id, 'name': user.name} if user else None

    def _ids_initiaux(self, cases):
        """Cas livrés par les données du module (ils ont un identifiant XML), par
        opposition à ceux ajoutés depuis le site."""
        if not cases:
            return set()
        return set(request.env['ir.model.data'].sudo().search([
            ('model', '=', 'nkezefuu.recette.cas'), ('res_id', 'in', cases.ids),
        ]).mapped('res_id'))

    def _compteurs(self, cases, user):
        balles = cases._balles_du_profil(user._recette_roles())
        resultats = cases.mapped('resultat')
        return {
            'total': len(cases),
            'non_teste': resultats.count('non_teste'),
            'ok': resultats.count('ok') + resultats.count('ok_apres_correction'),
            'ko': resultats.count('ko') + resultats.count('toujours_ko'),
            'regression': resultats.count('regression'),
            'bloque': resultats.count('bloque'),
            'a_moi': len(cases.filtered(lambda c: c.balle in balles)),
        }

    def _serialize_tableau(self, tableau, user):
        cases = request.env['nkezefuu.recette.cas'].sudo().search([('tableau_id', '=', tableau.id)])
        return {
            'id': tableau.id,
            'code': tableau.code,
            'name': tableau.name,
            'prefixe': tableau.prefixe,
            'description': tableau.description or '',
            'compteurs': self._compteurs(cases, user),
        }

    def _serialize_section(self, section):
        return {'id': section.id, 'name': section.name, 'sequence': section.sequence,
                'tableau': {'code': section.tableau_id.code, 'name': section.tableau_id.name}}

    def _serialize_cas(self, cas, user, initiaux, avec_echanges=False):
        roles = user._recette_roles()
        dernier_ok = cas._dernier_resultat_ok()
        regression = cas._echange_regression()
        initial = cas.id in initiaux
        data = {
            'id': cas.id,
            'reference': cas.reference,
            'numero': cas.numero,
            'tableau': {'code': cas.tableau_id.code, 'name': cas.tableau_id.name},
            'section': {'id': cas.section_id.id, 'name': cas.section_id.name},
            'ecran': cas.ecran,
            'profil': cas.profil,
            'action': cas.action,
            'attendu': cas.attendu,
            'active': cas.active,
            'resultat': self._sel(cas.resultat, RESULTATS),
            'constat': cas.constat or '',
            'teste_par': self._user(cas.teste_par),
            'teste_le': self._dt(cas.teste_le),
            'version_apk': cas.version_apk or '',
            'suite': self._sel(cas.suite, SUITES),
            'reponse': cas.reponse or '',
            'repondu_par': self._user(cas.repondu_par),
            'repondu_le': self._dt(cas.repondu_le),
            'tour': cas.tour,
            'balle': self._sel(cas.balle, BALLES),
            'version_dernier_ok': dernier_ok.version_apk or None,
            'version_regression': regression.version_apk or None,
            'origine': 'initial' if initial else 'site',
            'ajoute_par': None if initial else self._user(cas.create_uid),
            'ajoute_le': self._dt(cas.create_date),
            'droits': cas._droits(roles),
        }
        if avec_echanges:
            data['echanges'] = [self._serialize_echange(e) for e in cas.echange_ids]
        return data

    def _serialize_echange(self, echange):
        selection = RESULTATS if echange.type == 'resultat' else SUITES if echange.type == 'suite' else []
        return {
            'id': echange.id,
            'tour': echange.tour,
            'type': self._sel(echange.type, TYPES_ECHANGE),
            'statut': self._sel(echange.statut, selection) if echange.statut else None,
            'texte': echange.texte or '',
            'version_apk': echange.version_apk or '',
            'auteur': self._user(echange.auteur_id),
            'date': self._dt(echange.create_date),
        }

    def _cas_complet(self, cas, user):
        cas.invalidate_recordset()
        return {'cas': self._serialize_cas(cas, user, self._ids_initiaux(cas), avec_echanges=True)}

    def _get_cas(self, cas_id):
        cas = request.env['nkezefuu.recette.cas'].sudo().with_context(active_test=False).browse(cas_id).exists()
        if not cas:
            raise MissingError('Cas introuvable')
        return cas

    def _get_tableau(self, code):
        tableau = request.env['nkezefuu.recette.tableau'].sudo().search([('code', '=', code)], limit=1)
        if not tableau:
            raise MissingError('Tableau introuvable')
        return tableau

    @staticmethod
    def _exiger_admin(user):
        if ADMIN not in user._recette_roles():
            raise AccessError("Réservé à l'admin testeur.")

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------
    def _session(self, user, paire):
        return dict(paire, user={'id': user.id, 'name': user.name, 'roles': sorted(user._recette_roles())})

    @http.route('/api/recette/login', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
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
            # Message volontairement identique que l'identifiant existe ou non : le
            # site est public, il ne doit pas permettre de deviner les comptes.
            return self._error(headers, 401, 'Identifiant ou mot de passe incorrect')

        user = request.env['res.users'].sudo().browse(auth_info['uid'])
        if not user._recette_roles():
            return self._error(headers, 403, "Ce compte n'a pas accès à la recette.")
        paire = request.env['nkezefuu.recette.jeton']._emettre(user)
        return self._ok(headers, **self._session(user, paire))

    @http.route('/api/recette/refresh', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
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
            return self._error(headers, 403, "Ce compte n'a pas accès à la recette.")
        return self._ok(headers, **self._session(user, paire))

    @http.route('/api/recette/logout', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def logout(self, **kw):
        headers = self._headers('POST')
        if request.httprequest.method == 'OPTIONS':
            return Response(status=200, headers=headers)
        request.env['nkezefuu.recette.jeton']._revoquer(self._jeton_bearer())
        return self._ok(headers)

    @http.route('/api/recette/moi', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def moi(self, **kw):
        def action(user, body):
            return {'user': {'id': user.id, 'name': user.name, 'roles': sorted(user._recette_roles())}}
        return self._run('GET', action)

    # ------------------------------------------------------------------
    # Tableaux et sections
    # ------------------------------------------------------------------
    @http.route('/api/recette/tableaux', type='http', methods=['GET', 'POST', 'OPTIONS'], auth="none", csrf=False)
    def tableaux(self, **kw):
        if request.httprequest.method == 'POST':
            def creer(user, body):
                self._exiger_admin(user)
                vals = {k: (body.get(k) or '').strip() for k in ('name', 'code', 'prefixe')}
                manquants = [k for k, v in vals.items() if not v]
                if manquants:
                    raise UserError('Champs obligatoires manquants : %s.' % ', '.join(manquants))
                Tableau = request.env['nkezefuu.recette.tableau'].sudo()
                if Tableau.search_count([('code', '=', vals['code'])]):
                    raise UserError('Ce code de tableau est déjà utilisé.')
                if Tableau.search_count([('prefixe', '=', vals['prefixe'].upper())]):
                    raise UserError('Ce préfixe est déjà utilisé par un autre tableau.')
                dernier = Tableau.search([], order='sequence desc', limit=1)
                tableau = Tableau.create(dict(vals, prefixe=vals['prefixe'].upper(),
                                              description=body.get('description') or False,
                                              sequence=(dernier.sequence or 0) + 10))
                return {'tableau': self._serialize_tableau(tableau, user)}
            return self._run('GET, POST', creer, ecriture=True)

        def lister(user, body):
            tableaux = request.env['nkezefuu.recette.tableau'].sudo().search([])
            data = [self._serialize_tableau(t, user) for t in tableaux]
            ensemble = {k: sum(t['compteurs'][k] for t in data)
                        for k in ('total', 'non_teste', 'ok', 'ko', 'regression', 'bloque', 'a_moi')}
            return {'tableaux': data, 'ensemble': ensemble}
        return self._run('GET, POST', lister)

    @http.route('/api/recette/tableaux/<string:code>', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def tableau(self, code, **kw):
        """Le tableau complet, sections et lignes dans l'ordre. Filtres cumulables :
        balle=moi, resultat=ko,regression (codes séparés par des virgules),
        archives=1 pour inclure les cas archivés."""
        def action(user, body):
            tableau = self._get_tableau(code)
            args = request.httprequest.args
            domain = [('tableau_id', '=', tableau.id)]
            if args.get('balle') == 'moi':
                domain.append(('balle', 'in', request.env['nkezefuu.recette.cas']._balles_du_profil(user._recette_roles())))
            if args.get('resultat'):
                domain.append(('resultat', 'in', [r.strip() for r in args['resultat'].split(',') if r.strip()]))
            Cas = request.env['nkezefuu.recette.cas'].sudo()
            if args.get('archives') == '1':
                Cas = Cas.with_context(active_test=False)
            cases = Cas.search(domain)
            initiaux = self._ids_initiaux(cases)
            filtre = any(args.get(k) for k in ('balle', 'resultat'))

            sections = []
            for section in tableau.section_ids.sorted(lambda s: (s.sequence, s.id)):
                lignes = cases.filtered(lambda c: c.section_id == section)
                if filtre and not lignes:
                    continue
                sections.append(dict(self._serialize_section(section),
                                     cas=[self._serialize_cas(c, user, initiaux) for c in lignes]))
            return {'tableau': self._serialize_tableau(tableau, user), 'sections': sections}
        return self._run('GET', action)

    @http.route('/api/recette/sections', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def section_create(self, **kw):
        def action(user, body):
            self._exiger_admin(user)
            tableau = self._get_tableau(body.get('tableau') or '')
            name = (body.get('name') or '').strip()
            if not name:
                raise UserError('Le titre de la section est obligatoire.')
            Section = request.env['nkezefuu.recette.section'].sudo()
            sequence = body.get('sequence')
            if sequence is None:
                derniere = Section.search([('tableau_id', '=', tableau.id)], order='sequence desc', limit=1)
                sequence = (derniere.sequence or 0) + 10
            section = Section.create({'tableau_id': tableau.id, 'name': name, 'sequence': int(sequence)})
            return {'section': self._serialize_section(section)}
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/sections/<int:section_id>/update', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def section_update(self, section_id, **kw):
        """Renommer ou déplacer une section (sequence)."""
        def action(user, body):
            self._exiger_admin(user)
            section = request.env['nkezefuu.recette.section'].sudo().browse(section_id).exists()
            if not section:
                raise MissingError('Section introuvable')
            vals = {}
            if 'name' in body:
                name = (body.get('name') or '').strip()
                if not name:
                    raise UserError('Le titre de la section est obligatoire.')
                vals['name'] = name
            if 'sequence' in body:
                vals['sequence'] = int(body['sequence'])
            if vals:
                section.write(vals)
            return {'section': self._serialize_section(section)}
        return self._run('POST', action, ecriture=True)

    # ------------------------------------------------------------------
    # Cas
    # ------------------------------------------------------------------
    @http.route('/api/recette/cas', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_create(self, **kw):
        def action(user, body):
            tableau = self._get_tableau(body.get('tableau') or '')
            section = request.env['nkezefuu.recette.section'].sudo().browse(int(body.get('section_id') or 0)).exists()
            if not section:
                raise MissingError('Section introuvable')
            cas = request.env['nkezefuu.recette.cas'].creer(
                user, tableau, section, body.get('ecran'), body.get('profil'),
                body.get('action'), body.get('attendu'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cas/<int:cas_id>', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def cas_detail(self, cas_id, **kw):
        def action(user, body):
            return self._cas_complet(self._get_cas(cas_id), user)
        return self._run('GET', action)

    @http.route('/api/recette/cas/<int:cas_id>/update', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_update(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).modifier(user, body)
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cas/<int:cas_id>/archive', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_archive(self, cas_id, **kw):
        def action(user, body):
            return self._cas_complet(self._get_cas(cas_id).archiver(user), user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cas/<int:cas_id>/unarchive', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_unarchive(self, cas_id, **kw):
        def action(user, body):
            return self._cas_complet(self._get_cas(cas_id).restaurer(user), user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cas/<int:cas_id>/resultat', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_resultat(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).poser_resultat(
                user, body.get('resultat'), body.get('constat'), body.get('version_apk'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cas/<int:cas_id>/reponse', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_reponse(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).poser_suite(user, body.get('suite'), body.get('reponse'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)

    @http.route('/api/recette/cas/<int:cas_id>/commentaire', type='http', methods=['POST', 'OPTIONS'], auth="none", csrf=False)
    def cas_commentaire(self, cas_id, **kw):
        def action(user, body):
            cas = self._get_cas(cas_id).commenter(user, body.get('texte'))
            return self._cas_complet(cas, user)
        return self._run('POST', action, ecriture=True)
