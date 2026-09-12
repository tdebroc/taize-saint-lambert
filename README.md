# Prière esprit Taizé — Saint-Lambert de Vaugirard

Site statique et supports d'impression des « Prières esprit Taizé » à la Crypte
Saint-Lambert de Vaugirard (Paris 15e). Prière dans l'esprit de Taizé, organisée
par des bénévoles de la paroisse (aucun frère de Taizé n'est présent).

Chaque 2ème mardi du mois à 20h.

Site en ligne : https://tdebroc.github.io/taize-saint-lambert/

## Structure du dépôt

- `site/` — **le site web** publié sur GitHub Pages (`index.html`, `assets/`, `prieres/`).
- `*.html` à la racine — flyers / posters imprimables (A5, A2/A3), éditables dans le navigateur.
- `*.pdf`, `*.png` à la racine — versions exportées et images sources.

## 🚀 Publication / Republication (IMPORTANT)

**Le site est publié via GitHub Pages, alimenté par GitHub Actions.**

Le workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) déploie
automatiquement le **contenu du dossier `site/`** sur GitHub Pages.

### Pour (re)publier après une modification

1. Modifier les fichiers dans `site/`.
2. Committer et pousser sur la branche `main` :
   ```bash
   git add -A
   git commit -m "..."
   git push origin main
   ```
3. C'est tout : le push déclenche le workflow, qui republie le site en ~1 minute.

> ⚠️ Pour un LLM/agent qui reprend ce projet : **il n'y a pas d'autre étape de
> déploiement**. Modifier `site/` puis `git push origin main` suffit à mettre à
> jour https://tdebroc.github.io/taize-saint-lambert/. Ne pas chercher de FTP,
> de serveur ou de commande `deploy` : tout passe par GitHub Pages via Actions.
> La source Pages doit rester réglée sur « GitHub Actions » (build type `workflow`).
