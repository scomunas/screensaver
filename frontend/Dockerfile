FROM nginx:alpine

# Copy static assets to the default nginx location
COPY . /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
