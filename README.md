# nkezefuu_recette

Module Odoo 17 de recette fonctionnelle de l'application mobile NKEZEFUU.

Les cas de test, leurs résultats et la discussion entre le testeur et le développeur
mobile sont enregistrés dans Odoo, et manipulés uniquement par API depuis le site de
documentation des services (entrée « Recette »). Le module n'a volontairement ni vue
ni menu.

Il dépend du module `nkezefuu`, dont il réutilise les jetons (`jwt.token`).

## Profils

| Profil | Ce qu'il peut faire |
|---|---|
| Testeur | poser un résultat, commenter, ajouter un cas |
| Admin testeur | tout ce que fait le testeur, plus modifier le texte d'un cas, archiver, gérer sections et tableaux |
| Développeur mobile | poser une suite, commenter, ajouter un cas (un compte portail suffit) |

Un administrateur système est automatiquement Admin testeur.

## Données initiales

`data/recette_donnees.xml`, en `noupdate="1"` : 2 tableaux (Mes prêts, Comptes
bancaires), 12 sections, 125 cas. Ils sont créés à l'installation et jamais réécrits
ensuite : ce qui est corrigé depuis le site survit aux mises à jour, et un cas ajouté
plus tard dans ce fichier est créé à la mise à jour suivante sans toucher aux autres.

On archive un cas devenu inutile, on ne le supprime pas.

## Routes

Toutes sous `/api/recette`, jeton Bearer, réponse HTTP 200 avec le vrai résultat dans
`customstatus`. Toute création ou modification renvoie l'objet complet.

| Route | Rôle |
|---|---|
| `POST /login` | connexion, sans fiche membre requise |
| `GET /moi` | l'utilisateur connecté et ses profils |
| `GET /tableaux` | les tableaux et leurs compteurs |
| `POST /tableaux` | créer un tableau (admin testeur) |
| `GET /tableaux/{code}` | le tableau complet ; filtres `balle=moi`, `resultat=ko,regression`, `archives=1` |
| `POST /sections`, `POST /sections/{id}/update` | gérer les sections (admin testeur) |
| `POST /cas` | ajouter un cas |
| `GET /cas/{id}` | une ligne avec sa discussion |
| `POST /cas/{id}/update` | corriger le texte (admin testeur) |
| `POST /cas/{id}/archive`, `/unarchive` | archiver, restaurer (admin testeur) |
| `POST /cas/{id}/resultat` | le testeur pose un résultat |
| `POST /cas/{id}/reponse` | le développeur pose une suite |
| `POST /cas/{id}/commentaire` | message libre |

Le jeton dure 15 minutes et se renouvelle par la route existante `POST /api/auth/refresh`,
qui refuse tant qu'il n'a pas expiré : le renouveler en réponse à un 401.

## Déploiement

Chaque push sur `master` est contrôlé (compilation du Python, validité des XML et du
CSV des droits), puis déployé en production et le service `nkezefuu_production` est
redémarré. Si le contrôle échoue, rien n'est déployé.

Le pipeline ne met pas le module à jour. Après un changement de modèle, de droits ou
de données :

```bash
odoo-bin -c /etc/nkezefuu_production.conf -d <base> -u nkezefuu_recette --stop-after-init
```
