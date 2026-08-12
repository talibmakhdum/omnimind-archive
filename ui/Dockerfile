FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY streamlit_app.py /app/streamlit_app.py
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"]
