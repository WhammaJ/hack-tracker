# Hack Tracker

Static site tracking confirmed hacks and outages people suspected were hacks.

Live at [hacktracking.com](https://hacktracking.com/).

## Updating entries

Edit `data.json` to add or update entries (two lists: `confirmed` and `speculated`). Each entry has a `date` (the incident date, `YYYY-MM-DD`). If later reporting adds information to an existing entry, set or update the optional `updated` field (`YYYY-MM-DD`) to the date of that news. Do not change an entry's `org` or `date` after it is published; those two fields form the stable id used for comment threads.

Each entry also has a `countries` list of ISO 3166-1 alpha-2 codes (for example `["US"]` or `["US","GB"]`) for where the hacked organization is based and/or where affected victims are. Use `EU` for European Union institutions. An entry counts as USA if the list includes `"US"` — that is, a U.S. organization or government, or U.S. people or customers clearly affected. If the entry's own text and sources give no evidence of location, use `[]` and do not guess; those entries appear only in the Worldwide view. Use `GB` for the United Kingdom, not `UK`.

The site defaults to a USA view. A USA / Worldwide toggle (remembered in the browser, and shareable as `?region=us` or `?region=world`) filters the lists. The confirmed and speculated counts update with the current view. When you add or update an entry, set `countries` from that entry's own text and sources.

Entries are shown with the most recent incident or news update first (`updated` if it is later than `date`, otherwise `date`). When two entries share that date, higher severity comes first. Update `lastUpdated` when you change the file. Use only sourced facts; do not invent details.

After **every** `data.json` edit, rebuild the site with this one command, from the repo root:

```bash
python3 tools/build.py
```

Then commit the generated files and push to `main`.

That command regenerates `index.html`, `sitemap.xml`, `feed.xml`, `llms.txt`, `llms-full.txt`, and `og-image.png` from `data.json`. Do not edit `index.html` by hand; it is generated from `tools/template.html`. Do not edit `CNAME`.

A scheduled check updates `data.json` about every two hours during the day, Eastern Time. That update is not complete until `python3 tools/build.py` has been run and the result has been pushed.

