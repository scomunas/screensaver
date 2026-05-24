FROM nginx:alpine

# Copy static assets to the default nginx location
COPY . /usr/share/nginx/html

# Make the generation script executable and move it to nginx entrypoints folder
# Any script in /docker-entrypoint.d/ is executed before nginx starts
RUN chmod +x /usr/share/nginx/html/generate-config.sh && \
    mv /usr/share/nginx/html/generate-config.sh /docker-entrypoint.d/40-generate-config.sh

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
