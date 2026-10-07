# 🧪 Histórico de Experimentos e Decisões Técnicas

## 📌 Resumo

O desenvolvimento do sistema de roupas do Isometricon envolveu diversas rodadas de prototipagem, testes de regressão, hipóteses matemáticas e medições contra o Roblox Studio. Esta página registra formalmente as abordagens experimentadas, os sucessos, os fracassos e as justificativas técnicas para as decisões adotadas no código final em `src/clothing/`.

---

## 📋 Tabela Geral de Experimentos

| Experimento / Hipótese | O que Testou | Resultado Observado | Decisão Técnica Adotada | Commit / Relatório de Referência |
| :--- | :--- | :--- | :--- | :--- |
| **Heurística de Corte de Membros** | Cortar braços e encolher vértices do corpo sob a roupa por offsets rígidos. | Falhava para roupas novas, decotes ou regatas, criando buracos negros visíveis. | **Descartado totalmente.** O sistema deve manter a geometria original e usar cages volumétricas universais. | `proposta_motor_universal_roupas.md` |
| **Deformação Trilinear Direta** | Interpolar vértices da roupa em caixas delimitadoras tridimensionais (bounding boxes). | Roupas distorciam e colapsavam nas dobras de juntas (cotovelos e joelhos). | **Descartado.** Substituído pelo modelo de casca radial com coordenadas baricêntricas prismáticas. | `bbcc88d` |
| **Runtime WrapLayer Radial 1x** | Projeção puramente radial a partir do centro do membro até a outer cage. | Excelente no tronco, mas gerava estiramento excessivo em barras largas de vestidos e calças skater. | **Evoluído.** Criado campo combinado radial $\leftrightarrow$ global com transição suave. | `b97e252`, `artifacts/clothing_audit/RADIAL_SHELL_DECISION.md` |
| **Vértices Livres / Franjas** | Forçar todos os vértices da roupa a se projetarem na cage do corpo. | Franjas, cordões de saia e barras de vestido rasgavam entre as pernas em movimento. | **Sucesso.** Vértices a $> 3\text{ cm}$ da cage mantêm sua direção e vetor delta originais. | `2c93c51`, `artifacts/roblox_ground_truth/hanging_pants_report.json` |
| **HSR Binário Exclusivo (0x12)** | Utilizar unicamente a máscara binária oficial de HSR presente nos arquivos `.rbxm`. | Roupas do catálogo com formato de malha v2/v3 ou HSR versão 0x10 quebravam e mostravam pele em excesso. | **Sucesso.** Implementado fallback geométrico baseado em raio com margem de segurança. | `58570e9`, `68d056e`, `6e329e8` |
| **Espelhamento em X na Deformação** | Espelhar parâmetros do lado esquerdo para o lado direito para acelerar o cálculo. | Invertia números, textos em camisetas (ex.: '76ers', 'Brooklyn') e bolsos assimétricos. | **Corrigido.** Desativado espelhamento; cada vértice é avaliado individualmente no espaço 3D. | `8e312ad` |
| **Camadas Independentes** | Vestir camisa e calça sem comunicação mútua entre suas malhas. | O cós da calça jeans atravessava a barra do moletom; sobretudos furavam as calças. | **Sucesso.** Criado encadeamento de outer cages (`src/clothing/layer_clearance.py`). | `f3e1812`, `7c13c87`, `d4550aa` |
| **Cage Masculina no Blender** | Construir a cage masculina do zero como um novo modelo. | Incompatibilidade de UV e topologia impedia reaproveitamento de algoritmos da cage feminina. | **Sucesso.** A cage masculina foi gerada preservando rigorosamente a topologia e UVs da feminina. | `8c498e7` até `722de38` |
| **Encaixe de Cabelos por Cage** | Posicionar cabelos puramente por matriz de osso sem usar cage de cabeça. | Cabelos de formatos variados entravam no crânio ou flutuavam nas laterais. | **Sucesso.** Matriz afim do attachment combinada com deformação da cage da cabeça. | `0d7c1dc` |

---

## 🦴 Animação das roupas (30/09 a 06/10/2026)

| Experimento / Hipótese | O que Testou | Resultado Observado | Decisão Técnica Adotada |
| :--- | :--- | :--- | :--- |
| **Remover pele que fura ao animar** | Apagar triângulos de pele cujo vértice cruzava um raio roupa→osso em alguma pose. | Apagava 429 triângulos de pele visível (cropped + jeans), abria buracos. | **Descartado.** A animação nunca remove pele; só o HSR decide. |
| **Suavizar pesos de corpo e roupa (3 variantes)** | Pesos espalhados por difusão na cage e por distância, nos ombros. | A cage é aberta no ombro; a regata piorou; o ponto de pele no sovaco continuou. | **Descartado.** Ombro rígido (braço e manga independentes do tronco). |
| **Blend dos dois lados no ombro e DQS** | Mistura braço/tronco nos dois lados da junta; *dual quaternion skinning*. | Nenhum resolveu o ponto de pele; o tronco passava a ser puxado pelo braço. | **Descartado.** |
| **Regra de HSR para manga que envolve o braço** | Cobrir os pontos da borda aberta da cage do braço quando a manga envolve o membro (16 raios). | Resolveu o ponto de pele no sovaco sem esconder pele em regatas. | **Adotado** (`close_wrapped_limbs`). |
| **Pesos harmônicos sobre a malha da roupa** | Interpolar a parte do membro pela malha da roupa onde o rótulo da cage é incerto. | Manga do cropped deixou de abrir em anel; calça parou de rasgar no quadril e no joelho. | **Adotado** e generalizado para quadris, pernas, saias e casacos. |
| **Edição do Antigravity no rig (isolamento esquerda/direita)** | Cortes por sinal de X nos pesos e reatribuição pelve→coxa. | Melhorou um pouco o sentar e piorou o cós ao andar; sem antes/depois visual. | **Revertido.** Substituído pela mistura harmônica. |
| **Empurrar o tecido para fora das pernas** | Colisão por cápsulas nas pernas a cada quadro. | Só ajudou a saia longa (1162 → 855 cm²) e triplicou o esticado dela. | **Descartado.** |
| **Cauda do casaco seguir a perna ao lado** | Reetiquetar tecido do tronco abaixo do quadril com a perna mais próxima. | Sem efeito: a cauda já seguia as pernas em ~2/3. A pele furando era dos braços. | **Descartado.** |
| **Braços desviarem da roupa larga** | Ângulo de descanso que livra mão e antebraço da roupa que o braço não carrega. | Vestido longo e sobretudo: pele furando de ~700 para 0–300 cm². | **Adotado**, com limite de 30° tirado de um estudo do catálogo. |
| **Reencaixar no braço tecido longe do braço** | Na etapa de encaixe, tecido preso a prisma de braço com resíduo > 3 cm vai para o tronco. | Melhorou o Cloak, mas piorou fantasias de braços grossos e o sobretudo. | **Descartado.** Ficou só a regra da peça de membro e da cadeia da manga. |
| **Pernas da calça larga atravessando o meio** | Tecido entre a perna e o meio do corpo mantém a posição relativa entre os dois. | Calça skater deixou de fundir as pernas (cruzavam o meio até 5 cm). | **Adotado** no encaixe (cache v34). |
| **Medida de buraco sem tecido por baixo** | Pele escondida só é buraco se nada desenhado estiver até 3 cm abaixo dela. | Falhas por buraco de 22 para 6; os pés e golas de fantasias deixaram de contar. | **Adotado.** |
| **Buraco só com superfície em volta / longe de tudo** | Exigir superfície desenhada ao redor (vista de frente) ou distância > 1,5 cm de tudo. | Não separou o contorno da silhueta de um buraco real; zerou o pescoço do suéter. | **Descartado.** |
| **Teste de envolver o membro pelas arestas** | Cobertura angular pelas arestas da malha em vez dos vértices (malhas grosseiras). | Não mudou Baby Shark: o tecido fica atrás do braço, não em volta. | **Descartado.** |
| **Manga precisa de parede junto ao tronco** | Tecido em volta do braço só é manga se houver tecido entre o braço e o tronco. | Cloak: esticado 4829 → 4019; nenhuma outra peça mudou. | **Adotado.** |
| **Braço dentro de saco, pela forma** | Reduzir o balanço se o tecido fecha em volta do antebraço a até 30 cm mas não como manga (3 variantes). | Falsos positivos (cropped, adesivos, terno) e falsos negativos (Baby Shark, Pigeon, Cloak). | **Descartado.** |
| **Balanço dos braços medido** | Ao vestir, medir o tecido que os braços rasgam e escolher 100%, 60% ou 35%. | Cloak e White Cat saem da falha; roupa comum mantém o balanço com limite de 1500 cm² (com 600, camisa e bomber reduziam). | **Adotado.** |
| **Camadas encostadas se movem juntas** | No encaixe, vértices a < 1,5 cm sem aresta em comum recebem o mesmo deslocamento. | Fechou só as frestas junto à fita do Long Dress; os gomos não são camadas encostadas. | **Descartado.** |
| **Forma própria para tecido pendurado** (cache v35/v36) | Tecido fora da cage (saia do Long Dress: 2179 de 3077 vértices) segue rotação e escala únicas ajustadas à cintura e se move como um bloco, em vez do mapa da cage, que estica um eixo 27% a mais. | Long Dress fechou e ficou redondo, mas capas e fantasias encolheram ou cresceram: antebraço da Cloak descoberto (buraco 171 → 818), Pigeon e Squirrel com buracos, Baby Shark masculino rasgando parado. | **Revertido** (cache v37 = encaixe da v34). |
| **Separar saia livre de capa/fantasia** | Aplicar a forma própria só por distância ao corpo, com piso de escala, pelo deslocamento do tecido junto ao corpo, ou pela parte do corpo dentro do tecido. | Nenhum separa Long Dress de Baby Shark; por distância a saia ganha uma dobra no meio. O tipo de asset também não serve (Bear e Goose são tipo vestido). | **Descartado.** Falta um critério por peça. |
