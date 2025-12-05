import os
import subprocess

driver = r"C:\chromedriver\chromedriver.exe"

print("Exists:", os.path.exists(driver))
print("Is file:", os.path.isfile(driver))

try:
    subprocess.run([driver, "--version"], check=True)
except Exception as e:
    print("Cannot execute ChromeDriver:", e)
