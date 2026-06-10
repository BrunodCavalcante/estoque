COMO GERAR O EXECUTAVEL / INSTALADOR

1) Abra esta pasta no computador Windows.
2) Clique duas vezes em: gerar_exe.bat
3) Aguarde terminar.
4) O sistema pronto ficará em:
   dist\Controle_Estoque\Controle_Estoque.exe

Para usar em outra maquina:
- Copie a pasta inteira dist\Controle_Estoque
- Abra o arquivo Controle_Estoque.exe

PARA GERAR INSTALADOR (.exe de instalar):
1) Instale o Inno Setup no Windows.
2) Primeiro rode gerar_exe.bat.
3) Abra o arquivo gerar_instalador_inno.iss no Inno Setup.
4) Clique em Compile.
5) O instalador será gerado na pasta:
   instalador\Instalador_Controle_Estoque.exe

IMPORTANTE SOBRE O BANCO DE DADOS:
- O arquivo estoque.db fica ao lado do executável.
- Para backup, copie o arquivo estoque.db.
- Para limpar a base, apague o estoque.db com o sistema fechado; ele será recriado vazio.
