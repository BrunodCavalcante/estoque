# Controle de Estoque - Python + PyQt6

Sistema convertido de Electron/Node para Python + PyQt6, mantendo as funções principais:

- Dashboard
- Cadastro, edição e exclusão de produtos
- Cadastro, edição e exclusão de pessoas
- Entrada de estoque
- Retirada de materiais com subtração automática
- Histórico de movimentações
- Relatório de produtos
- Relatório mensal de saídas
- Log do sistema por dia
- Backup e importação de backup JSON
- Banco SQLite local `estoque.db`

## Como executar

1. Instale o Python 3.10 ou superior.
2. Abra o CMD dentro desta pasta.
3. Execute:

```bash
pip install -r requirements.txt
python main.py
```

## Senha de exclusão

A senha de administrador para excluir produtos e pessoas é:

```text
142536
```

Para alterar, edite a constante `SENHA_ADMIN` no arquivo `main.py`.

## Backup

O banco principal é o arquivo:

```text
estoque.db
```

Para backup manual, basta copiar esse arquivo.
