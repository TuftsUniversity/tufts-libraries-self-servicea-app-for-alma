#!/bin/bash
# ===========================================================
# Tufts Libraries - Barcode Report Automation
# ===========================================================

set -euo pipefail
PATH=/usr/local/bin:/usr/bin:/bin

WORKDIR="/home/libraryapps"
DATESTAMP=$(date +%Y%m%d%H%M%S)
CSVFILE="$WORKDIR/barcode_status_${DATESTAMP}.csv"
EMAIL_TO="tulips@tufts.edu"
EMAIL_SUBJECT="Barcode Status Report - $(date '+%Y-%m-%d %H:%M')"

# --- Run Python script ---
python3 /home/libraryapps/testAlmaInventoryApp.py \
  --url "https://stacked-gantt-stage.library.tufts.edu/barcodeReport.html" \
  --barcode "39090015942614" > "$CSVFILE"

# --- Email result ---
if [ -x /usr/sbin/sendmail ]; then
  {
    echo "To: $EMAIL_TO"
    echo "Subject: $EMAIL_SUBJECT"
    echo "MIME-Version: 1.0"
    echo "Content-Type: text/plain; charset=UTF-8"
    echo
    echo "Attached is the barcode status result."
    echo
    cat "$CSVFILE"
  } | /usr/sbin/sendmail -t
elif command -v mail >/dev/null 2>&1; then
  mail -s "$EMAIL_SUBJECT" "$EMAIL_TO" < "$CSVFILE"
else
  echo "No mailer found. CSV at $CSVFILE"
fi

# --- Cleanup old reports ---
find "$WORKDIR" -type f -name "barcode_status_*.csv" -mtime +7 -delete 2>/dev/null || true
