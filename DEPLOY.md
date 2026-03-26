# Deploying SurveyCAD to Render (with DWG Support)

Render's standard Python environment does not support installing Linux system packages like the **ODA File Converter**, which is absolutely required for generating DWG files.

To fix this and successfully deploy with 100% working DWG export, you must use **Docker** on Render. I have written the required `Dockerfile` for you.

## Step-by-Step Guide

1. **Download the ODA File Converter for Linux:**
   - Go to: [ODA File Converter Download Page](https://www.opendesign.com/guestfiles/oda_file_converter)
   - Download the **Ubuntu 20.04 DEB** version. The file should look like `ODAFileConverter_25.11_build_1_amd64.deb` (or a similar version).
   
2. **Move the file to your project folder:**
   - Place that `.deb` file directly into your `SurveyCAD` project folder (right next to `app.py` and `Dockerfile`).

3. **Push to GitHub:**
   - Ensure the `.deb` file, the `Dockerfile`, and all other files are pushed to your GitHub repository.

4. **Create the Web Service on Render:**
   - Go to your Render Dashboard → New → Web Service.
   - Connect your GitHub repository.
   - Render should automatically detect it as a **Docker** environment because of the `Dockerfile`. (If not, set the Environment or "Runtime" setting to Docker).
   - Click **Deploy**.

Render will automatically build your app, securely install the ODA File Converter from the `.deb` file, and deploy it using Gunicorn. DWG files will now generate perfectly online!
