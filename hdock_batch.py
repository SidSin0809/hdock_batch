#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import csv
import pathlib
import sys
import time
from typing import Dict

import pandas as pd
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PWTimeout

HDOCK_URL = "http://hdock.phys.hust.edu.cn/"

# ───────────────────────── helper functions ──────────────────────────
async def attach_file(page: Page, selector: str, file_path: pathlib.Path):
    await page.set_input_files(selector, file_path.as_posix())
    ok = await page.eval_on_selector(selector, "el => el.files.length > 0")
    if not ok:
        raise RuntimeError(f"File did not attach to {selector}")


def pick(row: Dict[str, str], *candidates) -> str:
    for c in candidates:
        if c in row and str(row[c]).strip():
            return str(row[c]).strip()
    return ""


async def fill_receptor_site(page: Page, residues: str):
    try:
        await page.click("#option1")
    except PWTimeout:
        pass
    await page.fill("input[name=sitenum1]", residues)


async def submit_one(row: Dict[str, str], idx: int, sem: asyncio.Semaphore, pw) -> Dict[str, str]:
    async with sem:
        browser: Browser = await pw.chromium.launch(headless=True)
        page: Page = await browser.new_page()
        await page.goto(HDOCK_URL, timeout=90_000)

        # receptor
        rec_path = pathlib.Path(row["receptor_pdb"]).expanduser().resolve()
        if not rec_path.exists():
            raise FileNotFoundError(f"[row {idx}] receptor_pdb not found: {rec_path}")
        await attach_file(page, "#pdbfile1", rec_path)

        # ligand autodetect fasta vs path
        ligand_raw = pick(
            row,
            "ligand_fasta",
            "ligand_path",
            "ligand_seq",
            "ligand_sequence",
            "ligand_pdb",
            "ligand_file",
            "ligand",
        ).strip()
        if not ligand_raw:
            raise ValueError(f"[row {idx}] Provide a ligand sequence or file path.")

        is_fasta_text = ligand_raw.startswith(">") or "\n" in ligand_raw
        ligand_seq = ""
        ligand_file: pathlib.Path | None = None
        if is_fasta_text and len(ligand_raw.splitlines()) >= 2:
            ligand_seq = ligand_raw
        else:
            candidate = pathlib.Path(ligand_raw).expanduser().resolve()
            if candidate.exists():
                ligand_file = candidate
            elif is_fasta_text:
                ligand_seq = ligand_raw
            else:
                raise FileNotFoundError(f"[row {idx}] ligand file not found: {candidate}")
        if ligand_file:
            await attach_file(page, "#pdbfile2", ligand_file)
        else:
            await page.fill("#fastaseq2", ligand_seq)
            await page.select_option("#ligtyp", value="protein")

        # optional binding site
        if rsite := pick(row, "receptor_site_residues"):
            await fill_receptor_site(page, rsite)

        # optional email/jobname
        jobname = pick(row, "jobname", "name")
        if mail := pick(row, "email"):
            await page.fill("#emailaddress", mail)
        if jobname:
            await page.fill("input[name=jobname]", jobname)

        # submit
        await page.click("input[name=upload]")
        await page.wait_for_load_state("networkidle")
        result_url = page.url

        # token logic (unchanged)
        token = ""
        if "token=" in result_url:
            token = result_url.split("token=")[-1]
        else:
            tail = result_url.rstrip("/").split("/")[-1]
            if tail and len(tail) >= 8:
                token = tail

        await browser.close()
        return {
            "row": idx,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "jobname": jobname,
            "token": token,
            "result_url": result_url,
            "ok": bool(token),
            "error": "" if token else "submission_failed",
        }


# ───────────────────────── orchestrator function ─────────────────────
async def main(args):
    df = pd.read_csv(args.csv).fillna("")
    df.columns = [c.lower() for c in df.columns]
    if "receptor_pdb" not in df.columns:
        sys.exit("CSV requires 'receptor_pdb' column.")
    needed = {
        "ligand_fasta",
        "ligand_path",
        "ligand_seq",
        "ligand_sequence",
        "ligand_pdb",
        "ligand_file",
        "ligand",
    }
    if not (needed & set(df.columns)):
        sys.exit("CSV needs a ligand column (sequence text or file path).")

    out_dir = pathlib.Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "run-log.csv"

    sem = asyncio.Semaphore(args.jobs)
    async with async_playwright() as pw:
        tasks = [
            submit_one(row, idx, sem, pw)
            for idx, row in enumerate(df.to_dict(orient="records"), start=1)
        ]
        total = len(tasks)
        completed = 0
        header_written = False
        for coro in asyncio.as_completed(tasks):
            res = await coro
            completed += 1
            status = "OK" if res["ok"] else "FAIL"
            print(f"{completed}/{total} | row {res['row']} | {status:<4} | {res['result_url'] if res['ok'] else '-'}")
            with open(log_file, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=res.keys())
                if not header_written:
                    writer.writeheader()
                    header_written = True
                writer.writerow(res)

    print(f"Finished. Log saved to {log_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch-submit to HDOCK with live progress.")
    parser.add_argument("csv", help="Input CSV file")
    parser.add_argument("--out", default="./hdock_logs", help="Run-log directory")
    parser.add_argument("-j", "--jobs", type=int, default=1, help="Concurrent browsers")
    asyncio.run(main(parser.parse_args()))