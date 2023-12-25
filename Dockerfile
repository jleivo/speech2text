FROM alpine:latest

ARG USER_ID=1000
ARG USER="speechtotext"
ARG GROUP_ID=1000

# Basic packages
RUN apk add --quiet --no-cache bash python3 py3-pip ffmpeg

# Create user and group
RUN addgroup -g ${GROUP_ID} ${USER} && \
    adduser -D -G ${USER} -u ${USER_ID} ${USER}
WORKDIR /home/${USER}

# Actual app
RUN mkdir /app /target /audio
COPY scripts/LLM_text_to_speech.py /app
# Install python modules for the user
RUN su - ${USER} -c "pip install --no-cache-dir --quiet --break-system-packages whisper"
RUN chown -R ${USER}:${USER} /app /target /audio

USER ${USER}