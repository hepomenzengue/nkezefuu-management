# -*- coding: utf-8 -*-

from odoo import fields, models


class DocParcours(models.Model):
    """Un parcours de l'application mobile (Mes prêts, Comptes bancaires…), décrit
    comme un arbre d'étapes. Chaque parcours a sa recette."""
    _name = 'nkezefuu.doc.parcours'
    _description = 'Parcours'
    _order = 'sequence, id'

    # Utilisé dans les adresses du site et de l'API : /parcours/mes-prets/
    code = fields.Char(string='Code', required=True)
    name = fields.Char(string='Nom', required=True)
    # Regroupe les parcours proches dans la navigation (Prêts, Comptes bancaires)
    groupe = fields.Char(string='Groupe', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    ligne_utilisateur = fields.Text(string='Utilisateur concerné')
    # Préfixe des références des cas de recette : RMP-012
    prefixe_recette = fields.Char(string='Préfixe des cas de recette', required=True)
    etape_ids = fields.One2many('nkezefuu.doc.etape', 'parcours_id', string='Étapes')
    test_ids = fields.One2many('nkezefuu.doc.test', 'parcours_id', string='Cas de test API')

    _code_unique = models.Constraint('unique(code)', 'Ce code de parcours est déjà utilisé.')
    _prefixe_unique = models.Constraint('unique(prefixe_recette)',
                                        'Ce préfixe est déjà utilisé par un autre parcours.')

    def _etapes_dans_l_ordre(self):
        """Les étapes du parcours à plat, dans l'ordre de lecture (1, 2, 2.1, 2.1.1,
        2.2…), chacune avec son numéro calculé. Le numéro n'est jamais stocké : il
        suit la place de l'étape dans l'arbre."""
        self.ensure_one()
        resultat = []

        def parcourir(etapes, prefixe):
            for rang, etape in enumerate(etapes.sorted(lambda e: (e.sequence, e.id)), 1):
                numero = '%s%d' % (prefixe, rang)
                resultat.append((etape, numero))
                parcourir(etape.enfant_ids, numero + '.')

        parcourir(self.etape_ids.filtered(lambda e: not e.parent_id), '')
        return resultat


class DocEtape(models.Model):
    """Une étape d'un parcours : sa phrase de récit, et les blocs qui l'accompagnent
    (écran, règles, maquette), gardés en JSON pour l'affichage."""
    _name = 'nkezefuu.doc.etape'
    _description = 'Étape de parcours'
    _order = 'parcours_id, sequence, id'

    parcours_id = fields.Many2one('nkezefuu.doc.parcours', string='Parcours', required=True,
                                  ondelete='cascade', index=True)
    parent_id = fields.Many2one('nkezefuu.doc.etape', string='Étape parente',
                                ondelete='cascade', index=True)
    enfant_ids = fields.One2many('nkezefuu.doc.etape', 'parent_id', string='Sous-étapes')
    # Identifiant fixe dans le parcours, jamais renuméroté : les cas de recette s'y
    # rattachent, et le texte d'une autre étape y renvoie en écrivant {{cle}}.
    cle = fields.Char(string='Clé', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    titre = fields.Char(string='Titre', required=True)
    texte = fields.Text(string='Texte', required=True)
    blocs = fields.Json(string='Blocs')
    cas_ids = fields.One2many('nkezefuu.recette.cas', 'etape_id', string='Cas de recette')

    _cle_unique = models.Constraint('unique(parcours_id, cle)',
                                    'Cette clé est déjà utilisée par une autre étape du parcours.')


class DocTest(models.Model):
    """Un cas de test de l'API, affiché en bas de la page du parcours. À ne pas
    confondre avec un cas de recette, qui se teste dans l'application mobile."""
    _name = 'nkezefuu.doc.test'
    _description = 'Cas de test API'
    _order = 'parcours_id, sequence, id'

    parcours_id = fields.Many2one('nkezefuu.doc.parcours', string='Parcours', required=True,
                                  ondelete='cascade', index=True)
    groupe = fields.Char(string='Groupe', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    code = fields.Char(string='Code', required=True)
    contrainte = fields.Char(string='Contrainte')
    titre = fields.Char(string='Titre', required=True)
    etant_donne = fields.Text(string='Étant donné')
    quand = fields.Text(string='Quand')
    alors = fields.Text(string='Alors')
    # { customstatus, message } attendus dans la réponse
    attendu = fields.Json(string='Réponse attendue')

    _code_unique = models.Constraint('unique(code)', 'Ce code de cas de test est déjà utilisé.')
