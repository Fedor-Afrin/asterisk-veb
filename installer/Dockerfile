FROM alpine:latest

RUN apk add --no-cache bash curl tar docker-cli docker-compose

WORKDIR /app
COPY install.sh /install.sh
RUN chmod +x /install.sh

ENTRYPOINT ["/install.sh"]