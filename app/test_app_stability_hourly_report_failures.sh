#!/bin/sh
# ===========================================================
# Tufts Libraries - Hourly Application Endpoint Failure Alert
# ===========================================================
# Runs hourly between 5 AM and 10 PM via cron:
#   0 5-22 * * * /home/libraryapps/test_app_stability_hourly_failures.sh
#
# Sends an HTML email *only* if one or more monitored endpoints
# return a non-2xx/3xx response or fail to connect.
# ===========================================================

set -eu
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# --- Configuration ---
EMAIL_TO="tulips@tufts.edu"
EMAIL_SUBJECT="Application Endpoint Alert"   
DATESTAMP=$(date +%Y%m%d%H%M%S)
WORKDIR="/home/libraryapps"
LOGFILE="$WORKDIR/app_status_${DATESTAMP}.txt"
HTMLFILE="$WORKDIR/app_status_${DATESTAMP}.html"

APPS="
Self Service Portal Prod|https://tufts-libraries-alma-self-service-app.lib>
Self Service Portal Staging|https://tufts-libraries-alma-self-service-stag>
Alma Inventory App Prod|https://tufts-libraries-alma-inventory-app.library>
Alma Inventory App Staging|https://tufts-libraries-alma-inventory-app-stag>
Alternative Endpoint to Alma Inventory App Prod|https://stacked-gantt.libr>
Alternative Endpoint to Alma Inventory App Staging|https://stacked-gantt-s>
Alma Media Equipment Webhook Listener Prod|https://stacked-gantt.library.t>
Alma Media Equipment Webhook Listener Staging|https://stacked-gantt-stage.>
LTS Stacked Gantt App for JIRA Prod|https://lts-project-jira.library.tufts>
LTS Stacked Gantt App for JIRA Staging|https://lts-project-jira-stage.libr>
"

# --- Initialize Logs ---
{
  echo "Endpoint failure check ($(date))"
  echo "Host: $(hostname)"
  echo "----------------------------------------"
} > "$LOGFILE"

{
  echo "<html><body>"
  echo "<h3>Endpoint failures ($(date)) on $(hostname)</h3>"
  echo "<table border='1' cellpadding='5' cellspacing='0'>"
  echo "<tr><th>Application</th><th>URL</th><th>Status</th><th>Documentati>
} > "$HTMLFILE"

failures=0

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

  # Flag failures only
  if ! echo "$status" | grep -Eq '^[23]'; then
    failures=$((failures + 1))
    echo "The application $name at $url has status code $status and may be>
    echo "<tr><td>$name</td><td><a href=\"$url\">$url</a></td><td style='c>
  fi
done

echo "</table></body></html>" >> "$HTMLFILE"

# --- Send HTML email only if failures detected ---
if [ $failures -gt 0 ]; then
  SUBJECT_FULL="$EMAIL_SUBJECT ($failures failure$( [ $failures -ne 1 ] &&>
  if [ -x /usr/sbin/sendmail ]; then
    {
      echo "To: $EMAIL_TO"
      echo "Subject: $SUBJECT_FULL"
      echo "MIME-Version: 1.0"
      echo "Content-Type: text/html"
      echo
      cat "$HTMLFILE"
  GNU nano 5.6.1      test_app_stability_hourly_failures.sh      Modified  
    } | /usr/sbin/sendmail -t
  elif command -v mail >/dev/null 2>&1; then
    # Prefer s-nail/mailx with HTML support
    if mail -V 2>&1 | grep -q "s-nail"; then
      mail -a "Content-Type: text/html" -s "$SUBJECT_FULL" "$EMAIL_TO" < ">
    else
      mail -s "$SUBJECT_FULL" "$EMAIL_TO" < "$LOGFILE"
    fi
  else
    echo "No mailer found. See $LOGFILE and $HTMLFILE"
  fi
fi

# --- Optional cleanup (keep 7 days of reports) ---
find "$WORKDIR" -type f -name "app_status_*.html" -mtime +7 -delete 2>/dev>
find "$WORKDIR" -type f -name "app_status_*.txt" -mtime +7 -delete 2>/dev/>
