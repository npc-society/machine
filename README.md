# La machine à clips · NPC Society

Repérage, tri depuis Discord, montage automatique et compilations. Elle tourne seule sur GitHub et ton ordinateur peut rester éteint.

## Comment ça marche

1. **Repérage, toutes les heures.** Les clips GTA 6 qui buzzent arrivent dans `#clips-fr` et `#clips-en`, un message par clip. Chaque message affiche la catégorie (😡 rage, 💥 fail, 🤯 incroyable, 🔍 découverte, 🏁 course, 😂 drôle) et la taille du streamer (🏆 gros ou 💎 pépite).
2. **Tu tries en appuyant sur une réaction** :
   - ✅ monter le clip en short pour la chaîne de sa langue ;
   - 🌍 en faire aussi une version sous-titrée pour l'autre chaîne (un clip FR sur la chaîne EN, ou l'inverse). Tu peux cumuler ✅ et 🌍 ;
   - ⭐ le garder pour la compilation de la semaine ;
   - ❌ le jeter.
3. **Montage automatique, dans les 30 minutes.** La vidéo verticale arrive dans `#montages-fr` ou `#montages-en`, avec son titre, sa description et ses hashtags prêts à copier. Le montage comprend :
   - la facecam en haut si elle est détectée, sinon un fond flouté ;
   - des sous-titres animés, une accroche et le crédit du streamer ;
   - le style « chaîne d'info satirique » : logo NPC Society, gros titre racoleur, et sous le clip, la barre « en direct » avec le crédit du streamer et un bandeau défilant qui commente l'action d'un ton moqueur ;
   - des zooms sur les moments forts, un tampon de presse (« DRAME », « INSOLITE »…), un bruitage et ton mème de réaction s'il y en a un.
4. **Tu valides la vidéo** :
   - ✅ elle est validée ;
   - 🔁 elle est refaite avec un autre mème ;
   - ❌ elle est jetée.

   Ensuite, tu la télécharges depuis Discord et tu la postes en ajoutant le son tendance dans TikTok ou Instagram.
5. **Le dimanche à 18 h**, la compilation « Top 10 de la semaine » est montée à partir de tes clips ⭐. Le lien arrive dans `#montages`.
6. **Chaque soir**, tu reçois le récap avec le top du jour et les pépites du jour.

## Titres
- **Sans clé IA :** la machine reprend le titre du clip Twitch s'il décrit l'action (« SQUEEZIE : IL CRASH LA VOITURE DE POLICE »). Sinon, elle utilise un titre descriptif selon la catégorie.
- **Avec la clé :** l'IA écrit un titre d'après ce qui se passe vraiment dans le clip, taquin mais jamais insultant ni trompeur.
- **Tampons de presse :** désactivés. Pour les réactiver, crée la variable `STAMPS` = `1`.

## Tri automatique
- **Clips trop courts ignorés** : moins de 15 s (variable `MIN_CLIP_SECONDS`).
- **Nudité** : chaque clip est analysé image par image (NudeNet, 2 images par seconde). Sur les passages concernés, le jeu est fortement flouté et, s'il y a une facecam, remplacé par un gros plan sur la réaction du streamer, avec l'étiquette « CENSURÉ PAR LES PNJ ». Si la nudité couvre plus de la moitié du clip (plus d'un tiers sans facecam), le clip est écarté.
- **Clips courts à fort buzz** : un clip de moins de 15 s n'est pas monté en short, mais s'il fait un gros buzz (vues ≥ 4 × `MIN_VIEWS`, ou 4 fois l'audience d'une pépite), il est proposé avec ⚡ et gardé pour les compils et les flashs.
- **L'IA regarde le clip** (4 images + la transcription) : elle écarte des montages automatiques, flashs et compils à thème les clips qui ne montrent pas vraiment le jeu (vidéo YouTube regardée en réaction, IRL…), ceux où elle voit de la nudité et ceux qui ne sont pas assez drôles. Sur tes ✅, elle n'écarte rien mais t'affiche un ⚠️.
- **Montages automatiques notés par l'IA** (avec `ANTHROPIC_API_KEY`) : seuls les clips jugés drôles ou intéressants (note ≥ `AUTO_MIN_SCORE`, 6/10 par défaut) et publiables sont envoyés. Tes ✅ manuels passent toujours.

## Formats automatiques
- **Montage automatique :** à chaque repérage, les 2 meilleurs clips par langue sont montés d'office, sans attendre ton ✅ (alternance gros streamer / pépite). Réglage : variable `AUTO_PER_RUN` (0 = désactivé).
- **Flash info, chaque jour à 18 h 20 :** 3 brèves de 15 secondes (variables `FLASH_SIZE`, `FLASH_SECONDS`), enchaînées façon zapping télé, une par streamer, avec le meilleur moment de chaque clip et un générique « Édition spéciale ». Réglage : `FLASH_SIZE`.
- **Compil à thème, à la demande :** plein de streamers dans la même situation (le club de strip, la première voiture volée…). Lance **Run workflow**, choisis l'action `theme`, puis remplis les mots-clés (`strip,club`), le titre (`ILS DÉCOUVRENT LE CLUB DE STRIP`) et la chaîne (`fr`, `en` ou `es`). Chaque soir, le récap te suggère les thèmes qui reviennent chez plusieurs streamers.
- **Compilation de la semaine, le dimanche :** à partir de tes clips ⭐.

## Installation (environ 30 minutes, une seule fois)

### 1. Twitch
1. Va sur https://dev.twitch.tv/console. La double authentification doit être activée sur ton compte Twitch.
2. Clique sur **Register Your Application**. Mets `http://localhost` comme OAuth Redirect URL et *Application Integration* comme catégorie.
3. Note le **Client ID** et le **Client Secret**.

### 2. Discord
1. Crée un serveur privé avec 4 salons : `#clips-fr`, `#clips-en`, `#montages-fr` et `#montages-en`.
2. Va sur https://discord.com/developers/applications et clique sur **New Application**.
3. Dans l'onglet **Bot**, clique sur **Reset Token** et note le **token**.
4. Dans **OAuth2 → URL Generator** :
   - coche `bot` ;
   - dans les permissions, coche *Send Messages*, *Embed Links*, *Attach Files*, *Add Reactions* et *Read Message History* ;
   - ouvre l'URL générée et ajoute le bot à ton serveur.
5. Dans Discord, va dans **Paramètres → Avancés** et active le **Mode développeur**. Fais ensuite un clic droit (ou un appui long) sur chaque salon et choisis **Copier l'identifiant**.

### 3. GitHub
1. Crée un dépôt **public** : les minutes de calcul y sont illimitées et gratuites. Tes clés restent cachées dans les secrets. En privé, le quota gratuit de 2 000 minutes par mois serait trop juste.
2. Envoie tous les fichiers de ce dossier dans le dépôt, y compris le dossier `.github`.
3. Va dans **Settings → Actions → General → Workflow permissions** et choisis **Read and write**.
4. Va dans **Settings → Secrets and variables → Actions** et ajoute ces secrets :

| Secret | Valeur |
| --- | --- |
| `TWITCH_CLIENT_ID` | Client ID Twitch |
| `TWITCH_CLIENT_SECRET` | Client Secret Twitch |
| `DISCORD_BOT_TOKEN` | token du bot |
| `DISCORD_CLIPS_FR` / `DISCORD_CLIPS_EN` | identifiants des salons de clips |
| `DISCORD_MONTAGES_FR` / `DISCORD_MONTAGES_EN` | identifiants des salons de montages |
| `ANTHROPIC_API_KEY` | *recommandé* : titres et commentaires écrits sur mesure d'après ce qui se passe dans le clip, et traduction des sous-titres pour les versions 🌍. Sans clé, des modèles de texte sont utilisés, et seule la traduction vers l'anglais fonctionne. |

5. Dans l'onglet **Actions**, ouvre **Machine à clips**, clique sur **Run workflow** et choisis `hunt`. Les premiers clips arrivent dans Discord.

## Personnaliser
- **Les tampons, bruitages et réactions** se gèrent dans `brand/memes.json`, par langue et par catégorie.
- **Les mèmes de réaction** sont tes références du moment, repérées sur TikTok et X. Dépose des vidéos courtes (1 à 2 s, .mp4) ou des images dans `assets/reactions/fr/` ou `assets/reactions/en/`, puis ajoute leur nom de fichier dans la liste `reactions` de la catégorie voulue. Ils apparaissent en incrustation, avec un cadre blanc, juste après le moment fort.
- **Le nom, le slogan, les sur-titres, les phrases du bandeau défilant, les couleurs et les hashtags** se modifient dans `brand/brand.json`.
- **Les gros titres par défaut** sont dans `texts.py`. Avec la clé `ANTHROPIC_API_KEY`, ils sont écrits sur mesure pour chaque clip.
- **Les bruitages** sont dans `assets/sfx/`. Les 4 fournis sont synthétisés, donc libres de droits. Tu peux ajouter tes propres fichiers libres de droits.
- **Les variables** se modifient dans **Settings → Variables** :
  - `PER_RUN_BIG` et `PER_RUN_SMALL` : le nombre de clips proposés par heure et par langue (3 et 2 par défaut) ;
  - `MIN_VIEWS` et `MIN_VIEWS_SMALL` : les seuils de vues ;
  - `LANGS` : les langues suivies ;
  - `GAME_NAMES` : les jeux suivis. Ajoute la catégorie GTA Online le jour où elle existe sur Twitch.

## À savoir
- **Une vidéo trop lourde pour Discord** (plus de 10 Mo) est automatiquement recompressée. Les compilations, elles, sont déposées dans les **Releases** du dépôt.
- **N'intègre pas de musique dans le montage.** Ajoute le son tendance au moment de publier, depuis l'appli.
- **Crédite toujours le streamer** (c'est automatique dans la description) et demande-lui l'autorisation. Le fichier `data/streamers.csv` contient les colonnes « contacte » et « accord » pour suivre tes demandes.

## Visuels de marque
- Le logo, le logo d'intro et la photo de profil sont dans `assets/brand/`.
- Pour les régénérer après avoir changé les couleurs dans `brand/brand.json`, lance `python make_brand.py`.
- Polices utilisées, toutes libres (licence OFL) : Barlow Condensed pour les titres et bandeaux, Archivo Black pour le logo et les tampons.
