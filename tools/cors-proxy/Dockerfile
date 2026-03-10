# Minimal transparent CORS proxy.
#
# Build:
#   docker build -t modelmesh-cors-proxy .
#
# Run:
#   docker run -p 9090:9090 modelmesh-cors-proxy
#
# Custom port:
#   docker run -p 8080:8080 -e PORT=8080 modelmesh-cors-proxy

FROM node:20-alpine

WORKDIR /app
COPY cors-proxy.js .

EXPOSE 9090
ENV PORT=9090

CMD ["node", "cors-proxy.js"]
