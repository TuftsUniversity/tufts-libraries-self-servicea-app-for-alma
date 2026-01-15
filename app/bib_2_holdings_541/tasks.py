import os
import smtplib
from email.message import EmailMessage
from datetime import datetime

from .bib_2_holdings_541 import Bib2Holdings541

RESULTS_DIR = os.getenv("BIB2HOLDINGS541_RESULTS_DIR", "/tmp/bib2holdings541_results")

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@yourdomain.edu")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")  # e.g. https://selfservice.library.tufts.edu

def _send_email(to_addr: str, subject: str, body: str, attachment_bytes: bytes | None = None, attachment_name: str = "results.zip"):
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment_bytes is not None:
        msg.add_attachment(
            attachment_bytes,
            maintype="application",
            subtype="zip",
            filename=attachment_name
        )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.send_message(msg)

def run_bib2holdings541_job(job_id: str, input_path: str, email: str, email_as_attachment: bool):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    try:
        with open(input_path, "rb") as f:
            proc = Bib2Holdings541(f)
            zip_bytes = proc.process_zip_bytes()

        # Save results so you can email a link (and/or keep an audit trail)
        out_name = f"{job_id}__rollup_files.zip"
        out_path = os.path.join(RESULTS_DIR, out_name)
        with open(out_path, "wb") as out:
            out.write(zip_bytes)

        if email_as_attachment:
            _send_email(
                to_addr=email,
                subject="Bib 2 Holdings 541: job complete",
                body="Your Bib 2 Holdings 541 job has completed. Results are attached.",
                attachment_bytes=zip_bytes,
                attachment_name="rollup_files.zip"
            )
        else:
            # you’ll expose a download route for this path (next section)
            link = f"{PUBLIC_BASE_URL}/bib_2_holdings_541/results/{out_name}" if PUBLIC_BASE_URL else out_name
            _send_email(
                to_addr=email,
                subject="Bib 2 Holdings 541: job complete",
                body=f"Your Bib 2 Holdings 541 job has completed.\n\nDownload: {link}\n"
            )

    except Exception as e:
        _send_email(
            to_addr=email,
            subject="Bib 2 Holdings 541: job failed",
            body=f"Your job failed with an error:\n\n{e}\n"
        )
        raise
    finally:
        # optional: cleanup input
        try:
            os.remove(input_path)
        except Exception:
            pass
