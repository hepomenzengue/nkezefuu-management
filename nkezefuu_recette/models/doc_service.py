# -*- coding: utf-8 -*-

from odoo import fields, models

# Qui peut appeler le service, côté application mobile. Les explications détaillées
# de chaque niveau restent affichées par le site.
ACCES = [
    ('public', 'Public'),
    ('member', 'Membre'),
    ('manager', 'Gestionnaire'),
    ('all', 'Selon le rôle'),
    ('admin', 'Administrateur seul'),
    ('bank_account_manager', 'Gestionnaire des comptes bancaires'),
]


class DocCategorie(models.Model):
    """Une rubrique de la page Services : Authentification, Prêts, Comptes bancaires…"""
    _name = 'nkezefuu.doc.categorie'
    _description = 'Catégorie de services'
    _order = 'sequence, id'

    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Nom', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Séquence', default=10)
    service_ids = fields.One2many('nkezefuu.doc.service', 'categorie_id', string='Services')

    _code_unique = models.Constraint('unique(code)', 'Ce code de catégorie est déjà utilisé.')


class DocService(models.Model):
    """Un service de l'API mobile, tel que décrit sur la page Services.

    Les listes de détail (paramètres, champs de réponse, erreurs, exemples, règles)
    sont gardées telles quelles en JSON : elles ne servent qu'à l'affichage, jamais
    à une recherche ou à un filtre.
    """
    _name = 'nkezefuu.doc.service'
    _description = "Service de l'API mobile"
    _order = 'sequence, id'

    # Identifiant fixe, cité par les blocs écran des étapes de parcours
    code = fields.Char(string='Code', required=True)
    categorie_id = fields.Many2one('nkezefuu.doc.categorie', string='Catégorie', required=True,
                                   ondelete='cascade', index=True)
    sequence = fields.Integer(string='Séquence', default=10)
    methode = fields.Selection([('GET', 'GET'), ('POST', 'POST')], string='Méthode', required=True)
    chemin = fields.Char(string='Chemin', required=True)
    resume = fields.Char(string='Résumé', required=True)
    acces = fields.Selection(ACCES, string='Accès', required=True)
    # « jsonrpc » : route Odoo type='json', réponse enveloppée dans { jsonrpc, id, result }
    enveloppe = fields.Char(string='Enveloppe')
    usage = fields.Text(string="Quand l'appeler")
    notes = fields.Json(string='Règles métier')
    parametres = fields.Json(string='Paramètres')
    exemple_requete = fields.Text(string='Exemple de requête')
    exemples_succes = fields.Json(string='Exemples de réponse')
    champs_reponse = fields.Json(string='Champs de la réponse')
    erreurs = fields.Json(string='Erreurs')

    _code_unique = models.Constraint('unique(code)', 'Ce code de service est déjà utilisé.')
