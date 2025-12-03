@echo off
echo Starting YouTube Video Data Analytics Streamlit app...
call yt-analyzer-env\Scripts\activate.bat
streamlit run youtube_analytics_app.py --server.port 8501 --server.address 0.0.0.0
pause