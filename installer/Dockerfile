FROM alpine:3.20

# docker-cli-compose даёт команду "docker compose" (v2)
RUN apk add --no-cache bash curl tar docker-cli docker-cli-compose

ENV IN_INSTALLER_CONTAINER=1
COPY install.sh /install.sh
RUN chmod +x /install.sh

ENTRYPOINT ["/install.sh"]
