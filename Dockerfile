# The Jheel Prahari API as a container (Hugging Face Docker Space: user 1000, port 7860).
FROM python:3.10-slim
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt
COPY --chown=user app.py ./
COPY --chown=user jheel/ jheel/
COPY --chown=user web/ web/
COPY --chown=user data/south-lhonak.json data/
USER user
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
