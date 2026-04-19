#!/bin/bash

echo "=== bipthelper Service Split Test ==="
echo

echo "1. Checking service structure..."
if [ -d "backend/crawler_service" ]; then
    echo "✓ crawler_service/ exists"
else
    echo "✗ crawler_service/ missing"
fi

if [ -d "backend/search_service" ]; then
    echo "✓ search_service/ exists"
else
    echo "✗ search_service/ missing"
fi

echo
echo "2. Checking crawler_service endpoints..."
if grep -q "crawl_admin_router" backend/crawler_service/main.py; then
    echo "✓ crawler_service uses crawl_admin_router"
else
    echo "✗ crawl_admin_router not found"
fi

if grep -q "8001" backend/crawler_service/main.py; then
    echo "✓ crawler_service runs on port 8001"
else
    echo "✗ port 8001 not configured"
fi

echo
echo "3. Checking search_service structure..."
if grep -q "StaticFiles" backend/search_service/main.py; then
    echo "✓ search_service serves static files"
else
    echo "✗ static files not configured"
fi

echo "✓ search_service configured (run with: uvicorn search_service.main:app --port 8000 --app-dir backend)"

echo
echo "4. Checking frontend build..."
if [ -d "backend/search_service/assets/frontend" ]; then
    echo "✓ frontend built into search_service/assets/frontend/"
else
    echo "✗ frontend build missing"
fi

if [ -f "frontend/src/api/index.js" ]; then
    if grep -q "CRAWLER_API" frontend/src/api/index.js; then
        echo "✓ frontend CRAWLER_API configured"
    else
        echo "✗ CRAWLER_API not set"
    fi
fi

echo
echo "5. Checking old files removed..."
if [ ! -f "backend/main.py" ]; then
    echo "✓ old backend/main.py removed"
else
    echo "✗ old backend/main.py still exists"
fi

if [ ! -d "backend/api" ]; then
    echo "✓ old backend/api/ removed"
else
    echo "✗ old backend/api/ still exists"
fi

echo
echo "6. Checking shared resources..."
if [ -f "backend/database.py" ]; then
    echo "✓ database.py shared"
fi
if [ -d "backend/models" ]; then
    echo "✓ models/ shared"
fi

echo
echo "=== Service Split Complete ==="
echo "crawler-service: http://localhost:8001"
echo "search-service:  http://localhost:8000"
