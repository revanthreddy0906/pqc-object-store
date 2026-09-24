# Builds the final MinIO community release from source (decision D1).
# The community edition is archived and its official images are no longer
# published, so the benchmark's storage server is compiled from the release tag.

ARG GO_VERSION=1.24.8
ARG MINIO_TAG=RELEASE.2025-10-15T17-29-55Z

FROM golang:${GO_VERSION}-bookworm AS build
ARG MINIO_TAG
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
WORKDIR /src
RUN git clone --depth 1 --branch "${MINIO_TAG}" https://github.com/minio/minio.git . \
 && git rev-parse HEAD > /minio.commit
# Same flags as upstream `make build`, with the version string taken from the tag.
RUN VERSION="$(echo "${MINIO_TAG}" | sed -E 's/RELEASE\.([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2})-([0-9]{2})Z/\1T\2:\3:\4Z/')" \
 && LDFLAGS="$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${VERSION}")" \
 && go build -tags kqueue -trimpath -ldflags "${LDFLAGS}" -o /out/minio \
 && sha256sum /out/minio > /out/minio.sha256 \
 && go version > /out/go.version

FROM debian:bookworm-slim
ARG MINIO_TAG
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /out/minio.sha256 /out/go.version /minio.commit /usr/share/minio-build/
RUN echo "${MINIO_TAG}" > /usr/share/minio-build/tag \
 && useradd --system --home /data minio \
 && mkdir -p /data && chown minio /data
USER minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--address", ":9000", "--console-address", ":9001"]
