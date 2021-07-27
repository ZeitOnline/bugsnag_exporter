# docker build --tag eu.gcr.io/zeitonline-210413/bugsnag-exporter:PACKAGEVERSION-DOCKERVERSION .
FROM python:3.9.5-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-deps -r requirements.txt
COPY ./ ./
RUN pip install --use-feature=in-tree-build --no-deps .
ENTRYPOINT ["bugsnag_exporter"]
