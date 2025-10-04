#!/usr/bin/env bash
set -euo pipefail

# -----------------------
# CONFIG - customize these
# -----------------------
ENV_FILE="./.env"                 # .env containing USERNAME=... and PASSWORD=...
INPUT_FILE="${1:-/bib_2_holdings_541_input.txt}"   # or pass as first arg
LOGIN_URL="https://tufts-libraries-alma-self-service-app.library.tufts.edu/bib_2_holdings_541/"    # change to your login endpoint
UPLOAD_URL="https://tufts-libraries-alma-self-service-app.library.tufts.edu/bib_2_holdings_541/upload"  # change to your upload endpoint
DOWNLOAD_PREFIX="result"                 # output filename prefix
EMAIL_RECIPIENT="henry.steele@tufts.edu"  # recipient (same always)
SUBJECT="Automated Test Result of 541 holdings file"
MAIL_BODY="Attached is the result file."

# -----------------------
# Derived / temp
# -----------------------
TMPDIR="$(mktemp -d)"
COOKIES_FILE="$TMPDIR/cookies.txt"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_FILE="/tmp/${DOWNLOAD_PREFIX}-${TIMESTAMP}.xlsx"

cleanup() {
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

# -----------------------
# Read .env - look for alma_system_username / alma_system_password
# -----------------------
if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key rawval || [[ -n "$key" ]]; do
    # strip whitespace
    key="$(echo "$key" | xargs)"
    # skip comments/empty
    [[ -z "$key" || "${key:0:1}" == "#" ]] && continue
    # strip leading/trailing spaces, strip surrounding quotes
    val="$(echo "$rawval" | sed -E 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed -E 's/^"(.+)"$/\1/; s/^'\''(.+)'\''$/\1/')"
    case "$key" in
      alma_system_username) ALMA_USERNAME="$val" ;;
      alma_system_password) ALMA_PASSWORD="$val" ;;
      *) ;; # ignore other keys
    esac
  done < "$ENV_FILE"
fi

# If not found in .env, try to read from environment
ALMA_USERNAME="${ALMA_USERNAME:-}"
ALMA_PASSWORD="${ALMA_PASSWORD:-}"


if [[ -z "${ALMA_USERNAME:-}" || -z "${ALMA_PASSWORD:-}" ]]; then
  echo "ERROR: alma_system_username and alma_system_password not found in $ENV_FILE or environment."
  exit 2
fi




# Basic existence checks
if [[ ! -f "$INPUT_FILE" ]]; then
  echo "ERROR: input file not found: $INPUT_FILE"
  exit 3
fi

echo "Logging in to $LOGIN_URL ..."
# Use curl to POST credentials and save cookies. Capture HTTP status code.
curl -s -c "$COOKIES_FILE" \
  -d "username=${ALMA_USERNAME}&password=${ALMA_PASSWORD}" \
  -X POST "$LOGIN_URL" -o /dev/null -w "%{http_code}\n"
if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "302" && "$HTTP_CODE" != "303" ]]; then
  echo "Login failed: HTTP $HTTP_CODE"
  echo "Inspect cookie file: $COOKIES_FILE"
  exit 4
fi
echo "Login request returned HTTP $HTTP_CODE. Cookies saved to $COOKIES_FILE."

echo "Uploading $INPUT_FILE to $UPLOAD_URL ... (saving to $OUTPUT_FILE)"
# Perform upload with saved cookies; follow redirects (-L)
curl -s -L -b "$COOKIES_FILE" -F "fileUpload=@${INPUT_FILE}" -o "$OUTPUT_FILE" "$UPLOAD_URL"

# Quick check that file exists and is non-empty
if [[ ! -s "$OUTPUT_FILE" ]]; then
  echo "ERROR: upload did not produce a downloadable file or the server returned empty response."
  echo "Check $OUTPUT_FILE (zero size) and cookies $COOKIES_FILE for troubleshooting."
  exit 5
fi

echo "Download saved to $OUTPUT_FILE (size: $(stat -c%s "$OUTPUT_FILE") bytes)."

# -----------------------
# Email the file
# Try mailx, mail, mutt (in that order). If none present, print helpful message.
# -----------------------
send_with_mailx() {
  # BSD/Heirloom mailx expects -a for attachment, some implementations use -A.
  if mailx -V >/dev/null 2>&1; then
    echo "$MAIL_BODY" | mailx -s "$SUBJECT" -a "$OUTPUT_FILE" "$EMAIL_RECIPIENT"
    return $?
  else
    return 1
  fi
}

send_with_mail_cmd() {
  # Some 'mail' support -A for attachments
  if mail -V >/dev/null 2>&1; then
    # try -A (GNU mailutils) first
    echo "$MAIL_BODY" | mail -s "$SUBJECT" -A "$OUTPUT_FILE" "$EMAIL_RECIPIENT" >/dev/null 2>&1 && return 0 || true
    # try -a (BSD mail)
    echo "$MAIL_BODY" | mail -s "$SUBJECT" -a "$OUTPUT_FILE" "$EMAIL_RECIPIENT" >/dev/null 2>&1 && return 0 || true
  fi
  return 1
}

send_with_mutt() {
  if command -v mutt >/dev/null 2>&1; then
    echo "$MAIL_BODY" | mutt -s "$SUBJECT" -a "$OUTPUT_FILE" -- "$EMAIL_RECIPIENT"
    return $?
  fi
  return 1
}

echo "Sending email to $EMAIL_RECIPIENT ..."
if send_with_mailx; then
  echo "Email sent with mailx."
elif send_with_mail_cmd; then
  echo "Email sent with mail."
elif send_with_mutt; then
  echo "Email sent with mutt."
else
  echo "No mail client found that supports command-line attachments (mailx / mail / mutt)."
  echo "As a fallback, you can send via Python's smtplib. Example:"
 