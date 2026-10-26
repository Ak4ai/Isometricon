# Menus e mundos

Execute `python src/main.py` para abrir o menu inicial. `--menu` também força o menu; `--terrain`, `--char` e as capturas com `--frames` mantêm os modos de diagnóstico existentes.

- Boas-vindas: painel horizontal para desktop, com criar mundo, continuar, configurações, créditos e sair.
- Lista de mundos: botão Excluir por mundo, com confirmação e opção de cancelar; exclui somente o save escolhido.
- Criação: nome e seed numérica ou textual. Seed vazia gera um número aleatório; texto usa SHA-256, de forma estável entre execuções.
- Pausa: ESC durante o jogo, com captura da cena ao fundo. A simulação fica suspensa enquanto qualquer menu está aberto. ESC primeiro fecha chat/editor quando eles estão ativos.
- Controles: cadastro `ACTIONS` em `src/core/game_storage.py`; cada entrada contém ID estável, descrição e tecla padrão. A interface pagina automaticamente. Teclas repetidas são rejeitadas e ESC fica reservado à navegação. O pan continua disponível por Shift + arrastar ou botão central; zoom pela roda também permanece disponível.
- Configurações: VSync, inversão da rotação Q/E, sensibilidade do pan, redução da interpolação da rotação e escala dos textos dos menus. Aplicar grava; sair com alterações abre a opção de descarte. Restaurar padrões só altera o rascunho até Aplicar.
- Som e legendas aparecem como indisponíveis: o motor ainda não implementa esses sistemas.

## O que é salvo

`saves/preferences.json` contém preferências compartilhadas. Cada mundo usa um UUID e arquivo próprio em `saves/worlds/`, com nome, seed, posição do jogador, tempo jogado, data de gravação e aparência/roupas do personagem. Gravação via arquivo temporário e substituição atômica. Arquivos inválidos não impedem abrir a biblioteca.

O terreno é regenerado pela seed. Alterações transitórias dos voxels e o estado de propagação da água não são persistidos nesta versão. O gerador atual deve permanecer compatível para reproduzir o terreno. O salvamento ocorre ao selecionar Salvar e voltar ao menu e ao fechar um mundo normal; não há indicador fictício de autosave. Capturas automatizadas com `--frames` não gravam automaticamente ao encerrar.

## Verificação

`pytest tests/test_game_menus.py -q` cobre seed, persistência, conflitos de teclas, rascunho de preferências e áreas de clique redimensionadas. A aplicação mantém `--screenshot` / `--frames`; `--menu --frames 2 --screenshot menu.png` captura o menu em OpenGL.
