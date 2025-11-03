#!/usr/bin/env python3
"""
Headless flow:
 1. Go to barcodeReport.html
 2. Click #addb (opens jQuery UI dialog)
 3. Type into #barcode
 4. Click "Add Barcode" button in dialog
 5. Wait until a row with [barcode="<BARCODE>"] has non-empty .status
 6. Scrape the row and print CSV to stdout

Relies on page structure:
 - #addb toolbar link
 - #dialog-form popup with input#barcode
 - result table #restable
"""

import argparse
import asyncio
import csv
import sys
from playwright.async_api import async_playwright


async def run_barcode(url: str, barcode: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})

        # Go to page
        print(f"Opening {url} ...", file=sys.stderr)
        await page.goto(url, wait_until="networkidle")

        # Click "Add Barcode"
        await page.wait_for_selector("#addb", timeout=30_000)
        await page.click("#addb")

        # Type barcode
        await page.wait_for_selector("#dialog-form", timeout=30_000, state="visible")
        await page.wait_for_selector("#barcode", timeout=30_000, state="visible")
        await page.fill("#barcode", barcode)

        # Click Add Barcode button in dialog
        await page.wait_for_selector(".ui-dialog-buttonpane .ui-button:not([disabled])", timeout=30_000)
        await page.keyboard.press("Enter")
        try:
            await page.click(".ui-dialog-buttonpane .ui-button:not([disabled])")
        except Exception:
            pass  # sometimes Enter is enough

        # Wait for row to appear and get populated
        row_selector = f'#restable tr.datarow[barcode="{barcode}"]'
        await page.wait_for_selector(row_selector, timeout=120_000)

        await page.wait_for_function(
            """sel => {
                const row = document.querySelector(sel);
                if (!row) return false;
                const td = row.querySelector('td.status');
                return td && td.textContent.trim().length > 0;
            }""",
            arg=row_selector,
            timeout=180_000,
        )

        # Extract result
        result = await page.evaluate(
            """sel => {
                const row = document.querySelector(sel);
                const pick = cls => (row.querySelector(`td.${cls}`)?.textContent || '').trim();
                const barcodeVal = row.getAttribute('barcode') || '';

                const data = {
                    barcode: barcodeVal,
                    location_code: pick('location_code'),
                    call_number: pick('call_number'),
                    volume: pick('volume'),
                    title: pick('title'),
                    process: pick('process'),
                    temp_location: pick('temp_location'),
                    bib_supp: pick('bib_supp'),
                    hold_supp: pick('hold_supp'),
                    record_num: pick('record_num'),
                    status: pick('status'),
                    status_msg: pick('status_msg'),
                    timestamp: pick('timestamp')
                };
                return data;
            }""",
            row_selector,
        )

        await browser.close()

        # Output as CSV
        writer = csv.DictWriter(sys.stdout, fieldnames=result.keys())
        writer.writeheader()
        writer.writerow(result)


def main():
    parser = argparse.ArgumentParser(description="Submit barcode and scrape results.")
    parser.add_argument("--url", required=True, help="Full URL to barcodeReport.html page")
    parser.add_argument("--barcode", required=True, help="Barcode to submit")
    args = parser.parse_args()

    try:
        asyncio.run(run_barcode(args.url, args.barcode))
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
