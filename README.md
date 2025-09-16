Create image
docker build -t alert-system .
docker run -d --name alert-system alert-system
