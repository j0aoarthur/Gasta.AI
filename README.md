# Bot Financeiro Pessoal para Telegram 🤖💰

Este é um bot para Telegram desenvolvido em Python que te ajuda a gerenciar suas finanças pessoais de forma simples e conversacional. Ele utiliza a API Gemini do Google para processamento de linguagem natural, permitindo que você registre transações e faça consultas usando frases do dia a dia.

## Funcionalidades ✨

*   **Registro de Transações por Linguagem Natural**:
    *   Basta enviar uma mensagem como "Gastei 50 reais no mercado" ou "Recebi 200 de um freela hoje de manhã".
    *   O bot identifica automaticamente o **tipo** (entrada/saída), **valor**, **categoria**, **descrição** e até mesmo a **data/hora** inferida da transação.
    *   Um fluxo de confirmação com botões inline permite verificar os dados antes de salvar.
*   **Consulta de Saldo**:
    *   Comando `/saldo` para ver seu balanço atual.
*   **Listagem de Transações**:
    *   Comando `/gastos` para ver suas últimas despesas.
    *   Comando `/entradas` para ver suas últimas receitas.
*   **Estatísticas Detalhadas**:
    *   Comando `/estatisticas` para iniciar uma conversa onde você pode perguntar coisas como:
        *   "Quanto gastei com alimentação este mês?"
        *   "Quais foram minhas 5 maiores receitas no ano passado?"
        *   "Total de entradas de 01/01/2024 a 15/01/2024"
    *   O bot interpreta sua pergunta, busca os dados e responde de forma conversacional.
*   **Armazenamento Persistente**:
    *   As transações são salvas em um banco de dados SQLite ([`transacoes.db`](transacoes.db)).
*   **Interface Amigável**:
    *   Respostas formatadas e uso de emojis para uma melhor experiência.

## Configuração ⚙️

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/j0aoarthur/Gasta.AI.git
    cd Gasta.AI
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Variáveis de Ambiente:**
    Crie um arquivo chamado `.env` na raiz do projeto (no mesmo nível que [`main.py`](main.py)) e adicione as seguintes variáveis:

    ```env
    // filepath: .env
    TELEGRAM_BOT_TOKEN="SEU_TOKEN_AQUI_DO_BOTFATHER"
    GEMINI_API_KEY="SUA_API_KEY_AQUI_DO_GOOGLE_AI_STUDIO"
    LLM_MODEL_NAME="gemini-1.5-flash-latest" # Ou outro modelo Gemini compatível
    DATABASE_URL="sqlite:///transacoes.db"
    ```

    *   `TELEGRAM_BOT_TOKEN`: Obtenha este token conversando com o [BotFather](https://t.me/botfather) no Telegram.
    *   `GEMINI_API_KEY`: Sua chave de API para o Google Gemini. Você pode obtê-la no [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   `LLM_MODEL_NAME`: O modelo específico do Gemini que você deseja usar. `gemini-1.5-flash-latest` é uma boa opção para equilíbrio entre custo e performance.
    *   `DATABASE_URL`: A string de conexão para o banco de dados. O padrão `sqlite:///transacoes.db` cria um arquivo SQLite chamado `transacoes.db` na raiz do projeto.

## Como Executar o Bot ▶️

Após configurar o ambiente e as variáveis, execute o bot com o seguinte comando:

```bash
python main.py
```

O bot irá inicializar o banco de dados (se ainda não existir) e começará a escutar por mensagens no Telegram.

## Comandos Disponíveis 🤖

*   `/start` ou `/ajuda`: Mostra a mensagem de boas-vindas e ajuda.
*   `/saldo`: Exibe o saldo atual.
*   `/gastos`: Lista as últimas 5 despesas.
*   `/entradas`: Lista as últimas 5 receitas.
*   `/estatisticas`: Inicia o modo de consulta de estatísticas, onde você pode fazer perguntas em linguagem natural sobre suas finanças.
    *   Dentro do modo de estatísticas, use `/cancelar_estatisticas` para sair.

Além dos comandos, você pode simplesmente enviar uma mensagem descrevendo uma transação financeira para registrá-la.

## Estrutura do Projeto 📁

```
.
├── .env                # Arquivo para variáveis de ambiente (NÃO versionar se contiver segredos)
├── database.py         # Lógica de interação com o banco de dados (SQLAlchemy)
├── llm_client.py       # Cliente para interagir com a API Gemini
├── main.py             # Ponto de entrada principal do bot Telegram
├── requirements.txt    # Lista de dependências Python
├── transacoes.db       # Arquivo do banco de dados SQLite (criado na primeira execução)
├── utils.py            # Funções utilitárias (formatação de moeda, parsing de data)
└── README.md           # Documentação do bot
```