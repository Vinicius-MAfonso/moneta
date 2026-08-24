#!/usr/bin/env bash
# ==============================================================================
# Moneta - Automated Ultra-Low Cost GCP Deploy Script
# ==============================================================================
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}  🚀 Moneta - Google Cloud Platform (GCP) Deployment ${NC}"
echo -e "${BLUE}  💡 Target: $0.00 / month (Always Free Tier)         ${NC}"
echo -e "${BLUE}=====================================================${NC}\n"

# 1. Check gcloud installation
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: 'gcloud' CLI is not installed.${NC}"
    echo -e "You can install Google Cloud SDK or run this script in ${YELLOW}Google Cloud Shell${NC}:"
    echo -e "🔗 https://shell.cloud.google.com\n"
    exit 1
fi

# 2. Get or Confirm Project ID
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
read -p "Enter your Google Cloud Project ID [${CURRENT_PROJECT}]: " PROJECT_ID
PROJECT_ID=${PROJECT_ID:-$CURRENT_PROJECT}

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Project ID cannot be empty. Please create a project at https://console.cloud.google.com/${NC}"
    exit 1
fi

echo -e "Using GCP Project: ${GREEN}${PROJECT_ID}${NC}"
gcloud config set project "$PROJECT_ID"

# 3. Select Region
echo -e "\nSelect deployment region:"
echo -e "  1) ${GREEN}southamerica-east1${NC} (São Paulo, Brazil - Lowest Latency)"
echo -e "  2) ${GREEN}us-central1${NC} (Iowa, USA - Maximum Free-Tier Availability)"
read -p "Select region [1]: " REGION_CHOICE

case "$REGION_CHOICE" in
    2) REGION="us-central1" ;;
    *) REGION="southamerica-east1" ;;
esac
echo -e "Selected Region: ${GREEN}${REGION}${NC}"

SERVICE_NAME="moneta-web"
REPO_NAME="moneta"

# 4. Enable Required APIs
echo -e "\n${YELLOW}==> Enabling GCP APIs (Cloud Run, Artifact Registry, Cloud Build)...${NC}"
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    --project="$PROJECT_ID"

# 5. Create Artifact Registry Repository (if not exists)
echo -e "\n${YELLOW}==> Checking Artifact Registry repository '${REPO_NAME}'...${NC}"
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "Creating repository '${REPO_NAME}' in ${REGION}..."
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository for Moneta" \
        --project="$PROJECT_ID"
else
    echo -e "${GREEN}Repository '${REPO_NAME}' already exists.${NC}"
fi

# 6. Gather Database URL & Secrets
echo -e "\n${BLUE}=====================================================${NC}"
echo -e "${BLUE}  🔑 Environment & Database Configuration            ${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo -e "Tip: You can use a free PostgreSQL database from ${GREEN}Neon (https://neon.tech)${NC} or ${GREEN}Supabase (https://supabase.com)${NC}."
read -p "Enter PostgreSQL DATABASE_URL: " DATABASE_URL

while [ -z "$DATABASE_URL" ]; do
    echo -e "${RED}DATABASE_URL is required for production!${NC}"
    read -p "Enter PostgreSQL DATABASE_URL: " DATABASE_URL
done

# Generate random SECRET_KEY if not provided
RANDOM_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || openssl rand -hex 32 2>/dev/null || echo "django-prod-$(date +%s)")
read -p "Enter Django SECRET_KEY (leave empty to generate automatically): " USER_SECRET_KEY
SECRET_KEY=${USER_SECRET_KEY:-$RANDOM_SECRET}

# Optional Email Brevo Key
read -p "Enter Brevo API Key (Optional - leave blank if not using yet): " BREVO_API_KEY

# Optional Superuser setup
echo -e "\n${YELLOW}Optional Admin Superuser Setup (created automatically on first boot):${NC}"
read -p "Admin Username (e.g. admin, leave blank to skip): " DJANGO_SUPERUSER_USERNAME
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    read -p "Admin Email: " DJANGO_SUPERUSER_EMAIL
    read -s -p "Admin Password: " DJANGO_SUPERUSER_PASSWORD
    echo ""
fi

# 7. Build and Deploy Container via Cloud Build
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

echo -e "\n${YELLOW}==> Building Docker image in GCP Cloud Build...${NC}"
gcloud builds submit \
    --tag="$IMAGE_TAG" \
    --project="$PROJECT_ID"

echo -e "\n${YELLOW}==> Deploying service '${SERVICE_NAME}' to Cloud Run...${NC}"

# Write temporary YAML env file to avoid comma/delimiter escaping issues in gcloud
ENV_FILE=$(mktemp ./env_vars.XXXXXX.yaml)
chmod 600 "$ENV_FILE"
trap 'rm -f "$ENV_FILE"' EXIT

cat <<EOF > "$ENV_FILE"
DEBUG: "False"
SECRET_KEY: "${SECRET_KEY}"
DATABASE_URL: "${DATABASE_URL}"
ALLOWED_HOSTS: "*"
CSRF_TRUSTED_ORIGINS: "https://*.run.app,https://*.a.run.app"
EOF

if [ -n "$BREVO_API_KEY" ]; then
    echo "BREVO_API_KEY: \"${BREVO_API_KEY}\"" >> "$ENV_FILE"
fi

if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
    cat <<EOF >> "$ENV_FILE"
DJANGO_SUPERUSER_USERNAME: "${DJANGO_SUPERUSER_USERNAME}"
DJANGO_SUPERUSER_EMAIL: "${DJANGO_SUPERUSER_EMAIL}"
DJANGO_SUPERUSER_PASSWORD: "${DJANGO_SUPERUSER_PASSWORD}"
EOF
fi

gcloud run deploy "$SERVICE_NAME" \
    --image="$IMAGE_TAG" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=0 \
    --max-instances=2 \
    --memory=512Mi \
    --cpu=1 \
    --port=8080 \
    --timeout=120 \
    --env-vars-file="$ENV_FILE" \
    --project="$PROJECT_ID"


SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')

# Automatically update SITE_URL to match the generated Cloud Run URL
if [ -n "$SERVICE_URL" ]; then
    gcloud run services update "$SERVICE_NAME" \
        --region="$REGION" \
        --update-env-vars="SITE_URL=${SERVICE_URL}" \
        --project="$PROJECT_ID" \
        --quiet &>/dev/null || true
fi

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}  🎉 Moneta successfully deployed to Cloud Run!     ${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "🌐 Application URL: ${BLUE}${SERVICE_URL}${NC}"
echo -e "🏥 Health Check:    ${BLUE}${SERVICE_URL}/healthz/${NC}"
echo -e "🔐 Admin Panel:     ${BLUE}${SERVICE_URL}/admin/${NC}\n"

