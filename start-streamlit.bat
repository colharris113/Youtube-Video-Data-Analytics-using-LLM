@echo off
echo Starting YouTube Video Data Analytics Streamlit app...
echo Using new multi-page architecture (app.py)
call yt-analyzer-env\Scripts\activate.bat
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
pause