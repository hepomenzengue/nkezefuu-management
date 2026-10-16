# nkezefuu-management

Modules de la plateforme de suivi des produits de la coopérative NKEZEFUU
(`management.nkezefuu.com`), sur une instance Odoo 19 dédiée, indépendante de la
production de la coopérative.

| Module | Rôle |
|---|---|
| `nkezefuu_recette` | documentation et recette fonctionnelle de l'application mobile |

## nkezefuu_recette

Module Odoo 19 qui porte tout ce qu'affiche le site `apps-docs.nkezefuu.com` :

- la **documentation** : les services de l'API mobile, les parcours et leurs étapes,
  les cas de test API ;
- la **recette**, par version de l'application : des cas rattachés aux étapes des
  parcours, testés dans l'application mobile, avec leurs résultats et l'historique
  des échanges entre le testeur et le développeur mobile.

Tout est lu et manipulé uniquement par API ; le site demande une connexion pour
chacune de ses pages. Le module n'a volontairement ni vue ni menu. Il ne dépend que
de `base`, et gère lui-même ses jetons de connexion.

## Profils

| Profil | Ce qu'il peut faire |
|---|---|
| Testeur | lire tout le site, enregistrer un résultat, commenter, signaler une régression |
| Administrateur de recette | tout ce que fait le testeur, plus reformuler un cas, le changer d'étape, l'archiver, le restaurer, le reporter, le remettre à « Non testé », publier la version |
| Développeur mobile | lire tout le site, répondre au testeur, commenter (un compte portail suffit) |

Chaque profil est attribué explicitement, administrateurs compris : le statut
d'administrateur système ne donne par lui-même aucun accès au site. Les testeurs et
développeurs sont créés en type **Portail**, pour qu'ils n'aient pas accès au
back-office Odoo.

Les profils vivent dans deux privilèges distincts, « Profil de recette » (Testeur
puis Administrateur de recette, qui s'excluent) et « Développement mobile ». Un même
compte peut donc être à la fois Administrateur de recette et Développeur mobile, ce
qui est utile pendant la mise au point.

## Documentation

`data/documentation/` contient `services.json` (catégories et services) et un fichier
par parcours dans `parcours/` (étapes en arbre, cas de test API, préfixe des cas de
recette). Ces fichiers font foi : ils sont relus à **chaque mise à jour** du module
(`data/documentation.xml`), ce qui y est corrigé est corrigé en base, ce qui en est
retiré est supprimé. Chaque élément est retrouvé par son identifiant fixe : `code`
pour un service, un parcours ou un cas de test API, `cle` pour une étape. Le numéro
d'une étape (2.1.2) n'est jamais stocké, il suit sa place dans l'arbre.

Dans le texte d'une étape, `{{cle}}` renvoie à l'étape de même clé du parcours.

Une étape qui porte encore des cas de recette ne peut pas être retirée : la mise à
jour s'arrête et nomme l'étape, plutôt que de perdre des résultats.

Pour un nouveau processus : l'API, puis son parcours et ses étapes dans ces fichiers,
puis ses cas de recette.

## Versions

La recette est organisée par version de l'application. Une version ne contient que
ses nouveautés : les cas écrits pour les fonctionnalités, mises à jour et correctifs
qu'elle apporte. Les parcours et les services, eux, ne sont pas versionnés.

Une seule version est en recette à la fois. Elle est déclarée dans
`data/recette_versions.xml`, rejoué à chaque mise à jour. Le numéro doit suivre la
dernière version publiée, et son type s'en déduit :

| Type | Quand | Après 0.0.1 |
|---|---|---|
| Correctif | correction ou petite mise à jour | 0.0.2 |
| Évolution | nouvelle fonctionnalité ou nouveau parcours | 0.1.0 |
| Majeure | refonte importante | 1.0.0 |

Toutes les actions de recette se font sur le site, aucune dans Odoo :

- **Publier** (administrateur de recette) : refusé tant qu'un cas actif n'est ni
  conforme ni reporté. La version et ses cas sont ensuite figés, consultables en
  lecture seule.
- **Reporter** un cas (administrateur de recette, motif obligatoire) : la version
  peut sortir sans lui. À l'ouverture de la version suivante, il y est repris
  automatiquement, en « Non testé », lié à son cas d'origine.
- **Signaler une régression** (testeur), depuis un cas conforme d'une version
  publiée : un nouveau cas est créé dans la version en recette, en « Régression »,
  lié au cas d'origine qui, lui, ne change pas. S'il n'y a pas de version en
  recette, un Correctif est ouvert automatiquement. Si on déclare ensuite une
  Évolution dans `recette_versions.xml`, ce Correctif prend son numéro et garde ses
  cas.

## Cas de recette

`data/recette_donnees.xml`, en `noupdate="1"` : 137 cas répartis sur 5 parcours
(références RMP, RLP, RMCB, RCB, RAP), qui forment la version 0.0.1.

Le parcours « Autres parcours » (RAP) regroupe les fonctions de l'application qui
n'ont pas encore leur propre parcours, une étape par fonction (tableau de bord,
historique, à payer, marché…). Ses étapes n'ont des cas que lorsqu'il le faut, par
exemple une régression sur une fonction jamais testée dans la recette : le cas est
alors écrit dans ce fichier, directement en « Régression ». Quand une fonction
reçoit son parcours, son étape et ses cas y sont déplacés. Chacun trouve son
étape par le code du parcours et la clé de l'étape. Ils sont créés une fois et jamais
réécrits ensuite : ce que l'administrateur de recette reformule depuis le site
survit aux mises à jour. Un cas ajouté plus tard dans ce fichier est créé à la mise
à jour suivante, dans la version en recette (la mise à jour s'arrête s'il n'y en a
pas). Il s'écrit sans numéro : il prend le suivant du parcours, après ceux que le
serveur a créés entre-temps (régressions, reprises de reports). Le site ne crée pas
de cas.

On archive un cas devenu inutile, on ne le supprime pas.

## Routes

Toutes sous `/api/recette`, nommées en anglais : « recette » est le seul mot français
des chemins et des champs. Les libellés et les messages destinés aux personnes
restent en français. Jeton Bearer, réponse HTTP 200 avec le vrai résultat dans
`customstatus`. Toute modification renvoie l'objet complet.

| Route | Rôle |
|---|---|
| `POST /auth/login` | identifiant et mot de passe contre une paire de jetons |
| `POST /auth/refresh` | nouvelle paire contre le jeton de renouvellement |
| `POST /auth/logout` | révoque la paire du jeton d'accès |
| `GET /account/profile` | l'utilisateur connecté (nom, identifiant) et ses profils |
| `POST /account/password` | changer son mot de passe ; révoque les autres connexions et renvoie une nouvelle paire |
| `GET /docs/services` | les services, rangés par catégorie |
| `GET /docs/journeys` | la liste des parcours |
| `GET /docs/journeys/{code}` | un parcours : arbre des étapes numérotées, cas de test API |
| `GET /versions` | les versions, de la plus récente à la plus ancienne, et celle affichée par défaut |
| `POST /versions/{id}/publish` | publier la version en recette (administrateur de recette) |
| `GET /journeys` | tableau de bord d'une version : indicateurs par parcours et synthèse ; `version={id}`, sinon celle en recette, sinon la dernière publiée |
| `GET /journeys/{code}` | la recette d'un parcours dans une version, étapes et cas ; filtres `version={id}`, `awaiting=tester` ou `developer`, `status=failed,regression`, `include_archived=1` |
| `POST /steps/{id}/not-implemented` | le testeur signale une étape absente de l'application : ses cas non testés de la version en recette passent en « Non implémenté » ; `observed_result` |
| `GET /cases/{id}` | un cas avec son historique |
| `POST /cases/{id}/update` | reformuler (`screen`, `user_profile`, `action`, `expected_result`) ou changer d'étape (`step_id`) (administrateur de recette) |
| `POST /cases/{id}/archive`, `/restore` | archiver, restaurer (administrateur de recette) |
| `POST /cases/{id}/result` | le testeur enregistre un résultat, ou l'administrateur de recette reporte le cas : `result`, `observed_result` (le motif pour un report) |
| `POST /cases/{id}/amend` | le testeur modifie son dernier résultat, tant que le développeur n'a pas répondu, sans changer le statut : `observed_result` (texte complet), `captures` |
| `POST /cases/{id}/regression` | le testeur signale la régression d'un cas conforme d'une version publiée : `observed_result` ; renvoie le nouveau cas |
| `POST /cases/{id}/reply` | le développeur répond : `fix_status`, `reply` |
| `POST /cases/{id}/comment` | message libre : `text`, ou seulement des `captures` |
| `GET /captures/{id}` | l'image d'une capture jointe à un message (pas du JSON) |

Les corps de `result`, `amend`, `regression`, `reply` et `comment` acceptent aussi `captures` :
liste de `{name, data}`, `data` en base64 (une URL `data:` est acceptée). Cinq au plus
par message, 3 Mo au plus chacune, en PNG, JPEG ou WebP (type lu dans le contenu). Le
site les réduit avant l'envoi. Elles sont stockées en pièces jointes de l'échange, ne se
modifient pas et ne se suppriment pas. L'historique d'un cas liste les `captures` de
chaque échange (`id`, `name`, `mimetype`), et chaque cas porte son `capture_count`.

Codes des résultats : `not_tested`, `passed`, `passed_with_reserve`, `failed`, `blocked`,
`not_implemented`, `passed_after_fix`, `still_failing`, `regression` (posé seulement par
le signalement d'une régression), `postponed` (Reporté). « Conforme avec réserve » (ce
qui était demandé est bon, mais un point reste à corriger, par exemple sur un ajout du
développeur) exige la réserve dans `observed_result`, renvoie le cas au développeur et
empêche la publication tant qu'elle n'est pas levée. « Non implémenté » (la fonction
n'existe pas dans l'application) se distingue de « Non conforme » (elle existe mais se
comporte mal) et de « Bloqué » (le test est empêché par autre chose) : il attend une
action du développeur, qui peut aussi demander des précisions en cas
d'incompréhension. Statuts de correction : `in_progress`,
`fixed_to_retest`, `works_as_intended`, `needs_clarification`. Action attendue de
(`awaiting`) : `tester`, `developer`, `closed`. Profils (`roles`) : `tester`,
`acceptance_admin`, `mobile_developer`. Versions : type `patch`, `minor`, `major` ;
état `in_progress`, `published`. Lien d'un cas avec son cas d'origine (`origin`) ou
ses reprises (`followups`) : `regression`, `postponed`. Chaque code est renvoyé avec son libellé
français (`{code, label}`), et chaque cas avec ses `permissions` pour le profil
connecté.

Une connexion produit un jeton d'accès valable 8 heures (`token`) et un jeton de
renouvellement valable 30 jours (`refresh_token`). Quand une route répond 401, appeler
`/auth/refresh` avec le jeton de renouvellement : il est consommé et remplacé par une
nouvelle paire, et ne peut pas être rejoué. Seules les empreintes des jetons sont
stockées en base. Un compte archivé perd ses accès immédiatement.

`/account/password` attend `current_password` et `new_password` (8 caractères
au moins, différent de l'actuel). Il passe par la même protection contre les essais en
rafale que la connexion (`customstatus` 429 pendant le délai d'attente). Un mot de
passe actuel faux renvoie 400, et non 401, pour que le site ne le prenne pas pour une
session expirée. En cas de succès, toutes les paires du compte sont révoquées et la
réponse est la session complète, comme `/auth/login` : le site remplace ses jetons.

## Déploiement

L'instance suit l'organisation des autres Odoo du serveur : un répertoire par
instance, avec ses propres sources, son venv, sa conf, sa base et son service.

| Élément | Valeur |
|---|---|
| Domaine | `management.nkezefuu.com` |
| Répertoire | `/opt/nkezefuu/management/` |
| Sources Odoo 19 | `/opt/nkezefuu/management/odoo/` |
| Venv | `/opt/nkezefuu/management/venv/` |
| Clone de ce dépôt | `/opt/nkezefuu/management/nkezefuu-management/` |
| Conf | `/etc/nkezefuu-management.conf` |
| Base | `management` |
| Port | 8075 |
| Service systemd | `nkezefuu-management` |

Un seul environnement : chaque push sur `master` est contrôlé (compilation du Python,
validité des XML, du CSV des droits et des JSON de la documentation, présence des
fichiers du manifeste), puis
déployé dans le clone ci-dessus, et le service est redémarré. Si le contrôle échoue,
rien n'est déployé.

Secrets requis, les mêmes que pour `nkezefuu-addons` : `VPS_HOST`, `VPS_USER`,
`VPS_SSH_PRIVATE_KEY`.

Le pipeline ne met pas le module à jour. Après un changement de modèle, de droits ou
de données, **documentation comprise** (un service ou une étape corrigés dans les
JSON n'apparaissent sur le site qu'après cette commande) :

```bash
sudo systemctl stop nkezefuu-management
sudo -u odoo /opt/nkezefuu/management/venv/bin/python3 \
    /opt/nkezefuu/management/odoo/odoo-bin \
    -c /etc/nkezefuu-management.conf -d management \
    -u nkezefuu_recette --stop-after-init
sudo systemctl start nkezefuu-management
```
