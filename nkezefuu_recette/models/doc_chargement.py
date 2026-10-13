# -*- coding: utf-8 -*-

import json
import os

from odoo import api, models
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path


class DocChargement(models.AbstractModel):
    """Charge la documentation (services, parcours, étapes, cas de test API) depuis
    les fichiers JSON du module, à chaque installation et mise à jour.

    Les fichiers font foi : ce qui y est corrigé est corrigé en base, ce qui en est
    retiré est supprimé. Chaque enregistrement est retrouvé par son identifiant fixe
    (code, ou clé d'étape), jamais par sa position.

    Les cas de recette ne sont pas concernés : ils vivent dans les données XML en
    noupdate, puisque l'administrateur de recette les reformule depuis le site.
    """
    _name = 'nkezefuu.doc.chargement'
    _description = 'Chargement de la documentation'

    @api.model
    def _charger_documentation(self):
        dossier = os.path.join(get_module_path('nkezefuu_recette'), 'data', 'documentation')
        self._charger_services(self._lire(os.path.join(dossier, 'services.json')))

        dossier_parcours = os.path.join(dossier, 'parcours')
        codes = [self._charger_parcours(self._lire(os.path.join(dossier_parcours, nom))).code
                 for nom in sorted(os.listdir(dossier_parcours)) if nom.endswith('.json')]
        retires = self.env['nkezefuu.doc.parcours'].sudo().search([('code', 'not in', codes)])
        self._retirer_etapes(retires.etape_ids)
        retires.unlink()

    @staticmethod
    def _lire(chemin):
        with open(chemin, encoding='utf-8') as fichier:
            return json.load(fichier)

    @staticmethod
    def _synchroniser(enregistrements, cle, lignes):
        """Aligne les enregistrements sur les lignes du fichier, par le champ `cle` :
        met à jour ceux qui existent, crée les autres. Renvoie les enregistrements
        absents du fichier, que l'appelant supprime."""
        existants = {enregistrement[cle]: enregistrement for enregistrement in enregistrements}
        for vals in lignes:
            enregistrement = existants.pop(vals[cle], None)
            if enregistrement:
                enregistrement.write(vals)
            else:
                enregistrements.create(vals)
        return enregistrements.browse([enregistrement.id for enregistrement in existants.values()])

    def _charger_services(self, data):
        Categorie = self.env['nkezefuu.doc.categorie'].sudo()
        categories_retirees = self._synchroniser(Categorie.search([]), 'code', [
            dict(categorie, sequence=rang * 10) for rang, categorie in enumerate(data['categories'], 1)
        ])
        par_code = {categorie.code: categorie.id for categorie in Categorie.search([])}

        lignes = []
        for rang, service in enumerate(data['services'], 1):
            vals = dict(service, sequence=rang * 10)
            code_categorie = vals.pop('categorie')
            if code_categorie not in par_code:
                raise UserError("Le service « %s » est rangé dans la catégorie « %s », qui n'existe pas."
                                % (vals['code'], code_categorie))
            vals['categorie_id'] = par_code[code_categorie]
            lignes.append(vals)
        Service = self.env['nkezefuu.doc.service'].sudo()
        self._synchroniser(Service.search([]), 'code', lignes).unlink()
        categories_retirees.unlink()

    def _charger_parcours(self, data):
        Parcours = self.env['nkezefuu.doc.parcours'].sudo()
        Etape = self.env['nkezefuu.doc.etape'].sudo()
        vals = {k: data[k] for k in ('code', 'name', 'groupe', 'sequence', 'ligne_utilisateur', 'prefixe_recette')}
        parcours = Parcours.search([('code', '=', data['code'])])
        if parcours:
            parcours.write(vals)
        else:
            parcours = Parcours.create(vals)

        existantes = {etape.cle: etape for etape in parcours.etape_ids}
        vues = set()

        def placer(lignes, parent):
            for rang, ligne in enumerate(lignes, 1):
                if ligne['cle'] in vues:
                    raise UserError("Parcours « %s » : la clé d'étape « %s » est utilisée deux fois."
                                    % (parcours.code, ligne['cle']))
                vues.add(ligne['cle'])
                vals = {
                    'parcours_id': parcours.id,
                    'parent_id': parent.id,
                    'cle': ligne['cle'],
                    'sequence': rang * 10,
                    'titre': ligne['titre'],
                    'texte': ligne['texte'],
                    'blocs': ligne.get('blocs') or [],
                }
                etape = existantes.get(ligne['cle'])
                if etape:
                    etape.write(vals)
                else:
                    etape = Etape.create(vals)
                placer(ligne.get('etapes') or [], etape)

        placer(data['etapes'], Etape)
        self._retirer_etapes(Etape.browse([etape.id for cle, etape in existantes.items() if cle not in vues]))

        lignes = []
        for groupe in data.get('tests') or []:
            for cas in groupe['cas']:
                lignes.append(dict(cas, groupe=groupe['groupe'], sequence=(len(lignes) + 1) * 10,
                                   parcours_id=parcours.id))
        # Recherche aussi par code : un cas de test déplacé d'un parcours à l'autre
        # est repris, et non recréé en doublon.
        Test = self.env['nkezefuu.doc.test'].sudo()
        tests = Test.search(['|', ('parcours_id', '=', parcours.id),
                             ('code', 'in', [ligne['code'] for ligne in lignes])])
        self._synchroniser(tests, 'code', lignes).unlink()
        return parcours

    def _retirer_etapes(self, etapes):
        """Une étape retirée du fichier est supprimée, sauf si des cas de recette y
        sont encore rattachés : la mise à jour s'arrête alors, plutôt que de perdre
        des résultats."""
        if not etapes:
            return
        utilisees = self.env['nkezefuu.recette.cas'].sudo().with_context(active_test=False).search(
            [('etape_id', 'in', etapes.ids)]).etape_id
        if utilisees:
            raise UserError(
                "Ces étapes ont été retirées des fichiers de parcours, mais des cas de recette y "
                "sont encore rattachés : %s. Rattachez d'abord ces cas à une autre étape."
                % ', '.join('%s / %s' % (etape.parcours_id.code, etape.cle) for etape in utilisees))
        etapes.unlink()
