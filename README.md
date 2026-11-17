# Hack Tracker

Static site tracking confirmed hacks and outages people suspected were hacks.

Live at [hacktracking.com](https://hacktracking.com/).

## Updating entries

Edit `data.json` to add or update entries (two lists: `confirmed` and `speculated`). Entries are shown in file order within each severity level (Critical, High, Medium, Low), so put bigger incidents first. Update `lastUpdated` when you change it. Use only sourced facts; do not invent details.

After **every** `data.json` edit, rebuild the site with this one command, from the repo root:

```bash
python3 tools/build.py
```

Then commit the generated files and push to `main`.

That command regenerates `index.html`, `sitemap.xml`, `feed.xml`, `llms.txt`, `llms-full.txt`, and `og-image.png` from `data.json`. Do not edit `index.html` by hand; it is generated from `tools/template.html`. Do not edit `CNAME`.

A scheduled check updates `data.json` about every two hours during the day, Eastern Time. That update is not complete until `python3 tools/build.py` has been run and the result has been pushed.
