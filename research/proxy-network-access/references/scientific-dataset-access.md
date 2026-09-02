# Scientific Dataset Access — Site-by-Site Guide

Lessons from downloading 19 polymer databases. Covers access methods, auth requirements, data formats, and workarounds.

## Accessible with Proxy (http://127.0.0.1:7890)

### HuggingFace Datasets
- **PolyOmics** (`yhayashi1986/PolyOmics`): 22 MD snapshot tar.gz files (3–9 GB each). Path: `MD_snapshot_JSON/<ABBREV>.tar.gz`. Use `list_repo_files()` for exact paths.
- **OPoly26-train** (`colabfit/OPoly26-train`): 16 sharded parquet files + `ds.parquet`, ~37 GB.
- **OPoly26-val** (`colabfit/OPoly26-val`): 1 parquet file + `ds.parquet`, ~1.2 GB.
- **PI1M**: Polymer image dataset, ~137 MB.

### polydatabase.com (Polymer-MD-Database)
- Django-based, server-rendered HTML.
- Search via GET: `https://polydatabase.com/?search=a` returns max 198 papers.
- Pagination: `https://polydatabase.com/?search=a&page=N` (20 results/page).
- Detail pages: `https://polydatabase.com/doi/<encoded_doi>/` — contains individual polymer study entries.
- Bulk scrape: curl all list pages → extract DOIs → curl each DOI page → parse HTML tables into JSON/CSV.
- Result: 118 papers, 549 polymer entries.

### materials.colabfit.org (OPoly26)
- ColabFit Exchange hosting for OPoly26 dataset.
- Direct download links on dataset page.
- HuggingFace mirror preferred for programmatic download.

### data.matr.io (HTP-MD)
- Portal page accessible, but actual data requires AWS Cognito authentication.
- Register at https://www.htpmd.matr.io/ — userPoolId: `us-east-1_bLHpPO2vu`.
- Full dataset: 5,962 polymer-salt systems, ~5.7 TB. Selective download only.

## Blocked / Restricted

### Figshare (403 with and without proxy)
- API returns 403 even with proxy — network-layer block, not IP-specific.
- Must download manually via browser.
- Article API format: `https://api.figshare.com/v2/articles/<id>`.

### NanoMine / MaterialsMine
- REST (`/rest/v1/`), GraphQL (`/api/v1/graphql`), SPARQL (`/api/v1/sparql`) — all return "Contact Administrator".
- GitHub repo (`Duke-MatSci/nanomine`) has source code, XML schema, sample data (~60 MB), not the full dataset.
- Full data requires admin registration.

### Polymer-Scholar
- Requires login credentials for API access.
- Site may be intermittently unavailable.

### polyid.nrel.gov
- Unreachable. Data available via GitHub: `NatLabRockies/polyID` (1.3 MB repo with data files + trained models).

## General Workflow for Scientific Dataset Harvesting

1. **Check HuggingFace first** — many datasets are mirrored there with programmatic access.
2. **Check GitHub** — project repos often contain data files or at least schemas.
3. **Test API access** — curl the base URL + known endpoints before writing scrapers.
4. **Scrape HTML as fallback** — for Django/Flask sites with no public API, paginate + parse.
5. **Save README + metadata** — even when data is inaccessible, document what's available and how to get it.
6. **Verify integrity** — compare file sizes to expected values; small files among large siblings indicate corruption.
7. **Use background downloads** — `terminal(background=True, notify_on_complete=True)` for files >1 GB.
