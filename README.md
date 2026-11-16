# Feynman's Legacy

Feynman's Legacy identifies Earth sites that resemble reference locations on the Moon and Mars. The notebooks prepare the data, train the monthly forecast model, and rank Earth sites. FastAPI serves the published results, and the Angular application displays them on an interactive map.

## Run the app for evaluation (Windows)

The repository includes the Earth data, reference profiles, and trained model used by the map. Follow the three steps below to open the app and run a search. The data-generation and training instructions are optional.

### 1. Open the repository in PowerShell

Install **Git for Windows with Git LFS**, **uv** (`winget install --id=astral-sh.uv -e`), and **Node.js 24.x with npm**. The [official Node.js 24.22.1 release](https://nodejs.org/download/release/v24.22.1/) has installers for Windows x64 and ARM64. After installing, open a new PowerShell window and confirm that these commands all print a version:

```powershell
git lfs version
uv --version
node --version
npm.cmd --version
```

If you have not cloned the repository yet, run:

```powershell
Set-Location "$env:USERPROFILE\Downloads" -ErrorAction Stop
git lfs install
git clone https://github.com/jose-aquino-jr/feynmans-legacy.git
```

Open the checkout from that clone or use the path to your existing checkout. Run these commands from its root before continuing:

```powershell
Set-Location "$env:USERPROFILE\Downloads\feynmans-legacy" -ErrorAction Stop
git rev-parse --show-toplevel
git lfs pull
```

Update the path in `Set-Location` if you cloned elsewhere. The Git root should contain `requirements.txt` and `front-end/proxy.conf.json`. If `git lfs pull` fails, resolve the download before starting the API.

### 2. Start the API

Keep this terminal at the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src -ErrorAction Stop).Path
uv run --no-project --python 3.13 --with-requirements requirements.txt python -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On the first run, uv may download Python and the dependencies into its cache. Keep the terminal open once Uvicorn is listening. Open [recommendation options](http://127.0.0.1:8000/api/v1/analogos/recomendacoes/opcoes) and verify that the JSON contains bases and observed months. This check also confirms the model can load.

### 3. Build and open the map

Open a **second PowerShell window**. Use the `front-end` directory in the same checkout as the API:

```powershell
Set-Location "$env:USERPROFILE\Downloads\feynmans-legacy\front-end" -ErrorAction Stop
npm.cmd ci
npm.cmd start -- --host 127.0.0.1 --port 4200
```

Run the start command after `npm.cmd ci` succeeds. The development server compiles the app and forwards `/api` to port 8000. When Angular reports that it is ready, open [the map](http://127.0.0.1:4200/mapa). Keep both terminals open while navigating.

1. Open **Analysis Settings**, select **Jezero Crater**, **Thermal**, and **August 2026**, then run the search. The map should list Earth sites from the observed data.
2. Try **September 2026** with the recursive projection. The first future search shows a progress state while the model computes the requested month.

For a production compilation check, run `npm.cmd run build` from `front-end/` after `npm.cmd ci`. The output is in `front-end/dist/`. To evaluate the app locally, use the development server above so API requests go through the proxy.

### If the map does not open or return results

| What you see | What to do |
|---|---|
| `requirements.txt` or `src` cannot be found | Correct the path in `Set-Location`. The API command runs from the repository root. |
| `npm.cmd` is not recognized | Install Node.js with npm enabled, then reopen PowerShell and run `npm.cmd --version` before continuing. |
| `WinError 10048` | The port is already in use. Check the [API options](http://127.0.0.1:8000/api/v1/analogos/recomendacoes/opcoes) or [map](http://127.0.0.1:4200/mapa), depending on the port. If the existing instance is the intended one, keep using it. Otherwise stop the earlier server in its terminal and retry. |
| The map opens, but searches fail | Open the [options endpoint through Angular](http://127.0.0.1:4200/api/v1/analogos/recomendacoes/opcoes). If it works directly on port 8000 but fails on port 4200, confirm Angular started from the correct checkout with `front-end/proxy.conf.json`. |
| The API options report that the model cannot load | Run `git lfs pull` from the repository root. The local pickle must match the SHA-256 in `data/terra/analise_analogos/manifesto_publicacao.json`. |

## Rebuild the data and model (optional)

<details>
<summary>Notebook pipeline and development checks</summary>

## 1. Clone the repository and set up Python

Install Git, Git LFS, Python 3.12, and Node.js with npm. The backend CI uses Python 3.12. The frontend declares its npm version in [front-end/package.json](front-end/package.json).

```bash
git lfs install
git clone https://github.com/jose-aquino-jr/feynmans-legacy.git
cd feynmans-legacy
git lfs pull
python -m venv .venv
```

Activate the environment for your shell:

| Shell | Command |
|---|---|
| PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Git Bash on Windows | `source .venv/Scripts/activate` |
| Linux or macOS | `source .venv/bin/activate` |

From the repository root:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m ipykernel install --sys-prefix --name feynmans-legacy --display-name "Python (Feynman's Legacy)"
```

Open the repository in a Jupyter-compatible editor such as VS Code with its Python and Jupyter extensions. Select **Python (Feynman's Legacy)** as the kernel in each notebook. The development requirements include the notebook dependencies and Optuna.

## 2. Check the input data

| Input | Purpose |
|---|---|
| `data/terra/terra.parquet` | Monthly Earth observations keyed by `location_id` and `anomes` (YYYYMM). |
| `data/terra/spec_analogos/estaticas.parquet` and `coordenadas.parquet` | Static features and geographic coordinates. |
| `data/terra/spec_analogos/dicionario_spec.csv` | Earth variable definitions and units. |
| `data/lua/lua.parquet` and `data/marte/marte.parquet` | Fixed reference profiles for the Moon and Mars. |
| `config/nichos.json` and `config/criterios_referencia_proposta.csv` | Variable mappings, targets, weights, and tolerances. |

Run the input-check cell in Notebook 01 before training. The prepared files above are the notebook inputs. Raw planetary data processing is documented in the [Moon README](data/lua/README.md), [Mars README](data/marte/README.md), and [Earth data specification](data/terra/spec_analogos/README.md).

## 3. Run the notebooks in order

Run each notebook from the first cell through the last. Restart its kernel before a clean run. The output directory is `data/terra/analise_analogos/`.

1. [**01 — Feature selection and clustering**](notebooks/01_spec_e_clusterizacao.ipynb). Validates the catalogs and keys, chooses clustering features and forecast targets, and writes the clusters, selection metadata, static features, and coordinates.
2. [**02 — Monthly forecasting**](notebooks/02_previsao_mensal.ipynb). Uses Optuna and LightGBM on a reproducible sample, evaluates the chronological holdout, and publishes predictions for one to three months after the cutoff. Allow time for tuning and batch inference. Check that `previsoes.parquet`, `metricas_previsao.parquet`, `otimizacao_lightgbm.json`, and `modelos/previsao_mensal.pkl` exist in the output directory. When using a published release instead of retraining, fetch its large model with `git lfs pull` and use the data and forecast artifacts from the same publication. Load pickle files only from your own training or a trusted project publication.
3. [**03 — Recommendations on the world map**](notebooks/03_recomendacao_e_mapa.ipynb). Run it to verify an observed month. Leave `ANOMES = None` to use the latest observation. To verify a forecast, set `ANOMES` to a month in `previsoes.parquet` and rerun the notebook. Choose the reference body with `CORPO`, the base with `BASE`, and the comparison profile with `NICHO`. The charts use English labels while the underlying identifiers still match the dataset.

If Plotly reports that `nbformat` is unavailable, check that the notebook is using the environment from step 1, reinstall the development requirements in that environment, and restart the kernel.

## 4. Publish the datasets for the API

With the outputs from Notebooks 01 and 02 available, run this from the repository root:

```bash
python scripts/gerar_analogos.py
```

The script writes the Earth–Moon and Earth–Mars pairs, scores, and related logistics data under `data/tratados/analogos/`. Re-run it after changing the input profiles or publishing a new set of forecasts. To name newly ranked sites, run `python scripts/nomear_locais.py` after the first generation, then run `python scripts/gerar_analogos.py` again.

For a checkout that includes the **temporal recommendations API** and `scripts/publicar_projecoes.py`, also seed the recursive forecast cache and verify the publication:

```bash
python scripts/publicar_projecoes.py
python scripts/publicar_projecoes.py --verificar
```

By default the script seeds 12 months after the observed cutoff. Use `--meses` for a different count or `--ate YYYYMM` for a specific month. The API can extend the forecast on demand. Keep its projection cache writable. If the publication script is absent, the checkout supports the notebook forecasts and published pairs, and you need the temporal recommendations changes for recursive forecasts in the web app.

## 5. Start FastAPI and check the data

Copy `.env.example` to `.env` if you need to override the defaults. The example documents the `FL_*` settings. Run the API from the repository root so relative data and model paths resolve correctly. In the API terminal, add the project source to the Python import path:

- PowerShell: `$env:PYTHONPATH = (Resolve-Path src).Path`
- Bash: `export PYTHONPATH="$PWD/src"`

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:8000/api/v1/analogos/bases
```

Open [Swagger UI](http://127.0.0.1:8000/docs) to inspect the actual responses. Verify that the bases endpoint returns reference sites, since a healthy API process alone does not confirm that the pipeline outputs are present. See [API examples](docs/api.md) for dataset, model, and analog endpoints.

With the temporal recommendations API available, check its options and run a query using an observed month from the options response:

```bash
curl -f http://127.0.0.1:8000/api/v1/analogos/recomendacoes/opcoes
curl -f "http://127.0.0.1:8000/api/v1/analogos/recomendacoes?anomes=202608&nicho=Todos&k=5"
```

To test a recursive forecast, replace `202609` below with a month after your observed cutoff.

```bash
curl -f "http://127.0.0.1:8000/api/v1/analogos/recomendacoes?anomes=202609&nicho=Todos&k=5&estrategia=recursiva"
```

An HTTP `202` means projection is in progress. Retry the same URL after the number of seconds in `Retry-After`.

## 6. Start the Angular application

Leave FastAPI running. From the repository root, open a separate terminal:

```bash
cd front-end
npm ci
npm start
```

Open [http://localhost:4200](http://localhost:4200). Open the map, select a Moon or Mars base and a comparison profile, and submit the query. On a checkout that includes the API-backed map, confirm that the browser requests succeed for both an observed month and a future month. The development proxy on that checkout forwards `/api` to `127.0.0.1:8000`. For production, serve the compiled frontend and route `/api` to FastAPI on the same origin.

## Checks

Run the backend checks from the repository root with the same `PYTHONPATH` as the API terminal:

```bash
python -m ruff check .
python -m mypy
python -m pytest -q
```

Run the frontend checks from `front-end/` after `npm ci`:

```bash
npm test -- --watch=false
npm run build
```

</details>

## Repository guide

| Path | Contents |
|---|---|
| `notebooks/` | Data preparation, forecasting, and recommendations. |
| `src/feynmans_legacy/` | Reusable analysis, modeling, and ranking code. |
| `app/` | FastAPI routes, schemas, and services. |
| `front-end/` | Angular application. |
| `config/` | Reference profiles and comparison criteria. |
| `data/` and `models/` | Data products, model artifacts, and their documentation. |
| `docs/` | API examples and methodology. |
