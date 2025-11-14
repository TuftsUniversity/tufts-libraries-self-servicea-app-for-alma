#!/usr/bin/env python3
from datetime import datetime, date
import requests 
users_url = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/users?"
user_url = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/users"
parameter = "q=identifiers~"
utln = "hsteel01"
apikey = "l8xx747a4b2c4c4b4ea4974c71c3b438ad00"

response = requests.get(users_url + parameter + utln + "&apikey=" + apikey + "&format=json")
print(response.text)
users = response.json()

if response.status_code == 200:

    trunk = users['user'][0]['primary_id']

    user_response = requests.get(user_url + '/' + trunk + "?apikey=" + apikey + "&format=json")

    if user_response.status_code == 200:

        user = user_response.json()
        print("User found:", user['first_name'], user['last_name'], "with primary ID:", user['primary_id'])
     

        print(user['user_role'])
        if 'user_role' in user:

            # print("User roles:", user['user_role'])
            # import json

           

            # Target role descriptions to check
            target_roles = {
                "Cataloger",
                "Cataloger Extended",
                "Catalog Manager",
                "Catalog Administrator"
            }

            target_roles = {"Cataloger", "Cataloger Extended", "Catalog Manager", "Catalog Administrator"}

            # Look through user_role entries
            has_catalog_role = any(
                role.get("role_type", {}).get("desc") in target_roles
                and (
                    # Parse expiry_date and check if today or later
                    (lambda d: datetime.strptime(d.rstrip("Z"), "%Y-%m-%d").date() >= date.today())
                    (role.get("expiry_date", "9999-12-31Z"))  # default far future if missing
                )
                for role in user.get("user_role", []))


            # Parse the expiry date (strip the trailing Z if present)

      
        else:
            print
            ##put here whatever in PHP Drupal should do if the call fails

    else:
        print("Failed to retrieve user details. Status code:", user_response.status_code)

else:
    print("Failed to retrieve users. Status code:", response.status_code)("No users found with the given identifier.")