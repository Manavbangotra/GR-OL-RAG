# MongoDB Setup Guide

This guide will help you set up MongoDB for the RAG Chatbot application.

## Option 1: Local MongoDB Installation

### Ubuntu/Debian

```bash
# Import MongoDB public GPG key
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -sc)/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update package database
sudo apt-get update

# Install MongoDB
sudo apt-get install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify installation
sudo systemctl status mongod
```

### Using Docker (Recommended for Development)

```bash
# Pull MongoDB image
docker pull mongo:latest

# Run MongoDB container
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -v mongodb_data:/data/db \
  mongo:latest

# Verify it's running
docker ps | grep mongodb

# View logs
docker logs mongodb
```

**Update .env**:
```env
MONGODB_URI=mongodb://localhost:27017/
```

## Option 2: MongoDB Atlas (Cloud - Free Tier Available)

### Steps:

1. **Sign Up**
   - Go to https://www.mongodb.com/cloud/atlas
   - Click "Try Free"
   - Create account with email or Google

2. **Create Cluster**
   - Choose "Free" tier (M0)
   - Select cloud provider (AWS, Google Cloud, or Azure)
   - Choose region closest to you
   - Click "Create Cluster" (takes 3-5 minutes)

3. **Configure Security**
   - **Database Access**: 
     - Click "Database Access" in left sidebar
     - Click "Add New Database User"
     - Create username and password (save these!)
     - Set role to "Read and write to any database"
   
   - **Network Access**:
     - Click "Network Access" in left sidebar
     - Click "Add IP Address"
     - For development: Click "Allow Access from Anywhere" (0.0.0.0/0)
     - For production: Add your specific IP

4. **Get Connection String**
   - Click "Database" in left sidebar
   - Click "Connect" on your cluster
   - Choose "Connect your application"
   - Copy the connection string
   - It looks like: `mongodb+srv://username:password@cluster.xxxxx.mongodb.net/`

5. **Update .env**
   ```env
   MONGODB_URI=mongodb+srv://username:password@cluster.xxxxx.mongodb.net/rag_chatbot?retryWrites=true&w=majority
   ```
   
   Replace:
   - `username` with your database username
   - `password` with your database password
   - `cluster.xxxxx` with your actual cluster address

## Verify MongoDB Connection

### Test Connection (Python)

```bash
cd /home/nikhilsharma/Desktop/RAG

# Create test script
cat > test_mongo.py << 'EOF'
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
print(f"Testing connection to: {mongodb_uri}")

try:
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB connection successful!")
    
    # List databases
    dbs = client.list_database_names()
    print(f"Available databases: {dbs}")
    
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check if MongoDB is running (local)")
    print("2. Verify MONGODB_URI in .env file")
    print("3. Check network access (Atlas)")
    print("4. Verify username/password (Atlas)")

EOF

# Run test
python3 test_mongo.py
```

### Test with MongoDB Compass (GUI)

1. Download MongoDB Compass: https://www.mongodb.com/products/compass
2. Install and open
3. Paste your connection string
4. Click "Connect"
5. You should see your databases

## MongoDB Commands

### Start/Stop Local MongoDB

```bash
# Start
sudo systemctl start mongod

# Stop
sudo systemctl stop mongod

# Restart
sudo systemctl restart mongod

# Status
sudo systemctl status mongod
```

### Docker MongoDB Commands

```bash
# Start container
docker start mongodb

# Stop container
docker stop mongodb

# View logs
docker logs -f mongodb

# Access MongoDB shell
docker exec -it mongodb mongosh
```

### MongoDB Shell Commands

```bash
# Connect to local MongoDB
mongosh

# Show databases
show dbs

# Use database
use rag_chatbot

# Show collections
show collections

# View checkpoints
db.checkpoints.find().pretty()

# Count documents
db.checkpoints.countDocuments()

# Delete all checkpoints
db.checkpoints.deleteMany({})

# Exit
exit
```

## Troubleshooting

### Connection Refused (Local)

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Restart MongoDB
sudo systemctl restart mongod
```

### Authentication Failed (Atlas)

1. Go to MongoDB Atlas dashboard
2. Database Access → Edit user
3. Reset password
4. Update `.env` with new password
5. Ensure password is URL-encoded if it contains special characters

### Network Timeout (Atlas)

1. Go to MongoDB Atlas dashboard
2. Network Access
3. Add your current IP address
4. Or temporarily allow 0.0.0.0/0 for testing

### Port Already in Use

```bash
# Find process using port 27017
sudo lsof -i :27017

# Kill the process
sudo kill -9 <PID>

# Or change MongoDB port in config
sudo nano /etc/mongod.conf
# Change: port: 27018
sudo systemctl restart mongod
```

## Recommended Setup for Development

**Use Docker** - Easiest and cleanest:

```bash
# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  mongodb:
    image: mongo:latest
    container_name: rag_mongodb
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      - MONGO_INITDB_DATABASE=rag_chatbot

volumes:
  mongodb_data:
EOF

# Start MongoDB
docker-compose up -d

# View logs
docker-compose logs -f mongodb

# Stop MongoDB
docker-compose down
```

Update `.env`:
```env
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=rag_chatbot
```

## Production Recommendations

1. **Use MongoDB Atlas** for production
2. **Enable authentication** on local MongoDB
3. **Use specific IP whitelist** instead of 0.0.0.0/0
4. **Enable SSL/TLS** for connections
5. **Regular backups** of your data
6. **Monitor performance** with Atlas monitoring tools

## Next Steps

After setting up MongoDB:

1. Update `.env` with your MongoDB connection string
2. Run `./run.sh` to start the application
3. Check `/health` endpoint to verify MongoDB connection
4. Upload documents and test queries

---

For more help, see:
- MongoDB Documentation: https://docs.mongodb.com/
- MongoDB Atlas Docs: https://docs.atlas.mongodb.com/
