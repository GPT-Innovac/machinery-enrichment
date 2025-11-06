import os, asyncio, json, shutil
from datetime import datetime
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
from .enrich import enrich_one

load_dotenv()

# Project paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DASHBOARD_DIR = OUTPUT_DIR / "dashboard"
OUTPUT_TABLE_DIR = OUTPUT_DIR / "table"
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)

INPUT_PATH = os.environ.get("INPUT_PATH", str(INPUT_DIR / "input.csv"))
OUTPUT_CSV_ENV = os.environ.get("OUTPUT_CSV")
OUTPUT_NDJSON_ENV = os.environ.get("OUTPUT_NDJSON")
ARCHIVE_CSV_PATH = os.environ.get("ARCHIVE_CSV")  # optional global append CSV
ARCHIVE_NDJSON_PATH = os.environ.get("ARCHIVE_NDJSON")  # optional global append NDJSON
CONCURRENCY = int(os.environ.get("CONCURRENCY", "5"))


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize diverse CRM headers to expected columns: company_name, address, website, phone."""
    # Clean headers
    df = df.rename(columns={c: c.strip() for c in df.columns})

    # Fast path: already normalized
    if {"company_name", "address"}.issubset(df.columns):
        if "website" not in df.columns:
            df["website"] = ""
        if "phone" not in df.columns:
            df["phone"] = ""
        return df

    # Try mapping Aquise CRM headers
    name_col = None
    street_col = None
    zip_col = None
    city_col = None
    website_col = None
    phone_col = None
    for col in df.columns:
        low = col.lower()
        if name_col is None and low.startswith("accountname"):
            name_col = col
        if street_col is None and "straße (rechnungsanschrift)" in low:
            street_col = col
        if zip_col is None and "plz (rechnungsanschrift)" in low:
            zip_col = col
        if city_col is None and "stadt (rechnungsanschrift)" in low:
            city_col = col
        if website_col is None and low.startswith("website"):
            website_col = col
        if phone_col is None and "telefon zentrale" in low:
            phone_col = col

    if name_col and (street_col or zip_col or city_col):
        def make_address(row: pd.Series) -> str:
            parts = []
            if street_col:
                parts.append(str(row.get(street_col, "")).strip())
            zip_val = str(row.get(zip_col, "")).strip() if zip_col else ""
            city_val = str(row.get(city_col, "")).strip() if city_col else ""
            town = (zip_val + " " + city_val).strip()
            if town:
                parts.append(town)
            parts.append("DE")
            return ", ".join([p for p in parts if p])

        out = pd.DataFrame()
        out["company_name"] = df[name_col].astype(str).str.strip()
        out["address"] = df.apply(make_address, axis=1)

        if website_col and website_col in df.columns:
            def norm_url(x: str) -> str:
                x = (x or "").strip()
                if not x or x.lower() in {"nan", "none", "null"}:
                    return ""
                if x.startswith("http://") or x.startswith("https://"):
                    return x
                if x.startswith("www.") or "." in x:
                    return "https://" + x
                return x
            out["website"] = df[website_col].astype(str).map(norm_url)
        else:
            out["website"] = ""
        # Phone mapping
        if phone_col and phone_col in df.columns:
            out["phone"] = df[phone_col].astype(str).str.strip()
        else:
            out["phone"] = ""
        return out

    # Fallback with helpful error
    missing = [c for c in ["company_name", "address"] if c not in df.columns]
    if missing:
        raise ValueError(
            "Unsupported CSV headers. Provide 'company_name' and 'address' columns, or a CRM export "
            "with 'Accountname', 'Straße (Rechnungsanschrift)', 'PLZ (Rechnungsanschrift)', 'Stadt (Rechnungsanschrift)'."
        )
    if "website" not in df.columns:
        df["website"] = ""
    if "phone" not in df.columns:
        df["phone"] = ""
    return df


def read_input(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return _normalize_columns(df)


async def worker(row, results, sem):
    async with sem:
        data = await enrich_one(row["company_name"], row["address"], row.get("website"), row.get("phone"))
        # Attach input fields for downstream outputs
        data["company_name"] = row.get("company_name", "")
        data["address"] = row.get("address", "")
        data["website"] = row.get("website", "")
        data["phone"] = row.get("phone", "")

        # Back-compat for dashboard: provide a derived wrapper
        if "derived" not in data or not isinstance(data.get("derived"), dict):
            data["derived"] = {}
        if "company_type" in data:
            data["derived"]["company_type"] = data.get("company_type")
        if "industry_focus" in data and not data["derived"].get("industry_focus"):
            data["derived"]["industry_focus"] = data.get("industry_focus", [])
        if "machine_types" in data and not data["derived"].get("machine_types"):
            data["derived"]["machine_types"] = data.get("machine_types", [])

        # Convenience aliases
        sb = data.get("score_breakdown") or {}
        if isinstance(sb, dict) and "total" in sb:
            data["score_total"] = sb.get("total")
        if "relevance_dach" in data and "relevance" not in data:
            data["relevance"] = data.get("relevance_dach")
        results.append(data)


async def run():
    df = read_input(INPUT_PATH)

    # Derive output filenames from input path when not explicitly set via env
    in_stem = os.path.splitext(os.path.basename(INPUT_PATH))[0]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Always write outputs under data/output/ unless explicitly overridden by env
    out_csv_path = OUTPUT_CSV_ENV or str(OUTPUT_DIR / f"{in_stem}__{ts}.csv")
    out_ndjson_path = OUTPUT_NDJSON_ENV or str(OUTPUT_DIR / f"{in_stem}__{ts}.ndjson")
    # Archive (append-across-batches) files always under data/output/
    archive_csv_path = ARCHIVE_CSV_PATH or str(OUTPUT_DIR / "all_batches.csv")
    archive_ndjson_path = ARCHIVE_NDJSON_PATH or str(OUTPUT_DIR / "all_batches.ndjson")
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks, results = [], []
    for _, row in df.iterrows():
        tasks.append(asyncio.create_task(worker(row, results, sem)))
    for t in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Enriching"):
        await t

    with open(out_ndjson_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # Append to archive NDJSON (with batch metadata), creating if needed
    try:
        with open(archive_ndjson_path, "a", encoding="utf-8") as f:
            for r in results:
                rec = dict(r)
                rec.setdefault("_batch_file", os.path.basename(out_ndjson_path))
                rec.setdefault("_batch_timestamp", ts)
                rec.setdefault("_batch_input", in_stem)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # Non-fatal: continue even if archive append fails
        pass

    rows = []
    for r in results:
        if "_raw" in r:
            rows.append({
                "company_name": r.get("company_name"),
                "address": r.get("address"),
                "website": r.get("website"),
                "phone": r.get("phone"),
                "score_total": None,
                "recommendation": None,
                "sales_one_liner": None,
                "sales_one_liner_german": None,
                "company_type": None,
                "industry_focus": None,
                "machine_types": None,
                "relevance": None,
                "observations": None,
                "contact_person_notes": None,
                "contact_1_name": None,
                "contact_1_title": None,
                "contact_1_email": None,
                "contact_1_phone": None,
                "contact_1_confidence": None,
                "contact_1_url": None,
                "contact_count": None,
                "sources": None,
                "raw": r["_raw"][:1000],
            })
            continue

        d = r.get("derived", {}) or {}
        top_company_type = r.get("company_type") or d.get("company_type")
        top_industry_focus = r.get("industry_focus") or d.get("industry_focus", [])
        top_machine_types = r.get("machine_types") or d.get("machine_types", [])
        score_total = r.get("score_total")
        if score_total is None:
            sb = r.get("score_breakdown") or {}
            if isinstance(sb, dict):
                score_total = sb.get("total")

        # Contact extraction flattening (first best contact if present)
        contacts = r.get("contact_persons", []) or []
        c1 = contacts[0] if contacts else {}
        rows.append({
            "company_name": r.get("company_name"),
            "address": r.get("address"),
            "website": r.get("website"),
            "phone": r.get("phone"),
            "score_total": score_total,
            "recommendation": r.get("recommendation"),
            "sales_one_liner": r.get("sales_one_liner"),
            "sales_one_liner_german": r.get("sales_one_liner_german"),
            "company_type": top_company_type,
            "industry_focus": "; ".join(top_industry_focus or []),
            "machine_types": "; ".join(top_machine_types or []),
            "relevance": r.get("relevance_dach") or r.get("relevance"),
            "observations": r.get("observations"),
            "contact_person_notes": r.get("contact_person_notes"),
            "contact_1_name": c1.get("name"),
            "contact_1_title": c1.get("title"),
            "contact_1_email": c1.get("email"),
            "contact_1_phone": c1.get("phone"),
            "contact_1_confidence": c1.get("confidence"),
            "contact_1_url": c1.get("page_url"),
            "contact_count": len(contacts),
            "sources": "; ".join(r.get("sources", [])),
        })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_csv_path, index=False)

    # Append to archive CSV (with batch metadata)
    try:
        out_df_with_meta = out_df.copy()
        out_df_with_meta["_batch_file"] = os.path.basename(out_csv_path)
        out_df_with_meta["_batch_timestamp"] = ts
        out_df_with_meta["_batch_input"] = in_stem
        header = not os.path.exists(archive_csv_path)
        out_df_with_meta.to_csv(archive_csv_path, mode="a", index=False, header=header)
    except Exception:
        pass

    # Move per-batch files into their designated subfolders for the dashboard/table
    try:
        dash_target = OUTPUT_DASHBOARD_DIR / os.path.basename(out_ndjson_path)
        table_target = OUTPUT_TABLE_DIR / os.path.basename(out_csv_path)
        # Use replace to move/overwrite if same-named file exists from prior runs
        shutil.replace(out_ndjson_path, dash_target)
        shutil.replace(out_csv_path, table_target)
        out_ndjson_path = str(dash_target)
        out_csv_path = str(table_target)
    except Exception:
        # Non-fatal; files still exist at original locations
        pass

    print(
        f"Wrote {out_ndjson_path} and {out_csv_path}\n"
        f"Appended to {archive_ndjson_path} and {archive_csv_path}"
    )


if __name__ == "__main__":
    asyncio.run(run())
