#!/bin/bash

# Network Management Platform - Development Startup Script

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Network Management Platform (Development Mode)${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env file. Please review and update as needed.${NC}"
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    echo -e "${RED}❌ docker-compose not found. Please install docker-compose.${NC}"
    exit 1
fi

echo -e "${BLUE}🔧 Starting infrastructure services...${NC}"

# Start database and Redis first
docker-compose up -d database redis

# Wait for database to be ready
echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
until docker-compose exec -T database pg_isready -U netmgmt -d network_mgmt; do
    sleep 2
done
echo -e "${GREEN}✅ Database is ready${NC}"

# Wait for Redis to be ready
echo -e "${YELLOW}⏳ Waiting for Redis to be ready...${NC}"
until docker-compose exec -T redis redis-cli ping | grep PONG; do
    sleep 2
done
echo -e "${GREEN}✅ Redis is ready${NC}"

# Start Ray cluster
echo -e "${BLUE}🎯 Starting Ray cluster...${NC}"
docker-compose up -d ray-head

# Wait a bit for Ray to initialize
sleep 10

# Start backend
echo -e "${BLUE}🔧 Starting backend service...${NC}"
docker-compose up -d backend

# Wait for backend to be ready
echo -e "${YELLOW}⏳ Waiting for backend to be ready...${NC}"
timeout=60
counter=0
until curl -f http://localhost:8000/health >/dev/null 2>&1; do
    sleep 2
    counter=$((counter + 2))
    if [ $counter -ge $timeout ]; then
        echo -e "${RED}❌ Backend failed to start within ${timeout} seconds${NC}"
        echo -e "${YELLOW}💡 Check logs with: docker-compose logs backend${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✅ Backend is ready${NC}"

# Start frontend
echo -e "${BLUE}🎨 Starting frontend...${NC}"
docker-compose up -d frontend

# Start monitoring services
echo -e "${BLUE}📊 Starting monitoring services...${NC}"
docker-compose up -d prometheus grafana

echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo
echo -e "${BLUE}📋 Service URLs:${NC}"
echo -e "   🌐 Web Interface:     ${GREEN}http://localhost:3000${NC}"
echo -e "   🔧 API Documentation: ${GREEN}http://localhost:8000/api/docs${NC}"
echo -e "   📊 Grafana:          ${GREEN}http://localhost:3001${NC} (admin/admin123)"
echo -e "   🎯 Ray Dashboard:     ${GREEN}http://localhost:8265${NC}"
echo -e "   📈 Prometheus:       ${GREEN}http://localhost:9090${NC}"
echo
echo -e "${YELLOW}💡 Useful commands:${NC}"
echo -e "   📋 View logs:        ${BLUE}docker-compose logs -f [service]${NC}"
echo -e "   🔄 Restart service:  ${BLUE}docker-compose restart [service]${NC}"
echo -e "   🛑 Stop all:         ${BLUE}docker-compose down${NC}"
echo -e "   🗑️  Clean all data:   ${BLUE}docker-compose down -v${NC}"
echo
echo -e "${GREEN}✨ Development environment is ready!${NC}"