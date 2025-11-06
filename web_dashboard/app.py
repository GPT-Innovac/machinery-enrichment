from flask import Flask, render_template, jsonify
import json
import pandas as pd
import os
from pathlib import Path
from typing import List

app = Flask(__name__)

# Path to data files
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
# Fixed locations for batch outputs
DASHBOARD_DIR = DATA_DIR / "output" / "dashboard"
TABLE_DIR = DATA_DIR / "output" / "table"

def _glob_sorted(paths: List[Path]) -> List[Path]:
    return sorted([p for p in paths if p.is_file()], key=lambda p: p.stat().st_mtime)

def _get_ndjson_dirs() -> List[Path]:
    """Directories to scan for NDJSON (cards). Defaults to data/output/dashboard + any RESULT_DASH_DIRS."""
    dirs: List[Path] = [DASHBOARD_DIR]
    extra = os.environ.get("RESULT_DASH_DIRS", "").strip()
    if extra:
        for raw in extra.split(","):
            p = Path(raw).expanduser()
            if p.exists() and p.is_dir():
                dirs.append(p)
    # de-dup
    seen, out = set(), []
    for d in dirs:
        if str(d) not in seen:
            out.append(d)
            seen.add(str(d))
    return out


def _get_csv_dirs() -> List[Path]:
    """Directories to scan for CSV (table). Defaults to data/output/table + any RESULT_TABLE_DIRS."""
    dirs: List[Path] = [TABLE_DIR]
    extra = os.environ.get("RESULT_TABLE_DIRS", "").strip()
    if extra:
        for raw in extra.split(","):
            p = Path(raw).expanduser()
            if p.exists() and p.is_dir():
                dirs.append(p)
    seen, out = set(), []
    for d in dirs:
        if str(d) not in seen:
            out.append(d)
            seen.add(str(d))
    return out

def load_enrichment_data():
    """Load and aggregate ALL enrichment results in data/ (multiple batches)."""
    try:
        detailed_data: list = []
        summary_frames: list[pd.DataFrame] = []

        # Use fixed dashboard/table directories (with optional env overrides)
        ndjson_dirs = _get_ndjson_dirs()
        ndjson_files: List[Path] = []
        for d in ndjson_dirs:
            # recursive to include data/output/, etc.
            ndjson_files += list(d.rglob("*.ndjson"))
        ndjson_files = _glob_sorted(ndjson_files)
        for p in ndjson_files:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            obj = json.loads(line)
                            obj["_batch_file"] = p.name
                            detailed_data.append(obj)
            except Exception as e:
                print(f"Warning: failed reading {p}: {e}")

        # Aggregate all CSV files (exclude input.csv) from table directories
        csv_dirs = _get_csv_dirs()
        csv_files: List[Path] = []
        for d in csv_dirs:
            csv_files += [p for p in d.rglob("*.csv") if p.name != "input.csv"]
        csv_files = _glob_sorted(csv_files)
        for p in csv_files:
            try:
                df = pd.read_csv(p)
                df["_batch_file"] = p.name
                summary_frames.append(df)
            except Exception as e:
                print(f"Warning: failed reading {p}: {e}")

        summary_data = pd.concat(summary_frames, ignore_index=True) if summary_frames else None
        return detailed_data, summary_data

    except Exception as e:
        print(f"Error loading data: {e}")
        return [], None

@app.route('/')
def dashboard():
    """Main dashboard page"""
    detailed_data, summary_data = load_enrichment_data()
    
    # Calculate summary statistics
    stats = {
        'total_companies': len(detailed_data),
        'high_priority': len([d for d in detailed_data if d.get('recommendation') == 'yes']),
        'medium_priority': len([d for d in detailed_data if d.get('recommendation') == 'maybe']),
        'low_priority': len([d for d in detailed_data if d.get('recommendation') == 'no']),
        'avg_score': round(sum(d.get('score_total', 0) for d in detailed_data) / len(detailed_data) if detailed_data else 0, 1)
    }
    
    return render_template('dashboard.html', 
                         companies=detailed_data, 
                         stats=stats)

@app.route('/table')
def table_view():
    """Tabular view of results using the flattened CSV output if available."""
    detailed_data, summary_data = load_enrichment_data()
    # Prefer CSV for a concise table; if not present, fall back to constructing from detailed JSON
    rows = []
    if summary_data is not None:
        rows = summary_data.fillna("").to_dict(orient='records')
    else:
        for r in detailed_data:
            d = r.get('derived', {}) or {}
            sb = r.get('score_breakdown') or {}
            contacts = r.get('contact_persons') or []
            c1 = contacts[0] if contacts else {}
            rows.append({
                'company_name': r.get('company_name',''),
                'address': r.get('address',''),
                'website': r.get('website',''),
                'phone': r.get('phone',''),
                'score_total': sb.get('total', ''),
                'recommendation': r.get('recommendation',''),
                'relevance': r.get('relevance_dach') or r.get('relevance',''),
                'company_type': r.get('company_type') or d.get('company_type',''),
                'industry_focus': "; ".join(r.get('industry_focus') or d.get('industry_focus', []) or []),
                'machine_types': "; ".join(r.get('machine_types') or d.get('machine_types', []) or []),
                'sales_one_liner': r.get('sales_one_liner',''),
                'sales_one_liner_german': r.get('sales_one_liner_german',''),
                'contact_1_name': c1.get('name') or '',
                'contact_1_title': c1.get('title') or '',
                'contact_1_email': c1.get('email') or '',
                'contact_1_phone': c1.get('phone') or '',
                'contact_1_confidence': c1.get('confidence') if c1.get('confidence') is not None else '',
                'contact_1_url': c1.get('page_url') or '',
                'contact_count': len(contacts),
            })
    return render_template('table.html', rows=rows)

@app.route('/api/companies')
def api_companies():
    """API endpoint for company data"""
    detailed_data, _ = load_enrichment_data()
    return jsonify(detailed_data)

@app.route('/company/<int:company_id>')
def company_detail(company_id):
    """Detailed view of a specific company"""
    detailed_data, _ = load_enrichment_data()
    
    if 0 <= company_id < len(detailed_data):
        company = detailed_data[company_id]
        return render_template('company_detail.html', company=company, company_id=company_id)
    else:
        return "Company not found", 404

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8080)
