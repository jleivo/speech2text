#!/bin/bash
#
# A dirty workaround for Juha to update the git repo on tuvlnxsrvp04
# Date: 2026-07-21
# Version: 1.0.0

echo "Changing ownership to Juha"
sudo chown juha:juha -R /srv/speech2text/

echo "Pulling changes"
git pull

echo "Changing ownershipt back to speech2text"
sudo chown speech2text:speech2text -R /srv/speech2text/

