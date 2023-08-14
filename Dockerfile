FROM alpine

# Install bash
RUN apk update && \
    apk add --no-cache bash python3 nodejs npm

# Create limited user
RUN adduser -D -s /bin/bash bot
USER bot
WORKDIR /home/bot
