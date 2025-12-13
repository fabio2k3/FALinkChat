FROM alpine:3.19

RUN apk add --no-cache \
    bash \
    curl \
    wget

COPY start_client.sh /start_client.sh
RUN chmod +x /start_client.sh

CMD ["/bin/bash", "/start_client.sh"]
