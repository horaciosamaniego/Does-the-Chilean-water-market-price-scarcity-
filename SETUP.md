# Publishing this repository

Delete this file once you are done — it is setup instructions, not part of the project.

## 1. Replace the placeholder

`horaciosamaniego` appears in four files and must be replaced with your GitHub account or
organisation name before anything is pushed:

```bash
grep -rl horaciosamaniego . | xargs sed -i '' 's/horaciosamaniego/your-github-name/g'   # macOS
grep -rl horaciosamaniego . | xargs sed -i    's/horaciosamaniego/your-github-name/g'   # Linux
```

Files affected: `README.md`, `CITATION.cff`, `docs/index.html`, and this file.

While you are there, add your ORCID to `CITATION.cff` — the placeholder is all zeros.

## 2. Create the repository

Either through the GitHub web interface, creating an empty repository named
`water-rights-chile` with no README, licence or `.gitignore`, or with the CLI:

```bash
gh repo create water-rights-chile --public --source=. --remote=origin
```

## 3. Push

```bash
git init
git add .
git commit -m "Data and analysis code for the Chilean water rights paper"
git branch -M main
git remote add origin https://github.com/your-github-name/water-rights-chile.git
git push -u origin main
```

## 4. Turn on the site

Settings → Pages → Source: *Deploy from a branch* → Branch: `main`, folder: `/docs`.
The site appears at `https://your-github-name.github.io/water-rights-chile/`
within a minute or two. Add that URL to the repository's About panel.

## 5. Get a DOI

Journals increasingly ask for one, and *Water Resources and Economics* will accept a
Zenodo DOI in the data availability statement. Link your GitHub account at
zenodo.org, enable the repository under Settings → GitHub, then cut a release:

```bash
git tag -a v1.0.0 -m "Version submitted for review"
git push origin v1.0.0
```

Zenodo mints the DOI automatically. Add it to `CITATION.cff` and to the manuscript.

## Before you push, decide two things

**The SISS transaction data.** `data/datos_mensual_mediterraneo_revb.csv` is a
derived aggregate of records held by the Superintendencia de Servicios Sanitarios.
Redistributing an aggregate for verification is normally defensible, but confirm
the terms before the repository goes public. If redistribution is not permitted,
remove that file, keep the precipitation and scenario data, and add a short note in
`data/README.md` explaining how to request the transaction records. The code will
fail informatively rather than silently.

**Whether to publish now or at acceptance.** Making the repository public now lets
you cite it in the cover letter and lets referees check the analysis, which is an
advantage for a paper whose central claim rests on a correction. Waiting until
acceptance is the more common practice. Either works, but decide before pushing,
since a repository that has been public cannot be made private in any meaningful
sense.
