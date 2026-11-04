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


## Identidade visual — atlas de aventuras

O menu inicial tem uma paisagem 3D de apresentação feita com o gerador, mesher e atlas de texturas do jogo. A geração ocorre em uma thread; somente a criação e desenho de recursos OpenGL ocorrem na thread da janela. Essa paisagem não modifica nenhum mundo salvo. A câmera se move lentamente; Reduzir movimento também desativa esse movimento e as transições de painéis.

Os painéis usam papel procedural, cantos ornamentados, sombra, acentos dourados e ícones desenhados em código. Botões respondem ao foco, hover e pressão; o clique só é confirmado ao soltar sobre o mesmo botão. A sensibilidade permite arrastar o slider, e os interruptores mostram o estado do rascunho até Aplicar.

Ao salvar, uma captura da partida é gravada em `saves/worlds/<uuid>.png`, quando disponível. Na ausência de captura, a biblioteca exibe um pequeno mapa gerado da seed. A exclusão de um mundo remove também sua miniatura. O conteúdo dos créditos permanece preservado.


## Resposta da interface

Papel, sombras e vinheta são reutilizados; os painéis das demais telas são preparados em segundo plano junto da paisagem. Textos e miniaturas possuem cache. A paisagem de apresentação usa uma malha combinada.

No modo OpenGL, a interface permanece na resolução lógica: escala, deslocamento e transparência das transições são aplicados na GPU. Hover e pressão enviam somente os retângulos alterados à textura, sem realocar a textura nem reconstruir a imagem por causa do fade. Mudanças de conteúdo ou de página atualizam a imagem inteira. A sincronização vertical só é reconfigurada quando a preferência muda.
