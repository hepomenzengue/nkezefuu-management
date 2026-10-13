# -*- coding: utf-8 -*-

import json
import logging

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)


class SocleApi:
    """Socle commun aux API du site apps-docs.nkezefuu.com (documentation et
    recette) : en-têtes, réponses, authentification par jeton, traduction des
    exceptions.

    Mêmes conventions que l'API mobile de la coopérative : jeton Bearer, réponse
    HTTP 200 avec le vrai résultat dans customstatus, et l'objet complet renvoyé
    après toute création ou modification.

    Toutes les routes sont sous /api/recette, et nommées en anglais : « recette »
    est le seul mot français des chemins et des champs. Les libellés et les
    messages destinés aux personnes restent en français.

    Simple classe de base, sans route : chaque contrôleur en hérite avec
    http.Controller.
    """

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
        profil ; (None, réponse d'erreur) sinon. Chaque page du site passe par là,
        documentation comprise."""
        acces = self._jeton_bearer()
        if not acces:
            return None, self._error(headers, 401, 'Authentification requise')
        user = request.env['nkezefuu.recette.jeton']._utilisateur_du_jeton(acces)
        if not user:
            return None, self._error(headers, 401, 'Token invalide ou expiré')
        request.update_env(user=user.id)
        user = request.env['res.users'].sudo().browse(user.id)
        if not user._recette_roles():
            return None, self._error(headers, 403, "Ce compte n'a pas accès au site.")
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
            _logger.exception("Erreur API apps-docs")
            return self._error(headers, 500, 'Une erreur est survenue: %s' % e)

    @staticmethod
    def _sel(code, selection):
        return {'code': code, 'label': dict(selection).get(code, code)} if code else None

    def _get_journey(self, code):
        parcours = request.env['nkezefuu.doc.parcours'].sudo().search([('code', '=', code)], limit=1)
        if not parcours:
            raise MissingError('Parcours introuvable')
        return parcours
