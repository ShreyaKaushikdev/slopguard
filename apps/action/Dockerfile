FROM python:3.11-slim

RUN pip install --no-cache-dir requests pyyaml

COPY entrypoint.sh /entrypoint.sh
COPY pr_check.py /pr_check.py

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
