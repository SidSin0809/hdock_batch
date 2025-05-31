# hdock_batch
Python utility that bulk-submits receptor/ligand pairs to the HDOCK server, tracks job tokens


[HDOCK Web Site](http://hdock.phys.hust.edu.cn/)

---

##  Key Features
* **CSV-driven workflow** – list any number of docking jobs in a spreadsheet.  
* **Ligand auto-detection** – accepts either a FASTA-formatted sequence **or** a file path and chooses the correct upload method automatically. :contentReference[oaicite:0]{index=0}  
* **Optional binding-site specification** – fill receptor residues if you need site-guided docking.
* **Concurrency** – `-j/--jobs` flag controls how many headless Chromium instances run in parallel.  
* **Live progress logger** – every finished job is echoed to the console and appended to `run-log.csv` with timestamp, job-name, token, and result URL.
* **Lightweight** – only needs *pandas* and *playwright*; runs on Linux, macOS, or Windows with Python 3.8+.  

---

##  Input CSV Schema

| Column (any casing) | Purpose | Required? | Example |
|---------------------|---------|-----------|---------|
| `receptor_pdb`      | Path to receptor PDB file             | **Yes** | `data/1abc.pdb` |
| `ligand_fasta` / `ligand_path` / `ligand_seq` / `ligand_pdb` / `ligand_file` / `ligand` | Either a FASTA sequence **or** a file path for the ligand | **Yes** | `>pep\nACDEFG…` or `lig/peptide.pdb` |
| `receptor_site_residues` | Comma-separated residue numbers (optional) | No | `45,79,102` |
| `jobname` / `name`  | Friendly job label (optional) | No | `ABL1_vs_pep` |
| `email`             | Address for HDOCK notification (optional) | No | `you@example.com` |

Only the receptor column **and at least one ligand column** are mandatory. Extra columns are ignored.

---

##  Quick Start

```bash
# 1. Clone and install
git clone https://github.com/SidSin0809/hdock-batch.git
cd hdock-batch
pip install -r requirements.txt
playwright install                                      # one-time browser download

# 2. Prepare jobs.csv (see example above)
# 3. Run
python hdock_batch.py jobs.csv --out ./hdock_logs -j 4

```
##  Output Files
run-log.csv – cumulative log with columns:
row,timestamp,jobname,token,result_url,ok,error

Docking reports – HDOCK itself hosts your result URLs; the script merely captures them.

##  Options
| Flag         | Default        | Description                  |
| ------------ | -------------- | ---------------------------- |
| `csv`        | —              | Input job list (see schema)  |
| `--out`      | `./hdock_logs` | Directory for `run-log.csv`  |
| `-j, --jobs` | `1`            | Concurrent browser instances |


## Troubleshooting
| Symptom                                         | Likely Cause                                                                                                                                                                                        | Fix                                                                         |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `RuntimeError: File did not attach…`            | Wrong path in CSV                                                                                                                                                                                   | Check file path; use absolute or relative to script                         |
| `submission_failed` in log yet result URL works | HDOCK sometimes returns a URL without `token=`; script falls back to last path element for token. If that element is shorter than 8 chars the `ok` flag stays *False* – but the URL is still valid. |                                                                             |
| Playwright timeouts                             | Slow network / server busy                                                                                                                                                                          | Increase browser timeout by editing the `page.goto` line, or lower `--jobs` |
