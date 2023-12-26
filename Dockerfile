FROM ubuntu:22.04

ARG USER_ID=1000
ARG USER="speechtotext"
ARG GROUP_ID=1000

# Package installation, add packages before &&
RUN apt-get update && apt-get install -qq -y --no-install-recommends \
    bash python3 ffmpeg python3-pip inotify-tools && \
    rm -rf /var/lib/apt/lists/*

# User creation
RUN groupadd -g ${GROUP_ID} ${USER} &&\
    useradd -m -u ${USER_ID} -g ${USER} -d /home/${USER} -s /bin/bash ${USER}
WORKDIR /home/${USER}

# Install python modules for the user
RUN su - ${USER} -c "pip install -U --no-cache-dir --quiet openai-whisper"

# Create baseline structures & files
RUN mkdir -p /app /target /audio /var/models
RUN chown -R ${USER}:${USER} /app /target /audio /var/models
COPY scripts/* /app/

USER ${USER}
# Bash shell entrypoint for monitoring
ENTRYPOINT ["/bin/bash", "/app/record_watcher.sh"]