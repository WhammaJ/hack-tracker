# Hack Tracker

Static site tracking confirmed hacks and outages people suspected were hacks.

Live at [hacktracking.com](https://hacktracking.com/).

## Updating entries

Edit `data.json` to add or update entries (two lists: `confirmed` and `speculated`). Each entry has a `date` (the incident date, `YYYY-MM-DD`). If later reporting adds information to an existing entry, set or update the optional `updated` field (`YYYY-MM-DD`) to the date of that news. Do not change an entry's `org` or `date` after it is published; those two fields form the stable id used for comment threads.

Entries are shown with the most recent incident or news update first (`updated` if it is later than `date`, otherwise `date`). When two entries share that date, higher severity comes first. Update `lastUpdated` when you change the file. Use only sourced facts; do not invent details.

After **every** `data.json` edit, rebuild the site with this one command, from the repo root:

```bash
python3 tools/build.py
```

Then commit the generated files and push to `main`.

That command regenerates `index.html`, `sitemap.xml`, `feed.xml`, `llms.txt`, `llms-full.txt`, and `og-image.png` from `data.json`. Do not edit `index.html` by hand; it is generated from `tools/template.html`. Do not edit `CNAME`.

A scheduled check updates `data.json` about every two hours during the day, Eastern Time. That update is not complete until `python3 tools/build.py` has been run and the result has been pushed.
