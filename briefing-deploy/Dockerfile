ARG BASE
FROM ${BASE}
USER root
RUN pip install --no-cache-dir 'httpx[http2]==0.28.1' 'PyJWT[crypto]>=2.10,<3'
COPY briefings.py briefing_catalog.json /app/app/
COPY patch.py /tmp/briefing-patch.py
RUN python /tmp/briefing-patch.py && python -m py_compile /app/app/main.py /app/app/briefings.py && rm /tmp/briefing-patch.py
ARG APP_USER=root
USER ${APP_USER}
