FROM alpine:3.13

RUN apk --no-cache update && apk --no-cache add python3 py3-pip py3-wheel python3-dev libffi libffi-dev gcc build-base

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY tgarchive ./tgarchive
COPY LICENSE ./
COPY MANIFEST.in ./
COPY README.md ./
COPY setup.py ./
COPY entrypoint.sh ./

RUN ["chmod", "+x", "./entrypoint.sh"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["--help"]
