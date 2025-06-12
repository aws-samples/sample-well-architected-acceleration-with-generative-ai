FROM python:3.11@sha256:a46ef4ef9f9d4fee62ad368f9526552a0a99e90882d246cdefe50d356e3a74dd
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt --no-cache-dir
COPY . .
EXPOSE 8501
HEALTHCHECK --interval=600s --timeout=2s --retries=12 \
    CMD ["curl", "-f", "http://localhost:8501/"]
ENTRYPOINT ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port=8501", "--browser.serverAddress=0.0.0.0", "--browser.gatherUsageStats", "false"]
USER 1001