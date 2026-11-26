# Persistência de mundos e construções

O menu mantém um arquivo JSON por mundo em `saves/worlds/`, identificado por UUID. Em um mundo procedural nomeado,
o atalho **R** salva o estado atual, cria outro UUID com nova seed e abre o novo mundo. A aparência do personagem e
as opções de geração acompanham a nova sessão. NPCs, construções e exploração permanecem associados ao mundo
original. O modo `--terrain` sem mundo nomeado mantém X/Z, ficha e ambientação, e carrega as construções da nova seed
em `saves/mundos/`.

Ao carregar pelo menu, o jogo valida o save e prepara terreno, construções e NPCs antes de ativar a sessão. Um
save inválido exibe o erro no menu. Campos opcionais ausentes em saves anteriores usam os padrões do jogo.

Ao importar um `.schem` externo, o jogo guarda uma cópia identificada pelo SHA-256 em `saves/schematics/`.
O save guarda o identificador, o rótulo, a posição, a rotação e as portas abertas. Para transportar os mundos,
copie a pasta de saves inteira, inclusive `schematics/`. A pasta é compartilhada entre mundos e seeds.

Referências externas de saves antigos são migradas quando a fonte original ainda está acessível. Se a fonte
antiga ou a cópia gerenciada estiver indisponível, o jogo mostra um aviso e mantém a entrada para tentar carregar
na próxima abertura. Uma fonte de save antigo que já desapareceu deve ser reposta no caminho original para
permitir a migração. O comando que limpa todas as construções também remove entradas indisponíveis do mundo ativo.
