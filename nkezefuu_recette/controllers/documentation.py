# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from ..models.doc_service import ACCES
from .socle import SocleApi


class DocumentationController(SocleApi, http.Controller):
    """Lecture de la documentation affichée par le site : la page Services et les
    pages Parcours. Réservée, comme le reste du site, aux comptes qui ont un
    profil. Rien ne s'écrit par ici : la documentation vient des fichiers du
    module."""

    def _serialize_service(self, service):
        return {
            'code': service.code,
            'category': service.categorie_id.code,
            'method': service.methode,
            'path': service.chemin,
            'summary': service.resume,
            'access': self._sel(service.acces, ACCES),
            'envelope': service.enveloppe or None,
            'usage': service.usage or '',
            'notes': service.notes or [],
            'params': service.parametres or [],
            'request_example': service.exemple_requete or '',
            'success_examples': service.exemples_succes or [],
            'response_fields': service.champs_reponse or [],
            'errors': service.erreurs or [],
        }

    def _serialize_journey(self, parcours):
        return {
            'code': parcours.code,
            'name': parcours.name,
            'group': parcours.groupe,
            'audience': parcours.ligne_utilisateur or '',
            'step_count': len(parcours.etape_ids),
        }

    @http.route('/api/recette/docs/services', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def services(self, **kw):
        """Tous les services, rangés par catégorie, dans l'ordre des fichiers."""
        def action(user, body):
            categories = request.env['nkezefuu.doc.categorie'].sudo().search([])
            return {'categories': [{
                'code': categorie.code,
                'name': categorie.name,
                'description': categorie.description or '',
                'services': [self._serialize_service(s) for s in categorie.service_ids],
            } for categorie in categories]}
        return self._run('GET', action)

    @http.route('/api/recette/docs/journeys', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def journeys(self, **kw):
        """Les parcours, pour la navigation du site."""
        def action(user, body):
            tous = request.env['nkezefuu.doc.parcours'].sudo().search([])
            return {'journeys': [self._serialize_journey(p) for p in tous]}
        return self._run('GET', action)

    @http.route('/api/recette/docs/journeys/<string:code>', type='http', methods=['GET', 'OPTIONS'], auth="none", csrf=False)
    def journey(self, code, **kw):
        """Un parcours complet : l'arbre des étapes, numérotées, et ses cas de test
        API groupés. Dans le texte d'une étape, {{key}} renvoie à l'étape de même
        clé du parcours."""
        def action(user, body):
            parcours = self._get_journey(code)
            numeros = {etape.id: numero for etape, numero in parcours._etapes_dans_l_ordre()}

            def arbre(etapes):
                return [{
                    'key': etape.cle,
                    'number': numeros[etape.id],
                    'title': etape.titre,
                    'text': etape.texte,
                    'blocks': etape.blocs or [],
                    'steps': arbre(etape.enfant_ids),
                } for etape in etapes.sorted(lambda e: (e.sequence, e.id))]

            groupes = []
            for test in parcours.test_ids:
                if not groupes or groupes[-1]['title'] != test.groupe:
                    groupes.append({'title': test.groupe, 'cases': []})
                groupes[-1]['cases'].append({
                    'code': test.code,
                    'constraint': test.contrainte or None,
                    'title': test.titre,
                    'given': test.etant_donne or '',
                    'when': test.quand or '',
                    'then': test.alors or '',
                    'expected': test.attendu or None,
                })
            return {'journey': dict(
                self._serialize_journey(parcours),
                steps=arbre(parcours.etape_ids.filtered(lambda e: not e.parent_id)),
                api_tests=groupes,
            )}
        return self._run('GET', action)
