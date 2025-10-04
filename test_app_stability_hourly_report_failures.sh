#!/bin/sh
set -eu

EMAIL_TO="tulips@tufts.edu"
EMAIL_SUBJECT="⚠️ Application Endpoint Alert"
LOGFILE="./app_status_$(date +%Y%m%d%H%M%S).txt"
HTMLFILE="./app_status_$(date +%Y%m%d%H%M%S).html"

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

# Initialize logs
{
  echo "Endpoint failure check ($(date))"
  echo "Host: $(hostname)"
  echo "----------------------------------------"
} > "$LOGFILE"

{
  echo "<html><body>"
  echo "<h3>Endpoint failures ($(date)) on $(hostname)</h3>"
  echo "<table border='1' cellpadding='5' cellspacing='0'>"
  echo "<tr><th>Application</th><th>URL</th><th>Status</th><th>Documentation</th></tr>"
} > "$HTMLFILE"

failures=0

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

  case "$status" in
    2*|3*)
      # do nothing, success
      ;;
    *)
      failures=$((failures + 1))
      echo "The application $name at $url has status code $status and may be unavailable. Documentation at $help_url" >> "$LOGFILE"
      echo "<tr><td>$name</td><td><a href=\"$url\">$url</a></td><td style='color:red;'>$status (Unavailable)</td><td><a href=\"$help_url\">Documentation</a></td></tr>" >> "$HTMLFILE"
      ;;
  esac
done

echo "</table></body></html>" >> "$HTMLFILE"

# ========= Send email only if failures exist =========
if [ $failures -gt 0 ]; then
  if command -v sendmail >/dev/null 2>&1; then
    {
      echo "To: $EMAIL_TO"
      echo "Subject: $EMAIL_SUBJECT ($failures failures)"
      echo "MIME-Version: 1.0"
      echo "Content-Type: text/html"
      echo
      cat "$HTMLFILE"
    } | sendmail -t
  elif command -v mail >/dev/null 2>&1; then
    mail -s "$EMAIL_SUBJECT ($failures failures)" "$EMAIL_TO" < "$LOGFILE"
  fi
fi
