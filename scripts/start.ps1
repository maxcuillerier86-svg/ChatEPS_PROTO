Copy-Item .env.example .env -ErrorAction SilentlyContinue
docker compose up --build
