# Moneta

Moneta é uma aplicação web de gestão financeira pessoal desenvolvida para ajudar você a controlar suas contas, despesas, receitas, cartões de crédito de forma intuitiva e eficiente.

## 🚀 Tecnologias Utilizadas

O projeto foi construído utilizando as seguintes tecnologias:
- **Backend:** [Django](https://www.djangoproject.com/) (Python)
- **Frontend Interativo:** [HTMX](https://htmx.org/) e [Alpine.js](https://alpinejs.dev/)
- **Estilização:** [Tailwind CSS](https://tailwindcss.com/)
- **Banco de Dados:** SQLite (padrão) com suporte plug-and-play para PostgreSQL.
- **Tarefas em Background:** [Django-Q](https://django-q.readthedocs.io/) (para Notificações Push automáticas).
- **Gráficos:** [Chart.js](https://www.chartjs.org/)

## 🌟 Funcionalidades

- **Dashboard:** Resumo da sua vida financeira, incluindo saldos, gráficos de fluxo de caixa e listagem de transações recentes.
- **Gestão de Contas (Wallets):**
  - Contas Correntes com suporte a edição de saldo inicial e reajuste dinâmico de saldo.
  - Cartões de Crédito com acompanhamento de limite usado, faturas e fechamento de faturas.
- **Transações:** 
  - Controle completo de Receitas, Despesas e Transferências.
  - Categorização com suporte a cores e ícones personalizados.
  - Filtros avançados para navegação entre meses e tipos de contas.
- **Transações Recorrentes:** Automação de registros que se repetem todo mês.

## 🛠️ Como Executar o Projeto

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/moneta.git
   cd moneta
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # No Windows use: venv\Scripts\activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Execute as migrações do banco de dados:
   ```bash
   python manage.py migrate
   ```

5. Crie um superusuário (opcional, mas recomendado para acessar a área administrativa):
   ```bash
   python manage.py createsuperuser
   ```

6. Inicie o servidor local:
   ```bash
   python manage.py runserver
   ```

7. (Opcional) Em outro terminal, inicie o disparador de tarefas em background para testar as notificações Push:
   ```bash
   python manage.py qcluster
   ```

8. Acesse no navegador: `http://localhost:8000`

## 🚀 Deploy no Google Cloud Run (São Paulo)

O Moneta está configurado para rodar em arquitetura serverless no **Google Cloud Run** na região do Brasil (`southamerica-east1` — São Paulo) com custo ultra-baixo / Free Tier.

### 1. Configurar credenciais no Secret Manager:
```bash
echo -n "postgresql://user:pass@host/moneta_db?sslmode=require" | gcloud secrets create moneta-db-url --data-file=-
echo -n "sua-chave-secreta-django" | gcloud secrets create moneta-secret-key --data-file=-
```

### 2. Realizar o Deploy:
```bash
gcloud run deploy moneta-web \
  --source . \
  --region southamerica-east1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --port 8080 \
  --set-env-vars="DEBUG=False,ALLOWED_HOSTS=*,CSRF_TRUSTED_ORIGINS=https://moneta-web-*.a.run.app" \
  --set-secrets="DATABASE_URL=moneta-db-url:latest,SECRET_KEY=moneta-secret-key:latest"
```

## 🎨 Contribuição

Sinta-se à vontade para enviar *pull requests*. Para grandes mudanças, abra primeiro uma *issue* para discutirmos a funcionalidade proposta.

## 📝 Licença

Desenvolvido com dedicação. Distribuído sob a licença MIT.
