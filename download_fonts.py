import urllib.request
import os

os.makedirs("fonts", exist_ok=True)
url_reg = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
url_bold = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf"

urllib.request.urlretrieve(url_reg, "fonts/DejaVuSans.ttf")
urllib.request.urlretrieve(url_bold, "fonts/DejaVuSans-Bold.ttf")
print("Fonts downloaded successfully")
