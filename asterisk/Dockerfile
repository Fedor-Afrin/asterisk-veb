FROM ubuntu:22.04

# Эта строка пропустит все вопросы про часовые пояса
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    asterisk \
    asterisk-modules \
    --no-install-recommends \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Создаем папку и даем права (на случай если захочешь запустить не от root)
RUN mkdir -p /etc/asterisk

CMD ["/usr/sbin/asterisk", "-f"]
