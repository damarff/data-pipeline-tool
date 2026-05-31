# Data Pipeline Tool

**Lightweight ETL pipeline for data processing automation.**

A portable Python ETL framework that extracts data from multiple sources (CSV, JSON, SQLite, HTTP API), applies configurable transformations via a modular transformer system, and loads results into Excel, CSV, JSON, or SQLite. Designed for freelancers and small teams who need reliable data processing without heavyweight infrastructure.

---

## Features

| Area | Capabilities |
|------|-------------|
| **Extract** | CSV, JSON, SQLite, HTTP REST API — with encoding, delimiter, and dtype config |
| **Transform** | 10+ transformers: clean missing values, normalize columns, rename, type-cast, compute formulas, filter rows, remove duplicates |
| **Load** | Excel (.xlsx with auto-column-width), CSV, JSON, SQLite |
| **Config** | Declarative YAML — one file defines the entire pipeline |
| **CLI** | Full pipeline mode or step-by-step (`extract` / `transform` / `load`) |
| **Auto-type** | Numeric columns averaged, text columns mode-filled — no manual config needed for basic cleaning |

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full pipeline with sample data
python main.py --config config.yaml

# Or step-by-step:
python main.py extract --source sample_data/sales.csv
python main.py transform --config config.yaml
python main.py load --output output/report.xlsx
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     config.yaml                              │
│  source → [transformations] → output                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                      Pipeline.run()                          │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐           │
│  │ EXTRACT  │───▶│  TRANSFORM   │───▶│   LOAD   │           │
│  │          │    │              │    │          │           │
│  │ • CSV    │    │ ┌──────────┐ │    │ • Excel  │           │
│  │ • JSON   │    │ │ clean    │ │    │ • CSV    │           │
│  │ • SQLite │    │ │ normalize│ │    │ • JSON   │           │
│  │ • API    │    │ │ compute  │ │    │ • SQLite │           │
│  │          │    │ │ filter   │ │    │          │           │
│  └──────────┘    │ └──────────┘ │    └──────────┘           │
│                  └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### Transformer Modules

```
transformers/
├── __init__.py        # Registry and exports
├── clean.py           # CleanMissing — fill/drop NA, drop duplicates
├── normalize.py       # NormalizeColumns — rename, type-cast, strip
├── compute.py         # AddColumn — evaluate arithmetic formulas
└── filter.py          # Filter — row conditions with operators
```

---

## Configuration

Full pipeline is defined in a single YAML file:

```yaml
pipeline:
  name: "Sales Data Processing"
  source:
    path: "sample_data/sales.csv"
  transformations:
    - type: "clean_missing"
      strategy: "fill"            # fill | drop | ffill | bfill
      drop_duplicates: true

    - type: "normalize_columns"
      mapping:
        "Nama": "name"
        "Harga": "price"
        "Jumlah": "quantity"
      type_casts:
        price: "float"
        quantity: "int"
        date: "datetime"

    - type: "add_column"
      name: "total"
      formula: "price * quantity"

    - type: "filter"
      condition: "price > 0"

  output:
    format: "excel"               # excel | csv | json | sqlite
    path: "output/processed_data.xlsx"
```

### Transformer Reference

| Type | Config Keys | Description |
|------|-------------|-------------|
| `clean_missing` | `strategy` (fill/drop/ffill/bfill), `fill_value`, `columns`, `drop_duplicates`, `duplicate_subset` | Handle missing values and duplicates |
| `normalize_columns` | `mapping` (rename dict), `type_casts` (col→type), `drop_unmapped`, `strip_whitespace` | Rename and cast columns |
| `add_column` | `name`, `formula` (arithmetic expression), or `operations` (list of name+formula) | Add computed columns |
| `filter` | `condition` (single) or `conditions` (list), `mode` (and/or) | Filter rows by expression |

### Supported Formula Syntax

The formula engine supports arithmetic on column references:

```
price * quantity
total * (1 - discount / 100)
(revenue - cost) / revenue * 100
qty_a + qty_b
```

---

## CLI Reference

```bash
# Full pipeline mode
python main.py --config config.yaml
python main.py -c config.yaml --log-level DEBUG

# Step-by-step mode
python main.py extract --source data.csv
python main.py extract --source data.json
python main.py extract --source sales.db --query "SELECT * FROM invoices WHERE total > 100"
python main.py extract --source https://api.example.com/sales --type api

python main.py transform --config transform.yaml

python main.py load --output report.xlsx
python main.py load --output report.csv --format csv
python main.py load --output data.db --format sqlite
```

---

## Sample Data

The `sample_data/sales.csv` file contains 20 realistic retail transaction rows with deliberately dirty data:

- Missing values in `Harga`, `Jumlah`, `Tanggal`, `Kategori`, `Diskon`
- Multiple date formats (`2024-01-05`, `15 Jan 2024`, `19-01-2024`, `31-Jan-2024`)
- Inconsistent column name language (Indonesian)
- Duplicate row

Running the pipeline cleans, normalizes, computes totals, and exports a clean Excel report.

### Before (sample_data/sales.csv)

```
Nama,Harga,Jumlah,Tanggal,Kategori,Diskon
Indomie Goreng,3500,10,2024-01-05,Makanan,0
Minyak Goreng,,5,2024-01-05,,5
Beras 5kg,75000,3,15 Jan 2024,Sembako,
...
```

### After (output/processed_sales.xlsx)

```
name,price,quantity,date,category,discount,total,discounted_total
Indomie Goreng,3500.0,10,2024-01-05,Makanan,0,35000.0,35000.0
Minyak Goreng,<mean>,5,2024-01-05,<mode>,5,<computed>,<computed>
Beras 5kg,75000.0,3,2024-01-15,Sembako,<mode>,225000.0,225000.0
...
```

---

## Project Structure

```
data-pipeline-tool/
├── pipeline.py            # ETL Pipeline class
├── main.py                # CLI entry point
├── config.yaml            # Example pipeline configuration
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── .gitignore
├── README.md
├── transformers/
│   ├── __init__.py
│   ├── clean.py           # Missing value handler
│   ├── normalize.py       # Column mapper & typecaster
│   ├── compute.py         # Formula evaluator
│   └── filter.py          # Row filter
└── sample_data/
    └── sales.csv           # Dirty sample data (20 rows)
```

---

## Dependencies

- **pandas** — data manipulation
- **openpyxl** — Excel read/write
- **pyyaml** — YAML config parsing
- **python-dotenv** — environment variable loading
- **requests** — HTTP API extraction

---

## Use Cases

- **Sales report automation** — extract raw CSVs, clean/normalize, compute KPIs, export formatted Excel
- **API data ingestion** — pull data from REST endpoints, transform, load into SQLite for analysis
- **Data migration** — convert between CSV → Excel → SQLite with transformations along the way
- **Freelance data processing** — one-off client data cleaning jobs with repeatable config

---

## License

MIT — free to use, modify, and distribute.
