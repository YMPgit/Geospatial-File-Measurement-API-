# Geospatial File Measurement API

Upload a **KML** file or a **Shapefile ZIP**, store it in **PostgreSQL**, and get back
**per-feature area/length measurements** computed with GDAL/pyproj — plus a React UI to
browse the results.

- **Backend:** FastAPI · SQLAlchemy · GeoPandas/pyogrio · pyproj/Shapely
- **Frontend:** React 19 · TypeScript · Tailwind CSS 4 · Vite · React Router
- **Infra:** PostgreSQL + uvicorn + Vite — runs fully on your machine, no containers
- **Tests:** pytest — 73 tests, green against both SQLite and PostgreSQL

---

## Quick start

Prerequisites: Python 3.13, Node 22, PostgreSQL 14+.

```bash
# 1. database
createdb geospatial_db                      # or point DATABASE_URL at any Postgres

# 2. backend  (http://localhost:8000)
cd backend
pip install -r requirements.txt
cp .env.example .env                        # then set your DATABASE_URL
uvicorn app.main:app --reload

# 3. frontend  (http://localhost:5173)
cd frontend
npm install
npm run dev
```

| Service  | URL                         |
| -------- | --------------------------- |
| Frontend | http://localhost:5173       |
| API      | http://localhost:8000       |
| Swagger  | http://localhost:8000/docs  |

`backend/.env` is read by pydantic-settings; environment variables always win over it.
The frontend reads `VITE_API_BASE_URL` (see `frontend/.env.development`, which points at
`http://localhost:8000`).

### Try it in 30 seconds

```bash
curl -F "file=@sample_data/sample_mixed.kml" http://localhost:8000/api/files/
# → {"id":"…","filename":"sample_mixed.kml","file_type":"kml","feature_count":3,
#    "crs":"EPSG:4326","status":"COMPLETED"}

curl http://localhost:8000/api/files/<id>/measurements/
```

Or open the UI, drag `sample_data/sample_shapefile_utm.zip` onto the drop zone and click
**Upload & measure**.

---

## API

| Method   | Path                                | Purpose                                        |
| -------- | ----------------------------------- | ---------------------------------------------- |
| `POST`   | `/api/files/`                       | Upload + measure a `.kml` or `.zip`            |
| `GET`    | `/api/files/`                       | List uploads, newest first (`limit`, `offset`) |
| `GET`    | `/api/files/{file_id}/`             | File metadata                                  |
| `GET`    | `/api/files/{file_id}/measurements/`| All per-feature measurements                   |
| `DELETE` | `/api/files/{file_id}/`             | Delete a file, its measurements and the stored original |
| `GET`    | `/health`                           | `{"status":"healthy"}`                         |
| `GET`    | `/docs`, `/openapi.json`            | Interactive docs / machine-readable spec       |

### Successful upload (201)

```json
{
  "id": "6f1c1b2e-4b0a-4a5e-9d5a-8f8d9a2c1111",
  "filename": "sample_mixed.kml",
  "file_type": "kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### Measurements (200)

```json
{
  "file_id": "6f1c1b2e-…",
  "filename": "sample_mixed.kml",
  "file_type": "kml",
  "feature_count": 3,
  "source_crs": "EPSG:4326",
  "status": "COMPLETED",
  "measurements": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "properties": { "Name": "City block" },
      "measurement_type": "area",
      "measurement_value": 1226874.1,
      "measurement_unit": "m²",
      "measurement_status": "CALCULATED",
      "measurement_reason": null,
      "projected_crs": "EPSG:32633",
      "geometry": { "type": "Polygon", "coordinates": [[[13.395, 52.515], "…"]] }
    }
  ]
}
```

Values are rounded to **4 decimals for presentation**; the database keeps full precision.

### Error semantics

Validation happens in two phases, which is why some 400s carry a record and some do not:

| Phase | Checked | On failure |
| ----- | ------- | ---------- |
| **1 — before any DB row** | extension (`.kml`/`.zip`), size, empty file, XML well-formedness, ZIP structure, Shapefile components (`.shp`+`.shx`+`.dbf`), unsafe ZIP entries, expansion cap | `400 {"detail": "…"}` (or `413`) and **no record is created** |
| **2 — record exists** | GDAL read errors, zero features, unrecoverable processing errors | record persisted with `status: "FAILED"`, response is **400 with the FAILED record body** (its `error_message` explains why) |

Other codes: `404` unknown file id · `413` upload too large (Content-Length middleware +
streaming guard) · `422` missing multipart field · `500` sanitized
`{"detail": "Internal server error"}` (the traceback is logged server-side only).

---

## How measurements are computed

### Geometry dispatch

| Geometry (first feature part) | Result |
| ----------------------------- | ------ |
| Polygon / MultiPolygon        | **area** in `m²` |
| LineString / MultiLineString / LinearRing | **length** in `m` |
| Point / MultiPoint            | `NOT_REQUIRED` (no meaningful area/length) |
| GeometryCollection / other    | `UNSUPPORTED` |
| Null / empty geometry         | `UNAVAILABLE` |
| Unknown source CRS            | `UNAVAILABLE` — a CRS is **never invented** |
| Invalid geometry              | repaired with `shapely.make_valid`, then measured; `measurement_reason` records the repair (e.g. bow-tie polygons) |

### CRS strategy

| Source CRS | What happens |
| ---------- | ------------ |
| **Projected** | measured in that CRS, converted to metres with the axis unit factor (e.g. EPSG:2229 US survey feet → ×0.3048006096 for length, squared for area) |
| **Geographic** | reprojected to the UTM zone of the feature's representative point when the whole feature fits that zone and latitude ∈ [-80°, 84°]; otherwise a regional **LAEA** (area) / **AEQD** (length) projection centred on the feature |
| **Missing** (e.g. shapefile without `.prj`) | measurements `UNAVAILABLE`, file still `COMPLETED` with `source_crs: null` |

`projected_crs` on every measurement tells you exactly which CRS was used
(`EPSG:32633`, `LAEA lon_0=13.4000 lat_0=52.5200`, …).

### Archive handling

- ZIP entries with absolute paths, `..` traversal or symbolic links are rejected.
- Total uncompressed size is capped at **20× the upload limit** (zip-bomb guard).
- Only the selected shapefile's components are extracted (to a temp dir that is always
  deleted); member basenames are used, so hostile names cannot escape the directory.
- A ZIP with **multiple `.shp` files** uses the lexicographically first one and logs a
  warning (deterministic and documented rather than "first in ZIP order").
- KML is read from its **default layer**; nested directories inside the ZIP are supported.

---

## Frontend

- **Dashboard (`/`)** — drag & drop upload (client-side extension/size checks, server
  errors surfaced verbatim), API health chip, recent uploads table (click to inspect,
  per-row **Delete** with confirmation).
- **Results (`/files/:id`)** — file metadata, failure banner for `FAILED` files, summary
  cards (features, total area, total length, calculation coverage), a per-feature table
  with properties, value+unit, status badge, reason and the CRS used (first 500 rows shown),
  and a **Delete** action that returns to the dashboard.
- Typed fetch client with timeouts and a normalized `ApiError`, no hardcoded hostnames
  (`VITE_API_BASE_URL`; empty = same origin, useful when serving the built app statically).

---

## Tests

```bash
cd backend
python -m pytest                          # SQLite (fast, default)
TEST_DATABASE_URL=postgresql+psycopg2://postgres:pass@localhost:5432/geospatial_db_test \
  python -m pytest                        # real PostgreSQL
```

Coverage includes: health, happy-path KML/Shapefile uploads, exact metric values
(10 000 m² square, 300 m line, 929.0341 m² from 10 000 ftUS²), geographic→UTM area within
1% of the geodesic truth, missing `.prj`, invalid-geometry repair, GeometryCollection
`UNSUPPORTED`, point `NOT_REQUIRED`, multi-shapefile tie-break, path traversal/symlink/zip
bomb rejection, 413/422/404 handling, FAILED persistence, delete (204, cascade, stored-file
removal, 404), response rounding, NaN-free JSON and a sanitized 500.

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run build       # typecheck + vite build
```

---

## Configuration

| Variable            | Default                                                      | Purpose |
| ------------------- | ------------------------------------------------------------ | ------- |
| `DATABASE_URL`      | `postgresql+psycopg2://postgres:postgres@localhost:5432/geospatial_db` | SQLAlchemy URL |
| `MAX_UPLOAD_SIZE_MB`| `20`                                                         | upload cap (middleware + streaming) |
| `UPLOAD_DIR`        | `uploads`                                                    | where originals are stored |
| `CORS_ORIGINS`      | `http://localhost:5173,http://localhost:3000`                | comma-separated allow-list |
| `ENVIRONMENT`       | `development`                                                | `development` / `production` / `test` |
| `LOG_LEVEL`         | `INFO`                                                       | logging verbosity |
| `VITE_API_BASE_URL` | `""` (dev: `http://localhost:8000`)                          | frontend API base |

---

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── api/files.py          # endpoints
│   │   ├── core/                 # config, logging, exceptions
│   │   ├── db/                   # engine/session + ORM models
│   │   ├── schemas/              # Pydantic response models
│   │   ├── services/             # crs, measurement, kml, shapefile, file_processor
│   │   ├── utils/                # JSON/GeoJSON helpers, upload validation
│   │   └── main.py               # app factory, middleware, handlers, /health
│   ├── tests/                    # pytest suite (73 tests)
│   ├── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # Uploader, RecentFilesTable, StatusBadge
│   │   ├── pages/                # Dashboard, Results
│   │   ├── services/api.ts       # typed fetch client
│   │   └── types.ts              # mirrors the API schemas
├── sample_data/                  # ready-to-upload examples (+ generator script)
└── README.md
```

---

## Design decisions

- **Two-phase validation** so a bad file never pollutes the database, while a file that is
  structurally fine but unreadable by GDAL is still auditable as `FAILED`.
- **`create_all` on startup** instead of Alembic: the schema is created by the app itself,
  which keeps the submission self-contained. For production you would add migrations.
- **Processing is synchronous inside the request** (files ≤ 20 MB) so `POST /api/files/`
  returns the finished measurement set; the `PROCESSING` state exists in the schema so an
  async worker can be dropped in later without a migration.
- **Uploads are kept on disk** (`uploads/`) for debugging and reprocessing; only metadata
  and measurements go to PostgreSQL.
- **Rounding only at the presentation layer**, so sums/aggregations stay accurate.
- **No geometry simplification** — full GeoJSON geometry is stored and returned so the
  results can be drawn on a map later.
- Known limitations: only the first KML layer is read; multi-ZIP/Multiple-file formats
  (GeoPackage, GeoJSON, …) are out of scope; antimeridian-crossing features fall back to a
  regional projection whose distortion increases far from its centre.

## Sample data

| File | Demonstrates |
| ---- | ------------ |
| `sample_mixed.kml` | polygon + line + point in one upload |
| `sample_polygon.kml` / `sample_line.kml` / `sample_point.kml` | single geometry types |
| `sample_shapefile_utm.zip` | exact 10 000 m² area in EPSG:32633 |
| `sample_shapefile_line.zip` | exact 500 m length |
| `sample_shapefile_no_prj.zip` | missing `.prj` → `UNAVAILABLE`, file still `COMPLETED` |
| `sample_shapefile_invalid_geometry.zip` | self-intersecting polygon repaired then measured |
| `corrupt_shapefile.zip` | structurally valid ZIP, unreadable `.shp` → `FAILED` record |
| `invalid_text.kml` | phase-1 rejection, no record created |

Regenerate them any time with `python sample_data/generate_samples.py`.
