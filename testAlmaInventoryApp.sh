#!/usr/bin/env bash
set -euo pipefail

# -----------------------
# CONFIG - customize these
# -----------------------
ENV_FILE="./.env"                 # .env containing USERNAME=... and PASSWORD=...
#INPUT_FILE="${1:-/bib_2_holdings_541_input.txt}"   # or pass as first arg
URL="https://tufts-libraries-alma-self-service-app.library.tufts.edu/bib_2_holdings_541/"    # change to your login endpoint
BARCODE_URL="https://tufts-libraries-alma-self-service-app.library.tufts.edu/bib_2_holdings_541/upload"  # change to your upload endpoint
DOWNLOAD_PREFIX="result"                 # output filename prefix
EMAIL_RECIPIENT="henry.steele@tufts.edu"  # recipient (same always)
SUBJECT="Automated Test Result of 541 holdings file"
MAIL_BODY="Attached is the result file."

# -----------------------
# Derived / temp
# -----------------------


echo "Accessing $URL ..."
# Use curl to POST credentials and save cookies. Capture HTTP status code.
curl -s -c "$COOKIES_FILE" \
  -d "username=${ALMA_USERNAME}&password=${ALMA_PASSWORD}" \
  -X POST "$LOGIN_URL" -o /dev/null -w "%{http_code}\n"
if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "302" && "$HTTP_CODE" != "303" ]]; then
  echo "Login failed: HTTP $HTTP_CODE"
  echo "Inspect cookie file: $COOKIES_FILE"
  exit 4
fi