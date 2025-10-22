# Standard library
import io
import os
import re
import time
import zipfile
from io import BytesIO
import xml.etree.cElementTree as et

# Third-party
import requests
import pymarc as pym
from flask import send_file
from dotenv import load_dotenv

# Load environment from repo root (and current)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_dotenv()


class Bib2Holdings541:
    """Always completes and returns a ZIP file, logging all failures explicitly."""

    def __init__(self, file_stream):
        self.file_stream = file_stream

        # Environment
        self.prod_bib_api_key = os.getenv("prod_bib_api_key")
        self.analytics_api_key = os.getenv("analytics_api_key")
        self.analytics_url = os.getenv("analytics_url")
        self.bib_url = os.getenv("bib_url")

        self.headers = {"Content-Type": "application/xml"}

        self.errorCount = 0
        self.successCount = 0

        # In-memory outputs
        self.count_file = io.BytesIO()
        self.output_file = io.BytesIO()
        self.error_file = io.BytesIO()

        try:
            self.output_file.write(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><holdings>'.encode("utf-8")
            )
        except Exception:
            pass

    # ---------- helpers ----------
    def _writetxt(self, buf: BytesIO, text: str, end_newline: bool = True):
        try:
            if text is None:
                text = ""
            if end_newline and not text.endswith("\n"):
                text += "\n"
            buf.write(text.encode("utf-8", errors="replace"))
        except Exception as e:
            import sys
            print(f"[LOGGING FAILURE] {e}", file=sys.stderr, flush=True)

    def log_err(self, text: str):
        self._writetxt(self.error_file, text)

    def log_count(self, text: str):
        self._writetxt(self.count_file, text)

    def _read_mms_list(self):
        ids = []
        try:
            self.file_stream.seek(0)
            for line in self.file_stream:
                try:
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if line:
                        ids.append(line)
                except Exception as e:
                    self.log_err(f"Failed to read a line from input: {e}")
                    self.errorCount += 1
        except Exception as e:
            self.log_err(f"Failed to read MMS list: {e}")
            self.errorCount += 1
        return ids

    # ---------- main ----------
    def process(self):
        try:
            mappings = self.getLocations()
            bibList = self._read_mms_list()
            self.log_count(f"Input MMS IDs: {len(bibList)}")

            for mms_id in bibList:
                try:
                    self._process_single_mms(mms_id, mappings)
                    self.log_count(f"Completed MMS {mms_id} with {self.errorCount} errors so far")
                except Exception as e:
                    self.log_err(f"[CRITICAL] MMS {mms_id} failed unexpectedly: {e}")
                    self.errorCount += 1
                    continue

            self.log_count(f"Records successfully updated: {self.successCount}")
            self.log_count(f"Errors: {self.errorCount}")

        except Exception as e:
            self.log_err(f"Top-level failure: {e}")
            self.errorCount += 1

        finally:
            return self._finalize_zip("rollup_files.zip")

    # ---------- per-record ----------
    def _process_single_mms(self, mms_id: str, mappings: dict):
        try:
            bib_url = f"{self.bib_url}{mms_id}?apikey={self.prod_bib_api_key}"
            holdings_url = f"{self.bib_url}{mms_id}/holdings?apikey={self.prod_bib_api_key}"
        except Exception as e:
            self.log_err(f"MMS {mms_id}: URL build error: {e}")
            self.errorCount += 1
            return

        try:
            bib_resp = requests.get(bib_url, timeout=30)
            bib_str = bib_resp.content.decode("utf-8", errors="replace")
        except Exception as e:
            self.log_err(f"MMS {mms_id}: bib fetch failed: {e}")
            self.errorCount += 1
            return

        if re.search(r"<errorsExist>true</errorsExist>", bib_str or ""):
            self.log_err(f"MMS {mms_id}: not found in system")
            self.errorCount += 1
            return

        try:
            holds_resp = requests.get(holdings_url, timeout=30)
            holds_str = holds_resp.content.decode("utf-8", errors="replace")
        except Exception as e:
            self.log_err(f"MMS {mms_id}: holdings list fetch failed: {e}")
            self.errorCount += 1
            return

        m = re.search(r'holdings\s+total_record_count="(\d+)"', holds_str or "")
        total_holdings = int(m.group(1)) if m else 0
        if total_holdings == 0:
            self.log_err(f"MMS {mms_id}: no holdings")
            self.errorCount += 1
            return

        try:
            bib_arr = pym.parse_xml_to_array(io.StringIO(bib_str))
        except Exception as e:
            self.log_err(f"MMS {mms_id}: bib parse error: {e}")
            self.errorCount += 1
            return

        try:
            root_list = et.ElementTree(et.fromstring(holds_str)).getroot()
        except Exception as e:
            self.log_err(f"MMS {mms_id}: holdings XML parse error: {e}")
            self.errorCount += 1
            return

        holdings_xml_parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><holdings>']
        for h in root_list.findall(".//holding"):
            hid = (h.findtext("holding_id") or "").strip()
            if not hid:
                continue
            try:
                rec = requests.get(f"{self.bib_url}{mms_id}/holdings/{hid}?apikey={self.prod_bib_api_key}", timeout=30)
                hx = rec.content.decode("utf-8", errors="replace").replace('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "")
                holdings_xml_parts.append(hx)
            except Exception as e:
                self.log_err(f"MMS {mms_id}: failed to fetch holding {hid}: {e}")
                self.errorCount += 1
        holdings_xml_parts.append("</holdings>")

        try:
            holdings_root = et.ElementTree(et.fromstring("".join(holdings_xml_parts))).getroot()
        except Exception as e:
            self.log_err(f"MMS {mms_id}: consolidated holdings parse error: {e}")
            self.errorCount += 1
            return

        try:
            bib_record = bib_arr[0]
        except Exception as e:
            self.log_err(f"MMS {mms_id}: bib record missing: {e}")
            self.errorCount += 1
            return

        for f541 in bib_record.get_fields("541"):
            try:
                found541 = False
                sub3 = (f541.get_subfields("3") or [""])[0]
                loc_match = re.search(
                    r"^(.+Library|TISCH|HHSL|MUSIC|GINN|VET|Tisch|Ginn|Music|Vet|Hirsh|EUR)\s*(.+)?(?:\s+print)?\s+copy\b[:\-]?",
                    (sub3 or "").strip(),
                    re.IGNORECASE,
                )
                library_541 = (loc_match.group(1).strip() if loc_match else "")

                libmap = {
                    "Tisch Library": "TISCH", "TISCH": "TISCH", "Tisch": "TISCH",
                    "Ginn Library": "GINN", "GINN": "GINN", "Ginn": "GINN",
                    "Lilly Music Library": "MUSIC", "MUSIC": "MUSIC", "Music": "MUSIC",
                    "W. Van Alan Clark, Jr. Library": "SMFA", "SMFA": "SMFA",
                    "Webster Family Library": "VET", "VET": "VET", "Vet": "VET",
                    "Hirsch Health Sciences Library": "HIRSH", "Hirsh Health Sciences Library": "HIRSH", "HHSL": "HIRSH", "Hirsh": "HIRSH",
                    "EUR": "Talloires"
                }
                library = libmap.get(library_541, "")

                try:
                    location_541 = (loc_match.group(2) or "") if loc_match else ""
                    location_541 = location_541.encode("utf-8", "replace").decode("utf-8")
                except Exception:
                    location_541 = ""

                countList = []
                for full_holding in holdings_root.findall("holding"):
                    holding_id = (full_holding.findtext("holding_id") or "").strip()
                    if not holding_id:
                        continue
                    try:
                        marc_h = pym.parse_xml_to_array(io.StringIO(et.tostring(full_holding).decode("utf-8", errors="replace")))[0]
                    except Exception as e:
                        self.log_err(f"MMS {mms_id} holding {holding_id}: MARC parse error {e}")
                        self.errorCount += 1
                        continue

                    full_holding_xml = et.tostring(full_holding)
                    foundLocation = False
                    location_code = ""
                    from_current_holding = False

                    # --- Begin rewritten location and update logic ---
                    foundLocation = False
                    location_code = ""
                    from_current_holding = False

                    # 1. Try to find a location match using mappings
                    if location_541 and library:
                        mapping_dict = mappings.get(library, {})
                        if mapping_dict:
                            for desc, code in mapping_dict.items():
                                if (location_541 or "").lower() in (desc or "").lower():
                                    location_code = (code or "").strip()
                                    foundLocation = True
                                    break
                            if not foundLocation:
                                self.log_err(f"MMS {mms_id} holding {holding_id}: no mapping match for location '{location_541}' in library '{library}'")
                                self.errorCount += 1
                        else:
                            self.log_err(f"MMS {mms_id} holding {holding_id}: no mappings found for library '{library}'")
                            self.errorCount += 1
                    else:
                        self.log_err(f"MMS {mms_id} holding {holding_id}: missing or invalid library/location_541 context")
                        self.errorCount += 1

                    # 2. Fallback: look for match in existing 852 field
                    if not foundLocation:
                        b_fields = marc_h.get_fields("852") or []
                        if not b_fields:
                            self.log_err(f"MMS {mms_id} holding {holding_id}: no 852 field found")
                            self.errorCount += 1
                        else:
                            b_sub_b = b_fields[0].get_subfields("b") or []
                            b_code = (b_sub_b[0] if b_sub_b else "").strip().upper()
                            lib_norm = (library or "").strip().upper()

                            if b_code == lib_norm and (lib_norm not in countList):
                                c_sub = b_fields[0].get_subfields("c") or []
                                location_code = (c_sub[0] if c_sub else "").strip()
                                countList.append(lib_norm)
                                foundLocation = True
                                from_current_holding = True
                            else:
                                self.log_err(f"MMS {mms_id} holding {holding_id}: 852 mismatch - b_code='{b_code}' lib_norm='{lib_norm}'")
                                self.errorCount += 1

                    # 3. If found a location, check for update conditions
                    if foundLocation:
                        b_fields = marc_h.get_fields("852") or []
                        c_val = ""
                        if b_fields:
                            c_subs = b_fields[0].get_subfields("c") or []
                            c_val = (c_subs[0] if c_subs else "").strip()

                        should_update = from_current_holding or (c_val == (location_code or "").strip())

                        if should_update:
                            found541 = True
                            ok = self.update_holding(marc_h, holding_id, full_holding_xml, f541, mms_id)
                            if ok:
                                self.successCount += 1
                                break
                            else:
                                self.log_err(f"MMS {mms_id} holding {holding_id}: update_holding failed")
                                self.errorCount += 1
                        else:
                            self.log_err(f"MMS {mms_id} holding {holding_id}: location '{c_val}' did not match '{location_code}', skipping update")
                            self.errorCount += 1

                    # 4. If still not found, log explicitly
                    if not foundLocation:
                        self.log_err(f"MMS {mms_id} holding {holding_id}: no valid location resolved from mapping or 852")
                        self.errorCount += 1
                    # --- End rewritten section ---

            except Exception as e:
                self.log_err(f"MMS {mms_id}: 541 processing error {e}")
                self.errorCount += 1

    # ---------- helpers ----------
    def update_holding(self, holding, holding_id, full_holding_string, five_forty_one, mms_id):
        try:
            holding.add_field(five_forty_one)
            updated_record = pym.record_to_xml(holding).decode("utf-8", errors="replace")
            full_holding_text = full_holding_string.decode("utf-8", errors="replace")
            full_updated_holding = re.sub(r"<record>(.+)</record>", updated_record, full_holding_text, flags=re.DOTALL).replace('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "")

            try:
                resp = requests.put(f"{self.bib_url}{mms_id}/holdings/{holding_id}?apikey={self.prod_bib_api_key}", data=full_updated_holding, headers=self.headers, timeout=60)
            except Exception as e:
                self.log_err(f"MMS {mms_id} holding {holding_id}: PUT failed {e}")
                self.errorCount += 1
                return False

            time.sleep(2)
            resp_text = resp.content.decode("utf-8", errors="replace") if hasattr(resp, "content") else ""
            if re.search(r"<errorsExist>true</errorsExist>", resp_text or ""):
                self.log_err(f"MMS {mms_id} holding {holding_id}: Alma writeback error")
                self.errorCount += 1
                return False
            else:
                try:
                    chunk = f"<MMS_ID_{mms_id}>{full_updated_holding}</MMS_ID_{mms_id}>"
                    self.output_file.write(chunk.encode("utf-8", errors="replace"))
                except Exception as e:
                    self.log_err(f"MMS {mms_id}: failed to append updated XML {e}")
                return True
        except Exception as e:
            self.log_err(f"MMS {mms_id} holding {holding_id}: update_holding exception {e}")
            self.errorCount += 1
            return False

    def getLocations(self):
        url = f"{self.analytics_url}{self.analytics_api_key}"
        limit = "&limit=1000"
        fmt = "&format=xml"
        path = "&path=%2Fshared%2FTufts+University%2FReports%2FCataloging%2FAdding+541+to+Holdings+Records%2FLocation+Name-Location+Code"

        try:
            rep = requests.get(url + fmt + path + limit, timeout=60)
            tree = et.ElementTree(et.fromstring(rep.content))
            root = tree.getroot()
        except Exception as e:
            self.log_err(f"Location mappings fetch failed: {e}")
            self.errorCount += 1
            return {}

        out = {}
        try:
            for el in root.iter():
                if re.match(r".*Row", el.tag or ""):
                    lib = code = desc = ""
                    for sub in el.iter():
                        tag = sub.tag or ""
                        if re.match(r".*Column1", tag):
                            lib = sub.text
                        elif re.match(r".*Column2", tag):
                            code = sub.text
                        elif re.match(r".*Column3", tag):
                            desc = sub.text
                    if lib:
                        out.setdefault(lib, {})
                        out[lib][desc] = code
        except Exception as e:
            self.log_err(f"Location mapping parse error: {e}")
            self.errorCount += 1
        return out

    def _finalize_zip(self, name: str):
        try:
            self.output_file.seek(0, os.SEEK_END)
            self.output_file.write(b"</holdings>")
        except Exception:
            pass
        for f in [self.count_file, self.output_file, self.error_file]:
            try:
                f.seek(0)
            except Exception:
                pass

        buf = io.BytesIO()
        try:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                try:
                    z.writestr("Count File.txt", self.count_file.getvalue())
                except Exception:
                    z.writestr("Count File.txt", b"(unavailable)")
                try:
                    z.writestr("Errors.txt", self.error_file.getvalue())
                except Exception:
                    z.writestr("Errors.txt", b"(unavailable)")
                try:
                    z.writestr("Output File.xml", self.output_file.getvalue())
                except Exception:
                    z.writestr("Output File.xml", b"(unavailable)")
            buf.seek(0)
        except Exception:
            # Fallback: minimal ZIP containing an error note
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("Errors.txt", b"ZIP assembly failed; see server logs.")
            buf.seek(0)

        # Always return a ZIP attachment
        return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=name)
