import html
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QDate, QMarginsF
from PyQt6.QtGui import QAction, QFont, QIntValidator, QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget
)

def caminho_app():
    # Quando estiver em .exe (PyInstaller), usa a pasta onde o executável está.
    # Quando estiver em modo desenvolvimento, usa a pasta deste arquivo.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

APP_DIR = caminho_app()
DB_PATH = APP_DIR / "estoque.db"
SENHA_ADMIN = "apae2235"

# ============================================================
# USUÁRIOS DO SISTEMA
# ============================================================
# Cadastre aqui os usuários que poderão abrir o sistema.
# Modelo:
#     "nome_do_usuario": "senha_do_usuario",
#
# Exemplo para adicionar um novo usuário:
#     "maria": "senha123",
#
# IMPORTANTE:
# - O nome do usuário diferencia maiúsculas/minúsculas.
# - Sempre mantenha vírgula no final de cada linha, exceto se for a última.
# - Ao fechar o sistema, o usuário é deslogado automaticamente.
USUARIOS_SISTEMA = {
    "admin": "apae2235",
    "apae": "apae22",
    "divina": "diva55",
    "bruna": "bruna12",
    "gabriela": "gabi87",
}

USUARIO_LOGADO_ATUAL = "Não identificado"


def agora_ptbr():
    return datetime.now().strftime("%d/%m/%Y, %H:%M:%S")


def data_iso_hoje():
    return datetime.now().strftime("%Y-%m-%d")


def parse_data_ptbr(valor):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(valor or ""))
    if not m:
        return None
    dia, mes, ano = m.groups()
    return f"{ano}-{mes}-{dia}"


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self):
        cur = self.conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            categoria TEXT,
            quantidade INTEGER,
            quantidade_minima INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS pessoas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            setor TEXT
        );
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            produto TEXT,
            pessoa TEXT,
            quantidade INTEGER,
            data TEXT
        );
        CREATE TABLE IF NOT EXISTS logs_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acao TEXT,
            detalhes TEXT,
            data TEXT,
            data_iso TEXT,
            usuario TEXT
        );
        """)
        colunas = [r[1] for r in cur.execute("PRAGMA table_info(produtos)").fetchall()]
        if "quantidade_minima" not in colunas:
            cur.execute("ALTER TABLE produtos ADD COLUMN quantidade_minima INTEGER DEFAULT 0")
        colunas_logs = [r[1] for r in cur.execute("PRAGMA table_info(logs_sistema)").fetchall()]
        if "usuario" not in colunas_logs:
            cur.execute("ALTER TABLE logs_sistema ADD COLUMN usuario TEXT DEFAULT 'Não registrado'")
        self.conn.commit()

    def rows(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def log(self, acao, detalhes, usuario=None):
        usuario_final = str(usuario or USUARIO_LOGADO_ATUAL or "Não identificado")
        self.execute(
            "INSERT INTO logs_sistema (acao, detalhes, data, data_iso, usuario) VALUES (?, ?, ?, ?, ?)",
            (str(acao or ""), str(detalhes or ""), agora_ptbr(), data_iso_hoje(), usuario_final),
        )


class Table(QTableWidget):
    def __init__(self, headers):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def set_data(self, rows):
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(str(value if value is not None else ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.setItem(r, c, item)


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.usuario_logado = None
        self.setWindowTitle("Login - Controle de Estoque")
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        titulo = QLabel("Acesso ao Sistema")
        titulo.setObjectName("loginTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)

        subtitulo = QLabel("Digite seu usuário e senha para continuar")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitulo.setObjectName("loginSubtitle")
        layout.addWidget(subtitulo)

        form = QFormLayout()
        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText("Usuário")
        self.senha = QLineEdit()
        self.senha.setPlaceholderText("Senha")
        self.senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.senha.returnPressed.connect(self.validar_login)
        form.addRow("Usuário:", self.usuario)
        form.addRow("Senha:", self.senha)
        layout.addLayout(form)

        botoes = QHBoxLayout()
        entrar = QPushButton("Entrar")
        sair = QPushButton("Sair")
        sair.setObjectName("secondary")
        entrar.clicked.connect(self.validar_login)
        sair.clicked.connect(self.reject)
        botoes.addWidget(entrar)
        botoes.addWidget(sair)
        layout.addLayout(botoes)

        self.setStyleSheet("""
        QDialog{font-family:Arial;font-size:14px;background:#f2f4f7;color:#222;}
        #loginTitle{font-size:24px;font-weight:bold;color:#1d4d2f;background:transparent;margin-top:8px;}
        #loginSubtitle{font-size:13px;color:#555;background:transparent;margin-bottom:12px;}
        QLineEdit{background:#ffffff;color:#111111;border:1px solid #b8c0cc;border-radius:8px;padding:8px;min-height:28px;selection-background-color:#2f7a49;selection-color:#ffffff;}
        QLineEdit:focus{border:2px solid #2f7a49;background:#ffffff;color:#111111;}
        QLineEdit::placeholder{color:#777777;}
        QPushButton{background:#2f7a49;color:white;border:none;border-radius:8px;padding:9px 14px;font-size:14px;min-height:32px;}
        QPushButton:hover{background:#368c55;}
        QPushButton#secondary{background:#777;}
        QLabel{background:transparent;}
        QMessageBox{background:#ffffff;color:#111111;}
        QMessageBox QLabel{background:transparent;color:#111111;font-size:13px;font-weight:normal;}
        QMessageBox QPushButton{background:#2f7a49;color:#ffffff;border:none;border-radius:7px;padding:7px 14px;min-width:80px;}
        QMessageBox QPushButton:hover{background:#368c55;}
        QInputDialog{background:#ffffff;color:#111111;}
        QInputDialog QLabel{background:transparent;color:#111111;font-size:13px;}
        QInputDialog QLineEdit{background:#ffffff;color:#111111;border:1px solid #b8c0cc;border-radius:8px;padding:8px;}
        QInputDialog QPushButton{background:#2f7a49;color:#ffffff;border:none;border-radius:7px;padding:7px 14px;min-width:80px;}
        """)

    def validar_login(self):
        usuario = self.usuario.text().strip()
        senha = self.senha.text().strip()
        if USUARIOS_SISTEMA.get(usuario) == senha:
            self.usuario_logado = usuario
            self.accept()
            return
        QMessageBox.warning(
            self,
            "Login inválido",
            "Usuário ou senha incorretos. Verifique os dados digitados e tente novamente."
        )
        self.senha.clear()
        self.senha.setFocus()


class MainWindow(QMainWindow):
    def __init__(self, usuario_logado):
        super().__init__()
        global USUARIO_LOGADO_ATUAL
        self.usuario_logado = usuario_logado
        USUARIO_LOGADO_ATUAL = usuario_logado
        self.db = Database()
        self.produtos = []
        self.pessoas = []
        self.produto_edit_id = None
        self.pessoa_edit_id = None
        self.retirada_atual = []
        self.historico = []
        self.indice_pagina_retirada = None
        self.setWindowTitle("Controle de Estoque")
        self.resize(1400, 900)
        self.build_ui()
        self.apply_style()
        self.refresh_all()

    def build_ui(self):
        root = QWidget()
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        side.setSpacing(10)
        titulo = QLabel("ESTOQUE")
        titulo.setObjectName("sidebarTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setMinimumHeight(48)
        side.addWidget(titulo)
        usuario_label = QLabel(f"Usuário: {self.usuario_logado}")
        usuario_label.setObjectName("sidebarUser")
        usuario_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(usuario_label)

        self.stack = QStackedWidget()
        pages = [
            ("Dashboard", self.page_dashboard()),
            ("Produtos", self.page_produtos()),
            ("Pessoas", self.page_pessoas()),
            ("Retirada", self.page_retirada()),
            ("Histórico", self.page_historico()),
            ("Relatórios", self.page_relatorios()),
            ("Backup", self.page_backup()),
        ]
        self.indice_pagina_retirada = 3
        self.stack.currentChanged.connect(self.ao_trocar_pagina)
        for i, (name, page) in enumerate(pages):
            btn = QPushButton(name)
            btn.setObjectName("sideButton")
            btn.setMinimumHeight(46)
            btn.setMaximumHeight(46)
            btn.clicked.connect(lambda _, idx=i: self.stack.setCurrentIndex(idx))
            side.addWidget(btn)
            self.stack.addWidget(page)
        side.addStretch()
        rodape = QLabel("© 2026 Bruno Cavalcante")
        rodape.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rodape.setStyleSheet("color:white;font-size:9px;background:transparent;border:none;")
        side.addWidget(rodape)

        main.addWidget(sidebar, 0)
        main.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def title(self, text):
        label = QLabel(text)
        label.setObjectName("pageTitle")
        return label

    def page_dashboard(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Dashboard"))
        cards = QHBoxLayout()
        self.card_produtos = self.card("Total Produtos", "0")
        self.card_itens = self.card("Itens em Estoque", "0")
        cards.addWidget(self.card_produtos); cards.addWidget(self.card_itens); cards.addStretch()
        layout.addLayout(cards); layout.addStretch()
        return w

    def card(self, title, value):
        box = QFrame(); box.setObjectName("card"); lay = QVBoxLayout(box)
        l1 = QLabel(title); l1.setObjectName("cardTitle")
        l2 = QLabel(value); l2.setObjectName("cardValue")
        lay.addWidget(l1); lay.addWidget(l2)
        return box

    def page_produtos(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Produtos"))
        form = QGroupBox("Cadastrar produto"); grid = QGridLayout(form)
        self.prod_nome = QLineEdit(); self.prod_nome.setPlaceholderText("Nome")
        self.prod_categoria = QLineEdit(); self.prod_categoria.setPlaceholderText("Categoria")
        self.prod_qtd = QLineEdit(); self.prod_qtd.setPlaceholderText("Quantidade atual"); self.prod_qtd.setValidator(QIntValidator(0, 10_000_000))
        self.prod_min = QLineEdit(); self.prod_min.setPlaceholderText("Quantidade mínima / média mensal"); self.prod_min.setValidator(QIntValidator(0, 10_000_000))
        self.btn_prod_salvar = QPushButton("Salvar"); self.btn_prod_salvar.clicked.connect(self.salvar_produto)
        self.btn_prod_cancelar = QPushButton("Cancelar edição"); self.btn_prod_cancelar.setObjectName("secondary"); self.btn_prod_cancelar.clicked.connect(self.cancelar_produto)
        grid.addWidget(self.prod_nome,0,0); grid.addWidget(self.prod_categoria,0,1); grid.addWidget(self.prod_qtd,0,2); grid.addWidget(self.prod_min,0,3)
        grid.addWidget(self.btn_prod_salvar,1,0); grid.addWidget(self.btn_prod_cancelar,1,1)
        layout.addWidget(form)
        entrada = QGroupBox("Entrada / atualização de estoque"); eg = QHBoxLayout(entrada)
        self.entrada_prod = QComboBox(); self.entrada_prod.addItem("Selecione o produto", "")
        self.entrada_qtd = QLineEdit(); self.entrada_qtd.setPlaceholderText("Quantidade que chegou"); self.entrada_qtd.setValidator(QIntValidator(1, 10_000_000))
        b = QPushButton("Adicionar ao estoque"); b.clicked.connect(self.entrada_estoque)
        eg.addWidget(self.entrada_prod); eg.addWidget(self.entrada_qtd); eg.addWidget(b)
        layout.addWidget(entrada)
        self.tabela_produtos = Table(["Nome", "Categoria", "Quantidade atual", "Qtd. mínima / média mensal"])
        self.tabela_produtos.cellDoubleClicked.connect(lambda row, col: self.editar_produto(row))
        layout.addWidget(self.tabela_produtos)
        actions = QHBoxLayout(); ed=QPushButton("Editar selecionado"); ex=QPushButton("Excluir selecionado"); ex.setObjectName("danger")
        ed.clicked.connect(self.editar_produto_selecionado); ex.clicked.connect(self.excluir_produto_selecionado)
        actions.addWidget(ed); actions.addWidget(ex); actions.addStretch(); layout.addLayout(actions)
        return w

    def page_pessoas(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Pessoas"))
        form = QGroupBox("Cadastrar pessoa"); h = QHBoxLayout(form)
        self.pessoa_nome = QLineEdit(); self.pessoa_nome.setPlaceholderText("Nome")
        self.pessoa_setor = QLineEdit(); self.pessoa_setor.setPlaceholderText("Setor")
        self.btn_pessoa_salvar = QPushButton("Salvar"); self.btn_pessoa_salvar.clicked.connect(self.salvar_pessoa)
        self.btn_pessoa_cancelar = QPushButton("Cancelar edição"); self.btn_pessoa_cancelar.setObjectName("secondary"); self.btn_pessoa_cancelar.clicked.connect(self.cancelar_pessoa)
        h.addWidget(self.pessoa_nome); h.addWidget(self.pessoa_setor); h.addWidget(self.btn_pessoa_salvar); h.addWidget(self.btn_pessoa_cancelar)
        layout.addWidget(form)
        self.tabela_pessoas = Table(["Nome", "Setor"]); self.tabela_pessoas.cellDoubleClicked.connect(lambda row, col: self.editar_pessoa(row))
        layout.addWidget(self.tabela_pessoas)
        actions = QHBoxLayout(); ed=QPushButton("Editar selecionado"); ex=QPushButton("Excluir selecionado"); ex.setObjectName("danger")
        ed.clicked.connect(self.editar_pessoa_selecionada); ex.clicked.connect(self.excluir_pessoa_selecionada)
        actions.addWidget(ed); actions.addWidget(ex); actions.addStretch(); layout.addLayout(actions)
        return w

    def page_retirada(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Retirada"))
        box = QGroupBox("Registrar retirada"); h = QHBoxLayout(box)
        self.ret_prod = QComboBox(); self.ret_prod.addItem("Selecione o produto", "")
        self.ret_pessoa = QComboBox(); self.ret_pessoa.addItem("Selecione a pessoa", "")
        self.ret_qtd = QLineEdit(); self.ret_qtd.setPlaceholderText("Quantidade"); self.ret_qtd.setValidator(QIntValidator(1, 10_000_000))
        b = QPushButton("Registrar"); b.clicked.connect(self.retirada)
        h.addWidget(self.ret_prod); h.addWidget(self.ret_pessoa); h.addWidget(self.ret_qtd); h.addWidget(b)
        layout.addWidget(box)

        resumo = QGroupBox("Relatório da retirada atual")
        rv = QVBoxLayout(resumo)
        self.retirada_resumo = QTextEdit()
        self.retirada_resumo.setReadOnly(True)
        self.retirada_resumo.setPlaceholderText("As retiradas registradas nesta tela aparecerão aqui. Ao sair da página, este relatório será reiniciado.")
        rv.addWidget(self.retirada_resumo)
        layout.addWidget(resumo)
        layout.addStretch()
        return w

    def page_historico(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Histórico"))
        self.tabela_historico = Table(["Tipo", "Produto", "Pessoa", "Quantidade", "Data"])
        self.tabela_historico.cellDoubleClicked.connect(lambda row, col: self.editar_retirada(row))
        layout.addWidget(self.tabela_historico)
        actions = QHBoxLayout()
        editar = QPushButton("Editar retirada selecionada")
        editar.setObjectName("secondary")
        editar.clicked.connect(self.editar_retirada_selecionada)
        actions.addWidget(editar)
        actions.addStretch()
        layout.addLayout(actions)
        return w

    def page_relatorios(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Relatórios"))
        gp = QGroupBox("Relatório de produtos cadastrados"); hp=QHBoxLayout(gp)
        self.rel_ordem = QComboBox(); self.rel_ordem.addItems(["Ordem alfabética", "Menor quantidade para maior", "Maior quantidade para menor"])
        bp=QPushButton("Gerar relatório"); bp.clicked.connect(self.gerar_relatorio_produtos)
        ip=QPushButton("Imprimir / salvar PDF"); ip.setObjectName("secondary"); ip.clicked.connect(self.imprimir_relatorio)
        hp.addWidget(self.rel_ordem); hp.addWidget(bp); hp.addWidget(ip); layout.addWidget(gp)
        gs = QGroupBox("Relatório mensal de saída de produtos"); hs=QHBoxLayout(gs)
        self.rel_mes = QLineEdit(datetime.now().strftime("%Y-%m")); self.rel_mes.setPlaceholderText("AAAA-MM")
        bs=QPushButton("Gerar relatório"); bs.clicked.connect(self.gerar_relatorio_saidas)
        hs.addWidget(self.rel_mes); hs.addWidget(bs); layout.addWidget(gs)
        gl = QGroupBox("Log do sistema por dia"); hl=QHBoxLayout(gl)
        self.rel_data = QDateEdit(QDate.currentDate()); self.rel_data.setCalendarPopup(True); self.rel_data.setDisplayFormat("yyyy-MM-dd")
        bl=QPushButton("Gerar relatório"); bl.clicked.connect(self.gerar_relatorio_logs)
        hl.addWidget(self.rel_data); hl.addWidget(bl); layout.addWidget(gl)
        self.relatorio_texto = QTextEdit(); self.relatorio_texto.setReadOnly(True)
        layout.addWidget(self.relatorio_texto)
        return w

    def page_backup(self):
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(30,30,30,30)
        layout.addWidget(self.title("Backup"))
        g1=QGroupBox("Gerar backup"); h1=QVBoxLayout(g1); h1.addWidget(QLabel("Use esta opção para salvar uma cópia dos produtos, pessoas e histórico de movimentações.")); b1=QPushButton("Gerar arquivo de backup"); b1.clicked.connect(self.gerar_backup); h1.addWidget(b1)
        g2=QGroupBox("Importar backup"); h2=QVBoxLayout(g2); h2.addWidget(QLabel("A importação substitui os dados atuais pelos dados do arquivo escolhido.")); b2=QPushButton("Importar backup"); b2.setObjectName("danger"); b2.clicked.connect(self.importar_backup); h2.addWidget(b2)
        layout.addWidget(g1); layout.addWidget(g2); layout.addStretch(); return w

    def ao_trocar_pagina(self, indice):
        if self.indice_pagina_retirada is not None and indice != self.indice_pagina_retirada:
            self.limpar_relatorio_retirada_atual()

    def limpar_relatorio_retirada_atual(self):
        self.retirada_atual = []
        if hasattr(self, 'retirada_resumo'):
            self.retirada_resumo.clear()

    def atualizar_relatorio_retirada_atual(self):
        if not hasattr(self, 'retirada_resumo'):
            return
        if not self.retirada_atual:
            self.retirada_resumo.clear()
            return
        total = sum(item['quantidade'] for item in self.retirada_atual)
        linhas = [
            'Relatório temporário da retirada atual',
            f'Total de registros: {len(self.retirada_atual)}',
            f'Total de itens retirados: {total}',
            '',
            'Horário | Produto | Pessoa | Quantidade',
            '-' * 80,
        ]
        for item in self.retirada_atual:
            linhas.append(f"{item['horario']} | {item['produto']} | {item['pessoa']} | {item['quantidade']}")
        self.retirada_resumo.setPlainText('\n'.join(linhas))

    def selected_row(self, table):
        rows = table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def refresh_all(self):
        self.carregar_produtos(); self.carregar_pessoas(); self.carregar_historico(); self.cancelar_produto(); self.cancelar_pessoa()

    def carregar_produtos(self):
        self.produtos = self.db.rows("SELECT * FROM produtos ORDER BY nome")
        self.tabela_produtos.set_data([[p['nome'], p['categoria'], p['quantidade'], p.get('quantidade_minima',0) or 0] for p in self.produtos])
        self.entrada_prod.clear(); self.ret_prod.clear()
        self.entrada_prod.addItem("Selecione o produto", ""); self.ret_prod.addItem("Selecione o produto", "")
        for p in self.produtos:
            label = f"{p['nome']} - estoque: {p['quantidade']}"
            self.entrada_prod.addItem(label, p['nome']); self.ret_prod.addItem(label, p['nome'])
        total = sum(int(p.get('quantidade') or 0) for p in self.produtos)
        self.card_produtos.findChildren(QLabel)[1].setText(str(len(self.produtos)))
        self.card_itens.findChildren(QLabel)[1].setText(str(total))

    def carregar_pessoas(self):
        self.pessoas = self.db.rows("SELECT * FROM pessoas ORDER BY nome")
        self.tabela_pessoas.set_data([[p['nome'], p['setor']] for p in self.pessoas])
        self.ret_pessoa.clear(); self.ret_pessoa.addItem("Selecione a pessoa", "")
        for p in self.pessoas:
            self.ret_pessoa.addItem(f"{p['nome']} - {p['setor']}", p['nome'])

    def carregar_historico(self):
        self.historico = self.db.rows("SELECT * FROM movimentacoes ORDER BY id DESC")
        self.tabela_historico.set_data([[h['tipo'], h['produto'], h['pessoa'], h['quantidade'], h['data']] for h in self.historico])

    def salvar_produto(self):
        nome, cat = self.prod_nome.text().strip(), self.prod_categoria.text().strip()
        qtd = int(self.prod_qtd.text() or 0)
        qtd_min = int(self.prod_min.text() or 0)
        if not nome or not cat:
            return self.erro("Preencha nome, categoria, quantidade atual e quantidade mínima/média mensal válidas.")
        if self.produto_edit_id:
            self.db.execute("UPDATE produtos SET nome=?, categoria=?, quantidade=?, quantidade_minima=? WHERE id=?", (nome, cat, qtd, qtd_min, self.produto_edit_id))
            self.db.log("Produto editado", f"Produto: {nome} | Categoria: {cat} | Quantidade: {qtd} | Qtd. mínima/média mensal: {qtd_min}")
        else:
            self.db.execute("INSERT INTO produtos (nome, categoria, quantidade, quantidade_minima) VALUES (?, ?, ?, ?)", (nome, cat, qtd, qtd_min))
            self.db.log("Produto cadastrado", f"Produto: {nome} | Categoria: {cat} | Quantidade: {qtd} | Qtd. mínima/média mensal: {qtd_min}")
        self.cancelar_produto(); self.carregar_produtos(); self.info("Produto salvo com sucesso.")

    def editar_produto(self, row):
        if row < 0 or row >= len(self.produtos): return
        p = self.produtos[row]; self.produto_edit_id = p['id']
        self.prod_nome.setText(p['nome']); self.prod_categoria.setText(p['categoria']); self.prod_qtd.setText(str(int(p['quantidade'] or 0))); self.prod_min.setText(str(int(p.get('quantidade_minima') or 0))); self.btn_prod_salvar.setText("Atualizar")

    def editar_produto_selecionado(self): self.editar_produto(self.selected_row(self.tabela_produtos))

    def cancelar_produto(self):
        self.produto_edit_id = None; self.prod_nome.clear(); self.prod_categoria.clear(); self.prod_qtd.clear(); self.prod_min.clear(); self.btn_prod_salvar.setText("Salvar")

    def excluir_produto_selecionado(self):
        row = self.selected_row(self.tabela_produtos)
        if row < 0: return self.erro("Selecione um produto para excluir.")
        senha, ok = self.solicitar_senha()
        if not ok: return
        if senha != SENHA_ADMIN: return self.erro("Senha de administrador incorreta.")
        p = self.produtos[row]
        if QMessageBox.question(self, "Confirmar exclusão", f"Excluir o produto {p['nome']}?") != QMessageBox.StandardButton.Yes: return
        self.db.execute("DELETE FROM produtos WHERE id=?", (p['id'],))
        self.db.log("Produto excluído", f"Produto: {p['nome']} | Categoria: {p['categoria']} | Quantidade: {p['quantidade']}")
        self.cancelar_produto(); self.carregar_produtos(); self.info("Produto excluído com sucesso.")

    def entrada_estoque(self):
        produto = self.entrada_prod.currentData()
        qtd_texto = self.entrada_qtd.text().strip()
        qtd = int(qtd_texto) if qtd_texto.isdigit() else 0
        if not produto or qtd <= 0: return self.erro("Selecione o produto e informe uma quantidade válida.")
        item = self.db.one("SELECT * FROM produtos WHERE nome=?", (produto,))
        if not item: return self.erro("Produto não encontrado.")
        cur = self.db.conn.cursor(); cur.execute("UPDATE produtos SET quantidade=quantidade+? WHERE nome=?", (qtd, produto)); cur.execute("INSERT INTO movimentacoes (tipo, produto, pessoa, quantidade, data) VALUES (?, ?, ?, ?, ?)", ("ENTRADA", produto, "", qtd, agora_ptbr())); self.db.conn.commit()
        self.db.log("Entrada de estoque", f"Produto: {produto} | Quantidade adicionada: {qtd}")
        self.entrada_qtd.clear(); self.carregar_produtos(); self.carregar_historico(); self.info("Estoque atualizado")

    def salvar_pessoa(self):
        nome, setor = self.pessoa_nome.text().strip(), self.pessoa_setor.text().strip()
        if not nome or not setor: return self.erro("Preencha nome e setor.")
        if self.pessoa_edit_id:
            self.db.execute("UPDATE pessoas SET nome=?, setor=? WHERE id=?", (nome, setor, self.pessoa_edit_id)); self.db.log("Pessoa editada", f"Pessoa: {nome} | Setor: {setor}")
        else:
            self.db.execute("INSERT INTO pessoas (nome, setor) VALUES (?, ?)", (nome, setor)); self.db.log("Pessoa cadastrada", f"Pessoa: {nome} | Setor: {setor}")
        self.cancelar_pessoa(); self.carregar_pessoas(); self.info("Pessoa salva com sucesso.")

    def editar_pessoa(self, row):
        if row < 0 or row >= len(self.pessoas): return
        p = self.pessoas[row]; self.pessoa_edit_id = p['id']; self.pessoa_nome.setText(p['nome']); self.pessoa_setor.setText(p['setor']); self.btn_pessoa_salvar.setText("Atualizar")

    def editar_pessoa_selecionada(self): self.editar_pessoa(self.selected_row(self.tabela_pessoas))

    def cancelar_pessoa(self):
        self.pessoa_edit_id = None; self.pessoa_nome.clear(); self.pessoa_setor.clear(); self.btn_pessoa_salvar.setText("Salvar")

    def excluir_pessoa_selecionada(self):
        row = self.selected_row(self.tabela_pessoas)
        if row < 0: return self.erro("Selecione uma pessoa para excluir.")
        senha, ok = self.solicitar_senha()
        if not ok: return
        if senha != SENHA_ADMIN: return self.erro("Senha de administrador incorreta.")
        p = self.pessoas[row]
        if QMessageBox.question(self, "Confirmar exclusão", f"Excluir a pessoa {p['nome']}?") != QMessageBox.StandardButton.Yes: return
        self.db.execute("DELETE FROM pessoas WHERE id=?", (p['id'],)); self.db.log("Pessoa excluída", f"Pessoa: {p['nome']} | Setor: {p['setor']}")
        self.cancelar_pessoa(); self.carregar_pessoas(); self.info("Pessoa excluída com sucesso.")

    def retirada(self):
        produto, pessoa = self.ret_prod.currentData(), self.ret_pessoa.currentData()
        qtd_texto = self.ret_qtd.text().strip()
        qtd = int(qtd_texto) if qtd_texto.isdigit() else 0
        if not produto or not pessoa or qtd <= 0: return self.erro("Selecione produto, pessoa e informe uma quantidade válida.")
        item = self.db.one("SELECT * FROM produtos WHERE nome=?", (produto,))
        if not item: return self.erro("Produto não encontrado.")
        if int(item['quantidade'] or 0) < qtd: return self.erro("Estoque insuficiente.")
        data_hora = agora_ptbr()
        cur = self.db.conn.cursor(); cur.execute("UPDATE produtos SET quantidade=quantidade-? WHERE nome=?", (qtd, produto)); cur.execute("INSERT INTO movimentacoes (tipo, produto, pessoa, quantidade, data) VALUES (?, ?, ?, ?, ?)", ("RETIRADA", produto, pessoa, qtd, data_hora)); self.db.conn.commit()
        self.db.log("Retirada de produto", f"Produto: {produto} | Pessoa: {pessoa} | Quantidade: {qtd}")
        self.retirada_atual.append({"horario": data_hora, "produto": produto, "pessoa": pessoa, "quantidade": qtd})
        self.atualizar_relatorio_retirada_atual()
        self.ret_prod.setCurrentIndex(0); self.ret_pessoa.setCurrentIndex(0); self.ret_qtd.clear(); self.carregar_produtos(); self.carregar_historico()

    def editar_retirada_selecionada(self):
        self.editar_retirada(self.selected_row(self.tabela_historico))

    def editar_retirada(self, row):
        if row < 0 or row >= len(self.historico):
            return self.erro("Selecione uma retirada no histórico para editar.")
        mov = self.historico[row]
        if mov.get('tipo') != 'RETIRADA':
            return self.erro("Somente movimentações do tipo RETIRADA podem ser editadas por esta opção.")

        senha, ok = self.solicitar_senha()
        if not ok:
            return
        if senha != SENHA_ADMIN:
            return self.erro("Senha de administrador incorreta.")

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar retirada")
        form = QFormLayout(dialog)

        produto_combo = QComboBox()
        produto_combo.addItem("Selecione o produto", "")
        for p in self.db.rows("SELECT * FROM produtos ORDER BY nome"):
            produto_combo.addItem(f"{p['nome']} - estoque: {p['quantidade']}", p['nome'])

        pessoa_combo = QComboBox()
        pessoa_combo.addItem("Selecione a pessoa", "")
        for p in self.db.rows("SELECT * FROM pessoas ORDER BY nome"):
            pessoa_combo.addItem(f"{p['nome']} - {p['setor']}", p['nome'])

        qtd_edit = QLineEdit(str(int(mov.get('quantidade') or 0)))
        qtd_edit.setValidator(QIntValidator(1, 10_000_000))

        self.selecionar_combo_por_valor(produto_combo, mov.get('produto'))
        self.selecionar_combo_por_valor(pessoa_combo, mov.get('pessoa'))

        form.addRow("Produto retirado:", produto_combo)
        form.addRow("Quem retirou:", pessoa_combo)
        form.addRow("Quantidade retirada:", qtd_edit)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(dialog.accept)
        botoes.rejected.connect(dialog.reject)
        form.addRow(botoes)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        novo_produto = produto_combo.currentData()
        nova_pessoa = pessoa_combo.currentData()
        qtd_texto = qtd_edit.text().strip()
        nova_qtd = int(qtd_texto) if qtd_texto.isdigit() else 0
        if not novo_produto or not nova_pessoa or nova_qtd <= 0:
            return self.erro("Selecione produto, pessoa e informe uma quantidade válida.")

        produto_antigo = mov.get('produto')
        pessoa_antiga = mov.get('pessoa')
        qtd_antiga = int(mov.get('quantidade') or 0)

        antigo = self.db.one("SELECT * FROM produtos WHERE nome=?", (produto_antigo,))
        novo = self.db.one("SELECT * FROM produtos WHERE nome=?", (novo_produto,))
        if not antigo:
            return self.erro("O produto original da retirada não existe mais no cadastro. Não é possível recalcular o estoque com segurança.")
        if not novo:
            return self.erro("Produto selecionado não encontrado.")

        estoque_novo_disponivel = int(novo['quantidade'] or 0)
        if produto_antigo == novo_produto:
            estoque_novo_disponivel += qtd_antiga
        if estoque_novo_disponivel < nova_qtd:
            return self.erro("Estoque insuficiente para salvar a alteração da retirada.")

        try:
            cur = self.db.conn.cursor()
            cur.execute("UPDATE produtos SET quantidade=quantidade+? WHERE nome=?", (qtd_antiga, produto_antigo))
            cur.execute("UPDATE produtos SET quantidade=quantidade-? WHERE nome=?", (nova_qtd, novo_produto))
            cur.execute(
                "UPDATE movimentacoes SET produto=?, pessoa=?, quantidade=? WHERE id=?",
                (novo_produto, nova_pessoa, nova_qtd, mov['id'])
            )
            self.db.conn.commit()
            self.db.log(
                "Retirada editada",
                f"Antes: Produto: {produto_antigo} | Pessoa: {pessoa_antiga} | Quantidade: {qtd_antiga} || "
                f"Depois: Produto: {novo_produto} | Pessoa: {nova_pessoa} | Quantidade: {nova_qtd}"
            )
            self.carregar_produtos()
            self.carregar_historico()
            self.info("Retirada editada com sucesso.")
        except Exception as e:
            self.db.conn.rollback()
            self.erro("Não foi possível editar a retirada: " + str(e))

    def selecionar_combo_por_valor(self, combo, valor):
        for i in range(combo.count()):
            if combo.itemData(i) == valor:
                combo.setCurrentIndex(i)
                return

    def gerar_relatorio_produtos(self):
        produtos = self.db.rows("SELECT * FROM produtos ORDER BY nome")
        idx = self.rel_ordem.currentIndex()
        if idx == 1: produtos.sort(key=lambda p: int(p['quantidade'] or 0))
        elif idx == 2: produtos.sort(key=lambda p: int(p['quantidade'] or 0), reverse=True)
        else: produtos.sort(key=lambda p: str(p['nome']).lower())
        total = sum(int(p['quantidade'] or 0) for p in produtos)
        texto = f"Relatório de produtos cadastrados\nGerado em: {agora_ptbr()}\nTotal de produtos: {len(produtos)} | Total de itens em estoque: {total}\nOrdenação: {self.rel_ordem.currentText()}\n\n"
        texto += "Produto | Categoria | Quantidade atual | Qtd. mínima / média mensal\n"
        texto += "-" * 90 + "\n"
        texto += "\n".join(f"{p['nome']} | {p['categoria']} | {p['quantidade']} | {p.get('quantidade_minima',0) or 0}" for p in produtos) or "Nenhum produto cadastrado."
        self.relatorio_texto.setPlainText(texto)

    def gerar_relatorio_saidas(self):
        mes = self.rel_mes.text().strip()
        if not re.match(r"^\d{4}-\d{2}$", mes): return self.erro("Informe o mês no formato AAAA-MM.")
        saidas = []
        for item in self.db.rows("SELECT * FROM movimentacoes ORDER BY id DESC"):
            data_iso = parse_data_ptbr(item['data'])
            if item['tipo'] == 'RETIRADA' and data_iso and data_iso.startswith(mes): saidas.append(item)
        por_prod = {}
        total = 0
        for s in saidas:
            q = int(s['quantidade'] or 0); total += q; por_prod[s['produto']] = por_prod.get(s['produto'], 0) + q
        texto = f"Relatório mensal de saída de produtos\nMês: {mes[5:7]}/{mes[:4]}\nGerado em: {agora_ptbr()}\nTotal de retiradas: {len(saidas)} | Total de itens retirados: {total}\n\nResumo por produto\n"
        texto += "\n".join(f"{p}: {q}" for p, q in por_prod.items()) or "Nenhuma saída registrada neste mês."
        texto += "\n\nDetalhamento das saídas\nData | Produto | Pessoa | Quantidade\n" + "-"*80 + "\n"
        texto += "\n".join(f"{s['data']} | {s['produto']} | {s['pessoa']} | {s['quantidade']}" for s in saidas) or "Nenhuma saída registrada neste mês."
        self.relatorio_texto.setPlainText(texto)

    def gerar_relatorio_logs(self):
        data = self.rel_data.date().toString("yyyy-MM-dd")
        logs = self.db.rows("SELECT * FROM logs_sistema WHERE data_iso=? ORDER BY id DESC", (data,))
        d, m, a = data[8:10], data[5:7], data[:4]
        texto = f"Log do sistema - {d}/{m}/{a}\nGerado em: {agora_ptbr()}\nTotal de alterações no dia: {len(logs)}\n\nData e horário | Usuário | Alteração | Detalhes\n" + "-"*120 + "\n"
        texto += "\n".join(f"{l['data']} | {l.get('usuario') or 'Não registrado'} | {l['acao']} | {l['detalhes']}" for l in logs) or "Nenhum registro encontrado para esta data."
        self.relatorio_texto.setPlainText(texto)

    def imprimir_relatorio(self):
        texto = self.relatorio_texto.toPlainText().strip()
        if not texto:
            return self.erro("Gere o relatório antes de imprimir.")

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

        dialog = QPrintDialog(printer, self)
        if dialog.exec():
            documento = QTextDocument()
            documento.setDefaultFont(QFont("Arial", 9))
            documento.setHtml(self.html_relatorio_para_impressao(texto))
            documento.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
            documento.print(printer)

    def html_relatorio_para_impressao(self, texto):
        linhas = texto.splitlines()
        partes = [
            "<html><head><meta charset='utf-8'><style>",
            "body{font-family:Arial,Helvetica,sans-serif;font-size:9pt;color:#111;}",
            "h1{font-size:15pt;margin:0 0 10px 0;color:#1d4d2f;}",
            "p{margin:3px 0;line-height:1.35;}",
            ".secao{font-weight:bold;margin-top:12px;color:#1d4d2f;}",
            "table{width:100%;border-collapse:collapse;table-layout:fixed;margin:8px 0 12px 0;}",
            "th{background:#e9f2ec;font-weight:bold;}",
            "th,td{border:1px solid #cfd8d3;padding:5px;vertical-align:top;word-wrap:break-word;}",
            "</style></head><body>"
        ]
        i = 0
        titulo_adicionado = False
        while i < len(linhas):
            linha = linhas[i].strip()
            if not linha:
                i += 1
                continue
            proxima = linhas[i + 1].strip() if i + 1 < len(linhas) else ""
            if " | " in linha and proxima and set(proxima.replace("|", "").replace(" ", "")) <= {"-"}:
                cabecalho = [html.escape(c.strip()) for c in linha.split("|")]
                i += 2
                rows = []
                while i < len(linhas) and " | " in linhas[i]:
                    rows.append([html.escape(c.strip()) for c in linhas[i].split("|")])
                    i += 1
                partes.append("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cabecalho) + "</tr></thead><tbody>")
                for row in rows:
                    while len(row) < len(cabecalho):
                        row.append("")
                    partes.append("<tr>" + "".join(f"<td>{c}</td>" for c in row[:len(cabecalho)]) + "</tr>")
                if not rows:
                    partes.append(f"<tr><td colspan='{len(cabecalho)}'>Nenhum registro encontrado.</td></tr>")
                partes.append("</tbody></table>")
                continue
            if set(linha.replace(" ", "")) <= {"-"}:
                i += 1
                continue
            if not titulo_adicionado:
                partes.append(f"<h1>{html.escape(linha)}</h1>")
                titulo_adicionado = True
            elif i + 1 < len(linhas) and linhas[i + 1].strip() and " | " not in linhas[i + 1] and not linhas[i + 1].startswith("-") and not ":" in linha and len(linha) < 60:
                partes.append(f"<p class='secao'>{html.escape(linha)}</p>")
            else:
                partes.append(f"<p>{html.escape(linha)}</p>")
            i += 1
        partes.append("</body></html>")
        return "".join(partes)

    def gerar_backup(self):
        backup = {
            "versao": 2, "geradoEm": agora_ptbr(),
            "produtos": self.db.rows("SELECT * FROM produtos ORDER BY id"),
            "pessoas": self.db.rows("SELECT * FROM pessoas ORDER BY id"),
            "movimentacoes": self.db.rows("SELECT * FROM movimentacoes ORDER BY id"),
            "logs_sistema": self.db.rows("SELECT * FROM logs_sistema ORDER BY id"),
        }
        default = APP_DIR / f"backup-estoque-{data_iso_hoje()}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar backup", str(default), "JSON (*.json)")
        if not path: return
        with open(path, "w", encoding="utf-8") as f: json.dump(backup, f, ensure_ascii=False, indent=2)
        self.info("Backup gerado com sucesso.")

    def importar_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar backup", str(APP_DIR), "JSON (*.json)")
        if not path: return
        if QMessageBox.question(self, "Importar backup", "A importação vai substituir os dados atuais. Deseja continuar?") != QMessageBox.StandardButton.Yes: return
        try:
            with open(path, "r", encoding="utf-8") as f: backup = json.load(f)
            if not all(isinstance(backup.get(k), list) for k in ["produtos", "pessoas", "movimentacoes"]): raise ValueError("Arquivo de backup inválido.")
            cur = self.db.conn.cursor(); cur.execute("DELETE FROM logs_sistema"); cur.execute("DELETE FROM movimentacoes"); cur.execute("DELETE FROM produtos"); cur.execute("DELETE FROM pessoas")
            for p in backup['produtos']: cur.execute("INSERT INTO produtos (id,nome,categoria,quantidade,quantidade_minima) VALUES (?,?,?,?,?)", (int(p.get('id') or 0), str(p.get('nome','')), str(p.get('categoria','')), int(p.get('quantidade') or 0), int(p.get('quantidade_minima') or p.get('quantidadeMinima') or 0)))
            for p in backup['pessoas']: cur.execute("INSERT INTO pessoas (id,nome,setor) VALUES (?,?,?)", (int(p.get('id') or 0), str(p.get('nome','')), str(p.get('setor',''))))
            for m in backup['movimentacoes']: cur.execute("INSERT INTO movimentacoes (id,tipo,produto,pessoa,quantidade,data) VALUES (?,?,?,?,?,?)", (int(m.get('id') or 0), str(m.get('tipo','')), str(m.get('produto','')), str(m.get('pessoa','')), int(m.get('quantidade') or 0), str(m.get('data',''))))
            for l in backup.get('logs_sistema', []): cur.execute("INSERT INTO logs_sistema (id,acao,detalhes,data,data_iso,usuario) VALUES (?,?,?,?,?,?)", (int(l.get('id') or 0), str(l.get('acao','')), str(l.get('detalhes','')), str(l.get('data','')), str(l.get('data_iso') or parse_data_ptbr(l.get('data')) or data_iso_hoje()), str(l.get('usuario') or 'Não registrado')))
            self.db.conn.commit(); self.db.log("Backup importado", f"Produtos: {len(backup['produtos'])} | Pessoas: {len(backup['pessoas'])} | Movimentações: {len(backup['movimentacoes'])}")
            self.refresh_all(); self.info("Backup importado com sucesso.")
        except Exception as e:
            self.erro("Não foi possível importar o backup: " + str(e))

    def solicitar_senha(self):
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, "Senha de administrador", "Digite a senha de administrador:", QLineEdit.EchoMode.Password)

    def info(self, msg): QMessageBox.information(self, "Controle de Estoque", msg)
    def erro(self, msg): QMessageBox.warning(self, "Controle de Estoque", msg)

    def apply_style(self):
        self.setStyleSheet("""
        QWidget{font-family:Arial;font-size:14px;background:#f2f4f7;color:#222;}
        #sidebar{background:#1d4d2f;min-width:250px;max-width:250px;}
        #sidebarTitle{color:white;background:#1d4d2f;font-size:26px;font-weight:bold;letter-spacing:1px;margin-bottom:8px;}
        #sidebarUser{color:#e7f3eb;background:#1d4d2f;font-size:13px;margin-bottom:10px;}
        #sideButton{background:#2f7a49;color:white;border:none;border-radius:8px;padding:8px 14px;text-align:left;font-size:16px;margin:0;}
        #sideButton:hover{background:#368c55;}
        #pageTitle{font-size:30px;font-weight:bold;margin-bottom:10px;background:transparent;}
        QGroupBox{background:white;border:none;border-radius:15px;margin-top:12px;padding:16px;font-weight:bold;}
        QGroupBox::title{subcontrol-origin:margin;left:16px;padding:0 6px;}
        QLineEdit,QSpinBox,QComboBox,QDateEdit{background:white;border:1px solid #ccc;border-radius:8px;padding:8px;min-height:26px;max-height:38px;}
        QPushButton{background:#2f7a49;color:white;border:none;border-radius:8px;padding:8px 14px;font-size:14px;min-height:28px;max-height:42px;}
        QPushButton:hover{background:#368c55;}
        QPushButton#secondary{background:#777;}
        QPushButton#danger{background:#b3261e;}
        QTableWidget{background:white;border:1px solid #ddd;border-radius:8px;gridline-color:#ddd;}
        QHeaderView::section{background:#f2f4f7;border:1px solid #ddd;padding:8px;font-weight:bold;}
        #card{background:white;border-radius:15px;min-width:250px;max-width:250px;padding:20px;border:1px solid #e5e5e5;}
        #cardTitle{background:transparent;font-size:18px;font-weight:bold;}
        #cardValue{background:transparent;font-size:28px;font-weight:bold;}
        QTextEdit{background:white;border:1px solid #ddd;border-radius:8px;padding:10px;font-family:Consolas,monospace;}
        QMessageBox{background:#ffffff;color:#111111;}
        QMessageBox QLabel{background:transparent;color:#111111;font-size:13px;font-weight:normal;}
        QMessageBox QPushButton{background:#2f7a49;color:#ffffff;border:none;border-radius:7px;padding:7px 14px;min-width:80px;}
        QMessageBox QPushButton:hover{background:#368c55;}
        QInputDialog{background:#ffffff;color:#111111;}
        QInputDialog QLabel{background:transparent;color:#111111;font-size:13px;}
        QInputDialog QLineEdit{background:#ffffff;color:#111111;border:1px solid #b8c0cc;border-radius:8px;padding:8px;selection-background-color:#2f7a49;selection-color:#ffffff;}
        QInputDialog QPushButton{background:#2f7a49;color:#ffffff;border:none;border-radius:7px;padding:7px 14px;min-width:80px;}
        """)


def main():
    app = QApplication(sys.argv)
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    win = MainWindow(login.usuario_logado)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
