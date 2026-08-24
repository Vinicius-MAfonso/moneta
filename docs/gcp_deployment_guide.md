# 🚀 Guia de Deploy do Moneta no Google Cloud Platform (GCP)
> **Meta:** Custo Zero ($0.00/mês) utilizando o **Always Free Tier do GCP** + **PostgreSQL Serverless Gratuito (Neon / Supabase)**.

---

## 💰 Arquitetura de Custo Zero ($0.00 / mês)

| Recurso | Provedor / Serviço | Cota Gratuita (Free Tier) | Custo Estimado |
| :--- | :--- | :--- | :--- |
| **Aplicação Web & Django-Q** | **Google Cloud Run** | 2.000.000 requisições/mês, 360.000 GB-segundos, 180.000 vCPU-segundos | **$0.00** |
| **Banco de Dados PostgreSQL** | **Neon.tech** ou **Supabase** | 0.5 GB de dados, computação serverless automática | **$0.00** |
| **Arquivos Estáticos (CSS/JS)** | **WhiteNoise** (embutido no container) | Servido direto da memória/disco do container | **$0.00** |
| **Registro de Containers** | **GCP Artifact Registry** | 0.5 GB/mês de armazenamento | **$0.00** |
| **Emails Transacionais** | **Brevo (Sendinblue)** | 300 emails/dia | **$0.00** |
| **Certificado SSL / HTTPS** | **Google Cloud Run** | SSL automático e renovação gratuita | **$0.00** |
| **Total Mensal** | | | **~$0.00** |

---

## 🛠️ Passo 1: Criar o Banco de Dados PostgreSQL Gratuito (2 Minutos)

O Google Cloud SQL tradicional custa cerca de R$ 80 a R$ 150/mês. Para atingir **custo zero**, recomendamos o [Neon](https://neon.tech) ou [Supabase](https://supabase.com):

### Opção A: Neon (Recomendado - Super Rápido)
1. Acesse [https://neon.tech](https://neon.tech) e crie uma conta gratuita (com GitHub ou Google).
2. Clique em **Create Project**, escolha o nome `moneta-db` e a região mais próxima (ex: `AWS us-east-2` ou `AWS us-east-1`).
3. No painel, copie a string de conexão em **Connection Details** (selecione o modo `Pooled connection` ou `Direct connection`).
4. Sua URL será parecida com:
   ```text
   postgresql://moneta_owner:AbC123XyZ@ep-sample-pooler.us-east-2.aws.neon.tech/moneta_db?sslmode=require
   ```

### Opção B: Supabase
1. Acesse [https://supabase.com](https://supabase.com) e crie um novo projeto.
2. Em **Project Settings -> Database -> Connection string**, copie a URL em modo `URI`.

---

## 🚀 Passo 2: Deploy no Google Cloud Platform

Você pode fazer o deploy diretamente pelo navegador via **Google Cloud Shell** (sem precisar instalar nada no seu computador) ou pelo terminal local com `gcloud`.

### Método 1: Via Script Automatizado (Mais Fácil)

1. Abra o [Google Cloud Shell](https://shell.cloud.google.com).
2. Clone seu repositório ou acesse a pasta do Moneta:
   ```bash
   git clone https://github.com/SEU_USUARIO/moneta.git
   cd moneta
   ```
3. Execute o script de deploy interativo:
   ```bash
   ./deploy-gcp.sh
   ```
4. O script irá:
   - Solicitar seu **ID do Projeto GCP**;
   - Ativar automaticamente as APIs do Cloud Run, Artifact Registry e Cloud Build;
   - Pedir a sua `DATABASE_URL` do Neon/Supabase;
   - Compilar a imagem Docker (com Tailwind CSS e WhiteNoise embutidos);
   - Fazer o deploy no Cloud Run com configuração `min-instances=0` (custo zero quando ocioso);
   - Executar as migrações do banco e configurar o agendador de tarefas do Django-Q automaticamente.

---

### Método 2: Deploy Manual via Linha de Comando (`gcloud`)

Caso prefira executar cada comando manualmente:

```bash
# 1. Defina as variáveis
PROJECT_ID="SEU_ID_DE_PROJETO_GCP"
REGION="southamerica-east1" # ou us-central1
REPO_NAME="moneta"
SERVICE_NAME="moneta-web"

# 2. Configure o projeto e ative os serviços
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# 3. Crie o repositório de containers
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repo Moneta"

# 4. Construa e envie a imagem
gcloud builds submit --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest"

# 5. Faça o Deploy no Cloud Run
gcloud run deploy $SERVICE_NAME \
    --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:latest" \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 2 \
    --memory 512Mi \
    --cpu 1 \
    --port 8080 \
    --set-env-vars "DEBUG=False,SECRET_KEY=$(openssl rand -hex 32),DATABASE_URL=SUA_DATABASE_URL_DO_NEON,ALLOWED_HOSTS=*,CSRF_TRUSTED_ORIGINS=https://*.run.app"
```

---

## 🔄 Passo 3: CI/CD Automático com GitHub (Opcional)

Se quiser que novos `git push` na branch `main` atualizem sua aplicação automaticamente:

1. No Google Cloud Console, acesse **Cloud Build -> Gatilhos (Triggers)**.
2. Clique em **Criar Gatilho (Create Trigger)**.
3. Conecte seu repositório GitHub.
4. Em **Configuração de compilação**, selecione **Arquivo de configuração do Cloud Build (yaml ou json)** e aponte para `cloudbuild.yaml`.
5. Salve o gatilho. A cada commit na branch `main`, o GCP compilará e atualizará o Cloud Run de forma 100% automatizada!

---

## 🌐 Passo 4: Mapear Domínio Personalizado (Opcional)

O Cloud Run já oferece uma URL segura HTTPS gratuita (ex: `https://moneta-web-xyz-rj.a.run.app`). Para usar seu próprio domínio (ex: `financas.meusite.com`):

1. No console do Cloud Run, clique no serviço **moneta-web** e selecione **Mapeamentos de domínio personalizado (Manage Custom Domains)**.
2. Clique em **Adicionar Mapeamento**, digite seu domínio e siga as instruções para adicionar os registros CNAME/TXT no seu provedor de DNS (Cloudflare, GoDaddy, Registro.br, etc.).
3. O Google provisionará um certificado SSL gratuito automaticamente.

---

## 🛡️ Dica Pro: Alerta de Orçamento no GCP (Segurança 100%)

Para garantir que você nunca terá surpresas na fatura do Google Cloud:
1. Acesse **Faturamento (Billing) -> Orçamentos e alertas (Budgets & alerts)** no console do GCP.
2. Crie um orçamento com valor de **R$ 1,00** ou **$1.00**.
3. Configure alertas por e-mail para 50%, 90% e 100%.
Assim, se qualquer consumo sair da cota gratuita, você será avisado imediatamente.

---

## 🏥 Verificação de Saúde da Aplicação

Após o deploy:
- **Painel Principal:** Acesse a URL gerada pelo Cloud Run.
- **Health Check:** Acesse `https://SUA_URL.run.app/healthz/` (deve retornar `{"status": "healthy", "database": "connected"}`).
- **Admin:** Acesse `https://SUA_URL.run.app/admin/` para gerenciar usuários e cadastros.
