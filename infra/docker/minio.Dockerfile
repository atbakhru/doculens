# Community MinIO is source-only. Build a fixed upstream revision instead of
# depending on retired Docker Hub images. Local demonstration use only.
FROM golang:1.25-bookworm AS build
ARG MINIO_REVISION=7aac2a2c5b7c882e68c1ce017d8256be2feea27f
RUN git init /src && cd /src && git remote add origin https://github.com/minio/minio.git && git fetch --depth 1 origin "$MINIO_REVISION" && git checkout --detach FETCH_HEAD
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -o /out/minio .
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home minio && mkdir /data && chown minio:minio /data
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /usr/share/doc/minio/LICENSE
USER minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
