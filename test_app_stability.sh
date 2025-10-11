#!/bin/sh
# ===========================================================
# Tufts Libraries - Application Endpoint Status Report
# ===========================================================
# Sends an HTML email report summarizing the status of key
# application endpoints. Designed for cron execution.
# ===========================================================

set -eu
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# --- Configuration ---
EMAIL_TO="tulips@tufts.edu"
EMAIL_SUBJECT="Application Endpoint Status Report"
DATESTAMP=$(date +%Y%m%d%H%M%S)
WORKDIR="/home/libraryapps"
LOGFILE="$WORKDIR/app_status_${DATESTAMP}.txt"
HTMLFILE="$WORKDIR/app_status_${DATESTAMP}.html"

APPS="
Self Service Portal Prod|https://tufts-libraries-alma-self-service-app.library.tufts.edu|https://tufts.box.com/s/s68lb0ngiezz21f1vx6e0x5thooc2sqj
Self Service Portal Staging|https://tufts-libraries-alma-self-service-stage-app.library.tufts.edu|https://tufts.box.com/s/s68lb0ngiezz21f1vx6e0x5thooc2sqj
Alma Inventory App Prod|https://tufts-libraries-alma-inventory-app.library.tufts.edu|https://tufts.box.com/s/dmrsnm1exoodb0n4hy6gps17w80acqyh
Alma Inventory App Staging|https://tufts-libraries-alma-inventory-app-stage.library.tufts.edu|https://tufts.box.com/s/dmrsnm1exoodb0n4hy6gps17w80acqyh
Alternative Endpoint to Alma Inventory App Prod|https://stacked-gantt.library.tufts.edu|https://tufts.box.com/s/h1cw3py0ux44e309boi6f85671u52eyt
Alternative Endpoint to Alma Inventory App Staging|https://stacked-gantt-stage.library.tufts.edu/barcodeReport.html|https://tufts.box.com/s/dmrsnm1exoodb0n4hy6gps17w80acqyh
Alma Media Equipment Webhook Listener Prod|https://stacked-gantt.library.tufts.edu|https://tufts.box.com/s/h1cw3py0ux44e309boi6f85671u52eyt
Alma Media Equipment Webhook Listener Staging|https://stacked-gantt-stage.library.tufts.edu|https://tufts.box.com/s/h1cw3py0ux44e309boi6f85671u52eyt
LTS Stacked Gantt App for JIRA Prod|https://lts-project-jira.library.tufts.edu/|
LTS Stacked Gantt App for JIRA Staging|https://lts-project-jira-stage.library.tufts.edu|
"

# --- Initialize Logs ---
{
  echo "Endpoint status check ($(date))"
  echo "Host: $(hostname)"
  echo "----------------------------------------"
} > "$LOGFILE"

{
  echo "<html><body>"
  echo "<h3>Endpoint status check ($(date)) on $(hostname)</h3>"
  echo "<table border='1' cellpadding='5' cellspacing='0'>"
  echo "<tr><th>Application</th><th>URL</th><th>Status</th><th>Documentation</th></tr>"
} > "$HTMLFILE"

# --- Check Each Endpoint ---
IFS='
'
for line in $APPS; do
  name=$(echo "$line" | cut -d'|' -f1)
  url=$(echo "$line" | cut -d'|' -f2)
  help_url=$(echo "$line" | cut -d'|' -f3)

  set +e
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  rc=$?
  set -e

  if [ $rc -ne 0 ] || [ -z "$status" ]; then
    status="000"
  fi

  if echo "$status" | grep -Eq '^[23]'; then
    color="green"
    summary="available"
  else
    color="red"
    summary="unavailable"
  fi

  echo "The application $name at $url has status code $status and is $summary. Documentation at $help_url" >> "$LOGFILE"
  echo "<tr><td>$name</td><td><a href=\"$url\">$url</a></td><td style=\"color:$color;\">$status ($summary)</td><td><a href=\"$help_url\">Documentation</a></td></tr>" >> "$HTMLFILE"
done

# --- Finish HTML ---
echo "</table></body></html>" >> "$HTMLFILE"

# --- Send HTML Email ---
if [ -x /usr/sbin/sendmail ]; then
  {
    echo "To: $EMAIL_TO"
    echo "Subject: $EMAIL_SUBJECT"
    echo "MIME-Version: 1.0"
    echo "Content-Type: text/html"
    echo
    cat "$HTMLFILE"
  } | /usr/sbin/sendmail -t
elif command -v mail >/dev/null 2>&1; then
  # Try to send HTML with mailx/s-nail if available
  if mail -V 2>&1 | grep -q "s-nail"; then
    mail -a "Content-Type: text/html" -s "$EMAIL_SUBJECT" "$EMAIL_TO" < "$HTMLFILE"
  else
    mail -s "$EMAIL_SUBJECT" "$EMAIL_TO" < "$LOGFILE"
  fi
else
  echo "No mailer found. See $LOGFILE and $HTMLFILE"
fi

# --- Optional cleanup (keep 7 days of reports) ---
find "$WORKDIR" -type f -name "app_status_*.html" -mtime +7 -delete 2>/dev/null || true
find "$WORKDIR" -type f -name "app_status_*.txt" -mtime +7 -delete 2>/dev/null || true