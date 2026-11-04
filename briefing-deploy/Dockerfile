ARG BASE
FROM ${BASE}
USER root
RUN pip install --no-cache-dir 'httpx[http2]==0.28.1' 'PyJWT[crypto]>=2.10,<3'
COPY briefings.py briefing_catalog.json /app/app/
COPY patch.py /tmp/briefing-patch.py
RUN python /tmp/briefing-patch.py && rm /tmp/briefing-patch.py
