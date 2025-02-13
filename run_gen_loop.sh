#!/bin/bash

while true; do
    echo "Starting cache generation..."
    
    if /bin/bash /app/gen.sh; then
        echo "Cache generation completed successfully."
        sleep 3600 # Sleep for one hour
    else
        echo "Cache generation failed. Retrying in 5 minutes..."
        sleep 300 # Sleep for 5 minutes
    fi
done
