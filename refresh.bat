@echo off
echo ================================
echo  B^&S Influence — Data Refresh
echo ================================
echo.

set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\dlawrence\Documents\commanding-air-450109-p0-f8a1b53898f5.json

echo [1/3] Fetching GA4 influencer data from BigQuery...
python scripts/fetch_ga4_influencer.py
if errorlevel 1 goto error

echo.
echo [2/3] Processing paid ads data...
python scripts/process_paid.py
if errorlevel 1 goto error

echo.
echo [3/3] Processing organic posts...
python scripts/process_organic.py
if errorlevel 1 goto error

echo.
echo Committing and pushing to GitHub...
git add data/ga4_influencer.json data/paid_ads.json data/organic_posts.json
git commit -m "chore: refresh influencer data"
git push

echo.
echo ================================
echo  Done! Dashboard updated.
echo  https://dlawrence-bands.github.io/bs-influence/
echo ================================
goto end

:error
echo.
echo Something went wrong — check the error above.

:end
pause
