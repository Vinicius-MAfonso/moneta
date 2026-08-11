# Moneta

Moneta é uma aplicação web de gestão financeira pessoal desenvolvida para ajudar você a controlar suas contas, despesas, receitas, cartões de crédito e investimentos de forma intuitiva e eficiente.

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
  - Contas Correntes, Poupanças e Investimentos com suporte a edição de saldo inicial e reajuste dinâmico de saldo.
  - Cartões de Crédito com acompanhamento de limite usado, faturas e fechamento de faturas.
- **Transações:** 
  - Controle completo de Receitas, Despesas e Transferências.
  - Categorização com suporte a cores e ícones personalizados.
  - Filtros avançados para navegação entre meses e tipos de contas.
- **Transações Recorrentes:** Automação de registros que se repetem todo mês.
- **Investimentos:** Acompanhe a valorização ou desvalorização do seu portfólio.
- **Interface Moderna:** Suporte a Light/Dark mode e layout responsivo.

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

## 🚀 Deploy no Render + Supabase

O Moneta está configurado nativamente para rodar gratuitamente na nuvem usando **Render** (para a aplicação) e **Supabase** (para o banco de dados PostgreSQL). 
Basta conectar este repositório no Render, configurar o `render.yaml` já incluso, e preencher a variável `DATABASE_URL` com as credenciais do seu Supabase.

## 🎨 Contribuição

Sinta-se à vontade para enviar *pull requests*. Para grandes mudanças, abra primeiro uma *issue* para discutirmos a funcionalidade proposta.

## 📝 Licença

Desenvolvido com dedicação. Distribuído sob a licença MIT.
