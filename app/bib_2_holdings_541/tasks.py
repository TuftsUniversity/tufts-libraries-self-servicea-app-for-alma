import os
import smtplib
from email.message import EmailMessage
from datetime import datetime

from .bib_2_holdings_541 import Bib2Holdings541

RESULTS_DIR = os.getenv("BIB2HOLDINGS541_RESULTS_DIR", "/tmp/bib2holdings541_results")

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_FROM = os.getenv("SMTP_FROM", "noreply-library@tufts.edu")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://tufts-libraries-alma-self-service-app.library.tufts.edu/")  # e.g. https://selfservice.library.tufts.edu

from typing import Optional

import subprocess

def _send_email(...):
    ...
    # Instead of smtplib.SMTP(...)
    subprocess.run(
        ["/usr/sbin/sendmail", "-t", "-oi"],
        input=msg.as_bytes(),
        check=True,
    )

import os
import shutil
import socket
import subprocess
import smtplib
from email.message import EmailMessage
from typing import Optional

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_FROM = os.getenv("SMTP_FROM", "noreply-library@tufts.edu")

import os
import shutil
import socket
import subprocess
import smtplib
from email.message import EmailMessage
from typing import Optional

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_FROM = os.getenv("SMTP_FROM", "noreply-library@tufts.edu")

def _send_email(
    to_addr: str,
    subject: str,
    body: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_name: str = "results.zip",
):
    """
    Send email in a way that works with Exim configured as an MUA wrapper
    (i.e., no SMTP daemon listening on localhost:25).

    Preferred path: /usr/sbin/sendmail (Exim provides this interface).
    Fallback path: direct SMTP using SMTP_HOST/SMTP_PORT.
    """

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
            filename=attachment_name,
        )

    # 1) Preferred: local sendmail submission (works with Exim mua_wrapper)
    sendmail_path = shutil.which("sendmail") or "/usr/sbin/sendmail"
    if os.path.exists(sendmail_path) and os.access(sendmail_path, os.X_OK):
        try:
            # -t: read recipients from headers
            # -oi: ignore single-dot line termination
            subprocess.run(
                [sendmail_path, "-t", "-oi"],
                input=msg.as_bytes(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode("utf-8", errors="replace")
            stdout = (e.stdout or b"").decode("utf-8", errors="replace")
            raise RuntimeError(
                f"sendmail failed (rc={e.returncode}). stderr={stderr.strip()} stdout={stdout.strip()}"
            )

    # 2) Fallback: direct SMTP
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.send_message(msg)
    except (OSError, smtplib.SMTPException, socket.error) as e:
        raise RuntimeError(f"SMTP send failed via {SMTP_HOST}:{SMTP_PORT}: {e}")

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
